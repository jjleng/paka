from kubernetes import client

from light.config import CloudConfig, CloudModelGroup, Config
from light.constants import ACCESS_ALL_SA
from light.k8s import apply_resource, try_load_kubeconfig
from light.kube_resources.model_group.model import MODEL_PATH_PREFIX, download_model
from light.utils import kubify_name, read_cluster_data

# We hardcode the image here for now
LLAMA_CPP_PYTHON_IMAGE = "ghcr.io/abetlen/llama-cpp-python:latest"

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
            containers=[
                client.V1Container(
                    name=f"{kubify_name(model_group.name)}",
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
                            value=f"/data/my_model.gguf",
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
                            "cpu": "3500m",  # 3.5 CPU core
                            "memory": "6Gi",  # 6 GB RAM
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
    namespace: str, model_group: CloudModelGroup, pod: client.V1Pod
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


def create_service(
    namespace: str, model_group: CloudModelGroup, port: int
) -> client.V1Service:
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
            name=f"{kubify_name(model_group.name)}",
            namespace=namespace,
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


def filter_services(namespace: str) -> list:
    """
    Filters Kubernetes services in a given namespace that have a selector with "app": "model-group".

    Args:
        namespace (str): The namespace in which to filter services.

    Returns:
        list: The filtered Kubernetes services.
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
                            average_utilization=95,
                        ),
                    ),
                )
            ],
        ),
    )


def create_model_group_service(
    namespace: str,
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

    # Download the model to S3 first
    download_model(model_group.name)

    port = 8000

    pod = create_pod(namespace, config, model_group, LLAMA_CPP_PYTHON_IMAGE, port)

    deployment = create_deployment(namespace, model_group, pod)
    apply_resource(deployment)

    svc = create_service(namespace, model_group, port)
    apply_resource(svc)

    hpa = create_hpa(namespace, model_group, deployment)
    apply_resource(hpa)
