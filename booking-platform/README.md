# Service Booking Platform

A local booking workflow for a small service business. Visitors can view services and request a time; overlapping active bookings are rejected inside an immediate SQLite transaction. This demo does not collect card details or process payments.

## Run

```sh
python -m pip install -r ../requirements-termux.txt
uvicorn app.main:app --reload
```

Open `/` for the booking form and `/docs` for the API. Set `BOOKING_DB` to move the local database.

## Endpoints

- `GET|POST /api/services`
- `GET /api/availability?service_id=1&day=YYYY-MM-DD&timezone=Africa/Johannesburg`
- `POST /api/bookings` — customer, service, and timezone-aware ISO start time
- `GET /api/bookings` and `POST /api/bookings/{id}/cancel` — require `X-Admin-Key`

Set `BOOKING_ADMIN_KEY` before using service or booking administration. Public booking submissions are rate-limited in memory per client address. Availability is 09:00–17:00 local time in 30-minute slots; this is a demo rule, not a configurable calendar yet.

Before public deployment, add customer accounts or email verification, persistent abuse controls, privacy and retention policies, and a payment provider sandbox if payments are needed.
