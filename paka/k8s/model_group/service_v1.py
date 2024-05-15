"""
v1 supports mixed on-demand and spot instances. Some key design decisions:
a) Fail safe on-demand pods and instances. A safe number of on-demand instances are always maintained.
b) Use spot instances for cost savings. Spot instances are preferred over on-demand instances. If the spot instance
   pool is exhausted, on-demand instances are used.
c) Once the spot instance pool has capacity, the on-demand pods (except the fail safe pods) are rescheduled to spot instances.
"""

from __future__ import annotations

import json

from kubernetes import client
from kubernetes import config as k8s_config
from kubernetes.client.exceptions import ApiException

from paka.cluster.context import Context
from paka.cluster.utils import get_model_store
from paka.config import T_MixedModelGroup
from paka.k8s.model_group.ingress import create_model_vservice
from paka.k8s.model_group.service import (
    create_pod,
    create_scaled_object,
    create_service,
    create_service_monitor,
)
from paka.k8s.utils import apply_resource
from paka.logger import logger
from paka.model.hf_model import HuggingFaceModel
from paka.utils import kubify_name


def ensure_priority_class(name: str, priority: int) -> None:
    """
    Ensure that the priority class exists in the cluster.
    """
    name = kubify_name(name)
    api_instance = client.SchedulingV1Api()

    priority_class = client.V1PriorityClass(
        api_version="scheduling.k8s.io/v1",
        kind="PriorityClass",
        metadata=client.V1ObjectMeta(name=name),
        value=priority,
    )
    try:
        api_instance.read_priority_class(name)
        api_instance.replace_priority_class(name, body=priority_class)

    except ApiException as e:
        if e.status == 404:
            api_instance.create_priority_class(body=priority_class)
        else:
            raise e


def ensure_pdb(namespace: str, model_group: T_MixedModelGroup) -> None:
    """
    Ensure that the PodDisruptionBudget exists for the model group.
    """
    pdb = client.V1PodDisruptionBudget(
        kind="PodDisruptionBudget",
        metadata=client.V1ObjectMeta(
            name=f"{kubify_name(model_group.name)}",
            namespace=namespace,
        ),
        spec=client.V1PodDisruptionBudgetSpec(
            # Will slow down the speed of scaling down pods. But spot instances are usually terminated with 2 minutes.
            max_unavailable="30%",
            selector=client.V1LabelSelector(
                match_labels={
                    "app": "model-group",
                    "model": model_group.name,
                }
            ),
        ),
    )

    policy_v1 = client.PolicyV1Api()

    assert pdb.metadata and pdb.metadata.name and pdb.metadata.namespace

    try:
        existing_pdb = policy_v1.read_namespaced_pod_disruption_budget(
            name=pdb.metadata.name, namespace=pdb.metadata.namespace
        )
        assert existing_pdb.metadata
        pdb.metadata.resource_version = existing_pdb.metadata.resource_version
        policy_v1.replace_namespaced_pod_disruption_budget(
            name=pdb.metadata.name, namespace=pdb.metadata.namespace, body=pdb
        )
    except ApiException as e:
        if e.status == 404:
            policy_v1.create_namespaced_pod_disruption_budget(
                namespace=pdb.metadata.namespace, body=pdb
            )
        else:
            raise


