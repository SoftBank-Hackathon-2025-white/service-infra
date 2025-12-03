import subprocess
import boto3
import os
import uuid
import pathlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

s3 = boto3.client("s3")

def download_user_code(bucket, key):
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

    if not bucket or not code_key or not log_bucket:
        print("⚠️ 환경변수(CODE_BUCKET, CODE_KEY, LOG_BUCKET) 미설정")
        return

    path = download_user_code(bucket, code_key)
    stdout, stderr = execute_code(path)

    log = f"STDOUT:\n{stdout}\nSTDERR:\n{stderr}"
    upload_log(log_bucket, f"logs/{uuid.uuid4()}.txt", log)

    print("🎉 Code Executed Successfully!")


# -----------------------------
# HTTP /health 서버 구현 부분
# -----------------------------
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"RUNNER READY")
        else:
            self.send_response(404)
            self.end_headers()


def start_health_server():
    port = int(os.getenv("HEALTH_PORT", "8080"))
    server = HTTPServer(("", port), Handler)
    print(f"🚀 Health Check Server running on port {port}")
    server.serve_forever()


# -----------------------------
# 메인 실행
# -----------------------------
if __name__ == "__main__":
    # 헬스 서버 별도 스레드 실행
    threading.Thread(target=start_health_server, daemon=True).start()

    # 실행 핸들러 시작
    handler()