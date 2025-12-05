import subprocess
import boto3
import os
import uuid
import pathlib
import time
import psutil
import json
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
    proc = psutil.Process(os.getpid())

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

    # CPU/메모리 측정 (현재 프로세스 기준)
    cpu_percent = proc.cpu_percent(interval=None)
    memory_mb = proc.memory_info().rss / (1024 * 1024)

    return result.stdout, result.stderr, exec_time_ms, cpu_percent, memory_mb

# -----------------------------
# 로그 업로드 (JSON 문자열 통째로 올림)
# -----------------------------
def upload_log(bucket, content: str):
    """
    content: 이미 JSON 문자열 상태로 전달받는다고 가정
    """
    log_key = f"logs/{uuid.uuid4()}.txt"
    s3.put_object(
        Bucket=bucket,
        Key=log_key,
        Body=content.encode("utf-8"),
        ContentType="application/json"
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

                # 공통 응답/로그 payload 구성
                payload = {
                    "stdout": stdout,
                    "stderr": stderr,
                    "execution_time_ms": exec_time_ms,
                    "cpu_percent": cpu_percent,
                    "memory_mb": memory_mb,
                    "code_key": code_key,
                }

                # 일단 log_key는 나중에 추가
                # JSON 문자열로 직렬화 (한 번만 만들기)
                # ensure_ascii=False → 한글도 그대로
                # separators로 가독성보다 사이즈를 조금 줄일 수 있음 (선택사항)
                # 일단 기본값 사용
                json_body_for_log = json.dumps(payload, ensure_ascii=False)

                # 로그 업로드 (log_key 생성)
                log_key = upload_log(log_bucket, json_body_for_log)

                # 응답에 log_key 포함
                payload["log_key"] = log_key
                json_body_for_response = json.dumps(payload, ensure_ascii=False)

                # 최종 응답
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json_body_for_response.encode("utf-8"))

            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
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