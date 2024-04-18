from __future__ import annotations

import concurrent.futures
import hashlib
from typing import TYPE_CHECKING, Any, Dict, List

import boto3
import requests
from botocore.client import Config
from botocore.exceptions import ClientError

from paka.kube_resources.model_group.manifest import Manifest
from paka.kube_resources.model_group.supported_models import SUPPORTED_MODELS
from paka.logger import logger
from paka.utils import read_current_cluster_data, to_yaml

if TYPE_CHECKING:
    from mypy_boto3_s3.client import S3Client

MODEL_PATH_PREFIX = "models"


def delete_s3_file(bucket_name: str, s3_file_name: str) -> None:
    s3 = boto3.client("s3")
    if s3_file_exists(bucket_name, s3_file_name):
        s3.delete_object(Bucket=bucket_name, Key=s3_file_name)
        logger.info(f"{s3_file_name} deleted.")
    else:
        logger.info(f"{s3_file_name} not found.")


def s3_file_exists(bucket_name: str, s3_file_name: str) -> bool:
    s3 = boto3.client("s3")
    try:
        s3.head_object(Bucket=bucket_name, Key=s3_file_name)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            return False
        else:
            raise  # some other error occurred


def s3_file_prefix_exists(bucket_name: str, s3_file_name: str) -> bool:
    s3 = boto3.resource("s3")
    bucket = s3.Bucket(bucket_name)
    return any(bucket.objects.filter(Prefix=s3_file_name))


def save_string_to_s3(bucket_name: str, file_name: str, data: str) -> None:
    s3 = boto3.resource("s3")
    s3.Object(bucket_name, file_name).put(Body=data)


def upload_part(
    s3: "S3Client",
    bucket_name: str,
    s3_file_name: str,
    upload_id: str,
    part_number: int,
    chunk: bytes,
) -> Dict[str, Any]:
    part = s3.upload_part(
        Body=chunk,
        Bucket=bucket_name,
        Key=s3_file_name,
        UploadId=upload_id,
        PartNumber=part_number,
    )
    return {"PartNumber": part_number, "ETag": part["ETag"]}


