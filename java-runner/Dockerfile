FROM amazoncorretto:17

WORKDIR /runner

# Install AWS SDK (Java) + JSON lib
RUN yum install -y unzip wget && \
    wget https://repo1.maven.org/maven2/org/json/json/20211205/json-20211205.jar -O /runner/json.jar && \
    wget https://repo1.maven.org/maven2/software/amazon/awssdk/bundle/2.20.40/bundle-2.20.40.jar -O /runner/aws.jar

COPY app.java /runner/app.java

# Compile main runner code
RUN javac -cp .:json.jar:aws.jar app.java

EXPOSE 8080

CMD ["java", "-cp", "/runner:json.jar:aws.jar", "App"]