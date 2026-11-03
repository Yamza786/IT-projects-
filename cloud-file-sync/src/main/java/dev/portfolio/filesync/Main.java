package dev.portfolio.filesync;

import java.net.InetSocketAddress;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.Map;

public final class Main {
    private Main() { }

    public static void main(String[] args) throws Exception {
        if (args.length != 0) throw new IllegalArgumentException("this service has no command-line arguments");
        String configured = System.getenv("FILESYNC_TOKENS");
        if (configured == null || configured.isBlank()) throw new IllegalArgumentException("FILESYNC_TOKENS must map owner IDs to private tokens");
        Map<String, String> tokens = new HashMap<>();
        for (String pair : configured.split(",")) {
            String[] values = pair.split("=", 2);
            if (values.length != 2 || tokens.putIfAbsent(values[0], values[1]) != null) throw new IllegalArgumentException("FILESYNC_TOKENS must use unique owner:token pairs");
        }
        int port = integerEnv("FILESYNC_PORT", 8082, 1, 65535);
        Path root = Path.of(System.getenv().getOrDefault("FILESYNC_ROOT", "data/file-sync"));
        Path database = Path.of(System.getenv().getOrDefault("FILESYNC_DATABASE", root.resolve("metadata.sqlite").toString()));
        FileStore store = new FileStore(root, database);
        FileSyncServer server = new FileSyncServer(new InetSocketAddress("127.0.0.1", port), store, tokens);
        Runtime.getRuntime().addShutdownHook(new Thread(server::close));
        server.start();
        System.out.printf("file sync API listening on 127.0.0.1:%d%n", server.port());
        Thread.currentThread().join();
    }

    private static int integerEnv(String key, int fallback, int minimum, int maximum) {
        String value = System.getenv(key);
        if (value == null || value.isBlank()) return fallback;
        try {
            int parsed = Integer.parseInt(value);
            if (parsed < minimum || parsed > maximum) throw new IllegalArgumentException(key + " is outside its allowed range");
            return parsed;
        } catch (NumberFormatException exception) { throw new IllegalArgumentException(key + " must be an integer", exception); }
    }
}
