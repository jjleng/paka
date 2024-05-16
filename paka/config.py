from __future__ import annotations

import re
from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from ruamel.yaml import YAML

from paka.utils import to_yaml

CONFIG_VERSION = "1.1"


class PakaBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


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


class ResourceRequest(PakaBaseModel):
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


class AwsGpuNodeConfig(PakaBaseModel):
    """
    Represents a configuration for an AWS GPU node.
    """

    enabled: bool = Field(False, description="Whether the GPU node is enabled.")

    # At least 40 GB is required for the disk size
    diskSize: Optional[int] = Field(
        40, description="The size of the disk for the GPU node in GB."
    )


class GcpGpuNodeConfig(PakaBaseModel):
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


class CloudNode(PakaBaseModel):
    """
    Represents a node in the cloud cluster.
    """

    nodeType: str = Field(..., description="The type of the node.")
    diskSize: int = Field(
        20, description="The size of the disk attached to the node in GB."
    )


class AwsNode(CloudNode):
    """
    Represents an AWS cloud node configuration.
    """

    gpu: Optional[AwsGpuNodeConfig] = Field(
        None, description="The AWS GPU node configuration, if applicable."
    )


class Runtime(PakaBaseModel):
    """
    Represents a runtime for a model.
    """

    image: str = Field(..., description="The Docker image to use for the runtime.")
    command: Optional[List[str]] = Field(
        None, description="The command to run in the Docker container."
    )


class Model(PakaBaseModel):
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


class Trigger(PakaBaseModel):
    """
    Represents a trigger.
    """

    type: str = Field(..., description="The type of the trigger.")
    metadata: Dict[str, str] = Field(
        ..., description="The metadata associated with the trigger."
    )


class CloudModelGroup(CloudNode):
    """
    Represents a group of cloud models.
    """

    name: str = Field(..., description="The name of the model group.")
    model: Optional[Model] = Field(
        None,
        description="The model to deploy in the model group. If None, runtime image is responsible for loading the model.",
    )
    runtime: Runtime = Field(..., description="The runtime for the model group.")

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

    isPublic: bool = Field(
        False,
        description="Whether the model group can be accessed through a public endpoint.",
    )


class ScalingConfig(PakaBaseModel):
    minInstances: int = Field(
        ..., description="The minimum number of instances to provision."
    )
    maxInstances: int = Field(
        ..., description="The maximum number of instances to provision."
    )

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


class OnDemandModelGroup(CloudModelGroup, ScalingConfig):
    pass


class MixedModelGroup(CloudModelGroup):
    baseInstances: int = Field(
        ...,
        description=(
            "Initial set of instances that are provisioned using on-demand "
            "instances. These instances are always running. Their primary purpose is to guarantee the constant "
            "availability of the model group service. If you don't require these base instances, you can set their number to 0."
        ),
    )
    maxOnDemandInstances: int = Field(
        ...,
        description=(
            "This sets the maximum limit for provisioning on-demand instances, including the base instances. "
            "It should always be set to a value equal to or greater than 'baseInstances'. "
            "These on-demand instances serve as a fallback when spot instances are unavailable. "
            "The actual number of on-demand instances is dynamically adjusted by the autoscaler based on the workload requirements."
        ),
    )
    spot: ScalingConfig = Field(
        ...,
        description=(
            "This configuration sets the scaling parameters for spot instances within the node group. "
            "It specifies the minimum and maximum number of spot instances that can be used. "
            "Spot instances are cost-effective but may not always be available due to market conditions. "
            "The autoscaler uses this configuration to dynamically adjust the number of spot instances based on workload demand."
        ),
    )

    @model_validator(mode="before")
    def check_instances_num(cls, values: Dict[str, int]) -> Dict[str, int]:
        base_instances, max_on_demand_instances = values.get(
            "baseInstances"
        ), values.get("maxOnDemandInstances")
        if (
            base_instances is not None
            and max_on_demand_instances is not None
            and max_on_demand_instances < base_instances
        ):
            raise ValueError(
                "maxOnDemandInstances must be greater than or equal to baseInstances"
            )
        return values

    @field_validator("baseInstances", mode="before")
    def validate_base_instances(cls, v: int) -> int:
        if v < 0:
            raise ValueError("baseInstances must be greater than or equal to 0")
        return v


