"""Versioned local integration API with scoped keys, rate limiting, and idempotency."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import sqlite3
import time
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
        db.execute("""CREATE TABLE IF NOT EXISTS rate_limits(
            key_fingerprint TEXT NOT NULL,minute_bucket INTEGER NOT NULL,request_count INTEGER NOT NULL,
            PRIMARY KEY(key_fingerprint,minute_bucket))""")
        db.commit()


@app.on_event("startup")
def startup():
    init()


def authorize(scope: Literal["read", "write"]):
    def dependency(request: Request, x_api_key: str | None = Header(default=None)):
        env_name="HUB_WRITE_KEYS" if scope=="write" else "HUB_READ_KEYS"
        legacy=WRITE_KEY if scope=="write" else (READ_KEY or WRITE_KEY)
        configured=os.environ.get(env_name,legacy)
        valid_keys=[value.strip() for value in configured.split(",") if value.strip()]
        if not x_api_key or not any(hmac.compare_digest(x_api_key,key) for key in valid_keys):
            raise HTTPException(401, "Valid API key required")
        fingerprint = hashlib.sha256(x_api_key.encode()).hexdigest()
        bucket=int(time.time()//60)
        with closing(connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            row=db.execute("SELECT request_count FROM rate_limits WHERE key_fingerprint=? AND minute_bucket=?",(fingerprint,bucket)).fetchone()
            if row and row["request_count"]>=RATE_LIMIT:
                db.rollback()
                raise HTTPException(429, "Rate limit exceeded", headers={"Retry-After": str(60-int(time.time()%60))})
            db.execute("INSERT INTO rate_limits(key_fingerprint,minute_bucket,request_count) VALUES(?,?,1) ON CONFLICT(key_fingerprint,minute_bucket) DO UPDATE SET request_count=request_count+1",(fingerprint,bucket))
            if bucket%60==0:
                db.execute("DELETE FROM rate_limits WHERE minute_bucket<?",(bucket-120,))
            db.commit()
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
def list_events(after_id: int = 0, limit: int = 100, _: dict = Depends(authorize("read"))):
    if after_id < 0:
        raise HTTPException(422, "after_id must be nonnegative")
    if not 1 <= limit <= 500:
        raise HTTPException(422, "limit must be between 1 and 500")
    with closing(connect()) as db:
        rows = [dict(r) for r in db.execute("SELECT * FROM events WHERE id>? ORDER BY id LIMIT ?", (after_id,limit))]
    for row in rows:
        row["payload"] = json.loads(row["payload"])
    return rows
