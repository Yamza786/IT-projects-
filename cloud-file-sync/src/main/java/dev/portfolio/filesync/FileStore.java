package dev.portfolio.filesync;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.List;
import java.util.UUID;

public final class FileStore {
    public static final int CHUNK_BYTES = 1_048_576;
    public static final long MAX_FILE_BYTES = 512L * CHUNK_BYTES;
    private final Path root;
    private final String jdbcUrl;

    public FileStore(Path root, Path database) throws IOException, SQLException {
        this.root = root.toAbsolutePath().normalize();
        Path staging = this.root.resolve(".staging");
        Path objects = this.root.resolve("objects");
        Files.createDirectories(staging); Files.createDirectories(objects); Files.createDirectories(database.toAbsolutePath().normalize().getParent());
        try {
            Files.setPosixFilePermissions(this.root, java.nio.file.attribute.PosixFilePermissions.fromString("rwx------"));
            Files.setPosixFilePermissions(staging, java.nio.file.attribute.PosixFilePermissions.fromString("rwx------"));
            Files.setPosixFilePermissions(objects, java.nio.file.attribute.PosixFilePermissions.fromString("rwx------"));
            Files.setPosixFilePermissions(database.toAbsolutePath().normalize().getParent(), java.nio.file.attribute.PosixFilePermissions.fromString("rwx------"));
        } catch (UnsupportedOperationException ignored) { /* Windows ACLs are inherited from the selected data directory. */ }
        jdbcUrl = "jdbc:sqlite:" + database.toAbsolutePath().normalize();
        try (Connection db = open(); var statement = db.createStatement()) {
            statement.execute("PRAGMA foreign_keys = ON");
            statement.execute("PRAGMA busy_timeout = 5000");
            statement.execute("CREATE TABLE IF NOT EXISTS uploads (id TEXT PRIMARY KEY, owner TEXT NOT NULL, name TEXT NOT NULL, size INTEGER NOT NULL, chunk_count INTEGER NOT NULL, sha256 TEXT NOT NULL, base_version INTEGER, state TEXT NOT NULL CHECK(state IN ('open','complete','canceled')), created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)");
            statement.execute("CREATE TABLE IF NOT EXISTS upload_chunks (upload_id TEXT NOT NULL REFERENCES uploads(id), chunk_index INTEGER NOT NULL, size INTEGER NOT NULL, sha256 TEXT NOT NULL, PRIMARY KEY(upload_id,chunk_index))");
            statement.execute("CREATE TABLE IF NOT EXISTS objects (id TEXT PRIMARY KEY, owner TEXT NOT NULL, name TEXT NOT NULL, size INTEGER NOT NULL, sha256 TEXT NOT NULL, version INTEGER NOT NULL, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, blob_path TEXT NOT NULL, UNIQUE(owner,name))");
            boolean hasBlobPath = false;
            try (var columns = statement.executeQuery("PRAGMA table_info(objects)")) {
                while (columns.next()) if (columns.getString("name").equals("blob_path")) hasBlobPath = true;
            }
            if (!hasBlobPath) statement.execute("ALTER TABLE objects ADD COLUMN blob_path TEXT NOT NULL DEFAULT ''");
        }
        try { Files.setPosixFilePermissions(database.toAbsolutePath().normalize(), java.nio.file.attribute.PosixFilePermissions.fromString("rw-------")); }
        catch (IOException | UnsupportedOperationException exception) { throw new IOException("cannot secure metadata database permissions", exception); }
    }

    private Connection open() throws SQLException {
        Connection db = DriverManager.getConnection(jdbcUrl);
        try (var statement = db.createStatement()) {
            statement.execute("PRAGMA foreign_keys = ON");
            statement.execute("PRAGMA busy_timeout = 5000");
            return db;
        } catch (SQLException exception) {
            db.close();
            throw exception;
        }
    }

    public record Upload(String id, int chunkCount, List<Integer> missingChunks) { }
    public record ObjectInfo(String name, long size, String sha256, int version, String updatedAt) { }

