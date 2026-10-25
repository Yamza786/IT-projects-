package dev.portfolio.filesync;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.security.MessageDigest;
import java.sql.SQLException;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.Executors;

public final class FileSyncServer implements AutoCloseable {
    private static final int MAX_REQUEST_BYTES = FileStore.CHUNK_BYTES;
    private final HttpServer server;
    private final FileStore store;
    private final Map<String, String> ownerTokens;
    private final java.util.concurrent.ExecutorService executor = Executors.newFixedThreadPool(8);

    public FileSyncServer(InetSocketAddress address, FileStore store, Map<String, String> ownerTokens) throws IOException {
        if (ownerTokens == null || ownerTokens.isEmpty()) throw new IllegalArgumentException("at least one owner token is required");
        ownerTokens.forEach((owner, token) -> {
            if (!owner.matches("[A-Za-z0-9._-]{1,64}") || token.length() < 32) throw new IllegalArgumentException("owners need safe IDs and tokens of at least 32 characters");
        });
        this.ownerTokens = Map.copyOf(ownerTokens);
        this.store = store;
        server = HttpServer.create(address, 64);
        server.createContext("/", this::handle);
        server.setExecutor(executor);
    }

    public void start() { server.start(); }
    public int port() { return server.getAddress().getPort(); }

    private void handle(HttpExchange exchange) throws IOException {
        exchange.getResponseHeaders().set("Cache-Control", "no-store");
        exchange.getResponseHeaders().set("X-Content-Type-Options", "nosniff");
        String method = exchange.getRequestMethod();
        String path = exchange.getRequestURI().getRawPath();
        if (method.equals("GET") && path.equals("/health")) { json(exchange, 200, "{\"status\":\"ok\"}"); return; }
        try {
            String owner = authenticate(exchange);
            if (method.equals("POST") && path.equals("/uploads")) {
                Map<String, String> query = query(exchange.getRequestURI().getRawQuery());
                String name = require(query, "name");
                long size = Long.parseLong(require(query, "size"));
                int chunks = Integer.parseInt(require(query, "chunks"));
                String hash = require(query, "sha256");
                String base = query.get("baseVersion");
                Integer baseVersion = base == null || base.isBlank() ? null : Integer.valueOf(base);
                FileStore.Upload upload = store.beginUpload(owner, name, size, chunks, hash, baseVersion);
                json(exchange, 201, uploadJson(upload)); return;
            }
            if (method.equals("GET") && path.matches("/uploads/[0-9a-fA-F-]{36}")) {
                FileStore.Upload upload = store.status(path.substring("/uploads/".length()), owner);
                json(exchange, 200, uploadJson(upload)); return;
            }
            if (method.equals("DELETE") && path.matches("/uploads/[0-9a-fA-F-]{36}")) {
                store.cancel(path.substring("/uploads/".length()), owner); json(exchange, 200, "{\"canceled\":true}"); return;
            }
            if (method.equals("POST") && path.matches("/uploads/[0-9a-fA-F-]{36}/complete")) {
                String id = path.substring("/uploads/".length(), path.length() - "/complete".length());
                FileStore.ObjectInfo object = store.complete(id, owner);
                json(exchange, 201, objectJson(object)); return;
            }
            if (method.equals("PUT") && path.matches("/uploads/[0-9a-fA-F-]{36}/chunks/[0-9]{1,3}")) {
                String[] parts = path.split("/");
                byte[] bytes = exchange.getRequestBody().readNBytes(MAX_REQUEST_BYTES + 1);
                if (bytes.length > MAX_REQUEST_BYTES) { json(exchange, 413, "{\"error\":\"chunk exceeds 1 MiB\"}"); return; }
                store.putChunk(parts[2], owner, Integer.parseInt(parts[4]), bytes);
                json(exchange, 201, "{\"stored\":true}"); return;
            }
            if (method.equals("GET") && path.equals("/files")) {
                List<FileStore.ObjectInfo> files = store.list(owner);
                json(exchange, 200, "{\"files\":[" + String.join(",", files.stream().map(FileSyncServer::objectJson).toList()) + "]}"); return;
            }
            if (method.equals("GET") && path.startsWith("/files/")) {
                String name = path.substring("/files/".length());
                if (name.contains("/") || name.contains("%")) { json(exchange, 400, "{\"error\":\"invalid filename path\"}"); return; }
                var file = store.download(owner, name);
                long size = Files.size(file);
                exchange.getResponseHeaders().set("Content-Type", "application/octet-stream");
                exchange.getResponseHeaders().set("Content-Disposition", "attachment; filename=\"" + name + "\"");
                exchange.sendResponseHeaders(200, size);
                try (var input = Files.newInputStream(file); var output = exchange.getResponseBody()) { input.transferTo(output); }
                return;
            }
            json(exchange, 404, "{\"error\":\"route not found\"}");
        } catch (IllegalArgumentException exception) {
            json(exchange, 400, errorJson(exception.getMessage()));
        } catch (IllegalStateException exception) {
            json(exchange, 409, errorJson(exception.getMessage()));
        } catch (RequestComplete ignored) {
            // The authentication helper already sent the response.
        } catch (SQLException | IOException exception) {
            json(exchange, 500, "{\"error\":\"storage operation failed\"}");
        } finally { exchange.close(); }
    }

