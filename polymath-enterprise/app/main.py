"""Integrated SME capstone with RBAC, audit records, and explainable reports."""

from __future__ import annotations

import hmac
import os
import sqlite3
from contextlib import closing
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import median
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query
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
            CREATE INDEX IF NOT EXISTS sales_day_idx ON sales(day);
            CREATE INDEX IF NOT EXISTS expenses_day_idx ON expenses(day);
        """)
        db.commit()


@app.on_event("startup")
def startup():
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
