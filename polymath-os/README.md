# Polymath OS

A personal command centre for goals, projects, notes, habits, and study. This first release is a small, local-first application built with FastAPI and SQLite. It runs without external services or API keys.

## Features

- Capture goals, projects, and searchable notes.
- Record daily habits and see a recent activity streak.
- Review a dashboard of open work and recent notes.
- Store data in a local SQLite database.
- Use the JSON API directly or the built-in responsive web interface.

## Run

From this directory, install the repository's FastAPI dependencies and start the app:

```sh
python -m pip install -r ../requirements-termux.txt
uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000>. The API reference is at <http://127.0.0.1:8000/docs>.

By default the database is `polymath.db` in the current directory. Set `POLYMATH_DB` to use another path. No personal data is sent to a server.

## API

- `GET /api/dashboard`
- `GET|POST /api/goals`
- `GET|POST /api/projects`
- `GET|POST /api/notes`
- `GET|POST /api/habits`
- `POST /api/habits/{habit_id}/check-ins`
- `GET /api/search?q=...`

## Next development steps

1. Add editing and archive flows, plus export and import.
2. Add recurring reminders and richer progress analytics.
3. Add PostgreSQL support and authentication before any hosted deployment.
4. Add an optional knowledge graph view connecting notes, goals, and projects.

This is a portfolio and learning project, not a substitute for a backup system. Keep the database file private and back it up before upgrades.
