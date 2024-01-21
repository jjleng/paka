import functools
import os
import re
from typing import Any, Tuple

import typer

from light.cluster.manager.aws import AWSClusterManager
from light.cluster.manager.base import ClusterManager
from light.config import parse_yaml
from light.logger import logger


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


def pick_runtime(runtime: str) -> Tuple[str, str]:
    language, version = runtime.split(":")
    if not language or not version:
        logger.info(
            "Invalid runtime. Runtime must be in the format of 'language:version'."
        )
        raise typer.Exit(1)

    if language not in ["python", "node"]:
        logger.info(
            f"Invalid language '{language}'. Supported languages are 'python' and 'node'."
        )
        raise typer.Exit(1)

    # Only support python for now
    if language != "python":
        logger.info(f"Invalid language '{language}'. Only 'python' is supported.")
        raise typer.Exit(1)

    # Only support version 3.11 for now
    if version not in ["3.11"]:
        logger.info(
            f"Invalid version '{version}'. Supported versions for language '{language}' are '3.11'."
        )
        raise typer.Exit(1)

    return (
        f"jijunleng/{language}-env-{version}:bookworm-slim",
        f"jijunleng/{language}-builder-{version}:bookworm-slim",
    )
