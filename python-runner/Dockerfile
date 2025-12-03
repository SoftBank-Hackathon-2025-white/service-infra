FROM python:3.10-slim

WORKDIR /runner

# 필요한 패키지 설치
RUN pip install boto3

# 실행 스크립트 복사
COPY app.py /runner/app.py

# Health Port 노출
EXPOSE 8080

CMD ["python", "app.py"]