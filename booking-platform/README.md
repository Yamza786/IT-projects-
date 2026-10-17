# Service Booking Platform

A local booking workflow for a small service business. Visitors can view services and request a time; overlapping active bookings are rejected inside an immediate SQLite transaction. It includes optional email verification and a deterministic payment sandbox that never collects card details or processes real money.

## Run

```sh
python -m pip install -r ../requirements-termux.txt
uvicorn app.main:app --reload
```

Open `/` for the booking form and `/docs` for the API. Set `BOOKING_DB` to move the local database.

## Endpoints

- `GET|POST /api/services`
- `GET /api/availability?service_id=1&day=YYYY-MM-DD&timezone=Africa/Johannesburg`
- `POST /api/accounts`, `POST /api/login`, `DELETE /api/account/session`
- `POST /api/bookings` — authenticated account, service, and timezone-aware ISO start time
- `GET /api/my-bookings`, `POST /api/my-bookings/{id}/cancel`
- `POST /api/accounts/verify`, `POST /api/accounts/verification/resend`
- `GET /api/calendar`, `PUT /api/calendar/{weekday}` — calendar changes require `X-Admin-Key`; weekday is Monday `0` through Sunday `6`
- `POST /api/my-bookings/{id}/payments/sandbox`, `GET /api/my-bookings/{id}/payments` — sandbox outcomes only
- `GET /api/bookings` and `POST /api/bookings/{id}/cancel` — require `X-Admin-Key`

Set `BOOKING_ADMIN_KEY` before using service or booking administration. The initial calendar opens daily from 09:00 to 17:00; administrators can set different open/close hours or close a weekday. Starts are offered every 30 minutes in the timezone requested by the caller, and overlapping bookings are rejected across all services.

Passwords are stored as salted scrypt hashes; bearer sessions expire after 24 hours and can be revoked. Set `BOOKING_VERIFICATION_MODE=development` to receive a one-time verification token in the local API response, or set it to `smtp` and configure `BOOKING_SMTP_HOST`, `BOOKING_SMTP_FROM`, optional SMTP credentials, and a STARTTLS-capable relay. The default `disabled` mode is for local demonstrations only. Verification tokens are stored as hashes and expire after 24 hours; the resend route uses a generic response to reduce account enumeration.

For payment-flow testing, submit `sbx_test_success` or `sbx_test_decline` to `POST /api/my-bookings/{id}/payments/sandbox` with an idempotency key. The API stores only the outcome, amount, and currency; it rejects card data by design. This is a local simulator, not a connection to a processor's test environment and cannot accept real funds. Public launches should use a chosen provider's official sandbox and webhook signature validation.

Public booking and authentication throttles are in memory and reset on restart. Use a gateway-level persistent limiter before exposing this demonstration to the internet.
