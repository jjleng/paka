import pytest
from light.cluster.manager.config import (
    Serve,
    CloudServeConfig,
    CloudServerless,
    CloudServer,
    CloudConfig,
    Config,
    LocalConfig,
    ClusterConfig,
    BlobStore,
    CloudInferenceGroup,
    CloudJobConfig,
    CloudWorkerConfig,
    LocalClusterConfig,
    LocalInferenceGroup,
    LocalServeConfig,
    LocalServer,
    LocalJobConfig,
    LocalWorkerConfig,
    generate_yaml,
    parse_yaml,
)

serverless_config = CloudServerless(region="us-east-1", maxInstances=1, minInstances=1)
server_config = CloudServer(maxInstances=1, minInstances=1, nodeType="t2.micro")
cloud_config = CloudConfig(
    cluster=ClusterConfig(name="test-cluster", defaultRegion="us-east-1"),
    blobStore=BlobStore(),
    InferenceGroups=[
        CloudInferenceGroup(name="test-model-group", replica=1, nodeType="t2.micro")
    ],
    serve=CloudServeConfig(serverless=serverless_config),
    job=CloudJobConfig(
        queue="test-queue",
        workers=CloudWorkerConfig(nodeType="t2.micro", instances=2),
    ),
)
local_config = LocalConfig(
    cluster=LocalClusterConfig(name="mycluster"),
    InferenceGroups=[LocalInferenceGroup(name="llama2", replica=1)],
    serve=LocalServeConfig(server=LocalServer(minInstances=1, maxInstances=2)),
    job=LocalJobConfig(queue="redis", workers=LocalWorkerConfig(instances=2)),
)


def test_serve_min_instances_less_than_max_instances() -> None:
    serve: Serve = Serve(minInstances=1, maxInstances=5)
    assert serve.minInstances < serve.maxInstances


def test_serve_min_instances_greater_than_max_instances() -> None:
    with pytest.raises(ValueError):
        Serve(minInstances=5, maxInstances=1)


def test_serve_min_instances_equal_to_max_instances() -> None:
    serve: Serve = Serve(minInstances=3, maxInstances=3)
    assert serve.minInstances == serve.maxInstances


def test_cloud_serve_config_one_field_set() -> None:
    try:
        CloudServeConfig(
            serverless=serverless_config,
        )
        CloudServeConfig(
            server=server_config,
        )
    except Exception:
        pytest.fail("Unexpected exception raised")


def test_cloud_serve_config_multiple_fields_set() -> None:
    with pytest.raises(ValueError):
        CloudServeConfig(serverless=serverless_config, server=server_config)


def test_cloud_serve_config_no_fields_set() -> None:
    with pytest.raises(ValueError):
        CloudServeConfig()


def test_config_only_aws_set() -> None:
    aws_config = cloud_config
    config = Config(aws=aws_config)
    assert config.aws is not None
    assert config.gcp is None
    assert config.local is None


def test_config_only_gcp_set() -> None:
    gcp_config = cloud_config
    config = Config(gcp=gcp_config)
    assert config.aws is None
    assert config.gcp is not None
    assert config.local is None


def test_config_only_local_set() -> None:
    config = Config(local=local_config)
    assert config.aws is None
    assert config.gcp is None
    assert config.local is not None


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
