package dev.portfolio.schemaguard;

import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DriverManager;

public final class Main {
    private Main() {}

    public static void main(String[] args) {
        try {
            run(args);
        } catch (Exception exception) {
            System.err.println("schema-guard: " + exception.getMessage());
            System.exit(1);
        }
    }

    private static void run(String[] args) throws Exception {
        if (args.length != 1) {
            printUsage();
            throw new IllegalArgumentException("Expected one command");
        }
        String command = args[0];
        Path migrations = Path.of(System.getenv().getOrDefault("SCHEMA_GUARD_MIGRATIONS", "./migrations"));
        if ("validate".equals(command)) {
            var loaded = MigrationRepository.load(migrations);
            System.out.printf("Validated %d migration pair(s).%n", loaded.size());
            return;
        }

        String jdbcUrl = System.getenv().getOrDefault("SCHEMA_GUARD_JDBC_URL", "jdbc:sqlite:./data/schema-guard.db");
        if (!jdbcUrl.startsWith("jdbc:sqlite:")) throw new IllegalArgumentException("Only SQLite JDBC URLs are supported");
        if (jdbcUrl.startsWith("jdbc:sqlite:./")) {
            Path database = Path.of(jdbcUrl.substring("jdbc:sqlite:".length()));
            if (database.getParent() != null) Files.createDirectories(database.getParent());
        }

        try (Connection connection = DriverManager.getConnection(jdbcUrl)) {
            try (var statement = connection.createStatement()) {
                statement.execute("PRAGMA foreign_keys = ON");
                statement.execute("PRAGMA busy_timeout = 5000");
            }
            MigrationRunner runner = new MigrationRunner(connection, migrations);
            switch (command) {
                case "status" -> runner.status().forEach(System.out::println);
                case "plan" -> runner.plan().forEach(System.out::println);
                case "up" -> System.out.printf("Applied %d migration(s).%n", runner.migrateUp());
                case "rollback" -> {
                    if (!runner.rollbackOne()) System.out.println("No migration to roll back.");
                }
                default -> {
                    printUsage();
                    throw new IllegalArgumentException("Unknown command: " + command);
                }
            }
        }
    }

    private static void printUsage() {
        System.err.println("Usage: schema-guard <validate|status|up|rollback>");
    }
}
