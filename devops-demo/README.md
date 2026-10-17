# Cloud Deployment and DevOps Demonstrator

This project packages Polymath Enterprise as a small, non-root container, runs a health check, and provides a GitHub Actions build workflow. It includes a hardened Compose deployment and a verified JSON export workflow. The workflow builds and smoke-checks locally in CI; it does not publish an image or deploy to a paid host automatically.

## Local container run

From the repository root:

```sh
docker build -f devops-demo/Dockerfile -t polymath-enterprise:local .
docker run --rm -p 8000:8000 -v polymath-enterprise-data:/data \
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

No cloud credentials, public registry, or paid service is required by this demonstration.
