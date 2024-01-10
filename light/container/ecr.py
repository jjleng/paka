import random
import shlex
import string
import subprocess

from light.logger import logger


def generate_random_version(length: int = 5) -> str:
    # Generate a random string of the specified length
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


def push_to_ecr(
    image_name: str, repository_uri: str, aws_region: str, app_name: str
) -> None:
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
        version = generate_random_version()

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
    except subprocess.CalledProcessError as e:
        logger.error(f"An error occurred: {e}")
        raise
