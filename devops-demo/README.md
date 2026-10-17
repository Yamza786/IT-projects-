# Cloud Deployment and DevOps Demonstrator

This project packages Polymath Enterprise as a small, non-root container, runs a health check, and provides a GitHub Actions build workflow. It documents how to deploy behind a TLS-terminating reverse proxy with persistent storage. The workflow builds and smoke-checks locally in CI; it does not publish an image or deploy to a paid host automatically.

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

## Host deployment checklist

1. Run the container on a private network behind a reverse proxy with HTTPS.
2. Mount a dedicated persistent volume at `/data`; restrict access to the host and backups. A Docker-managed named volume inherits the image's non-root directory permissions.
3. Set resource limits, automatic restart, and a tested backup schedule.
4. Keep admin interfaces private and set three distinct role keys before starting.
5. Review logs, update base images regularly, and test restore procedures.

No cloud credentials, public registry, or paid service is required by this demonstration.
