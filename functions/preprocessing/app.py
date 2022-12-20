import boto3
import pandas as pd
import pandas.api.types as ptypes
import numpy as np
import MeCab
import os
from faker import Faker
import logging
from datetime import datetime

logger = logging.getLogger()
logger.setLevel(logging.INFO)
fake = Faker()
path = '/tmp/data'
isExist = os.path.exists(path)
if isExist:
    logger.info("/tmp/data already exists")
else:
    os.mkdir(path)
    logger.info("Create /tmp/data directory")


class InvalidDataFrameException(Exception):
    pass


def retrieve_bucket_object(event):
    bucket_name = event["detail"]["bucket"]["name"]
    object_name = event["detail"]["object"]["key"]
    return {
        "bucket_name": bucket_name,
        "object_name": object_name
    }


def save_word_files_locally(params):
    bucket_name = params["bucket_name"]
    object_name = params["object_name"]
    local_file_path = f"/tmp/{object_name}"
    s3 = boto3.resource('s3', region_name="us-east-1")
    bucket = s3.Bucket(bucket_name)
    bucket.download_file(Key=object_name, Filename=local_file_path)
    return local_file_path


def remove_unnecessary_columns(filepath):
    df = pd.read_csv(filepath, header=0, encoding='utf8')
    if 'review_body' not in df.keys():
        raise InvalidDataFrameException('review_body not in keys')
    if 'star_rating' not in df.keys():
        raise InvalidDataFrameException('star_rating not in keys')
    df_pos_neg = df.loc[:, ['star_rating', 'review_body']]
    if not ptypes.is_int64_dtype(df['star_rating']):
        raise InvalidDataFrameException('star_rating must be int64')
    df_pos_neg = df_pos_neg[df_pos_neg.star_rating != 3]
    return df_pos_neg


def preprocess_row_of_label(x):
    """
    BlazingText expects input labels to be prefixed by the string __label__
    https://docs.aws.amazon.com/sagemaker/latest/dg/blazingtext.html#bt-inputoutput
    This function transforms document label of each row to meet the requirements.
    """
    if x["star_rating"] < 3:
        label = '0'
    else:
        label = '1'
    x["star_rating"] = "__label__" + label
    return x


def preprocess_row_of_sentence(x):
    """
    BlazingText expects input sentences to be separated by each word.
    https://docs.aws.amazon.com/sagemaker/latest/dg/blazingtext.html#bt-inputoutput
    This function transforms document sentence of each row to meet the requirements.
    """
    mecab = MeCab.Tagger("-Owakati")
    x["review_body"] = mecab.parse(
        x["review_body"].replace('<br />', '')).replace('\n', '')
    return x


def preprocess_whole_dataset(df):
    """
    Apply
    1. Label name replace
    2. Separate a sentence into words
    """
    labeled_df = df.apply(lambda x: preprocess_row_of_label(x), axis=1)
    separeted_df = labeled_df.apply(
        lambda x: preprocess_row_of_sentence(x), axis=1)
    return separeted_df


def upload_preprocessed_dataset(df):
    file_name = fake.file_name(extension='csv')
    file_path = f"/tmp/data/{file_name}"
    object_name = f"preprocessed/{file_name}"
    np.savetxt(file_path, df.values, fmt="%s %s", delimiter=' ')
    logger.info("Preprocessed file: %s", file_path)
    logger.info("Object name: %s", object_name)
    s3 = boto3.resource('s3', region_name="us-east-1")
    bucket_name = os.environ.get("TARGET_BUCKET")
    bucket = s3.Bucket(bucket_name)
    bucket.upload_file(Key=object_name, Filename=file_path)
    dataset_object_key = f"s3://{bucket_name}/{object_name}"
    return dataset_object_key


def lambda_handler(event, context):
    logger.info("event: %s", event)
    params = retrieve_bucket_object(event)
    logger.info("Retrieved parameters: %s", params)
    local_file_path = save_word_files_locally(params)
    logger.info("Saved file: %s", local_file_path)
    try:
        df = remove_unnecessary_columns(local_file_path)
        preprocessed_data = preprocess_whole_dataset(df)
        object_key = upload_preprocessed_dataset(preprocessed_data)

        now = datetime.now()
        suffix = now.strftime('%Y-%m-%d-%H-%M-%S')
        training_job_name = f"word-embedding-training-{suffix}"

        return {
            "dataset": object_key,
            "training": training_job_name
        }
    except InvalidDataFrameException as e:
        logger.error(
            "Cannot open Pandas DataFrame or preprocess the dataframe due to invalid columns")
        raise InvalidDataFrameException(e.args[0])
