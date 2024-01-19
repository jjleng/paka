import boto3
import requests
import typer
from botocore.exceptions import ClientError, NoCredentialsError

from light.k8s import try_load_kubeconfig
from light.kube_resources.model_group.service import MODEL_PATH_PREFIX
from light.logger import logger
from light.utils import read_current_cluster_data

try_load_kubeconfig()

model_app = typer.Typer()

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


def download_file_to_s3(url: str, bucket_name: str, s3_file_name: str) -> None:
    s3 = boto3.client("s3")

    try:
        response = requests.get(url, stream=True)

        if response.status_code == 200:
            # Upload file in chunks
            s3.upload_fileobj(
                Fileobj=response.raw, Bucket=bucket_name, Key=s3_file_name
            )
            print(f"File uploaded to S3: {s3_file_name}")
        else:
            print(
                f"Unable to download the file. HTTP Status Code: {response.status_code}"
            )

    except NoCredentialsError:
        print("Credentials not available")


@model_app.command(help="Download a model and save it to object store.")
def download(
    url: str = typer.Option(
        "",
        "--url",
        help="The URL to download the model from. Only GGUF models are supported for now.",
    ),
    name: str = typer.Option(
        "",
        "--name",
        help="The name of the model.",
    ),
) -> None:
    if not url and not name:
        logger.error(
            "Either --url or --name must be provided. Please see --help for more information."
        )
        raise typer.Exit(1)
    elif name:
        # Make sure the model name is valid
        if name not in SUPPORTED_MODELS:
            logger.error(
                f"Model {name} is not supported."
                f"Available models are: {', '.join(SUPPORTED_MODELS.keys())}"
            )
            raise typer.Exit(1)
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


@model_app.command(help="List the models available for download.")
def list() -> None:
    for model_name in SUPPORTED_MODELS:
        logger.info(model_name)


@model_app.command(help="List the models downloaded to object store.")
def list_downloaded() -> None:
    bucket = read_current_cluster_data("bucket")
    s3 = boto3.client("s3")
    response = s3.list_objects_v2(Bucket=bucket, Prefix=MODEL_PATH_PREFIX)
    if "Contents" in response:
        for obj in response["Contents"]:
            key = obj["Key"]
            if key.startswith(f"{MODEL_PATH_PREFIX}/"):
                key = key[len(f"{MODEL_PATH_PREFIX}/") :]
            logger.info(key)
    else:
        logger.info("No models found.")
