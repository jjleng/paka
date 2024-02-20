import shlex
from typing import Any, Literal, Tuple

from kubernetes import client
from kubernetes.dynamic import DynamicClient
from kubernetes.dynamic.exceptions import NotFoundError

from paka.k8s import try_load_kubeconfig

try_load_kubeconfig()


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
                "spec": {
                    "containers": [
                        {
                            "image": image,
                            "imagePullPolicy": "Always",
                            "command": shlex.split(entrypoint),
                        }
                    ]
                },
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
    except NotFoundError:
        service_resource.create(body=knative_service, namespace=namespace)


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
