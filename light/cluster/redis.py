import pulumi
from pulumi_kubernetes.helm.v3 import Chart, ChartOpts, FetchOpts
from light.utils import call_once
import pulumi_kubernetes as k8s
import secrets


@call_once
def create_redis(k8s_provider: k8s.Provider) -> None:
    """
    Installs redis with a helm chart.
    """
    k8s.core.v1.Namespace(
        "redis",
        metadata={"name": "redis"},
    )

    # Generate a 32-character random password
    password = secrets.token_hex(16)

    Chart(
        "redis",
        ChartOpts(
            chart="redis",
            version="18.6.1",  # Specify the version you want to use
            namespace="redis",
            fetch_opts=FetchOpts(repo="https://charts.bitnami.com/bitnami"),
            values={
                "architecture": "standalone",  # Use "replication" for high availability
                "auth": {"enabled": True, "password": password},
                # "master": {"persistence": {"enabled": True, "size": "2Gi"}},
                "metrics": {"enabled": True},  # For enabling metrics
            },
        ),
        opts=pulumi.ResourceOptions(provider=k8s_provider),
    )

    # Create a Kubernetes Secret to store the password
    secret = k8s.core.v1.Secret(
        "redis-password",
        metadata={"name": "redis-password", "namespace": "redis"},
        string_data={"password": password},
        opts=pulumi.ResourceOptions(provider=k8s_provider),
    )

    # Create a Kubernetes Role that allows reading the secret
    k8s.rbac.v1.Role(
        "redis-secret-reader",
        metadata={"namespace": "redis"},
        rules=[
            {
                "apiGroups": [""],
                "resources": ["secrets"],
                "verbs": ["get", "watch", "list"],
                "resourceNames": [secret.metadata["name"]],
            }
        ],
        opts=pulumi.ResourceOptions(provider=k8s_provider),
    )
