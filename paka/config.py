from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator
from ruamel.yaml import YAML

from paka.utils import to_yaml


def validate_size(v: str, error_message: str = "Invalid size format") -> str:
    """
    Validates the format of the size field.

    Args:
        v (str): The value of the size field.
        error_message (str, optional): The error message to raise if the format of the input value is invalid. Defaults to "Invalid size format".

    Returns:
        str: The input value if validation is successful.

    Raises:
        ValueError: If the format of the input value is invalid. The error message is specified by the `error_message` parameter.
    """
    if not re.match(r"^\d+(Mi|Gi)$", v):
        raise ValueError(error_message)
    return v


class ResourceRequest(BaseModel):
    """
    Represents the resource request for a container.
    """

    cpu: str = Field(..., description="The amount of CPU to request.")
    memory: str = Field(..., description="The amount of memory to request.")
    gpu: Optional[int] = Field(None, description="The number of GPUs to request.")

    @field_validator("cpu", mode="before")
    def validate_cpu(cls, v: str) -> str:
        """
        Validates the format of the cpu field.

        Args:
            v (str): The value of the cpu field.

        Returns:
            str: The input value if validation is successful.

        Raises:
            ValueError: If the format of the input value is invalid.
        """
        if not re.match(r"^\d+(m)?$", v):
            raise ValueError("Invalid CPU format")
        return v

    @field_validator("memory", mode="before")
    def validate_memory(cls, v: str) -> str:
        """
        Validates the format of the memory field.

        Args:
            v (str): The value of the memory field.

        Returns:
            str: The input value if validation is successful.

        Raises:
            ValueError: If the format of the input value is invalid.
        """
        return validate_size(v, "Invalid memory format")

    @field_validator("gpu", mode="before")
    def validate_gpu(cls, v: Optional[int]) -> Optional[int]:
        """
        Validates the value of the gpu field.

        Args:
            v (Optional[int]): The value of the gpu field.

        Returns:
            Optional[int]: The input value if validation is successful.

        Raises:
            ValueError: If the value is less than 0.
        """
        if v is not None and v < 0:
            raise ValueError("GPU count cannot be less than 0")
        return v


class AwsGpuNode(BaseModel):
    """
    Represents a configuration for an AWS GPU node.
    """

    diskSize: int = Field(
        ..., description="The size of the disk for the GPU node in GB."
    )


class GcpGpuNode(BaseModel):
    """
    Represents a Google Cloud Platform GPU node.
    """

    imageType: str = Field(..., description="The type of image used for the GPU node.")
    acceleratorType: str = Field(
        ..., description="The type of accelerator used for the GPU node."
    )
    acceleratorCount: int = Field(
        ..., description="The number of accelerators attached to the GPU node."
    )
    diskType: str = Field(..., description="The type of disk used for the GPU node.")
    diskSize: int = Field(
        ..., description="The size of the disk attached to the GPU node in GB."
    )


class CloudNode(BaseModel):
    """
    Represents a node in the cloud cluster.
    """

    nodeType: str = Field(..., description="The type of the node.")
    diskSize: int = Field(
        20, description="The size of the disk attached to the node in GB."
    )
    awsGpu: Optional[AwsGpuNode] = Field(
        None, description="The AWS GPU node configuration, if applicable."
    )
    gcpGpu: Optional[GcpGpuNode] = Field(
        None, description="The GCP GPU node configuration, if applicable."
    )

    @model_validator(mode="before")
    def validate_gpu(
        cls, values: Dict[str, Union[AwsGpuNode, GcpGpuNode]]
    ) -> Dict[str, Union[AwsGpuNode, GcpGpuNode]]:
        if values.get("awsGpu") and values.get("gcpGpu"):
            raise ValueError("At most one of awsGpu or gcpGpu can exist")
        return values


class Runtime(BaseModel):
    """
    Represents a runtime for a model.
    """

    image: str = Field(..., description="The Docker image to use for the runtime.")
    command: Optional[List[str]] = Field(
        None, description="The command to run in the Docker container."
    )


class Model(BaseModel):
    """
    Represents a model.
    """

    hfRepoId: Optional[str] = Field(
        None, description="The HuggingFace repository ID for the model."
    )
    files: List[str] = Field(
        ["*"], description="The list of files to include from the repository."
    )
    useModelStore: bool = Field(
        True, description="Whether to save the model to a model store, such as s3."
    )


