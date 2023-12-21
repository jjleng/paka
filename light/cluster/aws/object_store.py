from light.config import CloudConfig
import pulumi_aws as aws
from light.utils import call_once


@call_once
def create_object_store(config: CloudConfig) -> None:
    """
    Creates an object store in AWS S3 based on the provided configuration.

    Args:
        config (CloudConfig): The configuration object containing cluster information.

    Returns:
        None
    """
    project = config.cluster.name

    # `bucket` is the name of the bucket. It will avoid pulumi appending a random string to the name
    # `force_destroy`` is needed to delete the bucket when it's not empty
    aws.s3.Bucket(project, bucket=project, force_destroy=True)
