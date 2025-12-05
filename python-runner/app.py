import subprocess
import boto3
import os
import uuid
import pathlib
import time
import psutil
from urllib.parse import urlparse, parse_qs
from http.server import BaseHTTPRequestHandler, HTTPServer
import json

s3 = boto3.client("s3")

def download_user_code(bucket, key):
    filename = pathlib.Path(key).name
    local_path = f"/runner/{filename}"
    s3.download_file(bucket, key, local_path)
    return local_path

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

    cpu_percent = proc.cpu_percent()
    memory_mb = proc.memory_info().rss / (1024 * 1024)

    return result.stdout, result.stderr, exec_time_ms, cpu_percent, memory_mb

def upload_log_json(bucket, data):
    log_key = f"logs/{uuid.uuid4()}.json"
    s3.put_object(
        Bucket=bucket,
        Key=log_key,
        Body=json.dumps(data, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json"
    )
    return log_key


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
                local_path = download_user_code(bucket, code_key)
                stdout, stderr, exec_time_ms, cpu_percent, memory_mb = execute_code(local_path)

                response_data = {
                    "stdout": stdout,
                    "stderr": stderr,
                    "execution_time_ms": exec_time_ms,
                    "cpu_percent": cpu_percent,
                    "memory_mb": memory_mb,
                    "code_key": code_key
                }

                log_key = upload_log_json(log_bucket, response_data)
                response_data["log_key"] = log_key

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(response_data).encode("utf-8"))

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
    print(f"🚀 Python Runner running on port {port}")
    server.serve_forever()


if __name__ == "__main__":
    start_server()