    public Upload beginUpload(String owner, String name, long size, int chunks, String sha256, Integer baseVersion) throws SQLException, IOException {
        if (owner == null || !owner.matches("[A-Za-z0-9._-]{1,64}")) throw new IllegalArgumentException("invalid owner identifier");
        if (name == null || !name.matches("[A-Za-z0-9._-]{1,128}") || name.equals(".") || name.equals("..")) throw new IllegalArgumentException("filename must use safe ASCII letters, digits, dot, underscore, or dash");
        if (size < 1 || size > MAX_FILE_BYTES) throw new IllegalArgumentException("file size must be 1 byte to 512 MiB");
        int requiredChunks = (int)((size + CHUNK_BYTES - 1) / CHUNK_BYTES);
        if (chunks != requiredChunks) throw new IllegalArgumentException("chunk count does not match file size");
        if (sha256 == null || !sha256.matches("[a-f0-9]{64}")) throw new IllegalArgumentException("expected sha256 must be lowercase hex");
        if (baseVersion != null && baseVersion < 1) throw new IllegalArgumentException("base version must be positive");
        try (Connection db = open(); var active = db.prepareStatement("SELECT COUNT(*),COALESCE(SUM(size),0) FROM uploads WHERE owner=? AND state='open'")) {
            active.setString(1, owner);
            try (var rows = active.executeQuery()) {
                rows.next();
                if (rows.getInt(1) >= 20 || rows.getLong(2) + size > MAX_FILE_BYTES * 4) throw new IllegalStateException("owner upload quota exceeded");
            }
        }
        String id = UUID.randomUUID().toString();
        try (Connection db = open(); var insert = db.prepareStatement("INSERT INTO uploads(id,owner,name,size,chunk_count,sha256,base_version,state) VALUES(?,?,?,?,?,?,?,'open')")) {
            insert.setString(1, id); insert.setString(2, owner); insert.setString(3, name); insert.setLong(4, size); insert.setInt(5, chunks); insert.setString(6, sha256);
            if (baseVersion == null) insert.setNull(7, java.sql.Types.INTEGER); else insert.setInt(7, baseVersion);
            insert.executeUpdate();
        }
        Path uploadDirectory = uploadDirectory(id);
        try { Files.createDirectory(uploadDirectory); }
        catch (IOException exception) {
            try (Connection db = open(); var delete = db.prepareStatement("DELETE FROM uploads WHERE id=?")) { delete.setString(1, id); delete.executeUpdate(); }
            throw exception;
        }
        return new Upload(id, chunks, missing(id, owner));
    }

