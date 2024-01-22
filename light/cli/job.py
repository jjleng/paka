import os
from typing import Optional

import typer
from kubernetes import client

from light.cli.utils import resolve_image
from light.constants import APP_NS  # TODO: APP_NS should be loaded dynamically
from light.k8s import try_load_kubeconfig
from light.kube_resources.job.worker import create_workers, delete_workers
from light.logger import logger
from light.utils import kubify_name

try_load_kubeconfig()

job_app = typer.Typer()


def typed_job_name(job_name: str) -> str:
    if not job_name.startswith("job-"):
        return f"job-{job_name}"
    return job_name


@job_app.command(help="Deploy a job.")
def deploy(
    name: str = typer.Option(
        "",
        "--name",
        help="The name of the job.",
    ),
    entrypoint: str = typer.Option(
        ...,
        "--entrypoint",
        help="The entrypoint of the application.",
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
    max_workers: int = typer.Option(
        5,
        "--max-workers",
        help="The maximum number of workers.",
    ),
    tasks_per_worker: int = typer.Option(
        5,
        "--tasks-per-worker",
        help="The number of tasks each worker should handle before a new worker is created.",
    ),
    wait_existing_tasks: bool = typer.Option(
        True,
        "--wait-existing-tasks",
        help="Wait for existing tasks to drain before deploying.",
    ),
) -> None:
    resolved_image = resolve_image(image, source_dir)

    if image:
        job_name = image
    elif source_dir:
        job_name = os.path.basename(source_dir)

    create_workers(
        namespace=APP_NS,
        job_name=kubify_name(typed_job_name(name or job_name)),
        image=resolved_image,
        entrypoint=entrypoint,
        tasks_per_worker=tasks_per_worker,
        max_replicas=max_workers,
        drain_existing_job=wait_existing_tasks,
    )


@job_app.command(help="Delete a job.")
def delete(
    name: str = typer.Argument(
        ...,
        help="The job name.",
    ),
    wait_existing_tasks: bool = typer.Option(
        True,
        "--wait-existing-tasks",
        help="Wait for existing tasks to drain before deleting.",
    ),
) -> None:
    logger.info(f"Deleting job {name}")
    delete_workers(APP_NS, typed_job_name(name), wait_existing_tasks)
    logger.info(f"Successfully deleted job {name}")


@job_app.command(help="List jobs.")
def list() -> None:
    api_instance = client.AppsV1Api()

    label_selector = "role=worker"

    # List the deployments in the specified namespace that match the field selector
    deployments = api_instance.list_namespaced_deployment(
        namespace=APP_NS, label_selector=label_selector
    )

    for deployment in deployments.items:
        logger.info(deployment.metadata.name)

    if not deployments.items:
        logger.info("No jobs found.")
