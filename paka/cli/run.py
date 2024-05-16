import os
import shlex
from typing import Optional

import typer
from kubernetes import client

from paka.cli.utils import get_cluster_namespace, load_kubeconfig, resolve_image
from paka.k8s.utils import tail_logs
from paka.logger import logger
from paka.utils import kubify_name, random_str

CLEANUP_TIMEOUT = 600  # 10 minutes

run_app = typer.Typer()


@run_app.callback(invoke_without_command=True)
def one_off_script(
    cluster_name: Optional[str] = typer.Option(
        os.getenv("PAKA_CURRENT_CLUSTER"),
        "--cluster",
        "-c",
        help="The name of the cluster.",
    ),
    entrypoint: str = typer.Option(
        ...,
        "--entrypoint",
        help="The entrypoint of the application. This refers to the command "
        "defined in the Procfile that will be executed.",
    ),
    source_dir: Optional[str] = typer.Option(
        None,
        "--source",
        help="The directory containing the source code of the application. If "
        "specified, a new Docker image will be built using the source code from "
        "this directory. A Dockerfile is not required because the build process "
        "uses Cloud Native's Buildpacks, which automatically detect and install "
        "dependencies.",
    ),
    image: Optional[str] = typer.Option(
        None,
        "--image",
        help="The name of the Docker image to deploy. If both an image and a "
        "source directory are provided, this image will be used and the source "
        "directory will be ignored.",
    ),
) -> None:
    """
    Runs a one-off script.

    This command creates a new Kubernetes job that runs the specified entrypoint command
    in a container with the specified Docker image. If a source directory is provided, a new
    Docker image is built using the source code from that directory.
    """
    load_kubeconfig(cluster_name)
    resolved_image = resolve_image(cluster_name, image, source_dir)

    # Generate a job name which is the hash of the command
    job_name = f"run-{kubify_name(random_str(10))}"

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
                            image=resolved_image,
                            image_pull_policy="Always",
                            command=shlex.split(entrypoint),
                        )
                    ],
                    restart_policy="Never",
                )
            ),
            backoff_limit=0,
            ttl_seconds_after_finished=CLEANUP_TIMEOUT,
        ),
    )

    namespace = get_cluster_namespace(cluster_name)

    logger.info(f"Submitting the task...")
    batch_api = client.BatchV1Api()
    batch_api.create_namespaced_job(namespace=namespace, body=job)
    logger.info(f"Successfully submitted the task.")

    logger.info(f"Waiting for the task to complete...")
    api = client.CoreV1Api()
    pods = api.list_namespaced_pod(
        namespace=namespace, label_selector=f"job-name={job_name}"
    )
    for pod in pods.items:
        if pod.metadata and pod.metadata.name:
            tail_logs(namespace, pod.metadata.name, "one-off-script")
