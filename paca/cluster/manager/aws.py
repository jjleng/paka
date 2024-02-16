from paca.cluster.aws.container_registry import create_container_registry
from paca.cluster.aws.eks import create_k8s_cluster
from paca.cluster.aws.object_store import create_object_store
from paca.cluster.manager.base import ClusterManager
from paca.config import Config
from paca.utils import save_cluster_data


class AWSClusterManager(ClusterManager):
    """
    AWS-specific implementation of the ClusterManager abstract base class.

    The AWSClusterManager class is responsible for managing a cluster of AWS resources.
    It provides methods for creating and managing AWS-specific resources such as EKS clusters,
    node groups, and service accounts. It also handles AWS-specific configuration and setup tasks.
    """

    def __init__(self, config: Config) -> None:
        if config.aws is None:
            raise ValueError("AWS config is required")
        super().__init__(config)

    def provision_k8s(self) -> None:
        # TODO: Hardcoded provider value `aws` should be defined in config
        save_cluster_data(self.config.cluster.name, "provider", "aws")
        create_object_store(self.config)
        create_container_registry(self.config)
        create_k8s_cluster(self.config)
