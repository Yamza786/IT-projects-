package dev.portfolio.schemaguard;

import java.io.IOException;
import java.nio.file.Path;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

final class MigrationRunner {
    private final Connection connection;
    private final Path migrationDirectory;

    MigrationRunner(Connection connection, Path migrationDirectory) {
        this.connection = connection;
        this.migrationDirectory = migrationDirectory;
    }

    List<Migration> validate() throws IOException, SQLException {
        List<Migration> migrations = MigrationRepository.load(migrationDirectory);
        Map<Integer, String> applied = appliedVersions();
        String expectedSchema = readExpectedSchema();
        String actualSchema = currentSchemaFingerprint();
        if (!expectedSchema.equals(actualSchema)) {
            throw new IllegalStateException("Database schema drift detected; inspect sqlite_master before continuing");
        }
        Map<Integer, Migration> available = new HashMap<>();
        migrations.forEach(migration -> available.put(migration.version(), migration));
        for (Map.Entry<Integer, String> entry : applied.entrySet()) {
            Migration migration = available.get(entry.getKey());
            if (migration == null) {
                throw new IllegalStateException("Applied migration V%04d is missing from disk".formatted(entry.getKey()));
            }
            if (!migration.checksum().equals(entry.getValue())) {
                throw new IllegalStateException("Checksum drift in %s; applied migrations are immutable"
                        .formatted(migration.displayName()));
            }
        }
        int expected = 1;
        for (int version : applied.keySet().stream().sorted().toList()) {
            if (version != expected++) throw new IllegalStateException("Database migration history has a version gap");
        }
        return migrations;
    }

    List<String> status() throws IOException, SQLException {
        List<Migration> migrations = validate();
        Map<Integer, String> applied = appliedVersions();
        List<String> rows = new ArrayList<>();
        for (Migration migration : migrations) {
            rows.add("%s  %s  %s".formatted(
                    migration.displayName(),
                    applied.containsKey(migration.version()) ? "APPLIED" : "PENDING",
                    migration.checksum().substring(0, 12)));
        }
        if (rows.isEmpty()) rows.add("No migrations found.");
        return List.copyOf(rows);
    }

    List<String> plan() throws IOException, SQLException {
        List<Migration> migrations = validate();
        Map<Integer, String> applied = appliedVersions();
        List<String> actions = new ArrayList<>();
        for (Migration migration : migrations) {
            if (!applied.containsKey(migration.version()))
                actions.add("APPLY " + migration.displayName());
        }
        int latestApplied = applied.keySet().stream().mapToInt(Integer::intValue).max().orElse(0);
        if (latestApplied > 0) {
            Migration latest = migrations.stream().filter(item -> item.version() == latestApplied).findFirst()
                    .orElseThrow(() -> new IllegalStateException("Applied migration is not available: " + latestApplied));
            actions.add("ROLLBACK CANDIDATE " + latest.displayName() + " (latest applied only)");
        }
        if (actions.isEmpty()) actions.add("No forward migrations or rollback candidates.");
        return List.copyOf(actions);
    }

    int migrateUp() throws IOException, SQLException {
        List<Migration> migrations = validate();
        Map<Integer, String> applied = appliedVersions();
        int count = 0;
        for (Migration migration : migrations) {
            if (applied.containsKey(migration.version())) continue;
            inTransaction(() -> {
                executeScript(migration.upSql());
                try (PreparedStatement insert = connection.prepareStatement(
                        "INSERT INTO schema_history(version, name, checksum) VALUES (?, ?, ?)")) {
                    insert.setInt(1, migration.version());
                    insert.setString(2, migration.name());
                    insert.setString(3, migration.checksum());
                    insert.executeUpdate();
                }
                writeExpectedSchema(currentSchemaFingerprint());
            });
            count++;
            System.out.println("Applied " + migration.displayName());
        }
        return count;
    }

