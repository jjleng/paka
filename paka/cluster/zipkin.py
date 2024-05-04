import pulumi
from pulumi_kubernetes.helm.v3 import Chart, ChartOpts, FetchOpts

from paka.cluster.context import Context
from paka.utils import call_once


@call_once
def create_zipkin(ctx: Context) -> None:
    """
    Installs zipkin with a helm chart.
    """

    config = ctx.cloud_config

    if not config.tracing or not config.tracing.enabled:
        return

    autoscaling = (
        {"autoscaling": {"enabled": True}} if config.tracing.autoScalingEnabled else {}
    )

    Chart(
        "zipkin",
        ChartOpts(
            chart="zipkin",
            version="0.1.2",
            namespace="istio-system",
            fetch_opts=FetchOpts(repo="https://zipkin.io/zipkin-helm"),
            values={
                **autoscaling,
                **(config.tracing.zipkinHelmSettings or {}),
            },
        ),
        opts=pulumi.ResourceOptions(provider=ctx.k8s_provider),
    )
