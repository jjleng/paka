from kubernetes import client

from light.config import CloudConfig, CloudModelGroup, Config
from light.constants import SERVICE_ACCOUNT
from light.k8s import apply_resource
from light.utils import kubify_name

# We hardcode the image here for now
LLAMA_CPP_PYTHON_IMAGE = "ghcr.io/abetlen/llama-cpp-python:latest"


def init_aws(config: CloudConfig, model_group: CloudModelGroup) -> client.V1Container:
    """
    Initializes an AWS container for downloading a model from S3.

    Args:
        config (CloudConfig): The cloud configuration.
        model_group (CloudModelGroup): The cloud model group.

    Returns:
        client.V1Container: The initialized AWS container.
    """
    bucket = config.cluster.name
    return client.V1Container(
        name="init-s3-model-download",
        image="amazon/aws-cli",
        command=[
            "aws",
            "s3",
            "cp",
            f"s3://{bucket}/models/{model_group.name}",
            f"/data/{model_group.name}",
        ],
        volume_mounts=[
            client.V1VolumeMount(
                name="model-data",
                mount_path="/data",
            )
        ],
    )


def create_pod(
    config: Config, model_group: CloudModelGroup, runtime_image: str, port: int
) -> client.V1Pod:
    """
    Creates a Kubernetes pod for a model group.

    Args:
        config (Config): The configuration object.
        model_group (CloudModelGroup): The model group object.
        runtime_image (str): The runtime image for the pod.
        port (int): The port number for the pod.

    Returns:
        client.V1Pod: The created Kubernetes pod.
    """
    if config.aws is None:
        raise ValueError("Only AWS is supported at this time")

    return client.V1Pod(
        metadata=client.V1ObjectMeta(
            name=f"{kubify_name(model_group.name)}-pod",
            labels={
                "app": "model-group",
                "model": model_group.name,
            },
        ),
        spec=client.V1PodSpec(
            service_account_name=SERVICE_ACCOUNT,
            volumes=[
                client.V1Volume(
                    name="model-data",
                    empty_dir=client.V1EmptyDirVolumeSource(),
                )
            ],
            init_containers=[init_aws(config.aws, model_group)],
            containers=[
                client.V1Container(
                    name=f"{kubify_name(model_group.name)}-container",
                    image=runtime_image,
                    volume_mounts=[
                        client.V1VolumeMount(
                            name="model-data",
                            mount_path="/data",
                        )
                    ],
                    env=[
                        client.V1EnvVar(
                            name="USE_MLOCK",  # Model weights are locked in RAM or not
                            value="0",
                        ),
                        client.V1EnvVar(
                            name="MODEL",
                            value=f"/data/{model_group.name}",
                        ),
                        client.V1EnvVar(
                            name="PORT",
                            value=str(port),
                        ),
                    ],
                    # A good estimate for the resources required for a model group
                    # This will make the pod's QoS to be `Burstable`
                    resources=client.V1ResourceRequirements(
                        requests={
                            "cpu": "1900m",  # 1.9 CPU core
                            "memory": "8Gi",  # 8 GB RAM
                        },
                    ),
                    readiness_probe=client.V1Probe(
                        http_get=client.V1HTTPGetAction(
                            path="/v1/models",
                            port=port,
                        ),
                        initial_delay_seconds=60,
                        period_seconds=30,
                    ),
                    liveness_probe=client.V1Probe(
                        http_get=client.V1HTTPGetAction(
                            path="/v1/models",
                            port=port,
                        ),
                        initial_delay_seconds=240,
                        period_seconds=30,
                    ),
                )
            ],
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
    model_group: CloudModelGroup, pod: client.V1Pod
) -> client.V1Deployment:
    """
    Create a deployment for a model group.

    Args:
        model_group (CloudModelGroup): The model group object.
        pod (client.V1Pod): The pod object.

    Returns:
        client.V1Deployment: The created deployment object.
    """

    return client.V1Deployment(
        api_version="apps/v1",
        kind="Deployment",
        metadata=client.V1ObjectMeta(
            name=f"{kubify_name(model_group.name)}-deployment",
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


def create_service(model_group: CloudModelGroup, port: int) -> client.V1Service:
    """
    Creates a Kubernetes service for a given model group.

    Args:
        model_group (CloudModelGroup): The model group for which the service is created.
        port (int): The port number to expose for the service.

    Returns:
        V1Service: The created Kubernetes service.
    """
    return client.V1Service(
        api_version="v1",
        kind="Service",
        metadata=client.V1ObjectMeta(
            name=f"{kubify_name(model_group.name)}-service",
        ),
        spec=client.V1ServiceSpec(
            selector={
                "app": "model-group",
                "model": model_group.name,
            },
            ports=[
                client.V1ServicePort(
                    port=80,
                    target_port=port,
                )
            ],
        ),
    )


def create_hpa(
    model_group: CloudModelGroup, deployment: client.V1Deployment
) -> client.V2HorizontalPodAutoscaler:
    """
    Create a HorizontalPodAutoscaler for a given model group and deployment.

    Args:
        model_group (CloudModelGroup): The model group object.
        deployment (client.V1Deployment): The deployment object.

    Returns:
        client.V2HorizontalPodAutoscaler: The created HorizontalPodAutoscaler object.
    """
    return client.V2HorizontalPodAutoscaler(
        api_version="autoscaling/v2",
        kind="HorizontalPodAutoscaler",
        metadata=client.V1ObjectMeta(
            name=f"{kubify_name(model_group.name)}-hpa",
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


def create_model_group_service(
    config: Config,
    model_group: CloudModelGroup,
) -> None:
    """
    Creates a model group service.

    Args:
        config (Config): The configuration object.
        model_group (CloudModelGroup): The model group object.
        k8s_provider (k8s.Provider): The Kubernetes provider.

    Returns:
        None
    """
    if config.aws is None:
        raise ValueError("Only AWS is supported at this time")
    kubeconfig_name = config.aws.cluster.name

    port = 8000

    pod = create_pod(config, model_group, LLAMA_CPP_PYTHON_IMAGE, port)

    deployment = create_deployment(model_group, pod)
    apply_resource(deployment)

    svc = create_service(model_group, port)
    apply_resource(svc)

    hpa = create_hpa(model_group, deployment)
    apply_resource(hpa)
