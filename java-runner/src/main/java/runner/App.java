package runner;

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
import software.amazon.awssdk.core.sync.RequestBody;

import org.json.JSONObject;

public class App {

    private static final String CODE_BUCKET = System.getenv("CODE_BUCKET");
    private static final String LOG_BUCKET = System.getenv("LOG_BUCKET");
    private static final String AWS_REGION = System.getenv("AWS_REGION");

    private static final S3Client s3 = S3Client.builder()
            .region(Region.of(AWS_REGION))
            .build();

    public static void main(String[] args) throws Exception {
        HttpServer server = HttpServer.create(new InetSocketAddress(8090), 0);

        server.createContext("/health", App::healthCheck);
        server.createContext("/java/run", App::runJavaCode);

        server.setExecutor(Executors.newFixedThreadPool(4));
        System.out.println("🚀 Java Runner started on port 8090");

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
            String path = downloadCode(CODE_BUCKET, codeKey);

            String className = "Main";

            long start = System.currentTimeMillis();

            // compile
            Process compile = new ProcessBuilder("javac", path).start();
            compile.waitFor();

            // run
            Process run = new ProcessBuilder("java", "-cp", "/runner", className)
                    .redirectErrorStream(true)
                    .start();

            BufferedReader br = new BufferedReader(new InputStreamReader(run.getInputStream()));
            StringBuilder output = new StringBuilder();
            String line;

            while ((line = br.readLine()) != null) {
                output.append(line).append("\n");
            }

            int exitCode = run.waitFor();
            long end = System.currentTimeMillis();

            JSONObject result = new JSONObject();
            result.put("stdout", output.toString());
            result.put("stderr", exitCode == 0 ? "" : "Runtime error");
            result.put("execution_time_ms", (end - start));
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
        String path = "/runner/" + filename;

        GetObjectRequest req = GetObjectRequest.builder()
                .bucket(bucket)
                .key(key)
                .build();

        s3.getObject(req, java.nio.file.Paths.get(path));

        return path;
    }

    private static String uploadLogJson(JSONObject json) {
        String key = "logs/" + UUID.randomUUID() + ".json";

        PutObjectRequest put = PutObjectRequest.builder()
                .bucket(LOG_BUCKET)
                .key(key)
                .contentType("application/json")
                .build();

        s3.putObject(put, RequestBody.fromString(json.toString()));

        return key;
    }

    private static void sendJson(HttpExchange ex, JSONObject json) throws IOException {
        sendJson(ex, json, 200);
    }

    private static void sendJson(HttpExchange ex, JSONObject json, int status) throws IOException {
        byte[] response = json.toString().getBytes();
        ex.sendResponseHeaders(status, response.length);
        ex.getResponseBody().write(response);
        ex.getResponseBody().close();
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