from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Tuple

import pulumi
import pulumi_kubernetes as k8s
from pulumi_kubernetes.helm.v3 import Chart, ChartOpts, FetchOpts

from paka.cluster.context import Context


def memoize(func: Callable[..., Any]) -> Callable[..., Any]:
    cache: Dict[Callable[..., Any], Any] = dict()

    def memoized_func(*args: Tuple[Any, ...], **kwargs: Dict[str, Any]) -> Any:
        if func not in cache:
            cache[func] = func(*args, **kwargs)
        return cache[func]

    return memoized_func


@memoize
def create_prometheus(ctx: Context) -> Optional[Chart]:
    """
    Installs a Prometheus chart.
    """
    config = ctx.cloud_config
    if not config.prometheus or not config.prometheus.enabled:
        return None

    ns = k8s.core.v1.Namespace(
        "prometheus",
        metadata={"name": "prometheus"},
        opts=pulumi.ResourceOptions(provider=ctx.k8s_provider),
    )

    return Chart(
        "kube-prometheus-stack",
        ChartOpts(
            chart="kube-prometheus-stack",
            version="58.6.0",
            namespace="prometheus",
            fetch_opts=FetchOpts(
                repo="https://prometheus-community.github.io/helm-charts"
            ),
            values={
                "nodeExporter": {
                    "enabled": config.prometheus.nodeExporter,
                },
                "alertmanager": {
                    "enabled": config.prometheus.alertmanager,
                },
                "grafana": {
                    "enabled": config.prometheus.grafana,
                },
                "kubeApiServer": {
                    "enabled": config.prometheus.kubeApiServer,
                },
                "kubelet": {
                    "enabled": config.prometheus.kubelet,
                },
                "kubeControllerManager": {
                    "enabled": config.prometheus.kubeControllerManager,
                },
                "coreDns": {
                    "enabled": config.prometheus.coreDns,
                },
                "kubeEtcd": {
                    "enabled": config.prometheus.kubeEtcd,
                },
                "kubeScheduler": {
                    "enabled": config.prometheus.kubeScheduler,
                },
                "kubeProxy": {
                    "enabled": config.prometheus.kubeProxy,
                },
                "kubeStateMetrics": {
                    "enabled": config.prometheus.kubeStateMetrics,
                },
                "thanosRuler": {
                    "enabled": config.prometheus.thanosRuler,
                },
                # Disable the Prometheus Operator's admission webhooks, since they don't work with Pulumi.
                # This means ill-formatted Prometheus rules may make their way into Prometheus. :(
                "prometheusOperator": {
                    "admissionWebhooks": {"enabled": False},
                    "tls": {"enabled": False},
                },
                "kube-state-metrics": {
                    "metricLabelsAllowlist": [
                        "pods=[*]",
                        "deployments=[app.kubernetes.io/name,app.kubernetes.io/component,app.kubernetes.io/instance]",
                    ]
                },
                "prometheus": {
                    "prometheusSpec": {
                        "serviceMonitorSelectorNilUsesHelmValues": False,
                        "podMonitorSelectorNilUsesHelmValues": False,
                        "storageSpec": {
                            "volumeClaimTemplate": {
                                "spec": {
                                    "accessModes": ["ReadWriteOnce"],
                                    "resources": {
                                        "requests": {
                                            "storage": config.prometheus.storageSize,
                                        }
                                    },
                                }
                            }
                        },
                    }
                },
            },
        ),
        opts=pulumi.ResourceOptions(provider=ctx.k8s_provider, depends_on=[ns]),
    )
