import pulumi_aws as aws

from paka.cluster.context import Context
from paka.utils import call_once


@call_once
def create_object_store(ctx: Context) -> None:
    """
    Creates an object store in AWS S3 based on the provided configuration.

    Returns:
        None
    """
    # `bucket` is the name of the bucket. It will avoid pulumi appending a random string to the name
    # `force_destroy`` is needed to delete the bucket when it's not empty
    bucket = aws.s3.Bucket(ctx.cluster_name, force_destroy=True)
    bucket.id.apply(lambda id: ctx.set_bucket(id))