    boolean rollbackOne() throws IOException, SQLException {
        List<Migration> migrations = validate();
        Map<Integer, String> applied = appliedVersions();
        if (applied.isEmpty()) return false;

        int version = applied.keySet().stream().mapToInt(Integer::intValue).max().orElseThrow();
        Migration migration = migrations.stream().filter(item -> item.version() == version).findFirst()
                .orElseThrow(() -> new IllegalStateException("Applied migration is not available: " + version));
        inTransaction(() -> {
            executeScript(migration.downSql());
            try (PreparedStatement delete = connection.prepareStatement("DELETE FROM schema_history WHERE version = ?")) {
                delete.setInt(1, version);
                delete.executeUpdate();
            }
            writeExpectedSchema(currentSchemaFingerprint());
        });
        System.out.println("Rolled back " + migration.displayName());
        return true;
    }

    private Map<Integer, String> appliedVersions() throws SQLException {
        Map<Integer, String> applied = new HashMap<>();
        try (Statement statement = connection.createStatement()) {
            statement.execute("CREATE TABLE IF NOT EXISTS schema_history ("
                    + "version INTEGER PRIMARY KEY, name TEXT NOT NULL, checksum TEXT NOT NULL, "
                    + "applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)");
            statement.execute("CREATE TABLE IF NOT EXISTS schema_guard_state ("
                    + "singleton INTEGER PRIMARY KEY CHECK(singleton = 1), schema_fingerprint TEXT NOT NULL)");
        }
        try (Statement statement = connection.createStatement();
             ResultSet result = statement.executeQuery("SELECT version, checksum FROM schema_history")) {
            while (result.next()) applied.put(result.getInt(1), result.getString(2));
        }
        boolean hasSchemaState;
        try (Statement statement = connection.createStatement();
             ResultSet result = statement.executeQuery("SELECT schema_fingerprint FROM schema_guard_state WHERE singleton = 1")) {
            hasSchemaState = result.next();
        }
        if (!hasSchemaState) writeExpectedSchema(currentSchemaFingerprint());
        return applied;
    }

    private String readExpectedSchema() throws SQLException {
        try (Statement statement = connection.createStatement();
             ResultSet result = statement.executeQuery("SELECT schema_fingerprint FROM schema_guard_state WHERE singleton = 1")) {
            if (!result.next()) throw new IllegalStateException("Schema fingerprint state is missing");
            return result.getString(1);
        }
    }

    private void writeExpectedSchema(String fingerprint) throws SQLException {
        try (PreparedStatement statement = connection.prepareStatement(
                "INSERT INTO schema_guard_state(singleton, schema_fingerprint) VALUES (1, ?) "
                        + "ON CONFLICT(singleton) DO UPDATE SET schema_fingerprint = excluded.schema_fingerprint")) {
            statement.setString(1, fingerprint);
            statement.executeUpdate();
        }
    }

    private String currentSchemaFingerprint() throws SQLException {
        StringBuilder schema = new StringBuilder();
        try (Statement statement = connection.createStatement();
             ResultSet result = statement.executeQuery("SELECT type, name, tbl_name, COALESCE(sql, '') "
                     + "FROM sqlite_master WHERE name NOT GLOB 'sqlite_*' "
                     + "AND name NOT IN ('schema_history', 'schema_guard_state') ORDER BY type, name")) {
            while (result.next()) {
                schema.append(result.getString(1)).append('\0')
                        .append(result.getString(2)).append('\0')
                        .append(result.getString(3)).append('\0')
                        .append(result.getString(4)).append('\n');
            }
        }
        try {
            byte[] hash = MessageDigest.getInstance("SHA-256").digest(schema.toString().getBytes(StandardCharsets.UTF_8));
            return java.util.HexFormat.of().formatHex(hash);
        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException("SHA-256 is required by the Java runtime", exception);
        }
    }

    private void executeScript(String sql) throws SQLException {
        try (Statement statement = connection.createStatement()) {
            for (String command : SqlScript.statements(sql)) statement.execute(command);
        }
    }

    private void inTransaction(SqlWork work) throws SQLException {
        boolean previousAutoCommit = connection.getAutoCommit();
        connection.setAutoCommit(false);
        try {
            work.run();
            connection.commit();
        } catch (SQLException | RuntimeException exception) {
            connection.rollback();
            throw exception;
        } finally {
            connection.setAutoCommit(previousAutoCommit);
        }
    }

    @FunctionalInterface
    private interface SqlWork {
        void run() throws SQLException;
    }
}
