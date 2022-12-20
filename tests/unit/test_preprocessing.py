from functions.preprocessing import app
import json
import pytest
import os
import shutil
import boto3


@pytest.fixture(autouse=True)
def directory_setup_and_cleanup():
    """Make and remove /tmp/data directory before and after test"""
    try:
        os.mkdir('/tmp/data')
    except OSError as e:
        print("/tmp/data exists %s." % (e.strerror))
    yield
    try:
        shutil.rmtree('/tmp/data')
    except OSError as e:
        print("Error: %s - %s." % (e.filename, e.strerror))


def generate_valid_object_created_event():
    """Return dummy event from valid_object_created.json"""
    f = open('tests/events/valid_object_created.json')
    event = json.load(f)
    return event


def generate_invalid_object_created_event():
    """Return dummy event from valid_object_created.json"""
    f = open('tests/events/invalid_object_created.json')
    event = json.load(f)
    return event


def test_retrieve_bucket_object():
    event = generate_valid_object_created_event()
    response = app.retrieve_bucket_object(event)
    assert response["bucket_name"] == "source-bucket"
    assert response["object_name"] == "data/valid.csv"


def test_save_word_files_locally(environment_variables, s3_bucket):
    event = generate_valid_object_created_event()
    response = app.retrieve_bucket_object(event)
    local_file_path = app.save_word_files_locally(response)
    assert local_file_path == "/tmp/data/valid.csv"


def test_remove_unnecessary_columns():
    valid_testdata = "tests/data/valid.csv"
    valid_df = app.remove_unnecessary_columns(valid_testdata)
    assert valid_df.columns.to_list() == ['star_rating', 'review_body']

    lack_review_body = "tests/data/lack_review_body.csv"
    with pytest.raises(app.InvalidDataFrameException) as exc_info:
        app.remove_unnecessary_columns(lack_review_body)
    assert str(exc_info.value) == 'review_body not in keys'

    invalid_star_rating = "tests/data/invalid_star.csv"
    with pytest.raises(app.InvalidDataFrameException) as exc_info:
        app.remove_unnecessary_columns(invalid_star_rating)
    assert str(exc_info.value) == 'star_rating must be int64'


def test_preprocess_whole_dataset():
    testdata = "tests/data/valid.csv"
    df = app.remove_unnecessary_columns(testdata)
    preprocessed_data = app.preprocess_whole_dataset(df)
    assert set(preprocessed_data['star_rating'].values.tolist()) == set(
        ["__label__0", "__label__1"])


def test_upload_preprocessed_dataset(environment_variables, s3_bucket):
    testdata = "tests/data/valid.csv"
    df = app.remove_unnecessary_columns(testdata)
    preprocessed_data = app.preprocess_whole_dataset(df)
    object_name = app.upload_preprocessed_dataset(preprocessed_data)
    bucket_name = os.environ.get("TARGET_BUCKET")
    s3_client = boto3.client('s3')
    result = s3_client.list_objects_v2(Bucket=bucket_name)
    assert 'Contents' in result


def test_handler_valid_object(environment_variables, s3_bucket):
    event = generate_valid_object_created_event()
    response = app.lambda_handler(event, "")
    assert "dataset" in response


def test_handler_invalid_object(environment_variables, s3_bucket):
    event = generate_invalid_object_created_event()
    with pytest.raises(app.InvalidDataFrameException) as exc_info:
        response = app.lambda_handler(event, "")
    assert str(exc_info.value) == 'star_rating must be int64'
