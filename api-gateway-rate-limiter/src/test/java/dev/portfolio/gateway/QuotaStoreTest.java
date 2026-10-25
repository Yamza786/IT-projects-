package dev.portfolio.gateway;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.net.URI;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class QuotaStoreTest {
    @TempDir Path directory;

    @Test void enforcesIndependentClientWindowsAndExpiresQuota() throws Exception {
        QuotaStore store = new QuotaStore(directory.resolve("quota.sqlite").toString());
        Route route = new Route("GET", "/api", URI.create("http://localhost:8081"), 2, 1_000);
        assertTrue(store.consume("client-a", route, 10_000, 2));
        assertTrue(store.consume("client-a", route, 10_500, 2));
        assertFalse(store.consume("client-a", route, 10_600, 2));
        assertTrue(store.consume("client-b", route, 10_600, 2));
        assertTrue(store.consume("client-a", route, 11_001, 2));
    }
}
