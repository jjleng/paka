import pulumi
import pulumi_kubernetes as k8s
from light.constants import SERVICE_ACCOUNT
from light.cluster.config import CloudConfig, CloudModelGroup, Config


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
            "/data/{model_group.name}",
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
    k8s_provider: k8s.Provider,
) -> None:
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
                )
            ],
        ),
        opts=pulumi.ResourceOptions(provider=k8s_provider),
    )


def create_service(
    model_group: CloudModelGroup,
    k8s_provider: k8s.Provider,
) -> k8s.core.v1.Service:
    """
    Creates a Kubernetes service for the model service.

    Args:
        config (pulumi.Config): The Pulumi configuration object.
        service_account (k8s.core.v1.ServiceAccount): The service account for the model service.
        pod (k8s.core.v1.Pod): The pod for the model service.

    Returns:
        None
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
                    target_port=8080,
                )
            ],
        ),
        opts=pulumi.ResourceOptions(provider=k8s_provider),
    )


# HPA Configuration
def create_hpa(
    model_group: CloudModelGroup,
    service: k8s.core.v1.Service,
    k8s_provider: k8s.Provider,
) -> k8s.autoscaling.v2beta2.HorizontalPodAutoscaler:
    """
    Creates a HorizontalPodAutoscaler for the model service.

    Args:
        service (k8s.core.v1.Service): The service for the model service.

    Returns:
        None
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
