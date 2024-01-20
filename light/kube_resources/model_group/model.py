import hashlib

import boto3
import requests
from botocore.client import Config
from botocore.exceptions import ClientError

from light.logger import logger
from light.utils import read_current_cluster_data

MODEL_PATH_PREFIX = "models"

SUPPORTED_MODELS = {
    "llama2-7b": "https://huggingface.co/TheBloke/Llama-2-7B-Chat-GGUF/resolve/main/llama-2-7b-chat.Q4_0.gguf",
    "mistral-7b": "https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q4_0.gguf",
    "codellama-7b": "https://huggingface.co/TheBloke/CodeLlama-7B-GGUF/resolve/main/codellama-7b.Q4_0.gguf",
}


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


def download_file_to_s3(
    url: str, bucket_name: str, s3_file_name: str, chunk_size: int = 5 * 1024 * 1024
) -> None:
    """
    Download a file from a URL and upload it to S3 using multipart upload.

    :param url: URL of the file to download.
    :param bucket_name: Name of the S3 bucket.
    :param s3_file_name: Name for the file in S3.
    :param chunk_size: Size of each chunk for multipart upload. Default is 5 MB.
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
                part_number = 1

                for chunk in response.iter_content(chunk_size=chunk_size):
                    sha256.update(chunk)
                    part = s3.upload_part(
                        Body=chunk,
                        Bucket=bucket_name,
                        Key=s3_file_name,
                        UploadId=upload_id,
                        PartNumber=part_number,
                    )
                    parts.append({"PartNumber": part_number, "ETag": part["ETag"]})
                    part_number += 1

                    processed_size += len(chunk)
                    progress = (processed_size / total_size) * 100
                    logger.info(f"Progress: {progress:.2f}%")

                s3.complete_multipart_upload(
                    Bucket=bucket_name,
                    Key=s3_file_name,
                    UploadId=upload_id,
                    MultipartUpload={"Parts": parts},
                )
                upload_completed = True
                logger.info(f"File uploaded to S3: {s3_file_name}")
                sha256_value = sha256.hexdigest()
                logger.info(f"SHA2-256 hash of the file: {sha256_value}")
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
    if name not in SUPPORTED_MODELS:
        logger.error(
            f"Model {name} is not supported."
            f"Available models are: {', '.join(SUPPORTED_MODELS.keys())}"
        )
        raise Exception(f"Model {name} is not supported.")

    url = SUPPORTED_MODELS[name]

    logger.info(f"Downloading model from {url}...")
    # Get the model name from the URL
    model_name = url.split("/")[-1]
    full_model_path = f"{MODEL_PATH_PREFIX}/{model_name}"
    bucket = read_current_cluster_data("bucket")

    if s3_file_exists(bucket, full_model_path):
        logger.info(f"Model {model_name} already exists.")
        return

    download_file_to_s3(url, bucket, full_model_path)


def get_model_file_name(model_name: str) -> str:
    if model_name not in SUPPORTED_MODELS:
        logger.error(
            f"Model {model_name} is not supported."
            f"Available models are: {', '.join(SUPPORTED_MODELS.keys())}"
        )
        raise Exception(f"Model {model_name} is not supported.")

    url = SUPPORTED_MODELS[model_name]

    # Get the model name from the URL
    model_name = url.split("/")[-1]
    return model_name
