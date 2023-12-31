import pulumi
from pulumi_kubernetes.helm.v3 import Chart, ChartOpts, FetchOpts
from light.utils import call_once
import pulumi_kubernetes as k8s
import secrets
from light.constants import JOBS_NS


@call_once
def create_redis(k8s_provider: k8s.Provider) -> None:
    """
    Installs redis with a helm chart.
    """
    k8s.core.v1.Namespace(
        "redis",
        metadata={"name": JOBS_NS},
    )

    # Generate a 32-character random password
    password = secrets.token_hex(16)

    Chart(
        "redis",
        ChartOpts(
            chart="redis",
            version="18.6.1",  # Specify the version you want to use
            namespace=JOBS_NS,
            fetch_opts=FetchOpts(repo="https://charts.bitnami.com/bitnami"),
            values={
                "architecture": "standalone",  # Use "replication" for high availability
                "auth": {"enabled": True, "password": password},  # TODO: set password
                # "master": {"persistence": {"enabled": True, "size": "2Gi"}},
                "metrics": {"enabled": True},  # For enabling metrics
            },
        ),
        opts=pulumi.ResourceOptions(provider=k8s_provider),
    )

    # Create a Kubernetes Secret to store the password
    k8s.core.v1.Secret(
        "redis-password",
        metadata={"name": "redis-password", "namespace": JOBS_NS},
        string_data={"password": password},
        opts=pulumi.ResourceOptions(provider=k8s_provider),
    )
