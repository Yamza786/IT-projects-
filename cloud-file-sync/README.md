# Cloud File Storage and Synchronization Prototype

A Java 21 resumable file store with authenticated owner-scoped metadata, fixed 1 MiB chunks, SHA-256 integrity checks, SQLite metadata, optimistic conflict detection, and atomic local blob replacement. It binds to loopback for the demo and is not a public cloud deployment.

## Run

Set a unique random bearer token of at least 32 characters for each owner in `FILESYNC_TOKENS=alice=TOKEN,bob=TOKEN`, then:

```sh
gradle test
gradle run
```

The service binds to `127.0.0.1:8082`. `FILESYNC_ROOT`, `FILESYNC_DATABASE`, and `FILESYNC_PORT` can configure local paths and port. The root and database are created with private Unix permissions where supported. The upload directory must have enough disk space for the staged upload and its committed blob.

## API

Except `/health`, every route requires `Authorization: Bearer TOKEN`. Owner identity is derived from the configured token and never taken from request data.

1. Start an upload with `POST /uploads?name=report.bin&size=1234&chunks=1&sha256=<lowercase-hex>`; include `baseVersion=N` when replacing an existing file. New files omit it.
2. Send raw bytes with `PUT /uploads/{id}/chunks/{index}`. Chunks are at most 1 MiB; each position must have its exact expected size. Re-sending an identical chunk is safe and idempotent.
3. `GET /uploads/{id}` reports missing chunk indices so an interrupted client can resume.
4. `POST /uploads/{id}/complete` assembles and verifies the full SHA-256, checks the base version, and atomically updates metadata/blob state.
5. `GET /files` lists metadata and versions; `GET /files/{name}` downloads the owner's copy. `DELETE /uploads/{id}` cancels an open transfer.

Files are limited to 512 MiB, 1 MiB chunks and 20 active uploads per owner (at most 2 GiB of staged content). A new file conflicts if it already exists; updates require the current version. There are no silent last-write-wins updates.

## Verification and limits

JUnit covers resume, duplicate chunk idempotency, integrity failure, version conflicts, owner separation, and embedded HTTP upload/download. The service is single-instance local storage: it has no cloud object-store adapter, replication, TLS termination, multi-region sync, encryption at rest, or garbage collector for abandoned transfers. Keep token secrets private and place the service behind a reviewed authenticated TLS boundary before any remote use.
