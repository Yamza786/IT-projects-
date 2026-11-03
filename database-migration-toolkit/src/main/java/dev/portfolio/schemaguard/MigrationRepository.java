package dev.portfolio.schemaguard;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

final class MigrationRepository {
    private static final Pattern FILE_NAME = Pattern.compile(
            "V([0-9]{4,})__([a-z][a-z0-9_-]*)\\.(up|down)\\.sql");

    private MigrationRepository() {}

    static List<Migration> load(Path directory) throws IOException {
        if (!Files.isDirectory(directory)) throw new IOException("Migration directory does not exist: " + directory);

        Map<Integer, Pair> pairs = new TreeMap<>();
        try (var files = Files.list(directory)) {
            for (Path file : files.filter(Files::isRegularFile).sorted().toList()) {
                Matcher matcher = FILE_NAME.matcher(file.getFileName().toString());
                if (!matcher.matches()) {
                    throw new IOException("Invalid migration filename: " + file.getFileName()
                            + " (expected V0001__description.up.sql or .down.sql)");
                }
                int version;
                try {
                    version = Integer.parseInt(matcher.group(1));
                } catch (NumberFormatException exception) {
                    throw new IOException("Migration version is too large: " + file.getFileName(), exception);
                }
                if (version < 1) throw new IOException("Migration versions start at 1: " + file.getFileName());

                String name = matcher.group(2);
                Pair pair = pairs.computeIfAbsent(version, ignored -> new Pair(name));
                if (!pair.name.equals(name)) throw new IOException("Migration version " + version + " has inconsistent names");
                String sql = Files.readString(file, StandardCharsets.UTF_8);
                if (sql.isBlank()) throw new IOException("Migration is empty: " + file.getFileName());
                try {
                    if (SqlScript.statements(sql).isEmpty())
                        throw new IOException("Migration has no SQL statements: " + file.getFileName());
                } catch (IllegalArgumentException exception) {
                    throw new IOException("Invalid SQL script: " + file.getFileName(), exception);
                }
                if ("up".equals(matcher.group(3))) {
                    if (pair.up != null) throw new IOException("Duplicate up migration: " + file.getFileName());
                    pair.up = sql;
                } else {
                    if (pair.down != null) throw new IOException("Duplicate down migration: " + file.getFileName());
                    pair.down = sql;
                }
            }
        }

        List<Migration> migrations = new ArrayList<>();
        int expectedVersion = 1;
        for (Map.Entry<Integer, Pair> entry : pairs.entrySet()) {
            int version = entry.getKey();
            Pair pair = entry.getValue();
            if (version != expectedVersion) {
                throw new IOException("Migration versions must be contiguous; expected V%04d but found V%04d"
                        .formatted(expectedVersion, version));
            }
            if (pair.up == null || pair.down == null) {
                throw new IOException("Migration V%04d__%s must have both .up.sql and .down.sql files"
                        .formatted(version, pair.name));
            }
            migrations.add(new Migration(version, pair.name, pair.up, pair.down, sha256(pair.up)));
            expectedVersion++;
        }
        return List.copyOf(migrations);
    }

    private static String sha256(String text) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(text.getBytes(StandardCharsets.UTF_8));
            return java.util.HexFormat.of().formatHex(digest);
        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException("SHA-256 is required by the Java runtime", exception);
        }
    }

    private static final class Pair {
        private final String name;
        private String up;
        private String down;
        private Pair(String name) { this.name = name; }
    }
}
