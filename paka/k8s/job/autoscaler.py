from kubernetes import client

from paka.k8s.utils import (
    CustomResource,
    apply_resource,
    delete_namespaced_custom_object,
)


def create_autoscaler(
    namespace: str,
    redis_svc_name: str,
    queue_name: str,
    trigger_queue_length: int,
    job_name: str,
    min_replicas: int,
    max_replicas: int,
) -> None:
    """
    Creates a KEDA autoscaler for a job with a Redis trigger.

    The autoscaler scales the job based on the length of a Redis list.
    The job is scaled up when the list length exceeds the trigger queue length,
    and scaled down when the list is empty.

    Args:
        namespace (str): The namespace to create the resources in.
        redis_svc_name (str): The name of the Redis service.
        queue_name (str): The name of the Redis list to monitor.
        trigger_queue_length (int): The list length at which to trigger scaling.
        job_name (str): The name of the job to scale.
        min_replicas (int): The minimum number of job replicas.
        max_replicas (int): The maximum number of job replicas.

    Returns:
        None
    """
    scaled_object = CustomResource(
        api_version="keda.sh/v1alpha1",
        kind="ScaledObject",
        plural="scaledobjects",
        metadata=client.V1ObjectMeta(name=job_name, namespace=namespace),
        spec={
            "scaleTargetRef": {
                "kind": "Deployment",
                "name": job_name,
            },
            "minReplicaCount": min_replicas,
            "maxReplicaCount": max_replicas,
            "triggers": [
                {
                    "type": "redis",
                    "metadata": {
                        "type": "list",
                        "listName": queue_name,
                        "listLength": f"{trigger_queue_length}",
                        "address": f"{redis_svc_name}.redis.svc.cluster.local:6379",
                    },
                }
            ],
        },
    )
    apply_resource(scaled_object)


def delete_autoscaler(namespace: str, job_name: str) -> None:
    scaled_object = CustomResource(
        api_version="keda.sh/v1alpha1",
        kind="ScaledObject",
        plural="scaledobjects",
        metadata=client.V1ObjectMeta(name=job_name, namespace=namespace),
        spec={},
    )
    delete_namespaced_custom_object(job_name, namespace, scaled_object)
