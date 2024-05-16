from __future__ import annotations

import functools
import os
import platform
import re
import subprocess
from datetime import timedelta
from typing import Any, Optional

import typer
from kubernetes import config as k8s_config

from paka.cluster.manager.aws import AWSClusterManager
from paka.cluster.manager.base import ClusterManager
from paka.config import CloudConfig, Config, parse_yaml
from paka.constants import BP_BUILDER_ENV_VAR
from paka.container.ecr import push_to_ecr
from paka.container.pack import ensure_pack
from paka.logger import logger
from paka.utils import get_pulumi_root, read_pulumi_stack


def build_and_push(
    cluster_name: Optional[str],
    source_dir: str,
    image_name: str,
) -> str:
    """
    Builds a Docker image from the source code in the specified directory.

    This function uses the Cloud Native Buildpacks (pack) tool to build a Docker image from the source code
    in the specified directory. The resulting image is then pushed to the Amazon Elastic Container Registry (ECR).

    Args:
        cluster_name (str): The name of the cluster to build the image for.
        source_dir (str): The directory containing the source code of the application.
        image_name (str): The name of the Docker image to build. If not provided, the name of the source directory is used.

    Returns:
        str: The image tag of the built Docker image.
    """
    pack_bin = ensure_pack()

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

    # Parse runtime.txt and set BP_CPYTHON_VERSION
    runtime_path = os.path.join(source_dir, "runtime.txt")
    bp_cpython_version = None
    bp_node_version = None
    if os.path.exists(runtime_path):
        with open(runtime_path, "r") as file:
            content = file.read()
            match = re.search(r"python-(\d+\.\d+(\.\d+|\.\*))", content)
            if match:
                bp_cpython_version = match.group(1)
            else:
                match = re.search(r"nodejs-(\d+\.\d+(\.\d+|\.\*))", content)
                if match:
                    bp_node_version = match.group(1)

    try:
        if not os.path.exists(source_dir):
            logger.error(f"Source directory {source_dir} does not exist.")
            raise typer.Exit(1)

        builder = os.environ.get(BP_BUILDER_ENV_VAR, "paketobuildpacks/builder:base")

        pack_command = [
            pack_bin,
            "build",
            image_name,
            "--builder",
            builder,
        ]
        if bp_cpython_version:
            pack_command.extend(["--env", f"BP_CPYTHON_VERSION={bp_cpython_version}"])
        elif bp_node_version:
            pack_command.extend(["--env", f"BP_NODE_VERSION={bp_node_version}"])

        subprocess.run(pack_command, cwd=source_dir, check=True)
        logger.info(f"Successfully built {image_name}")

        cluster_name = ensure_cluster_name(cluster_name)

        return push_to_ecr(
            image_name,
            read_pulumi_stack(cluster_name, "registry"),
            read_pulumi_stack(cluster_name, "region"),
            image_name,
        )

    except subprocess.CalledProcessError as e:
        logger.error(f"An error occurred: {e}")
        raise typer.Exit(1)


def load_cluster_config(cluster_config_file: Optional[str]) -> Optional[Config]:
    if not cluster_config_file:
        cluster_config_file = "./cluster.yaml"
    cluster_config_file = os.path.abspath(os.path.expanduser(cluster_config_file))
    if not os.path.exists(cluster_config_file):
        return None

    with open(cluster_config_file, "r") as file:
        config = parse_yaml(file.read())
        return config


def load_cluster_manager(cluster_config: str) -> ClusterManager:
    """
    Loads the cluster manager based on the provided cluster configuration YAML file.

    This function reads the cluster configuration file, parses it as YAML, and then
    creates and returns a cluster manager object based on the cloud provider specified
    in the configuration. Currently, only AWS is supported.

    Args:
        cluster_config (str): The path to the cluster configuration file. If not
        provided, defaults to "./cluster.yaml".

    Returns:
        ClusterManager: An instance of the cluster manager corresponding to the
        cloud provider specified in the configuration.

    Raises:
        FileNotFoundError: If the cluster configuration file does not exist.
        ValueError: If the cloud provider specified in the configuration is not supported.
    """
    config_data = load_cluster_config(cluster_config)

    if not config_data:
        raise FileNotFoundError(f"The cluster config file does not exist")

    if config_data.aws:
        return AWSClusterManager(config=config_data)
    else:
        raise ValueError("Unsupported cloud provider")


def validate_name(func: Any) -> Any:
    """
    Decorator to validate the name argument of a function.

    This decorator checks if the name argument of the decorated function matches
    the specified regular expression and is not longer than 63 characters. If
    the name is invalid, it logs an error message and exits the program.

    Args:
        func (Any): The function to decorate.

    Returns:
        Any: The decorated function.
    """

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
                "Invalid name. It must contain no more than 63 characters, contain "
                "only lowercase alphanumeric characters or '-', start with an "
                "alphanumeric character, and end with an alphanumeric character."
            )
            raise typer.Exit(1)
        return func(name, *args, **kwargs)

    return wrapper


