import pulumi
import pulumi_kubernetes as k8s
from pulumi_kubernetes.helm.v3 import Chart, ChartOpts, FetchOpts

from paka.config import CloudConfig
from paka.utils import call_once


@call_once
def create_zipkin(config: CloudConfig, k8s_provider: k8s.Provider) -> None:
    """
    Installs zipkin with a helm chart.
    """

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
        opts=pulumi.ResourceOptions(provider=k8s_provider),
    )
