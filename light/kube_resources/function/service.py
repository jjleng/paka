from typing import Literal, Tuple

from kubernetes import client
from kubernetes.dynamic import DynamicClient

from light.k8s import try_load_kubeconfig

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
    min_instances: int,
    max_instances: int,
    # concurrency refers to the number of simultaneous requests that a single pod can handle
    # rps refers to requests per second a single pod can handle
    scaling_metric: Tuple[Literal["concurrency", "rps"], str],
    scale_down_delay: str = "0s",
) -> None:
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
                            "env": [
                                {
                                    "name": "REDIS_PASSWORD",
                                    "valueFrom": {
                                        "secretKeyRef": {
                                            "name": "redis-password",
                                            "key": "password",
                                        }
                                    },
                                }
                            ],
                        }
                    ]
                },
            }
        },
    }

    k8s_client = client.ApiClient()
    dyn_client = DynamicClient(k8s_client)

    dyn_client.resources.get(
        api_version="serving.knative.dev/v1", kind="Service"
    ).create(body=knative_service, namespace=namespace)