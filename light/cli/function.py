from typing import Literal, Optional

import click
import typer
from kubernetes.dynamic.exceptions import NotFoundError
from tabulate import tabulate

from light.cli.utils import resolve_image
from light.constants import APP_NS  # TODO: APP_NS should be loaded dynamically
from light.k8s import try_load_kubeconfig
from light.kube_resources.function.service import (
    create_knative_service,
    delete_knative_service,
    list_knative_services,
)
from light.logger import logger
from light.utils import kubify_name

try_load_kubeconfig()

function_app = typer.Typer()


@function_app.command()
def deploy(
    name: str = typer.Option(
        ...,
        "--name",
        help="The name of the function to be deployed.",
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
    min_instances: int = typer.Option(
        0,
        "--min-replicas",
        help="The minimum number of instances to be maintained at all times to "
        "handle incoming requests. The default value is 0, indicating that the "
        "system can scale down to zero instances when no requests are being processed.",
    ),
    max_instances: int = typer.Option(
        0,
        "--max-replicas",
        help="The maximum number of instances that can be created to handle peak "
        "load. The default value is set to 0, indicating that there is no upper "
        "limit on the number of instances that can be created.",
    ),
    scaling_metric: Literal["concurrency", "rps"] = typer.Option(
        "concurrency",
        "--scaling-metric",
        help="The performance metric that the scaling system should monitor to "
        "determine when to adjust the number of instances.",
        case_sensitive=True,
        click_type=click.Choice(["rps", "concurrency"]),
    ),
    metric_target: int = typer.Option(
        10,
        "--metric-target",
        help="The desired value for the chosen scaling metric. The system will "
        "adjust the number of active instances to attempt to reach this target.",
    ),
    scale_down_delay: str = typer.Option(
        "0s",
        "--scale-down-delay",
        help="The delay before the system scales down after a spike in traffic. "
        "This value must be a duration between 0 seconds and 1 hour, represented "
        "as a string (e.g., '0s', '1m', '1h').",
    ),
) -> None:
    """
    Deploy a function to a Knative service.

    Args:
        name (str): The name of the function.
        source_dir (Optional[str]): The source directory of the application. If provided, a new Docker image
            will be built from this directory. If not provided, the `image` parameter must be provided.
        image (Optional[str]): The name of the Docker image to deploy. If not provided, the `source_dir`
            parameter must be provided.
        min_instances (int): The minimum number of instances for the Knative service.
        max_instances (int): The maximum number of instances for the Knative service.
        scaling_metric (Literal["concurrency", "rps"]): The metric to scale on. Must be either "concurrency" or "rps".
        metric_target (int): The target value for the scaling metric.
        scale_down_delay (str): The delay before scaling down after a spike in traffic. Must be a string
            representing a duration in seconds (e.g. "0s", "1m", "1h").

    Returns:
        None
    """
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
    """
    List all deployed functions.

    Returns:
        None
    """
    services = list_knative_services(APP_NS)

    if not services.items:
        logger.info("No functions found.")
        return

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


@function_app.command()
def delete(name: str) -> None:
    """
    Delete a function.

    Args:
        name (str): The name of the function to delete.

    Returns:
        None
    """
    logger.info(f"Deleting function {name}")
    try:
        delete_knative_service(kubify_name(name), APP_NS)
        logger.info(f"Successfully deleted function {name}")
    except NotFoundError:
        logger.error(f"Function {name} not found.")
