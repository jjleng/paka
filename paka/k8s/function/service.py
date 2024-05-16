from __future__ import annotations

import re
import shlex
from typing import Any, Dict, List, Literal, Optional, Tuple

from kubernetes import client
from kubernetes.client.exceptions import ApiException
from kubernetes.dynamic import DynamicClient  # type: ignore

VALID_RESOURCES = ["cpu", "memory"]

VALID_RESOURCES_GPU = ["nvidia.com/gpu"]


def validate_resource(resource: str, value: str) -> None:
    if resource == "cpu":
        if not re.match(r"^\d+(m)?$", value):
            raise ValueError("Invalid CPU value")
    elif resource == "memory":
        if not re.match(r"^\d+(Mi|Gi)$", value):
            raise ValueError("Invalid memory value")
    elif resource == "nvidia.com/gpu":
        if not value.isdigit() or int(value) < 1:
            raise ValueError("Invalid GPU value")


def enable_scale_to_zero(namespace: str = "knative-serving") -> None:
    """
    Enable scale to zero for the knative-serving namespace.
    """
    config_map = client.V1ConfigMap(
        api_version="v1",
        kind="ConfigMap",
        metadata=client.V1ObjectMeta(
            name="config-autoscaler",
            namespace=namespace,
        ),
        data={
            "enable-scale-to-zero": "true",
        },
    )

    api_instance = client.CoreV1Api()
    api_instance.patch_namespaced_config_map(
        name="config-autoscaler",
        namespace="knative-serving",
        body=config_map,
    )


def create_knative_service(
    service_name: str,
    namespace: str,
    image: str,
    entrypoint: str,
    min_instances: int,
    max_instances: int,
    # concurrency refers to the number of simultaneous requests that a single pod can handle
    # rps refers to requests per second a single pod can handle
    scaling_metric: Tuple[Literal["concurrency", "rps"], str],
    scale_down_delay: str = "0s",
    resource_requests: Optional[Dict[str, str]] = None,
    resource_limits: Optional[Dict[str, str]] = None,
) -> None:
    """
    Creates a Knative Service with the specified configuration.

    This function creates a Knative Service with the provided service name, namespace, image,
    minimum and maximum instances, scaling metric, and scale down delay.

    The function validates the input parameters and raises a ValueError if any of them are invalid.

    Args:
        service_name (str): The name of the service.
        namespace (str): The namespace to create the service in.
        image (str): The Docker image for the service.
        min_instances (int): The minimum number of instances for the service.
        max_instances (int): The maximum number of instances for the service.
        scaling_metric (Tuple[Literal["concurrency", "rps"], str]): The scaling metric and target value.
        scale_down_delay (str, optional): The delay before scaling down. Defaults to "0s".
        resource_requests (Optional[Dict[str, str]], optional): The resource requests for the service, in the format {"cpu": "100m", "memory": "128Mi"}. Defaults to None.
        resource_limits (Optional[Dict[str, str]], optional): The resource limits for the service, in the format {"cpu": "200m", "memory": "256Mi", "gpu": "1"}. Defaults to None.

    Raises:
        ValueError: If any of the input parameters are invalid.

    Returns:
        None
    """
    if not isinstance(min_instances, int) or not isinstance(max_instances, int):
        raise ValueError("min_replicas and max_replicas must be integers")
    if min_instances > max_instances:
        raise ValueError("min_replicas cannot be greater than max_replicas")

    metric_key, metric_value = scaling_metric
    if metric_key not in ["concurrency", "rps"]:
        raise ValueError(f"Invalid key in scaling_metric: {metric_key}")
    if not metric_value.isdigit():
        raise ValueError(f"Invalid value in scaling_metric: {metric_value}")

    container: Dict[str, Any] = {
        "image": image,
        "imagePullPolicy": "Always",
        "command": shlex.split(entrypoint),
    }

    if resource_limits or resource_requests:
        container["resources"] = {}

    if resource_requests:
        if not all(key in VALID_RESOURCES for key in resource_requests.keys()):
            raise ValueError(
                f"Invalid resource request key. Valid keys are {VALID_RESOURCES}"
            )
        for resource, value in resource_requests.items():
            validate_resource(resource, value)
        container["resources"]["requests"] = resource_requests

    if resource_limits:
        if not all(
            key in (VALID_RESOURCES + VALID_RESOURCES_GPU)
            for key in resource_limits.keys()
        ):
            raise ValueError(
                f"Invalid resource limit key. Valid keys are {VALID_RESOURCES + VALID_RESOURCES_GPU}"
            )
        for resource, value in resource_limits.items():
            validate_resource(resource, value)
        container["resources"]["limits"] = resource_limits

    metric = {
        "autoscaling.knative.dev/metric": metric_key,
        "autoscaling.knative.dev/target": metric_value,
    }

    # Create the Knative Service
    knative_service = {
        "apiVersion": "serving.knative.dev/v1",
        "kind": "Service",
        "metadata": {
            "name": service_name,
            "namespace": namespace,
        },
        "spec": {
            "template": {
                "metadata": {
                    "annotations": {
                        "autoscaling.knative.dev/class": "kpa.autoscaling.knative.dev",
                        "autoscaling.knative.dev/min-scale": str(min_instances),
                        "autoscaling.knative.dev/max-scale": str(max_instances),
                        "autoscaling.knative.dev/scale-down-delay": scale_down_delay,
                        **metric,
                    },
                },
                "spec": {"containers": [container]},
            }
        },
    }

    k8s_client = client.ApiClient()
    dyn_client = DynamicClient(k8s_client)

    service_resource = dyn_client.resources.get(
        api_version="serving.knative.dev/v1", kind="Service"
    )

    try:
        service_resource.get(name=service_name, namespace=namespace)
        service_resource.patch(
            body=knative_service,
            namespace=namespace,
            name=service_name,
            content_type="application/merge-patch+json",
        )
    except ApiException as e:
        if e.status == 404:
            service_resource.create(body=knative_service, namespace=namespace)
        else:
            raise


