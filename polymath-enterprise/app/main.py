"""Integrated SME capstone with RBAC, audit records, and explainable reports."""

from __future__ import annotations

import hmac
import json
import os
import sqlite3
from contextlib import closing
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import median
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field

DB_PATH = Path(os.environ.get("ENTERPRISE_DB", "enterprise.db"))
KEYS = {"reader": os.environ.get("ENTERPRISE_READER_KEY", ""),
        "manager": os.environ.get("ENTERPRISE_MANAGER_KEY", ""),
        "admin": os.environ.get("ENTERPRISE_ADMIN_KEY", "")}
app = FastAPI(title="Polymath Enterprise", version="0.1.0")
RANK = {"reader": 1, "manager": 2, "admin": 3}


def connect():
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    return db


def initialize():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with closing(connect()) as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS customers(id INTEGER PRIMARY KEY,name TEXT NOT NULL,email TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY,sku TEXT NOT NULL UNIQUE,name TEXT NOT NULL,
                price_cents INTEGER NOT NULL CHECK(price_cents>=0),stock INTEGER NOT NULL CHECK(stock>=0),active INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE IF NOT EXISTS sales(id INTEGER PRIMARY KEY,customer_id INTEGER NOT NULL REFERENCES customers(id),
                day TEXT NOT NULL,total_cents INTEGER NOT NULL CHECK(total_cents>=0),created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sale_items(id INTEGER PRIMARY KEY,sale_id INTEGER NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
                product_id INTEGER NOT NULL REFERENCES products(id),product_name TEXT NOT NULL,quantity INTEGER NOT NULL CHECK(quantity>0),unit_price_cents INTEGER NOT NULL CHECK(unit_price_cents>=0));
            CREATE TABLE IF NOT EXISTS expenses(id INTEGER PRIMARY KEY,category TEXT NOT NULL,amount_cents INTEGER NOT NULL CHECK(amount_cents>0),
                memo TEXT NOT NULL DEFAULT '',day TEXT NOT NULL,created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS stock_ledger(id INTEGER PRIMARY KEY,product_id INTEGER NOT NULL REFERENCES products(id),
                delta INTEGER NOT NULL,reason TEXT NOT NULL,created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS audit_log(id INTEGER PRIMARY KEY,actor_role TEXT NOT NULL,event TEXT NOT NULL,
                entity TEXT NOT NULL,entity_id INTEGER NOT NULL,detail TEXT NOT NULL,created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS security_reports(id INTEGER PRIMARY KEY,input_sha256 TEXT NOT NULL UNIQUE,
                event_count INTEGER NOT NULL,created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS security_alerts(id INTEGER PRIMARY KEY,report_id INTEGER NOT NULL REFERENCES security_reports(id) ON DELETE CASCADE,
                rule TEXT NOT NULL,severity TEXT NOT NULL,source TEXT NOT NULL,failure_count INTEGER NOT NULL,success_count INTEGER NOT NULL,
                evidence_lines TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS research_evidence(id INTEGER PRIMARY KEY,title TEXT NOT NULL,locator TEXT NOT NULL,
                excerpt TEXT NOT NULL,document_id INTEGER,created_at TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS sales_day_idx ON sales(day);
            CREATE INDEX IF NOT EXISTS expenses_day_idx ON expenses(day);
        """)
        db.commit()


@app.on_event("startup")
def startup():
    configured=[value for value in KEYS.values() if value]
    if len(configured)!=len(set(configured)):
        raise RuntimeError("Enterprise role keys must be unique")
    initialize()


def require_role(minimum: str):
    def dependency(x_api_key: str | None = Header(default=None, alias="X-API-Key")):
        if not x_api_key:
            raise HTTPException(401, "X-API-Key is required")
        for role, configured in KEYS.items():
            if configured and hmac.compare_digest(x_api_key, configured) and RANK[role] >= RANK[minimum]:
                return {"role": role}
        raise HTTPException(403, "API key does not have the required role")
    return dependency


def audit(db, actor: dict, event: str, entity: str, entity_id: int, detail: str):
    db.execute("INSERT INTO audit_log(actor_role,event,entity,entity_id,detail,created_at) VALUES(?,?,?,?,?,?)",
               (actor["role"],event,entity,entity_id,detail,datetime.now(timezone.utc).isoformat(timespec="seconds")))


class CustomerIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    email: str = Field(default="", max_length=254)


class ProductIn(BaseModel):
    sku: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=1, max_length=160)
    price_cents: int = Field(ge=0, le=10_000_000_000)
    opening_stock: int = Field(ge=0, le=10_000_000)


class StockChangeIn(BaseModel):
    delta: int = Field(ge=-1_000_000, le=1_000_000)
    reason: str = Field(min_length=3, max_length=300)


class SaleLineIn(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0, le=1_000_000)


class SaleIn(BaseModel):
    customer_id: int = Field(gt=0)
    day: date = Field(default_factory=date.today)
    items: list[SaleLineIn] = Field(min_items=1, max_items=100)


class ExpenseIn(BaseModel):
    category: str = Field(min_length=1, max_length=100)
    amount_cents: int = Field(gt=0, le=10_000_000_000)
    memo: str = Field(default="", max_length=500)
    day: date = Field(default_factory=date.today)


class SecurityAlertIn(BaseModel):
    rule: str = Field(min_length=1,max_length=100)
    severity: Literal["low","medium","high"]
    source: str = Field(min_length=1,max_length=100)
    failure_count: int = Field(ge=0)
    success_count: int = Field(ge=0)
    evidence_lines: list[int] = Field(default_factory=list,max_items=1000)


class SecurityReportIn(BaseModel):
    input_sha256: str = Field(regex=r"^[0-9a-fA-F]{64}$")
    events_parsed: int = Field(ge=0)
    alerts: list[SecurityAlertIn] = Field(default_factory=list,max_items=10000)


class ResearchEvidenceIn(BaseModel):
    title: str = Field(min_length=1,max_length=300)
    locator: str = Field(min_length=1,max_length=1000)
    excerpt: str = Field(min_length=1,max_length=5000)
    document_id: int | None = Field(default=None,gt=0)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/customers")
def get_customers(_: dict = Depends(require_role("reader"))):
    with closing(connect()) as db:
        return [dict(r) for r in db.execute("SELECT id,name,email,created_at FROM customers ORDER BY name")]


@app.post("/api/customers", status_code=201)
def add_customer(item: CustomerIn, actor: dict = Depends(require_role("manager"))):
    with closing(connect()) as db:
        cur = db.execute("INSERT INTO customers(name,email,created_at) VALUES(?,?,?)",
                         (item.name.strip(),item.email.strip(),datetime.now(timezone.utc).isoformat(timespec="seconds")))
        audit(db,actor,"customer_created","customer",cur.lastrowid,"Customer record created")
        db.commit()
        return dict(db.execute("SELECT * FROM customers WHERE id=?", (cur.lastrowid,)).fetchone())


@app.get("/api/products")
def get_products(_: dict = Depends(require_role("reader"))):
    with closing(connect()) as db:
        return [dict(r) for r in db.execute("SELECT * FROM products WHERE active=1 ORDER BY name")]


@app.post("/api/products", status_code=201)
def add_product(item: ProductIn, actor: dict = Depends(require_role("manager"))):
    with closing(connect()) as db:
        try:
            cur = db.execute("INSERT INTO products(sku,name,price_cents,stock) VALUES(?,?,?,?)",
                             (item.sku.strip().upper(),item.name.strip(),item.price_cents,item.opening_stock))
        except sqlite3.IntegrityError as exc:
            raise HTTPException(409,"SKU already exists") from exc
        product_id = cur.lastrowid
        if item.opening_stock:
            db.execute("INSERT INTO stock_ledger(product_id,delta,reason,created_at) VALUES(?,?,?,?)",
                       (product_id,item.opening_stock,"opening stock",datetime.now(timezone.utc).isoformat(timespec="seconds")))
        audit(db,actor,"product_created","product",product_id,f"SKU {item.sku.strip().upper()} created")
        db.commit()
        return dict(db.execute("SELECT * FROM products WHERE id=?",(product_id,)).fetchone())


@app.post("/api/products/{product_id}/stock", status_code=201)
def change_stock(product_id: int, item: StockChangeIn, actor: dict = Depends(require_role("manager"))):
    if item.delta == 0:
        raise HTTPException(422, "Stock adjustment cannot be zero")
    with closing(connect()) as db:
        db.execute("BEGIN IMMEDIATE")
        product = db.execute("SELECT * FROM products WHERE id=? AND active=1",(product_id,)).fetchone()
        if not product:
            db.rollback(); raise HTTPException(404,"Product not found")
        if product["stock"] + item.delta < 0:
            db.rollback(); raise HTTPException(409,"Stock cannot become negative")
        db.execute("UPDATE products SET stock=stock+? WHERE id=?",(item.delta,product_id))
        db.execute("INSERT INTO stock_ledger(product_id,delta,reason,created_at) VALUES(?,?,?,?)",
                   (product_id,item.delta,item.reason.strip(),datetime.now(timezone.utc).isoformat(timespec="seconds")))
        audit(db,actor,"stock_adjusted","product",product_id,f"Stock delta {item.delta}: {item.reason.strip()}")
        db.commit()
        return dict(db.execute("SELECT * FROM products WHERE id=?",(product_id,)).fetchone())


@app.post("/api/sales", status_code=201)
def create_sale(item: SaleIn, actor: dict = Depends(require_role("manager"))):
    quantities: dict[int,int] = {}
    for line in item.items:
        quantities[line.product_id] = quantities.get(line.product_id,0) + line.quantity
    with closing(connect()) as db:
        db.execute("BEGIN IMMEDIATE")
        if not db.execute("SELECT 1 FROM customers WHERE id=?",(item.customer_id,)).fetchone():
            db.rollback(); raise HTTPException(404,"Customer not found")
        product_lines, total = [], 0
        for product_id, quantity in quantities.items():
            product = db.execute("SELECT * FROM products WHERE id=? AND active=1",(product_id,)).fetchone()
            if not product:
                db.rollback(); raise HTTPException(404,f"Product {product_id} not found")
            if product["stock"] < quantity:
                db.rollback(); raise HTTPException(409,f"Insufficient stock for product {product_id}")
            product_lines.append((product,quantity))
            total += product["price_cents"] * quantity
        cur = db.execute("INSERT INTO sales(customer_id,day,total_cents,created_at) VALUES(?,?,?,?)",
                         (item.customer_id,item.day.isoformat(),total,datetime.now(timezone.utc).isoformat(timespec="seconds")))
        sale_id = cur.lastrowid
        for product,quantity in product_lines:
            db.execute("INSERT INTO sale_items(sale_id,product_id,product_name,quantity,unit_price_cents) VALUES(?,?,?,?,?)",
                       (sale_id,product["id"],product["name"],quantity,product["price_cents"]))
            db.execute("UPDATE products SET stock=stock-? WHERE id=?",(quantity,product["id"]))
            db.execute("INSERT INTO stock_ledger(product_id,delta,reason,created_at) VALUES(?,?,?,?)",
                       (product["id"],-quantity,f"sale {sale_id}",datetime.now(timezone.utc).isoformat(timespec="seconds")))
        audit(db,actor,"sale_recorded","sale",sale_id,f"{len(product_lines)} product line(s), total {total} cents")
        db.commit()
        return {"id":sale_id,"customer_id":item.customer_id,"day":item.day.isoformat(),"total_cents":total,
                "items":[{"product_id":p["id"],"name":p["name"],"quantity":q,"unit_price_cents":p["price_cents"]} for p,q in product_lines]}


@app.post("/api/expenses", status_code=201)
def add_expense(item: ExpenseIn, actor: dict = Depends(require_role("manager"))):
    with closing(connect()) as db:
        cur = db.execute("INSERT INTO expenses(category,amount_cents,memo,day,created_at) VALUES(?,?,?,?,?)",
                         (item.category.strip(),item.amount_cents,item.memo.strip(),item.day.isoformat(),datetime.now(timezone.utc).isoformat(timespec="seconds")))
        audit(db,actor,"expense_recorded","expense",cur.lastrowid,f"{item.amount_cents} cents in {item.category.strip()}")
        db.commit()
        return dict(db.execute("SELECT * FROM expenses WHERE id=?",(cur.lastrowid,)).fetchone())


def report_data(month: str):
    with closing(connect()) as db:
        sales = db.execute("SELECT COALESCE(SUM(total_cents),0) FROM sales WHERE substr(day,1,7)=?",(month,)).fetchone()[0]
        expenses = db.execute("SELECT COALESCE(SUM(amount_cents),0) FROM expenses WHERE substr(day,1,7)=?",(month,)).fetchone()[0]
        categories = [dict(r) for r in db.execute("SELECT category,SUM(amount_cents) AS total_cents,COUNT(*) AS count FROM expenses WHERE substr(day,1,7)=? GROUP BY category ORDER BY total_cents DESC",(month,))]
        monthly_expenses = [dict(r) for r in db.execute("SELECT id,category,amount_cents,day FROM expenses WHERE substr(day,1,7)=? ORDER BY category,amount_cents",(month,))]
        low_stock = [dict(r) for r in db.execute("SELECT sku,name,stock FROM products WHERE active=1 AND stock<=2 ORDER BY stock,name")]
        evidence = [dict(r) for r in db.execute("SELECT id,title,locator,excerpt,document_id,created_at FROM research_evidence ORDER BY id DESC LIMIT 20")]
    grouped: dict[str,list[dict]] = {}
    for entry in monthly_expenses:
        grouped.setdefault(entry["category"],[]).append(entry)
    candidates=[]
    for category, entries in grouped.items():
        values=[entry["amount_cents"] for entry in entries]
        if len(values) < 5:
            continue
        center=median(values)
        mad=median([abs(value-center) for value in values])
        if mad == 0:
            continue
        for entry in entries:
            score=0.6745*(entry["amount_cents"]-center)/mad
            if score > 3.5:
                candidates.append({"expense_id":entry["id"],"category":category,"amount_cents":entry["amount_cents"],
                                   "median_cents":center,"modified_z_score":round(score,2),
                                   "reason":"Amount is more than 3.5 robust standard deviations above this month's category median."})
    return {"month":month,"sales_revenue_cents":sales,"expenses_cents":expenses,"operating_balance_cents":sales-expenses,
            "expense_categories":categories,"low_stock_products":low_stock,"expense_anomaly_candidates":candidates,
            "supporting_sources":evidence,
            "method":"Modified z-score using category median and median absolute deviation; minimum five observations per category. Candidates require human review and are not findings of misconduct."}


@app.get("/api/report")
def report(month: str = Query(regex=r"^\d{4}-\d{2}$"), _: dict = Depends(require_role("reader"))):
    return report_data(month)


@app.get("/api/audit")
def get_audit(limit: int = 100, _: dict = Depends(require_role("admin"))):
    if not 1 <= limit <= 500:
        raise HTTPException(422,"limit must be between 1 and 500")
    with closing(connect()) as db:
        return [dict(r) for r in db.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?",(limit,))]


@app.get("/api/stock-ledger")
def stock_ledger(product_id: int | None = None, _: dict = Depends(require_role("reader"))):
    with closing(connect()) as db:
        if product_id:
            return [dict(r) for r in db.execute("SELECT * FROM stock_ledger WHERE product_id=? ORDER BY id DESC",(product_id,))]
        return [dict(r) for r in db.execute("SELECT * FROM stock_ledger ORDER BY id DESC LIMIT 500")]


@app.post("/api/security-reports", status_code=201)
def import_security_report(item: SecurityReportIn, actor: dict = Depends(require_role("admin"))):
    with closing(connect()) as db:
        try:
            cur=db.execute("INSERT INTO security_reports(input_sha256,event_count,created_at) VALUES(?,?,?)",
                           (item.input_sha256.lower(),item.events_parsed,datetime.now(timezone.utc).isoformat(timespec="seconds")))
        except sqlite3.IntegrityError:
            raise HTTPException(409,"This log file hash has already been imported")
        report_id=cur.lastrowid
        db.executemany("INSERT INTO security_alerts(report_id,rule,severity,source,failure_count,success_count,evidence_lines) VALUES(?,?,?,?,?,?,?)",
                       [(report_id,a.rule,a.severity,a.source,a.failure_count,a.success_count,",".join(str(n) for n in a.evidence_lines)) for a in item.alerts])
        audit(db,actor,"security_report_imported","security_report",report_id,f"{len(item.alerts)} alert(s), {item.events_parsed} parsed events")
        db.commit()
    return {"id":report_id,"input_sha256":item.input_sha256.lower(),"alerts_imported":len(item.alerts)}


@app.get("/api/security-reports")
def get_security_reports(limit: int = 50, _: dict = Depends(require_role("reader"))):
    if not 1 <= limit <= 200:
        raise HTTPException(422,"limit must be between 1 and 200")
    with closing(connect()) as db:
        reports=[dict(r) for r in db.execute("SELECT * FROM security_reports ORDER BY id DESC LIMIT ?",(limit,))]
        for report in reports:
            report["alerts"]=[dict(a) for a in db.execute("SELECT * FROM security_alerts WHERE report_id=? ORDER BY severity DESC,id",(report["id"],))]
    return reports


@app.post("/api/research-evidence",status_code=201)
def add_research_evidence(item: ResearchEvidenceIn,actor: dict = Depends(require_role("manager"))):
    with closing(connect()) as db:
        cur=db.execute("INSERT INTO research_evidence(title,locator,excerpt,document_id,created_at) VALUES(?,?,?,?,?)",
                       (item.title.strip(),item.locator.strip(),item.excerpt.strip(),item.document_id,datetime.now(timezone.utc).isoformat(timespec="seconds")))
        audit(db,actor,"research_evidence_added","research_evidence",cur.lastrowid,"Source passage added for report context")
        db.commit()
        return dict(db.execute("SELECT * FROM research_evidence WHERE id=?",(cur.lastrowid,)).fetchone())


@app.get("/api/research-evidence")
def get_research_evidence(_: dict = Depends(require_role("reader"))):
    with closing(connect()) as db:
        return [dict(r) for r in db.execute("SELECT * FROM research_evidence ORDER BY id DESC LIMIT 100")]


@app.get("/api/integration-feed")
def integration_feed(after_id: int = 0, limit: int = 100, _: dict = Depends(require_role("reader"))):
    if after_id < 0 or not 1 <= limit <= 500:
        raise HTTPException(422,"after_id must be nonnegative and limit between 1 and 500")
    event_names={"sale_recorded":"sales.completed","expense_recorded":"expenses.recorded",
                 "stock_adjusted":"inventory.adjusted","product_created":"inventory.product-created"}
    with closing(connect()) as db:
        entries=[dict(r) for r in db.execute("SELECT * FROM audit_log WHERE id>? ORDER BY id LIMIT ?",(after_id,limit))]
    return [{"source":"polymath-enterprise","external_id":f"audit-{entry['id']}",
             "idempotency_key":f"polymath-enterprise-audit-{entry['id']}",
             "kind":event_names.get(entry["event"],"audit."+entry["event"]),
             "occurred_at":entry["created_at"],
             "payload":{"entity":entry["entity"],"entity_id":entry["entity_id"],"detail":entry["detail"],"actor_role":entry["actor_role"]}}
            for entry in entries]


@app.get("/api/backup")
def export_backup(_: dict = Depends(require_role("admin"))):
    """Create a consistent read-only JSON backup for restore drills."""
    tables=("customers","products","sales","sale_items","expenses","stock_ledger","audit_log",
            "security_reports","security_alerts","research_evidence")
    with closing(connect()) as db:
        db.execute("BEGIN")
        snapshot={table:[dict(row) for row in db.execute(f"SELECT * FROM {table} ORDER BY id")] for table in tables}
        db.commit()
    payload={"format":"polymath-enterprise-backup-v1","created_at":datetime.now(timezone.utc).isoformat(timespec="seconds"),"data":snapshot}
    return Response(json.dumps(payload,ensure_ascii=False,indent=2),media_type="application/json",
                    headers={"Content-Disposition":"attachment; filename=polymath-enterprise-backup.json","Cache-Control":"no-store"})


@app.get("/",response_class=HTMLResponse)
def home():
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Polymath Enterprise</title><style>
    *{box-sizing:border-box}body{margin:0;background:#101712;color:#edf4ed;font:15px/1.5 system-ui,sans-serif}main{max-width:1050px;margin:auto;padding:30px 18px}.tag{color:#8be3a9;font-size:12px;font-weight:700;letter-spacing:.13em}h1{font-size:clamp(30px,5vw,44px);margin:8px 0}p,.muted{color:#a2b0a5}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}section{background:#1a251d;border:1px solid #314638;border-radius:13px;padding:18px}h2{font-size:17px;margin:0 0 12px}label{font-weight:650;display:block;margin:9px 0 5px}input,textarea,button{font:inherit;width:100%;padding:10px;border:1px solid #405449;border-radius:8px;background:#101a14;color:#edf4ed}textarea{min-height:120px}button{background:#8be3a9;border:0;color:#132218;font-weight:700;cursor:pointer;margin-top:9px}pre{white-space:pre-wrap;word-break:break-word;max-height:430px;overflow:auto;background:#0c120e;border-radius:8px;padding:12px;color:#c8f2d4}#status{min-height:1.5em}.wide{grid-column:1/-1}@media(max-width:700px){.grid{grid-template-columns:1fr}.wide{grid-column:auto}}
    </style></head><body><main><div class="tag">POLYMATH ENTERPRISE · SMALL BUSINESS WORKSPACE</div><h1>Operations with a clear audit trail.</h1><p>Enter a role key to manage business records. Keys are used in this browser tab only; this local app does not store them.</p><section><label for="key">Reader, manager, or admin API key</label><input id="key" type="password" autocomplete="off"><button id="connect">Load workspace</button><p id="status" role="status" aria-live="polite"></p></section><div class="grid"><section><h2>Monthly report</h2><label for="month">Month</label><input id="month" type="month"><button onclick="loadReport()">Load analytics</button><pre id="report">Connect to load this month's sales, expenses, stock, and anomaly candidates.</pre></section><section><h2>Products and stock</h2><form id="product"><label>SKU</label><input name="sku" required><label>Product name</label><input name="name" required><label>Unit price in cents</label><input name="price_cents" type="number" min="0" required><label>Opening stock</label><input name="opening_stock" type="number" min="0" required><button>Add product</button></form></section><section><h2>Customer</h2><form id="customer"><label>Name</label><input name="name" required><label>Email</label><input name="email" type="email"><button>Add customer</button></form></section><section><h2>Record a sale</h2><form id="sale"><label>Customer ID</label><input name="customer_id" type="number" min="1" required><label>Product ID</label><input name="product_id" type="number" min="1" required><label>Quantity</label><input name="quantity" type="number" min="1" required><button>Complete sale and deduct stock</button></form></section><section><h2>Operating expense</h2><form id="expense"><label>Category</label><input name="category" required><label>Amount in cents</label><input name="amount_cents" type="number" min="1" required><label>Memo</label><input name="memo"><button>Record expense</button></form></section><section><h2>Security report import</h2><p>Paste JSON exported by the SSH Log Analyzer. Requires an admin key.</p><form id="security"><label>Analyzer report JSON</label><textarea name="body" required></textarea><button>Import report</button></form><pre id="security-result"></pre></section><section class="wide"><h2>Workspace data</h2><button onclick="loadWorkspace()">Refresh products and customers</button><pre id="workspace">Connect to load current records.</pre></section><section class="wide"><h2>Integration feed</h2><button onclick="loadFeed()">Load canonical events for the Integration Hub</button><pre id="feed">Events include stable IDs for safe retries.</pre></section></div><p class="muted">Money uses integer cents. Outlier candidates are review prompts, not findings. <a style="color:#8be3a9" href="/docs">API reference</a> · <a style="color:#8be3a9" href="/health">Health</a></p></main><script>
    const month=document.getElementById('month');month.value=new Date().toISOString().slice(0,7);function headers(){return {'Content-Type':'application/json','X-API-Key':document.getElementById('key').value}}async function call(url,method='GET',body){const r=await fetch(url,{method,headers:headers(),...(body===undefined?{}:{body:JSON.stringify(body)})});const d=await r.json();if(!r.ok)throw Error(d.detail||'Request failed');return d}async function connect(){try{await call('/api/products');document.getElementById('status').textContent='Connected. Role permissions apply to each action.';await loadWorkspace()}catch(e){document.getElementById('status').textContent=e.message}}document.getElementById('connect').onclick=connect;async function loadWorkspace(){try{const [p,c]=await Promise.all([call('/api/products'),call('/api/customers')]);document.getElementById('workspace').textContent=JSON.stringify({products:p,customers:c},null,2)}catch(e){document.getElementById('status').textContent=e.message}}async function loadReport(){try{const d=await call('/api/report?month='+encodeURIComponent(month.value));document.getElementById('report').textContent=JSON.stringify(d,null,2)}catch(e){document.getElementById('report').textContent=e.message}}async function loadFeed(){try{document.getElementById('feed').textContent=JSON.stringify(await call('/api/integration-feed'),null,2)}catch(e){document.getElementById('feed').textContent=e.message}}function bindForm(id,endpoint,makeBody,onSuccess){document.getElementById(id).onsubmit=async e=>{e.preventDefault();try{const data=await call(endpoint,'POST',makeBody(new FormData(e.target)));onSuccess?.(data);document.getElementById('status').textContent='Saved successfully.';e.target.reset()}catch(err){document.getElementById('status').textContent=err.message}}}bindForm('product','/api/products',f=>({sku:f.get('sku'),name:f.get('name'),price_cents:Number(f.get('price_cents')),opening_stock:Number(f.get('opening_stock'))}));bindForm('customer','/api/customers',f=>({name:f.get('name'),email:f.get('email')}));bindForm('sale','/api/sales',f=>({customer_id:Number(f.get('customer_id')),items:[{product_id:Number(f.get('product_id')),quantity:Number(f.get('quantity'))}]}),d=>document.getElementById('report').textContent=JSON.stringify(d,null,2));bindForm('expense','/api/expenses',f=>({category:f.get('category'),amount_cents:Number(f.get('amount_cents')),memo:f.get('memo')}));document.getElementById('security').onsubmit=async e=>{e.preventDefault();try{const body=JSON.parse(e.target.body.value);document.getElementById('security-result').textContent=JSON.stringify(await call('/api/security-reports','POST',body),null,2)}catch(err){document.getElementById('security-result').textContent=err.message}};
    </script></body></html>'''
