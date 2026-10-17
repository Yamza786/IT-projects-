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
- `POST /api/bookings` — customer, service, and timezone-aware ISO start time
- `GET /api/bookings`
- `POST /api/bookings/{id}/cancel`

Before public deployment, add authentication for administration, email verification, abuse controls, privacy and retention policies, and a payment provider sandbox if payments are needed.
