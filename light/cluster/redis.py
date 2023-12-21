import pulumi
from pulumi_kubernetes.helm.v3 import Chart, ChartOpts, FetchOpts
from light.utils import call_once
import pulumi_kubernetes as k8s


@call_once
def create_redis(k8s_provider: k8s.Provider) -> None:
    """
    Installs redis with a helm chart.
    """
    k8s.core.v1.Namespace(
        "redis",
        metadata={"name": "redis"},
    )
    Chart(
        "redis",
        ChartOpts(
            chart="redis",
            version="18.6.1",  # Specify the version you want to use
            namespace="redis",
            fetch_opts=FetchOpts(repo="https://charts.bitnami.com/bitnami"),
            values={
                "architecture": "standalone",  # Use "replication" for high availability
                "auth": {"enabled": False},
                # "master": {"persistence": {"enabled": True, "size": "2Gi"}},
                "metrics": {"enabled": True},  # For enabling metrics
            },
        ),
        opts=pulumi.ResourceOptions(provider=k8s_provider),
    )
