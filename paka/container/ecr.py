import base64
import subprocess

import boto3

from paka.logger import logger
from paka.utils import random_str


def authenticate_docker_to_ecr(aws_region: str) -> str:
    try:
        ecr_client = boto3.client("ecr", region_name=aws_region)
        token = ecr_client.get_authorization_token()
        username, password = (
            base64.b64decode(token["authorizationData"][0]["authorizationToken"])
            .decode("utf-8")
            .split(":")
        )
        ecr_url = token["authorizationData"][0]["proxyEndpoint"]

        p = subprocess.Popen(
            ["docker", "login", "-u", username, "--password-stdin", ecr_url],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = p.communicate(input=password.encode())
        if p.returncode != 0:
            raise Exception(f"Docker login failed: {stderr.decode()}")

        return ecr_url
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        raise


def push_to_ecr(
    image_name: str, repository_uri: str, aws_region: str, app_name: str
) -> str:
    """
    Pushes a Docker image to an Amazon ECR repository.

    This function tags the Docker image with a version tag and the "latest" tag,
    logs in to the ECR repository, and pushes the image to the repository.
    The version tag is generated randomly.

    All applications share the same container registry repository.
    To differentiate between them, we append the application name to the image tag.
    The '-latest' suffix is added to handle cases where applications themselves are tagged.
    This ensures that even tagged applications have a unique identifier in the shared repository.

    Args:
        image_name (str): The name of the Docker image to push.
        repository_uri (str): The URI of the ECR repository to push the image to.
        aws_region (str): The AWS region where the ECR repository is located.
        app_name (str): The name of the application. Used to generate the image tags.

    Raises:
        subprocess.CalledProcessError: If an error occurs while executing a subprocess command.

    Returns:
        str: The version tag of the image that was pushed.
    """
    try:
        # Generate a random version number
        version = random_str()

        # Tag the image with the repository URI and the version tag
        version_tag = f"{app_name}-v{version}"

        # Tag the image with the repository URI
        subprocess.run(
            [
                "docker",
                "tag",
                f"{image_name}:latest",
                f"{repository_uri}:{version_tag}",
            ],
            check=True,
        )

        # Tag the image with the repository URI and the "latest" tag
        latest_tag = f"{app_name}-latest"
        subprocess.run(
            [
                "docker",
                "tag",
                f"{image_name}:latest",
                f"{repository_uri}:{latest_tag}",
            ],
            check=True,
        )

        # Authenticate Docker to the ECR
        authenticate_docker_to_ecr(aws_region)

        # Push the image to the ECR repository
        subprocess.run(
            ["docker", "push", f"{repository_uri}:{version_tag}"], check=True
        )
        subprocess.run(["docker", "push", f"{repository_uri}:{latest_tag}"], check=True)

        logger.info(f"Successfully pushed {image_name} to {repository_uri}")
        return version_tag
    except subprocess.CalledProcessError as e:
        logger.error(f"An error occurred: {e}")
        raise
