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
from datetime import datetime

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

    cpu_percent = proc.cpu_percent(interval=0.1)
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

    # JSON 응답 유틸리티
    def _send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):

        # -------------------------
        # 헬스체크
        # -------------------------
        if self.path.startswith("/health"):
            self._send_json({"status": "RUNNER READY"})
            return

        # -------------------------
        # 하드웨어 상태 조회 (/python/status)
        # -------------------------
        if self.path.startswith("/python/status"):
            try:
                vm = psutil.virtual_memory()
                cpu_total = psutil.cpu_percent(interval=0.1)

                proc = psutil.Process()
                proc_cpu = proc.cpu_percent(interval=0.1)
                proc_mem = proc.memory_info().rss / (1024 * 1024)

                data = {
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "system": {
                        "cpu_percent": cpu_total,
                        "memory_total_mb": round(vm.total / (1024 * 1024), 2),
                        "memory_used_mb": round(vm.used / (1024 * 1024), 2),
                        "memory_percent": vm.percent,
                    },
                    "process": {
                        "cpu_percent": proc_cpu,
                        "memory_mb": round(proc_mem, 2),
                    }
                }

                self._send_json(data)
            except Exception as e:
                self._send_json({"error": str(e)}, status=500)
            return

        # -------------------------
        # 코드 실행 (/python/run)
        # -------------------------
        if self.path.startswith("/python/run"):
            query = parse_qs(urlparse(self.path).query)
            code_key = query.get("code_key", [None])[0]

            if not code_key:
                self._send_json({"error": "Missing code_key parameter"}, status=400)
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
                    "code_key": code_key,
                }

                log_key = upload_log_json(log_bucket, response_data)
                response_data["log_key"] = log_key

                self._send_json(response_data)

            except Exception as e:
                self._send_json({"error": str(e)}, status=500)
            return

        # -------------------------
        # 404
        # -------------------------
        self._send_json({"error": "Not Found"}, status=404)


def start_server():
    port = int(os.getenv("PORT", "8080"))
    server = HTTPServer(("", port), Handler)
    print(f"🚀 Python Runner running on port {port}")
    server.serve_forever()


if __name__ == "__main__":
    start_server()