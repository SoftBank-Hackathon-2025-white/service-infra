FROM openjdk:17-slim       

WORKDIR /app

COPY pom.xml .
COPY src ./src

RUN mvn -q package -DskipTests

FROM eclipse-temurin:17-jre

WORKDIR /runner

# fat-jar 복사
COPY --from=build /app/target/java-runner-1.0.0-jar-with-dependencies.jar /runner/java-runner.jar

EXPOSE 8090

CMD ["java", "-jar", "/runner/java-runner.jar"]