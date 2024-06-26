from __future__ import annotations

import json
import subprocess
import time
from typing import Any, Callable, Tuple, Type

import pulumi_kubernetes as k8s
import pytest
from kubernetes import client
from kubernetes import config as k8s_config
from kubernetes.client.exceptions import ApiException
from ruamel.yaml import YAML

from paka.cluster.context import Context
from paka.cluster.namespace import create_namespace
from paka.config import CloudConfig, Config, parse_yaml
from paka.constants import ACCESS_ALL_SA
from paka.k8s.function.service import (
    create_knative_service,
    list_knative_revisions,
    list_knative_services,
)
from paka.k8s.model_group.service import (
    cleanup_staled_model_group_services,
    create_model_group_service,
)
from paka.utils import kubify_name

from .pytest_kind.cluster import KindCluster


def retry_until_successful(
    func: Callable[..., Any],
    success_condition: Callable[[Any], bool],
    max_retries: int,
    interval: int,
    error_message: str,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """
    Retries a function until it returns a successful result or a maximum number of retries is reached.

    Args:
        func (callable): The function to retry.
        success_condition (callable): A function that takes the result of the function and returns True if the result is successful.
        max_retries (int): The maximum number of times to retry the function.
        interval (int): The time between retries (in seconds).
        error_message (str): The error message to raise if the function does not return a successful result within the maximum number of retries.
        *args: The positional arguments to pass to the function.
        **kwargs: The keyword arguments to pass to the function.

    Returns:
        The result of the function.

    Raises:
        Exception: If the function does not return a successful result within the maximum number of retries.
    """
    for i in range(max_retries):
        result = func(*args, **kwargs)
        if success_condition(result):
            return result
        time.sleep(interval)
    raise Exception(error_message)


def retry_on_exceptions(
    func: Callable[..., Any],
    exceptions: tuple[Type[BaseException]],
    max_retries: int,
    interval: int,
    error_message: str,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """
    Retries a function when it raises a specific exception.

    Args:
        func (callable): The function to retry.
        exceptions (tuple): The exceptions to catch.
        max_retries (int): The maximum number of times to retry the function.
        interval (int): The time between retries (in seconds).
        error_message (str): The error message to raise if the function does not return a successful result within the maximum number of retries.
        *args: The positional arguments to pass to the function.
        **kwargs: The keyword arguments to pass to the function.

    Returns:
        The result of the function.

    Raises:
        Exception: If the function does not return a successful result within the maximum number of retries.
    """
    for i in range(max_retries):
        try:
            return func(*args, **kwargs)
        except exceptions:
            if i < max_retries - 1:
                time.sleep(interval)
            else:
                raise Exception(error_message)


def get_config() -> Tuple[Config, CloudConfig]:
    cluster_config = """
version: "1.0"
aws:
  cluster:
    name: test_cluster
    region: us-west-2
    nodeType: t2.medium
    minNodes: 2
    maxNodes: 4
  modelGroups:
    - nodeType: c7a.xlarge
      minInstances: 1
      maxInstances: 1
      name: gte-base
      resourceRequest:
        cpu: 1000m
        memory: 1Gi
      runtime:
        image: 'ghcr.io/ggerganov/llama.cpp:server'
      model:
        hfRepoId: jjleng/gte-base-gguf
        files:
          - 'gte-base.q4_0.gguf'
        useModelStore: false
"""

    config = parse_yaml(cluster_config)
    assert isinstance(config, Config)
    assert config.aws is not None

    return (config, config.aws)


def create_knative(kind_cluster: KindCluster) -> None:
    kind_cluster.kubectl(
        "apply",
        "-f",
        "https://github.com/knative/serving/releases/download/knative-v1.13.1/serving-crds.yaml",
    )

    kind_cluster.kubectl(
        "apply",
        "-f",
        "https://github.com/knative/serving/releases/download/knative-v1.13.1/serving-core.yaml",
    )

    kind_cluster.kubectl(
        "apply",
        "-l",
        "knative.dev/crd-install=true",
        "-f",
        "https://github.com/knative/net-istio/releases/download/knative-v1.13.1/istio.yaml",
    )

    kind_cluster.kubectl(
        "apply",
        "-f",
        "https://github.com/knative/net-istio/releases/download/knative-v1.13.1/istio.yaml",
    )

    retry_on_exceptions(
        lambda: kind_cluster.kubectl(
            "apply",
            "-f",
            "https://github.com/knative/net-istio/releases/download/knative-v1.13.1/net-istio.yaml",
        ),
        (subprocess.CalledProcessError,),
        max_retries=10,
        interval=5,
        error_message="Failed to apply net-istio.yaml",
    )


def create_service_account() -> None:
    # Create a service account for paka
    (_, config) = get_config()

    v1 = client.CoreV1Api()

    service_account = client.V1ServiceAccount(
        metadata=client.V1ObjectMeta(
            namespace=config.cluster.namespace,
            name=ACCESS_ALL_SA,
        )
    )

    assert (
        service_account.metadata
        and service_account.metadata.name
        and service_account.metadata.namespace
    )

    try:
        v1.read_namespaced_service_account(
            name=service_account.metadata.name,
            namespace=service_account.metadata.namespace,
        )
    except ApiException as e:
        if e.status == 404:
            v1.create_namespaced_service_account(
                namespace=service_account.metadata.namespace, body=service_account
            )
        else:
            raise


@pytest.mark.order(1)
def test_setup_cluster(kind_cluster: KindCluster) -> None:
    kubeconfig_path = str(kind_cluster.kubeconfig_path)
    k8s_provider = k8s.Provider("k8s-provider", kubeconfig=kubeconfig_path)

    yaml = YAML(typ="safe")
    with open(kubeconfig_path, "r") as f:
        kubeconfig_json = yaml.load(f)

    (config, _) = get_config()

    ctx = Context()
    ctx.set_k8s_provider(k8s_provider)
    ctx.set_config(config)

    create_namespace(ctx, json.dumps(kubeconfig_json))

    create_knative(kind_cluster)

    create_service_account()


@pytest.mark.order(2)
def test_create_model_group(kind_cluster: KindCluster) -> None:
    kubeconfig_path = str(kind_cluster.kubeconfig_path)
    yaml = YAML(typ="safe")
    with open(kubeconfig_path, "r") as f:
        kubeconfig_json = yaml.load(f)

    (config, cloud_config) = get_config()
    assert cloud_config.modelGroups is not None
    model_group = cloud_config.modelGroups[0]

    ctx = Context()
    ctx.set_config(config)
    ctx.set_kubeconfig(json.dumps(kubeconfig_json))

    create_model_group_service(ctx, ctx.namespace, model_group)

    core_v1_api = client.CoreV1Api()

    # Make sure all model group pods are running successfully
    retry_until_successful(
        lambda: core_v1_api.list_namespaced_pod(
            namespace=cloud_config.cluster.namespace,
            label_selector="app=model-group,model=gte-base",
        ),
        lambda pods: all(pod.status.phase == "Running" for pod in pods.items),
        max_retries=10,
        interval=5,
        error_message="Model group pod did not start within 50 seconds",
    )

    # Verify that the model group resources are created
    apps_v1_api = client.AppsV1Api()
    try:
        apps_v1_api.read_namespaced_deployment(
            name=kubify_name("gte-base"), namespace=cloud_config.cluster.namespace
        )
    except ApiException as e:
        if e.status == 404:
            assert False, "Failed to create model group deployment"
        else:
            raise

    core_v1_api = client.CoreV1Api()
    try:
        core_v1_api.read_namespaced_service(
            name=kubify_name("gte-base"), namespace=cloud_config.cluster.namespace
        )
    except ApiException as e:
        if e.status == 404:
            assert False, "Failed to create model group service"
        else:
            raise


@pytest.mark.order(3)
def test_create_functions(kind_cluster: KindCluster) -> None:
    kubeconfig_path = str(kind_cluster.kubeconfig_path)
    yaml = YAML(typ="safe")
    with open(kubeconfig_path, "r") as f:
        kubeconfig_json = yaml.load(f)
        k8s_config.load_kube_config_from_dict(kubeconfig_json)

    (config, cloud_config) = get_config()

    create_knative_service(
        service_name="echo-server",
        namespace=cloud_config.cluster.namespace,
        image="jmalloc/echo-server:0.3.5",
        entrypoint="/bin/echo-server",
        min_instances=0,
        max_instances=1,
        scaling_metric=("concurrency", "10"),  # type: ignore
    )

    retry_until_successful(
        lambda: list_knative_services(
            namespace=cloud_config.cluster.namespace,
        ),
        lambda services: len(services.items) == 1,
        max_retries=10,
        interval=5,
        error_message="Functions are not ready within 50 seconds",
    )

    # Update the function
    create_knative_service(
        service_name="echo-server",
        namespace=cloud_config.cluster.namespace,
        image="jmalloc/echo-server:0.3.6",
        entrypoint="/bin/echo-server",
        min_instances=0,
        max_instances=1,
        scaling_metric=("concurrency", "10"),  # type: ignore
    )

    retry_until_successful(
        lambda: list_knative_revisions(
            namespace=cloud_config.cluster.namespace,
            service_name="echo-server",
        ),
        lambda revisions: len(revisions) == 2,
        max_retries=10,
        interval=5,
        error_message="Functions are not ready within 50 seconds",
    )


@pytest.mark.order(4)
def test_destroy_model_group() -> None:
    (config, cloud_config) = get_config()
    cloud_config.modelGroups = []

    ctx = Context()
    ctx.set_config(config)

    cleanup_staled_model_group_services(
        cloud_config.cluster.namespace,
        [mg.name for mg in cloud_config.modelGroups or []],
    )

    for model_group in cloud_config.modelGroups:
        create_model_group_service(ctx, ctx.namespace, model_group)

    # Verify that the model group resources are deleted
    apps_v1_api = client.AppsV1Api()
    try:
        retry_until_successful(
            lambda: apps_v1_api.read_namespaced_deployment(
                name=kubify_name("gte-base"), namespace=cloud_config.cluster.namespace
            ),
            lambda _: False,
            max_retries=12,
            interval=5,
            error_message="Model group deployment was not deleted",
        )
    except ApiException as e:
        if e.status != 404:
            raise

    core_v1_api = client.CoreV1Api()
    try:
        retry_until_successful(
            lambda: core_v1_api.read_namespaced_service(
                name=kubify_name("gte-base"), namespace=cloud_config.cluster.namespace
            ),
            lambda _: False,
            max_retries=12,
            interval=5,
            error_message="Model group service was not deleted",
        )
    except ApiException as e:
        if e.status != 404:
            raise
