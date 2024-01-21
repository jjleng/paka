from light.cluster.aws.container_registry import create_container_registry
from light.cluster.aws.eks import create_k8s_cluster
from light.cluster.aws.object_store import create_object_store
from light.cluster.manager.base import ClusterManager
from light.config import Config
from light.utils import save_cluster_data


class AWSClusterManager(ClusterManager):
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
