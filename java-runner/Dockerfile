FROM maven:3.9.4-eclipse-temurin-17 AS build
WORKDIR /app

COPY pom.xml .
COPY src ./src

RUN mvn -q package -DskipTests

# -----------------------------
# Runtime Stage
# -----------------------------
FROM eclipse-temurin:17-jre

WORKDIR /runner

COPY --from=build /app/target/*-shaded.jar java-runner.jar

EXPOSE 8090
CMD ["java", "-jar", "java-runner.jar"]