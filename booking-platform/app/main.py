"""Local service booking demo with overlap prevention and no card data."""

from __future__ import annotations

import html
import os
import sqlite3
import hmac
import hashlib
import secrets
import time
from collections import defaultdict, deque
from contextlib import closing
from datetime import date, datetime, time as clock_time, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Query, Request, Depends
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, SecretStr
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DB_PATH = Path(os.environ.get("BOOKING_DB", "booking.db"))
app = FastAPI(title="Service Booking Platform", version="0.1.0")
ADMIN_KEY = os.environ.get("BOOKING_ADMIN_KEY", "")
creation_times: dict[str, deque[float]] = defaultdict(deque)


def require_admin(x_admin_key: str | None = Header(default=None, alias="X-Admin-Key")):
    if not ADMIN_KEY:
        raise HTTPException(503,"Configure BOOKING_ADMIN_KEY before using administration routes")
    if not x_admin_key or not hmac.compare_digest(x_admin_key,ADMIN_KEY):
        raise HTTPException(401,"Valid admin key required")
    return True


def check_public_rate(request: Request):
    address=request.client.host if request.client else "unknown"
    now=time.monotonic()
    stamps=creation_times[address]
    while stamps and now-stamps[0]>=3600:
        stamps.popleft()
    if len(stamps)>=20:
        raise HTTPException(429,"Booking request limit reached for this client")
    stamps.append(now)
    return True


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
            CREATE TABLE IF NOT EXISTS accounts(id INTEGER PRIMARY KEY,customer_id INTEGER NOT NULL UNIQUE REFERENCES customers(id) ON DELETE CASCADE,
                email TEXT NOT NULL UNIQUE,salt BLOB NOT NULL,password_hash BLOB NOT NULL,created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sessions(id INTEGER PRIMARY KEY,account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                token_hash TEXT NOT NULL UNIQUE,expires_at TEXT NOT NULL,created_at TEXT NOT NULL);
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
    starts_at: datetime


class AccountIn(BaseModel):
    name: str = Field(min_length=1,max_length=160)
    email: str = Field(min_length=3,max_length=254)
    password: SecretStr = Field(min_length=12,max_length=256)


class LoginIn(BaseModel):
    email: str = Field(min_length=3,max_length=254)
    password: SecretStr


def service_rows():
    with closing(connect()) as db:
        return [dict(r) for r in db.execute("SELECT * FROM services WHERE active=1 ORDER BY name")]


def password_hash(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode("utf-8"),salt=salt,n=2**14,r=8,p=1,dklen=32)


def current_account(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401,"Log in to your booking account")
    token=authorization[7:]
    token_hash=hashlib.sha256(token.encode()).hexdigest()
    with closing(connect()) as db:
        row=db.execute("""SELECT a.id AS account_id,a.customer_id,a.email,c.name,s.id AS session_id
            FROM sessions s JOIN accounts a ON a.id=s.account_id JOIN customers c ON c.id=a.customer_id
            WHERE s.token_hash=? AND s.expires_at>?""",(token_hash,datetime.now(timezone.utc).isoformat(timespec="seconds"))).fetchone()
    if not row:
        raise HTTPException(401,"Session is invalid or expired")
    return dict(row)


@app.post("/api/accounts",status_code=201)
def create_account(item: AccountIn):
    email=item.email.strip().lower()
    salt=secrets.token_bytes(16)
    with closing(connect()) as db:
        try:
            cur=db.execute("INSERT INTO customers(name,email,created_at) VALUES(?,?,?)",
                           (item.name.strip(),email,datetime.now(timezone.utc).isoformat(timespec="seconds")))
            customer_id=cur.lastrowid
            db.execute("INSERT INTO accounts(customer_id,email,salt,password_hash,created_at) VALUES(?,?,?,?,?)",
                       (customer_id,email,salt,password_hash(item.password.get_secret_value(),salt),datetime.now(timezone.utc).isoformat(timespec="seconds")))
            db.commit()
        except sqlite3.IntegrityError as exc:
            db.rollback()
            raise HTTPException(409,"An account with this email already exists") from exc
    return {"created":True,"email":email,"message":"Account created. You can now sign in."}


@app.post("/api/login")
def login(item: LoginIn):
    with closing(connect()) as db:
        account=db.execute("SELECT * FROM accounts WHERE email=?",(item.email.strip().lower(),)).fetchone()
        if not account or not hmac.compare_digest(password_hash(item.password.get_secret_value(),account["salt"]),account["password_hash"]):
            raise HTTPException(401,"Email or password is incorrect")
        token=secrets.token_urlsafe(32)
        created=datetime.now(timezone.utc)
        expires=created+timedelta(hours=24)
        db.execute("INSERT INTO sessions(account_id,token_hash,expires_at,created_at) VALUES(?,?,?,?)",
                   (account["id"],hashlib.sha256(token.encode()).hexdigest(),expires.isoformat(timespec="seconds"),created.isoformat(timespec="seconds")))
        db.commit()
    return {"access_token":token,"token_type":"bearer","expires_at":expires.isoformat(timespec="seconds")}


@app.delete("/api/account/session")
def logout(account: dict = Depends(current_account)):
    with closing(connect()) as db:
        db.execute("DELETE FROM sessions WHERE id=?",(account["session_id"],))
        db.commit()
    return {"logged_out":True}


@app.get("/api/services")
def get_services():
    return service_rows()


@app.post("/api/services", status_code=201)
def add_service(item: ServiceIn, _: bool = Depends(require_admin)):
    with closing(connect()) as db:
        try:
            cur = db.execute("INSERT INTO services(name,description,duration_minutes,price_cents) VALUES(?,?,?,?)",
                             (item.name.strip(), item.description.strip(), item.duration_minutes, item.price_cents))
            db.commit()
        except sqlite3.IntegrityError as exc:
            raise HTTPException(409, "A service with this name already exists") from exc
        return dict(db.execute("SELECT * FROM services WHERE id=?", (cur.lastrowid,)).fetchone())


@app.post("/api/bookings", status_code=201)
def create_booking(item: BookingIn, account: dict = Depends(current_account), _: bool = Depends(check_public_rate)):
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
        local_minute=item.starts_at.hour*60+item.starts_at.minute
        if item.starts_at.minute not in (0,30) or item.starts_at.second or item.starts_at.microsecond or local_minute<9*60 or local_minute+service["duration_minutes"]>17*60:
            db.rollback()
            raise HTTPException(422,"Choose a 30-minute slot between 09:00 and 17:00 in the submitted timezone")
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
        cur = db.execute("INSERT INTO bookings(service_id,customer_id,starts_at_utc,ends_at_utc,status,created_at) VALUES(?,?,?,?,'confirmed',?)",
                         (service["id"], account["customer_id"], start_iso, end_iso, datetime.now(timezone.utc).isoformat(timespec="seconds")))
        db.commit()
        return {"id": cur.lastrowid, "service": service["name"], "starts_at_utc": start_iso, "ends_at_utc": end_iso, "status": "confirmed"}


@app.get("/api/availability")
def availability(service_id: int = Query(gt=0), day: date = Query(), timezone_name: str = Query(default="UTC", alias="timezone", max_length=100)):
    try:
        zone=ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(422,"Unknown IANA timezone") from exc
    with closing(connect()) as db:
        service=db.execute("SELECT * FROM services WHERE id=? AND active=1",(service_id,)).fetchone()
        if not service:
            raise HTTPException(404,"Service not found")
        existing=[(datetime.fromisoformat(r[0]),datetime.fromisoformat(r[1])) for r in db.execute("SELECT starts_at_utc,ends_at_utc FROM bookings WHERE status='confirmed'")]
    slots=[]
    for minute in range(9*60,17*60-service["duration_minutes"]+1,30):
        naive=datetime.combine(day,clock_time(minute//60,minute%60))
        local=naive.replace(tzinfo=zone)
        if local.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None)!=naive:
            continue
        start=local.astimezone(timezone.utc)
        end=start+timedelta(minutes=service["duration_minutes"])
        if start<=datetime.now(timezone.utc):
            continue
        if any(start<busy_end and busy_start<end for busy_start,busy_end in existing):
            continue
        slots.append(local.isoformat(timespec="minutes"))
    return {"service_id":service_id,"day":day.isoformat(),"timezone":timezone_name,"slots":slots,
            "availability_rule":"Weekdays are not restricted; daily slots are 09:00–17:00 local time at 30-minute intervals."}


@app.get("/api/bookings")
def get_bookings(_: bool = Depends(require_admin)):
    with closing(connect()) as db:
        return [dict(r) for r in db.execute("""
            SELECT b.id,b.starts_at_utc,b.ends_at_utc,b.status,s.name AS service,c.name AS customer
            FROM bookings b JOIN services s ON s.id=b.service_id JOIN customers c ON c.id=b.customer_id
            ORDER BY b.starts_at_utc LIMIT 200
        """)]


@app.get("/api/my-bookings")
def my_bookings(account: dict = Depends(current_account)):
    with closing(connect()) as db:
        return [dict(r) for r in db.execute("""
            SELECT b.id,b.starts_at_utc,b.ends_at_utc,b.status,s.name AS service
            FROM bookings b JOIN services s ON s.id=b.service_id WHERE b.customer_id=? ORDER BY b.starts_at_utc
        """,(account["customer_id"],))]


@app.post("/api/my-bookings/{booking_id}/cancel")
def cancel_my_booking(booking_id: int, account: dict = Depends(current_account)):
    with closing(connect()) as db:
        cur=db.execute("UPDATE bookings SET status='cancelled' WHERE id=? AND customer_id=? AND status='confirmed'",
                       (booking_id,account["customer_id"]))
        if not cur.rowcount:
            raise HTTPException(404,"Active booking not found")
        db.commit()
    return {"id":booking_id,"status":"cancelled"}


@app.post("/api/bookings/{booking_id}/cancel")
def cancel_booking(booking_id: int, _: bool = Depends(require_admin)):
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
    </style></head><body><main><div class="eyebrow">OPENSLOT · EASY SERVICE BOOKINGS</div><h1>Choose a time that works.</h1><p>Available 30-minute slots use your device's IANA timezone.</p><section><h2>Your account</h2><form id="account"><label for="account-name">Name for new account</label><input id="account-name" name="name" autocomplete="name" maxlength="160"><label for="account-email">Email</label><input id="account-email" name="email" type="email" autocomplete="email" required maxlength="254"><label for="account-password">Password · at least 12 characters</label><input id="account-password" name="password" type="password" autocomplete="current-password" minlength="12" required><div><button type="button" id="register">Create account</button> <button type="button" id="login">Sign in</button> <button type="button" id="logout">Sign out</button></div><p id="account-status" role="status" aria-live="polite"></p></form><ul id="mine"></ul></section><section><form id="book"><label for="service">Service</label><select id="service" name="service_id">{cards}</select><label for="day">Date</label><input id="day" name="day" type="date" required><label for="time">Available start time</label><select id="time" name="starts_at" required></select><button>Request booking</button></form><p id="message" role="status" aria-live="polite"></p></section><p>No card details are collected. <a href="/docs">API reference</a></p></main><script>
    const form=document.getElementById('book'),timeSelect=document.getElementById('time');const now=new Date();const localDate=new Date(now.getTime()-now.getTimezoneOffset()*60000).toISOString().slice(0,10);form.day.value=localDate;form.day.min=localDate;async function loadSlots(){{timeSelect.replaceChildren();const zone=Intl.DateTimeFormat().resolvedOptions().timeZone;const url=`/api/availability?service_id=${{form.service_id.value}}&day=${{form.day.value}}&timezone=${{encodeURIComponent(zone)}}`;const data=await fetch(url).then(r=>r.json());for(const slot of data.slots||[]){{const option=new Option(slot.slice(11,16),slot);timeSelect.add(option)}}if(!timeSelect.options.length)timeSelect.add(new Option('No times available',''))}}form.day.onchange=loadSlots;form.service_id.onchange=loadSlots;loadSlots();
    let token=sessionStorage.getItem('bookingToken')||'';const accountForm=document.getElementById('account'),accountStatus=document.getElementById('account-status');async function accountAction(mode){{const f=accountForm;const body={{email:f.email.value,password:f.password.value}};if(mode==='register'){{body.name=f.name.value;const r=await fetch('/api/accounts',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(body)}});const d=await r.json();accountStatus.textContent=r.ok?'Account created; sign in to continue.':(d.detail||'Could not create account');return}}const r=await fetch('/api/login',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(body)}});const d=await r.json();if(!r.ok){{accountStatus.textContent=d.detail||'Sign-in failed';return}}token=d.access_token;sessionStorage.setItem('bookingToken',token);accountStatus.textContent='Signed in · token expires '+d.expires_at;loadMine()}}document.getElementById('register').onclick=()=>accountAction('register');document.getElementById('login').onclick=()=>accountAction('login');document.getElementById('logout').onclick=async()=>{{if(token)await fetch('/api/account/session',{{method:'DELETE',headers:{{'Authorization':'Bearer '+token}}}});token='';sessionStorage.removeItem('bookingToken');accountStatus.textContent='Signed out';document.getElementById('mine').replaceChildren()}};
    async function loadMine(){{if(!token)return;const r=await fetch('/api/my-bookings',{{headers:{{'Authorization':'Bearer '+token}}}});if(!r.ok){{sessionStorage.removeItem('bookingToken');token='';accountStatus.textContent='Session expired; sign in again.';return}}const items=await r.json(),box=document.getElementById('mine');box.replaceChildren();for(const b of items){{const li=document.createElement('li');li.textContent=`${{b.service}} · ${{b.starts_at_utc}} · ${{b.status}} `;if(b.status==='confirmed'){{const btn=document.createElement('button');btn.textContent='Cancel';btn.onclick=async()=>{{await fetch(`/api/my-bookings/${{b.id}}/cancel`,{{method:'POST',headers:{{'Authorization':'Bearer '+token}}}});loadMine()}};li.append(btn)}}box.append(li)}}}}if(token)loadMine();
    form.onsubmit=async e=>{{e.preventDefault();if(!token){{document.getElementById('message').textContent='Sign in before booking.';return}}const f=e.target;const body={{service_id:Number(f.service_id.value),starts_at:f.starts_at.value}};const r=await fetch('/api/bookings',{{method:'POST',headers:{{'Content-Type':'application/json','Authorization':'Bearer '+token}},body:JSON.stringify(body)}});const d=await r.json();document.getElementById('message').textContent=r.ok?'Booking confirmed for '+d.starts_at_utc:(d.detail||'Could not book this time.');if(r.ok){{loadSlots();loadMine()}}}}
    </script></body></html>'''
