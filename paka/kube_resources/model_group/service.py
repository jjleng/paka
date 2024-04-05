from typing import Any, List, Optional

from kubernetes import client

from paka.config import CloudConfig, CloudModelGroup, Config
from paka.constants import ACCESS_ALL_SA
from paka.k8s import CustomResource, apply_resource, try_load_kubeconfig
from paka.kube_resources.model_group.model import MODEL_PATH_PREFIX, download_model
from paka.utils import kubify_name, read_cluster_data

# `latest` will be stale because of the `IfNotPresent` policy
# We hardcode the image here for now, we can make it configurable later
LLAMA_CPP_PYTHON_IMAGE = "ghcr.io/abetlen/llama-cpp-python:latest"

LLAMA_CPP_PYTHON_CUDA = "jijunleng/llama-cpp-python-cuda:latest"

try_load_kubeconfig()


def init_aws(config: CloudConfig, model_group: CloudModelGroup) -> client.V1Container:
    """
    Initializes an AWS container for downloading a model from S3.

    Args:
        config (CloudConfig): The cloud configuration.
        model_group (CloudModelGroup): The cloud model group.

    Returns:
        client.V1Container: The initialized AWS container.
    """
    bucket = read_cluster_data(config.cluster.name, "bucket")

    return client.V1Container(
        name="init-s3-model-download",
        image="amazon/aws-cli",
        command=[
            "aws",
            "s3",
            "cp",
            f"s3://{bucket}/{MODEL_PATH_PREFIX}/{model_group.name}/",
            "/data/",
            "--recursive",
        ],
        volume_mounts=[
            client.V1VolumeMount(
                name="model-data",
                mount_path="/data",
            )
        ],
    )


def init_parse_manifest() -> client.V1Container:
    """
    Initializes a container for creating a symbolic link to the model file.

    Returns:
        client.V1Container: The initialized container for handling the manifest.
    """
    return client.V1Container(
        name="init-parse-manifest",
        image="busybox",
        command=[
            "sh",
            "-c",
            "model_type=$(cat /data/manifest.yaml | grep 'type' | cut -d ':' -f2 | tr -d ' '); "
            'if [ "$model_type" != "gguf" ]; then echo \'Invalid model type\' && exit 1; fi; '
            "model_file=$(cat /data/manifest.yaml | grep 'file' | cut -d ':' -f2 | tr -d ' '); "
            "ln -s /data/${model_file} /data/my_model.gguf",
        ],
        volume_mounts=[
            client.V1VolumeMount(
                name="model-data",
                mount_path="/data",
            )
        ],
    )


def create_pod(
    namespace: str,
    config: Config,
    model_group: CloudModelGroup,
    runtime_image: str,
    port: int,
) -> client.V1Pod:
    """
    Creates a Kubernetes Pod for a machine learning model group.

    This function creates a Kubernetes Pod with the specified configuration. The Pod runs a container
    with the specified runtime image and exposes the specified port. The container runs a machine learning
    model from the model group.

    Args:
        namespace (str): The namespace to create the Pod in.
        config (Config): The configuration for the Pod.
        model_group (CloudModelGroup): The model group to run in the Pod.
        runtime_image (str): The runtime image for the container.
        port (int): The port to expose on the container.

    Raises:
        ValueError: If the AWS configuration is not provided.

    Returns:
        client.V1Pod: The created Pod.
    """
    if config.aws is None:
        raise ValueError("Only AWS is supported at this time")

    container_args = {
        "name": f"{kubify_name(model_group.name)}",
        "image": runtime_image,
        "volume_mounts": [
            client.V1VolumeMount(
                name="model-data",
                mount_path="/data",
            )
        ],
        "env": [
            client.V1EnvVar(
                name="USE_MLOCK",  # Model weights are locked in RAM or not
                value="1",
            ),
            client.V1EnvVar(
                name="MODEL",
                value=f"/data/my_model.gguf",
            ),
            client.V1EnvVar(
                name="PORT",
                value=str(port),
            ),
        ],
        "readiness_probe": client.V1Probe(
            http_get=client.V1HTTPGetAction(
                path="/v1/models",
                port=port,
            ),
            initial_delay_seconds=60,
            period_seconds=5,
            timeout_seconds=30,
            success_threshold=1,
            failure_threshold=5,
        ),
        "liveness_probe": client.V1Probe(
            http_get=client.V1HTTPGetAction(
                path="/v1/models",
                port=port,
            ),
            initial_delay_seconds=240,
            period_seconds=30,
            timeout_seconds=30,
            success_threshold=1,
            failure_threshold=5,
        ),
    }

    if model_group.resourceRequest:
        container_args["resources"] = client.V1ResourceRequirements(
            requests={
                "cpu": model_group.resourceRequest.cpu,
                "memory": model_group.resourceRequest.memory,
            },
        )

    if model_group.awsGpu and model_group.awsGpu.enabled:
        if "resources" not in container_args:
            container_args["resources"] = client.V1ResourceRequirements(
                requests={},
            )
        # Ah, we only support nvidia GPUs for now
        container_args["resources"].requests["nvidia.com/gpu"] = 1

    return client.V1Pod(
        metadata=client.V1ObjectMeta(
            name=f"{kubify_name(model_group.name)}",
            namespace=namespace,
            labels={
                "app": "model-group",
                "model": model_group.name,
            },
        ),
        spec=client.V1PodSpec(
            service_account_name=ACCESS_ALL_SA,
            volumes=[
                client.V1Volume(
                    name="model-data",
                    empty_dir=client.V1EmptyDirVolumeSource(),
                )
            ],
            init_containers=[init_aws(config.aws, model_group), init_parse_manifest()],
            containers=[client.V1Container(**container_args)],
            tolerations=[
                client.V1Toleration(
                    key="app",
                    value="model-group",
                    effect="NoSchedule",
                ),
                client.V1Toleration(
                    key="model",
                    value=model_group.name,
                    effect="NoSchedule",
                ),
            ],
            affinity=client.V1Affinity(
                node_affinity=client.V1NodeAffinity(
                    required_during_scheduling_ignored_during_execution=client.V1NodeSelector(
                        node_selector_terms=[
                            client.V1NodeSelectorTerm(
                                match_expressions=[
                                    client.V1NodeSelectorRequirement(
                                        key="app", operator="In", values=["model-group"]
                                    ),
                                    client.V1NodeSelectorRequirement(
                                        key="model",
                                        operator="In",
                                        values=[model_group.name],
                                    ),
                                ]
                            )
                        ]
                    )
                ),
                pod_anti_affinity=client.V1PodAntiAffinity(
                    required_during_scheduling_ignored_during_execution=[
                        client.V1PodAffinityTerm(
                            label_selector=client.V1LabelSelector(
                                match_labels={
                                    "app": "model-group",
                                    "model": model_group.name,
                                }
                            ),
                            topology_key="kubernetes.io/hostname",
                        )
                    ]
                ),
            ),
        ),
    )