class ModelGroup(BaseModel):
    """
    Represents a group of VMs that serve the inference for a specific type of model.
    """

    name: str = Field(..., description="The name of the model group.")
    minInstances: int = Field(
        ..., description="The minimum number of instances to provision."
    )
    maxInstances: int = Field(
        ..., description="The maximum number of instances to provision."
    )
    model: Optional[Model] = Field(
        None,
        description="The model to deploy in the model group. If None, runtime image is responsible for loading the model.",
    )
    runtime: Runtime = Field(..., description="The runtime for the model group.")

    @model_validator(mode="before")
    def check_instances_num(cls, values: Dict[str, int]) -> Dict[str, int]:
        min_instances, max_instances = values.get("minInstances"), values.get(
            "maxInstances"
        )
        if min_instances and max_instances and max_instances < min_instances:
            raise ValueError(
                "maxInstances must be greater than or equal to minInstances"
            )
        return values

    @field_validator("minInstances", mode="before")
    def validate_min_instances(cls, v: int) -> int:
        """
        Validates the value of the minInstances field. Spinning up 1 model group instance is heavy.
        No scaling down to 0 for now.

        Args:
            v (int): The value of the minInstances field.

        Returns:
            int: The input value if validation is successful.

        Raises:
            ValueError: If the value of the input value is invalid.
        """
        if v <= 0:
            raise ValueError("minInstances must be greater than 0")
        return v


class Trigger(BaseModel):
    """
    Represents a trigger.
    """

    type: str = Field(..., description="The type of the trigger.")
    metadata: Dict[str, str] = Field(
        ..., description="The metadata associated with the trigger."
    )


class CloudModelGroup(ModelGroup, CloudNode):
    """
    Represents a group of cloud models.
    """

    # TODO: make required for HPA to work
    resourceRequest: Optional[ResourceRequest] = Field(
        None,
        description="The resource request for the model group, specifying the amount of CPU and memory to request.",
    )

    autoScaleTriggers: Optional[List[Trigger]] = Field(
        None,
        description="""The list of triggers for auto-scaling.
    Triggers for autoscaling the model group. Trigger are not strongly typed, so we use a list of dictionaries to represent them.
    For example:

    autoScaleTriggers=[
        # CPU trigger example
        Trigger(
            type="cpu",
            metadata={
                "type": "Utilization",
                "value": "70"
            }
        ),
        # Prometheus trigger example
        Trigger(
            type="prometheus",
            metadata={
                "serverAddress": "http://prometheus-operated.default.svc.cluster.local",
                "metricName": "http_requests_total",
                "threshold": "100",
                "query": "sum(rate(http_requests_total{job=\"example-job\"}[2m]))"
            }
        )
    ]
    """,
    )


class ClusterConfig(BaseModel):
    """
    Represents the configuration for a cluster.
    """

    name: str = Field(..., description="The name of the cluster.")
    region: str = Field(..., description="The default region for the cluster.")
    namespace: str = Field(
        "default", description="The namespace in which the cluster is deployed."
    )
    nodeType: str = Field(..., description="The type of nodes in the cluster.")
    minNodes: int = Field(
        ..., description="The minimum number of nodes in the cluster."
    )
    maxNodes: int = Field(
        ..., description="The maximum number of nodes in the cluster."
    )
    logRetentionDays: int = Field(
        14, description="The number of days to retain log entries."
    )


class CloudVectorStore(CloudNode):
    """
    Represents a cloud vector store.
    """

    replicas: int = Field(1, description="The number of replicas for the vector store.")
    storage_size: str = Field(
        "10Gi", description="The size of the storage of one node for the vector store."
    )
    resourceRequest: Optional[ResourceRequest] = Field(
        None,
        description="The resource request for the vector store, specifying the amount of CPU and memory to request.",
    )

    @field_validator("storage_size", mode="before")
    def validate_storage_size(cls, v: str) -> str:
        """
        Validates the format of the storage_size field.

        Args:
            v (str): The value of the storage_size field.

        Returns:
            str: The input value if validation is successful.

        Raises:
            ValueError: If the format of the input value is invalid.
        """
        return validate_size(v, "Invalid storage size format")

    @field_validator("replicas", mode="before")
    def validate_replicas(cls, v: int) -> int:
        """
        Validates the value of the replicas field.

        Args:
            v (int): The value of the replicas field.

        Returns:
            int: The input value if validation is successful.

        Raises:
            ValueError: If the value of the input value is invalid.
        """
        if v <= 0:
            raise ValueError("replicas must be greater than 0")
        return v


class Job(BaseModel):
    """
    Represents a job cluster configuration.
    """

    enabled: bool = Field(False, description="Whether the job cluster is enabled.")
    broker_storage_size: str = Field(
        "10Gi", description="The size of the storage for the broker."
    )

    @field_validator("broker_storage_size", mode="before")
    def validate_broker_storage_size(cls, v: str) -> str:
        """
        Validates the format of the broker_storage_size field.

        Args:
            v (str): The value of the storage_size field.

        Returns:
            str: The input value if validation is successful.

        Raises:
            ValueError: If the format of the input value is invalid.
        """
        return validate_size(v, "Invalid storage size format")


