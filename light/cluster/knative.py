from functools import partial
from typing import Any, Callable

import pulumi
import pulumi_kubernetes as k8s
from pulumi import ResourceOptions
from pulumi_kubernetes.yaml import ConfigFile

from light.utils import call_once

VERSION = "v1.12.3"
ISTIO_VERSION = "v1.12.1"


def limit_hpa_min_replicas(args: Any, opts: pulumi.ResourceOptions) -> None:
    if (
        args["kind"] == "HorizontalPodAutoscaler"
        and args["metadata"]["name"] == "istiod"
    ):
        args["spec"]["minReplicas"] = 1


def limit_resources(args: Any, opts: pulumi.ResourceOptions) -> None:
    if args["kind"] == "Deployment" and args["metadata"]["name"] == "istiod":
        for container in args["spec"]["template"]["spec"]["containers"]:
            if container["name"] == "discovery":
                container["resources"] = {
                    "requests": {"cpu": "300m", "memory": "1Gi"},
                }


def crd_resources(labels: dict) -> bool:
    return labels.get("knative.dev/crd-install") == "true"


def non_crd_resources(labels: dict) -> bool:
    return labels.get("knative.dev/crd-install") != "true"


def crd_install_filter(
    inputs: Any, opts: ResourceOptions, filter: Callable[[Any], bool]
) -> None:
    if "metadata" in inputs:
        if not filter(inputs["metadata"].get("labels", {})):
            inputs["kind"] = "List"
            inputs["items"] = []


only_crd_transform = partial(crd_install_filter, filter=crd_resources)
non_crd_transform = partial(crd_install_filter, filter=non_crd_resources)


@call_once
def create_knative(k8s_provider: k8s.Provider) -> None:
    yaml_files = [
        # TODO: sigstore verification
        # Creates resources under the knative-serving namespace
        f"https://github.com/knative/serving/releases/download/knative-{VERSION}/serving-core.yaml",
    ]
    for i, yaml_file in enumerate(yaml_files):
        ConfigFile(
            yaml_file.split("/")[-1],
            file=yaml_file,
            opts=pulumi.ResourceOptions(provider=k8s_provider),
        )

    yaml_file = f"https://github.com/knative/net-istio/releases/download/knative-{ISTIO_VERSION}/istio.yaml"
    istio_crd_install = ConfigFile(
        "istio-crd-install",
        file=yaml_file,
        transformations=[only_crd_transform],
        opts=pulumi.ResourceOptions(provider=k8s_provider),
    )

    istio_full_install = ConfigFile(
        "istio-non-crd-install",
        file=yaml_file,
        transformations=[non_crd_transform, limit_resources, limit_hpa_min_replicas],
        opts=pulumi.ResourceOptions(
            provider=k8s_provider, depends_on=[istio_crd_install]
        ),
    )

    yaml_file = f"https://github.com/knative/net-istio/releases/download/knative-{ISTIO_VERSION}/net-istio.yaml"
    net_istio = ConfigFile(
        "net-istio",
        file=yaml_file,
        opts=pulumi.ResourceOptions(
            provider=k8s_provider, depends_on=[istio_full_install]
        ),
    )

    yaml_file = f"https://github.com/knative/serving/releases/download/knative-{VERSION}/serving-default-domain.yaml"
    ConfigFile(
        "kn-default-domain",
        file=yaml_file,
        opts=pulumi.ResourceOptions(provider=k8s_provider, depends_on=[net_istio]),
    )
