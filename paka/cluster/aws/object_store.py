import pulumi_aws as aws

from paka.config import CloudConfig
from paka.utils import call_once, save_cluster_data


@call_once
def create_object_store(config: CloudConfig) -> None:
    """
    Creates an object store in AWS S3 based on the provided configuration.

    Args:
        config (CloudConfig): The configuration object containing cluster information.

    Returns:
        None
    """
    # `bucket` is the name of the bucket. It will avoid pulumi appending a random string to the name
    # `force_destroy`` is needed to delete the bucket when it's not empty
    bucket = aws.s3.Bucket(config.cluster.name, force_destroy=True)
    bucket.id.apply(lambda id: save_cluster_data(config.cluster.name, "bucket", id))
