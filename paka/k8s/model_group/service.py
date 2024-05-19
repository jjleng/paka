from __future__ import annotations

import json
from typing import List, Optional, Tuple, cast

from kubernetes import client
from kubernetes import config as k8s_config

from paka.cluster.context import Context
from paka.cluster.utils import get_model_store
from paka.config import CloudModelGroup, T_OnDemandModelGroup
from paka.constants import ACCESS_ALL_SA, MODEL_MOUNT_PATH
from paka.k8s.model_group.ingress import create_model_vservice
from paka.k8s.model_group.runtime.llama_cpp import (
    get_runtime_command_llama_cpp,
    is_llama_cpp_image,
)
from paka.k8s.model_group.runtime.vllm import get_runtime_command_vllm, is_vllm_image
from paka.k8s.utils import CustomResource, apply_resource, get_gpu_count
from paka.logger import logger
from paka.model.hf_model import HuggingFaceModel
from paka.model.store import MODEL_PATH_PREFIX
from paka.utils import get_instance_info, kubify_name


def get_runtime_command(
    ctx: Context, model_group: CloudModelGroup, port: int
) -> List[str]:
    """
    Gets the runtime command for a machine learning model group.

    Args:
        model_group (T_CloudModelGroup): The model group to get the runtime command for.

    Returns:
        List[str]: The runtime command.
    """
    command = []  # Default to the command in images
    runtime = model_group.runtime
    if runtime.command and not is_llama_cpp_image(runtime.image):
        command = runtime.command

    # If user did not provide a command, we need to provide a default command with heuristics.
    if is_llama_cpp_image(runtime.image):
        command = get_runtime_command_llama_cpp(ctx, model_group)
    elif is_vllm_image(runtime.image):
        command = get_runtime_command_vllm(ctx, model_group)

    # Add or replace the port in the command
    for i in range(len(command)):
        if command[i] == "--port":
            command[i + 1] = str(port)
            break
    else:
        command.extend(["--port", str(port)])

    return command


def get_health_check_paths(model_group: CloudModelGroup) -> Tuple[str, str]:
    # Return a tuple for ready and live probes
    if is_llama_cpp_image(model_group.runtime.image):
        return ("/health", "/health")
    elif is_vllm_image(model_group.runtime.image):
        return ("/health", "/health")

    raise ValueError("Unsupported runtime image for health check paths.")


def init_aws(ctx: Context, model_group: CloudModelGroup) -> client.V1Container:
    """
    Initializes an AWS container for downloading a model from S3.

    Args:
        config (CloudConfig): The cloud configuration.
        model_group (T_CloudModelGroup): The cloud model group.

    Returns:
        client.V1Container: The initialized AWS container.
    """
    bucket = ctx.bucket

    return client.V1Container(
        name="init-s3-model-download",
        image="amazon/aws-cli",
        command=[
            "aws",
            "s3",
            "cp",
            f"s3://{bucket}/{MODEL_PATH_PREFIX}/{model_group.name}/",
            f"{MODEL_MOUNT_PATH}/",
            "--recursive",
        ],
        volume_mounts=[
            client.V1VolumeMount(
                name="model-data",
                mount_path=MODEL_MOUNT_PATH,
            )
        ],
    )


