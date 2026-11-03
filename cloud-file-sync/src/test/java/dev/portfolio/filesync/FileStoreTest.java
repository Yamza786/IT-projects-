package dev.portfolio.filesync;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class FileStoreTest {
    @TempDir Path directory;
    private FileStore store;

    @BeforeEach void setup() throws Exception { store = new FileStore(directory.resolve("objects"), directory.resolve("metadata.sqlite")); }

    @Test void resumesIdempotentChunksAndVerifiesStoredContent() throws Exception {
        byte[] data = "portable file fixture".getBytes(StandardCharsets.UTF_8);
        String hash = FileStore.sha256(data);
        FileStore.Upload upload = store.beginUpload("alice", "notes.txt", data.length, 1, hash, null);
        assertEquals(java.util.List.of(0), upload.missingChunks());
        assertThrows(IllegalArgumentException.class, () -> store.status(upload.id(), "bob"));
        store.putChunk(upload.id(), "alice", 0, data);
        store.putChunk(upload.id(), "alice", 0, data);
        assertTrue(store.status(upload.id(), "alice").missingChunks().isEmpty());
        FileStore.ObjectInfo object = store.complete(upload.id(), "alice");
        assertEquals(1, object.version());
        assertEquals(hash, object.sha256());
        assertEquals("portable file fixture", Files.readString(store.download("alice", "notes.txt")));
        assertEquals(1, store.list("alice").size());
        assertTrue(store.list("bob").isEmpty());
    }

    @Test void rejectsIncompleteAndCorruptUploadsAndSupportsOptimisticUpdates() throws Exception {
        byte[] first = "v1".getBytes(StandardCharsets.UTF_8);
        var initial = store.beginUpload("alice", "state.bin", first.length, 1, FileStore.sha256(first), null);
        assertThrows(IllegalStateException.class, () -> store.complete(initial.id(), "alice"));
        store.putChunk(initial.id(), "alice", 0, first);
        store.complete(initial.id(), "alice");

        byte[] second = "v2".getBytes(StandardCharsets.UTF_8);
        var stale = store.beginUpload("alice", "state.bin", second.length, 1, FileStore.sha256(second), 9);
        store.putChunk(stale.id(), "alice", 0, second);
        assertThrows(IllegalStateException.class, () -> store.complete(stale.id(), "alice"));
        store.cancel(stale.id(), "alice");

        var update = store.beginUpload("alice", "state.bin", second.length, 1, FileStore.sha256(second), 1);
        store.putChunk(update.id(), "alice", 0, second);
        assertEquals(2, store.complete(update.id(), "alice").version());
        assertEquals("v2", Files.readString(store.download("alice", "state.bin")));
    }

    @Test void rejectsMismatchedChecksumsUnsafeNamesAndBadChunkIndexes() throws Exception {
        byte[] data = "payload".getBytes(StandardCharsets.UTF_8);
        var upload = store.beginUpload("alice", "data.bin", data.length, 1, "0".repeat(64), null);
        assertThrows(IllegalArgumentException.class, () -> store.putChunk(upload.id(), "alice", 1, data));
        store.putChunk(upload.id(), "alice", 0, data);
        assertThrows(IllegalStateException.class, () -> store.complete(upload.id(), "alice"));
        assertFalse(store.list("alice").stream().anyMatch(file -> file.name().equals("data.bin")));
        assertThrows(IllegalArgumentException.class, () -> store.beginUpload("alice", "../escape", data.length, 1, FileStore.sha256(data), null));
    }
}
