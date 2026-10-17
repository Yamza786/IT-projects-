# FastAPI template

A small, secure FastAPI starter with health and connectivity checks, token-protected example API, Docker support, and tests.

## Features

- `GET /` service information
- `GET /health` readiness check
- `GET /ping` connectivity check
- `GET /secure` example endpoint protected by an `X-API-Token` header
- Dockerfile and test suite

## Run locally

```sh
cd fastapi-template
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Set API_TOKEN in .env to a long random value before using /secure.
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Visit `http://127.0.0.1:8000/docs` for interactive API documentation. The `/secure` endpoint returns `503` if the server token is not configured and `401` if the supplied token is missing or incorrect.

## Run tests

```sh
pip install -r requirements-dev.txt
pytest -q
```

## Build and run with Docker

```sh
docker build -t fastapi-template .
docker run --rm -p 8000:80 --env-file .env fastapi-template
```
