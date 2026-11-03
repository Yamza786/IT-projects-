package dev.portfolio.filesync;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.net.InetSocketAddress;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class FileSyncServerTest {
    @TempDir Path directory;

    @Test void servesOwnerScopedResumableUploadAndDownloadApi() throws Exception {
        byte[] data = "from http".getBytes(StandardCharsets.UTF_8);
        String token = "alice-local-test-token-0123456789abcdef";
        FileStore store = new FileStore(directory.resolve("files"), directory.resolve("metadata.sqlite"));
        try (FileSyncServer server = new FileSyncServer(new InetSocketAddress("127.0.0.1", 0), store, Map.of("alice", token))) {
            server.start();
            HttpClient client = HttpClient.newHttpClient();
            URI base = URI.create("http://127.0.0.1:" + server.port());
            HttpResponse<String> unauthorized = client.send(HttpRequest.newBuilder(base.resolve("/files")).GET().build(), HttpResponse.BodyHandlers.ofString());
            assertEquals(401, unauthorized.statusCode());
            String query = "name=api.txt&size=" + data.length + "&chunks=1&sha256=" + FileStore.sha256(data);
            HttpRequest begin = HttpRequest.newBuilder(base.resolve("/uploads?" + query)).header("Authorization", "Bearer " + token).POST(HttpRequest.BodyPublishers.noBody()).build();
            HttpResponse<String> created = client.send(begin, HttpResponse.BodyHandlers.ofString());
            assertEquals(201, created.statusCode());
            String uploadId = created.body().replaceAll(".*\\\"id\\\":\\\"([^\\\"]+)\\\".*", "$1");
            HttpRequest put = HttpRequest.newBuilder(base.resolve("/uploads/" + uploadId + "/chunks/0")).header("Authorization", "Bearer " + token).PUT(HttpRequest.BodyPublishers.ofByteArray(data)).build();
            assertEquals(201, client.send(put, HttpResponse.BodyHandlers.ofString()).statusCode());
            HttpRequest complete = HttpRequest.newBuilder(base.resolve("/uploads/" + uploadId + "/complete")).header("Authorization", "Bearer " + token).POST(HttpRequest.BodyPublishers.noBody()).build();
            assertTrue(client.send(complete, HttpResponse.BodyHandlers.ofString()).body().contains("\"version\":1"));
            HttpRequest download = HttpRequest.newBuilder(base.resolve("/files/api.txt")).header("Authorization", "Bearer " + token).GET().build();
            assertEquals("from http", client.send(download, HttpResponse.BodyHandlers.ofString()).body());
        }
    }
}
