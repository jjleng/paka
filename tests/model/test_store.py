import hashlib
import io

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

from paka.model.store import MODEL_PATH_PREFIX, S3ModelStore


@mock_aws
def test_s3_model_store_save() -> None:
    conn = boto3.resource("s3", region_name="us-east-1")
    conn.create_bucket(Bucket="mybucket")

    store = S3ModelStore()
    store.s3_bucket = "mybucket"

    store.save("test.txt", b"Test data")

    body = conn.Object("mybucket", f"{MODEL_PATH_PREFIX}/test.txt").get()["Body"].read()
    assert body == b"Test data"


@mock_aws
def test_save_stream() -> None:
    conn = boto3.resource("s3", region_name="us-east-1")
    conn.create_bucket(Bucket="mybucket")

    store = S3ModelStore()
    store.s3_bucket = "mybucket"

    data = b"Test data"
    sha256_hash = hashlib.sha256(data).hexdigest()
    stream = io.BytesIO(data)
    store.save_stream("test.txt", stream, len(stream.getvalue()), sha256_hash)

    body = conn.Object("mybucket", f"{MODEL_PATH_PREFIX}/test.txt").get()["Body"].read()
    assert body == b"Test data"

    with pytest.raises(
        Exception,
        match="SHA256 hash of the downloaded file does not match the expected value",
    ):
        stream = io.BytesIO(data)
        store.save_stream("test_2.txt", stream, len(stream.getvalue()), "invalid_hash")

    try:
        conn.Object("mybucket", f"{MODEL_PATH_PREFIX}/test_2.txt").load()
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            file_exists = False
        else:
            raise
    else:
        file_exists = True

    assert not file_exists


@mock_aws
def test_file_exists() -> None:
    conn = boto3.resource("s3", region_name="us-east-1")
    conn.create_bucket(Bucket="mybucket")

    store = S3ModelStore()
    store.s3_bucket = "mybucket"

    assert not store.file_exists("test.txt")

    conn.Object("mybucket", f"{MODEL_PATH_PREFIX}/test.txt").put(Body=b"Test data")

    assert store.file_exists("test.txt")

    assert store.file_exists("test", prefix_match=True)
    assert not store.file_exists("nonexistent", prefix_match=True)