def download_file_to_s3(
    url: str,
    bucket_name: str,
    s3_file_name: str,
    chunk_size: int = 5 * 1024 * 1024,
    max_parallel_uploads: int = 20,
) -> str:
    """
    Downloads a file from a URL and uploads it to an S3 bucket in chunks.

    This function downloads a file from the specified URL and uploads it to the specified S3 bucket.
    The file is uploaded in chunks of the specified size. The function uses a ThreadPoolExecutor to
    upload the chunks in parallel, with the specified maximum number of parallel uploads.

    The function calculates the SHA256 hash of the file while it is being downloaded and uploaded.
    If the upload is successful, the function returns the SHA256 hash.

    If an error occurs during the download or upload, the function logs the error and raises an exception.
    If an error occurs during the upload, the function aborts the multipart upload.

    Args:
        url (str): The URL to download the file from.
        bucket_name (str): The name of the S3 bucket to upload the file to.
        s3_file_name (str): The name to give to the file in the S3 bucket.
        chunk_size (int, optional): The size of the chunks to upload. Defaults to 5 * 1024 * 1024.
        max_parallel_uploads (int, optional): The maximum number of parallel uploads. Defaults to 20.

    Raises:
        Exception: If an error occurs during the download or upload.

    Returns:
        str: The SHA256 hash of the file.
    """

    s3 = boto3.client("s3", config=Config(signature_version="s3v4"))
    upload_id = None
    upload_completed = False

    try:
        with requests.get(url, stream=True) as response:
            if response.status_code == 200:
                sha256 = hashlib.sha256()
                total_size = int(response.headers.get("content-length", 0))
                processed_size = 0

                upload = s3.create_multipart_upload(
                    Bucket=bucket_name, Key=s3_file_name
                )
                upload_id = upload["UploadId"]
                parts = []

                with concurrent.futures.ThreadPoolExecutor(
                    max_workers=max_parallel_uploads
                ) as executor:
                    futures: List[concurrent.futures.Future] = []
                    part_number = 1

                    for chunk in response.iter_content(chunk_size=chunk_size):
                        sha256.update(chunk)
                        while len(futures) >= max_parallel_uploads:
                            # Wait for one of the uploads to complete
                            done, _ = concurrent.futures.wait(
                                futures, return_when=concurrent.futures.FIRST_COMPLETED
                            )
                            for future in done:
                                parts.append(future.result())
                                futures.remove(future)

                        # Submit new chunk for upload
                        future = executor.submit(
                            upload_part,
                            s3,
                            bucket_name,
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
                s3.complete_multipart_upload(
                    Bucket=bucket_name,
                    Key=s3_file_name,
                    UploadId=upload_id,
                    MultipartUpload={"Parts": parts},
                )

                upload_completed = True
                logger.info(f"File uploaded to S3: {s3_file_name}")
                sha256_value = sha256.hexdigest()
                logger.info(f"SHA256 hash of the file: {sha256_value}")
                return sha256_value
            else:
                error_message = f"Unable to download the file. HTTP Status Code: {response.status_code}"
                logger.error(error_message)
                raise Exception(error_message)

    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        raise

    finally:
        if upload_id is not None and not upload_completed:
            # If an error occurred and upload was not completed
            s3.abort_multipart_upload(
                Bucket=bucket_name, Key=s3_file_name, UploadId=upload_id
            )


def download_model(name: str) -> None:
    """
    Downloads a machine learning model from a URL and uploads it to an S3 bucket.

    This function checks if the model is supported and if it already exists in the S3 bucket.
    If the model is supported and does not exist, the function downloads the model from the URL
    and uploads it to the S3 bucket. The function also saves a manifest file in the S3 bucket
    with metadata about the model.

    If the SHA256 hash of the downloaded file does not match the expected hash, the function
    deletes the file from the S3 bucket and raises an exception.

    Args:
        name (str): The name of the model to download.

    Raises:
        Exception: If the model is not supported or if the SHA256 hash of the downloaded file does not match.

    Returns:
        None
    """

    if name not in SUPPORTED_MODELS:
        logger.error(
            f"Model {name} is not supported."
            f"Available models are: {', '.join(SUPPORTED_MODELS.keys())}"
        )
        raise Exception(f"Model {name} is not supported.")

    model = SUPPORTED_MODELS[name]

    logger.info(f"Downloading model from {model.url}...")
    # Get the model name from the URL
    model_file_name = model.url.split("/")[-1]
    model_path = f"{MODEL_PATH_PREFIX}/{name}"

    full_model_file_path = f"{model_path}/{model_file_name}"
    bucket = read_current_cluster_data("bucket")

    if s3_file_prefix_exists(bucket, f"{model_path}/"):
        logger.info(f"Model {name} already exists.")
        return

    sha256 = download_file_to_s3(model.url, bucket, full_model_file_path)
    if sha256 != model.sha256:
        logger.error(f"SHA256 hash of the downloaded file does not match.")
        # Delete the file
        delete_s3_file(bucket, full_model_file_path)
        raise Exception(f"SHA256 hash of the downloaded file does not match.")

    # Save model manifest
    manifest = Manifest(
        name=name,
        sha256=model.sha256,
        url=model.url,
        type="gguf",  # TODO: hard-coded for now
        file=model_file_name,
    )

    manifest_yaml = to_yaml(manifest.model_dump(exclude_none=True))
    save_string_to_s3(bucket, f"{model_path}/manifest.yaml", manifest_yaml)

    logger.info(f"Model {name} downloaded successfully.")


def get_model_file_name(model_name: str) -> str:
    """
    Returns the file name of a machine learning model.

    This function checks if the model is supported and if so, returns the file name of the model.
    The file name is extracted from the model's URL.

    Args:
        model_name (str): The name of the model.

    Raises:
        Exception: If the model is not supported.

    Returns:
        str: The file name of the model.
    """
    if model_name not in SUPPORTED_MODELS:
        logger.error(
            f"Model {model_name} is not supported."
            f"Available models are: {', '.join(SUPPORTED_MODELS.keys())}"
        )
        raise Exception(f"Model {model_name} is not supported.")

    model = SUPPORTED_MODELS[model_name]

    # Get the model name from the URL
    model_name = model.url.split("/")[-1]
    return model_name
