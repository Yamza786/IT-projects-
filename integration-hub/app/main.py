"""Versioned local integration API with scoped keys, rate limiting, and idempotency."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import sqlite3
import time
from collections import defaultdict, deque
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field

DB_PATH = Path(os.environ.get("HUB_DB", "hub.db"))
WRITE_KEY = os.environ.get("HUB_WRITE_KEY", "")
READ_KEY = os.environ.get("HUB_READ_KEY", "")
RATE_LIMIT = max(10, int(os.environ.get("HUB_RATE_LIMIT", "120")))
app = FastAPI(title="Integration Hub", version="1.0.0")
requests_by_key: dict[str, deque[float]] = defaultdict(deque)


def connect():
    c = sqlite3.connect(DB_PATH, timeout=10)
    c.row_factory = sqlite3.Row
    return c


def init():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with closing(connect()) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS events(
            id INTEGER PRIMARY KEY,source TEXT NOT NULL,external_id TEXT NOT NULL,kind TEXT NOT NULL,
            occurred_at TEXT NOT NULL,payload TEXT NOT NULL,idempotency_key TEXT NOT NULL UNIQUE,received_at TEXT NOT NULL,
            UNIQUE(source,external_id,kind))""")
        db.commit()


@app.on_event("startup")
def startup():
    init()


def authorize(scope: Literal["read", "write"]):
    def dependency(request: Request, x_api_key: str | None = Header(default=None)):
        configured = WRITE_KEY if scope == "write" else (READ_KEY or WRITE_KEY)
        if not configured or not x_api_key or not hmac.compare_digest(x_api_key, configured):
            raise HTTPException(401, "Valid API key required")
        fingerprint = hashlib.sha256(x_api_key.encode()).hexdigest()[:16]
        now = time.monotonic()
        stamps = requests_by_key[fingerprint]
        while stamps and now - stamps[0] >= 60:
            stamps.popleft()
        if len(stamps) >= RATE_LIMIT:
            raise HTTPException(429, "Rate limit exceeded", headers={"Retry-After": "60"})
        stamps.append(now)
        return {"scope": scope}
    return dependency


class EventIn(BaseModel):
    external_id: str = Field(min_length=1, max_length=160)
    kind: str = Field(min_length=1, max_length=100, regex=r"^[a-zA-Z0-9_.-]+$")
    occurred_at: datetime
    payload: dict[str, Any] = Field(default_factory=dict)


@app.get("/health")
def health():
    return {"status": "ok", "api_version": "v1"}


@app.post("/api/v1/integrations/{source}/events", status_code=201)
def ingest(source: str, item: EventIn, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
           _: dict = Depends(authorize("write"))):
    source = source.lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,49}", source):
        raise HTTPException(422, "Source name must use letters, numbers, hyphens, or underscores")
    if not idempotency_key or not re.fullmatch(r"[A-Za-z0-9._:-]{1,200}", idempotency_key):
        raise HTTPException(422, "A valid Idempotency-Key header is required")
    payload = json.dumps(item.payload, sort_keys=True, separators=(",", ":"))
    with closing(connect()) as db:
        existing = db.execute("SELECT * FROM events WHERE idempotency_key=?", (idempotency_key,)).fetchone()
        if existing:
            if existing["source"] != source or existing["external_id"] != item.external_id:
                raise HTTPException(409, "Idempotency key was already used for a different event")
            return {**dict(existing), "payload": json.loads(existing["payload"]), "replayed": True}
        try:
            cur = db.execute("INSERT INTO events(source,external_id,kind,occurred_at,payload,idempotency_key,received_at) VALUES(?,?,?,?,?,?,?)",
                             (source,item.external_id,item.kind,item.occurred_at.isoformat(),payload,idempotency_key,datetime.now(timezone.utc).isoformat(timespec="seconds")))
            db.commit()
        except sqlite3.IntegrityError as exc:
            raise HTTPException(409, "An event with this source, external ID, and kind already exists") from exc
        row = dict(db.execute("SELECT * FROM events WHERE id=?", (cur.lastrowid,)).fetchone())
    row["payload"] = json.loads(row["payload"])
    row["replayed"] = False
    return row


@app.get("/api/v1/events")
def list_events(limit: int = 100, _: dict = Depends(authorize("read"))):
    if not 1 <= limit <= 500:
        raise HTTPException(422, "limit must be between 1 and 500")
    with closing(connect()) as db:
        rows = [dict(r) for r in db.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,))]
    for row in rows:
        row["payload"] = json.loads(row["payload"])
    return rows
