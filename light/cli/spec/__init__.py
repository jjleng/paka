import os

import typer

from light.cli.spec.schema import FunctionSpec, Resource, Resources, Settings
from light.cli.utils import validate_name
from light.logger import logger
from light.utils import to_yaml

spec_app = typer.Typer()


@spec_app.command("function", help="Create a function spec.")
@validate_name
def create_function(
    name: str = typer.Argument(
        ...,
        help="The spec name.",
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
        help="The minimum cpu to use for the function runtime.",
    ),
    max_cpu: str = typer.Option(
        "",
        "--max-cpu",
        "-C",
        help="The maximum cpu to use for the function runtime.",
    ),
    min_memory: str = typer.Option(
        "",
        "--min-memory",
        "-m",
        help="The minimum memory to use for the function runtime.",
    ),
    max_memory: str = typer.Option(
        "",
        "--max-memory",
        "-M",
        help="The maximum memory to use for the function runtime.",
    ),
    concurrency: int = typer.Option(
        500,
        "--concurrency",
        help="The maximum number of concurrent pods/instances.",
    ),
    timeout: int = typer.Option(
        60,
        "--timeout",
        help="The maximum number of seconds a function can run.",
    ),
    idle_timeout: int = typer.Option(
        120,
        "--idle-timeout",
        help="The maximum number of seconds a function can be idle.",
    ),
    requests_per_pod: int = typer.Option(
        1,
        "--requests-per-pod",
        help="The maximum concurrent requests that can go to one pod/instance.",
    ),
) -> None:
    resources = Resources(
        requests=Resource(cpu=min_cpu, memory=min_memory),
        limits=Resource(cpu=max_cpu, memory=max_memory),
    )
    settings = Settings(
        concurrency=concurrency,
        timeout=timeout,
        idle_timeout=idle_timeout,
        requests_per_pod=requests_per_pod,
    )
    function_spec = FunctionSpec(
        name=name,
        runtime=runtime,
        resources=resources,
        settings=settings,
    )

    spec_yaml = to_yaml(function_spec.model_dump(exclude_none=True))

    # Save spec_yaml to current directory
    filename = f"{name}.yaml"
    if os.path.exists(filename):
        raise FileExistsError(f"The file {filename} already exists.")

    with open(filename, "w") as f:
        f.write(spec_yaml)
    logger.info(f"Function spec '{filename}' created successfully.")
