import pulumi
import pulumi_kubernetes as k8s
from pulumi_kubernetes.core.v1 import ConfigMap
from pulumi_kubernetes.yaml import ConfigFile

from light.utils import call_once

VERSION = "v1.12.3"


@call_once
def create_knative(k8s_provider: k8s.Provider) -> None:
    yaml_files = [
        # TODO: sigstore verification
        # Creates resources under the knative-serving namespace
        f"https://github.com/knative/serving/releases/download/knative-{VERSION}/serving-core.yaml",
        # Use kourier as the networking layer
        f"https://github.com/knative/net-kourier/releases/download/knative-{VERSION}/kourier.yaml",
    ]
    for i, yaml_file in enumerate(yaml_files):
        ConfigFile(
            yaml_file.split("/")[-1],
            file=yaml_file,
            opts=pulumi.ResourceOptions(provider=k8s_provider),
        )

    # Desired configuration
    config_data = {"ingress-class": "kourier.ingress.networking.knative.dev"}

    # Define the ConfigMap resource
    ConfigMap(
        "config-network",
        api_version="v1",
        kind="ConfigMap",
        metadata={"namespace": "knative-serving", "name": "config-network"},
        data=config_data,
        opts=pulumi.ResourceOptions(provider=k8s_provider),
    )
