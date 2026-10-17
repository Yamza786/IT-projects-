"""Case research organizer focused on traceable sources and deadlines."""

from __future__ import annotations

import html
import os
import sqlite3
from contextlib import closing
from datetime import date, datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

DB_PATH = Path(os.environ.get("LEGAL_DB", "legal.db"))
app = FastAPI(title="Legal Research Organizer", version="0.1.0", description="Research administration only; not legal advice")


def connect():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with closing(connect()) as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS cases(id INTEGER PRIMARY KEY,title TEXT NOT NULL,reference TEXT NOT NULL DEFAULT '',status TEXT NOT NULL DEFAULT 'open',created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sources(id INTEGER PRIMARY KEY,case_id INTEGER REFERENCES cases(id) ON DELETE SET NULL,
                title TEXT NOT NULL,issuer TEXT NOT NULL,locator TEXT NOT NULL DEFAULT '',published_on TEXT,accessed_on TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS notes(id INTEGER PRIMARY KEY,case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
                source_id INTEGER REFERENCES sources(id) ON DELETE SET NULL,claim TEXT NOT NULL,passage TEXT NOT NULL DEFAULT '',note TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS documents(id INTEGER PRIMARY KEY,case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
                title TEXT NOT NULL,version INTEGER NOT NULL CHECK(version>0),locator TEXT NOT NULL DEFAULT '',sha256 TEXT NOT NULL DEFAULT '',
                added_at TEXT NOT NULL,UNIQUE(case_id,title,version));
            CREATE TABLE IF NOT EXISTS deadlines(id INTEGER PRIMARY KEY,case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
                title TEXT NOT NULL,due_on TEXT NOT NULL,done INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL);
        """)
        db.commit()


@app.on_event("startup")
def startup():
    init()


class CaseIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    reference: str = Field(default="", max_length=120)


class SourceIn(BaseModel):
    case_id: int | None = None
    title: str = Field(min_length=1, max_length=300)
    issuer: str = Field(min_length=1, max_length=200)
    locator: str = Field(default="", max_length=1000)
    published_on: date | None = None
    accessed_on: date = Field(default_factory=date.today)


class NoteIn(BaseModel):
    case_id: int
    source_id: int | None = None
    claim: str = Field(min_length=1, max_length=1000)
    passage: str = Field(default="", max_length=5000)
    note: str = Field(default="", max_length=5000)


class DeadlineIn(BaseModel):
    case_id: int
    title: str = Field(min_length=1, max_length=200)
    due_on: date


class DocumentIn(BaseModel):
    case_id: int
    title: str = Field(min_length=1, max_length=300)
    version: int = Field(gt=0, le=10000)
    locator: str = Field(default="", max_length=1000)
    sha256: str = Field(default="", regex=r"^(?:[0-9a-fA-F]{64})?$")


def all_rows(sql: str, params=()):
    with closing(connect()) as db:
        return [dict(r) for r in db.execute(sql, params)]


@app.get("/api/cases")
def cases():
    return all_rows("SELECT * FROM cases ORDER BY id DESC")


@app.post("/api/cases", status_code=201)
def add_case(item: CaseIn):
    with closing(connect()) as db:
        cur = db.execute("INSERT INTO cases(title,reference,status,created_at) VALUES(?,?,'open',?)",
                         (item.title.strip(), item.reference.strip(), datetime.now(timezone.utc).isoformat(timespec="seconds")))
        db.commit()
        return dict(db.execute("SELECT * FROM cases WHERE id=?", (cur.lastrowid,)).fetchone())


@app.get("/api/sources")
def sources(case_id: int | None = None):
    if case_id is None:
        return all_rows("SELECT * FROM sources ORDER BY id DESC")
    return all_rows("SELECT * FROM sources WHERE case_id=? ORDER BY id DESC", (case_id,))


@app.post("/api/sources", status_code=201)
def add_source(item: SourceIn):
    with closing(connect()) as db:
        if item.case_id and not db.execute("SELECT 1 FROM cases WHERE id=?", (item.case_id,)).fetchone():
            raise HTTPException(404, "Case not found")
        cur = db.execute("INSERT INTO sources(case_id,title,issuer,locator,published_on,accessed_on) VALUES(?,?,?,?,?,?)",
                         (item.case_id, item.title.strip(), item.issuer.strip(), item.locator.strip(), item.published_on.isoformat() if item.published_on else None, item.accessed_on.isoformat()))
        db.commit()
        return dict(db.execute("SELECT * FROM sources WHERE id=?", (cur.lastrowid,)).fetchone())


@app.get("/api/notes")
def notes(case_id: int | None = None):
    sql = "SELECT n.*,s.title AS source_title,s.issuer AS source_issuer FROM notes n LEFT JOIN sources s ON s.id=n.source_id"
    return all_rows(sql + (" WHERE n.case_id=?" if case_id is not None else "") + " ORDER BY n.id DESC", (case_id,) if case_id is not None else ())


@app.post("/api/notes", status_code=201)
def add_note(item: NoteIn):
    with closing(connect()) as db:
        if not db.execute("SELECT 1 FROM cases WHERE id=?", (item.case_id,)).fetchone():
            raise HTTPException(404, "Case not found")
        if item.source_id and not db.execute("SELECT 1 FROM sources WHERE id=?", (item.source_id,)).fetchone():
            raise HTTPException(404, "Source not found")
        cur = db.execute("INSERT INTO notes(case_id,source_id,claim,passage,note,created_at) VALUES(?,?,?,?,?,?)",
                         (item.case_id,item.source_id,item.claim.strip(),item.passage.strip(),item.note.strip(),datetime.now(timezone.utc).isoformat(timespec="seconds")))
        db.commit()
        return dict(db.execute("SELECT * FROM notes WHERE id=?", (cur.lastrowid,)).fetchone())


@app.get("/api/deadlines")
def deadlines(from_day: date | None = Query(default=None, alias="from"), to_day: date | None = Query(default=None, alias="to")):
    clauses, params = ["d.done=0"], []
    if from_day:
        clauses.append("d.due_on>=?"); params.append(from_day.isoformat())
    if to_day:
        clauses.append("d.due_on<=?"); params.append(to_day.isoformat())
    return all_rows("SELECT d.*,c.title AS case_title FROM deadlines d JOIN cases c ON c.id=d.case_id WHERE " + " AND ".join(clauses) + " ORDER BY d.due_on", tuple(params))


@app.post("/api/deadlines", status_code=201)
def add_deadline(item: DeadlineIn):
    with closing(connect()) as db:
        if not db.execute("SELECT 1 FROM cases WHERE id=?", (item.case_id,)).fetchone():
            raise HTTPException(404, "Case not found")
        cur = db.execute("INSERT INTO deadlines(case_id,title,due_on,created_at) VALUES(?,?,?,?)",
                         (item.case_id,item.title.strip(),item.due_on.isoformat(),datetime.now(timezone.utc).isoformat(timespec="seconds")))
        db.commit()
        return dict(db.execute("SELECT * FROM deadlines WHERE id=?", (cur.lastrowid,)).fetchone())


@app.get("/api/documents")
def documents(case_id: int | None = None):
    if case_id is None:
        return all_rows("SELECT * FROM documents ORDER BY case_id,title,version DESC")
    return all_rows("SELECT * FROM documents WHERE case_id=? ORDER BY title,version DESC",(case_id,))


@app.post("/api/documents", status_code=201)
def add_document(item: DocumentIn):
    with closing(connect()) as db:
        if not db.execute("SELECT 1 FROM cases WHERE id=?",(item.case_id,)).fetchone():
            raise HTTPException(404,"Case not found")
        try:
            cur=db.execute("INSERT INTO documents(case_id,title,version,locator,sha256,added_at) VALUES(?,?,?,?,?,?)",
                            (item.case_id,item.title.strip(),item.version,item.locator.strip(),item.sha256.lower(),datetime.now(timezone.utc).isoformat(timespec="seconds")))
            db.commit()
        except sqlite3.IntegrityError as exc:
            raise HTTPException(409,"That document version already exists") from exc
        return dict(db.execute("SELECT * FROM documents WHERE id=?",(cur.lastrowid,)).fetchone())


@app.post("/api/cases/{case_id}/close")
def close_case(case_id: int):
    with closing(connect()) as db:
        cur=db.execute("UPDATE cases SET status='closed' WHERE id=? AND status='open'",(case_id,))
        if not cur.rowcount:
            raise HTTPException(404,"Open case not found")
        db.commit()
        return dict(db.execute("SELECT * FROM cases WHERE id=?",(case_id,)).fetchone())


@app.post("/api/deadlines/{deadline_id}/complete")
def complete_deadline(deadline_id: int):
    with closing(connect()) as db:
        cur=db.execute("UPDATE deadlines SET done=1 WHERE id=? AND done=0",(deadline_id,))
        if not cur.rowcount:
            raise HTTPException(404,"Open deadline not found")
        db.commit()
        return dict(db.execute("SELECT * FROM deadlines WHERE id=?",(deadline_id,)).fetchone())


@app.get("/", response_class=HTMLResponse)
def home():
    case_list = "".join(f'<li><strong>{html.escape(c["title"])}</strong> <span>{html.escape(c["reference"])}</span></li>' for c in cases()) or "<li>No matters recorded yet.</li>"
    note_list = "".join(f'<article><strong>{html.escape(n["claim"])}</strong><p>{html.escape(n["passage"])}</p><small>Source: {html.escape(n["source_title"] or "unlinked")} · {html.escape(n["source_issuer"] or "")}</small></article>' for n in notes()) or "<p>No research notes yet.</p>"
    due_list = "".join(f'<li>{html.escape(d["due_on"])} · {html.escape(d["title"])} <small>({html.escape(d["case_title"])})</small></li>' for d in deadlines(None,None)) or "<li>No upcoming deadlines recorded.</li>"
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Briefcase · Research Organizer</title><style>
    *{{box-sizing:border-box}}body{{margin:0;background:#f5f3f0;color:#292621;font:15px/1.55 system-ui,sans-serif}}main{{max-width:900px;margin:auto;padding:32px 20px}}.tag{{color:#86643d;font-weight:700;font-size:12px;letter-spacing:.12em}}h1{{font-size:clamp(30px,5vw,44px)}}section{{background:white;border:1px solid #e6e0d7;border-radius:12px;padding:18px;margin:14px 0}}h2{{font-size:18px;margin:0 0 10px}}li{{padding:8px;border-bottom:1px solid #eee;list-style:none}}ul{{padding:0}}span,small{{color:#756e63}}article{{padding:12px;border-left:3px solid #c6a575;margin:10px 0;background:#faf9f6}}button,input,textarea,select{{font:inherit;padding:9px;border:1px solid #d8d2c8;border-radius:7px}}form{{display:grid;gap:8px}}button{{background:#80613b;color:white;border:0;cursor:pointer}}.two{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}@media(max-width:650px){{.two{{grid-template-columns:1fr}}}}
    </style></head><body><main><div class="tag">BRIEFCASE · RESEARCH ADMINISTRATION</div><h1>Keep the record traceable.</h1><p>Organize matters, authorities, research notes, and dates. This is not a legal adviser.</p><div class="two"><section><h2>Matters</h2><ul>{case_list}</ul><form id="case"><input name="title" placeholder="Matter name" required><input name="reference" placeholder="Reference (optional)"><button>Add matter</button></form></section><section><h2>Upcoming deadlines</h2><ul>{due_list}</ul></section></div><section><h2>Source-linked research notes</h2>{note_list}</section><section><h2>Register a source</h2><form id="source"><input name="title" placeholder="Source title" required><input name="issuer" placeholder="Issuing body" required><input name="locator" placeholder="URL or library identifier"><input name="published_on" type="date"><button>Save source</button></form></section><p><a href="/docs">API reference</a>. Verify source currency and preserve confidentiality.</p></main><script>
    async function post(form,url,body){{const r=await fetch(url,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(body)}});if(r.ok)location.reload();else alert((await r.json()).detail||'Could not save')}}document.getElementById('case').onsubmit=e=>{{e.preventDefault();const f=e.target;post(f,'/api/cases',{{title:f.title.value,reference:f.reference.value}})}}document.getElementById('source').onsubmit=e=>{{e.preventDefault();const f=e.target;post(f,'/api/sources',{{title:f.title.value,issuer:f.issuer.value,locator:f.locator.value,published_on:f.published_on.value||null}})}}
    </script></body></html>'''
