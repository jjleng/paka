from typing import Literal, Optional

import click
import typer
from tabulate import tabulate

from light.cli.utils import resolve_image
from light.constants import APP_NS  # TODO: APP_NS should be loaded dynamically
from light.k8s import try_load_kubeconfig
from light.kube_resources.function.service import (
    create_knative_service,
    list_knative_services,
)
from light.logger import logger
from light.utils import kubify_name

try_load_kubeconfig()

function_app = typer.Typer()


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
    resolved_image = resolve_image(image, source_dir)

    logger.info(f"Deploying {name}...")

    create_knative_service(
        service_name=kubify_name(name),
        namespace=APP_NS,
        image=resolved_image,
        min_instances=min_instances,
        max_instances=max_instances,
        scaling_metric=(scaling_metric, str(metric_target)),
        scale_down_delay=scale_down_delay,
    )

    logger.info(f"Successfully deployed {name}")


@function_app.command()
def list() -> None:
    services = list_knative_services(APP_NS)

    table = [
        (
            svc.metadata.name,
            svc.status.url,
            svc.status.latestCreatedRevisionName,
            svc.status.latestReadyRevisionName,
            svc.status.conditions[0].status if len(svc.status.conditions) > 0 else "",
            svc.status.conditions[0].reason if len(svc.status.conditions) > 0 else "",
        )
        for svc in services.items
    ]
    logger.info(
        tabulate(
            table,
            headers=[
                "Name",
                "Endpoint",
                "LatestCreated",
                "LatestReady",
                "Ready",
                "Reason",
            ],
        )
    )
