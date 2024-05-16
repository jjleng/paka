from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import List, Literal, Optional, Tuple

import click
import typer
from kubernetes.client.exceptions import ApiException
from tabulate import tabulate

from paka.cli.utils import (
    format_timedelta,
    get_cluster_namespace,
    load_kubeconfig,
    resolve_image,
)
from paka.k8s.function.service import (
    create_knative_service,
    delete_knative_service,
    list_knative_revisions,
    list_knative_services,
    split_traffic_among_revisions,
)
from paka.logger import logger
from paka.utils import kubify_name

function_app = typer.Typer()

VALID_PERCENTAGE_RANGE = (0, 100)


def validate_traffic_split(split: str) -> Tuple[str, int]:
    """
    Validate a single traffic split string and return the revision and percentage.

    Args:
        split (str): The traffic split string in the format 'revision=percentage'.

    Returns:
        Tuple[str, int]: A tuple containing the revision and percentage.

    Raises:
        ValueError: If the input string is not in the expected format or the percentage is out of range.
    """
    if "=" not in split:
        raise ValueError(f"Invalid format, missing '=': {split}")

    revision, percent_str = split.split("=")
    if not percent_str.strip().isdigit():
        raise ValueError(f"Invalid format or non-numeric percentage: {split}")

    percent = int(percent_str.strip())
    if percent not in range(*VALID_PERCENTAGE_RANGE):
        raise ValueError(
            f"Traffic percentage out of valid range ({VALID_PERCENTAGE_RANGE[0]}-{VALID_PERCENTAGE_RANGE[1]}): {percent}"
        )

    return revision, percent


def process_traffic_splits(
    traffic_splits: List[str],
) -> Tuple[List[Tuple[str, int]], int]:
    total_traffic_percent = 0
    splits = []
    revisions = set()
    for split_str in traffic_splits:
        for split in re.split(r",\s*", split_str):
            revision, percent = validate_traffic_split(split)
            if revision in revisions:
                logger.error(f"Error: Duplicate revision '{revision}' provided.")
                raise typer.Exit(1)
            revisions.add(revision)
            splits.append((revision, percent))
            total_traffic_percent += percent

    return splits, total_traffic_percent


