import os
import pytest
import json
from moto import mock_s3
import boto3


@pytest.fixture()
def environment_variables():
    """Mocked AWS credentials and environment variables"""
    os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
    os.environ['AWS_SECURITY_TOKEN'] = 'testing'
    os.environ['AWS_SESSION_TOKEN'] = 'testing'
    os.environ['AWS_REGION'] = 'us-east-1'
    os.environ['TARGET_BUCKET'] = 'target-bucket'


@pytest.fixture()
def s3_bucket(environment_variables):
    target_bucket_name = os.environ.get("TARGET_BUCKET")
    source_bucket_name = "source-bucket"
    valid_object_name = "data/valid.csv"
    invalid_object_name = "data/invalid_star.csv"
    with mock_s3():
        s3 = boto3.resource('s3', region_name='us-east-1')
        target_bucket = s3.Bucket(target_bucket_name)
        target_bucket.create()
        source_bucket = s3.Bucket(source_bucket_name)
        source_bucket.create()
        source_bucket.upload_file(Filename="tests/data/valid.csv",
                                  Key=valid_object_name)
        source_bucket.upload_file(Filename="tests/data/invalid_star.csv",
                                  Key=invalid_object_name)
        yield
