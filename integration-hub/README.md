# API and Integration Hub

A small versioned API that accepts records from source systems, validates them into a canonical event format, and deduplicates retries with an idempotency key. It demonstrates authorization, input validation, rate limiting, and versioned routes without making outbound network requests.

## Run

Set separate read and write API keys, then launch locally:

```sh
export HUB_READ_KEY='replace-with-a-long-random-value'
export HUB_WRITE_KEY='replace-with-a-different-long-random-value'
python -m pip install -r ../requirements-termux.txt
uvicorn app.main:app --reload
```

Do not put real keys in source control. API keys are compared in memory and are not stored in the database. This local demo has in-memory rate limits and is not a substitute for a production gateway.

## Example

```sh
curl -H "X-API-Key: $HUB_WRITE_KEY" -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: accounting-2026-00017' \
  -d '{"external_id":"00017","kind":"invoice.paid","occurred_at":"2026-10-17T12:00:00Z","payload":{"invoice":"INV-17","total_cents":12500}}' \
  http://127.0.0.1:8000/api/v1/integrations/accounting/events
```

Read accepted events with the read key at `GET /api/v1/events`. Reusing an idempotency key returns the original event.
