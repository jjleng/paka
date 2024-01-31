import pulumi
import pulumi_kubernetes as k8s
from pulumi_kubernetes.core.v1 import ConfigMap
from pulumi_kubernetes.helm.v3 import Chart, ChartOpts, FetchOpts

from light.config import CloudConfig
from light.utils import call_once


@call_once
def create_prometheus(config: CloudConfig, k8s_provider: k8s.Provider) -> None:
    """
    Installs a Prometheus chart.
    """
    if not config.prometheus:
        return

    k8s.core.v1.Namespace(
        "prometheus",
        metadata={"name": "prometheus"},
        opts=pulumi.ResourceOptions(provider=k8s_provider),
    )

    ConfigMap(
        "prometheus-config",
        metadata={"namespace": "prometheus"},
        # fmt: off
        data={"prometheus.yml": """
            global:
              scrape_interval: 15s
              evaluation_interval: 15s
            rule_files:
              - /etc/prometheus/rules
              - /etc/prometheus/rules/*
            """},
        # fmt: on
        opts=pulumi.ResourceOptions(provider=k8s_provider),
    )

    Chart(
        "prometheus",
        ChartOpts(
            chart="prometheus",
            version="25.11.0",
            namespace="prometheus",
            fetch_opts=FetchOpts(
                repo="https://prometheus-community.github.io/helm-charts"
            ),
            values={
                "server": {
                    "persistentVolume": {
                        "enabled": True,
                        "size": config.prometheus.storage_size,
                    },
                },
                "serverFiles": {},
                "extraConfigmapMounts": [
                    {
                        "name": "prometheus-config",
                        "mountPath": "/etc/prometheus",
                        "configMap": "prometheus-config",
                        "subPath": "prometheus.yml",
                        "readOnly": True,
                    }
                ],
            },
        ),
        opts=pulumi.ResourceOptions(provider=k8s_provider),
    )