@function_app.command()
def deploy(
    cluster_name: Optional[str] = typer.Option(
        os.getenv("PAKA_CURRENT_CLUSTER"),
        "--cluster",
        "-c",
        help="The name of the cluster.",
    ),
    name: str = typer.Option(
        ...,
        "--name",
        help="The name of the function to be deployed.",
    ),
    entrypoint: str = typer.Option(
        "web",
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
    resource_requests: Optional[str] = typer.Option(
        None,
        "--resource-requests",
        help='The resource requests for the function, in JSON format. For example: \'{"cpu": "100m", "memory": "128Mi"}\'',
    ),
    resource_limits: Optional[str] = typer.Option(
        None,
        "--resource-limits",
        help='The resource limits for the function, in JSON format. For example: \'{"cpu": "200m", "memory": "256Mi"}\'',
    ),
) -> None:
    """
    Deploy a function to a Knative service.
    """
    load_kubeconfig(cluster_name)
    resolved_image = resolve_image(cluster_name, image, source_dir)

    logger.info(f"Deploying {name}...")

    resource_requests_dict = (
        json.loads(resource_requests) if resource_requests else None
    )
    resource_limits_dict = json.loads(resource_limits) if resource_limits else None

    create_knative_service(
        service_name=kubify_name(name),
        namespace=get_cluster_namespace(cluster_name),
        image=resolved_image,
        entrypoint=entrypoint,
        min_instances=min_instances,
        max_instances=max_instances,
        scaling_metric=(scaling_metric, str(metric_target)),
        scale_down_delay=scale_down_delay,
        resource_requests=resource_requests_dict,
        resource_limits=resource_limits_dict,
    )

    logger.info(f"Successfully deployed {name}")


@function_app.command()
def list(
    cluster_name: Optional[str] = typer.Option(
        os.getenv("PAKA_CURRENT_CLUSTER"),
        "--cluster",
        "-c",
        help="The name of the cluster.",
    ),
) -> None:
    """
    List all deployed functions.
    """
    load_kubeconfig(cluster_name)
    services = list_knative_services(get_cluster_namespace(cluster_name))

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
def list_revisions(
    cluster_name: Optional[str] = typer.Option(
        os.getenv("PAKA_CURRENT_CLUSTER"),
        "--cluster",
        "-c",
        help="The name of the cluster.",
    ),
    name: str = typer.Argument(
        ...,
        help="The name of the function to list revisions for. If not provided, list revisions for all services.",
    ),
) -> None:
    """
    List all deployed functions.
    """
    load_kubeconfig(cluster_name)
    revisions = list_knative_revisions(get_cluster_namespace(cluster_name), name)

    if not revisions:
        logger.info("No revisions found.")
        return

    table = []
    for revision in revisions:
        filtered_conditions = [
            condition
            for condition in revision.status.conditions
            if condition.get("reason") != "NoTraffic"
        ]

        sorted_conditions = sorted(
            filtered_conditions,
            key=lambda condition: condition.get("lastTransitionTime"),
            reverse=True,
        )
        latest_condition = sorted_conditions[0] if sorted_conditions else None

        true_conditions = sum(
            c.get("status") == "True" for c in revision.status.conditions
        )

        table.append(
            (
                revision.metadata.name,
                revision.metadata.labels["serving.knative.dev/service"],
                revision.traffic,
                revision.metadata.labels.get("tags", ""),
                revision.metadata.labels["serving.knative.dev/configurationGeneration"],
                format_timedelta(
                    datetime.now(timezone.utc)
                    - datetime.strptime(
                        revision.metadata.creationTimestamp, "%Y-%m-%dT%H:%M:%SZ"
                    ).replace(tzinfo=timezone.utc)
                ),
                f"{true_conditions} OK / {len(revision.status.conditions)}",
                latest_condition.get("status", ""),
                latest_condition.get("reason", ""),
                # latest_condition.get("message", ""),
            )
        )

    logger.info(
        tabulate(
            table,
            headers=[
                "Name",
                "Service",
                "Traffic",
                "Tags",
                "Generation",
                "Age",
                "Conditions",
                "Status",
                "Reason",
                # "Message",
            ],
        )
    )


@function_app.command()
def update_traffic(
    cluster_name: Optional[str] = typer.Option(
        os.getenv("PAKA_CURRENT_CLUSTER"),
        "--cluster",
        "-c",
        help="The name of the cluster.",
    ),
    name: str = typer.Argument(
        ...,
        help="The name of the function to update traffic for.",
    ),
    traffic_splits: List[str] = typer.Option(
        [],
        "--traffic",
        help="Specify traffic splits for each revision in the format 'revision=percentage'. "
        "Multiple splits can be provided.",
        show_default=False,
    ),
    latest_revision_traffic: int = typer.Option(
        0,
        "--latest-revision-traffic",
        help="The percentage of traffic to send to the latest revision.",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Automatic yes to prompts. Use this option to bypass the confirmation "
        "prompt and directly proceed with the operation.",
    ),
) -> None:
    """
    Update the traffic distribution among the revisions of a function.

    You can provide the traffic splits in two ways:

    1. Using multiple `--traffic` options, e.g.:
       `update_traffic --traffic revision1=50 --traffic revision2=30 --traffic revision3=20`

    2. Using a comma-separated list within a single `--traffic` option, e.g.:
       `update_traffic --traffic revision1=50,revision2=30,revision3=20`

    If the total traffic percentage is less than 100% and `--latest-revision-traffic` is not provided,
    the user will be prompted to confirm whether the remaining traffic should be assigned to the latest revision.
    """
    splits, total_traffic_percent = process_traffic_splits(traffic_splits)

    if total_traffic_percent + latest_revision_traffic > 100:
        logger.error("Total traffic percent should not exceed 100%")
        raise typer.Exit(1)

    if total_traffic_percent < 100 and latest_revision_traffic == 0:
        remaining_traffic = 100 - total_traffic_percent
        confirm = yes or typer.confirm(
            f"Assign remaining {remaining_traffic}% traffic to the latest revision?",
            default=True,
        )
        if confirm:
            latest_revision_traffic = remaining_traffic
        else:
            logger.error("Traffic distribution aborted by user.")
            raise typer.Abort()

    load_kubeconfig(cluster_name)
    logger.info(f"Updating traffic for function {name}")
    split_traffic_among_revisions(
        get_cluster_namespace(cluster_name),
        name,
        splits,
        latest_revision_traffic,
    )
    logger.info(f"Successfully updated traffic for service {name}")


@function_app.command()
def delete(
    cluster_name: Optional[str] = typer.Option(
        os.getenv("PAKA_CURRENT_CLUSTER"),
        "--cluster",
        "-c",
        help="The name of the cluster.",
    ),
    name: str = typer.Argument(
        ...,
        help="The name of the function to delete.",
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
    Delete a function.
    """
    if yes or typer.confirm(
        f"Are you sure you want to delete the function {name}?", default=False
    ):
        load_kubeconfig(cluster_name)
        logger.info(f"Deleting function {name}")
        try:
            delete_knative_service(
                kubify_name(name), get_cluster_namespace(cluster_name)
            )
            logger.info(f"Successfully deleted function {name}")
        except ApiException as e:
            if e.status == 404:
                logger.error(f"Function {name} not found.")
            else:
                raise
