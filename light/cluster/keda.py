from pulumi_kubernetes.helm.v3 import Chart, ChartOpts, FetchOpts
from light.utils import call_once


@call_once
def create_keda() -> None:
    """
    Installs a KEDA chart.
    """
    Chart(
        "keda",
        ChartOpts(
            chart="keda",
            version="2.12.1",
            namespace="keda",
            fetch_opts=FetchOpts(repo="https://kedacore.github.io/charts"),
            values={},
        ),
    )
