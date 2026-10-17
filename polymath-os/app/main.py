"""Local-first personal knowledge and productivity app."""

from __future__ import annotations

import html
import os
import sqlite3
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

DB_PATH = Path(os.environ.get("POLYMATH_DB", "polymath.db"))
app = FastAPI(title="Polymath OS", version="0.1.0", description="A local-first personal command centre")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with closing(connect()) as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS goals (
                id INTEGER PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','completed','paused')),
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','completed','paused')),
                goal_id INTEGER REFERENCES goals(id) ON DELETE SET NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL DEFAULT '',
                tags TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS habits (
                id INTEGER PRIMARY KEY, title TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS check_ins (
                id INTEGER PRIMARY KEY, habit_id INTEGER NOT NULL REFERENCES habits(id) ON DELETE CASCADE,
                day TEXT NOT NULL, UNIQUE(habit_id, day)
            );
            CREATE INDEX IF NOT EXISTS notes_search_idx ON notes(title, body, tags);
        """)
        db.commit()


@app.on_event("startup")
def startup() -> None:
    initialize()


class GoalIn(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=4000)
    status: Literal["active", "completed", "paused"] = "active"


class ProjectIn(GoalIn):
    goal_id: int | None = None


class NoteIn(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    body: str = Field(default="", max_length=20000)
    tags: str = Field(default="", max_length=500)


class HabitIn(BaseModel):
    title: str = Field(min_length=1, max_length=100)


def rows(table: str, limit: int = 100) -> list[dict]:
    with closing(connect()) as db:
        return [dict(row) for row in db.execute(f"SELECT * FROM {table} ORDER BY id DESC LIMIT ?", (limit,))]


def create_item(table: str, fields: dict) -> dict:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    fields["created_at"] = now
    keys = list(fields)
    with closing(connect()) as db:
        try:
            cursor = db.execute(
                f"INSERT INTO {table} ({','.join(keys)}) VALUES ({','.join('?' for _ in keys)})",
                tuple(fields[k] for k in keys),
            )
            db.commit()
            return dict(db.execute(f"SELECT * FROM {table} WHERE id=?", (cursor.lastrowid,)).fetchone())
        except sqlite3.IntegrityError as exc:
            raise HTTPException(status_code=409, detail="That item conflicts with an existing record.") from exc


@app.get("/api/dashboard")
def dashboard() -> dict:
    with closing(connect()) as db:
        goals = [dict(r) for r in db.execute("SELECT * FROM goals WHERE status='active' ORDER BY id DESC")]
        projects = [dict(r) for r in db.execute("SELECT * FROM projects WHERE status='active' ORDER BY id DESC")]
        notes = [dict(r) for r in db.execute("SELECT * FROM notes ORDER BY id DESC LIMIT 5")]
        habits = [dict(r) for r in db.execute("""
            SELECT h.*, MAX(c.day) AS last_check_in,
            SUM(CASE WHEN c.day >= ? THEN 1 ELSE 0 END) AS check_ins_7d
            FROM habits h LEFT JOIN check_ins c ON c.habit_id=h.id
            GROUP BY h.id ORDER BY h.id DESC
        """, ((date.today() - timedelta(days=6)).isoformat(),))]
    return {"goals": goals, "projects": projects, "notes": notes, "habits": habits}


@app.get("/api/goals")
def get_goals() -> list[dict]:
    return rows("goals")


@app.post("/api/goals", status_code=201)
def add_goal(item: GoalIn) -> dict:
    return create_item("goals", item.dict())


@app.get("/api/projects")
def get_projects() -> list[dict]:
    return rows("projects")


@app.post("/api/projects", status_code=201)
def add_project(item: ProjectIn) -> dict:
    data = item.dict()
    with closing(connect()) as db:
        if data["goal_id"] is not None and not db.execute("SELECT 1 FROM goals WHERE id=?", (data["goal_id"],)).fetchone():
            raise HTTPException(status_code=404, detail="Goal not found")
    return create_item("projects", data)


@app.get("/api/notes")
def get_notes() -> list[dict]:
    return rows("notes")


@app.post("/api/notes", status_code=201)
def add_note(item: NoteIn) -> dict:
    return create_item("notes", item.dict())


@app.get("/api/habits")
def get_habits() -> list[dict]:
    return rows("habits")


@app.post("/api/habits", status_code=201)
def add_habit(item: HabitIn) -> dict:
    return create_item("habits", item.dict())


@app.post("/api/habits/{habit_id}/check-ins", status_code=201)
def check_in(habit_id: int, day: date | None = None) -> dict:
    check_day = (day or date.today()).isoformat()
    with closing(connect()) as db:
        if not db.execute("SELECT 1 FROM habits WHERE id=?", (habit_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Habit not found")
        try:
            cursor = db.execute("INSERT INTO check_ins (habit_id, day) VALUES (?, ?)", (habit_id, check_day))
            db.commit()
            return dict(db.execute("SELECT * FROM check_ins WHERE id=?", (cursor.lastrowid,)).fetchone())
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="Already checked in for this day")


@app.get("/api/search")
def search(q: str = Query(min_length=1, max_length=200)) -> dict:
    term = f"%{q.strip()}%"
    with closing(connect()) as db:
        found = {}
        for table, columns in (("goals", ("title", "description")), ("projects", ("title", "description")), ("notes", ("title", "body", "tags"))):
            where = " OR ".join(f"{column} LIKE ?" for column in columns)
            found[table] = [dict(r) for r in db.execute(f"SELECT * FROM {table} WHERE {where} ORDER BY id DESC LIMIT 30", (term,) * len(columns))]
    return found


def e(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    data = dashboard()
    goal_cards = "".join(f'<li><strong>{e(x["title"])}</strong><span>{e(x["description"])}</span></li>' for x in data["goals"]) or "<li class='empty'>No goals yet. Add your first one below.</li>"
    project_cards = "".join(f'<li><strong>{e(x["title"])}</strong><span>{e(x["description"])}</span></li>' for x in data["projects"]) or "<li class='empty'>Your active projects will appear here.</li>"
    note_cards = "".join(f'<article class="note"><h3>{e(x["title"])}</h3><p>{e(x["body"][:180])}</p><small>{e(x["tags"])}</small></article>' for x in data["notes"]) or "<p class='empty'>Capture useful ideas and learning notes.</p>"
    habits = "".join(f'<li><span><strong>{e(x["title"])}</strong><small>{int(x["check_ins_7d"] or 0)} check-ins this week</small></span><button onclick="checkIn({x["id"]})">Check in</button></li>' for x in data["habits"]) or "<li class='empty'>Create a habit to track daily practice.</li>"
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Polymath OS</title><style>
    :root{{--bg:#0b1020;--panel:#141c30;--line:#27334d;--muted:#9aabc7;--text:#f4f7ff;--accent:#9ee6c2;--blue:#a9bdff}}*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(ellipse at 12% 0,#1b2a47 0,transparent 36%),var(--bg);color:var(--text);font:15px/1.5 system-ui,sans-serif}}main{{max-width:1100px;margin:auto;padding:36px 20px 70px}}header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:30px}}.brand{{color:var(--accent);font-weight:700;letter-spacing:.08em;font-size:12px}}h1{{font-size:clamp(30px,5vw,48px);line-height:1.05;margin:12px 0}}h2{{font-size:18px;margin:0 0 16px}}p,.muted{{color:var(--muted)}}.pill{{border:1px solid var(--line);padding:7px 12px;border-radius:20px;color:var(--muted);font-size:12px}}.grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}}.panel{{background:color-mix(in srgb,var(--panel) 94%,transparent);border:1px solid var(--line);border-radius:16px;padding:20px;box-shadow:0 10px 35px #0002}}.wide{{grid-column:1/-1}}ul{{list-style:none;padding:0;margin:0}}li{{padding:12px 0;border-top:1px solid var(--line);display:flex;justify-content:space-between;gap:12px}}li span{{display:block;color:var(--muted);font-size:13px}}li strong{{font-size:14px}}.empty{{color:var(--muted);padding:12px 0}}.notes{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px}}.note{{border:1px solid var(--line);border-radius:12px;padding:14px}}.note h3{{margin:0 0 4px;font-size:15px}}.note p{{margin:0 0 12px;font-size:13px}}small{{color:var(--blue)}}button,input,textarea{{font:inherit}}button{{border:0;border-radius:9px;padding:8px 12px;background:var(--accent);color:#10221a;font-weight:650;cursor:pointer}}form{{display:grid;gap:9px;margin-top:10px}}input,textarea{{width:100%;background:#0d1425;border:1px solid var(--line);border-radius:9px;padding:10px;color:var(--text)}}textarea{{min-height:75px;resize:vertical}}.forms{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}}.formbox{{padding-top:12px}}.formbox h3{{font-size:14px;margin:0}}#results{{margin-top:10px}}@media(max-width:700px){{.grid{{grid-template-columns:1fr}}.wide{{grid-column:auto}}.forms{{grid-template-columns:1fr}}header{{align-items:flex-start}}}}
    </style></head><body><main><header><div><div class="brand">POLYMATH OS / PERSONAL WORKSPACE</div><h1>Make room for<br>what matters.</h1><p>One calm place for your goals, projects, habits, and ideas.</p></div><span class="pill">LOCAL DATA · {date.today().strftime('%d %b %Y')}</span></header>
    <section class="grid"><div class="panel"><h2>Active goals</h2><ul>{goal_cards}</ul></div><div class="panel"><h2>Projects in motion</h2><ul>{project_cards}</ul></div><div class="panel"><h2>Daily practice</h2><ul>{habits}</ul></div><div class="panel"><h2>Find anything</h2><input id="search" placeholder="Search goals, projects, notes…" oninput="searchItems(this.value)"><div id="results"></div></div><div class="panel wide"><h2>Recent notes</h2><div class="notes">{note_cards}</div></div>
    <div class="panel wide"><h2>Capture something</h2><div class="forms"><div class="formbox"><h3>New goal</h3><form onsubmit="submitForm(event,'/api/goals',['title','description'])"><input name="title" placeholder="Goal title" required maxlength="160"><textarea name="description" placeholder="What does success look like?"></textarea><button>Add goal</button></form></div><div class="formbox"><h3>New project</h3><form onsubmit="submitForm(event,'/api/projects',['title','description'])"><input name="title" placeholder="Project title" required maxlength="160"><textarea name="description" placeholder="A small next step…"></textarea><button>Add project</button></form></div><div class="formbox"><h3>New note</h3><form onsubmit="submitForm(event,'/api/notes',['title','body','tags'])"><input name="title" placeholder="Note title" required maxlength="160"><textarea name="body" placeholder="Capture an idea…"></textarea><input name="tags" placeholder="Tags, comma separated"><button>Save note</button></form></div></div><div class="formbox"><h3>Start a habit</h3><form style="grid-template-columns:1fr auto;max-width:430px" onsubmit="submitForm(event,'/api/habits',['title'])"><input name="title" placeholder="e.g. Read for 20 minutes" required maxlength="100"><button>Add habit</button></form></div></div></section>
    <p class="muted" style="text-align:center;margin-top:24px">Your workspace stays on this device. <a style="color:var(--blue)" href="/docs">Explore the API</a></p></main><script>
    async function submitForm(ev,url,keys){{ev.preventDefault();const form=ev.target;const body=Object.fromEntries(keys.map(k=>[k,form.elements[k].value]));const res=await fetch(url,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(body)}});if(!res.ok){{alert((await res.json()).detail||'Could not save');return}}location.reload()}}
    async function checkIn(id){{const res=await fetch(`/api/habits/${{id}}/check-ins`,{{method:'POST'}});if(!res.ok)alert((await res.json()).detail||'Could not check in');else location.reload()}}
    let timer;function searchItems(q){{clearTimeout(timer);const box=document.getElementById('results');if(!q.trim()){{box.innerHTML='';return}}timer=setTimeout(async()=>{{const r=await fetch('/api/search?q='+encodeURIComponent(q));const data=await r.json();box.innerHTML=Object.entries(data).map(([kind,items])=>items.map(x=>`<div class="muted"><strong>${{kind.slice(0,-1)}}:</strong> ${{escapeHtml(x.title)}}</div>`).join('')).join('')||'<div class="muted">No matches</div>'}},180)}}function escapeHtml(s){{return String(s).replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]))}}
    </script></body></html>'''
