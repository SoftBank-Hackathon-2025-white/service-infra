# ---------- Build Stage ----------
FROM maven:3.9.6-amazoncorretto-17 AS build

WORKDIR /app

COPY pom.xml .
COPY src ./src

RUN mvn -q package -DskipTests

# ---------- Runtime Stage ----------
FROM amazoncorretto:17

WORKDIR /runner
RUN mkdir -p /runner && chmod -R 777 /runner

RUN yum install -y unzip wget

COPY --from=build /app/target/java-runner-1.0.0.jar /runner/java-runner.jar

EXPOSE 8090

CMD ["java", "-jar", "/runner/java-runner.jar"]