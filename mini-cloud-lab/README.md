# Mini Cloud Infrastructure Lab

A small containerized HTTP service for practicing image builds, health checks, configuration, persistent storage, and CI. It is intentionally a lab, not a cloud provider deployment or hardened production template.

```sh
docker compose up --build
curl http://localhost:8090/health
```

The service listens only on the configured Compose port. GitHub Actions builds the image and checks `/health`. Review the Dockerfile, compose file, and workflow to understand the deployment lifecycle. Never place secrets in the image or repository.
