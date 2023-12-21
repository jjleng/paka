from pulumi_kubernetes.helm.v3 import Chart, ChartOpts, FetchOpts
from light.utils import call_once


@call_once
def create_redis() -> None:
    """
    Creates a Redis chart.
    """
    Chart(
        "redis",
        ChartOpts(
            chart="redis",
            version="18.6.1",  # Specify the version you want to use
            fetch_opts=FetchOpts(repo="https://charts.bitnami.com/bitnami"),
            values={
                "architecture": "standalone",  # Use "replication" for high availability
                "auth": {"enabled": False},
                # "master": {"persistence": {"enabled": True, "size": "2Gi"}},
                "metrics": {"enabled": True},  # For enabling metrics
            },
        ),
    )
