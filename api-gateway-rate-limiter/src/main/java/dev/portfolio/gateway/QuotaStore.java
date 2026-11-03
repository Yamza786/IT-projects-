package dev.portfolio.gateway;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;
import java.util.Objects;

public final class QuotaStore {
    private final String jdbcUrl;

    public QuotaStore(String databasePath) throws SQLException {
        Objects.requireNonNull(databasePath, "databasePath");
        java.nio.file.Path file = java.nio.file.Path.of(databasePath).toAbsolutePath().normalize();
        try {
            java.nio.file.Files.createDirectories(file.getParent());
            if (!System.getProperty("os.name", "").toLowerCase(java.util.Locale.ROOT).contains("win")) {
                java.nio.file.Files.setPosixFilePermissions(file.getParent(), java.nio.file.attribute.PosixFilePermissions.fromString("rwx------"));
            }
        } catch (java.io.IOException | UnsupportedOperationException exception) {
            throw new SQLException("cannot prepare private database directory", exception);
        }
        jdbcUrl = "jdbc:sqlite:" + file;
        try (Connection connection = open(); var statement = connection.createStatement()) {
            statement.execute("PRAGMA busy_timeout = 5000");
            statement.execute("CREATE TABLE IF NOT EXISTS quota_windows (client TEXT NOT NULL, route TEXT NOT NULL, window_start INTEGER NOT NULL, request_count INTEGER NOT NULL, PRIMARY KEY (client, route))");
            statement.execute("CREATE TABLE IF NOT EXISTS request_audit (id INTEGER PRIMARY KEY, occurred_at INTEGER NOT NULL, client TEXT NOT NULL, route TEXT NOT NULL, status INTEGER NOT NULL)");
        }
        try {
            if (!System.getProperty("os.name", "").toLowerCase(java.util.Locale.ROOT).contains("win")) {
                java.nio.file.Files.setPosixFilePermissions(file, java.nio.file.attribute.PosixFilePermissions.fromString("rw-------"));
            }
        } catch (java.io.IOException | UnsupportedOperationException exception) {
            throw new SQLException("cannot secure quota database permissions", exception);
        }
    }

    private Connection open() throws SQLException { return DriverManager.getConnection(jdbcUrl); }

    public synchronized boolean consume(String client, Route route, long now, int limit) throws SQLException {
        try (Connection connection = open()) {
            connection.setAutoCommit(false);
            try {
                try (var update = connection.prepareStatement("INSERT INTO quota_windows(client,route,window_start,request_count) VALUES(?,?,?,1) ON CONFLICT(client,route) DO UPDATE SET window_start=CASE WHEN quota_windows.window_start <= ? THEN excluded.window_start ELSE quota_windows.window_start END, request_count=CASE WHEN quota_windows.window_start <= ? THEN 1 ELSE quota_windows.request_count + 1 END")) {
                    update.setString(1, client);
                    update.setString(2, route.id());
                    update.setLong(3, now);
                    update.setLong(4, now - route.windowMillis());
                    update.setLong(5, now - route.windowMillis());
                    update.executeUpdate();
                }
                int count;
                try (var select = connection.prepareStatement("SELECT request_count FROM quota_windows WHERE client=? AND route=?")) {
                    select.setString(1, client);
                    select.setString(2, route.id());
                    try (var result = select.executeQuery()) { result.next(); count = result.getInt(1); }
                }
                connection.commit();
                return count <= limit;
            } catch (SQLException exception) {
                connection.rollback();
                throw exception;
            }
        }
    }

    public synchronized void audit(long now, String client, Route route, int status) throws SQLException {
        try (Connection connection = open(); var insert = connection.prepareStatement("INSERT INTO request_audit(occurred_at,client,route,status) VALUES(?,?,?,?)")) {
            insert.setLong(1, now);
            insert.setString(2, client);
            insert.setString(3, route.id());
            insert.setInt(4, status);
            insert.executeUpdate();
        }
    }
}
