# Mini SIEM API

All endpoints are same-origin by default. Every endpoint except `GET /api/v1/health` requires `Authorization: Bearer <SIEM_API_TOKEN>`. Requests and responses use JSON. Payload size is limited to 16 KiB for event ingestion and 1 KiB for triage updates; unknown JSON fields and trailing JSON values are rejected.

## Endpoints

| Method and path | Purpose |
|---|---|
| `GET /api/v1/health` | Liveness only; no sensitive details |
| `POST /api/v1/events` | Validate, normalize, persist and evaluate one event; returns the normalized event and alerts created |
| `GET /api/v1/events?limit=100` | Recent persisted events, newest first; limit is capped at 500 |
| `GET /api/v1/alerts?status=open&limit=100` | Alert queue filtered by `open`, `acknowledged`, or `resolved` |
| `PATCH /api/v1/alerts/{id}` | Change alert status using `{"status":"acknowledged"}` or `{"status":"resolved"}` |

## Event shape

```json
{
  "occurred_at": "2026-10-24T12:00:00Z",
  "source": "auth-demo",
  "actor": "synthetic-user",
  "action": "failed_login",
  "outcome": "failure",
  "source_ip": "192.0.2.10",
  "summary": "Synthetic sign-in failure"
}
```

`source`, `actor`, and `action` are required. Accepted outcomes are `success`, `failure`, and `denied`. Time is restricted to the last 30 days and at most five minutes in the future. IP values must parse as IPv4/IPv6. Server-generated IDs and receive timestamps are returned.

## Detection rules

- `auth-failures-5m`: five failed `failed_login` events for the same actor in a five-minute event-time window create a high-severity alert.
- `privilege-change`: successful or denied `privilege_change` activity creates a medium-severity alert.

Rules are deterministic and intentionally small. They are not a substitute for a production detection engineering pipeline.

Errors have the shape `{"error":{"code":"...","message":"..."}}`. Event ingestion returns `201`; validation errors return `400`, missing/bad bearer credentials `401`, invalid state transitions `409`, missing alerts `404`, and persistence failures `500` without leaking file paths.
