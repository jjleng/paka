import json

import pulumi
import pulumi_kubernetes as k8s
from kubernetes import client, config

from cusco.utils import read_current_cluster_data


def create_namespace(k8s_provider: k8s.Provider, kubeconfig_json: str) -> None:
    if read_current_cluster_data("namespace") != "default":
        k8s.core.v1.Namespace(
            "app-ns",
            metadata={
                "name": read_current_cluster_data("namespace"),
                "labels": {"istio-injection": "enabled"},
            },
            opts=pulumi.ResourceOptions(provider=k8s_provider),
        )
    else:
        config.load_kube_config_from_dict(json.loads(kubeconfig_json))
        # We are dealing with the default namespace
        api_instance = client.CoreV1Api()

        body = {"metadata": {"labels": {"istio-injection": "enabled"}}}

        api_instance.patch_namespace("default", body)
