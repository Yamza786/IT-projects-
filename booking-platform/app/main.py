"""Local service booking demo with overlap prevention and no card data."""

from __future__ import annotations

import html
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

DB_PATH = Path(os.environ.get("BOOKING_DB", "booking.db"))
app = FastAPI(title="Service Booking Platform", version="0.1.0")


def connect():
    c = sqlite3.connect(DB_PATH, timeout=10)
    c.row_factory = sqlite3.Row
    return c


def init():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with closing(connect()) as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS services(id INTEGER PRIMARY KEY,name TEXT NOT NULL UNIQUE,description TEXT NOT NULL DEFAULT '',duration_minutes INTEGER NOT NULL CHECK(duration_minutes BETWEEN 5 AND 480),price_cents INTEGER NOT NULL CHECK(price_cents>=0),active INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE IF NOT EXISTS customers(id INTEGER PRIMARY KEY,name TEXT NOT NULL,email TEXT NOT NULL,created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS bookings(id INTEGER PRIMARY KEY,service_id INTEGER NOT NULL REFERENCES services(id),customer_id INTEGER NOT NULL REFERENCES customers(id),starts_at_utc TEXT NOT NULL,ends_at_utc TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'confirmed' CHECK(status IN ('confirmed','cancelled')),created_at TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS booking_time_idx ON bookings(status,starts_at_utc,ends_at_utc);
        """)
        if not db.execute("SELECT 1 FROM services LIMIT 1").fetchone():
            db.execute("INSERT INTO services(name,description,duration_minutes,price_cents) VALUES('Discovery session','A sample 30-minute consultation.',30,0)")
        db.commit()


@app.on_event("startup")
def startup():
    init()


class ServiceIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=1000)
    duration_minutes: int = Field(ge=5, le=480)
    price_cents: int = Field(ge=0)


class BookingIn(BaseModel):
    service_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=160)
    email: str = Field(min_length=3, max_length=254)
    starts_at: datetime


def service_rows():
    with closing(connect()) as db:
        return [dict(r) for r in db.execute("SELECT * FROM services WHERE active=1 ORDER BY name")]


@app.get("/api/services")
def get_services():
    return service_rows()


@app.post("/api/services", status_code=201)
def add_service(item: ServiceIn):
    with closing(connect()) as db:
        try:
            cur = db.execute("INSERT INTO services(name,description,duration_minutes,price_cents) VALUES(?,?,?,?)",
                             (item.name.strip(), item.description.strip(), item.duration_minutes, item.price_cents))
            db.commit()
        except sqlite3.IntegrityError as exc:
            raise HTTPException(409, "A service with this name already exists") from exc
        return dict(db.execute("SELECT * FROM services WHERE id=?", (cur.lastrowid,)).fetchone())


@app.post("/api/bookings", status_code=201)
def create_booking(item: BookingIn):
    if item.starts_at.tzinfo is None or item.starts_at.utcoffset() is None:
        raise HTTPException(422, "starts_at must include a timezone offset")
    starts = item.starts_at.astimezone(timezone.utc)
    if starts <= datetime.now(timezone.utc):
        raise HTTPException(422, "Booking time must be in the future")
    with closing(connect()) as db:
        db.execute("BEGIN IMMEDIATE")
        service = db.execute("SELECT * FROM services WHERE id=? AND active=1", (item.service_id,)).fetchone()
        if not service:
            db.rollback()
            raise HTTPException(404, "Service not found")
        ends = starts.timestamp() + service["duration_minutes"] * 60
        start_iso = starts.isoformat(timespec="seconds")
        end_iso = datetime.fromtimestamp(ends, timezone.utc).isoformat(timespec="seconds")
        conflict = db.execute("""
            SELECT 1 FROM bookings b JOIN services s ON s.id=b.service_id
            WHERE b.status='confirmed' AND b.starts_at_utc < ? AND ? < b.ends_at_utc LIMIT 1
        """, (end_iso, start_iso)).fetchone()
        if conflict:
            db.rollback()
            raise HTTPException(409, "That time overlaps an existing booking")
        cur = db.execute("INSERT INTO customers(name,email,created_at) VALUES(?,?,?)",
                         (item.name.strip(), item.email.strip().lower(), datetime.now(timezone.utc).isoformat(timespec="seconds")))
        customer_id = cur.lastrowid
        cur = db.execute("INSERT INTO bookings(service_id,customer_id,starts_at_utc,ends_at_utc,status,created_at) VALUES(?,?,?,?,'confirmed',?)",
                         (service["id"], customer_id, start_iso, end_iso, datetime.now(timezone.utc).isoformat(timespec="seconds")))
        db.commit()
        return {"id": cur.lastrowid, "service": service["name"], "starts_at_utc": start_iso, "ends_at_utc": end_iso, "status": "confirmed"}


@app.get("/api/bookings")
def get_bookings():
    with closing(connect()) as db:
        return [dict(r) for r in db.execute("""
            SELECT b.id,b.starts_at_utc,b.ends_at_utc,b.status,s.name AS service,c.name AS customer
            FROM bookings b JOIN services s ON s.id=b.service_id JOIN customers c ON c.id=b.customer_id
            ORDER BY b.starts_at_utc LIMIT 200
        """)]


@app.post("/api/bookings/{booking_id}/cancel")
def cancel_booking(booking_id: int):
    with closing(connect()) as db:
        cur = db.execute("UPDATE bookings SET status='cancelled' WHERE id=? AND status='confirmed'", (booking_id,))
        if not cur.rowcount:
            db.rollback()
            if not db.execute("SELECT 1 FROM bookings WHERE id=?", (booking_id,)).fetchone():
                raise HTTPException(404, "Booking not found")
            raise HTTPException(409, "Booking is already cancelled")
        db.commit()
    return {"id": booking_id, "status": "cancelled"}


@app.get("/", response_class=HTMLResponse)
def home():
    cards = "".join(f'<option value="{s["id"]}">{html.escape(s["name"])} · {s["duration_minutes"]} min</option>' for s in service_rows())
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>OpenSlot · Booking</title><style>
    *{{box-sizing:border-box}}body{{margin:0;background:#f4f7f6;color:#1d302c;font:16px/1.5 system-ui,sans-serif}}main{{max-width:700px;margin:auto;padding:40px 20px}}.eyebrow{{color:#16836d;font-size:12px;letter-spacing:.13em;font-weight:700}}h1{{font-size:clamp(32px,5vw,48px);margin:8px 0}}section{{background:white;border:1px solid #dce8e4;border-radius:16px;padding:22px;margin:18px 0}}label{{display:block;font-weight:650;margin:14px 0 6px}}input,select,button{{width:100%;font:inherit;padding:11px;border:1px solid #cbdad5;border-radius:9px}}button{{margin-top:16px;background:#16836d;color:white;border:0;font-weight:700;cursor:pointer}}#message{{min-height:1.6em}}a{{color:#16836d}}
    </style></head><body><main><div class="eyebrow">OPENSLOT · EASY SERVICE BOOKINGS</div><h1>Choose a time that works.</h1><p>A sample booking page for a service business. Time must include your local UTC offset.</p><section><form id="book"><label for="service">Service</label><select id="service" name="service_id">{cards}</select><label for="name">Your name</label><input id="name" name="name" autocomplete="name" required maxlength="160"><label for="email">Email</label><input id="email" name="email" type="email" autocomplete="email" required maxlength="254"><label for="time">Start time</label><input id="time" name="starts_at" type="datetime-local" required><button>Request booking</button></form><p id="message" role="status" aria-live="polite"></p></section><p>Times are interpreted using this device's UTC offset. No card details are collected. <a href="/docs">API reference</a></p></main><script>
    document.getElementById('book').onsubmit=async e=>{{e.preventDefault();const f=e.target;const local=new Date(f.starts_at.value);const offset=-local.getTimezoneOffset();const sign=offset>=0?'+':'-';const hh=String(Math.floor(Math.abs(offset)/60)).padStart(2,'0');const mm=String(Math.abs(offset)%60).padStart(2,'0');const body={{service_id:Number(f.service_id.value),name:f.name.value,email:f.email.value,starts_at:f.starts_at.value+sign+hh+':'+mm}};const r=await fetch('/api/bookings',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(body)}});const d=await r.json();document.getElementById('message').textContent=r.ok?'Booking confirmed for '+d.starts_at_utc:(d.detail||'Could not book this time.')}}
    </script></body></html>'''
