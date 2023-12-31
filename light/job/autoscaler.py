from light.k8s import CustomResource, apply_resource
from light.config import CloudConfig
from kubernetes import client


def create_autoscaler(
    config: CloudConfig,
    namespace: str,
    redis_svc_name: str,
    queue_name: str,
    trigger_queue_length: int,
    deployment_name: str,
    min_replicas: int,
    max_replicas: int,
) -> None:
    kubeconfig_name = config.cluster.name

    trigger_auth = CustomResource(
        api_version="keda.sh/v1alpha1",
        kind="TriggerAuthentication",
        plural="triggerauthentications",
        metadata=client.V1ObjectMeta(name="redis-auth-trigger", namespace=namespace),
        spec={
            "secretTargetRef": [
                {"parameter": "password", "name": "redis-password", "key": "password"}
            ]
        },
    )
    apply_resource(kubeconfig_name, trigger_auth)

    scaled_object = CustomResource(
        api_version="keda.sh/v1alpha1",
        kind="ScaledObject",
        plural="scaledobjects",
        metadata=client.V1ObjectMeta(name="redis-worker-scaler", namespace=namespace),
        spec={
            "scaleTargetRef": {
                "kind": "Deployment",
                "name": deployment_name,
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
                        "address": f"{redis_svc_name}.{namespace}.svc.cluster.local:6379",
                    },
                    "authenticationRef": {"name": "redis-auth-trigger"},
                }
            ],
        },
    )
    apply_resource(kubeconfig_name, scaled_object)