class AwsModelGroup(OnDemandModelGroup, AwsNode):
    pass


class AwsMixedModelGroup(MixedModelGroup, AwsNode):
    pass


class ClusterConfig(PakaBaseModel):
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


class Job(PakaBaseModel):
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


class Prometheus(PakaBaseModel):
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


class Tracing(PakaBaseModel):
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


T_OnDemandModelGroup = TypeVar("T_OnDemandModelGroup", bound=OnDemandModelGroup)
T_MixedModelGroup = TypeVar("T_MixedModelGroup", bound=MixedModelGroup)


class CloudConfig(PakaBaseModel, Generic[T_OnDemandModelGroup, T_MixedModelGroup]):
    """
    Represents the configuration for the cloud environment.
    """

    cluster: ClusterConfig = Field(
        ..., description="The configuration for the Kubernetes cluster."
    )
    modelGroups: Optional[List[T_OnDemandModelGroup]] = Field(
        None,
        description="The list of model groups to be deployed in the cloud. Default is None. If None, no model groups are deployed.",
    )
    mixedModelGroups: Optional[List[T_MixedModelGroup]] = Field(
        None,
        description="The list of mixed model groups to be deployed in the cloud. Default is None. If None, no mixed model groups are deployed.",
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

    @model_validator(mode="before")
    def check_model_group_names(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        # No model groups should have the same name
        model_group_names = set()

        for group in values.get("modelGroups", []):
            group_name = dict(group)["name"]
            if group_name in model_group_names:
                raise ValueError(f"Duplicate model group names are not allowed")
            model_group_names.add(group_name)

        for mixed_group in values.get("mixedModelGroups", []):
            mixed_group_name = dict(mixed_group)["name"]
            if mixed_group_name in model_group_names:
                raise ValueError(f"Duplicate model group names are not allowed")
            model_group_names.add(mixed_group_name)

        return values


class AwsConfig(CloudConfig[AwsModelGroup, AwsMixedModelGroup]):
    modelGroups: Optional[List[AwsModelGroup]] = Field(
        None,
        description="The list of model groups to be deployed in the cloud. Default is None. If None, no model groups are deployed.",
    )

    mixedModelGroups: Optional[List[AwsMixedModelGroup]] = Field(
        None,
        description="The list of mixed model groups to be deployed in the cloud. Default is None. If None, no mixed model groups are deployed.",
    )


class Config(PakaBaseModel):
    """
    Configuration class for managing cloud cluster settings.
    """

    version: str = Field(..., description="The version of the configuration.")
    aws: Optional[AwsConfig] = Field(None, description="The AWS cloud configuration.")

    @model_validator(mode="before")
    def check_one_field(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validates that exactly one cloud configuration is provided.

        Args:
            values (Dict[str, Any]): Dictionary of field values for the Config class.

        Returns:
            Dict[str, Any]: The input values if validation is successful.

        Raises:
            ValueError: If more or less than one cloud configuration is provided.
        """
        if "aws" not in values:
            raise ValueError("Exactly one cloud configuration must be provided")

        return values

    @field_validator("version", mode="before")
    def validate_version(cls, v: str) -> str:
        if not re.match(r"^\d+\.\d+$", v):
            raise ValueError('version must be in the format "x.x"')
        return v


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
    version = data.get("version", None)
    if version is None:
        raise ValueError("Invalid configuration: The 'version' field is missing.")

    if not re.match(r"^\d+\.\d+$", version):
        raise ValueError('version must be in the format "x.x"')

    # Make sure the major version matches
    major_version, minor_version = map(int, version.split("."))
    tool_major_version, tool_minor_version = map(int, CONFIG_VERSION.split("."))

    if major_version < tool_major_version:
        raise ValueError(
            f"Invalid configuration: This tool supports versions starting from {tool_major_version}.0."
            " Please use an older version of the tool if you need to work with a previous configuration version."
        )
    elif major_version > tool_major_version:
        raise ValueError(
            f"Invalid configuration: Your current tool is too old. Please upgrade your tool to handle this configuration."
        )
    elif minor_version > tool_minor_version:  # No forward compatibility
        raise ValueError(
            f"Invalid configuration: This tool supports versions up to {tool_major_version}.{tool_minor_version}."
            " Please upgrade your tool to handle this configuration."
        )

    return Config(**data)
