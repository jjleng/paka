import pulumi
import pulumi_kubernetes as k8s
from pulumi_kubernetes.helm.v3 import Chart, ChartOpts, FetchOpts

from paca.config import CloudConfig
from paca.utils import call_once


@call_once
def create_qdrant(
    config: CloudConfig,
    k8s_provider: k8s.Provider,
) -> None:
    """
    Installs the qdrant helm chart.
    """
    if not config.vectorStore:
        return

    k8s.core.v1.Namespace(
        "qdrant",
        metadata={"name": "qdrant", "labels": {"istio-injection": "enabled"}},
        opts=pulumi.ResourceOptions(provider=k8s_provider),
    )

    resource_request = (
        {
            "resources": {
                "requests": {
                    "cpu": config.vectorStore.resourceRequest.cpu,
                    "memory": config.vectorStore.resourceRequest.memory,
                },
            }
        }
        if config.vectorStore.resourceRequest
        else {}
    )

    Chart(
        "qdrant",
        ChartOpts(
            chart="qdrant",
            version="0.7.5",
            namespace="qdrant",
            fetch_opts=FetchOpts(repo="https://qdrant.github.io/qdrant-helm"),
            values={
                "metrics": {
                    "serviceMonitor": {
                        "enabled": (
                            True
                            if config.prometheus and config.prometheus.enabled
                            else False
                        ),
                    },
                },
                "replicaCount": config.vectorStore.replicas,
                "persistence": {
                    "size": config.vectorStore.storage_size,
                },
                "livenessProbe": {
                    "enabled": True,
                },
                "tolerations": [
                    {
                        "key": "app",
                        "operator": "Equal",
                        "value": "qdrant",
                        "effect": "NoSchedule",
                    }
                ],
                "affinity": {
                    "nodeAffinity": {
                        "requiredDuringSchedulingIgnoredDuringExecution": {
                            "nodeSelectorTerms": [
                                {
                                    "matchExpressions": [
                                        {
                                            "key": "app",
                                            "operator": "In",
                                            "values": ["qdrant"],
                                        }
                                    ]
                                }
                            ]
                        }
                    },
                    "podAntiAffinity": {
                        "requiredDuringSchedulingIgnoredDuringExecution": [
                            {
                                "labelSelector": {
                                    "matchExpressions": [
                                        {
                                            "key": "app",
                                            "operator": "In",
                                            "values": ["qdrant"],
                                        }
                                    ]
                                },
                                "topologyKey": "kubernetes.io/hostname",
                            }
                        ]
                    },
                },
                "topologySpreadConstraints": [
                    {
                        "maxSkew": 1,
                        "topologyKey": "topology.kubernetes.io/zone",
                        "whenUnsatisfiable": "ScheduleAnyway",
                        "labelSelector": {"matchLabels": {"app": "qdrant"}},
                    }
                ],
                **resource_request,
            },
        ),
        opts=pulumi.ResourceOptions(provider=k8s_provider),
    )
