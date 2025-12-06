# =========================
# 1) Build Stage (Maven)
# =========================
FROM maven:3.9.6-eclipse-temurin-17 AS builder

WORKDIR /app

# Copy pom.xml and download dependencies first (cache layer)
COPY pom.xml .
RUN mvn -q dependency:resolve

# Copy source code
COPY src ./src

# Build JAR
RUN mvn -q package -DskipTests

# =========================
# 2) Runtime Stage
# =========================
FROM eclipse-temurin:17-jre

WORKDIR /runner

# Copy built executable JAR from the builder
COPY --from=builder /app/target/java-runner.jar /runner/java-runner.jar

EXPOSE 8090

CMD ["java", "-jar", "/runner/java-runner.jar"]