class Prometheus(BaseModel):
    """
    Represents a Prometheus configuration.
    """

    enabled: bool = Field(False, description="Whether Prometheus is enabled.")
    storage_size: str = Field(
        "10Gi", description="The size of the storage for Prometheus."
    )
    grafana: bool = Field(False, description="Whether Grafana is enabled.")
    alertmanager: bool = Field(False, description="Whether Alertmanager is enabled.")
    kube_api_server: bool = Field(
        False, description="Whether the Kubernetes API server is enabled."
    )
    kubelet: bool = Field(False, description="Whether the Kubelet is enabled.")
    kube_controller_manager: bool = Field(
        False, description="Whether the Kubernetes controller manager is enabled."
    )
    core_dns: bool = Field(False, description="Whether CoreDNS is enabled.")
    kube_etcd: bool = Field(
        False, description="Whether the Kubernetes etcd is enabled."
    )
    kube_scheduler: bool = Field(
        False, description="Whether the Kubernetes scheduler is enabled."
    )
    kube_proxy: bool = Field(
        False, description="Whether the Kubernetes proxy is enabled."
    )
    kube_state_metrics: bool = Field(
        False, description="Whether the Kubernetes state metrics are enabled."
    )
    node_exporter: bool = Field(
        False, description="Whether the Node Exporter is enabled."
    )
    thanos_ruler: bool = Field(
        False, description="Whether the Thanos Ruler is enabled."
    )

    @field_validator("storage_size", mode="before")
    def validate_storage_size(cls, v: str) -> str:
        """
        Validates the format of the storage_size field.

        Args:
            v (str): The value of the storage_size field.

        Returns:
            str: The input value if validation is successful.

        Raises:
            ValueError: If the format of the input value is invalid.
        """
        return validate_size(v, "Invalid storage size format")


class Tracing(BaseModel):
    """
    Represents the configuration for tracing.
    """

    enabled: bool = Field(False, description="Whether tracing is enabled.")
    autoScalingEnabled: bool = Field(
        False, description="Whether auto-scaling is enabled for tracing."
    )
    zipkinHelmSettings: Optional[Dict[str, Any]] = Field(
        None,
        description="The settings for the Zipkin Helm chart. See https://github.com/openzipkin/zipkin-helm",
    )


class CloudConfig(BaseModel):
    """
    Represents the configuration for the cloud environment.
    """

    cluster: ClusterConfig = Field(
        ..., description="The configuration for the Kubernetes cluster."
    )
    modelGroups: Optional[List[CloudModelGroup]] = Field(
        None,
        description="The list of model groups to be deployed in the cloud. Default is None. If None, no model groups are deployed.",
    )
    vectorStore: Optional[CloudVectorStore] = Field(
        None,
        description="The configuration for the vector store in the cloud. Default is None. If None, no vector store is deployed",
    )
    job: Optional[Job] = Field(
        None,
        description="The configuration for the job broker. Default is None. If None, no job broker is deployed.",
    )
    prometheus: Optional[Prometheus] = Field(
        None,
        description="The configuration for Prometheus. Default is None. If None, Prometheus is not deployed.",
    )
    tracing: Optional[Tracing] = Field(
        None,
        description="The configuration for tracing. Default is None. If None, tracing is not enabled.",
    )

    @field_validator("modelGroups", mode="before")
    def check_model_group(cls, v: List[Any]) -> List[Any]:
        if v is None or len(v) == 0:
            return v
        # Check if there are duplicated model group names
        model_group_names = [dict(group)["name"] for group in v]
        if len(set(model_group_names)) != len(model_group_names):
            raise ValueError("Duplicate model group names are not allowed")
        return v


class Config(BaseModel):
    """
    Configuration class for managing cloud cluster settings.
    """

    # version: int = Field(..., description="The version of the configuration.")
    aws: Optional[CloudConfig] = Field(None, description="The AWS cloud configuration.")

    @model_validator(mode="before")
    def check_one_field(cls, values: Dict[str, CloudConfig]) -> Dict[str, CloudConfig]:
        """
        Validates that exactly one cloud configuration is provided.

        Args:
            values (Dict[str, CloudConfig]): Dictionary of field values, where keys are the cloud providers (aws, gcp) and values are the corresponding cloud configurations.

        Returns:
            Dict[str, CloudConfig]: The input values if validation is successful.

        Raises:
            ValueError: If more or less than one cloud configuration is provided.
        """
        non_none_fields = sum(value is not None for value in values.values())
        if non_none_fields != 1:
            raise ValueError("Exactly one cloud configuration must be provided")

        return values


def generate_yaml(config: Config) -> str:
    """
    Generate a YAML string representation of the given config object.

    Args:
        config (Config): The config object to generate YAML from.

    Returns:
        str: The YAML string representation of the config object.
    """
    return to_yaml(config.model_dump(exclude_none=True))


def parse_yaml(yaml_str: str) -> Config:
    """
    Parse a YAML string and return a Config object.

    Args:
        yaml_str (str): The YAML string to parse.

    Returns:
        Config: The parsed Config object.
    """
    yaml = YAML()
    data = yaml.load(yaml_str)
    # Migrate data if it's an old version
    # version = data.get("version", 1)  # Default to version 1 if no version is specified
    # if version < 2:
    #     data = migrate_v1_to_v2(data)
    # if version > cls.version:
    #         raise ValueError(f"Unsupported config version: {version}. Please update your tool.")

    return Config(**data)
