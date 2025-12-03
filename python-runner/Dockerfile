FROM python:3.10-slim

# 작업 디렉토리
WORKDIR /runner

# AWS SDK 설치
RUN pip install boto3

# 실행 스크립트 복사
COPY run.py /runner/run.py

CMD ["python", "run.py"]