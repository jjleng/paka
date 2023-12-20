from pydantic import BaseModel, model_validator
from typing import Dict, Optional, List
from ruamel.yaml import YAML
from io import StringIO
from utils import sanitize_k8s_name


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
        skip (bool): Indicates whether to skip the blob store provision.
    """

    skip: bool = False


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

    @property
    def sanitized_name(self) -> str:
        return sanitize_k8s_name(self.name)


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


class LocalModelGroup(ModelGroup):
    """
    Represents a group of local models.

    This class is a subclass of ModelGroup and can be used to manage a group of local models.

    Inherited Attributes:
        name (str): The name of the model group.
        minInstances (int): The min number of replicas for the model group.
        maxInstances (int): The max number of replicas for the model group.
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


class LocalServer(Serve):
    """
    Represents a app server config for local deployment.

    This class inherits from the Serve class.

    Inherited Attributes:
        minInstances (int): The minimum number of instances to run.
        maxInstances (int): The maximum number of instances to run.
    """

    pass


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
        cls, values: Dict[str, CloudServerless | CloudServer | None]
    ) -> Dict[str, CloudServerless | CloudServer | None]:
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


class LocalServeConfig(BaseModel):
    """
    Configuration for local server.

    Attributes:
        server (LocalServer): The local server configuration.
    """

    server: LocalServer


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


class LocalWorkerConfig(Worker):
    """
    Configuration class for local worker.
    Inherited Attributes:
        instances (int): The number of instances of the worker to launch.
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


class LocalJobConfig(JobConfig):
    """
    Configuration for local job execution.

    Attributes:
        workers (LocalWorkerConfig): Configuration for local workers.

    Inherited Attributes:
        queue (str): The name of the queue.
        lazyCreate (bool, optional): Whether to lazily create the job. Defaults to True.
    """

    workers: LocalWorkerConfig


class ClusterConfig(BaseModel):
    """
    Represents the configuration for a cluster.

    Attributes:
        name (str): The name of the cluster.
        defaultRegion (str): The default region for the cluster.
    """

    name: str
    defaultRegion: str


class CloudConfig(BaseModel):
    """
    Represents the configuration for the cloud environment.

    Attributes:
        cluster (ClusterConfig): The configuration for the cluster.
        blobStore (BlobStore): The configuration for the blob store.
        ModelGroups (List[CloudModelGroup]): The list of cloud model groups.
        serve (CloudServeConfig): The configuration for serving models in the cloud.
        job (CloudJobConfig): The configuration for cloud jobs.
    """

    cluster: ClusterConfig
    blobStore: Optional[BlobStore] = None
    modelGroups: Optional[List[CloudModelGroup]] = None
    serve: Optional[CloudServeConfig] = None
    job: Optional[CloudJobConfig] = None


class LocalClusterConfig(BaseModel):
    """
    Configuration class for local cluster.

    Attributes:
        name (str): The name of the local cluster.
    """

    name: str


class LocalConfig(BaseModel):
    """
    Configuration class for local cluster settings.

    Attributes:
        cluster (LocalClusterConfig): Configuration for the local cluster.
        ModelGroups (List[LocalModelGroup]): List of local model groups.
        serve (LocalServeConfig): Configuration for local serving.
        job (LocalJobConfig): Configuration for local jobs.
    """

    cluster: LocalClusterConfig
    modelGroups: Optional[List[LocalModelGroup]] = None
    serve: Optional[LocalServeConfig] = None
    job: Optional[LocalJobConfig] = None


class Config(BaseModel):
    """
    Configuration class for managing cluster settings.

    Attributes:
        aws (Optional[CloudConfig]): AWS cloud configuration.
        gcp (Optional[CloudConfig]): GCP cloud configuration.
        local (Optional[LocalConfig]): Local configuration.

    Methods:
        check_one_field: Validates that exactly one field (aws|gcp|local) is set.

    """

    aws: Optional[CloudConfig] = None
    gcp: Optional[CloudConfig] = None
    local: Optional[LocalConfig] = None

    @model_validator(mode="before")
    def check_one_field(
        cls, values: Dict[str, CloudConfig | LocalConfig]
    ) -> Dict[str, CloudConfig | LocalConfig]:
        """
        Validates that exactly one field is set.

        Args:
            values (Dict[str, CloudConfig | LocalConfig]): Dictionary of field values.

        Returns:
            Dict[str, CloudConfig | LocalConfig]: The input values.

        Raises:
            ValueError: If more or less than one field is set.

        """
        non_none_fields = sum(value is not None for value in values.values())
        if non_none_fields != 1:
            raise ValueError("Exactly one field must be set")

        return values


def generate_yaml(config: Config) -> str:
    """
    Generate a YAML string representation of the given config object.

    Args:
        config (Config): The config object to generate YAML from.

    Returns:
        str: The YAML string representation of the config object.
    """
    yaml = YAML()
    yaml.indent(mapping=2, sequence=4, offset=2)
    buf = StringIO()
    yaml.dump(config.model_dump(exclude_none=True), buf)
    return buf.getvalue()


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
