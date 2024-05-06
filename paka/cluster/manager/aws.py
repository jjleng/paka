from paka.cluster.aws.container_registry import create_container_registry
from paka.cluster.aws.eks import create_k8s_cluster
from paka.cluster.aws.object_store import create_object_store
from paka.cluster.manager.base import ClusterManager
from paka.config import Config


class AWSClusterManager(ClusterManager):
    """
    AWS-specific implementation of the ClusterManager abstract base class.

    The AWSClusterManager class is responsible for managing a cluster of AWS resources.
    It provides methods for creating and managing AWS-specific resources such as EKS clusters,
    node groups, and service accounts. It also handles AWS-specific configuration and setup tasks.
    """

    def __init__(self, config: Config) -> None:
        super().__init__(config)

    def provision_k8s(self) -> None:
        create_object_store(self.ctx)
        create_container_registry(self.ctx)
        create_k8s_cluster(self.ctx)
