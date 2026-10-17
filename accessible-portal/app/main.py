"""Accessible local catalogue for reviewed, multilingual public information."""

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

DB_PATH = Path(os.environ.get("PORTAL_DB", "portal.db"))
LANGUAGES = {"en": "English", "af": "Afrikaans", "zu": "isiZulu", "xh": "isiXhosa", "st": "Sesotho", "nso": "Sepedi", "tn": "Setswana", "ss": "siSwati", "ve": "Tshivenda", "ts": "itsonga"}
app = FastAPI(title="Accessible Multilingual Services Portal", version="0.1.0")


def connect():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with closing(connect()) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS resources(
            id INTEGER PRIMARY KEY,slug TEXT NOT NULL,language TEXT NOT NULL,title TEXT NOT NULL,summary TEXT NOT NULL,
            topic TEXT NOT NULL,source_title TEXT NOT NULL,source_url TEXT NOT NULL,verified_on TEXT NOT NULL,created_at TEXT NOT NULL,
            UNIQUE(slug,language))""")
        db.commit()


@app.on_event("startup")
def startup():
    init()


class ResourceIn(BaseModel):
    slug: str = Field(min_length=1, max_length=100, regex=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    language: str = Field(min_length=2, max_length=3)
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=3000)
    topic: str = Field(min_length=1, max_length=100)
    source_title: str = Field(min_length=1, max_length=200)
    source_url: str = Field(min_length=9, max_length=1000, regex=r"^https://\S+$")
    verified_on: date


@app.get("/api/languages")
def languages():
    return [{"code": code, "name": name} for code, name in LANGUAGES.items()]


@app.get("/api/resources")
def resources(language: str | None = Query(default=None), topic: str | None = Query(default=None, max_length=100)):
    clauses, args = [], []
    if language:
        if language not in LANGUAGES:
            raise HTTPException(422, "Unsupported language code")
        clauses.append("language=?"); args.append(language)
    if topic:
        clauses.append("topic=?"); args.append(topic)
    sql = "SELECT * FROM resources" + (" WHERE " + " AND ".join(clauses) if clauses else "") + " ORDER BY topic,title,language"
    with closing(connect()) as db:
        return [dict(r) for r in db.execute(sql, tuple(args))]


@app.post("/api/resources", status_code=201)
def add_resource(item: ResourceIn):
    if item.language not in LANGUAGES:
        raise HTTPException(422, "Unsupported language code")
    with closing(connect()) as db:
        try:
            cur = db.execute("INSERT INTO resources(slug,language,title,summary,topic,source_title,source_url,verified_on,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                             (item.slug,item.language,item.title.strip(),item.summary.strip(),item.topic.strip(),item.source_title.strip(),item.source_url,item.verified_on.isoformat(),datetime.now(timezone.utc).isoformat(timespec="seconds")))
            db.commit()
        except sqlite3.IntegrityError as exc:
            raise HTTPException(409, "That resource already has an entry in this language") from exc
        return dict(db.execute("SELECT * FROM resources WHERE id=?", (cur.lastrowid,)).fetchone())


@app.get("/", response_class=HTMLResponse)
def home():
    language_options = "".join(f'<option value="{code}">{html.escape(name)}</option>' for code, name in LANGUAGES.items())
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Clearpath · Public Services</title><style>
    *{{box-sizing:border-box}}body{{margin:0;background:#eef3f4;color:#182b33;font:16px/1.6 system-ui,sans-serif}}.skip{{position:absolute;left:-999px;top:8px;background:white;padding:12px;z-index:2}}.skip:focus{{left:8px}}main{{max-width:950px;margin:auto;padding:30px 20px}}.eyebrow{{font-size:12px;letter-spacing:.12em;color:#087b71;font-weight:700}}h1{{font-size:clamp(30px,5vw,44px);margin:8px 0}}section,article{{background:white;border:1px solid #d9e3e3;border-radius:13px;padding:18px;margin:14px 0}}.filters{{display:flex;gap:10px;flex-wrap:wrap}}label{{font-weight:650}}select,input,textarea,button{{font:inherit;padding:9px;border:1px solid #aebfbe;border-radius:8px}}button{{background:#087b71;color:white;border:0;font-weight:700;cursor:pointer}}:focus-visible{{outline:3px solid #e5a900;outline-offset:3px}}.card h2{{font-size:20px;margin:0}}.card p{{color:#435a60}}.source{{font-size:13px;color:#435a60}}form{{display:grid;gap:9px;max-width:650px}}.muted{{color:#52666b}}a{{color:#075f59}}@media(max-width:600px){{main{{padding:22px 14px}}}}
    </style></head><body><a class="skip" href="#content">Skip to content</a><main id="content"><header><div class="eyebrow">CLEARPATH · PUBLIC INFORMATION</div><h1>Useful services, clearly explained.</h1><p class="muted">Browse information in your language. Each item shows its official source and last verification date.</p></header><section><h2>Find information</h2><div class="filters"><label for="language">Language</label><select id="language">{language_options}</select><label for="topic">Topic</label><input id="topic" placeholder="Optional topic filter"><button id="search">Show resources</button></div></section><div id="results" aria-live="polite"></div><details><summary>Content editor · add a reviewed resource</summary><section><form id="add"><label>Shared resource key <input name="slug" pattern="[a-z0-9]+(-[a-z0-9]+)*" required></label><label>Language <select name="language">{language_options}</select></label><label>Title <input name="title" required maxlength="200"></label><label>Summary <textarea name="summary" required maxlength="3000"></textarea></label><label>Topic <input name="topic" required maxlength="100"></label><label>Official source name <input name="source_title" required maxlength="200"></label><label>HTTPS source URL <input name="source_url" type="url" pattern="https://.*" required></label><label>Verified on <input name="verified_on" type="date" value="{date.today().isoformat()}" required></label><button>Publish resource locally</button></form></section></details><p class="muted">Translations should be checked by fluent speakers. <a href="/docs">API reference</a>.</p></main><script>
    const result=document.getElementById('results');async function load(){{result.replaceChildren();const u=new URL('/api/resources',location);u.searchParams.set('language',document.getElementById('language').value);const topic=document.getElementById('topic').value.trim();if(topic)u.searchParams.set('topic',topic);const r=await fetch(u);const rows=await r.json();if(!rows.length){{result.textContent='No reviewed resources in this language and topic yet.';return}}for(const x of rows){{const article=document.createElement('article');article.className='card';const title=document.createElement('h2');title.textContent=x.title;const summary=document.createElement('p');summary.textContent=x.summary;const source=document.createElement('p');source.className='source';source.textContent=`${{x.source_title}} · verified ${{x.verified_on}}`;const link=document.createElement('a');link.href=x.source_url;link.textContent='Open official source';article.append(title,summary,source,link);result.append(article)}}}}document.getElementById('search').onclick=load;document.getElementById('language').onchange=load;load();document.getElementById('add').onsubmit=async e=>{{e.preventDefault();const f=e.target;const body=Object.fromEntries(['slug','language','title','summary','topic','source_title','source_url','verified_on'].map(k=>[k,f[k].value]));const r=await fetch('/api/resources',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(body)}});if(r.ok){{f.reset();load();alert('Resource added.')}}else alert((await r.json()).detail||'Could not save resource')}}
    </script></body></html>'''
