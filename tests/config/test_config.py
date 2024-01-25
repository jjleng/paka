from typing import Any

import pytest

from light.config import (
    CloudConfig,
    CloudModelGroup,
    ClusterConfig,
    Config,
    generate_yaml,
    parse_yaml,
)

cloud_config = CloudConfig(
    cluster=ClusterConfig(name="test-cluster", defaultRegion="us-east-1"),
    modelGroups=[
        CloudModelGroup(
            name="test-model-group", minInstances=1, maxInstances=2, nodeType="t2.micro"
        )
    ],
)


def test_config_only_aws_set() -> None:
    aws_config = cloud_config
    config = Config(aws=aws_config)
    assert config.aws is not None
    assert config.gcp is None


def test_config_only_gcp_set() -> None:
    gcp_config = cloud_config
    config = Config(gcp=gcp_config)
    assert config.aws is None
    assert config.gcp is not None


def test_config_multiple_fields_set() -> None:
    aws_config = cloud_config
    gcp_config = cloud_config
    with pytest.raises(ValueError):
        Config(aws=aws_config, gcp=gcp_config)


def test_config_no_fields_set() -> None:
    with pytest.raises(ValueError):
        Config()


def test_generate_yaml() -> None:
    config = Config(aws=cloud_config)
    yaml_str = generate_yaml(config)
    assert isinstance(yaml_str, str)
    assert "aws" in yaml_str


def test_parse_yaml() -> None:
    yaml_str = """
    aws:
        cluster:
            name: test_cluster
            defaultRegion: us-west-2
        blobStore:
            bucket: test_bucket
    """
    config = parse_yaml(yaml_str)
    assert isinstance(config, Config)
    assert config.aws is not None
    assert config.aws.cluster.name == "test_cluster"
    assert config.aws.cluster.defaultRegion == "us-west-2"


def test_round_trip() -> None:
    original_config = Config(aws=cloud_config)
    yaml_str = generate_yaml(original_config)
    parsed_config = parse_yaml(yaml_str)
    assert original_config == parsed_config


def test_aws_yaml(snapshot: Any) -> None:
    original_config = Config(aws=cloud_config)
    yaml_str = generate_yaml(original_config)
    snapshot.assert_match(yaml_str, "aws_yaml.txt")
