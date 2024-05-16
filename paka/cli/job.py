from __future__ import annotations

import os
from typing import Optional

import typer
from kubernetes import client

from paka.cli.utils import get_cluster_namespace, load_kubeconfig, resolve_image
from paka.k8s.job.worker import create_workers, delete_workers
from paka.logger import logger
from paka.utils import kubify_name

job_app = typer.Typer()


def prefixed_job_name(job_name: str) -> str:
    # Prefix the job name with "job-" to reduce the chances of name collision
    # between jobs and functions.
    if not job_name.startswith("job-"):
        return f"job-{job_name}"
    return job_name


@job_app.command()
def deploy(
    cluster_name: Optional[str] = typer.Option(
        os.getenv("PAKA_CURRENT_CLUSTER"),
        "--cluster",
        "-c",
        help="The name of the cluster.",
    ),
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
    """
    load_kubeconfig(cluster_name)
    resolved_image = resolve_image(cluster_name, image, source_dir)

    if image:
        job_name = image
    elif source_dir:
        job_name = os.path.basename(source_dir)

    create_workers(
        namespace=get_cluster_namespace(cluster_name),
        job_name=kubify_name(prefixed_job_name(name or job_name)),
        image=resolved_image,
        entrypoint=entrypoint,
        tasks_per_worker=tasks_per_worker,
        max_replicas=max_workers,
        drain_existing_job=wait_existing_tasks,
    )


@job_app.command()
def delete(
    cluster_name: Optional[str] = typer.Option(
        os.getenv("PAKA_CURRENT_CLUSTER"),
        "--cluster",
        "-c",
        help="The name of the cluster.",
    ),
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
    Delete a job.
    """
    if yes or typer.confirm(
        f"Are you sure you want to delete the job {name}?", default=False
    ):
        load_kubeconfig(cluster_name)
        logger.info(f"Deleting job {name}")
        delete_workers(
            get_cluster_namespace(cluster_name),
            prefixed_job_name(name),
            wait_existing_tasks,
        )
        logger.info(f"Successfully deleted job {name}")


@job_app.command()
def list(
    cluster_name: Optional[str] = typer.Option(
        os.getenv("PAKA_CURRENT_CLUSTER"),
        "--cluster",
        "-c",
        help="The name of the cluster.",
    ),
) -> None:
    """
    Lists all jobs.
    """
    load_kubeconfig(cluster_name)
    api_instance = client.AppsV1Api()

    label_selector = "role=worker"

    # List the deployments in the specified namespace that match the field selector
    deployments = api_instance.list_namespaced_deployment(
        namespace=get_cluster_namespace(cluster_name), label_selector=label_selector
    )

    for deployment in deployments.items:
        if deployment.metadata and deployment.metadata.name:
            logger.info(deployment.metadata.name)

    if not deployments.items:
        logger.info("No jobs found.")
