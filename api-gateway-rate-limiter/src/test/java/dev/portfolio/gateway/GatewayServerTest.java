package dev.portfolio.gateway;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class GatewayServerTest {
    @TempDir Path directory;

    @Test void forwardsAuthAndEnforcesBurstQuota() throws Exception {
        HttpServer backend = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 4);
        backend.createContext("/", exchange -> {
            String authorization = exchange.getRequestHeaders().getFirst("Authorization");
            byte[] body = (authorization == null ? "missing" : authorization).getBytes(java.nio.charset.StandardCharsets.UTF_8);
            exchange.sendResponseHeaders(200, body.length);
            exchange.getResponseBody().write(body);
            exchange.close();
        });
        backend.start();
        Route route = new Route("GET", "/api", URI.create("http://127.0.0.1:" + backend.getAddress().getPort()), 1, 60_000);
        try (GatewayServer gateway = new GatewayServer(new InetSocketAddress("127.0.0.1", 0), java.util.List.of(route), new QuotaStore(directory.resolve("gateway.sqlite").toString()))) {
            gateway.start();
            HttpClient client = HttpClient.newHttpClient();
            URI uri = URI.create("http://127.0.0.1:" + gateway.port() + "/api/check");
            HttpRequest request = HttpRequest.newBuilder(uri).header("Authorization", "Bearer fixture").GET().build();
            HttpResponse<String> first = client.send(request, HttpResponse.BodyHandlers.ofString());
            HttpResponse<String> second = client.send(request, HttpResponse.BodyHandlers.ofString());
            assertEquals(200, first.statusCode());
            assertEquals("Bearer fixture", first.body());
            assertEquals(429, second.statusCode());
        } finally {
            backend.stop(0);
        }
    }

    @Test void rejectsUnsafeRouteAndCredentialBearingUpstream() {
        assertThrows(IllegalArgumentException.class, () -> new Route("GET", "/../private", URI.create("http://localhost"), 1, 1000));
        assertThrows(IllegalArgumentException.class, () -> new Route("GET", "/api", URI.create("http://user:pass@localhost"), 1, 1000));
    }

    @Test void returnsBadGatewayWhenUpstreamIsUnavailable() throws Exception {
        Route route = new Route("GET", "/api", URI.create("http://127.0.0.1:1"), 10, 60_000);
        try (GatewayServer gateway = new GatewayServer(new InetSocketAddress("127.0.0.1", 0), java.util.List.of(route), new QuotaStore(directory.resolve("failed-upstream.sqlite").toString()))) {
            gateway.start();
            HttpRequest request = HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + gateway.port() + "/api/check")).GET().build();
            HttpResponse<String> response = HttpClient.newHttpClient().send(request, HttpResponse.BodyHandlers.ofString());
            assertEquals(502, response.statusCode());
        }
    }
}
