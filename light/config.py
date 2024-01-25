from typing import Dict, List, Optional

from pydantic import BaseModel, model_validator
from ruamel.yaml import YAML

from light.utils import to_yaml


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


class CloudModelGroup(ModelGroup, CloudNode):
    """
    Represents a group of cloud models.

    This class inherits from both the `ModelGroup` and `CloudNode` classes.

    Inherited Attributes:
        name (str): The name of the model group.
        minInstances (int): The min number of replicas for the model group.
        maxInstances (int): The max number of replicas for the model group.
        nodeType (str): The type of the node.
    """

    pass


class ClusterConfig(BaseModel):
    """
    Represents the configuration for a cluster.

    Attributes:
        name (str): The name of the cluster.
        defaultRegion (str): The default region for the cluster.
    """

    name: str
    defaultRegion: str


class CloudVectorStore(CloudNode):
    """
    Represents a cloud vector store.

    Attributes:
        replicas (int): The number of replicas for the vector store.
        storage_size (str): The size of the storage of one node for the vector store.
    """

    replicas: int = 1
    storage_size: str = "10Gi"


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
