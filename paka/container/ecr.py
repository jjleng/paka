import shlex
import subprocess

from paka.logger import logger
from paka.utils import random_str


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
        # Get ECR login password
        login_password = (
            subprocess.check_output(
                ["aws", "ecr", "get-login-password", "--region", aws_region]
            )
            .decode()
            .strip()
        )

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

        # Perform Docker login and push in one command
        login_push_cmd = (
            f"echo {shlex.quote(login_password)} | "
            f"docker login --username AWS --password-stdin {repository_uri} && "
            f"docker push {repository_uri}:{version_tag} && "
            f"docker push {repository_uri}:{latest_tag}"
        )
        subprocess.run(login_push_cmd, shell=True, check=True, executable="/bin/sh")

        logger.info(f"Successfully pushed {image_name} to {repository_uri}")
        return version_tag
    except subprocess.CalledProcessError as e:
        logger.error(f"An error occurred: {e}")
        raise