def create_pod(
    ctx: Context,
    namespace: str,
    model_group: CloudModelGroup,
    port: int,
) -> client.V1PodTemplateSpec:
    """
    Creates a Kubernetes Pod for a machine learning model group.

    This function creates a Kubernetes Pod with the specified configuration. The Pod runs a container
    with the specified runtime image and exposes the specified port. The container runs a machine learning
    model from the model group.

    Args:
        namespace (str): The namespace to create the Pod in.
        config (Config): The configuration for the Pod.
        model_group (T_CloudModelGroup): The model group to run in the Pod.
        runtime_image (str): The runtime image for the container.
        port (int): The port to expose on the container.

    Raises:
        ValueError: If the AWS configuration is not provided.

    Returns:
        client.V1Pod: The created Pod.
    """
    ready_probe_path, live_probe_path = get_health_check_paths(model_group)

    container_args = {
        "name": f"{kubify_name(model_group.name)}",
        "image": model_group.runtime.image,
        "command": get_runtime_command(ctx, model_group, port),
        "volume_mounts": [
            client.V1VolumeMount(
                name="model-data",
                mount_path=MODEL_MOUNT_PATH,
            )
        ],
        "env": [
            client.V1EnvVar(
                name="PORT",
                value=str(port),
            ),
        ],
        "ports": [client.V1ContainerPort(container_port=port)],
        "readiness_probe": client.V1Probe(
            http_get=client.V1HTTPGetAction(
                path=ready_probe_path,
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
                path=live_probe_path,
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
        cpu_request = model_group.resourceRequest.cpu
        memory_request = model_group.resourceRequest.memory
    else:
        instance_info = get_instance_info(
            ctx.provider, ctx.region, model_group.nodeType
        )
        if not instance_info:
            raise ValueError(
                f"No instance information found for instance type {model_group.nodeType} in {ctx.provider} {ctx.region}"
            )
        cpu_milli = cast(int, instance_info["cpu"]) * 1000
        # Leave 400m for other processes
        cpu_request = f"{cpu_milli - 400}m"
        # Leave 2GB for other processes
        memory_request = f"{cast(int, instance_info['memory']) - (2 * 1024)}Mi"

    resources = client.V1ResourceRequirements(
        requests={
            "cpu": cpu_request,
            "memory": memory_request,
        },
    )

    container_args["resources"] = resources

    if hasattr(model_group, "gpu") and model_group.gpu and model_group.gpu.enabled:
        if resources.limits is None:
            resources.limits = {}

        gpu_count = get_gpu_count(ctx=ctx, model_group=model_group)

        # Ah, we only support nvidia GPUs for now
        resources.limits["nvidia.com/gpu"] = str(gpu_count)

    return client.V1PodTemplateSpec(
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
            # Download models from s3 only when s3 is used as a model store
            init_containers=(
                [init_aws(ctx, model_group)]
                if model_group.model and model_group.model.useModelStore
                else []
            ),
            containers=[client.V1Container(**container_args)],  # type: ignore
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
    namespace: str, model_group: T_OnDemandModelGroup, pod: client.V1PodTemplateSpec
) -> client.V1Deployment:
    """
    Creates a Kubernetes Deployment for a machine learning model group.

    Args:
        namespace (str): The namespace to create the Deployment in.
        model_group (T_CloudModelGroup): The model group to run in the Deployment.
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
            name=kubify_name(model_group.name), namespace=namespace
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

    # Both llama-cpp and vllm servers expose metrics on /metrics
    if is_llama_cpp_image(model_group.runtime.image) or is_vllm_image(
        model_group.runtime.image
    ):
        monitor.spec["endpoints"].append(
            {
                "port": "http",
                "path": "/metrics",
                "interval": "15s",
            }
        )
    apply_resource(monitor)


def create_service(
    namespace: str,
    model_group: CloudModelGroup,
    port: int,
    sidecar_port: int = 15090,
) -> client.V1Service:
    """
    Creates a Kubernetes Service for a machine learning model group.

    Args:
        namespace (str): The namespace to create the Service in.
        model_group (T_CloudModelGroup): The model group to expose with the Service.
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


def filter_services(namespace: str) -> List[client.V1Service]:
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
        if service.spec
        and service.spec.selector
        and service.spec.selector.get("app") == "model-group"
        and service.spec.selector.get("model")
    ]

    return filtered_services


def create_hpa(
    namespace: str, model_group: T_OnDemandModelGroup, deployment: client.V1Deployment
) -> client.V2HorizontalPodAutoscaler:
    """
    Creates a Kubernetes Horizontal Pod Autoscaler (HPA) for a machine learning model group.

    This function creates a Kubernetes HPA with the specified namespace, model group, and deployment.
    The HPA automatically scales the number of Pods in the deployment based on the CPU utilization.

    The HPA is configured to maintain a specified number of replicas of the Pod.
    The HPA increases the number of replicas when the average CPU utilization exceeds 95%.

    Args:
        namespace (str): The namespace to create the HPA in.
        model_group (T_CloudModelGroup): The model group to scale with the HPA.
        deployment (client.V1Deployment): The deployment to scale.

    Returns:
        client.V2HorizontalPodAutoscaler: The created HPA.
    """
    assert deployment.metadata and deployment.metadata.name
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
    namespace: str,
    model_group: CloudModelGroup,
    deployment: client.V1Deployment,
    min_replicas: int,
    max_replicas: int,
) -> Optional[CustomResource]:
    """
    Creates a KEDA ScaledObject for a given model group.

    This function creates a ScaledObject custom resource for Kubernetes Event-driven Autoscaling (KEDA).
    The ScaledObject is used to scale a Kubernetes Deployment based on the triggers defined in the model group.

    Args:
        namespace (str): The namespace in which to create the ScaledObject.
        model_group (T_CloudModelGroup): The model group for which to create the ScaledObject.
            This object should have `autoScaleTriggers`, `minInstances`, and `maxInstances` attributes.
        deployment (client.V1Deployment): The Kubernetes Deployment that the ScaledObject should scale.

    Returns:
        None
    """
    if not model_group.autoScaleTriggers:
        return None

    assert deployment.metadata and deployment.metadata.name

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
            "minReplicaCount": min_replicas,
            "maxReplicaCount": max_replicas,
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
    ctx: Context,
    namespace: str,
    model_group: T_OnDemandModelGroup,
) -> None:
    """
    Creates a Kubernetes service for a machine learning model group.

    Args:
        namespace (str): The namespace to create the service in.
        config (Config): The configuration for the service.
        model_group (T_CloudModelGroup): The model group to create the service for.

    Raises:
        ValueError: If the AWS configuration is not provided.

    Returns:
        None
    """
    k8s_config.load_kube_config_from_dict(json.loads(ctx.kubeconfig))

    config = ctx.cloud_config
    # Download the model to S3 first
    if model_group.model and model_group.model.useModelStore:
        if model_group.model.hfRepoId:
            model = HuggingFaceModel(
                name=model_group.name,
                repo_id=model_group.model.hfRepoId,
                files=model_group.model.files,
                model_store=get_model_store(ctx),
            )
            # If the model is not already in the model store, save it
            # That means users cannot update the model in the model store
            # They have to create a new model group or delete the old one
            if not model.model_store.glob(f"{model_group.name}/*"):
                model.save()
            else:
                logger.info(
                    f"Model {model_group.name} already exists in the model store. Skipping download."
                )

    port = 8000

    pod = create_pod(
        ctx,
        namespace,
        model_group,
        port,
    )

    deployment = create_deployment(namespace, model_group, pod)
    apply_resource(deployment)

    svc = create_service(namespace, model_group, port)
    apply_resource(svc)

    if config.prometheus and config.prometheus.enabled:
        create_service_monitor(namespace, model_group)

    scaled_object = create_scaled_object(
        namespace,
        model_group,
        deployment,
        model_group.minInstances,
        model_group.maxInstances,
    )
    if scaled_object:
        apply_resource(scaled_object)

    # Create a vservice to export the model group to the outside world
    if model_group.isPublic:
        create_model_vservice(namespace, model_group.name)