    private String authenticate(HttpExchange exchange) throws IOException {
        String header = exchange.getRequestHeaders().getFirst("Authorization");
        if (header == null || !header.startsWith("Bearer ") || header.length() > 263) { json(exchange, 401, "{\"error\":\"bearer token required\"}"); throw new RequestComplete(); }
        byte[] provided = header.substring(7).getBytes(StandardCharsets.UTF_8);
        for (var entry : ownerTokens.entrySet()) {
            if (MessageDigest.isEqual(provided, entry.getValue().getBytes(StandardCharsets.UTF_8))) return entry.getKey();
        }
        json(exchange, 401, "{\"error\":\"invalid bearer token\"}"); throw new RequestComplete();
    }

    private static final class RequestComplete extends RuntimeException { private static final long serialVersionUID = 1L; }

    private static Map<String, String> query(String raw) {
        Map<String, String> result = new HashMap<>();
        if (raw == null || raw.length() > 4096) throw new IllegalArgumentException("query string is missing or too long");
        for (String pair : raw.split("&")) {
            String[] values = pair.split("=", 2);
            String key = java.net.URLDecoder.decode(values[0], StandardCharsets.UTF_8);
            String value = values.length == 2 ? java.net.URLDecoder.decode(values[1], StandardCharsets.UTF_8) : "";
            if (result.putIfAbsent(key, value) != null) throw new IllegalArgumentException("duplicate query parameter");
        }
        return result;
    }

    private static String require(Map<String, String> values, String key) {
        String value = values.get(key);
        if (value == null || value.isBlank()) throw new IllegalArgumentException("missing query parameter: " + key);
        return value;
    }

    private static String uploadJson(FileStore.Upload upload) {
        return "{\"id\":" + quote(upload.id()) + ",\"chunkCount\":" + upload.chunkCount() + ",\"missingChunks\":" + upload.missingChunks() + "}";
    }

    private static String objectJson(FileStore.ObjectInfo object) {
        return "{\"name\":" + quote(object.name()) + ",\"size\":" + object.size() + ",\"sha256\":" + quote(object.sha256()) + ",\"version\":" + object.version() + ",\"updatedAt\":" + quote(object.updatedAt()) + "}";
    }

    private static String quote(String value) {
        return "\"" + value.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n").replace("\r", "\\r") + "\"";
    }

    private static String errorJson(String message) { return "{\"error\":" + quote(message == null ? "request failed" : message) + "}"; }

    private static void json(HttpExchange exchange, int status, String body) throws IOException {
        byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().set("Content-Type", "application/json; charset=utf-8");
        exchange.sendResponseHeaders(status, bytes.length);
        exchange.getResponseBody().write(bytes);
    }

    @Override public void close() { server.stop(0); executor.shutdownNow(); }
}
