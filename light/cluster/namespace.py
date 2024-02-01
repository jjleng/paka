import pulumi
import pulumi_kubernetes as k8s
from kubernetes import client

from light.k8s import try_load_kubeconfig
from light.utils import read_current_cluster_data

APP_NS = read_current_cluster_data("namespace")

try_load_kubeconfig()


def create_namespace(k8s_provider: k8s.Provider) -> None:
    if APP_NS != "default":
        k8s.core.v1.Namespace(
            "app-ns",
            metadata={"name": APP_NS, "labels": {"istio-injection": "enabled"}},
            opts=pulumi.ResourceOptions(provider=k8s_provider),
        )
    else:
        # We are dealing with the default namespace
        api_instance = client.CoreV1Api()

        body = {"metadata": {"labels": {"istio-injection": "enabled"}}}

        api_instance.patch_namespace("default", body)
