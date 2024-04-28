from __future__ import annotations

import json
import subprocess
import time
from typing import Any, Callable, Tuple, Type

import pulumi_kubernetes as k8s
import pytest
from kubernetes import client
from kubernetes.client.exceptions import ApiException
from ruamel.yaml import YAML

from paka.cluster.namespace import create_namespace
from paka.config import CloudConfig, Config, parse_yaml
from paka.constants import ACCESS_ALL_SA
from paka.k8s.model_group.service import create_model_group_service

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

    create_namespace(k8s_provider, json.dumps(kubeconfig_json))

    create_knative(kind_cluster)

    create_service_account()


@pytest.mark.order(2)
def test_create_model_group() -> None:
    (config, cloud_config) = get_config()
    assert cloud_config.modelGroups is not None
    model_group = cloud_config.modelGroups[0]

    create_model_group_service(cloud_config.cluster.namespace, config, model_group)

    v1 = client.CoreV1Api()

    # Make sure all model group pods are running successfully
    retry_until_successful(
        lambda: v1.list_namespaced_pod(
            namespace=cloud_config.cluster.namespace,
            label_selector="app=model-group,model=gte-base",
        ),
        lambda pods: all(pod.status.phase == "Running" for pod in pods.items),
        max_retries=10,
        interval=5,
        error_message="Model group pod did not start within 50 seconds",
    )
