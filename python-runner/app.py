import subprocess
import boto3
import os
import uuid
import pathlib

s3 = boto3.client("s3")

def download_user_code(bucket, key):
    # key에서 파일명 추출
    filename = pathlib.Path(key).name
    local_path = f"/runner/{filename}"

    s3.download_file(bucket, key, local_path)
    return local_path

def execute_code(path):
    result = subprocess.run(
        ["python3", path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=15
    )
    return result.stdout, result.stderr

def upload_log(bucket, log_key, content):
    s3.put_object(
        Bucket=bucket,
        Key=log_key,
        Body=content.encode("utf-8")
    )

def handler():
    bucket = os.getenv("CODE_BUCKET")
    code_key = os.getenv("CODE_KEY")
    log_bucket = os.getenv("LOG_BUCKET")

    path = download_user_code(bucket, code_key)
    stdout, stderr = execute_code(path)

    log = f"STDOUT:\n{stdout}\nSTDERR:\n{stderr}"

    upload_log(log_bucket, f"logs/{uuid.uuid4()}.txt", log)

if __name__ == "__main__":
    handler()