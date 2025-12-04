import subprocess
import boto3
import os
import uuid
import pathlib
import time
import psutil
from urllib.parse import urlparse, parse_qs
from http.server import BaseHTTPRequestHandler, HTTPServer

s3 = boto3.client("s3")

# -----------------------------
# S3에서 코드 다운로드
# -----------------------------
def download_user_code(bucket, key):
    filename = pathlib.Path(key).name
    local_path = f"/runner/{filename}"
    s3.download_file(bucket, key, local_path)
    return local_path

# -----------------------------
# 코드 실행
# -----------------------------
def execute_code(path):
    proc = psutil.Process()

    start_time = time.time()
    result = subprocess.run(
        ["python3", path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=15
    )
    end_time = time.time()

    exec_time_ms = int((end_time - start_time) * 1000)

    # CPU/메모리 측정
    cpu_percent = proc.cpu_percent()
    memory_mb = proc.memory_info().rss / (1024 * 1024)

    return result.stdout, result.stderr, exec_time_ms, cpu_percent, memory_mb

# -----------------------------
# 로그 업로드
# -----------------------------
def upload_log(bucket, content):
    log_key = f"logs/{uuid.uuid4()}.txt"
    s3.put_object(
        Bucket=bucket,
        Key=log_key,
        Body=content.encode("utf-8")
    )
    return log_key


# ============================================================================
# HTTP 서버 핸들러
# ============================================================================
class Handler(BaseHTTPRequestHandler):

    def do_GET(self):

        if self.path.startswith("/health"):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"RUNNER READY")
            return

        if self.path.startswith("/python/run"):
            query = parse_qs(urlparse(self.path).query)
            code_key = query.get("code_key", [None])[0]

            if code_key is None:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Missing code_key parameter")
                return

            bucket = os.getenv("CODE_BUCKET")
            log_bucket = os.getenv("LOG_BUCKET")

            try:
                path = download_user_code(bucket, code_key)
                stdout, stderr, exec_time_ms, cpu_percent, memory_mb = execute_code(path)

                # 로그 저장
                log_txt = f"STDOUT:\n{stdout}\n\nSTDERR:\n{stderr}"
                log_key = upload_log(log_bucket, log_txt)

                # 응답
                response = {
                    "stdout": stdout,
                    "stderr": stderr,
                    "log_key": log_key,
                    "execution_time_ms": exec_time_ms,
                    "cpu_percent": cpu_percent,
                    "memory_mb": memory_mb,
                    "code_key": code_key
                }

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(str(response).encode("utf-8"))

            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode("utf-8"))

        else:
            self.send_response(404)
            self.end_headers()


def start_server():
    port = int(os.getenv("PORT", "8080"))
    server = HTTPServer(("", port), Handler)
    print(f"🚀 Execution Engine HTTP Server running on port {port}")
    server.serve_forever()


if __name__ == "__main__":
    start_server()