import os
from typing import Literal, Optional

import click
import typer

from light.cli.build import build
from light.constants import APP_NS  # TODO: APP_NS should be loaded dynamically
from light.k8s import try_load_kubeconfig
from light.kube_resources.function.service import create_knative_service
from light.logger import logger
from light.utils import kubify_name, read_current_cluster_data

try_load_kubeconfig()

function_app = typer.Typer()


def typed_job_name(job_name: str) -> str:
    if not job_name.startswith("job-"):
        return f"job-{job_name}"
    return job_name


@function_app.command(help="Deploy a function.")
def deploy(
    name: str = typer.Option(
        ...,
        "--name",
        help="The name of the function.",
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
    min_instances: int = typer.Option(
        0,
        "--min-replicas",
        help="The minimum number of instances.",
    ),
    max_instances: int = typer.Option(
        0,
        "--max-replicas",
        help="The maximum number of instances.",
    ),
    scaling_metric: Literal["concurrency", "rps"] = typer.Option(
        "concurrency",
        "--scaling-metric",
        help="The metric to scale on.",
        case_sensitive=True,
        prompt="Please choose a scaling metric",
        show_choices=True,
        click_type=click.Choice(["rps", "concurrency"]),
    ),
    metric_target: int = typer.Option(
        10,
        "--metric-target",
        help="The metric target.",
    ),
    scale_down_delay: str = typer.Option(
        "0s",
        "--scale-down-delay",
        help="The scale down delay (e.g. 0s, 1m, 1h). Must be 0s <= value <= 1h",
    ),
) -> None:
    if not source_dir and not image:
        logger.error(
            "Either --source or --image must be provided. Please see --help for more information."
        )
        raise typer.Exit(1)
    elif source_dir:
        source_dir = os.path.abspath(os.path.expanduser(source_dir))
        image = os.path.basename(source_dir)
        # Always build and deploy the latest image
        build(source_dir, image)
        # We always use the latest image
        image = f"{image}-latest"

    registry_uri = read_current_cluster_data("registry")

    logger.info(f"Deploying {name}...")

    create_knative_service(
        kubify_name(name),
        APP_NS,
        f"{registry_uri}:{image}",
        min_instances,
        max_instances,
        (scaling_metric, str(metric_target)),
        scale_down_delay,
    )

    logger.info(f"Successfully deployed {name}")