def list_knative_services(namespace: str) -> Any:
    """
    List all Knative Services in the specified namespace.

    Args:
        namespace (str): The namespace to list services in. Defaults to "knative-serving".

    Returns:
        None
    """
    k8s_client = client.ApiClient()
    dyn_client = DynamicClient(k8s_client)

    service_resource = dyn_client.resources.get(
        api_version="serving.knative.dev/v1", kind="Service"
    )

    return service_resource.get(namespace=namespace)


def delete_knative_service(service_name: str, namespace: str) -> None:
    """
    Delete a Knative Service.

    Args:
        service_name (str): The name of the service to delete.
        namespace (str): The namespace to delete the service from.

    Returns:
        None
    """
    k8s_client = client.ApiClient()
    dyn_client = DynamicClient(k8s_client)

    service_resource = dyn_client.resources.get(
        api_version="serving.knative.dev/v1", kind="Service"
    )

    service_resource.delete(name=service_name, namespace=namespace)


def list_knative_revisions(namespace: str, service_name: Optional[str] = None) -> Any:
    """
    List all Knative Revisions in the specified namespace.

    Args:
        namespace (str): The namespace to list revisions in.
        service_name (str, optional): The name of the service to list revisions for. If None, list revisions for all services.

    Returns:
        None
    """
    k8s_client = client.ApiClient()
    dyn_client = DynamicClient(k8s_client)

    service_resource = dyn_client.resources.get(
        api_version="serving.knative.dev/v1", kind="Service"
    )

    if not service_name:
        services = service_resource.get(namespace=namespace).items
    else:
        try:
            services = [service_resource.get(name=service_name, namespace=namespace)]
        except client.ApiException as e:
            if e.status == 404:
                services = []

    revision_resource = dyn_client.resources.get(
        api_version="serving.knative.dev/v1", kind="Revision"
    )

    try:
        revisions = revision_resource.get(namespace=namespace).items
    except client.ApiException as e:
        if e.status == 404:
            revisions = []

    for service in services:
        service_revisions = [
            rev
            for rev in revisions
            if rev.metadata.labels["serving.knative.dev/service"]
            == service.metadata.name
        ]

        # Add traffic information to the revisions
        traffic_list = (
            service.spec.traffic if service.spec and service.spec.traffic else []
        )
        for traffic in traffic_list:
            for rev in service_revisions:
                if rev.metadata.name == traffic.revisionName:
                    rev.traffic = f"{traffic.percent}%"

        return sorted(
            service_revisions,
            key=lambda x: int(
                x.metadata.labels["serving.knative.dev/configurationGeneration"]
            ),
            reverse=True,
        )


def split_traffic_among_revisions(
    namespace: str,
    service_name: str,
    traffic_splits: List[Tuple[str, int]],
    latest_revision_traffic: int,
) -> None:
    """
    Split traffic among the specified revisions of a service.

    Args:
        service_name (str): The name of the service.
        namespace (str): The namespace of the service.
        traffic_splits (List[Tuple[str, int]]): A list of tuples, where each tuple contains a revision name and a traffic percent.
        latest_revision_traffic (int): The traffic percent to assign to the latest revision.

    Raises:
        ValueError: If the traffic percent is not valid.

    Returns:
        None
    """
    total_traffic_percent = (
        sum(percent for _, percent in traffic_splits) + latest_revision_traffic
    )

    if not all(0 <= percent <= 100 for _, percent in traffic_splits) or not (
        0 <= latest_revision_traffic <= 100
    ):
        raise ValueError("All traffic percents must be between 0 and 100")

    if total_traffic_percent != 100:
        raise ValueError("Total traffic percent should be 100%")

    k8s_client = client.ApiClient()
    dyn_client = DynamicClient(k8s_client)

    service_resource = dyn_client.resources.get(
        api_version="serving.knative.dev/v1", kind="Service"
    )

    service = service_resource.get(name=service_name, namespace=namespace)

    traffic = [
        {
            "revisionName": revision_name,
            "percent": percent,
        }
        for revision_name, percent in traffic_splits
    ]

    if latest_revision_traffic > 0:
        traffic.append(
            {
                "latestRevision": True,
                "percent": latest_revision_traffic,
            }
        )

    service_spec = service.to_dict()

    service_spec["spec"]["traffic"] = traffic

    service_resource.patch(
        body=service_spec,
        namespace=namespace,
        name=service_name,
        content_type="application/merge-patch+json",
    )
