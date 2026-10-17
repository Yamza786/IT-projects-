"""Local IT asset register and audit API."""
import os,sqlite3
from fastapi import FastAPI,HTTPException,Query
from pydantic import BaseModel,Field

DB=os.environ.get("IT_ASSET_DB","it-assets.db");app=FastAPI(title="IT Asset Management",version="1.0")
class AssetIn(BaseModel):
 tag:str=Field(min_length=2,max_length=40);name:str=Field(min_length=2,max_length=120);category:str=Field(min_length=2,max_length=60);serial:str=Field(default="",max_length=100);location:str=Field(default="",max_length=120);assigned_to:str=Field(default="",max_length=120);status:str=Field(default="in-stock",max_length=20)
def connect():
 c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;c.execute("CREATE TABLE IF NOT EXISTS assets(tag TEXT PRIMARY KEY,name TEXT,category TEXT,serial TEXT,location TEXT,assigned_to TEXT,status TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,updated_at TEXT DEFAULT CURRENT_TIMESTAMP)");c.execute("CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,tag TEXT,action TEXT,detail TEXT,at TEXT DEFAULT CURRENT_TIMESTAMP)");return c
@app.get("/")
def root():return {"service":app.title,"docs":"/docs"}
@app.post("/assets",status_code=201)
def create(body:AssetIn):
 if body.status not in {"in-stock","assigned","repair","retired"}:raise HTTPException(422,"invalid status")
 with connect() as c:
  try:c.execute("INSERT INTO assets(tag,name,category,serial,location,assigned_to,status) VALUES(?,?,?,?,?,?,?)",tuple(body.dict().values()))
  except sqlite3.IntegrityError:raise HTTPException(409,"asset tag already exists")
  c.execute("INSERT INTO audit(tag,action,detail) VALUES(?,?,?)",(body.tag,"created",body.json()));return dict(c.execute("SELECT * FROM assets WHERE tag=?",(body.tag,)).fetchone())
@app.get("/assets")
def list_assets(q:str=Query(default="",max_length=100),status:str|None=None):
 with connect() as c:
  return [dict(r) for r in c.execute("SELECT * FROM assets WHERE (tag LIKE ? OR name LIKE ? OR category LIKE ?) AND (? IS NULL OR status=?) ORDER BY tag",(f"%{q}%",f"%{q}%",f"%{q}%",status,status))]
@app.patch("/assets/{tag}")
def update(tag:str,body:dict):
 allowed={"location","assigned_to","status","name","category"};changes={k:v for k,v in body.items() if k in allowed}
 if not changes:raise HTTPException(400,"provide editable fields")
 if "status" in changes and changes["status"] not in {"in-stock","assigned","repair","retired"}:raise HTTPException(422,"invalid status")
 with connect() as c:
  if not c.execute("SELECT 1 FROM assets WHERE tag=?",(tag,)).fetchone():raise HTTPException(404,"asset not found")
  sql=", ".join(f"{key}=?" for key in changes)+", updated_at=CURRENT_TIMESTAMP";c.execute(f"UPDATE assets SET {sql} WHERE tag=?",(*changes.values(),tag));c.execute("INSERT INTO audit(tag,action,detail) VALUES(?,?,?)",(tag,"updated",str(changes)));return dict(c.execute("SELECT * FROM assets WHERE tag=?",(tag,)).fetchone())
@app.get("/audit")
def audit(tag:str|None=None):
 with connect() as c:return [dict(r) for r in c.execute("SELECT * FROM audit WHERE (? IS NULL OR tag=?) ORDER BY id DESC LIMIT 200",(tag,tag))]
