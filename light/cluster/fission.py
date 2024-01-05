import pulumi
import pulumi_kubernetes as k8s
from pulumi_kubernetes.helm.v3 import Chart, ChartOpts, FetchOpts
from pulumi_kubernetes.yaml import ConfigFile

from light.utils import call_once


@call_once
def create_fission(k8s_provider: k8s.Provider) -> None:
    k8s.core.v1.Namespace(
        "fission",
        metadata={"name": "fission"},
    )
    crd_urls = [
        "https://raw.githubusercontent.com/fission/fission/v1.20.0/crds/v1/fission.io_canaryconfigs.yaml",
        "https://raw.githubusercontent.com/fission/fission/v1.20.0/crds/v1/fission.io_environments.yaml",
        "https://raw.githubusercontent.com/fission/fission/v1.20.0/crds/v1/fission.io_functions.yaml",
        "https://raw.githubusercontent.com/fission/fission/v1.20.0/crds/v1/fission.io_httptriggers.yaml",
        "https://raw.githubusercontent.com/fission/fission/v1.20.0/crds/v1/fission.io_kuberneteswatchtriggers.yaml",
        "https://raw.githubusercontent.com/fission/fission/v1.20.0/crds/v1/fission.io_messagequeuetriggers.yaml",
        "https://raw.githubusercontent.com/fission/fission/v1.20.0/crds/v1/fission.io_packages.yaml",
        "https://raw.githubusercontent.com/fission/fission/v1.20.0/crds/v1/fission.io_timetriggers.yaml",
    ]
    for crd_url in crd_urls:
        ConfigFile(crd_url.split("/")[-1], file=crd_url)

    Chart(
        "fission",
        ChartOpts(
            chart="fission-all",
            version="1.20.0",
            fetch_opts=FetchOpts(repo="https://fission.github.io/fission-charts/"),
            namespace="fission",
            values={
                "serviceType": "ClusterIP",
                "routerServiceType": "ClusterIP",
                "analytics": False,
                "gaTrackingID": "",
            },
        ),
        opts=pulumi.ResourceOptions(provider=k8s_provider),
    )
