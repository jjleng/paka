import typer

from light.cli.utils import validate_name
from light.fission.function import delete_fn, list_fns, upsert_fn
from light.logger import logger
from light.utils import to_yaml

function_app = typer.Typer()


@function_app.command("create")
@function_app.command("update")
@validate_name
def function_upsert(
    name: str = typer.Argument(
        ...,
        help="The function name.",
    ),
    package: str = typer.Option(
        ...,
        "--package",
        "-p",
        help="The package name.",
    ),
    entrypoint: str = typer.Option(
        ...,
        "--entrypoint",
        "-e",
        help="The entrypoint of the function.",
    ),
) -> None:
    upsert_fn(name, "default", package, entrypoint)


@function_app.command("delete")
def function_delete(
    name: str = typer.Argument(
        ...,
        help="The function name.",
    ),
) -> None:
    delete_fn(name, "default")
    logger.info(f"Function '{name}' deleted successfully.")


@function_app.command("list")
def function_list() -> None:
    functions = list_fns("default")
    for function in functions:
        logger.info(function["metadata"]["name"])
        logger.debug(to_yaml(function))
