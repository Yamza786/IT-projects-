"""Cited offline helpdesk API with optional OpenAI-compatible completion."""
import json, os, re, sqlite3, urllib.request
from pathlib import Path
from fastapi import FastAPI
from pydantic import BaseModel, Field

ARTICLES = [
 {"id":"net-001","title":"Check Wi-Fi connectivity","tags":["wifi","internet","network","wireless"],"steps":["Confirm airplane mode is off.","Reconnect to the approved Wi-Fi network.","Check whether another device has connectivity.","If only this device is affected, record the time and contact IT."]},
 {"id":"acct-001","title":"Account sign-in troubleshooting","tags":["password","login","sign in","account","mfa"],"steps":["Check the account identifier and keyboard layout.","Use the organization's password reset page; never share a password or MFA code.","If MFA prompts are unexpected, stop and report them to IT."]},
 {"id":"print-001","title":"Printer queue checks","tags":["printer","print","queue"],"steps":["Confirm the selected printer and that it is online.","Check for a paused queue or paper/toner warning.","Retry one small test page; report repeated failures to IT."]},
 {"id":"slow-001","title":"Slow computer first checks","tags":["slow","performance","computer","pc"],"steps":["Save your work and note when the slowdown began.","Check for an approved restart or update notice.","Do not install cleanup tools; contact IT with the affected application and time."]},
]
DB = os.environ.get("HELPDESK_DB", "helpdesk.db")
app=FastAPI(title="AI IT Helpdesk Assistant", version="1.0")
class Question(BaseModel): question:str=Field(min_length=3,max_length=1000)
class Ticket(BaseModel): title:str=Field(min_length=3,max_length=160); description:str=Field(min_length=3,max_length=3000); requester:str=Field(default="local-user",max_length=100)
def db():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row
 c.execute("CREATE TABLE IF NOT EXISTS tickets(id INTEGER PRIMARY KEY,title TEXT,description TEXT,requester TEXT,status TEXT DEFAULT 'open',created_at TEXT DEFAULT CURRENT_TIMESTAMP)"); return c
def search(q):
 words=set(re.findall(r"[a-z0-9]+",q.lower())); ranked=[]
 for item in ARTICLES:
  text=" ".join([item["title"],*item["tags"],*item["steps"]]).lower(); score=sum(1 for w in words if w in text)
  if score: ranked.append((score,item))
 return [x[1] for x in sorted(ranked,key=lambda x:(-x[0],x[1]["id"]))[:3]]
@app.get("/")
def home(): return {"name":app.title,"mode":"offline keyword retrieval","docs":"/docs"}
@app.post("/ask")
def ask(body:Question):
 refs=search(body.question)
 answer="I couldn't find a matching approved article. Please contact your IT support team." if not refs else "\n\n".join(f"{a['title']} ({a['id']}): " + " ".join(a["steps"]) for a in refs)
 remote_enabled=bool(os.environ.get("LLM_BASE_URL") and os.environ.get("LLM_API_KEY") and os.environ.get("LLM_MODEL"))
 if refs and remote_enabled:
  payload={"model":os.environ["LLM_MODEL"],"messages":[{"role":"system","content":"Answer only from supplied support articles. If they do not answer the question, say contact IT. Do not request credentials."},{"role":"user","content":json.dumps({"question":body.question,"articles":refs})}],"temperature":0}
  req=urllib.request.Request(os.environ["LLM_BASE_URL"].rstrip("/")+"/chat/completions",data=json.dumps(payload).encode(),headers={"Authorization":"Bearer "+os.environ["LLM_API_KEY"],"Content-Type":"application/json"})
  with urllib.request.urlopen(req,timeout=12) as response: answer=json.load(response)["choices"][0]["message"]["content"]
 return {"answer":answer,"sources":[{"id":a["id"],"title":a["title"]} for a in refs],"mode":"remote-grounded" if remote_enabled and refs else "offline"}
@app.post("/tickets")
def ticket(body:Ticket):
 with db() as c: cur=c.execute("INSERT INTO tickets(title,description,requester) VALUES(?,?,?)",(body.title,body.description,body.requester)); return {"id":cur.lastrowid,"status":"open"}
@app.get("/tickets")
def tickets():
 with db() as c:return [dict(r) for r in c.execute("SELECT * FROM tickets ORDER BY id DESC")]
