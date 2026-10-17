# IT Asset Management System

Local SQLite inventory for tracking hardware/software assets, ownership, lifecycle state, and changes. It exposes a small FastAPI interface with asset CRUD, assignment, search, and an append-only audit trail.

```sh
python -m pip install fastapi uvicorn
python -m uvicorn app:app --app-dir it-asset-management --host 127.0.0.1 --port 8092
```

Open `/docs`; set `IT_ASSET_DB` for the database file. Example: `POST /assets` with `{"tag":"LAP-001","name":"Training laptop","category":"laptop","serial":"SYNTHETIC-001"}`. Never store passwords or personal data in asset notes. This local demo has no identity provider or multi-user authorization; do not expose it to the internet.