def create_fail_safe_deployment(
    namespace: str, model_group: T_MixedModelGroup, pod: client.V1PodTemplateSpec
) -> client.V1Deployment:

    # Lack of optional chaining support in Python makes this code a bit verbose.
    assert (
        pod.spec
        and pod.spec.affinity
        and pod.spec.affinity.node_affinity
        and pod.spec.affinity.node_affinity.required_during_scheduling_ignored_during_execution
    )

    # We need to change the pod's affinity to ensure that it is scheduled on an on-demand instance.
    pod.spec.affinity.node_affinity.required_during_scheduling_ignored_during_execution.node_selector_terms.append(
        client.V1NodeSelectorTerm(
            match_expressions=[
                client.V1NodeSelectorRequirement(
                    key="lifecycle",
                    operator="In",
                    values=["on-demand"],
                )
            ]
        )
    )

    # We would also like to ensure that the pod is scheduled on a node with a higher priority.
    # This would reduce the chances of the pod being preempted by keda or HPA.
    # CA will also try to fullfil the pods with higher priority first.
    priority_class = "fail-safe"
    ensure_priority_class(priority_class, 100000)
    pod.spec.priority_class_name = priority_class

    return client.V1Deployment(
        api_version="apps/v1",
        kind="Deployment",
        metadata=client.V1ObjectMeta(
            name=f"{kubify_name(model_group.name)}-baseline",
            namespace=namespace,
        ),
        spec=client.V1DeploymentSpec(
            replicas=model_group.baseInstances,
            selector=client.V1LabelSelector(
                match_labels={
                    "app": "model-group",
                    "model": model_group.name,
                }
            ),
            template=pod,
        ),
    )


def create_auto_scale_deployment(
    namespace: str, model_group: T_MixedModelGroup, pod: client.V1PodTemplateSpec
) -> client.V1Deployment:

    ensure_pdb(namespace, model_group)

    # We want to change the pod's affinity to ensure that it prefers to be scheduled on a spot instances.
    # With this change, the pod will be scheduled on a spot instance if available.
    # However, if no instances are available, CA doesn't respect below preferred affinity as it is not a required affinity.
    # In such cases, CA relies on the priority expander to scale out more instances. We have given a higher priority to spot instances.
    assert pod.spec and pod.spec.affinity and pod.spec.affinity.node_affinity
    pod.spec.affinity.node_affinity.preferred_during_scheduling_ignored_during_execution = [
        client.V1PreferredSchedulingTerm(
            preference=client.V1NodeSelectorTerm(
                match_expressions=[
                    client.V1NodeSelectorRequirement(
                        key="lifecycle",
                        operator="In",
                        values=["spot"],
                    )
                ]
            ),
            weight=100,
        )
    ]

    return client.V1Deployment(
        api_version="apps/v1",
        kind="Deployment",
        metadata=client.V1ObjectMeta(
            name=f"{kubify_name(model_group.name)}",
            namespace=namespace,
        ),
        spec=client.V1DeploymentSpec(
            replicas=model_group.spot.minInstances,  # Scaler will update this
            selector=client.V1LabelSelector(
                match_labels={
                    "app": "model-group",
                    "model": model_group.name,
                }
            ),
            template=pod,
        ),
    )


def create_model_group_service(
    ctx: Context,
    namespace: str,
    model_group: T_MixedModelGroup,
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

    fail_safe_deployment = create_fail_safe_deployment(namespace, model_group, pod)
    apply_resource(fail_safe_deployment)

    auto_scale_deployment = create_auto_scale_deployment(namespace, model_group, pod)
    apply_resource(auto_scale_deployment)

    # Service will direct traffic to pods managed by both deployments
    svc = create_service(namespace, model_group, port)
    apply_resource(svc)

    # Prometheus will monitor pods managed by both deployments
    if config.prometheus and config.prometheus.enabled:
        create_service_monitor(namespace, model_group)

    # Horizontal pod autoscaler will only scale the auto_scale_deployment, fail_safe_deployment is not scaled
    scaled_object = create_scaled_object(
        namespace,
        model_group,
        auto_scale_deployment,
        model_group.spot.minInstances,
        # Might result in many pending pods if spot.maxInstances > maxOnDemandInstances when spot pool is not available
        max(
            model_group.maxOnDemandInstances,
            model_group.spot.maxInstances,
        ),
    )
    if scaled_object:
        apply_resource(scaled_object)

    # Create a vservice to export the model group to the outside world
    if model_group.isPublic:
        create_model_vservice(namespace, model_group.name)
