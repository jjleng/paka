import typer
from typing import Tuple
from light.logger import logger
from light.cli.fission.env import upsert_env, delete_env, list_envs
from light.cli.utils import validate_name
from light.utils import to_yaml


env_app = typer.Typer()


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

    # Only support version 3.12 for now
    if version not in ["3.12"]:
        logger.info(
            f"Invalid version '{version}'. Supported versions for language '{language}' are '3.12'."
        )
        raise typer.Exit(1)

    return (
        f"jijunleng/{language}-env-{version}:dev",
        f"jijunleng/{language}-builder-{version}:dev",
    )


@env_app.command("create")
@env_app.command("update")
@validate_name
def env_upsert(
    name: str = typer.Argument(
        ...,
        help="The env name.",
    ),
    runtime: str = typer.Option(
        ...,
        "--runtime",
        "-r",
        help="The runtime to use for the env. Runtime is a combination of language and version. Supported runtimes are 'python:3.12', 'node:18', etc",
    ),
) -> None:
    image, builder_image = pick_runtime(runtime)

    upsert_env("open-copilot", name, "default", image, builder_image)


@env_app.command("delete")
def env_delete(
    name: str = typer.Argument(
        ...,
        help="The env name.",
    ),
) -> None:
    delete_env("open-copilot", name, "default")
    logger.info(f"Env '{name}' deleted successfully.")


@env_app.command("list")
def env_list() -> None:
    envs = list_envs("open-copilot", "default")
    for env in envs:
        del env["metadata"]["managedFields"]
        logger.info(env["metadata"]["name"])
        logger.debug(to_yaml(env))
