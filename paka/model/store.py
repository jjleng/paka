from __future__ import annotations

import concurrent.futures
import functools
import hashlib
import re
from abc import ABC, abstractmethod
from io import IOBase
from typing import Any, Callable, Dict, List, TypeVar, Union, cast

import boto3
import requests
from botocore.client import Config
from botocore.exceptions import ClientError
from typing_extensions import TypeAlias

from paka.logger import logger
from paka.model.progress_bar import NullProgressBar, ProgressBar

MODEL_PATH_PREFIX = "models"

StreamLike: TypeAlias = Union[requests.Response, IOBase]

T = TypeVar("T", bound=Callable[..., Any])


def resolve_path(func: T) -> T:
    @functools.wraps(func)
    def wrapper(self: Any, path: str, *args: Any, **kwargs: Any) -> Any:
        resolved_path = (
            f"{MODEL_PATH_PREFIX}/{path}"
            if not path.startswith(f"{MODEL_PATH_PREFIX}/")
            else path
        )
        return func(self, resolved_path, *args, **kwargs)

    return cast(T, wrapper)


class ModelStore(ABC):
    @abstractmethod
    def save_stream(
        self,
        path: str,
        stream: StreamLike,
        total_size: int,
        sha256: str = "",
    ) -> None:
        pass

    @abstractmethod
    def save(self, path: str, data: bytes) -> None:
        pass

    @abstractmethod
    def file_exists(self, path: str, prefix_match: bool = False) -> bool:
        pass

    @abstractmethod
    def delete_file(self, path: str) -> None:
        pass

    @abstractmethod
    def glob(self, path_pattern: str) -> List[str]:
        pass


