import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, field_validator, model_validator
from ruamel.yaml import YAML

from light.utils import to_yaml


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

    Attributes:
        cpu (str): The amount of CPU to request.
        memory (str): The amount of memory to request.
    """

    cpu: str
    memory: str

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


class CloudNode(BaseModel):
    """
    Represents a node in the cloud cluster.

    Attributes:
        nodeType (str): The type of the node.

    """

    nodeType: str


class ModelGroup(BaseModel):
    """
    Represents a group of VMs that serve the inference for a specific type of model.

    Attributes:
        name (str): The name of the model group.
        minInstances (int): The minimum number of instances to provision.
        maxInstances (int): The maximum number of instances to provision.
    """

    name: str
    minInstances: int
    maxInstances: int

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


class CloudModelGroup(ModelGroup, CloudNode):
    """
    Represents a group of cloud models.

    This class inherits from both the `ModelGroup` and `CloudNode` classes.

    Attributes:
        resource_request (Optional[ResourceRequest]): The resource request for the model group, specifying the amount of CPU and memory to request.

    Inherited Attributes:
        name (str): The name of the model group.
        minInstances (int): The minimum number of instances to provision for the model group.
        maxInstances (int): The maximum number of instances to provision for the model group.
        nodeType (str): The type of the node.
    """

    resource_request: Optional[ResourceRequest] = None


class ClusterConfig(BaseModel):
    """
    Represents the configuration for a cluster.

    Attributes:
        name (str): The name of the cluster.
        region (str): The default region for the cluster.
    """

    name: str
    region: str


class CloudVectorStore(CloudNode):
    """
    Represents a cloud vector store.

    Attributes:
        replicas (int): The number of replicas for the vector store. Defaults to 1.
        storage_size (str): The size of the storage of one node for the vector store. Defaults to "10Gi".
        resource_request (Optional[ResourceRequest]): The resource request for the vector store, specifying the amount of CPU and memory to request.

    Inherited Attributes:
        nodeType (str): The type of the node.

    Methods:
        validate_storage_size: Validates the format of the storage_size field.
    """

    replicas: int = 1
    storage_size: str = "10Gi"
    resource_request: Optional[ResourceRequest] = None

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


class CloudConfig(BaseModel):
    """
    Represents the configuration for the cloud environment.

    Attributes:
        cluster (ClusterConfig): The configuration for the cluster.
        ModelGroups (List[CloudModelGroup]): The list of cloud model groups.
        vectorStore (CloudVectorStore): The configuration for the cloud vector store.
    """

    cluster: ClusterConfig
    modelGroups: Optional[List[CloudModelGroup]] = None
    vectorStore: Optional[CloudVectorStore] = None

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

    Attributes:
        aws (Optional[CloudConfig]): AWS cloud configuration.
        gcp (Optional[CloudConfig]): GCP cloud configuration.

    Methods:
        check_one_field: Validates that exactly one cloud configuration (aws or gcp) is provided.
    """

    aws: Optional[CloudConfig] = None
    gcp: Optional[CloudConfig] = None

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
    return Config(**data)
