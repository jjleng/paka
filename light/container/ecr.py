import shlex
import subprocess

from light.logger import logger


def push_to_ecr(
    image_name: str, repository_uri: str, aws_region: str, tag: str = "latest"
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

        # Tag the image with the repository URI
        subprocess.run(
            ["docker", "tag", f"{image_name}:{tag}", f"{repository_uri}:{tag}"],
            check=True,
        )

        # Perform Docker login and push in one command
        login_push_cmd = (
            f"echo {shlex.quote(login_password)} | "
            f"docker login --username AWS --password-stdin {repository_uri} && "
            f"docker push {repository_uri}:{tag}"
        )
        subprocess.run(login_push_cmd, shell=True, check=True, executable="/bin/sh")

        logger.info(f"Successfully pushed {image_name} to {repository_uri}")
    except subprocess.CalledProcessError as e:
        logger.error(f"An error occurred: {e}")
        raise
