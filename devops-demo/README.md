# Cloud Deployment and DevOps Demonstrator

This project packages Polymath Enterprise as a small, non-root container, runs a health check, and provides a GitHub Actions build workflow. It includes a hardened Compose deployment and a verified JSON export workflow. The workflow builds and smoke-checks locally in CI; it does not publish an image or deploy to a paid host automatically.

## Local container run

From the repository root:

```sh
docker build -f devops-demo/Dockerfile -t polymath-enterprise:local .
docker run --rm -p 8000:10000 -v polymath-enterprise-data:/data \
  -e ENTERPRISE_READER_KEY='replace-me' \
  -e ENTERPRISE_MANAGER_KEY='replace-with-a-different-key' \
  -e ENTERPRISE_ADMIN_KEY='replace-with-another-key' polymath-enterprise:local
```

Open `http://127.0.0.1:8000`. Database files persist in `./data`.

## Compose deployment

From the repository root, copy `devops-demo/.env.production.example` to `devops-demo/.env.production`, replace all three keys with long independent secrets, then run:

```sh
docker compose -f devops-demo/compose.yaml up --build -d
curl --fail http://127.0.0.1:8000/health
```

The listener is bound to loopback, the root filesystem is read-only, Linux capabilities are dropped, and SQLite data stays in a named volume. Put a TLS reverse proxy in front of it before making it public. Keep `.env.production` outside version control.

## Backup and restore drill

With `ENTERPRISE_ADMIN_KEY` available in the shell, run `devops-demo/backup.sh /path/to/off-host-backups`. The script requests the administrator-only snapshot, validates its format, writes with restrictive permissions, and only then renames it into place. Keep copies off the application host. The endpoint exports records; it is not an automated database restore command. For a restore drill, stop the service, copy the SQLite volume using a SQLite-aware backup or the documented maintenance window, restore to a separate instance, and verify `/health`, customer/product counts, sales totals, audit records, and security reports before promoting the restored volume.

## Host deployment checklist

1. Select a host with persistent storage, TLS, and a private service network; confirm its costs and data-region requirements.
2. Set resource limits and an off-host backup schedule; test restoring a backup before public launch.
3. Keep admin routes private and rotate the three distinct role keys through the host's secret manager.
4. Review logs, update base images regularly, and alert on failed health checks and backup failures.

The local build and CI demonstration require no cloud credentials, public registry, or paid service. The container listens on port 10000 by default; Compose and the local run command publish that as port 8000 on the host.

## Optional Render deployment

The repository-root [`render.yaml`](../render.yaml) defines a single-instance Docker web service with `/health` checks, three platform-generated role secrets, and a 1 GB persistent disk mounted at `/data` for SQLite. It deploys new commits only after repository checks pass. To launch it, connect the private GitHub repository to Render, select the `integration/fastapi` branch, review the Blueprint resources and current billing estimate, then create the service in the Render dashboard. The service name can be changed there if it is already taken.

This configuration requires a paid web-service plan because Render free web services cannot attach persistent disks. At the time this note was checked (2026-10-17), Render lists the selected 256 MB plan at $6/month and persistent disk storage at $0.25/GB/month; bandwidth or other account usage can add charges. Confirm the current total in Render before creating the service. A persistent disk is single-instance and causes a short service interruption during redeploys. See [Render pricing](https://render.com/pricing), [persistent disk requirements](https://render.com/docs/disks), and the [Blueprint specification](https://render.com/docs/blueprint-spec).
