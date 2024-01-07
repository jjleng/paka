import typer

from light.cli.utils import pick_runtime, validate_name
from light.constants import FISSION_RESOURCE_NS
from light.fission.env import delete_env, list_envs, upsert_env
from light.logger import logger
from light.utils import to_yaml

env_app = typer.Typer()


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
    min_cpu: str = typer.Option(
        "",
        "--min-cpu",
        "-c",
        help="The minimum cpu to use for the env.",
    ),
    max_cpu: str = typer.Option(
        "",
        "--max-cpu",
        "-C",
        help="The maximum cpu to use for the env.",
    ),
    min_memory: str = typer.Option(
        "",
        "--min-memory",
        "-m",
        help="The minimum memory to use for the env.",
    ),
    max_memory: str = typer.Option(
        "",
        "--max-memory",
        "-M",
        help="The maximum memory to use for the env.",
    ),
) -> None:
    image, builder_image = pick_runtime(runtime)

    upsert_env(
        name,
        FISSION_RESOURCE_NS,
        image,
        builder_image,
        min_cpu=min_cpu,
        max_cpu=max_cpu,
        min_memory=min_memory,
        max_memory=max_memory,
    )


@env_app.command("delete")
def env_delete(
    name: str = typer.Argument(
        ...,
        help="The env name.",
    ),
) -> None:
    delete_env(name, FISSION_RESOURCE_NS)
    logger.info(f"Env '{name}' deleted successfully.")


@env_app.command("list")
def env_list() -> None:
    envs = list_envs(FISSION_RESOURCE_NS)
    for env in envs:
        del env["metadata"]["managedFields"]
        logger.info(env["metadata"]["name"])
        logger.debug(to_yaml(env))
