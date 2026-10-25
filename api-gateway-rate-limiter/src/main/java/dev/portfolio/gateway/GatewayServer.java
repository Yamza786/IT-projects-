package dev.portfolio.gateway;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.sql.SQLException;
import java.time.Duration;
import java.util.List;
import java.util.Set;

public final class GatewayServer implements AutoCloseable {
    private static final int MAX_REQUEST_BYTES = 1_048_576;
    private static final Set<String> HOP_HEADERS = Set.of("connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailer", "transfer-encoding", "upgrade", "host", "content-length");
    private final HttpServer server;
    private final List<Route> routes;
    private final QuotaStore store;
    private final java.util.concurrent.ExecutorService executor = java.util.concurrent.Executors.newFixedThreadPool(8);
    private final HttpClient client = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(2)).followRedirects(HttpClient.Redirect.NEVER).build();

    public GatewayServer(InetSocketAddress address, List<Route> routes, QuotaStore store) throws IOException {
        if (routes == null || routes.isEmpty()) throw new IllegalArgumentException("at least one route is required");
        this.routes = List.copyOf(routes);
        this.store = store;
        server = HttpServer.create(address, 64);
        server.createContext("/", this::handle);
        server.setExecutor(executor);
    }

    public void start() { server.start(); }
    public int port() { return server.getAddress().getPort(); }

    private void handle(HttpExchange exchange) throws IOException {
        long now = System.currentTimeMillis();
        String path = exchange.getRequestURI().getRawPath();
        Route route = routes.stream().filter(candidate -> candidate.matches(exchange.getRequestMethod(), path))
                .max(java.util.Comparator.comparingInt(candidate -> candidate.prefix().length())).orElse(null);
        if (route == null) { reply(exchange, 404, "route not configured\n"); return; }
        String identity = exchange.getRemoteAddress().getAddress().getHostAddress();
        int status = 502;
        try {
            if (!store.consume(identity, route, now, route.requestLimit())) {
                status = 429;
                exchange.getResponseHeaders().set("Retry-After", Long.toString(Math.max(1, route.windowMillis() / 1000)));
                reply(exchange, status, "rate limit exceeded\n");
                return;
            }
            byte[] body = exchange.getRequestBody().readNBytes(MAX_REQUEST_BYTES + 1);
            if (body.length > MAX_REQUEST_BYTES) { status = 413; reply(exchange, status, "request body too large\n"); return; }
            URI target = route.target(path, exchange.getRequestURI().getRawQuery());
            HttpRequest.Builder request = HttpRequest.newBuilder(target).timeout(Duration.ofSeconds(5));
            exchange.getRequestHeaders().forEach((name, values) -> {
                if (!HOP_HEADERS.contains(name.toLowerCase(java.util.Locale.ROOT))) {
                    values.forEach(value -> request.header(name, value));
                }
            });
            request.method(exchange.getRequestMethod(), body.length == 0 ? HttpRequest.BodyPublishers.noBody() : HttpRequest.BodyPublishers.ofByteArray(body));
            HttpResponse<byte[]> response = client.send(request.build(), HttpResponse.BodyHandlers.ofByteArray());
            status = response.statusCode();
            response.headers().map().forEach((name, values) -> {
                if (!HOP_HEADERS.contains(name.toLowerCase(java.util.Locale.ROOT))) values.forEach(value -> exchange.getResponseHeaders().add(name, value));
            });
            exchange.sendResponseHeaders(status, response.body().length);
            exchange.getResponseBody().write(response.body());
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            status = 502;
            reply(exchange, status, "upstream request interrupted\n");
        } catch (IOException | SQLException | IllegalArgumentException exception) {
            status = 502;
            reply(exchange, status, "gateway request failed\n");
        } finally {
            try { store.audit(now, identity, route, status); } catch (SQLException ignored) { /* request handling must not leak internal errors */ }
            exchange.close();
        }
    }

    private static void reply(HttpExchange exchange, int status, String body) throws IOException {
        byte[] bytes = body.getBytes(java.nio.charset.StandardCharsets.UTF_8);
        exchange.getResponseHeaders().set("Content-Type", "text/plain; charset=utf-8");
        exchange.getResponseHeaders().set("Cache-Control", "no-store");
        exchange.sendResponseHeaders(status, bytes.length);
        exchange.getResponseBody().write(bytes);
    }

    @Override public void close() { server.stop(0); executor.shutdownNow(); }
}
