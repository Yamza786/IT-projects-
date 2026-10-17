"""Small business inventory and invoicing demo with atomic stock handling."""

from __future__ import annotations

import html
import hmac
import os
import sqlite3
from contextlib import closing
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

DB_PATH = Path(os.environ.get("SME_DB", "sme.db"))
app = FastAPI(title="SME Business Management", version="0.1.0")
ROLE_KEYS = {"reader":os.environ.get("SME_READER_KEY",""),"manager":os.environ.get("SME_MANAGER_KEY",""),"admin":os.environ.get("SME_ADMIN_KEY","")}
ROLE_RANK = {"reader":1,"manager":2,"admin":3}


def require_role(minimum: str):
    def dependency(x_api_key: str | None = Header(default=None,alias="X-API-Key")):
        configured=[(role,key) for role,key in ROLE_KEYS.items() if key]
        if not configured:
            return {"role":"local_dev"}
        if not x_api_key:
            raise HTTPException(401,"X-API-Key is required")
        for role,key in configured:
            if hmac.compare_digest(x_api_key,key) and ROLE_RANK[role]>=ROLE_RANK[minimum]:
                return {"role":role}
        raise HTTPException(403,"API key does not have the required role")
    return dependency


def connect():
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    return db


def initialize():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with closing(connect()) as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY, sku TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
                unit_price_cents INTEGER NOT NULL CHECK(unit_price_cents>=0), stock INTEGER NOT NULL CHECK(stock>=0),
                reorder_at INTEGER NOT NULL DEFAULT 0 CHECK(reorder_at>=0), active INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE IF NOT EXISTS customers(id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL DEFAULT '',
                phone TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS invoices(id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL REFERENCES customers(id),
                status TEXT NOT NULL CHECK(status IN ('draft','issued','paid','void')), created_at TEXT NOT NULL, paid_at TEXT);
            CREATE TABLE IF NOT EXISTS invoice_items(id INTEGER PRIMARY KEY, invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
                product_id INTEGER NOT NULL REFERENCES products(id), description TEXT NOT NULL, quantity INTEGER NOT NULL CHECK(quantity>0),
                unit_price_cents INTEGER NOT NULL CHECK(unit_price_cents>=0));
            CREATE TABLE IF NOT EXISTS stock_ledger(id INTEGER PRIMARY KEY,product_id INTEGER NOT NULL REFERENCES products(id),
                delta INTEGER NOT NULL,reason TEXT NOT NULL,created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS audit_log(id INTEGER PRIMARY KEY, event TEXT NOT NULL, entity TEXT NOT NULL,
                entity_id INTEGER NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS invoice_status_idx ON invoices(status,created_at);
        """)
        db.commit()


@app.on_event("startup")
def startup():
    configured=[key for key in ROLE_KEYS.values() if key]
    if len(configured)!=len(set(configured)):
        raise RuntimeError("SME role keys must be unique")
    initialize()


class ProductIn(BaseModel):
    sku: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=1, max_length=160)
    unit_price_cents: int = Field(ge=0, le=10_000_000_000)
    stock: int = Field(ge=0, le=10_000_000)
    reorder_at: int = Field(default=0, ge=0)


class CustomerIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    email: str = Field(default="", max_length=254)
    phone: str = Field(default="", max_length=50)


class LineIn(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0, le=1_000_000)


class InvoiceIn(BaseModel):
    customer_id: int = Field(gt=0)
    items: list[LineIn] = Field(min_items=1, max_items=100)


class StockAdjustmentIn(BaseModel):
    delta: int = Field(ge=-1_000_000, le=1_000_000)
    reason: str = Field(min_length=3, max_length=300)


def audit(db, event: str, entity: str, entity_id: int, detail: str):
    db.execute("INSERT INTO audit_log(event,entity,entity_id,detail,created_at) VALUES(?,?,?,?,?)",
               (event, entity, entity_id, detail, datetime.now(timezone.utc).isoformat(timespec="seconds")))


@app.get("/api/products")
def products(_: dict = Depends(require_role("reader"))):
    with closing(connect()) as db:
        return [dict(r) for r in db.execute("SELECT * FROM products WHERE active=1 ORDER BY name")]


@app.post("/api/products", status_code=201)
def add_product(item: ProductIn, actor: dict = Depends(require_role("manager"))):
    with closing(connect()) as db:
        try:
            cur = db.execute("INSERT INTO products(sku,name,unit_price_cents,stock,reorder_at) VALUES(?,?,?,?,?)",
                             (item.sku.strip().upper(), item.name.strip(), item.unit_price_cents, item.stock, item.reorder_at))
            audit(db, "product_created", "product", cur.lastrowid, f"{actor['role']} created SKU {item.sku.strip().upper()}; opening stock {item.stock}")
            if item.stock:
                db.execute("INSERT INTO stock_ledger(product_id,delta,reason,created_at) VALUES(?,?,?,?)",
                           (cur.lastrowid,item.stock,"opening stock",datetime.now(timezone.utc).isoformat(timespec="seconds")))
            db.commit()
            return dict(db.execute("SELECT * FROM products WHERE id=?", (cur.lastrowid,)).fetchone())
        except sqlite3.IntegrityError as exc:
            raise HTTPException(409, "SKU already exists") from exc


@app.get("/api/customers")
def customers(_: dict = Depends(require_role("reader"))):
    with closing(connect()) as db:
        return [dict(r) for r in db.execute("SELECT id,name,email,phone,created_at FROM customers ORDER BY name")]


@app.post("/api/customers", status_code=201)
def add_customer(item: CustomerIn, actor: dict = Depends(require_role("manager"))):
    with closing(connect()) as db:
        cur = db.execute("INSERT INTO customers(name,email,phone,created_at) VALUES(?,?,?,?)",
                         (item.name.strip(), item.email.strip(), item.phone.strip(), datetime.now(timezone.utc).isoformat(timespec="seconds")))
        audit(db,"customer_created","customer",cur.lastrowid,f"{actor['role']} created customer record")
        db.commit()
        return dict(db.execute("SELECT * FROM customers WHERE id=?", (cur.lastrowid,)).fetchone())


@app.post("/api/invoices", status_code=201)
def create_invoice(item: InvoiceIn, actor: dict = Depends(require_role("manager"))):
    with closing(connect()) as db:
        if not db.execute("SELECT 1 FROM customers WHERE id=?", (item.customer_id,)).fetchone():
            raise HTTPException(404, "Customer not found")
        cur = db.execute("INSERT INTO invoices(customer_id,status,created_at) VALUES(?,'draft',?)",
                         (item.customer_id, datetime.now(timezone.utc).isoformat(timespec="seconds")))
        invoice_id = cur.lastrowid
        try:
            for line in item.items:
                product = db.execute("SELECT * FROM products WHERE id=? AND active=1", (line.product_id,)).fetchone()
                if not product:
                    raise HTTPException(404, f"Product {line.product_id} not found")
                db.execute("INSERT INTO invoice_items(invoice_id,product_id,description,quantity,unit_price_cents) VALUES(?,?,?,?,?)",
                           (invoice_id, product["id"], product["name"], line.quantity, product["unit_price_cents"]))
            audit(db, "quote_created", "invoice", invoice_id, f"{actor['role']} created draft quote for customer {item.customer_id}")
            db.commit()
        except Exception:
            db.rollback()
            raise
        return invoice_detail(db, invoice_id)


@app.post("/api/products/{product_id}/adjustments", status_code=201)
def adjust_stock(product_id: int, item: StockAdjustmentIn, actor: dict = Depends(require_role("manager"))):
    if item.delta == 0:
        raise HTTPException(422,"Stock adjustment cannot be zero")
    with closing(connect()) as db:
        db.execute("BEGIN IMMEDIATE")
        product=db.execute("SELECT * FROM products WHERE id=? AND active=1",(product_id,)).fetchone()
        if not product:
            db.rollback(); raise HTTPException(404,"Product not found")
        if product["stock"]+item.delta<0:
            db.rollback(); raise HTTPException(409,"Stock cannot become negative")
        db.execute("UPDATE products SET stock=stock+? WHERE id=?",(item.delta,product_id))
        db.execute("INSERT INTO stock_ledger(product_id,delta,reason,created_at) VALUES(?,?,?,?)",
                   (product_id,item.delta,item.reason.strip(),datetime.now(timezone.utc).isoformat(timespec="seconds")))
        audit(db,"stock_adjusted","product",product_id,f"{actor['role']} stock delta {item.delta}: {item.reason.strip()}")
        db.commit()
        return dict(db.execute("SELECT * FROM products WHERE id=?",(product_id,)).fetchone())


@app.get("/api/stock-ledger")
def stock_ledger(product_id: int | None = None, _: dict = Depends(require_role("reader"))):
    with closing(connect()) as db:
        if product_id:
            return [dict(r) for r in db.execute("SELECT * FROM stock_ledger WHERE product_id=? ORDER BY id DESC",(product_id,))]
        return [dict(r) for r in db.execute("SELECT * FROM stock_ledger ORDER BY id DESC LIMIT 500")]


@app.get("/api/audit")
def get_audit(limit: int = Query(default=100,ge=1,le=500), _: dict = Depends(require_role("admin"))):
    with closing(connect()) as db:
        return [dict(r) for r in db.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?",(limit,))]


def invoice_detail(db, invoice_id: int):
    invoice = db.execute("SELECT i.*,c.name AS customer_name FROM invoices i JOIN customers c ON c.id=i.customer_id WHERE i.id=?", (invoice_id,)).fetchone()
    if not invoice:
        return None
    lines = [dict(r) for r in db.execute("SELECT * FROM invoice_items WHERE invoice_id=?", (invoice_id,))]
    total = sum(line["quantity"] * line["unit_price_cents"] for line in lines)
    return {**dict(invoice), "items": lines, "total_cents": total}


@app.get("/api/invoices")
def invoices(limit: int = Query(default=100, ge=1, le=500), _: dict = Depends(require_role("reader"))):
    with closing(connect()) as db:
        ids = [r[0] for r in db.execute("SELECT id FROM invoices ORDER BY id DESC LIMIT ?", (limit,))]
        return [invoice_detail(db, invoice_id) for invoice_id in ids]


@app.post("/api/invoices/{invoice_id}/issue")
def issue_invoice(invoice_id: int, actor: dict = Depends(require_role("manager"))):
    with closing(connect()) as db:
        db.execute("BEGIN IMMEDIATE")
        invoice = db.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
        if not invoice:
            db.rollback()
            raise HTTPException(404, "Quote not found")
        if invoice["status"] != "draft":
            db.rollback()
            raise HTTPException(409, "Only a draft quote can be issued")
        lines = db.execute("SELECT product_id, SUM(quantity) AS quantity FROM invoice_items WHERE invoice_id=? GROUP BY product_id", (invoice_id,)).fetchall()
        for line in lines:
            cur = db.execute("UPDATE products SET stock=stock-? WHERE id=? AND stock>=?",
                             (line["quantity"], line["product_id"], line["quantity"]))
            if cur.rowcount != 1:
                db.rollback()
                raise HTTPException(409, f"Insufficient stock for product {line['product_id']}")
            db.execute("INSERT INTO stock_ledger(product_id,delta,reason,created_at) VALUES(?,?,?,?)",
                       (line["product_id"],-line["quantity"],f"invoice {invoice_id}",datetime.now(timezone.utc).isoformat(timespec="seconds")))
        db.execute("UPDATE invoices SET status='issued' WHERE id=?", (invoice_id,))
        audit(db, "invoice_issued", "invoice", invoice_id, f"{actor['role']} issued quote; stock deducted atomically")
        for line in lines:
            audit(db, "stock_deducted", "product", line["product_id"], f"{line['quantity']} units for invoice {invoice_id}")
        db.commit()
        return invoice_detail(db, invoice_id)


@app.post("/api/invoices/{invoice_id}/paid")
def mark_paid(invoice_id: int, actor: dict = Depends(require_role("manager"))):
    with closing(connect()) as db:
        cur = db.execute("UPDATE invoices SET status='paid',paid_at=? WHERE id=? AND status='issued'",
                         (datetime.now(timezone.utc).isoformat(timespec="seconds"), invoice_id))
        if not cur.rowcount:
            db.rollback()
            if not db.execute("SELECT 1 FROM invoices WHERE id=?", (invoice_id,)).fetchone():
                raise HTTPException(404, "Invoice not found")
            raise HTTPException(409, "Only an issued invoice can be marked paid")
        audit(db, "invoice_paid", "invoice", invoice_id, f"{actor['role']} recorded payment")
        db.commit()
        return invoice_detail(db, invoice_id)


@app.get("/api/report")
def report(month: str = Query(regex=r"^\d{4}-\d{2}$"), _: dict = Depends(require_role("reader"))):
    with closing(connect()) as db:
        low = [dict(r) for r in db.execute("SELECT id,sku,name,stock,reorder_at FROM products WHERE active=1 AND stock<=reorder_at ORDER BY stock,name")]
        summary = db.execute("""
            SELECT COUNT(*) AS invoice_count,COALESCE(SUM((SELECT SUM(quantity*unit_price_cents) FROM invoice_items x WHERE x.invoice_id=i.id)),0) AS amount_cents
            FROM invoices i WHERE status='paid' AND substr(paid_at,1,7)=?
        """, (month,)).fetchone()
        outstanding = db.execute("SELECT COUNT(*) AS count FROM invoices WHERE status='issued'").fetchone()["count"]
    return {"month": month, "paid_invoice_count": summary["invoice_count"], "paid_revenue_cents": summary["amount_cents"],
            "outstanding_invoice_count": outstanding, "low_stock": low}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def home():
    items = "" if any(ROLE_KEYS.values()) else "".join(f'<tr><td>{html.escape(p["sku"])}</td><td>{html.escape(p["name"])}</td><td>{p["stock"]}</td><td>R {p["unit_price_cents"]/100:,.2f}</td></tr>' for p in products())
    if not items:
        items='<tr><td colspan="4" class="muted">Connect with a reader or manager key to load products.</td></tr>'
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Workshop · SME Manager</title><style>
    *{{box-sizing:border-box}}body{{margin:0;background:#101512;color:#edf4ed;font:15px/1.5 system-ui,sans-serif}}main{{max-width:1000px;margin:auto;padding:36px 20px}}.tag{{color:#89e1a5;font-size:12px;letter-spacing:.12em;font-weight:700}}h1{{font-size:clamp(30px,5vw,46px);margin:8px 0}}p,.muted{{color:#9bab9e}}section{{background:#19231d;border:1px solid #314638;border-radius:15px;padding:20px;margin:16px 0}}h2{{font-size:18px;margin:0 0 14px}}form{{display:grid;grid-template-columns:repeat(4,1fr);gap:9px}}input,button{{font:inherit;padding:10px;border-radius:8px;border:1px solid #395043;background:#101a14;color:#edf4ed}}button{{background:#89e1a5;color:#132218;border:0;font-weight:700;cursor:pointer}}table{{width:100%;border-collapse:collapse}}td,th{{padding:10px;border-bottom:1px solid #314638;text-align:left}}th{{color:#9bab9e;font-size:12px}}@media(max-width:650px){{form{{grid-template-columns:1fr 1fr}}}}
    </style></head><body><main><div class="tag">WORKSHOP · LOCAL BUSINESS DEMO</div><h1>Operations, in one view.</h1><p>Products, customers, and invoice workflows for a fictional small business. Configure role keys to restrict the API.</p><section><label for="apiKey">Manager API key (only needed when keys are configured)</label><input id="apiKey" type="password" autocomplete="off"></section><section><h2>Products and stock</h2><div style="overflow:auto"><table><thead><tr><th>SKU</th><th>Product</th><th>Stock</th><th>Price</th></tr></thead><tbody>{items}</tbody></table></div></section>
    <section><h2>Add a product</h2><form id="product"><input name="sku" placeholder="SKU" required><input name="name" placeholder="Product name" required><input name="price" type="number" min="0" step="0.01" placeholder="Unit price (R)" required><input name="stock" type="number" min="0" step="1" placeholder="Opening stock" required><input name="reorder" type="number" min="0" step="1" placeholder="Reorder below"><button>Add product</button></form></section>
    <section><h2>API workflows</h2><p>Create a customer at <code>POST /api/customers</code>, create a quote at <code>POST /api/invoices</code>, then issue it using <code>POST /api/invoices/{'{invoice_id}'}/issue</code>. Issuing checks stock and deducts it in one database transaction.</p><a style="color:#89e1a5" href="/docs">Open the API reference</a></section></main><script>
    document.getElementById('product').onsubmit=async ev=>{{ev.preventDefault();const f=ev.target;const b={{sku:f.sku.value,name:f.name.value,unit_price_cents:Math.round(Number(f.price.value)*100),stock:Number(f.stock.value),reorder_at:Number(f.reorder.value||0)}};const r=await fetch('/api/products',{{method:'POST',headers:{{'Content-Type':'application/json','X-API-Key':document.getElementById('apiKey').value}},body:JSON.stringify(b)}});if(r.ok)location.reload();else alert((await r.json()).detail||'Could not save product')}}
    </script></body></html>'''
