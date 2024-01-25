from typing import Dict, List, Optional, Union

from pydantic import BaseModel, model_validator
from ruamel.yaml import YAML

from light.utils import to_yaml


class CloudResource(BaseModel):
    """
    Represents a cloud resource in a specific region.

    Attributes:
        region (Optional[str], optional): The region where the cloud resource is located. Defaults to None.
    """

    region: Optional[str] = None


class CloudNode(CloudResource):
    """
    Represents a node in the cloud cluster.

    Attributes:
        nodeType (str): The type of the node.

    Inherited Attributes:
        region (str): The region where the cloud resource is located.
    """

    nodeType: str


class BlobStore(BaseModel):
    """
    Represents a blob store. Bucket name will be the same as the cluster name.

    Attributes:
        bucket (str): The name of the bucket.
    """

    bucket: str


class Serve(BaseModel):
    """
    Represents the configuration for serving instances.

    Attributes:
        minInstances (int): The minimum number of instances to provision.
        maxInstances (int): The maximum number of instances to provision.
    """

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


class ModelGroup(Serve):
    """
    Represents a group of VMs that serve the inference for a specific type of model.

    Attributes:
        name (str): The name of the model group.

    Inherited Attributes:
        minInstances (int): The min number of replicas for the model group.
        maxInstances (int): The max number of replicas for the model group.
    """

    name: str


class CloudModelGroup(ModelGroup, CloudNode):
    """
    Represents a group of cloud models.

    This class inherits from both the `ModelGroup` and `CloudNode` classes.

    Inherited Attributes:
        name (str): The name of the model group.
        minInstances (int): The min number of replicas for the model group.
        maxInstances (int): The max number of replicas for the model group.
        region (str): The region where the cloud resource is located.
        nodeType (str): The type of the node.
    """

    pass


class CloudServerless(Serve, CloudResource):
    """
    Represents a cloud serverless resource.

    This class inherits from the Serve and CloudResource classes.

    Inherited Attributes:
        minInstances (int): The minimum number of instances to provision.
        maxInstances (int): The maximum number of instances to provision.
        region (str): The region where the cloud resource is located.
    """

    pass


class CloudServer(Serve, CloudNode):
    """
    VM app server config for cloud deployment.

    Attributes:
        loadBalancer (bool): Indicates whether a load balancer should be provisioned.
        region (str): The region where the server is located.
        nodeType (str): The type of the server node.

    Inherited Attributes:
        minInstances (int): The minimum number of instances to run.
        maxInstances (int): The maximum number of instances to run.
    """

    loadBalancer: bool = True


class CloudServeConfig(BaseModel):
    """
    Configuration class for cloud server settings.

    Attributes:
        serverless (Optional[CloudServerless]): The serverless configuration.
        server (Optional[CloudServer]): The server configuration.
    """

    serverless: Optional[CloudServerless] = None
    server: Optional[CloudServer] = None

    @model_validator(mode="before")
    def check_one_field(
        cls, values: Dict[str, Union[CloudServerless, CloudServer, None]]
    ) -> Dict[str, Union[CloudServerless, CloudServer, None]]:
        """
        Validates that exactly one field is set in the configuration.

        Args:
            values: A dictionary containing the field values.

        Returns:
            The validated dictionary of field values.

        Raises:
            ValueError: If more or less than one field is set.
        """
        non_none_fields = sum(value is not None for value in values.values())
        if non_none_fields != 1:
            raise ValueError("Exactly one field must be set")

        return values


class Worker(BaseModel):
    """
    Represents a worker in the cluster.

    Attributes:
        instances (int): The number of instances of the worker to launch.
    """

    instances: int


class CloudWorkerConfig(Worker, CloudNode):
    """
    Configuration class for cloud worker.

    Inherited Attributes:
        nodeType (str): The type of the node.
        maxInstances (int): The maximum number of instances to run.
        region (str): The region where the cloud resource is located.
    """

    pass


class JobConfig(BaseModel):
    """
    Represents the configuration for a job.

    Attributes:
        queue (str): The name of the queue.
        lazyCreate (bool, optional): Whether to lazily create the job. Defaults to True.
    """

    queue: str
    lazyCreate: bool = True


class CloudJobConfig(JobConfig):
    """
    Configuration for a cloud job.

    Attributes:
        workers (CloudWorkerConfig): The cloud worker configuration.

    Inherited Attributes:
        queue (str): The name of the queue.
        lazyCreate (bool, optional): Whether to lazily create the job. Defaults to True.
    """

    workers: CloudWorkerConfig


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
        blobStore (BlobStore): The configuration for the blob store.
        ModelGroups (List[CloudModelGroup]): The list of cloud model groups.
        serve (CloudServeConfig): The configuration for serving models in the cloud.
        job (CloudJobConfig): The configuration for cloud jobs.
        vectorStore (CloudVectorStore): The configuration for the cloud vector store.
    """

    cluster: ClusterConfig
    blobStore: Optional[BlobStore] = None
    modelGroups: Optional[List[CloudModelGroup]] = None
    serve: Optional[CloudServeConfig] = None
    job: Optional[CloudJobConfig] = None
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
