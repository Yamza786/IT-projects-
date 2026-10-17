# Personal Finance and Wealth Analytics

A local, rand-denominated ledger for income, spending, budgets, savings goals, and simple scenario comparisons. It uses integer cents for money and stores data in SQLite. Scenarios are hypothetical calculations, not investment recommendations.

## Run

```sh
python -m pip install -r ../requirements-termux.txt
uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000>; API docs are at `/docs`. Set `FINANCE_DB` to change the database path. Data stays local.

## API

- `GET /api/summary?month=YYYY-MM`
- `GET|POST /api/transactions`
- `GET|POST /api/budgets`
- `GET|POST /api/savings-goals`
- `POST /api/scenarios`

Use synthetic data for demos and keep the database private. No bank connection or real investment products are involved.
