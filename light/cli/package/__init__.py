import os
import tempfile
import time

import typer
from kubernetes.client.rest import ApiException

from light.cli.package.ignore import blacklist
from light.cli.package.zip import archive_directory
from light.cli.utils import validate_name
from light.fission.env import get_env
from light.fission.package import (
    delete_package,
    get_package,
    list_packages,
    upsert_package,
)
from light.logger import logger
from light.utils import to_yaml

package_app = typer.Typer()


@package_app.command("create")
@package_app.command("update")
@validate_name
def package_upsert(
    name: str = typer.Argument(
        ...,
        help="The package name",
    ),
    source_directory: str = typer.Option(
        ...,
        "--source",
        "-s",
        help="The source directory to create the package from",
    ),
    env: str = typer.Option(
        ...,
        "--env",
        "-e",
        help="The environment to use for the package. Supported environments are 'python:3.12', 'node:18', etc.",
    ),
) -> None:
    try:
        get_env(env, "default")
    except ApiException as e:
        if e.status == 404:
            logger.info(f"Env '{env}' doesn't exist. Please create it first.")
            raise typer.Exit(1)
        else:
            raise e

    with tempfile.TemporaryDirectory() as temp_dir:
        archive_path = os.path.join(temp_dir, name)
        archive_directory(source_directory, archive_path, blacklist)
        logger.info(f"Archive '{archive_path}.zip' created successfully.")
        upsert_package(name, "default", env, f"{archive_path}.zip", "./build.sh")
        package = get_package(name, "default")
        status = package["status"]

        if status["buildstatus"] in ["pending", "running"]:
            logger.info("Package building")

        while status["buildstatus"] in ["pending", "running"]:
            package = get_package(name, "default")
            status = package["status"]
            print(".", end="", flush=True)
            time.sleep(1)

        logger.info("")
        logger.debug(status.get("buildlog", ""))

        if status["buildstatus"] != "succeeded":
            logger.info("Package build failed.")
        else:
            logger.info("Package build succeeded.")


@package_app.command("delete")
def package_delete(
    name: str = typer.Argument(
        ...,
        help="The package name",
    ),
) -> None:
    delete_package(name, "default")
    logger.info(f"Package '{name}' deleted successfully.")


@package_app.command("list")
def package_list() -> None:
    packages = list_packages("default")
    for package in packages:
        logger.info(package["metadata"]["name"])
        logger.debug(to_yaml(package))
