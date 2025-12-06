FROM amazoncorretto:17

WORKDIR /runner

# Install necessary tools
RUN yum install -y unzip wget

COPY target/java-runner.jar /runner/java-runner.jar

EXPOSE 8090

CMD ["java", "-jar", "java-runner.jar"]