def create_deployment(
    namespace: str, model_group: CloudModelGroup, pod: client.V1Pod
) -> client.V1Deployment:
    """
    Creates a Kubernetes Deployment for a machine learning model group.

    Args:
        namespace (str): The namespace to create the Deployment in.
        model_group (CloudModelGroup): The model group to run in the Deployment.
        pod (client.V1Pod): The Pod to use as a template for the Deployment.

    Returns:
        client.V1Deployment: The created Deployment.
    """
    return client.V1Deployment(
        api_version="apps/v1",
        kind="Deployment",
        metadata=client.V1ObjectMeta(
            name=f"{kubify_name(model_group.name)}",
            namespace=namespace,
        ),
        spec=client.V1DeploymentSpec(
            replicas=model_group.minInstances,
            selector=client.V1LabelSelector(
                match_labels={
                    "app": "model-group",
                    "model": model_group.name,
                }
            ),
            template=pod,
        ),
    )


def create_service_monitor(namespace: str, model_group: CloudModelGroup) -> None:
    monitor = CustomResource(
        api_version="monitoring.coreos.com/v1",
        kind="ServiceMonitor",
        plural="servicemonitors",
        metadata=client.V1ObjectMeta(
            name=f"{model_group.name}-monitor", namespace=namespace
        ),
        spec={
            "selector": {
                "matchLabels": {"app": "model-group", "model": model_group.name}
            },
            "namespaceSelector": {
                "matchNames": [namespace],
            },
            "endpoints": [
                {
                    "port": "http-envoy-prom",
                    "path": "/stats/prometheus",
                    "interval": "15s",
                },
            ],
        },
    )
    apply_resource(monitor)


def create_service(
    namespace: str, model_group: CloudModelGroup, port: int, sidecar_port: int = 15090
) -> client.V1Service:
    """
    Creates a Kubernetes Service for a machine learning model group.

    Args:
        namespace (str): The namespace to create the Service in.
        model_group (CloudModelGroup): The model group to expose with the Service.
        port (int): The port to expose on the Service.
        sidecar_port (int): The port on which the istio sidecar is exposing metrics.


    Returns:
        client.V1Service: The created Service.
    """
    return client.V1Service(
        api_version="v1",
        kind="Service",
        metadata=client.V1ObjectMeta(
            name=f"{kubify_name(model_group.name)}",
            namespace=namespace,
            labels={
                "app": "model-group",
                "model": model_group.name,
            },
        ),
        spec=client.V1ServiceSpec(
            selector={
                "app": "model-group",
                "model": model_group.name,
            },
            ports=[
                client.V1ServicePort(
                    name="http-app",
                    port=80,
                    target_port=port,
                ),
                client.V1ServicePort(
                    name="http-envoy-prom",
                    port=sidecar_port,
                    target_port=sidecar_port,
                ),
            ],
        ),
    )


