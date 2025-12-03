FROM python:3.10-slim

WORKDIR /runner

# 필요한 패키지 설치
RUN pip install boto3

# 실행 스크립트 복사
COPY app.py /runner/app.py

CMD ["python", "app.py"]