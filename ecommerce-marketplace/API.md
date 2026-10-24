# Marketplace API

All request and response bodies use JSON. Authentication uses an HTTP-only, same-site session cookie; call `/auth/login` first and retain `marketplace_session`. The app is bound to loopback by default. In production, use HTTPS, set `SECURE_COOKIES=true`, and terminate TLS at a trusted reverse proxy.

## Accounts and seller stores

- `POST /auth/register` — `{ "email": "buyer@example.test", "password": "at-least-12-characters" }`
- `POST /auth/login` — returns a session cookie and user summary.
- `POST /auth/logout` and `GET /auth/me` — session lifecycle and current account.
- `POST /seller/stores` — authenticated user creates their single seller store.
- `GET /seller/stores/:storeId/products` — store owner lists active and archived products with stock.
- `POST /seller/stores/:storeId/products` — store owner adds `{ name, description, priceCents, inventory }`.
- `PATCH /seller/stores/:storeId/products/:productId` — owner updates inventory and `ACTIVE`/`ARCHIVED` status.

## Catalog, cart and orders

- `GET /products?limit=30&offset=0` — active, in-stock products, bounded to 100 per page.
- `PUT /cart/items` — authenticated `{ "productId": "<uuid>", "quantity": 2 }`; sets quantity, does not reserve stock.
- `GET /cart` and `DELETE /cart/items/:productId` — view or remove the caller's cart lines.
- `POST /orders` — authenticated `{}` with an `Idempotency-Key` header; atomically validates inventory, places an order and decrements stock.
- `GET /orders` — caller's recent orders.
- `GET /seller/stores/:storeId/orders` — seller-only order lines for that store.

Money is represented in integer cents. A checkout records `SIMULATED_UNPAID`; it does not charge a payment method or imply a successful payment. API errors are JSON and do not expose SQL or stack traces.
