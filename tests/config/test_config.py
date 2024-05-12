from __future__ import annotations

from typing import Any

import pytest

from paka.config import (
    CONFIG_VERSION,
    AwsConfig,
    AwsModelGroup,
    CloudConfig,
    CloudVectorStore,
    ClusterConfig,
    Config,
    MixedModelGroup,
    ResourceRequest,
    Runtime,
    ScalingConfig,
    generate_yaml,
    parse_yaml,
)

cloud_config = AwsConfig(
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
        AwsModelGroup(
            name="test-model-group",
            minInstances=1,
            maxInstances=2,
            nodeType="t2.micro",
            runtime=Runtime(image="test-image"),
            resourceRequest=ResourceRequest(cpu="500m", memory="2Gi"),
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


def test_invalid_gpu_resource_request() -> None:
    with pytest.raises(ValueError, match="GPU count cannot be less than 0"):
        ResourceRequest(cpu="500m", memory="2Gi", gpu=-1)


def test_mixed_model_group() -> None:
    with pytest.raises(
        ValueError, match="baseInstances must be greater than or equal to 0"
    ):
        MixedModelGroup(
            name="test",
            nodeType="c7i.xlarge",
            runtime=Runtime(image="test-image"),
            baseInstances=-1,
            maxOnDemandInstances=0,
            spot=ScalingConfig(minInstances=1, maxInstances=10),
        )

    with pytest.raises(
        ValueError,
        match="maxOnDemandInstances must be greater than or equal to baseInstances",
    ):
        MixedModelGroup(
            name="test",
            nodeType="c7i.xlarge",
            runtime=Runtime(image="test-image"),
            baseInstances=2,
            maxOnDemandInstances=1,
            spot=ScalingConfig(minInstances=1, maxInstances=10),
        )


def test_aws_model_group() -> None:
    # Test with valid minInstances and maxInstances
    model_group = AwsModelGroup(
        name="test",
        nodeType="c7i.xlarge",
        minInstances=1,
        maxInstances=2,
        runtime=Runtime(image="test-image"),
    )
    assert model_group.name == "test"
    assert model_group.minInstances == 1
    assert model_group.maxInstances == 2

    # Test with maxInstances less than minInstances
    with pytest.raises(
        ValueError, match="maxInstances must be greater than or equal to minInstances"
    ):
        AwsModelGroup(
            name="test",
            nodeType="c7i.xlarge",
            minInstances=2,
            maxInstances=1,
            runtime=Runtime(image="test-image"),
        )

    # Test with minInstances less than or equal to 0
    with pytest.raises(ValueError, match="minInstances must be greater than 0"):
        AwsModelGroup(
            name="test",
            nodeType="c7i.xlarge",
            minInstances=0,
            maxInstances=2,
            runtime=Runtime(image="test-image"),
        )


def test_cloud_vector_store() -> None:
    # Test with valid replicas and storage_size
    resource_request = ResourceRequest(cpu="2000m", memory="2Gi")
    vector_store = CloudVectorStore(
        nodeType="t2.small",
        replicas=2,
        storage_size="20Gi",
        resourceRequest=resource_request,
    )
    assert vector_store.nodeType == "t2.small"
    assert vector_store.replicas == 2
    assert vector_store.storage_size == "20Gi"
    assert vector_store.resourceRequest == resource_request

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
    model_group1 = AwsModelGroup(
        nodeType="c7a.xlarge",
        name="test-group1",
        minInstances=1,
        maxInstances=2,
        runtime=Runtime(image="test-image"),
        resourceRequest=ResourceRequest(cpu="500m", memory="2Gi"),
    )
    model_group2 = AwsModelGroup(
        nodeType="c7a.xlarge",
        name="test-group2",
        minInstances=1,
        maxInstances=2,
        runtime=Runtime(image="test-image"),
        resourceRequest=ResourceRequest(cpu="500m", memory="2Gi"),
    )
    resource_request = ResourceRequest(cpu="2000m", memory="2Gi")
    vector_store = CloudVectorStore(
        nodeType="t2.small",
        replicas=2,
        storage_size="20Gi",
        resourceRequest=resource_request,
    )
    cloud_config = AwsConfig(
        cluster=cluster,
        modelGroups=[model_group1, model_group2],
        vectorStore=vector_store,
    )
    assert cloud_config.cluster == cluster
    assert cloud_config.modelGroups == [model_group1, model_group2]
    assert cloud_config.vectorStore == vector_store

    # Test with duplicate model group names
    model_group1 = AwsModelGroup(
        nodeType="c7a.xlarge",
        name="test-group",
        minInstances=1,
        maxInstances=2,
        runtime=Runtime(image="test-image"),
        resourceRequest=ResourceRequest(cpu="500m", memory="2Gi"),
    )
    model_group2 = AwsModelGroup(
        nodeType="c7a.xlarge",
        name="test-group",
        minInstances=1,
        maxInstances=2,
        runtime=Runtime(image="test-image"),
        resourceRequest=ResourceRequest(cpu="500m", memory="2Gi"),
    )
    with pytest.raises(ValueError, match="Duplicate model group names are not allowed"):
        CloudConfig(
            cluster=cluster,
            modelGroups=[model_group1, model_group2],
            vectorStore=vector_store,
        )


def test_config_only_aws_set() -> None:
    aws_config = cloud_config
    config = Config(version="1.0", aws=aws_config)
    assert config.aws is not None


def test_config_no_fields_set() -> None:
    with pytest.raises(ValueError):
        Config(version="1.0")


def test_generate_yaml() -> None:
    config = Config(version="1.0", aws=cloud_config)
    yaml_str = generate_yaml(config)
    assert isinstance(yaml_str, str)
    assert "aws" in yaml_str


def test_parse_yaml() -> None:
    yaml_str = """
    version: "1.0"
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
              runtime:
                image: test-image
              gpu:
              resourceRequest:
                cpu: 500m
                memory: 2Gi
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
    assert model_group.gpu is None
    assert config.aws.vectorStore is not None
    assert config.aws.vectorStore.nodeType == "t2.small"
    assert config.aws.vectorStore.replicas == 2

    yaml_str = """
    version: "1.0"
    aws:
        cluster:
            name: test_cluster
            region: us-west-2
            nodeType: t2.medium
            minNodes: 2
            maxNodes: 4
        modelGroups:
            - nodeType: c7a.xlarge
              minInstances: 1
              maxInstances: 1
              name: llama2-7b
              runtime:
                image: test-image
              gpu:
                diskSize: 100
              resourceRequest:
                cpu: 500m
                memory: 2Gi
    """
    config = parse_yaml(yaml_str)
    assert isinstance(config, Config)
    assert config.aws is not None
    assert config.aws.modelGroups is not None
    assert len(config.aws.modelGroups) == 1
    model_group = config.aws.modelGroups[0]
    assert model_group.gpu is not None
    assert model_group.gpu.diskSize == 100


def test_round_trip() -> None:
    original_config = Config(version="1.0", aws=cloud_config)
    yaml_str = generate_yaml(original_config)
    parsed_config = parse_yaml(yaml_str)
    assert original_config == parsed_config


def test_aws_yaml(snapshot: Any) -> None:
    original_config = Config(version="1.0", aws=cloud_config)
    yaml_str = generate_yaml(original_config)
    snapshot.assert_match(yaml_str, "aws_yaml.txt")


def test_config_version_validation() -> None:
    with pytest.raises(ValueError, match='version must be in the format "x.x"'):
        Config(version="1", aws={})


def test_parse_yaml_version_validation() -> None:
    major_version, minor_version = map(int, CONFIG_VERSION.split("."))
    with pytest.raises(
        ValueError, match="Invalid configuration: The 'version' field is missing."
    ):
        parse_yaml("aws: {}")

    with pytest.raises(ValueError, match='version must be in the format "x.x"'):
        parse_yaml("version: '1'\naws: {}")

    with pytest.raises(
        ValueError,
        match=f"Invalid configuration: This tool supports versions starting from {major_version}.0.",
    ):
        parse_yaml(f"""version: '{major_version - 1}.0'\naws: {{}}""")

    with pytest.raises(
        ValueError, match="Invalid configuration: Your current tool is too old."
    ):
        parse_yaml(f"""version: '{major_version + 1}.0'\naws: {{}}""")

    with pytest.raises(
        ValueError,
        match=f"Invalid configuration: This tool supports versions up to {major_version}.{minor_version}.",
    ):
        parse_yaml(f"""version: '{major_version}.{minor_version + 1}'\naws: {{}}""")
