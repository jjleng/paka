import typer
from kubernetes import config
from ruamel.yaml import YAML

from light.cli.env import pick_runtime
from light.cli.fission.env import upsert_env
from light.cli.spec.schema import APP_KIND_FUNCTION, FunctionSpec
from light.logger import logger

APP_NS = "default"
JOB_NS = "jobs"

deploy_app = typer.Typer()


def deploy_function(spec: FunctionSpec, build_command: str) -> None:
    logger.info(f"Deploying function spec '{spec.name}'")

    # Create the runtime env. If the env does not exist, we need to create it.
    # If the env exists, we need to update it.
    image, builder_image = pick_runtime(spec.runtime)
    language, _ = spec.runtime.split(":")

    if language == "python" and not build_command:
        build_command = r"sh -c 'pip3 install -r ${SRC_PKG}/requirements.txt -t ${SRC_PKG} && cp -r ${SRC_PKG} ${DEPLOY_PKG}'"

    upsert_env(
        spec.name,
        APP_NS,
        image=image,
        builder_image=builder_image,
        builder_command=build_command,
    )

    # Create the package.


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
        file_data = f.read()
        yaml = YAML()
        yaml_data = yaml.load(file_data)
        if yaml_data["kind"] == APP_KIND_FUNCTION:
            deploy_function(FunctionSpec(**yaml_data), build_command)
