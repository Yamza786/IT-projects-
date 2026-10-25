# Workbench Browser IDE

Workbench is a local browser editor for short JavaScript snippets. The Go API sends each run to a fresh Docker container and returns bounded stdout/stderr. It is a learning tool for trusted local users, not a public multi-tenant code hosting service.

## Features

- Browser editor with a minimal TypeScript client.
- Node.js snippets run in disposable containers with no network, read-only root filesystem, no Linux capabilities, a non-root UID, 128 MiB memory, 0.5 CPU, 32 processes, and an 8 MiB temporary filesystem.
- Eight KiB source limit, two-second timeout, two global concurrent runs, ten runs per client per hour, and 16 KiB each for stdout and stderr.
- API binds to `127.0.0.1:8080` by default and rejects non-loopback callers.
- No run history, host directory mounts, credentials, or personal data.

## Requirements

- Go 1.22 or newer.
- Node.js 24 and npm for compiling the TypeScript browser client.
- Docker Engine with the `node:22-alpine` image available. Pull it before disconnecting from the network if runs must work offline.

## Run locally

```sh
npm ci
npm run build
go test ./...
go run ./cmd/coderunner
```

Open <http://127.0.0.1:8080>. The API exposes `GET /healthz` and `POST /api/runs` with JSON `{ "code": "console.log(1 + 1)" }`.

Set `IDE_ADDR` to another loopback address if port 8080 is busy. Keep this service bound to localhost; a public deployment would need authenticated accounts, stronger isolation, and operational review.

## Limits

The sandbox depends on the local Docker daemon and kernel isolation. A container is not a complete hostile-code isolation boundary; use a dedicated VM or hardened sandbox runtime for untrusted public submissions. Jobs and quotas are in-memory and reset when the process exits. This MVP supports JavaScript only; it does not compile or retain user projects.

## Contribution and license

Use the repository's [contribution guidance](../CONTRIBUTING.md). This project is distributed under the repository's [license](../LICENSE).
