FROM python:3.10-slim

WORKDIR /runner

# 시스템 패키지 업데이트 (권장)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 필요한 pip 패키지 설치
RUN pip install --no-cache-dir boto3 psutil

# 앱 복사
COPY app.py /runner/app.py

EXPOSE 8080

CMD ["python", "app.py"]