"""Accessible starter learning app with transparent topic recommendations."""

from __future__ import annotations

import html
import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

DB_PATH = Path(os.environ.get("LEARNING_DB", "learning.db"))
app = FastAPI(title="Adaptive Learning Platform", version="0.1.0")


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with closing(connect()) as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS lessons(id INTEGER PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL, tags TEXT NOT NULL DEFAULT '');
            CREATE TABLE IF NOT EXISTS questions(id INTEGER PRIMARY KEY, lesson_id INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
                prompt TEXT NOT NULL, options TEXT NOT NULL, correct_index INTEGER NOT NULL, explanation TEXT NOT NULL, tag TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS attempts(id INTEGER PRIMARY KEY, question_id INTEGER NOT NULL REFERENCES questions(id),
                selected_index INTEGER NOT NULL, is_correct INTEGER NOT NULL, created_at TEXT NOT NULL);
        """)
        if not db.execute("SELECT 1 FROM lessons LIMIT 1").fetchone():
            cur = db.execute("INSERT INTO lessons(title,body,tags) VALUES(?,?,?)", (
                "Working with evidence", "A good technical claim can be checked against reliable evidence. Record where a claim came from, when the source was published, and what it does not establish. Correlation describes a relationship between observations; by itself, it does not show that one caused the other.", "research,critical-thinking"))
            lid = cur.lastrowid
            examples = [
                ("What does a correlation alone establish?", ["That one event caused another", "That two measurements vary together", "That the data has no limitations"], 1, "Correlation describes how measurements vary together; causal evidence requires more.", "critical-thinking"),
                ("What makes a claim easier to verify?", ["A traceable source and date", "A confident tone", "Removing uncertainty"], 0, "A reader needs a traceable source and enough context to check the claim.", "research"),
            ]
            db.executemany("INSERT INTO questions(lesson_id,prompt,options,correct_index,explanation,tag) VALUES(?,?,?,?,?,?)",
                           [(lid, p, json.dumps(o), i, x, t) for p, o, i, x, t in examples])
        db.commit()


@app.on_event("startup")
def startup():
    init()


class AnswerIn(BaseModel):
    selected_index: int = Field(ge=0, le=20)


@app.get("/api/lessons")
def lessons():
    with closing(connect()) as db:
        return [dict(r) for r in db.execute("SELECT id,title,body,tags FROM lessons ORDER BY id")]


@app.get("/api/lessons/{lesson_id}/quiz")
def quiz(lesson_id: int):
    with closing(connect()) as db:
        if not db.execute("SELECT 1 FROM lessons WHERE id=?", (lesson_id,)).fetchone():
            raise HTTPException(404, "Lesson not found")
        return [{"id": r["id"], "prompt": r["prompt"], "options": json.loads(r["options"]), "tag": r["tag"]}
                for r in db.execute("SELECT id,prompt,options,tag FROM questions WHERE lesson_id=?", (lesson_id,))]


@app.post("/api/questions/{question_id}/answer")
def answer(question_id: int, item: AnswerIn):
    with closing(connect()) as db:
        question = db.execute("SELECT * FROM questions WHERE id=?", (question_id,)).fetchone()
        if not question:
            raise HTTPException(404, "Question not found")
        if item.selected_index >= len(json.loads(question["options"])):
            raise HTTPException(422, "Selected option is out of range")
        correct = item.selected_index == question["correct_index"]
        db.execute("INSERT INTO attempts(question_id,selected_index,is_correct,created_at) VALUES(?,?,?,?)",
                   (question_id, item.selected_index, int(correct), datetime.now(timezone.utc).isoformat(timespec="seconds")))
        db.commit()
        return {"correct": correct, "explanation": question["explanation"], "topic": question["tag"]}


@app.get("/api/progress")
def progress():
    with closing(connect()) as db:
        totals = db.execute("SELECT COUNT(*) AS answered,COALESCE(SUM(is_correct),0) AS correct FROM attempts").fetchone()
        topics = [dict(r) for r in db.execute("""
            SELECT q.tag,COUNT(*) AS attempts,SUM(CASE WHEN a.is_correct=0 THEN 1 ELSE 0 END) AS missed
            FROM attempts a JOIN questions q ON q.id=a.question_id GROUP BY q.tag ORDER BY missed DESC,q.tag
        """)]
    return {"answered": totals["answered"], "correct": totals["correct"],
            "accuracy_percent": round(totals["correct"] / totals["answered"] * 100, 1) if totals["answered"] else None,
            "topics": topics}


@app.get("/api/recommendations")
def recommendations():
    p = progress()
    weakest = [t for t in p["topics"] if t["missed"] > 0]
    return {"items": [{"topic": t["tag"], "reason": f"{t['missed']} missed answers across {t['attempts']} attempts"} for t in weakest[:3]],
            "rule": "Topics are ordered by missed-answer count; no opaque learner profile is built."}


@app.get("/", response_class=HTMLResponse)
def home():
    cards = "".join(f'<article><h2>{html.escape(l["title"])}</h2><p>{html.escape(l["body"])}</p><button onclick="start({l["id"]})">Practice this lesson</button></article>' for l in lessons())
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Studywell · Learning</title><style>
    *{{box-sizing:border-box}}body{{margin:0;background:#f5f7fb;color:#19253a;font:16px/1.6 system-ui,sans-serif}}main{{max-width:850px;margin:auto;padding:32px 20px}}header{{padding:24px 0}}.tag{{font-weight:700;color:#365fc2;font-size:12px;letter-spacing:.1em}}h1{{font-size:clamp(30px,5vw,44px);margin:8px 0}}article,.quiz{{background:white;border:1px solid #dfe5f0;border-radius:14px;padding:22px;margin:16px 0;box-shadow:0 8px 24px #1a2b4b0b}}p{{color:#52617a}}button{{background:#315dc2;color:white;border:0;border-radius:8px;padding:10px 14px;font:inherit;font-weight:650;cursor:pointer}}button:focus,input:focus{{outline:3px solid #a8c1ff;outline-offset:2px}}fieldset{{border:1px solid #dfe5f0;border-radius:10px;margin:14px 0;padding:14px}}label{{display:block;padding:6px}}#feedback{{font-weight:650}}@media(prefers-reduced-motion:reduce){{*{{scroll-behavior:auto!important}}}}
    </style></head><body><main><header><div class="tag">STUDYWELL · LEARN WITH EVIDENCE</div><h1>Small lessons. Clear progress.</h1><p>Practice at your pace. Your answers stay in the local database.</p></header>{cards}<section class="quiz" id="quiz" hidden><h2>Quick practice</h2><div id="questions"></div><div id="feedback" role="status" aria-live="polite"></div></section><section class="quiz"><h2>Your progress</h2><p id="progress">Loading progress…</p><ul id="topics"></ul></section><p><a href="/docs">API reference</a></p></main><script>
    async function start(id){{const r=await fetch(`/api/lessons/${{id}}/quiz`);const qs=await r.json();const box=document.getElementById('questions');document.getElementById('quiz').hidden=false;box.innerHTML=qs.map((q,i)=>`<fieldset><legend>${{i+1}}. ${{esc(q.prompt)}}</legend>${{q.options.map((o,j)=>`<label><input type="radio" name="q${{q.id}}" value="${{j}}"> ${{esc(o)}}</label>`).join('')}}<button onclick="submitAnswer(${{q.id}})">Check answer</button></fieldset>`).join('');document.getElementById('quiz').scrollIntoView()}}
    async function submitAnswer(id){{const selected=document.querySelector(`input[name="q${{id}}"]:checked`);if(!selected){{document.getElementById('feedback').textContent='Choose an answer first.';return}}const r=await fetch(`/api/questions/${{id}}/answer`,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{selected_index:Number(selected.value)}})}});const d=await r.json();document.getElementById('feedback').textContent=(d.correct?'Correct. ':'Review this topic. ')+d.explanation;loadProgress()}}
    async function loadProgress(){{const [p,r]=await Promise.all([fetch('/api/progress').then(x=>x.json()),fetch('/api/recommendations').then(x=>x.json())]);document.getElementById('progress').textContent=`${{p.answered}} answers · ${{p.accuracy_percent??'—'}}% correct`;document.getElementById('topics').innerHTML=r.items.map(x=>`<li>${{esc(x.topic)}}: ${{esc(x.reason)}}</li>`).join('')||'<li>No revision suggestions yet.</li>'}}function esc(x){{return String(x).replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]))}}loadProgress()
    </script></body></html>'''
