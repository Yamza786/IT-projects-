#!/bin/bash
set -e

# Script to open PRs for all project branches. Requires GitHub CLI (gh) and authentication.

REPO="Yamza786/IT-projects-"

gh pr create --repo "$REPO" --base main --head algorithms-python --title "Add algorithms-python scaffold, CI (ruff + pytest), and .gitignore" --body "Added algorithms implementations, tests, CI workflow (ruff + pytest), and .gitignore.\n\nRun tests locally: python -m pytest algorithms-python/tests"

gh pr create --repo "$REPO" --base main --head fastapi-template --title "Add fastapi-template scaffold, CI (ruff + pytest) and Docker build" --body "Minimal FastAPI app, Dockerfile, CI workflow that runs ruff, pytest and builds the Docker image on PRs, and a basic test.\n\nRun locally: pip install -r fastapi-template/requirements.txt && uvicorn fastapi-template.app.main:app --reload"

gh pr create --repo "$REPO" --base main --head sys-admin-scripts --title "Add sys-admin-scripts scaffold, CI (shellcheck + ruff), and .gitignore" --body "Small bash and Python sysadmin utilities (backup.sh, user-report.py) plus CI that runs shellcheck on shell scripts and ruff on Python. Usage examples included in README."

gh pr create --repo "$REPO" --base main --head vuln-web-lab --title "Add vuln-web-lab scaffold and CI to validate docker-compose" --body "Docker Compose scaffold to run OWASP Juice Shop locally and a walkthrough. CI validates docker-compose.yml syntax using yamllint."

gh pr create --repo "$REPO" --base main --head ml-from-scratch --title "Add ml-from-scratch scaffold, CI (ruff + pytest), and .gitignore" --body "Educational ML implementations and notebooks, plus CI (ruff + pytest). Example: ml-from-scratch/ml/linear_regression.py included.\n\nRun examples: pip install -r ml-from-scratch/requirements.txt"
