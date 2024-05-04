import json

import pulumi
import pulumi_kubernetes as k8s
from kubernetes import client, config

from paka.cluster.context import Context


def create_namespace(ctx: Context, kubeconfig_json: str) -> None:
    # Pulumi does not support creating the default namespace again, so we need to handle it separately
    if ctx.namespace != "default":
        k8s.core.v1.Namespace(
            "app-ns",
            metadata={
                "name": ctx.namespace,
                "labels": {"istio-injection": "enabled"},
            },
            opts=pulumi.ResourceOptions(provider=ctx.k8s_provider),
        )
    else:
        config.load_kube_config_from_dict(json.loads(kubeconfig_json))
        # We are dealing with the default namespace
        api_instance = client.CoreV1Api()

        body = {"metadata": {"labels": {"istio-injection": "enabled"}}}

        api_instance.patch_namespace("default", body)