def cleanup_model_group_service_by_name(
    namespace: str,
    model_group_name: str,
) -> None:
    """
    Cleans up a Kubernetes service for a machine learning model group.

    Args:
        namespace (str): The namespace to clean up the service in.
        model_group_name (str): The name of the model group to clean up the service for.

    Returns:
        None
    """

    apps_v1_api = client.AppsV1Api()

    # Delete the deployment
    apps_v1_api.delete_namespaced_deployment(
        name=kubify_name(model_group_name),
        namespace=namespace,
        body=client.V1DeleteOptions(
            propagation_policy="Foreground", grace_period_seconds=30
        ),
    )

    # Delete the service
    core_v1_api = client.CoreV1Api()

    # Delete the service
    core_v1_api.delete_namespaced_service(
        name=kubify_name(model_group_name),
        namespace=namespace,
        body=client.V1DeleteOptions(
            propagation_policy="Foreground", grace_period_seconds=30
        ),
    )

    custom_objects_api = client.CustomObjectsApi()

    # Best effort deletion
    try:
        # Delete the service monitor
        custom_objects_api.delete_namespaced_custom_object(
            group="monitoring.coreos.com",
            version="v1",
            namespace=namespace,
            plural="servicemonitors",
            name=kubify_name(model_group_name),
            body=client.V1DeleteOptions(),
        )
    except:
        pass

    # Delete the scaled object
    try:
        custom_objects_api.delete_namespaced_custom_object(
            group="keda.sh",
            version="v1alpha1",
            namespace=namespace,
            plural="scaledobjects",
            name=kubify_name(model_group_name),
            body=client.V1DeleteOptions(),
        )
    except:
        pass


def cleanup_staled_model_group_services(
    namespace: str, source_of_truth_model_groups: List[str]
) -> None:
    services = filter_services(namespace)
    model_groups = [
        # Get the model group name from the service selector
        service.spec.selector.get("model", "")
        for service in services
        if service.spec and service.spec.selector
    ]

    source_of_truth_model_groups_set = set(source_of_truth_model_groups)

    for model_group in model_groups:
        if model_group not in source_of_truth_model_groups_set:
            cleanup_model_group_service_by_name(namespace, model_group)
