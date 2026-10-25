"""S3-compatible release storage for tests: KAJENN_RELEASE_S3 names a private JSON file.

The file holds endpoint_url, access_key and secret_key of a disposable server
(RustFS in Docker during development). Each test uses its own bucket.
"""

import json
import os
from uuid import uuid4

import s3fs


def s3_credentials():
    with open(os.environ["KAJENN_RELEASE_S3"]) as stream:
        return json.load(stream)


def filesystem():
    credentials = s3_credentials()
    return s3fs.S3FileSystem(
        key=credentials["access_key"],
        secret=credentials["secret_key"],
        client_kwargs={"endpoint_url": credentials["endpoint_url"]},
        skip_instance_cache=True,
    )


def release_bucket():
    """Create a fresh bucket and return its Genro Storage mount configuration."""
    bucket = "releases-" + uuid4().hex[:20]
    filesystem().mkdir(bucket)
    credentials = s3_credentials()
    return {
        "protocol": "s3",
        "bucket": bucket,
        "endpoint_url": credentials["endpoint_url"],
        "access_key": credentials["access_key"],
        "secret_key": credentials["secret_key"],
    }


def bucket_objects(config):
    """Every key in the bucket mapped to its bytes."""
    fs = filesystem()
    keys = fs.find(config["bucket"])
    return {key.split("/", 1)[1]: fs.cat_file(key) for key in keys}
