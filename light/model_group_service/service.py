import pulumi
import pulumi_kubernetes as k8s
from light.constants import SERVICE_ACCOUNT
from light.config import CloudConfig, CloudModelGroup, Config

# We hardcode the image here for now
LLAMA_CPP_PYTHON_IMAGE = "ghcr.io/abetlen/llama-cpp-python:latest"


def init_aws(
    config: CloudConfig, model_group: CloudModelGroup
) -> k8s.core.v1.ContainerArgs:
    bucket = config.cluster.name
    return k8s.core.v1.ContainerArgs(
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
            k8s.core.v1.VolumeMountArgs(
                name="model-data",
                mount_path="/data",
            )
        ],
    )


def create_pod(
    config: Config,
    model_group: CloudModelGroup,
    runtime_image: str,
    port: int,
    k8s_provider: k8s.Provider,
) -> None:
    """
    Creates a Kubernetes pod for the given model group.

    Args:
        config (Config): The configuration object.
        model_group (CloudModelGroup): The model group object.
        runtime_image (str): The runtime image for the container.
        port (int): The port number for the container.
        k8s_provider (k8s.Provider): The Kubernetes provider.

    Raises:
        ValueError: If the config does not have AWS information.

    Returns:
        None
    """
    if config.aws is None:
        raise ValueError("Only AWS is supported at this time")

    k8s.core.v1.Pod(
        f"{model_group.name}-pod",
        metadata=k8s.meta.v1.ObjectMetaArgs(
            labels={
                "app": "model-group",
                "model": model_group.name,
            },
        ),
        spec=k8s.core.v1.PodSpecArgs(
            service_account_name=SERVICE_ACCOUNT,
            volumes=[
                k8s.core.v1.VolumeArgs(
                    name="model-data",
                    empty_dir=k8s.core.v1.EmptyDirVolumeSourceArgs(),
                )
            ],
            init_containers=[init_aws(config.aws, model_group)],
            containers=[
                k8s.core.v1.ContainerArgs(
                    name=f"{model_group.name}-container",
                    image=runtime_image,
                    volume_mounts=[
                        k8s.core.v1.VolumeMountArgs(
                            name="model-data",
                            mount_path="/data",
                        )
                    ],
                    env=[
                        k8s.core.v1.EnvVarArgs(
                            name="USE_MLOCK",  # Model weights are locked in RAM or not
                            value="0",
                        ),
                        k8s.core.v1.EnvVarArgs(
                            name="MODEL",
                            value=f"/data/{model_group.name}",
                        ),
                        k8s.core.v1.EnvVarArgs(
                            name="PORT",
                            value=str(port),
                        ),
                    ],
                    # A good estimate for the resources required for a model group
                    # This will make the pod's priority to be `Burstable`
                    resources=k8s.core.v1.ResourceRequirementsArgs(
                        requests={
                            "cpu": "900m",  # 0.9 CPU core
                            "memory": "8Gi",  # 8 GB RAM
                        },
                    ),
                )
            ],
            tolerations=[
                k8s.core.v1.TolerationArgs(
                    key="app",
                    value="model-group",
                    effect="NoSchedule",
                ),
                k8s.core.v1.TolerationArgs(
                    key="model",
                    value=model_group.name,
                    effect="NoSchedule",
                ),
            ],
            affinity=k8s.core.v1.AffinityArgs(
                node_affinity=k8s.core.v1.NodeAffinityArgs(
                    required_during_scheduling_ignored_during_execution=k8s.core.v1.NodeSelectorArgs(
                        node_selector_terms=[
                            k8s.core.v1.NodeSelectorTermArgs(
                                match_expressions=[
                                    k8s.core.v1.NodeSelectorRequirementArgs(
                                        key="app",
                                        operator="In",
                                        values=["model-group"],
                                    ),
                                    k8s.core.v1.NodeSelectorRequirementArgs(
                                        key="model",
                                        operator="In",
                                        values=[model_group.name],
                                    ),
                                ]
                            )
                        ]
                    )
                ),
                pod_anti_affinity=k8s.core.v1.PodAntiAffinityArgs(
                    required_during_scheduling_ignored_during_execution=[
                        k8s.core.v1.PodAffinityTermArgs(
                            label_selector=k8s.meta.v1.LabelSelectorArgs(
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
        opts=pulumi.ResourceOptions(provider=k8s_provider),
    )


def create_service(
    model_group: CloudModelGroup,
    port: int,
    k8s_provider: k8s.Provider,
) -> k8s.core.v1.Service:
    """
    Creates a Kubernetes service for a given model group.

    Args:
        model_group (CloudModelGroup): The model group for which the service is created.
        port (int): The port number to expose for the service.
        k8s_provider (k8s.Provider): The Kubernetes provider.

    Returns:
        k8s.core.v1.Service: The created Kubernetes service.
    """
    return k8s.core.v1.Service(
        f"{model_group.name}-service",
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name=f"{model_group.name}-service",
        ),
        spec=k8s.core.v1.ServiceSpecArgs(
            selector={
                "app": "model-group",
                "model": model_group.name,
            },
            ports=[
                k8s.core.v1.ServicePortArgs(
                    port=80,
                    target_port=port,
                )
            ],
        ),
        opts=pulumi.ResourceOptions(provider=k8s_provider),
    )


def create_hpa(
    model_group: CloudModelGroup,
    service: k8s.core.v1.Service,
    k8s_provider: k8s.Provider,
) -> k8s.autoscaling.v2beta2.HorizontalPodAutoscaler:
    """
    Creates a HorizontalPodAutoscaler (HPA) for a given model group service.

    Args:
        model_group (CloudModelGroup): The model group for which the HPA is being created.
        service (k8s.core.v1.Service): The service associated with the model group.
        k8s_provider (k8s.Provider): The Kubernetes provider.

    Returns:
        k8s.autoscaling.v2beta2.HorizontalPodAutoscaler: The created HPA.
    """
    return k8s.autoscaling.v2beta2.HorizontalPodAutoscaler(
        "model-hpa",
        spec=k8s.autoscaling.v2beta2.HorizontalPodAutoscalerSpecArgs(
            scale_target_ref=k8s.autoscaling.v2beta2.CrossVersionObjectReferenceArgs(
                api_version="v1",
                kind="Service",
                name=service.metadata.name,
            ),
            min_replicas=model_group.minInstances,
            max_replicas=model_group.maxInstances,
            metrics=[
                k8s.autoscaling.v2beta2.MetricSpecArgs(
                    type="Resource",
                    resource=k8s.autoscaling.v2beta2.ResourceMetricSourceArgs(
                        name="cpu",
                        target=k8s.autoscaling.v2beta2.MetricTargetArgs(
                            type="Utilization",
                            average_utilization=50,
                        ),
                    ),
                )
            ],
        ),
        opts=pulumi.ResourceOptions(provider=k8s_provider),
    )


def create_model_group_service(
    config: Config,
    model_group: CloudModelGroup,
    k8s_provider: k8s.Provider,
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
    port = 8000
    create_pod(config, model_group, LLAMA_CPP_PYTHON_IMAGE, port, k8s_provider)
    service = create_service(model_group, port, k8s_provider)
    create_hpa(model_group, service, k8s_provider)
