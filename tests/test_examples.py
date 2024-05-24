from pathlib import Path

import pytest

from paka.config import parse_yaml

examples_path = Path(__file__).parent.parent / "examples"


@pytest.mark.parametrize(
    "cluster_config",
    [
        examples_path / "website_rag" / "cluster.yaml",
        examples_path / "invoice_extraction" / "cluster.yaml",
        examples_path / "invoice_extraction" / "cluster_cpu.yaml",
    ],
)
def test_example_configs(cluster_config: Path) -> None:
    cluster_config = Path(cluster_config).expanduser().absolute()

    if not cluster_config.exists():
        raise FileNotFoundError(f"The cluster config file does not exist")

    with open(cluster_config, "r") as file:
        parse_yaml(file.read())
