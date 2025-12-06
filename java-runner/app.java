import com.sun.net.httpserver.HttpServer;
import com.sun.net.httpserver.HttpExchange;

import java.io.*;
import java.net.InetSocketAddress;
import java.net.URI;
import java.nio.file.Files;
import java.util.*;
import java.util.concurrent.Executors;

import software.amazon.awssdk.auth.credentials.EnvironmentVariableCredentialsProvider;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.s3.*;
import software.amazon.awssdk.services.s3.model.*;

import org.json.JSONObject;

public class App {

    private static final String CODE_BUCKET = System.getenv("CODE_BUCKET");
    private static final String LOG_BUCKET = System.getenv("LOG_BUCKET");
    private static final String AWS_REGION = System.getenv("AWS_REGION");

    private static final S3Client s3 = S3Client.builder()
            .region(Region.of(AWS_REGION))
            .credentialsProvider(EnvironmentVariableCredentialsProvider.create())
            .build();

    public static void main(String[] args) throws Exception {
        HttpServer server = HttpServer.create(new InetSocketAddress(8080), 0);

        server.createContext("/health", App::healthCheck);
        server.createContext("/java/run", App::runJavaCode);

        server.setExecutor(Executors.newFixedThreadPool(4));
        System.out.println("🚀 Java Runner started on port 8080");
        server.start();
    }

    private static void healthCheck(HttpExchange exchange) throws IOException {
        sendJson(exchange, new JSONObject().put("status", "JAVA RUNNER READY"));
    }

    private static void runJavaCode(HttpExchange exchange) throws IOException {
        URI requestURI = exchange.getRequestURI();
        Map<String, String> params = queryToMap(requestURI.getQuery());

        String codeKey = params.get("code_key");
        if (codeKey == null) {
            sendJson(exchange, new JSONObject().put("error", "Missing code_key"), 400);
            return;
        }

        try {
            String downloadedPath = downloadCode(CODE_BUCKET, codeKey);
            String className = "Main";

            long start = System.currentTimeMillis();

            // Compile
            Process compile = new ProcessBuilder("javac", downloadedPath).start();
            compile.waitFor();

            // Run
            Process run = new ProcessBuilder("java", "-cp", "/runner", className)
                    .redirectErrorStream(true)
                    .start();

            BufferedReader reader = new BufferedReader(new InputStreamReader(run.getInputStream()));
            StringBuilder output = new StringBuilder();
            String line;

            while ((line = reader.readLine()) != null)
                output.append(line).append("\n");

            int exitCode = run.waitFor();

            long end = System.currentTimeMillis();

            JSONObject result = new JSONObject();
            result.put("stdout", output.toString());
            result.put("stderr", exitCode == 0 ? "" : "Runtime error");
            result.put("execution_time_ms", end - start);
            result.put("code_key", codeKey);

            String logKey = uploadLogJson(result);
            result.put("log_key", logKey);

            sendJson(exchange, result);

        } catch (Exception e) {
            sendJson(exchange, new JSONObject().put("error", e.getMessage()), 500);
        }
    }

    private static String downloadCode(String bucket, String key) throws IOException {
        String filename = key.substring(key.lastIndexOf("/") + 1);
        String localPath = "/runner/" + filename;

        GetObjectRequest request = GetObjectRequest.builder()
                .bucket(bucket)
                .key(key)
                .build();

        s3.getObject(request, java.nio.file.Paths.get(localPath));

        return localPath;
    }

    private static String uploadLogJson(JSONObject json) {
        String key = "logs/" + UUID.randomUUID() + ".json";

        PutObjectRequest put = PutObjectRequest.builder()
                .bucket(LOG_BUCKET)
                .key(key)
                .contentType("application/json")
                .build();

        s3.putObject(put, RequestBody.fromString(json.toString(2)));

        return key;
    }

    private static void sendJson(HttpExchange exchange, JSONObject json) throws IOException {
        sendJson(exchange, json, 200);
    }

    private static void sendJson(HttpExchange exchange, JSONObject json, int status) throws IOException {
        byte[] bytes = json.toString().getBytes();
        exchange.sendResponseHeaders(status, bytes.length);
        exchange.getResponseBody().write(bytes);
        exchange.getResponseBody().close();
    }

    private static Map<String, String> queryToMap(String query) {
        Map<String, String> map = new HashMap<>();
        if (query == null)
            return map;

        for (String param : query.split("&")) {
            String[] pair = param.split("=");
            if (pair.length > 1)
                map.put(pair[0], pair[1]);
        }

        return map;
    }
}