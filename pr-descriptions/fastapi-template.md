# PR: fastapi-template

Title: Add fastapi-template scaffold, CI (ruff + pytest) and Docker build

Body:
Minimal FastAPI app, Dockerfile, CI workflow that runs ruff, pytest and builds the Docker image on PRs, and a basic test.

Run locally:

pip install -r fastapi-template/requirements.txt && uvicorn fastapi-template.app.main:app --reload