def resolve_image(
    cluster_name: Optional[str], image: Optional[str], source_dir: Optional[str]
) -> str:
    """
    Determines the Docker image to be utilized by either using the provided image
    directly or by building an image from the specified source directory.

    This function checks if exactly one of image or source_dir is provided. If
    both or neither are provided, it logs an error message and exits the program.
    If only source_dir is provided, it builds the Docker image from the source
    directory and sets the image name to the base name of the source directory.
    If only image is provided, it uses the provided image name. If the image
    name does not contain a tag, it adds the default tag 'latest'.

    Args:
        image (Optional[str]): The name of the Docker image to use. If not
            provided, a Docker image is built from the source directory.
        source_dir (Optional[str]): The path to the source directory to build the
            Docker image from. If not provided, the provided image name is used.

    Returns:
        str: The resolved Docker image name.

    Raises:
        typer.Exit: If both or neither image and source_dir are provided.
    """
    if bool(source_dir) == bool(image):
        logger.error(
            "Exactly one of --source or --image must be provided. Please see --help for more information."
        )
        raise typer.Exit(1)

    result_image = ""

    if not image and source_dir:
        source_dir = os.path.abspath(os.path.expanduser(source_dir))
        result_image = os.path.basename(source_dir)
        result_image = build_and_push(cluster_name, source_dir, result_image)
    elif image:
        result_image = image

    # If a fully qualified image name is provided, use it directly. This gives users
    # the flexibility to use images from other registries. Otherwise, the image is assumed
    # to be located in the default registry and will be retrieved from there.
    cluster_name = ensure_cluster_name(cluster_name)
    if ":" not in result_image:
        registry_uri = read_pulumi_stack(cluster_name, "registry")
        result_image = f"{registry_uri}:{result_image}"

    return result_image


def init_pulumi() -> None:
    """
    Initializes Pulumi by setting up necessary environment variables and creating
    the Pulumi state root directory.

    This function sets the Pulumi configuration passphrase and backend URL
    environment variables. If these variables are not already set in the
    environment, it assigns them default values. The default value for the
    passphrase is an empty string, and the default for the backend URL is a
    file URL pointing to the Pulumi root directory.

    The Pulumi root directory is created if it does not already exist.
    """
    os.environ["PULUMI_CONFIG_PASSPHRASE"] = os.environ.get(
        "PULUMI_CONFIG_PASSPHRASE", ""
    )

    pulumi_root = get_pulumi_root()
    os.makedirs(pulumi_root, exist_ok=True)
    os.environ["PULUMI_DEBUG_COMMANDS"] = os.environ.get(
        "PULUMI_DEBUG_COMMANDS", "false"
    )
    os.environ["PULUMI_HOME"] = os.environ.get("PULUMI_HOME", pulumi_root)

    system = platform.system().lower()
    if system == "windows":
        _, pulumi_root = os.path.splitdrive(pulumi_root)
        pulumi_url = f"file:///{pulumi_root}"
    else:
        pulumi_url = f"file://{pulumi_root}"

    os.environ["PULUMI_BACKEND_URL"] = os.environ.get(
        "PULUMI_BACKEND_URL",
        pulumi_url,
    )


def ensure_cluster_name(cluster_name: Optional[str]) -> str:
    if cluster_name:
        return cluster_name
    # This will load the `./cluster.yaml` file if it exists
    config = load_cluster_config("")
    if not config:
        logger.error("Please provide a cluster name.")
        raise typer.Exit(1)

    assert config.aws, "Only AWS is supported for now"
    return config.aws.cluster.name


def ensure_cluster_config(cluster_file: Optional[str]) -> CloudConfig:
    config = load_cluster_config(cluster_file)
    if not config:
        logger.error("Cannot locate cluster configuration file.")
        raise typer.Exit(1)

    assert config.aws, "Only AWS is supported for now"
    return config.aws


def get_cluster_namespace(cluster_name: Optional[str]) -> str:
    cluster_name = ensure_cluster_name(cluster_name)
    namespace = read_pulumi_stack(cluster_name, "namespace")
    return namespace


def load_kubeconfig(cluster_name: Optional[str]) -> None:
    cluster_name = ensure_cluster_name(cluster_name)
    kubeconfig = read_pulumi_stack(cluster_name, "kubeconfig")
    k8s_config.load_kube_config_from_dict(kubeconfig)


def format_timedelta(td: timedelta) -> str:
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    days, hours = divmod(hours, 24)

    if days > 0:
        return f"{days}d{hours}h"
    elif hours > 0:
        return f"{hours}h{minutes}m"
    elif minutes > 0:
        return f"{minutes}m{seconds}s"
    else:
        return f"{seconds}s"
