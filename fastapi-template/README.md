fastapi-template

Mission
-------
Help developers boot a reliable FastAPI service with sensible defaults for development, testing, and deployment.

Objectives
- Provide a straightforward directory layout and a single, documented entrypoint (app.main:app).
- Include CI to run linting and tests automatically on PRs.
- Ship a small, secure Docker image and run instructions.
- Encourage good developer ergonomics with pre-commit, formatter and linter rules.

Intended users
- Developers starting a new microservice, instructors demonstrating modern Python API practices, or teams standardizing API scaffolding.

Success criteria
- Green CI on new PRs, reproducible Docker build, and at least one example endpoint with tests.

Run locally (venv)

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

Docker build

docker build -t it-projects-fastapi:latest .

docker run -p 8000:8000 --env-file .env.example it-projects-fastapi:latest

Tests

pip install -r requirements-dev.txt
pytest -q

Note: Adjust the ASGI app import path in the Dockerfile/CMD if your application module path differs.
