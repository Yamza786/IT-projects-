fastapi-template

A small FastAPI starter with a Dockerfile, health endpoint, and smoke tests.

Features:
- `GET /` service information
- `GET /health` readiness check
- `GET /ping` connectivity check
- Dockerfile, dependency list, and test suite

Intended users
- Developers starting a new microservice, instructors demonstrating modern Python API practices, or teams standardizing API scaffolding.

1. `cd fastapi-template`
2. `python -m venv .venv && . .venv/bin/activate`
3. `pip install -r requirements.txt`
4. `uvicorn app.main:app --reload`

Visit `http://127.0.0.1:8000/docs` for the interactive API documentation.

Run the tests with `pytest` from this directory.

Build and run the container:

```sh
docker build -t fastapi-template .
docker run --rm -p 8000:80 fastapi-template
```
