# SME Business Management System

A local-first workflow for products, customers, quotations, invoices, inventory, and a basic sales report. SQLite transactions protect invoice issuance and stock deduction as one operation. This portfolio edition has no user accounts or multi-device sync; do not expose it to the internet with real customer data.

## Run

```sh
python -m pip install -r ../requirements-termux.txt
uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000>; API docs are at `/docs`. Set `SME_DB` to choose the database location. Use fictional customers and products for demos.

## Workflows

1. Add products with opening stock and a reorder threshold.
2. Add a customer.
3. Create a draft quote with line items.
4. Issue the quote as an invoice; stock is checked and decremented atomically.
5. Review low stock, invoice status, and paid revenue through the report endpoint.

Stock adjustments are recorded with a reason in the stock ledger. Workflow changes appear in `/api/audit`.

Prices are integer cents. The application records an audit event for stock changes and invoice issue/paid transitions.
