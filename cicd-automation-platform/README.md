# Pipeline Forge — CI/CD Automation Platform

Pipeline Forge is a Go CLI for validating declarative YAML pipelines, showing an execution plan, and running ordered jobs in constrained Docker workers. It writes structured run and job statuses, captures bounded logs, and copies declared artifacts into a local run record with SHA-256 checksums.

## Problem and features

Small teams need repeatable build checks without adopting a hosted CI service. Pipeline Forge provides a compact, inspectable local runner with explicit worker limits and machine-readable results.

- Strict YAML decoding rejects unknown keys, multiple documents, oversized files and invalid job graphs.
- Jobs declare an image, ordered shell steps, earlier job dependencies, timeout and literal artifact paths.
- Worker containers disable networking, use a read-only container root, drop Linux capabilities, set a non-root user, and cap processes, memory, CPUs and temporary storage.
- Jobs use a temporary copy of the source tree (excluding `.git` and previous run records); pipeline steps do not write into the original checkout.
- Logs are capped at 256 KiB per job. Run records and checksummed artifacts are stored under `.pipeline/runs/<run-id>/`.
- Failed dependencies skip downstream jobs; unrelated jobs continue so one failure does not hide other results.

## Architecture and boundaries

`cmd/cicdctl` handles CLI output. `internal/pipeline` owns YAML validation, workspace preparation, Docker invocation and run records. Each job is a separate Docker container that shares the isolated temporary workspace for this run.

This is a local learning-scale runner, not a hosted multi-tenant control plane. Pipeline YAML and its shell commands are executable code: only run configurations you trust. Docker containers add process and resource boundaries, but are not a substitute for a hardened VM or a hostile-code sandbox. A Docker daemon is required for `run`; validation and planning work without one. There is no secrets manager, remote worker pool, webhook service or artifact retention policy. Do not place credentials in pipeline YAML or logs. Pin production images by digest; the example uses a versioned tag for readability.

## Requirements and setup

- Go 1.23 or newer.
- Docker Engine with permission to run containers for execution (not required for `validate` or `plan`).

Dependencies are pinned in `go.mod` and `go.sum`.

```sh
go mod download
go test ./...
go vet ./...
go run ./cmd/cicdctl validate pipeline.example.yaml
go run ./cmd/cicdctl plan pipeline.example.yaml
```

To run the sample, from this directory:

```sh
go run ./cmd/cicdctl run pipeline.example.yaml
```

The demo uses `alpine:3.22`; Docker pulls it if it is not already cached. A successful run creates a JSON status record and copies `dist/report.txt` under `.pipeline/runs/<run-id>/`. That artifact is synthetic and has no external deployment effect.

## Pipeline format

```yaml
name: sample
version: 1
jobs:
  - id: checks
    image: alpine:3.22
    timeout_minutes: 5
    steps:
      - name: run checks
        run: printf 'checks passed\n'
    artifacts:
      - reports/checks.txt
```

Job IDs and pipeline names use lowercase letters, digits and hyphens. Dependencies must refer to earlier jobs. Each job accepts 1–32 steps and a 1–60 minute timeout; the default is 10 minutes. Artifacts are relative literal paths and must resolve to regular files without symlink components.

## Tests, CI and security

Unit tests cover strict YAML validation, job dependency boundaries, workspace path safety, container flags, artifact checksums and dependency failure behavior. Tests use a fake Docker executable, so they verify runner command construction and status handling without claiming a container actually started. GitHub Actions runs formatting checks, `go test -race`, `go vet`, CLI validation/planning, and the sample pipeline on a hosted Linux runner.

Do not expose the Docker socket to worker containers, mount sensitive host directories, or use this prototype for untrusted pull request code. The job container receives only a temporary source copy. Always review a pipeline change before running it.

## Contribution and license

Follow the repository contribution guidance. Add focused tests for changes to the pipeline schema, worker limits, artifact handling or record format. This project uses the repository MIT license.
