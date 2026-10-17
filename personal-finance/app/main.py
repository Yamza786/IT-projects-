"""Local personal finance tracker using integer cents and SQLite."""

from __future__ import annotations

import html
import os
import sqlite3
from contextlib import closing
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

DB_PATH = Path(os.environ.get("FINANCE_DB", "finance.db"))
app = FastAPI(title="Personal Finance and Wealth Analytics", version="0.1.0")


def db_connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with closing(db_connect()) as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY, kind TEXT NOT NULL CHECK(kind IN ('income','expense')),
                category TEXT NOT NULL, amount_cents INTEGER NOT NULL CHECK(amount_cents > 0),
                memo TEXT NOT NULL DEFAULT '', day TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS budgets (
                id INTEGER PRIMARY KEY, category TEXT NOT NULL, month TEXT NOT NULL,
                limit_cents INTEGER NOT NULL CHECK(limit_cents > 0), UNIQUE(category, month)
            );
            CREATE TABLE IF NOT EXISTS savings_goals (
                id INTEGER PRIMARY KEY, title TEXT NOT NULL, target_cents INTEGER NOT NULL CHECK(target_cents > 0),
                saved_cents INTEGER NOT NULL DEFAULT 0 CHECK(saved_cents >= 0), due_date TEXT
            );
            CREATE INDEX IF NOT EXISTS txn_day_idx ON transactions(day);
        """)
        db.commit()


@app.on_event("startup")
def startup():
    initialize()


class TransactionIn(BaseModel):
    kind: Literal["income", "expense"]
    category: str = Field(min_length=1, max_length=80)
    amount_cents: int = Field(gt=0, le=10_000_000_000)
    memo: str = Field(default="", max_length=500)
    day: date = Field(default_factory=date.today)


class BudgetIn(BaseModel):
    category: str = Field(min_length=1, max_length=80)
    month: str = Field(regex=r"^\d{4}-\d{2}$")
    limit_cents: int = Field(gt=0, le=10_000_000_000)


class SavingsGoalIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    target_cents: int = Field(gt=0)
    saved_cents: int = Field(default=0, ge=0)
    due_date: date | None = None


class ScenarioIn(BaseModel):
    initial_cents: int = Field(ge=0)
    monthly_cents: int = Field(ge=0)
    annual_return_percent: float = Field(ge=-100, le=100)
    months: int = Field(ge=1, le=1200)


def money(cents: int) -> str:
    return f"R {cents / 100:,.2f}"


@app.get("/api/transactions")
def get_transactions(limit: int = Query(default=100, ge=1, le=500)):
    with closing(db_connect()) as db:
        return [dict(row) for row in db.execute("SELECT * FROM transactions ORDER BY day DESC, id DESC LIMIT ?", (limit,))]


@app.post("/api/transactions", status_code=201)
def add_transaction(item: TransactionIn):
    with closing(db_connect()) as db:
        cursor = db.execute("INSERT INTO transactions(kind,category,amount_cents,memo,day,created_at) VALUES(?,?,?,?,?,?)",
                             (item.kind, item.category.strip(), item.amount_cents, item.memo.strip(), item.day.isoformat(), datetime.now(timezone.utc).isoformat()))
        db.commit()
        return dict(db.execute("SELECT * FROM transactions WHERE id=?", (cursor.lastrowid,)).fetchone())


@app.get("/api/budgets")
def get_budgets(month: str = Query(regex=r"^\d{4}-\d{2}$")):
    with closing(db_connect()) as db:
        return [dict(row) for row in db.execute("""
            SELECT b.*, COALESCE(SUM(t.amount_cents),0) AS spent_cents
            FROM budgets b LEFT JOIN transactions t ON t.category=b.category AND t.kind='expense' AND substr(t.day,1,7)=b.month
            WHERE b.month=? GROUP BY b.id ORDER BY b.category
        """, (month,))]


@app.post("/api/budgets", status_code=201)
def set_budget(item: BudgetIn):
    with closing(db_connect()) as db:
        db.execute("INSERT INTO budgets(category,month,limit_cents) VALUES(?,?,?) ON CONFLICT(category,month) DO UPDATE SET limit_cents=excluded.limit_cents",
                   (item.category.strip(), item.month, item.limit_cents))
        db.commit()
        return dict(db.execute("SELECT * FROM budgets WHERE category=? AND month=?", (item.category.strip(), item.month)).fetchone())


@app.get("/api/savings-goals")
def get_savings_goals():
    with closing(db_connect()) as db:
        return [dict(row) for row in db.execute("SELECT * FROM savings_goals ORDER BY id DESC")]


@app.post("/api/savings-goals", status_code=201)
def add_savings_goal(item: SavingsGoalIn):
    with closing(db_connect()) as db:
        cursor = db.execute("INSERT INTO savings_goals(title,target_cents,saved_cents,due_date) VALUES(?,?,?,?)",
                             (item.title.strip(), item.target_cents, item.saved_cents, item.due_date.isoformat() if item.due_date else None))
        db.commit()
        return dict(db.execute("SELECT * FROM savings_goals WHERE id=?", (cursor.lastrowid,)).fetchone())


@app.get("/api/summary")
def summary(month: str = Query(regex=r"^\d{4}-\d{2}$")):
    with closing(db_connect()) as db:
        totals = db.execute("""
            SELECT COALESCE(SUM(CASE WHEN kind='income' THEN amount_cents ELSE 0 END),0) AS income_cents,
                   COALESCE(SUM(CASE WHEN kind='expense' THEN amount_cents ELSE 0 END),0) AS expense_cents
            FROM transactions WHERE substr(day,1,7)=?
        """, (month,)).fetchone()
        budgets = [dict(r) for r in db.execute("""
            SELECT b.category,b.limit_cents,COALESCE(SUM(t.amount_cents),0) AS spent_cents
            FROM budgets b LEFT JOIN transactions t ON t.category=b.category AND t.kind='expense' AND substr(t.day,1,7)=b.month
            WHERE b.month=? GROUP BY b.id
        """, (month,))]
    income = totals["income_cents"]
    expenses = totals["expense_cents"]
    return {"month": month, "income_cents": income, "expense_cents": expenses, "net_cents": income-expenses,
            "savings_rate_percent": round((income-expenses) / income * 100, 2) if income else None, "budgets": budgets}


@app.post("/api/scenarios")
def scenario(item: ScenarioIn):
    """Monthly compounding approximation, with deposits made at month end."""
    balance = item.initial_cents
    rate = item.annual_return_percent / 100 / 12
    for _ in range(item.months):
        balance = balance * (1 + rate) + item.monthly_cents
    total_deposited = item.initial_cents + item.monthly_cents * item.months
    return {"projected_cents": round(balance), "contributions_cents": total_deposited,
            "difference_cents": round(balance) - total_deposited, "months": item.months,
            "assumptions": "Fixed monthly rate derived from the annual percentage; contributions occur at month end; excludes fees, tax, inflation, and volatility."}


@app.get("/", response_class=HTMLResponse)
def home():
    month = date.today().strftime("%Y-%m")
    data = summary(month)
    rows = "".join(f'<tr><td>{html.escape(x["day"])}</td><td>{html.escape(x["category"])}</td><td>{html.escape(x["kind"])}</td><td>{money(x["amount_cents"])}</td></tr>' for x in get_transactions(15)) or '<tr><td colspan="4" class="muted">Add a transaction to get started.</td></tr>'
    rate = "—" if data["savings_rate_percent"] is None else f'{data["savings_rate_percent"]:.1f}%'
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Randwise · Personal Finance</title><style>
    *{{box-sizing:border-box}}body{{margin:0;background:#0d1221;color:#eef3ff;font:15px/1.5 system-ui,sans-serif}}main{{max-width:1000px;margin:auto;padding:36px 20px}}header{{margin-bottom:24px}}.eyebrow{{color:#72e0b5;font-size:12px;letter-spacing:.12em;font-weight:700}}h1{{font-size:clamp(30px,5vw,46px);margin:8px 0}}p,.muted{{color:#9caac3}}.cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}}section{{background:#161f33;border:1px solid #293653;border-radius:15px;padding:18px;margin-bottom:16px}}.metric{{font-size:25px;font-weight:700;margin-top:6px}}h2{{font-size:17px;margin:0 0 14px}}form{{display:grid;grid-template-columns:repeat(4,1fr);gap:9px}}input,select,button{{font:inherit;padding:10px;border-radius:8px;border:1px solid #34415b;background:#0f1728;color:#eef3ff}}button{{background:#72e0b5;color:#102119;border:0;font-weight:700;cursor:pointer}}table{{width:100%;border-collapse:collapse}}td,th{{padding:10px;border-bottom:1px solid #293653;text-align:left}}th{{color:#9caac3;font-size:12px}}@media(max-width:700px){{.cards{{grid-template-columns:1fr}}form{{grid-template-columns:1fr 1fr}}}}
    </style></head><body><main><header><div class="eyebrow">RANDWISE · PRIVATE LOCAL LEDGER</div><h1>Know where your money goes.</h1><p>Monthly view for {month}. Amounts are stored in cents and shown in South African rand.</p></header>
    <div class="cards"><section><span class="muted">Income</span><div class="metric">{money(data['income_cents'])}</div></section><section><span class="muted">Spending</span><div class="metric">{money(data['expense_cents'])}</div></section><section><span class="muted">Net · savings rate {rate}</span><div class="metric">{money(data['net_cents'])}</div></section></div>
    <section><h2>Record a transaction</h2><form id="txn"><select name="kind"><option value="expense">Expense</option><option value="income">Income</option></select><input name="category" placeholder="Category" required maxlength="80"><input name="amount" type="number" min="0.01" step="0.01" placeholder="Amount (R)" required><input name="day" type="date" value="{date.today().isoformat()}" required><input name="memo" placeholder="Note (optional)" maxlength="500"><button>Save transaction</button></form></section>
    <section><h2>Latest transactions</h2><div style="overflow:auto"><table><thead><tr><th>Date</th><th>Category</th><th>Type</th><th>Amount</th></tr></thead><tbody>{rows}</tbody></table></div></section>
    <p>Scenario calculations are illustrative estimates only. <a style="color:#72e0b5" href="/docs">Open the API</a>.</p></main><script>
    document.getElementById('txn').onsubmit=async ev=>{{ev.preventDefault();const f=ev.target;const amount=Math.round(Number(f.amount.value)*100);const body={{kind:f.kind.value,category:f.category.value,amount_cents:amount,memo:f.memo.value,day:f.day.value}};const r=await fetch('/api/transactions',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(body)}});if(r.ok)location.reload();else alert('Could not save transaction; check the fields.')}}
    </script></body></html>'''