    public synchronized void putChunk(String id, String owner, int index, byte[] bytes) throws SQLException, IOException {
        UploadRow upload = requireOpen(id, owner);
        if (index < 0 || index >= upload.chunks()) throw new IllegalArgumentException("chunk index is outside upload range");
        int expected = index == upload.chunks() - 1 ? (int)(upload.size() - (long)index * CHUNK_BYTES) : CHUNK_BYTES;
        if (bytes == null || bytes.length != expected) throw new IllegalArgumentException("chunk length does not match its position");
        String digest = sha256(bytes);
        Path target = uploadDirectory(id).resolve(index + ".part");
        try (Connection db = open(); var existing = db.prepareStatement("SELECT sha256,size FROM upload_chunks WHERE upload_id=? AND chunk_index=?")) {
            existing.setString(1, id); existing.setInt(2, index);
            try (var rows = existing.executeQuery()) {
                if (rows.next()) {
                    if (rows.getInt("size") == bytes.length && rows.getString("sha256").equals(digest)) return;
                    throw new IllegalStateException("chunk index already contains different data");
                }
            }
        }
        Files.write(target, bytes, StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
        try (Connection db = open(); var insert = db.prepareStatement("INSERT INTO upload_chunks(upload_id,chunk_index,size,sha256) VALUES(?,?,?,?)")) {
            insert.setString(1, id); insert.setInt(2, index); insert.setInt(3, bytes.length); insert.setString(4, digest); insert.executeUpdate();
        } catch (SQLException exception) {
            Files.deleteIfExists(target);
            throw exception;
        }
    }

    public Upload status(String id, String owner) throws SQLException {
        try (Connection db = open(); var query = db.prepareStatement("SELECT chunk_count FROM uploads WHERE id=? AND owner=? AND state='open'")) {
            query.setString(1, id); query.setString(2, owner);
            try (var rows = query.executeQuery()) {
                if (!rows.next()) throw new IllegalArgumentException("upload does not exist or is not open");
                return new Upload(id, rows.getInt(1), missing(id, owner));
            }
        }
    }

    private record UploadRow(long size, int chunks, String name, String digest, Integer baseVersion) { }

    private UploadRow requireOpen(String id, String owner) throws SQLException {
        try (Connection db = open(); var query = db.prepareStatement("SELECT size,chunk_count,name,sha256,base_version FROM uploads WHERE id=? AND owner=? AND state='open'")) {
            query.setString(1, id); query.setString(2, owner);
            try (var rows = query.executeQuery()) {
                if (!rows.next()) throw new IllegalArgumentException("upload does not exist or is not open");
                int base = rows.getInt("base_version"); Integer baseVersion = rows.wasNull() ? null : base;
                return new UploadRow(rows.getLong("size"), rows.getInt("chunk_count"), rows.getString("name"), rows.getString("sha256"), baseVersion);
            }
        }
    }

    private List<Integer> missing(String id, String owner) throws SQLException {
        try (Connection db = open(); var query = db.prepareStatement("SELECT chunk_count FROM uploads WHERE id=? AND owner=?")) {
            query.setString(1, id); query.setString(2, owner);
            try (var rows = query.executeQuery()) {
                if (!rows.next()) throw new IllegalArgumentException("upload does not exist");
                int count = rows.getInt(1);
                List<Integer> missing = new ArrayList<>();
                try (var chunks = db.prepareStatement("SELECT chunk_index FROM upload_chunks WHERE upload_id=?")) {
                    chunks.setString(1, id);
                    try (var received = chunks.executeQuery()) {
                        boolean[] found = new boolean[count];
                        while (received.next()) found[received.getInt(1)] = true;
                        for (int i = 0; i < count; i++) if (!found[i]) missing.add(i);
                    }
                }
                return List.copyOf(missing);
            }
        }
    }

    public synchronized ObjectInfo complete(String id, String owner) throws SQLException, IOException {
        UploadRow upload = requireOpen(id, owner);
        List<Integer> missing = missing(id, owner);
        if (!missing.isEmpty()) throw new IllegalStateException("upload is incomplete; missing chunks " + missing);
        Path staging = root.resolve(".staging").resolve(id + ".ready");
        MessageDigest digest = newDigest();
        long copied = 0;
        try (var output = Files.newOutputStream(staging, StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE)) {
            for (int index = 0; index < upload.chunks(); index++) {
                Path part = uploadDirectory(id).resolve(index + ".part");
                try (InputStream input = Files.newInputStream(part)) {
                    byte[] buffer = new byte[64 * 1024]; int count;
                    while ((count = input.read(buffer)) >= 0) {
                        if (count == 0) continue;
                        output.write(buffer, 0, count); digest.update(buffer, 0, count); copied += count;
                    }
                }
            }
        } catch (IOException exception) { Files.deleteIfExists(staging); throw exception; }
        if (copied != upload.size() || !HexFormat.of().formatHex(digest.digest()).equals(upload.digest())) {
            Files.deleteIfExists(staging);
            throw new IllegalStateException("assembled file size or SHA-256 does not match the declared value");
        }

        String objectId = UUID.randomUUID().toString();
        Path destination = root.resolve("objects").resolve(objectId + ".blob");
        boolean moved = false;
        String oldBlob = null;
        try (Connection db = open()) {
            db.setAutoCommit(false);
            try {
                Integer currentVersion = null;
                try (var query = db.prepareStatement("SELECT id,version,blob_path FROM objects WHERE owner=? AND name=?")) {
                    query.setString(1, owner); query.setString(2, upload.name());
                    try (var rows = query.executeQuery()) { if (rows.next()) { currentVersion = rows.getInt("version"); oldBlob = rows.getString("blob_path"); } }
                }
                if (upload.baseVersion() == null ? currentVersion != null : !upload.baseVersion().equals(currentVersion)) {
                    throw new IllegalStateException("file version conflict; refresh metadata and retry");
                }
                int version = currentVersion == null ? 1 : currentVersion + 1;
                Files.move(staging, destination, StandardCopyOption.ATOMIC_MOVE); moved = true;
                try (var save = db.prepareStatement("INSERT INTO objects(id,owner,name,size,sha256,version,blob_path) VALUES(?,?,?,?,?,?,?) ON CONFLICT(owner,name) DO UPDATE SET id=excluded.id,size=excluded.size,sha256=excluded.sha256,version=excluded.version,blob_path=excluded.blob_path,updated_at=CURRENT_TIMESTAMP")) {
                    save.setString(1, objectId); save.setString(2, owner); save.setString(3, upload.name()); save.setLong(4, upload.size()); save.setString(5, upload.digest()); save.setInt(6, version); save.setString(7, destination.toString()); save.executeUpdate();
                }
                try (var done = db.prepareStatement("UPDATE uploads SET state='complete' WHERE id=? AND state='open'")) { done.setString(1, id); done.executeUpdate(); }
                db.commit();
                if (oldBlob != null) try { Files.deleteIfExists(Path.of(oldBlob)); } catch (IOException ignored) { /* stale blobs are harmless and remain private */ }
                try { deleteParts(id); } catch (IOException ignored) { /* completion is durable; orphan staging data can be garbage-collected later */ }
                return new ObjectInfo(upload.name(), upload.size(), upload.digest(), version, java.time.Instant.now().toString());
            } catch (SQLException | IOException | RuntimeException exception) {
                db.rollback();
                if (moved) Files.deleteIfExists(destination);
                throw exception;
            }
        } finally { Files.deleteIfExists(staging); }
    }

    public List<ObjectInfo> list(String owner) throws SQLException {
        try (Connection db = open(); var query = db.prepareStatement("SELECT name,size,sha256,version,updated_at FROM objects WHERE owner=? ORDER BY name")) {
            query.setString(1, owner);
            try (var rows = query.executeQuery()) {
                List<ObjectInfo> result = new ArrayList<>();
                while (rows.next()) result.add(new ObjectInfo(rows.getString(1), rows.getLong(2), rows.getString(3), rows.getInt(4), rows.getString(5)));
                return List.copyOf(result);
            }
        }
    }

    public Path download(String owner, String name) throws SQLException {
        try (Connection db = open(); var query = db.prepareStatement("SELECT blob_path FROM objects WHERE owner=? AND name=?")) {
            query.setString(1, owner); query.setString(2, name);
            try (var rows = query.executeQuery()) {
                if (!rows.next()) throw new IllegalArgumentException("file not found");
                Path path = Path.of(rows.getString(1)).toAbsolutePath().normalize();
                if (!path.startsWith(root.resolve("objects")) || !Files.isRegularFile(path, java.nio.file.LinkOption.NOFOLLOW_LINKS)) throw new IllegalStateException("stored file metadata is invalid");
                return path;
            }
        }
    }

    public synchronized void cancel(String id, String owner) throws SQLException, IOException {
        try (Connection db = open(); var update = db.prepareStatement("UPDATE uploads SET state='canceled' WHERE id=? AND owner=? AND state='open'")) {
            update.setString(1, id); update.setString(2, owner);
            if (update.executeUpdate() != 1) throw new IllegalArgumentException("upload does not exist or is not open");
        }
        deleteParts(id);
    }

    private Path uploadDirectory(String id) { return root.resolve(".staging").resolve(id); }
    private void deleteParts(String id) throws IOException {
        Path directory = uploadDirectory(id);
        if (Files.exists(directory, java.nio.file.LinkOption.NOFOLLOW_LINKS)) {
            try (var files = Files.list(directory)) { for (Path file : files.toList()) Files.deleteIfExists(file); }
            Files.deleteIfExists(directory);
        }
    }

    public static String sha256(byte[] bytes) { return HexFormat.of().formatHex(newDigest().digest(bytes)); }
    private static MessageDigest newDigest() {
        try { return MessageDigest.getInstance("SHA-256"); }
        catch (NoSuchAlgorithmException exception) { throw new IllegalStateException("SHA-256 is unavailable", exception); }
    }
}
