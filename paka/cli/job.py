import os
from typing import Optional

import click
import typer
from kubernetes import client

from paka.cli.utils import resolve_image
from paka.k8s import try_load_kubeconfig
from paka.kube_resources.job.worker import create_workers, delete_workers
from paka.logger import logger
from paka.utils import kubify_name, read_current_cluster_data

try_load_kubeconfig()

job_app = typer.Typer()


def prefixed_job_name(job_name: str) -> str:
    # Prefix the job name with "job-" to reduce the chances of name collision
    # between jobs and functions.
    if not job_name.startswith("job-"):
        return f"job-{job_name}"
    return job_name


@job_app.command()
def deploy(
    name: str = typer.Option(
        "",
        "--name",
        help="The name of the job. This name will be used to track the job's "
        "progress and manage its resources. If not provided, the system will use "
        "the base name of the 'source_dir' or the 'image' name as the job name.",
    ),
    entrypoint: str = typer.Option(
        ...,
        "--entrypoint",
        help="The entrypoint of the application. This refers to the command "
        "defined in the Procfile that will be executed to start the application "
        "when the job is run.",
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
    max_workers: int = typer.Option(
        5,
        "--max-workers",
        help="The maximum number of workers that can be allocated for this job. "
        "This sets an upper limit on the number of workers that the autoscaling "
        "system can create to handle tasks for this job.",
    ),
    tasks_per_worker: int = typer.Option(
        5,
        "--tasks-per-worker",
        help="The number of tasks that need to be allocated to each worker before "
        "the autoscaler creates a new worker.",
    ),
    wait_existing_tasks: bool = typer.Option(
        True,
        "--wait-existing-tasks",
        help="Determines whether the system should wait for existing tasks to "
        "complete before deploying the new job. If set to true, the deployment "
        "will wait until all current tasks have finished.",
    ),
) -> None:
    """
    Deploy a job.

    A job leverages a Redis queue to distribute work to a pool of autoscaling workers.
    The job can be specified by providing a Docker image or a source directory containing the application code.

    If a Docker image is provided, the cluster will run the job using this image.
    If a source directory is provided, the cluster will build a Docker image from the source code and then run the job.

    If both an image and a source directory are provided, the Docker image is used and the source directory is ignored.
    """
    resolved_image = resolve_image(image, source_dir)

    if image:
        job_name = image
    elif source_dir:
        job_name = os.path.basename(source_dir)

    create_workers(
        namespace=read_current_cluster_data("namespace"),
        job_name=kubify_name(prefixed_job_name(name or job_name)),
        image=resolved_image,
        entrypoint=entrypoint,
        tasks_per_worker=tasks_per_worker,
        max_replicas=max_workers,
        drain_existing_job=wait_existing_tasks,
    )


@job_app.command()
def delete(
    name: str = typer.Argument(
        ...,
        help="The name of the job to delete.",
    ),
    wait_existing_tasks: bool = typer.Option(
        True,
        "--wait-existing-tasks",
        help="Determines whether the system should wait for existing tasks to "
        "complete before deploying the new job. If set to true, the deployment "
        "will wait until all current tasks have finished.",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Automatic yes to prompts. Use this option to bypass the confirmation "
        "prompt and directly proceed with the deletion.",
    ),
) -> None:
    """
    Deletes a job.

    Args:
        name (str): The unique identifier of the job to be deleted.
        wait_existing_tasks (bool): Determines whether the system should wait for existing tasks to complete before deleting the job.
        yes (bool): If True, bypasses the confirmation prompt and directly proceeds with the deletion.

    Returns:
        None
    """
    if yes or click.confirm(
        f"Are you sure you want to delete the job {name}?", default=False
    ):
        logger.info(f"Deleting job {name}")
        delete_workers(
            read_current_cluster_data("namespace"),
            prefixed_job_name(name),
            wait_existing_tasks,
        )
        logger.info(f"Successfully deleted job {name}")


@job_app.command()
def list() -> None:
    """
    Lists all jobs.
    """
    api_instance = client.AppsV1Api()

    label_selector = "role=worker"

    # List the deployments in the specified namespace that match the field selector
    deployments = api_instance.list_namespaced_deployment(
        namespace=read_current_cluster_data("namespace"), label_selector=label_selector
    )

    for deployment in deployments.items:
        logger.info(deployment.metadata.name)

    if not deployments.items:
        logger.info("No jobs found.")
