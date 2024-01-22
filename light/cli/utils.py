import functools
import os
import re
import subprocess
from typing import Any, Optional

import typer

from light.cluster.manager.aws import AWSClusterManager
from light.cluster.manager.base import ClusterManager
from light.config import parse_yaml
from light.container.ecr import push_to_ecr
from light.container.pack import install_pack
from light.logger import logger
from light.utils import get_pulumi_root, read_current_cluster_data


def build(
    source_dir: str,
    image_name: str,
) -> None:
    # Install pack first
    install_pack()

    # Expand the source_dir path
    source_dir = os.path.abspath(os.path.expanduser(source_dir))

    if not os.path.exists(os.path.join(source_dir, ".cnignore")):
        logger.error(".cnignore file does not exist in the source directory.")
        raise typer.Exit(1)

    if not os.path.exists(os.path.join(source_dir, "Procfile")):
        logger.error("Procfile does not exist in the source directory.")
        raise typer.Exit(1)

    # If image_name is empty, use the directory name of source_dir
    if not image_name:
        image_name = os.path.basename(source_dir)

    logger.info(f"Building image {image_name}...")

    try:
        # Navigate to the application directory
        # (This step may be optional depending on your setup)
        subprocess.run(["cd", source_dir], check=True)

        # Build the application using pack
        subprocess.run(
            ["pack", "build", image_name, "--builder", "paketobuildpacks/builder:base"],
            check=True,
        )
        logger.info(f"Successfully built {image_name}")

        push_to_ecr(
            image_name,
            read_current_cluster_data("registry"),
            read_current_cluster_data("region"),
            image_name,
        )

    except subprocess.CalledProcessError as e:
        logger.error(f"An error occurred: {e}")


def load_cluster_manager(cluster_config: str) -> ClusterManager:
    if not cluster_config:
        cluster_config = "./cluster.yaml"

    cluster_config = os.path.expanduser(cluster_config)
    cluster_config = os.path.abspath(cluster_config)

    if not os.path.exists(cluster_config):
        raise FileNotFoundError(f"The cluster config file does not exist")

    with open(cluster_config, "r") as file:
        config_data = parse_yaml(file.read())

        if config_data.aws:
            return AWSClusterManager(config=config_data)
        else:
            raise ValueError("Unsupported cloud provider")


def validate_name(func: Any) -> Any:
    @functools.wraps(func)
    def wrapper(name: str, *args: Any, **kwargs: Any) -> Any:
        if (
            not re.match(
                r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$",
                name,
            )
            or len(name) > 63
        ):
            logger.info(
                "Invalid name. It must contain no more than 63 characters, contain only lowercase alphanumeric characters or '-', start with an alphanumeric character, and end with an alphanumeric character."
            )
            raise typer.Exit(1)
        return func(name, *args, **kwargs)

    return wrapper


def resolve_image(image: Optional[str], source_dir: Optional[str]) -> str:
    if bool(source_dir) == bool(image):
        logger.error(
            "Exactly one of --source or --image must be provided. Please see --help for more information."
        )
        raise typer.Exit(1)

    result_image = ""

    if not image and source_dir:
        source_dir = os.path.abspath(os.path.expanduser(source_dir))
        result_image = os.path.basename(source_dir)
        build(source_dir, result_image)
        result_image = f"{result_image}-latest"
    elif image:
        result_image = image

    if ":" not in result_image:
        registry_uri = read_current_cluster_data("registry")
        result_image = f"{registry_uri}:{result_image}"

    return result_image


def init_pulumi() -> None:
    os.environ["PULUMI_CONFIG_PASSPHRASE"] = ""
    os.environ["PULUMI_ACCESS_TOKEN"] = "NOT_NEEDED"

    pulumi_root = get_pulumi_root()
    os.makedirs(pulumi_root, exist_ok=True)
    os.environ["PULUMI_ROOT"] = f"file://{pulumi_root}"
