# Polymath OS

A personal command centre for goals, projects, notes, habits, and study. This first release is a small, local-first application built with FastAPI and SQLite. It runs without external services or API keys.

## Features

- Capture goals, projects, and searchable notes.
- Record daily habits and see a recent activity streak.
- Connect goals, projects, and notes in a searchable relationship graph.
- Create and complete timezone-aware reminders.
- Review activity counts and export all workspace data as JSON.
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
- `GET /api/graph?q=...`, `POST /api/links`
- `GET|POST /api/reminders`, `POST /api/reminders/{id}/complete`
- `GET /api/analytics`, `GET /api/export`

## Data editing and restore

Goals, projects, and notes have editing endpoints. Download a JSON workspace from `GET /api/export/download`; import a compatible backup with `POST /api/import` only into a fresh database. Import is intentionally refused when the database already has records. Back up the SQLite file separately before upgrades.

## Limits

This is a single-user, local portfolio application. It has no login or synchronization and should not be exposed publicly with personal data. For architecture and trade-offs shared across the portfolio, see [the architecture guide](../portfolio/ARCHITECTURE.md) and [the roadmap](../portfolio/ROADMAP.md).
