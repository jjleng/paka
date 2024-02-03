from typing import Any

import pytest

from cusco.config import (
    CloudConfig,
    CloudModelGroup,
    CloudVectorStore,
    ClusterConfig,
    Config,
    ModelGroup,
    ResourceRequest,
    generate_yaml,
    parse_yaml,
)

cloud_config = CloudConfig(
    cluster=ClusterConfig(
        name="test-cluster",
        region="us-east-1",
        nodeType="t2.micro",
        minNodes=2,
        maxNodes=2,
        logRetentionDays=14,
        namespace="default",
    ),
    modelGroups=[
        CloudModelGroup(
            name="test-model-group", minInstances=1, maxInstances=2, nodeType="t2.micro"
        )
    ],
)


def test_valid_resource_request() -> None:
    rr = ResourceRequest(cpu="500m", memory="2Gi")
    assert rr.cpu == "500m"
    assert rr.memory == "2Gi"

    rr = ResourceRequest(cpu="2", memory="200Mi")
    assert rr.cpu == "2"
    assert rr.memory == "200Mi"


def test_invalid_cpu_resource_request() -> None:
    with pytest.raises(ValueError, match="Invalid CPU format"):
        ResourceRequest(cpu="500n", memory="2Gi")


def test_invalid_memory_resource_request() -> None:
    with pytest.raises(ValueError, match="Invalid memory format"):
        ResourceRequest(cpu="500m", memory="2G")


def test_model_group() -> None:
    # Test with valid minInstances and maxInstances
    model_group = ModelGroup(name="test", minInstances=1, maxInstances=2)
    assert model_group.name == "test"
    assert model_group.minInstances == 1
    assert model_group.maxInstances == 2

    # Test with maxInstances less than minInstances
    with pytest.raises(
        ValueError, match="maxInstances must be greater than or equal to minInstances"
    ):
        ModelGroup(name="test", minInstances=2, maxInstances=1)

    # Test with minInstances less than or equal to 0
    with pytest.raises(ValueError, match="minInstances must be greater than 0"):
        ModelGroup(name="test", minInstances=0, maxInstances=2)


def test_cloud_vector_store() -> None:
    # Test with valid replicas and storage_size
    resource_request = ResourceRequest(cpu="2000m", memory="2Gi")
    vector_store = CloudVectorStore(
        nodeType="t2.small",
        replicas=2,
        storage_size="20Gi",
        resource_request=resource_request,
    )
    assert vector_store.nodeType == "t2.small"
    assert vector_store.replicas == 2
    assert vector_store.storage_size == "20Gi"
    assert vector_store.resource_request == resource_request

    # Test with replicas less than or equal to 0
    with pytest.raises(ValueError, match="replicas must be greater than 0"):
        CloudVectorStore(nodeType="t2.small", replicas=0, storage_size="10Gi")

    # Test with invalid storage_size format
    with pytest.raises(ValueError, match="Invalid storage size format"):
        CloudVectorStore(nodeType="t2.small", replicas=1, storage_size="10Gib")


def test_cloud_config() -> None:
    # Test with valid cluster, modelGroups, and vectorStore
    cluster = ClusterConfig(
        name="test-cluster",
        region="us-west-2",
        nodeType="t2.micro",
        minNodes=2,
        maxNodes=2,
        logRetentionDays=14,
        namespace="default",
    )
    model_group1 = CloudModelGroup(
        nodeType="c7a.xlarge", name="test-group1", minInstances=1, maxInstances=2
    )
    model_group2 = CloudModelGroup(
        nodeType="c7a.xlarge", name="test-group2", minInstances=1, maxInstances=2
    )
    resource_request = ResourceRequest(cpu="2000m", memory="2Gi")
    vector_store = CloudVectorStore(
        nodeType="t2.small",
        replicas=2,
        storage_size="20Gi",
        resource_request=resource_request,
    )
    cloud_config = CloudConfig(
        cluster=cluster,
        modelGroups=[model_group1, model_group2],
        vectorStore=vector_store,
    )
    assert cloud_config.cluster == cluster
    assert cloud_config.modelGroups == [model_group1, model_group2]
    assert cloud_config.vectorStore == vector_store

    # Test with duplicate model group names
    model_group1 = CloudModelGroup(
        nodeType="c7a.xlarge", name="test-group", minInstances=1, maxInstances=2
    )
    model_group2 = CloudModelGroup(
        nodeType="c7a.xlarge", name="test-group", minInstances=1, maxInstances=2
    )
    with pytest.raises(ValueError, match="Duplicate model group names are not allowed"):
        CloudConfig(
            cluster=cluster,
            modelGroups=[model_group1, model_group2],
            vectorStore=vector_store,
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
            region: us-west-2
            namespace: test_namespace
            nodeType: t2.medium
            minNodes: 2
            maxNodes: 4
            logRetentionDays: 7
        modelGroups:
            - nodeType: c7a.xlarge
              minInstances: 1
              maxInstances: 1
              name: llama2-7b
        vectorStore:
            nodeType: t2.small
            replicas: 2
    """
    config = parse_yaml(yaml_str)
    assert isinstance(config, Config)
    assert config.aws is not None
    assert config.aws.cluster.name == "test_cluster"
    assert config.aws.cluster.region == "us-west-2"
    assert config.aws.cluster.namespace == "test_namespace"
    assert config.aws.cluster.nodeType == "t2.medium"
    assert config.aws.cluster.minNodes == 2
    assert config.aws.cluster.maxNodes == 4
    assert config.aws.cluster.logRetentionDays == 7
    assert config.aws.modelGroups is not None
    assert len(config.aws.modelGroups) == 1
    model_group = config.aws.modelGroups[0]
    assert model_group.nodeType == "c7a.xlarge"
    assert model_group.minInstances == 1
    assert model_group.maxInstances == 1
    assert model_group.name == "llama2-7b"
    assert config.aws.vectorStore is not None
    assert config.aws.vectorStore.nodeType == "t2.small"
    assert config.aws.vectorStore.replicas == 2


def test_round_trip() -> None:
    original_config = Config(aws=cloud_config)
    yaml_str = generate_yaml(original_config)
    parsed_config = parse_yaml(yaml_str)
    assert original_config == parsed_config


def test_aws_yaml(snapshot: Any) -> None:
    original_config = Config(aws=cloud_config)
    yaml_str = generate_yaml(original_config)
    snapshot.assert_match(yaml_str, "aws_yaml.txt")
