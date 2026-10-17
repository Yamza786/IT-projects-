# Polymath Enterprise

An integrated, local-first small-business capstone combining customers, inventory, sales, expenses, reporting, and role-checked API access. The app writes an audit event for business changes and rejects sales that exceed available stock in a single SQLite transaction.

Its explainable report finds possible expense outliers using the modified z-score (median absolute deviation). Each result includes the category baseline and score; it is a review prompt, not a fraud finding or an AI-generated conclusion. This local release avoids sending private business data to an external model.

## Run

```sh
export ENTERPRISE_READER_KEY='use-a-long-random-value'
export ENTERPRISE_MANAGER_KEY='use-a-different-long-random-value'
export ENTERPRISE_ADMIN_KEY='use-another-long-random-value'
python -m pip install -r ../requirements-termux.txt
uvicorn app.main:app --reload
```

Open `/` for the business interface or `/docs` for the API. The database defaults to `enterprise.db`; set `ENTERPRISE_DB` to choose another path. Keep the API on a trusted local network and protect the database and backups. This is a portfolio capstone, not a production accounting or security system.

`/health` checks SQLite readiness. Admin-key protected `/metrics` exposes process uptime, database size, and low-cardinality record counts for external monitoring; it does not expose customer or financial values.

## Roles

- Reader key: read catalogue, report, and audit history.
- Manager key: reader access plus customers, products, stock changes, sales, and expense entry.
- Admin key: manager access plus audit-history access.

Keys are read from environment variables and compared in memory; they are never stored in the database. Do not commit them.

## Main workflows

1. Create a customer and products with opening stock.
2. Record a sale with one or more product quantities; inventory is deducted atomically.
3. Record an operating expense in integer cents.
4. Read monthly revenue, expenses, net operating balance, and category summaries.
5. Review anomaly candidates and the evidence used to flag them.
6. Import a JSON report from `security-log-analyzer` through `POST /api/security-reports`.
7. Read the idempotent business event feed at `GET /api/integration-feed` and forward events into the Integration Hub.
8. Attach authorized source passages through `POST /api/research-evidence`; monthly reports include these citations for review.

API calls use `X-API-Key`. Example body schemas are available in `/docs`.

The Security Log Analyzer exports the fields accepted by the security report import endpoint. The integration feed provides stable event IDs and idempotency keys so downstream ingestion can safely retry.
