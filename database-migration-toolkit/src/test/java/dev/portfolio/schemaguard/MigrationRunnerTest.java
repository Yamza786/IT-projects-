package dev.portfolio.schemaguard;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.DriverManager;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class MigrationRunnerTest {
    @TempDir Path temporaryDirectory;

    @Test
    void appliesMigrationsOnceAndReportsStatus() throws Exception {
        Path migrations = copyMigrations();
        try (var connection = DriverManager.getConnection("jdbc:sqlite::memory:")) {
            MigrationRunner runner = new MigrationRunner(connection, migrations);
            assertEquals(2, runner.migrateUp());
            assertEquals(0, runner.migrateUp());
            assertTrue(runner.status().get(0).contains("APPLIED"));
            try (var query = connection.createStatement().executeQuery("PRAGMA table_info(projects)")) {
                boolean statusColumnFound = false;
                while (query.next()) statusColumnFound |= "status".equals(query.getString("name"));
                assertTrue(statusColumnFound);
            }
        }
    }

    @Test
    void rollsBackExactlyTheLatestMigration() throws Exception {
        try (var connection = DriverManager.getConnection("jdbc:sqlite::memory:")) {
            MigrationRunner runner = new MigrationRunner(connection, copyMigrations());
            runner.migrateUp();
            assertTrue(runner.rollbackOne());
            assertFalse(runner.status().get(1).contains("APPLIED"));
            assertTrue(runner.rollbackOne());
            assertFalse(runner.rollbackOne());
        }
    }

    @Test
    void refusesChecksumDrift() throws Exception {
        Path migrations = copyMigrations();
        try (var connection = DriverManager.getConnection("jdbc:sqlite::memory:")) {
            MigrationRunner runner = new MigrationRunner(connection, migrations);
            runner.migrateUp();
            Path migration = migrations.resolve("V0001__create_projects.up.sql");
            Files.writeString(migration, Files.readString(migration) + "-- changed after apply\n");
            assertThrows(IllegalStateException.class, runner::status);
        }
    }

    @Test
    void refusesUntrackedDatabaseSchemaChanges() throws Exception {
        try (var connection = DriverManager.getConnection("jdbc:sqlite::memory:")) {
            MigrationRunner runner = new MigrationRunner(connection, copyMigrations());
            runner.migrateUp();
            try (var statement = connection.createStatement()) {
                statement.execute("CREATE TABLE manual_change(id INTEGER)");
            }
            assertThrows(IllegalStateException.class, runner::status);
        }
    }

    @Test
    void planIsReadOnlyAndShowsPendingMigrations() throws Exception {
        try (var connection = DriverManager.getConnection("jdbc:sqlite::memory:")) {
            MigrationRunner runner = new MigrationRunner(connection, copyMigrations());
            assertEquals(2, runner.plan().stream().filter(line -> line.startsWith("APPLY ")).count());
            assertEquals(0, runner.status().stream().filter(line -> line.contains("APPLIED")).count());
        }
    }

    @Test
    void rejectsMissingRollbackPair() throws Exception {
        Path migrations = Files.createDirectory(temporaryDirectory.resolve("incomplete"));
        Files.writeString(migrations.resolve("V0001__first.up.sql"), "CREATE TABLE sample(id INTEGER);");
        assertThrows(IOException.class, () -> MigrationRepository.load(migrations));
    }

    @Test
    void splitsOnlyAtUnquotedSemicolonsAndSkipsComments() {
        List<String> statements = SqlScript.statements(
                "-- heading\nINSERT INTO t(v) VALUES ('a;b'); /* c; */ SELECT \"x;y\";");
        assertEquals(2, statements.size());
        assertTrue(statements.get(0).contains("'a;b'"));
        assertTrue(statements.get(1).contains("\"x;y\""));
    }

    @Test
    void failedMigrationRollsBackItsSqlAndHistoryEntry() throws Exception {
        Path migrations = Files.createDirectory(temporaryDirectory.resolve("failure"));
        Files.writeString(migrations.resolve("V0001__broken.up.sql"),
                "CREATE TABLE should_rollback(id INTEGER); INSERT INTO missing_table VALUES (1);");
        Files.writeString(migrations.resolve("V0001__broken.down.sql"), "DROP TABLE should_rollback;");
        try (var connection = DriverManager.getConnection("jdbc:sqlite::memory:")) {
            MigrationRunner runner = new MigrationRunner(connection, migrations);
            assertThrows(java.sql.SQLException.class, runner::migrateUp);
            try (var query = connection.createStatement().executeQuery(
                    "SELECT count(*) FROM sqlite_master WHERE type = 'table' AND name = 'should_rollback'")) {
                assertTrue(query.next());
                assertEquals(0, query.getInt(1));
            }
            assertFalse(runner.status().get(0).contains("APPLIED"));
        }
    }

    @Test
    void rejectsVersionGaps() throws Exception {
        Path migrations = Files.createDirectory(temporaryDirectory.resolve("gap"));
        Files.writeString(migrations.resolve("V0001__one.up.sql"), "CREATE TABLE one(id INTEGER);");
        Files.writeString(migrations.resolve("V0001__one.down.sql"), "DROP TABLE one;");
        Files.writeString(migrations.resolve("V0003__three.up.sql"), "CREATE TABLE three(id INTEGER);");
        Files.writeString(migrations.resolve("V0003__three.down.sql"), "DROP TABLE three;");
        assertThrows(IOException.class, () -> MigrationRepository.load(migrations));
    }

    @Test
    void rejectsUnterminatedSqlQuotesDuringValidation() throws Exception {
        Path migrations = Files.createDirectory(temporaryDirectory.resolve("unterminated"));
        Files.writeString(migrations.resolve("V0001__bad.up.sql"), "INSERT INTO sample VALUES ('unfinished);");
        Files.writeString(migrations.resolve("V0001__bad.down.sql"), "DROP TABLE sample;");
        assertThrows(IOException.class, () -> MigrationRepository.load(migrations));
    }

    private Path copyMigrations() throws IOException {
        Path source = Path.of("migrations");
        Path target = Files.createDirectory(temporaryDirectory.resolve("migrations-" + System.nanoTime()));
        try (var files = Files.list(source)) {
            for (Path file : files.toList()) Files.copy(file, target.resolve(file.getFileName()));
        }
        return target;
    }
}
