import os

import typer
from ruamel.yaml import YAML

from light.cli.spec.schema import APP_KIND_FUNCTION, FunctionSpec
from light.logger import logger

deploy_app = typer.Typer()


def deploy_function(
    spec: FunctionSpec, source_directory: str, build_command: str
) -> None:
    logger.info(f"Deploying function spec '{spec.name}'")


@deploy_app.callback(invoke_without_command=True)
def deploy(
    spec: str = typer.Argument(
        ...,
        help="Path of the spec file.",
    ),
    build_command: str = typer.Option(
        "",
        "--build-command",
        "-b",
        help="The command to build the function.",
    ),
) -> None:
    with open(spec, "r") as f:
        file_directory = os.path.dirname(os.path.abspath(f.name))
        file_data = f.read()
        yaml = YAML()
        yaml_data = yaml.load(file_data)
        if yaml_data["kind"] == APP_KIND_FUNCTION:
            deploy_function(FunctionSpec(**yaml_data), file_directory, build_command)
