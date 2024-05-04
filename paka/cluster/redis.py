import pulumi
import pulumi_kubernetes as k8s
from pulumi_kubernetes.apiextensions import CustomResource
from pulumi_kubernetes.helm.v3 import Chart, ChartOpts, FetchOpts

from paka.cluster.context import Context
from paka.utils import call_once


@call_once
def create_redis(ctx: Context) -> None:
    """
    Installs redis with a helm chart.
    """
    config = ctx.cloud_config

    if not config.job or not config.job.enabled:
        return

    ns = k8s.core.v1.Namespace(
        "redis",
        metadata={"name": "redis"},
        opts=pulumi.ResourceOptions(provider=ctx.k8s_provider),
    )

    chart = Chart(
        "redis",
        ChartOpts(
            chart="redis",
            version="18.6.1",
            namespace=ctx.namespace,
            fetch_opts=FetchOpts(repo="https://charts.bitnami.com/bitnami"),
            values={
                "architecture": "standalone",
                "master": {
                    "persistence": {
                        "enabled": True,
                        "size": config.job.broker_storage_size,
                    },
                },
                "metrics": {"enabled": True},  # For enabling metrics
            },
        ),
        opts=pulumi.ResourceOptions(provider=ctx.k8s_provider, depends_on=[ns]),
    )

    if not config.prometheus or not config.prometheus.enabled:
        return

    CustomResource(
        "redis-metrics-monitor",
        api_version="monitoring.coreos.com/v1",
        kind="ServiceMonitor",
        metadata={
            "name": "redis-metrics-monitor",
            "namespace": "redis",
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
                "matchNames": ["redis"],
            },
            "endpoints": [
                {
                    "port": "http-metrics",
                    "interval": "15s",
                },
            ],
        },
        opts=pulumi.ResourceOptions(
            provider=ctx.k8s_provider,
            depends_on=[chart],
        ),
    )
