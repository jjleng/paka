import concurrent.futures
import hashlib
from threading import Lock
from typing import Any, Dict, List

import boto3
import requests
from botocore.client import Config
from botocore.exceptions import ClientError
from tqdm import tqdm

from paka.logger import logger
from paka.utils import read_current_cluster_data

MODEL_PATH_PREFIX = "models"


class Model:
    def __init__(
        self,
        name: str,
        inference_devices: list[str] = ["cpu"],
        quantization: str = "GPTQ",
        runtime: str = "llama.cpp",
        prompt_template: str = "chatml",
        download_max_concurrency: int = 10,
        s3_chunk_size: int = 8 * 1024 * 1024,
        s3_max_concurrency: int = 20,
    ) -> None:
        """
        Initializes a Model object.

        Args:
            name (str): The name of the model, repository id.
            inference_devices (list[str], optional): The list (cpu, gpu, tpu, etc) of inference devices to use. Defaults to ['cpu'].
            quantization (str, optional): The quantization method (GPTQ, AWQ, GGUF_Q4_0, etc) to use. Defaults to 'GPTQ'.
            runtime (str, optional): The runtime (vLLM, pytorch, etc) to use. Defaults to 'llama.cpp'.
            prompt_template (str, optional): The prompt template (chatml, llama-2, gemma, etc) to use. Defaults to 'chatml'.
            download_max_concurrency (int, optional): The maximum number of concurrent downloads. Defaults to 10.
            s3_chunk_size (int, optional): The size of each chunk to upload to S3 in bytes. Defaults to 8 * 1024 * 1024.
            s3_max_concurrency (int, optional): The maximum number of concurrent uploads to S3. Defaults to 20.
        """
        # model info
        self.name = name
        self.inference_devices = inference_devices
        self.quantization = quantization
        self.runtime = runtime
        self.prompt_template = prompt_template

        # s3 bucket
        self.s3_bucket = read_current_cluster_data("bucket")
        self.s3_chunk_size = s3_chunk_size
        self.download_max_concurrency = download_max_concurrency
        self.s3_max_concurrency = s3_max_concurrency
        self.s3 = boto3.client("s3", config=Config(signature_version="s3v4"))
        # Shared counter
        self.counter: dict[str, int] = {}
        self.counter_lock = Lock()
        self.pbar: tqdm = None
        self.completed_files: list[tuple[str, str]] = []

    def get_s3_file_path(self, file_path: str) -> str:
        """
        Returns the S3 file path for a given file name.

        Args:
            file_path (str): The path of the file.

        Returns:
            str: The S3 file path.
        """
        return f"{MODEL_PATH_PREFIX}/{file_path}"

    def download(
        self,
        url: str,
        response: requests.Response | Any,
        total_size: int,
        sha256: str = "",
    ) -> None:
        """
        Downloads a single file from a URL.

        Args:
            url (str): The URL of the file to download.
            sha256 (str, optional): The expected SHA256 hash of the downloaded file.

        Raises:
            Exception: If the SHA256 hash of the downloaded file does not match the expected value.
        """
        with self.counter_lock:
            if self.pbar is None:
                self.create_pbar(total_size)

        full_model_file_path = self.get_s3_file_path(
            f"{self.name}/{url.split('/')[-1]}"
        )

        upload_id = None
        file_uploaded = False
        try:
            if full_model_file_path not in self.counter:
                with self.counter_lock:
                    if self.pbar is not None:
                        self.pbar.total += total_size
                        self.pbar.refresh()

            if self.s3_file_exists(full_model_file_path):
                logger.info(f"Model source already exists in {full_model_file_path}.")
                self.update_progress(full_model_file_path, total_size)
                return

            upload = self.s3.create_multipart_upload(
                Bucket=self.s3_bucket, Key=full_model_file_path
            )
            upload_id = upload["UploadId"]
            sha256_value = self.upload_to_s3(response, full_model_file_path, upload_id)
            if sha256 and sha256 != sha256_value:
                self.delete_s3_file(full_model_file_path)
                raise Exception(
                    f"SHA256 hash of the downloaded file does not match the expected value. {full_model_file_path}"
                )
            file_uploaded = True
        except Exception as e:
            self.logging_for_class(f"An error occurred: {str(e)}", "error")
            raise e
        finally:
            # If an error occurred and upload was not completed
            if upload_id is not None and not file_uploaded:
                self.s3.abort_multipart_upload(
                    Bucket=self.s3_bucket, Key=full_model_file_path, UploadId=upload_id
                )
            else:
                self.logging_for_class(
                    f"Model file {full_model_file_path} uploaded successfully."
                )
                self.completed_files.append((url, sha256))
                self.update_progress()

    def upload_to_s3(
        self,
        response: Any,
        s3_file_name: str,
        upload_id: str,
    ) -> str:
        """
        Uploads a single file to S3.

        Args:
            response (requests.Response | FileStream): The response object from the file download or the file stream object.
            s3_file_name (str): The name of the file in S3.
            upload_id (str): The upload ID of the multipart upload.

        Returns:
            str: The SHA256 hash of the uploaded file.
        """
        try:
            self.pbar.postfix = f"{s3_file_name}"
            sha256 = hashlib.sha256()
            processed_size = 0
            parts = []

            with concurrent.futures.ThreadPoolExecutor(
                max_workers=self.s3_max_concurrency
            ) as executor:
                futures: List[concurrent.futures.Future] = []
                part_number = 1
                for chunk in (
                    response.iter_content(chunk_size=self.s3_chunk_size)
                    if "Response" in str(response)
                    else iter(lambda: response.read(self.s3_chunk_size), b"")
                ):
                    sha256.update(chunk)
                    while len(futures) >= self.s3_max_concurrency:
                        done, _ = concurrent.futures.wait(
                            futures, return_when=concurrent.futures.FIRST_COMPLETED
                        )
                        for future in done:
                            parts.append(future.result())
                            futures.remove(future)

                    future = executor.submit(
                        self.upload_part,
                        s3_file_name,
                        upload_id,
                        part_number,
                        chunk,
                    )
                    futures.append(future)
                    part_number += 1
                    processed_size += len(chunk)
                    self.update_progress(s3_file_name, processed_size)

                for future in concurrent.futures.as_completed(futures):
                    parts.append(future.result())

            parts.sort(key=lambda part: part["PartNumber"])
            self.s3.complete_multipart_upload(
                Bucket=self.s3_bucket,
                Key=s3_file_name,
                UploadId=upload_id,
                MultipartUpload={"Parts": parts},
            )

            sha256_value = sha256.hexdigest()
            return sha256_value
        except Exception as e:
            self.logging_for_class(
                f"An error occurred in upload_to_s3: {str(e)}", "error"
            )
            raise e

    def upload_part(
        self,
        s3_file_name: str,
        upload_id: str,
        part_number: int,
        chunk: bytes,
    ) -> Dict[str, Any]:
        """
        Uploads a part of a file to S3.

        Args:
            s3_file_name (str): The name of the file in S3.
            upload_id (str): The upload ID of the multipart upload.
            part_number (int): The part number of the chunk being uploaded.
            chunk (bytes): The chunk of data to upload.

        Returns:
            dict: A dictionary containing the part number and the ETag of the uploaded part.
        """
        part = self.s3.upload_part(
            Body=chunk,
            Bucket=self.s3_bucket,
            Key=s3_file_name,
            UploadId=upload_id,
            PartNumber=part_number,
        )
        return {"PartNumber": part_number, "ETag": part["ETag"]}

    def s3_file_exists(self, s3_file_name: str) -> bool:
        """
        Checks if a file exists in S3.

        Args:
            s3_file_name (str): The name of the file in S3.

        Returns:
            bool: True if the file exists, False otherwise.
        """
        try:
            self.s3.head_object(Bucket=self.s3_bucket, Key=s3_file_name)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            else:
                raise  # some other error occurred

    def s3_file_prefix_exists(self, s3_file_name: str) -> bool:
        """
        Checks if a file prefix exists in S3.

        Args:
            s3_file_name (str): The prefix of the file name in S3.

        Returns:
            bool: True if the file prefix exists, False otherwise.
        """
        bucket = self.s3.Bucket(self.s3_bucket)
        return any(bucket.objects.filter(Prefix=s3_file_name))

    def delete_s3_file(self, s3_file_name: str) -> None:
        """
        Deletes the specified file from the S3 bucket.

        Args:
            s3_file_name (str): The name of the file to be deleted.

        Returns:
            None
        """
        if self.s3_file_exists(s3_file_name):
            self.s3.delete_object(Bucket=self.s3_bucket, Key=s3_file_name)
            logger.info(f"{s3_file_name} deleted.")
        else:
            logger.info(f"{s3_file_name} not found.")

    def clear_counter(self) -> None:
        with self.counter_lock:
            self.counter = {}

    def create_pbar(self, total_size: int) -> None:
        self.pbar = tqdm(total=total_size, unit="B", unit_scale=True, desc="Uploading")

    def close_pbar(self) -> None:
        self.pbar.close()
        self.pbar = None

    def update_progress(self, key: str = "", value: int = 0) -> None:
        with self.counter_lock:
            if key:
                self.counter[key] = value
            total_progress = sum(self.counter.values())
            self.pbar.update(total_progress - self.pbar.n)

    def logging_for_class(self, message: str, type: str = "info") -> None:
        """
        Logs an informational message.

        Args:
            message (str): The message to log.

        Returns:
            None
        """
        if type == "info":
            logger.info(f"{self.__str__()} ({self.name}): {message}")
        elif type == "warn":
            logger.warn(f"{self.__str__()} ({self.name}): {message}")
        elif type == "error":
            logger.error(f"{self.__str__()} ({self.name}): {message}")
        else:
            logger.info(f"{self.__str__()} ({self.name}): {message}")
