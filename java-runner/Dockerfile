FROM openjdk:17-slim

WORKDIR /runner

# javac 사용 가능해야 함
RUN apt-get update && apt-get install -y --no-install-recommends \
    nano wget unzip && rm -rf /var/lib/apt/lists/*

# 애플리케이션 복사
COPY target/java-runner.jar /runner/java-runner.jar

EXPOSE 8090

CMD ["java", "-jar", "/runner/java-runner.jar"]