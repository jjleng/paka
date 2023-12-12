import pulumi
from pulumi_aws import s3


def s3_bucket(cluster_name: str) -> s3.Bucket:
    bucket = s3.Bucket(cluster_name)

    pulumi.export("bucket_name", bucket.id)

    return bucket
