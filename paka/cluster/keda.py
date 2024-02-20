import pulumi
import pulumi_kubernetes as k8s
from pulumi_kubernetes.helm.v3 import Chart, ChartOpts, FetchOpts

from paka.cluster.prometheus import create_prometheus
from paka.config import CloudConfig
from paka.utils import call_once


@call_once
def create_keda(config: CloudConfig, k8s_provider: k8s.Provider) -> None:
    """
    Installs a KEDA chart.
    """
    prometheus = create_prometheus(config, k8s_provider)

    # Prometheus is a dependency for KEDA to work with the Prometheus metrics.
    # However, Prometheus might not be enabled in the config. In that case,
    # deletion of the KEDA resource will be blocked if Prometheus trigger is used.
    dependencies = [prometheus] if prometheus else []

    ns = k8s.core.v1.Namespace(
        "keda",
        metadata={"name": "keda"},
        opts=pulumi.ResourceOptions(provider=k8s_provider),
    )
    Chart(
        "keda",
        ChartOpts(
            chart="keda",
            version="2.12.1",
            namespace="keda",
            fetch_opts=FetchOpts(repo="https://kedacore.github.io/charts"),
            values={},
        ),
        opts=pulumi.ResourceOptions(
            provider=k8s_provider, depends_on=[ns, *dependencies]
        ),
    )
