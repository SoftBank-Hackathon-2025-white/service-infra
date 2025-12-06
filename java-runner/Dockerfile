FROM maven:3.9.6-eclipse-temurin-17 AS build
WORKDIR /app

COPY pom.xml .
COPY src ./src

RUN mvn -q package -DskipTests

FROM eclipse-temurin:17-jre
WORKDIR /runner

COPY --from=build /app/target/java-runner-1.0.0.jar app.jar

EXPOSE 8090

ENTRYPOINT ["java", "-jar", "app.jar"]