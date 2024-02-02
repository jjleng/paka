import secrets

import pulumi
import pulumi_kubernetes as k8s
from pulumi_kubernetes.apiextensions import CustomResource
from pulumi_kubernetes.helm.v3 import Chart, ChartOpts, FetchOpts

from light.config import CloudConfig
from light.utils import call_once, read_current_cluster_data


@call_once
def create_redis(config: CloudConfig, k8s_provider: k8s.Provider) -> None:
    """
    Installs redis with a helm chart.
    """

    # Generate a 32-character random password
    password = secrets.token_hex(16)

    chart = Chart(
        "redis",
        ChartOpts(
            chart="redis",
            version="18.6.1",  # Specify the version you want to use
            namespace=read_current_cluster_data("namespace"),
            fetch_opts=FetchOpts(repo="https://charts.bitnami.com/bitnami"),
            values={
                "architecture": "standalone",  # Use "replication" for high availability
                "auth": {"enabled": True, "password": password},
                "master": {
                    "persistence": {"enabled": True, "size": "10Gi"},
                    "podAnnotations": {"sidecar.istio.io/inject": "false"},
                },
                "metrics": {"enabled": True},  # For enabling metrics
            },
        ),
        opts=pulumi.ResourceOptions(provider=k8s_provider),
    )

    # Create a Kubernetes Secret to store the password
    k8s.core.v1.Secret(
        "redis-password",
        metadata={
            "name": "redis-password",
            "namespace": read_current_cluster_data("namespace"),
        },
        string_data={"password": password},
        opts=pulumi.ResourceOptions(provider=k8s_provider),
    )

    if not config.prometheus:
        return

    CustomResource(
        "redis-metrics-monitor",
        api_version="monitoring.coreos.com/v1",
        kind="ServiceMonitor",
        metadata={
            "name": "redis-metrics-monitor",
            "namespace": read_current_cluster_data("namespace"),
        },
        spec={
            "selector": {
                "matchLabels": {
                    "app.kubernetes.io/instance": "redis",
                    "app.kubernetes.io/name": "redis",
                    "app.kubernetes.io/component": "metrics",
                }
            },
            "namespaceSelector": {
                "matchNames": [read_current_cluster_data("namespace")],
            },
            "endpoints": [
                {
                    "port": "http-metrics",
                    "interval": "15s",
                },
            ],
        },
        opts=pulumi.ResourceOptions(
            provider=k8s_provider,
            depends_on=[chart],
        ),
    )
