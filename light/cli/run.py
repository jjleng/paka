import os
import shlex
from typing import Optional

import typer
from kubernetes import client

from light.cli.build import build
from light.constants import APP_NS
from light.k8s import try_load_kubeconfig
from light.logger import logger
from light.utils import random_str

run_app = typer.Typer()

try_load_kubeconfig()


@run_app.command(help="Run a one-off script.")
def one_off_script(
    command: str = typer.Option(
        ...,
        "--command",
        help="The command to run.",
    ),
    source_dir: Optional[str] = typer.Option(
        None,
        "--source",
        help="Source directory of the application.",
    ),
    image: Optional[str] = typer.Option(
        None,
        "--image",
        help="The name of the image to deploy.",
    ),
) -> None:
    if not source_dir and not image:
        logger.error(
            "Either --source or --image must be provided. Please see --help for more information."
        )
        raise typer.Exit(1)

    # Generate a job name which is the hash of the command
    job_name = random_str(10)

    if not image and source_dir:
        source_dir = os.path.abspath(os.path.expanduser(source_dir))
        image = os.path.basename(source_dir)
        build(source_dir, image)
        image = f"{image}-latest"

    job = client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=client.V1ObjectMeta(name=job_name, labels={"job-name": job_name}),
        spec=client.V1JobSpec(
            template=client.V1PodTemplateSpec(
                spec=client.V1PodSpec(
                    containers=[
                        client.V1Container(
                            name="one-off-script",
                            image=image,
                            command=shlex.split(command),
                        )
                    ],
                    restart_policy="Never",
                )
            ),
            backoff_limit=4,
        ),
    )

    api = client.BatchV1Api()
    api.create_namespaced_job(namespace=APP_NS, body=job)