class S3ModelStore(ModelStore):
    """
    A store for storing models in S3.

    This class provides methods for saving and retrieving models
    from an S3 bucket.
    """

    progress_bar: Union[ProgressBar, NullProgressBar]

    def __init__(
        self,
        s3_bucket: str,
        s3_chunk_size: int = 8 * 1024 * 1024,
        s3_max_concurrency: int = 20,
        with_progress_bar: bool = True,
    ) -> None:
        # s3 bucket
        self.s3_bucket = s3_bucket
        self.s3_chunk_size = s3_chunk_size
        self.s3_max_concurrency = s3_max_concurrency
        self.s3 = boto3.client("s3", config=Config(signature_version="s3v4"))
        self.with_progress_bar = with_progress_bar

        if with_progress_bar:
            self.progress_bar = ProgressBar("Saving model(s) to S3")
        else:
            self.progress_bar = NullProgressBar()

    @resolve_path
    def save(self, path: str, data: bytes) -> None:
        s3 = boto3.resource("s3")
        s3.Object(self.s3_bucket, path).put(Body=data)

    @resolve_path
    def save_stream(
        self,
        path: str,
        stream: StreamLike,
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
        self.progress_bar.create_progress_bar(0)

        self.progress_bar.update_progress_bar(path, total_size)

        try:
            if self.file_exists(path):
                self.progress_bar.advance_progress_bar(path, total_size)
                return

            sha256_value = self._upload_to_s3(stream, path)
            if sha256 and sha256 != sha256_value:
                self.progress_bar.close_progress_bar()

                message = f"SHA256 hash of the downloaded file does not match the expected value for {path}"
                # Log the error message so that users know why the file was deleted
                logger.error(message)
                self.delete_file(path)

                raise Exception(message)

            if not self.with_progress_bar:
                logger.info(f"Model file {path} is saved successfully.")
            self.progress_bar.advance_progress_bar(path, total_size)
        except Exception:
            self.progress_bar.close_progress_bar()
            raise

    def _upload_to_s3(
        self,
        stream: StreamLike,
        s3_file_name: str,
    ) -> str:
        """
        Uploads a single file to S3.

        Args:
            response (requests.Response | FileStream): The response object from the file download or the file stream object.
            s3_file_name (str): The name of the file in S3.

        Returns:
            str: The SHA256 hash of the uploaded file.
        """
        upload_id = None
        upload_completed = False
        try:
            self.progress_bar.set_postfix_str(s3_file_name)

            sha256 = hashlib.sha256()
            processed_size = 0
            parts = []

            upload = self.s3.create_multipart_upload(
                Bucket=self.s3_bucket, Key=s3_file_name
            )
            upload_id = upload["UploadId"]

            with concurrent.futures.ThreadPoolExecutor(
                max_workers=self.s3_max_concurrency
            ) as executor:
                futures: List[concurrent.futures.Future] = []
                part_number = 1

                if isinstance(stream, requests.Response):
                    chunks = stream.iter_content(chunk_size=self.s3_chunk_size)
                else:
                    response_io = cast(IOBase, stream)
                    chunks = iter(lambda: response_io.read(self.s3_chunk_size), b"")

                for chunk in chunks:
                    sha256.update(chunk)
                    while len(futures) >= self.s3_max_concurrency:
                        done, _ = concurrent.futures.wait(
                            futures, return_when=concurrent.futures.FIRST_COMPLETED
                        )
                        for future in done:
                            parts.append(future.result())
                            futures.remove(future)

                    future = executor.submit(
                        self._upload_part,
                        s3_file_name,
                        upload_id,
                        part_number,
                        chunk,
                    )
                    futures.append(future)
                    part_number += 1
                    processed_size += len(chunk)
                    self.progress_bar.advance_progress_bar(s3_file_name, processed_size)

                for future in concurrent.futures.as_completed(futures):
                    parts.append(future.result())

            parts.sort(key=lambda part: part["PartNumber"])
            self.s3.complete_multipart_upload(
                Bucket=self.s3_bucket,
                Key=s3_file_name,
                UploadId=upload_id,
                MultipartUpload={"Parts": parts},
            )
            upload_completed = True

            sha256_value = sha256.hexdigest()
            return sha256_value

        except Exception as e:
            raise e

        finally:
            if upload_id is not None and not upload_completed:
                self.s3.abort_multipart_upload(
                    Bucket=self.s3_bucket, Key=s3_file_name, UploadId=upload_id
                )

    def _upload_part(
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

    @resolve_path
    def file_exists(self, path: str, prefix_match: bool = False) -> bool:
        """
        Checks if a file exists in the S3 bucket.

        Args:
            path (str): The path of the file in the S3 bucket.
            prefix_match (bool, optional): If True, checks if any file with the given path prefix exists.
                Defaults to False.

        Returns:
            bool: True if the file exists, False otherwise.
        """
        if prefix_match:
            s3 = boto3.resource("s3")
            bucket = s3.Bucket(self.s3_bucket)
            return any(bucket.objects.filter(Prefix=path))

        try:
            self.s3.head_object(Bucket=self.s3_bucket, Key=path)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            else:
                raise  # some other error occurred

    @resolve_path
    def delete_file(self, path: str) -> None:
        """
        Deletes the specified file from the S3 bucket.

        Args:
            path (str): The path of the file to be deleted.

        Returns:
            None
        """
        if self.file_exists(path):
            self.s3.delete_object(Bucket=self.s3_bucket, Key=path)
            logger.info(f"{path} deleted.")
        else:
            logger.info(f"{path} not found.")

    @resolve_path
    def glob(self, path_pattern: str) -> List[str]:
        """
        Lists all files in the S3 bucket that match the specified pattern.

        Args:
            path_pattern (str): The pattern to match.

        Returns:
            List[str]: A list of file paths that match the pattern.
        """
        s3 = boto3.resource("s3")
        bucket = s3.Bucket(self.s3_bucket)

        pattern = re.compile(path_pattern)
        return [obj.key for obj in bucket.objects.all() if pattern.match(obj.key)]