def filter_services(namespace: str) -> List[Any]:
    """
    Filters the Kubernetes Services in a namespace that belong to a model group.

    Args:
        namespace (str): The namespace to filter the Services in.

    Returns:
        List[Any]: The filtered Services.
    """

    v1 = client.CoreV1Api()

    services = v1.list_namespaced_service(namespace)
    filtered_services = [
        service
        for service in services.items
        if service.spec.selector
        and service.spec.selector.get("app") == "model-group"
        and service.spec.selector.get("model")
    ]

    return filtered_services


def create_hpa(
    namespace: str, model_group: CloudModelGroup, deployment: client.V1Deployment
) -> client.V2HorizontalPodAutoscaler:
    """
    Creates a Kubernetes Horizontal Pod Autoscaler (HPA) for a machine learning model group.

    This function creates a Kubernetes HPA with the specified namespace, model group, and deployment.
    The HPA automatically scales the number of Pods in the deployment based on the CPU utilization.

    The HPA is configured to maintain a specified number of replicas of the Pod.
    The HPA increases the number of replicas when the average CPU utilization exceeds 95%.

    Args:
        namespace (str): The namespace to create the HPA in.
        model_group (CloudModelGroup): The model group to scale with the HPA.
        deployment (client.V1Deployment): The deployment to scale.

    Returns:
        client.V2HorizontalPodAutoscaler: The created HPA.
    """
    return client.V2HorizontalPodAutoscaler(
        api_version="autoscaling/v2",
        kind="HorizontalPodAutoscaler",
        metadata=client.V1ObjectMeta(
            name=f"{kubify_name(model_group.name)}",
            namespace=namespace,
        ),
        spec=client.V2HorizontalPodAutoscalerSpec(
            scale_target_ref=client.V2CrossVersionObjectReference(
                api_version="apps/v1",
                kind="Deployment",
                name=deployment.metadata.name,
            ),
            min_replicas=model_group.minInstances,
            max_replicas=model_group.maxInstances,
            metrics=[
                client.V2MetricSpec(
                    type="Resource",
                    resource=client.V2ResourceMetricSource(
                        name="cpu",
                        target=client.V2MetricTarget(
                            type="Utilization",
                            average_utilization=50,
                        ),
                    ),
                )
            ],
        ),
    )


def create_scaled_object(
    namespace: str, model_group: CloudModelGroup, deployment: client.V1Deployment
) -> Optional[CustomResource]:
    """
    Creates a KEDA ScaledObject for a given model group.

    This function creates a ScaledObject custom resource for Kubernetes Event-driven Autoscaling (KEDA).
    The ScaledObject is used to scale a Kubernetes Deployment based on the triggers defined in the model group.

    Args:
        namespace (str): The namespace in which to create the ScaledObject.
        model_group (CloudModelGroup): The model group for which to create the ScaledObject.
            This object should have `autoScaleTriggers`, `minInstances`, and `maxInstances` attributes.
        deployment (client.V1Deployment): The Kubernetes Deployment that the ScaledObject should scale.

    Returns:
        None
    """
    if not model_group.autoScaleTriggers:
        return None

    return CustomResource(
        api_version="keda.sh/v1alpha1",
        kind="ScaledObject",
        plural="scaledobjects",
        metadata=client.V1ObjectMeta(
            name=f"{kubify_name(model_group.name)}", namespace=namespace
        ),
        spec={
            "scaleTargetRef": {
                "kind": "Deployment",
                "name": deployment.metadata.name,
            },
            "minReplicaCount": model_group.minInstances,
            "maxReplicaCount": model_group.maxInstances,
            "pollingInterval": 15,
            "triggers": list(
                map(
                    lambda trigger: {
                        "type": trigger.type,
                        "metadata": trigger.metadata,
                    },
                    model_group.autoScaleTriggers,
                )
            ),
        },
    )


def create_model_group_service(
    namespace: str,
    config: Config,
    model_group: CloudModelGroup,
) -> None:
    """
    Creates a Kubernetes service for a machine learning model group.

    Args:
        namespace (str): The namespace to create the service in.
        config (Config): The configuration for the service.
        model_group (CloudModelGroup): The model group to create the service for.

    Raises:
        ValueError: If the AWS configuration is not provided.

    Returns:
        None
    """
    if config.aws is None:
        raise ValueError("Only AWS is supported at this time")

    # Download the model to S3 first
    download_model(model_group.name)

    port = 8000

    pod = create_pod(
        namespace,
        config,
        model_group,
        (
            LLAMA_CPP_PYTHON_CUDA
            if model_group.awsGpu and model_group.awsGpu.enabled
            else LLAMA_CPP_PYTHON_IMAGE
        ),
        port,
    )

    deployment = create_deployment(namespace, model_group, pod)
    apply_resource(deployment)

    svc = create_service(namespace, model_group, port)
    apply_resource(svc)

    if config.aws.prometheus and config.aws.prometheus.enabled:
        create_service_monitor(namespace, model_group)

    scaled_object = create_scaled_object(namespace, model_group, deployment)
    if scaled_object:
        apply_resource(scaled_object)
