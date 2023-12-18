from light.cluster.config import CloudConfig
import pulumi_aws as aws


def create_container_registry(config: CloudConfig) -> None:
    """
    Create a container registry in AWS ECR for storing Docker images.

    Args:
        config (CloudConfig): The configuration object containing cluster information.

    Returns:
        None
    """
    project = config.cluster.name
    aws.ecr.Repository(project, image_tag_mutability="MUTABLE")
