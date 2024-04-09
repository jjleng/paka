import concurrent.futures
import hashlib
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List

import boto3
import requests
from botocore.client import BaseClient, Config
from botocore.exceptions import ClientError

from paka.logger import logger
from paka.utils import get_item, read_current_cluster_data

MODEL_PATH_PREFIX = "models"


class Model:
    def __init__(
        self,
        name: str,
        download_max_concurrency: int = 10,
        s3_chunk_size: int = 8 * 1024 * 1024,
        s3_max_concurrency: int = 20,
    ):
        """
        Initializes a Model object.

        Args:
            name (str): The name of the model, repository id.
            download_max_concurrency (int): The maximum number of concurrent downloads.
            s3_chunk_size (int): The size of each chunk to upload to S3 in bytes.
            s3_max_concurrency (int): The maximum number of concurrent uploads to S3.
        """
        self.name = name
        self.bucket = read_current_cluster_data("bucket")
        self.s3_chunk_size = s3_chunk_size
        self.download_max_concurrency = download_max_concurrency
        self.s3_max_concurrency = s3_max_concurrency
        self.s3 = boto3.client("s3", config=Config(signature_version="s3v4"))

    def download(self, url: str, sha256: str | None = None) -> None:
        """
        Downloads a single file from a URL.

        Args:
            url (str): The URL of the file to download.
            sha256 (str, optional): The expected SHA256 hash of the downloaded file.

        Raises:
            Exception: If the SHA256 hash of the downloaded file does not match the expected value.
        """
        full_model_file_path = f"{MODEL_PATH_PREFIX}/{self.name}/{url.split('/')[-1]}"
        if self.s3_file_exists(full_model_file_path):
            logger.info(f"Model file {full_model_file_path} already exists.")
            return

        logger.info(f"Downloading model from {url}")
        completed_upload_id = None
        try:
            with requests.get(url, stream=True) as response:
                response.raise_for_status()
                upload_id, sha256_value = self.upload_to_s3(
                    response, full_model_file_path
                )
                if sha256 is not None and sha256 != sha256_value:
                    raise Exception(
                        f"SHA256 hash of the downloaded file does not match the expected value. {full_model_file_path}"
                    )
                completed_upload_id = upload_id
        except Exception as e:
            logger.error(f"An error occurred, download: {str(e)}")
            raise e
        finally:
            # If an error occurred and upload was not completed
            if completed_upload_id is None:
                self.s3.abort_multipart_upload(
                    Bucket=self.bucket, Key=full_model_file_path, UploadId=upload_id
                )

    def upload_to_s3(
        self, response: requests.Response, s3_file_name: str
    ) -> tuple[Any, str]:
        """
        Uploads a single file to S3.

        Args:
            response (requests.Response): The response object from the file download.
            s3_file_name (str): The name of the file in S3.

        Returns:
            tuple: A tuple containing the upload ID and the SHA256 hash of the file.
        """
        logger.info(f"Uploading model to {s3_file_name}")
        sha256 = hashlib.sha256()
        total_size = int(response.headers.get("content-length", 0))
        processed_size = 0

        upload = self.s3.create_multipart_upload(Bucket=self.bucket, Key=s3_file_name)
        upload_id = upload["UploadId"]
        parts = []

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.s3_max_concurrency
        ) as executor:
            futures: List[concurrent.futures.Future] = []
            part_number = 1

            for chunk in response.iter_content(chunk_size=self.s3_chunk_size):
                sha256.update(chunk)
                while len(futures) >= self.s3_max_concurrency:
                    # Wait for one of the uploads to complete
                    done, _ = concurrent.futures.wait(
                        futures, return_when=concurrent.futures.FIRST_COMPLETED
                    )
                    for future in done:
                        parts.append(future.result())
                        futures.remove(future)

                # Submit new chunk for upload
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
                progress = (processed_size / total_size) * 100
                print(f"Progress: {progress:.2f}%", end="\r")

            # Wait for all remaining uploads to complete
            for future in concurrent.futures.as_completed(futures):
                parts.append(future.result())

        parts.sort(key=lambda part: part["PartNumber"])
        self.s3.complete_multipart_upload(
            Bucket=self.bucket,
            Key=s3_file_name,
            UploadId=upload_id,
            MultipartUpload={"Parts": parts},
        )

        logger.info(f"File uploaded to S3: {s3_file_name}")
        sha256_value = sha256.hexdigest()
        logger.info(f"SHA256 hash of the file: {sha256_value}")
        return upload_id, sha256_value

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
            Bucket=self.bucket,
            Key=s3_file_name,
            UploadId=upload_id,
            PartNumber=part_number,
        )
        return {"PartNumber": part_number, "ETag": part["ETag"]}

    def download_all(self, urls: list[str], sha256s: list[str | None] = []) -> None:
        """
        Downloads multiple files from a list of URLs.

        Args:
            urls (list[str]): A list of URLs of the files to download.
            sha256s (list[str], optional): A list of expected SHA256 hashes for the downloaded files.
        """
        with ThreadPoolExecutor(max_workers=self.download_max_concurrency) as executor:
            executor.map(
                lambda url, index: self.download(url, get_item(sha256s, index)),
                urls,
                range(len(urls)),
            )

    def s3_file_exists(self, s3_file_name: str) -> bool:
        """
        Checks if a file exists in S3.

        Args:
            s3_file_name (str): The name of the file in S3.

        Returns:
            bool: True if the file exists, False otherwise.
        """
        s3 = boto3.client("s3")
        try:
            s3.head_object(Bucket=self.bucket, Key=s3_file_name)
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
        s3 = boto3.resource("s3")
        bucket = s3.Bucket(self.bucket)
        return any(bucket.objects.filter(Prefix=s3_file_name))
