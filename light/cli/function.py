import typer
from light.logger import logger
from light.cli.fission.function import upsert_fn
from light.cli.utils import validate_name


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
    upsert_fn("open-copilot", name, "default", package, entrypoint)
