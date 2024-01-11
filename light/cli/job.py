import os
from typing import Optional

import typer

from light.job.worker import create_workers, delete_workers
from light.logger import logger
from light.utils import read_current_cluster_data

job_app = typer.Typer()


@job_app.command(help="Deploy a job.")
def deploy(
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
    image_name: Optional[str] = typer.Option(
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
    if not source_dir and not image_name:
        logger.error(
            "Either --source or --image must be provided. Please see --help for more information."
        )
        raise typer.Exit(1)
    elif image_name:
        task_name = image_name
    elif source_dir:
        source_dir = os.path.abspath(source_dir)
        image_name = os.path.basename(source_dir)
        task_name = image_name

    registry_uri = read_current_cluster_data("registry")

    create_workers(
        entrypoint,
        task_name,
        f"{registry_uri}:{image_name or task_name}",
        tasks_per_worker,
        max_workers,
        wait_existing_tasks,
    )


@job_app.command(help="Delete a job.")
def delete(
    job_name: str = typer.Argument(
        ...,
        help="The job name.",
    ),
) -> None:
    logger.info(f"Deleting job {job_name}")
    delete_workers(job_name)
    logger.info(f"Successfully deleted job {job_name}")
