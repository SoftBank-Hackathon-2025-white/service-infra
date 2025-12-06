package runner;

import com.sun.net.httpserver.HttpServer;
import com.sun.net.httpserver.HttpExchange;

import java.io.*;
import java.net.InetSocketAddress;
import java.net.URI;
import java.nio.file.Files;
import java.util.*;
import java.util.concurrent.Executors;

import software.amazon.awssdk.services.s3.*;
import software.amazon.awssdk.services.s3.model.*;
import software.amazon.awssdk.core.sync.RequestBody;
import software.amazon.awssdk.regions.Region;

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
        URI uri = exchange.getRequestURI();
        Map<String, String> params = queryToMap(uri.getQuery());

        String codeKey = params.get("code_key");
        if (codeKey == null) {
            sendJson(exchange, new JSONObject().put("error", "Missing code_key"), 400);
            return;
        }

        JSONObject json = new JSONObject();
        long startTime = System.currentTimeMillis();

        try {
            // 랜덤 파일명 생성
            String tempBase = "Main_" + UUID.randomUUID();
            String tempJavaFile = "/runner/" + tempBase + ".java";
            String tempClassName = tempBase;
            String tempClassFile = "/runner/" + tempClassName + ".class";

            downloadCode(CODE_BUCKET, codeKey, tempJavaFile);

            // CPU/Memory: 시작 시점 측정
            long cpuStart = readCpuStat();
            long memBefore = readMemoryUsageMB();

            // compile
            Process compile = new ProcessBuilder("javac", tempJavaFile).start();
            compile.waitFor();

            // run
            Process run = new ProcessBuilder("java", "-cp", "/runner", tempClassName)
                    .redirectErrorStream(true)
                    .start();

            BufferedReader br = new BufferedReader(new InputStreamReader(run.getInputStream()));
            StringBuilder output = new StringBuilder();
            String line;
            while ((line = br.readLine()) != null)
                output.append(line).append("\n");

            int exitCode = run.waitFor();
            long endTime = System.currentTimeMillis();

            // CPU/Memory: 종료 시점 측정
            long cpuEnd = readCpuStat();
            double cpuPercent = calculateCpuPercent(cpuStart, cpuEnd, endTime - startTime);
            long memAfter = readMemoryUsageMB();

            json.put("stdout", output.toString());
            json.put("stderr", exitCode == 0 ? "" : "Runtime error");
            json.put("execution_time_ms", endTime - startTime);
            json.put("cpu_percent", cpuPercent);
            json.put("memory_mb", memAfter);
            json.put("code_key", codeKey);

            // 로그 저장
            String logKey = uploadLogJson(json);
            json.put("log_key", logKey);

            // temp 파일 삭제
            tryDelete(tempJavaFile);
            tryDelete(tempClassFile);

            sendJson(exchange, json);

        } catch (Exception e) {
            json.put("error", e.getMessage());
            sendJson(exchange, json, 500);
        }
    }

    private static long readCpuStat() {
        try {
            BufferedReader reader = new BufferedReader(new FileReader("/proc/stat"));
            String line = reader.readLine(); // 첫 번째 줄: cpu ...
            reader.close();
            String[] parts = line.split("\\s+");
            long user = Long.parseLong(parts[1]);
            long nice = Long.parseLong(parts[2]);
            long system = Long.parseLong(parts[3]);
            long idle = Long.parseLong(parts[4]);
            return user + nice + system + idle;
        } catch (Exception e) {
            return 0;
        }
    }

    private static double calculateCpuPercent(long start, long end, long elapsedMs) {
        if (elapsedMs <= 0)
            return 0.0;
        return (double) (end - start) / (elapsedMs * 100.0);
    }

    private static long readMemoryUsageMB() {
        try {
            BufferedReader reader = new BufferedReader(new FileReader("/proc/self/status"));
            String line;
            while ((line = reader.readLine()) != null) {
                if (line.startsWith("VmRSS:")) {
                    String[] parts = line.split("\\s+");
                    return Long.parseLong(parts[1]) / 1024; // kB → MB
                }
            }
            reader.close();
        } catch (Exception ignored) {
        }
        return 0;
    }

    private static void downloadCode(String bucket, String key, String localPath) {
        s3.getObject(
                GetObjectRequest.builder().bucket(bucket).key(key).build(),
                java.nio.file.Paths.get(localPath));
    }

    private static void tryDelete(String path) {
        try {
            Files.deleteIfExists(java.nio.file.Paths.get(path));
        } catch (Exception ignored) {
        }
    }

    private static String uploadLogJson(JSONObject json) {
        String key = "logs/" + UUID.randomUUID() + ".json";
        s3.putObject(
                PutObjectRequest.builder()
                        .bucket(LOG_BUCKET)
                        .key(key)
                        .contentType("application/json")
                        .build(),
                RequestBody.fromString(json.toString()));
        return key;
    }

    private static void sendJson(HttpExchange ex, JSONObject json) throws IOException {
        sendJson(ex, json, 200);
    }

    private static void sendJson(HttpExchange ex, JSONObject json, int status) throws IOException {
        byte[] data = json.toString().getBytes();
        ex.sendResponseHeaders(status, data.length);
        ex.getResponseBody().write(data);
        ex.getResponseBody().close();
    }

    private static Map<String, String> queryToMap(String query) {
        Map<String, String> map = new HashMap<>();
        if (query == null)
            return map;
        for (String p : query.split("&")) {
            String[] pair = p.split("=");
            if (pair.length > 1)
                map.put(pair[0], pair[1]);
        }
        return map;
    }
}