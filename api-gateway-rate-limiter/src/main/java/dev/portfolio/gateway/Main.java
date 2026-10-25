package dev.portfolio.gateway;

import java.net.InetSocketAddress;
import java.net.URI;
import java.sql.SQLException;
import java.util.List;

public final class Main {
    private Main() {}

    public static void main(String[] args) throws Exception {
        int port = integerEnv("GATEWAY_PORT", 8080, 1, 65535);
        int limit = integerEnv("GATEWAY_RATE_LIMIT", 60, 1, 1_000_000);
        long window = integerEnv("GATEWAY_WINDOW_SECONDS", 60, 1, 86_400) * 1000L;
        String upstream = System.getenv().getOrDefault("GATEWAY_UPSTREAM", "http://127.0.0.1:8081");
        String prefix = System.getenv().getOrDefault("GATEWAY_PREFIX", "/api");
        String database = System.getenv().getOrDefault("GATEWAY_DATABASE", "data/gateway.sqlite");
        Route route = new Route("*", prefix, URI.create(upstream), limit, window);
        QuotaStore store = new QuotaStore(database);
        GatewayServer gateway = new GatewayServer(new InetSocketAddress("127.0.0.1", port), List.of(route), store);
        Runtime.getRuntime().addShutdownHook(new Thread(gateway::close));
        gateway.start();
        System.out.printf("gateway listening on 127.0.0.1:%d; route %s -> %s%n", gateway.port(), route.id(), route.upstream());
        Thread.currentThread().join();
    }

    private static int integerEnv(String key, int fallback, int minimum, int maximum) {
        String value = System.getenv(key);
        if (value == null || value.isBlank()) return fallback;
        try {
            int parsed = Integer.parseInt(value);
            if (parsed < minimum || parsed > maximum) throw new IllegalArgumentException(key + " is outside its allowed range");
            return parsed;
        } catch (NumberFormatException exception) {
            throw new IllegalArgumentException(key + " must be an integer", exception);
        }
    }
}
