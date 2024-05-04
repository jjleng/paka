import pulumi_aws as aws

from paka.cluster.context import Context
from paka.utils import call_once


@call_once
def create_container_registry(ctx: Context) -> None:
    """
    Create a container registry in AWS ECR for storing Docker images.

    Returns:
        None
    """
    repository = aws.ecr.Repository(
        ctx.cluster_name,
        force_delete=True,
        image_tag_mutability="MUTABLE",
    )

    # Save the repository URL to the cluster data file
    repository.repository_url.apply(lambda url: ctx.set_registry(url))
