# HTTP API

The service listens on `127.0.0.1` by default. JSON errors have the form `{"error":"..."}`; validation errors also include field paths. Login returns an HttpOnly, SameSite=Strict cookie named `saas_session`. Send that cookie on subsequent requests. The service stores only a SHA-256 digest of the random session token.

## Routes

| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/health` | Public | Process health check |
| POST | `/auth/login` | Public | Authenticate with `{ "email", "password" }` |
| POST | `/auth/logout` | Signed in | Revoke current session |
| GET | `/auth/me` | Signed in | Current identity and tenant memberships |
| POST | `/users` | Platform administrator | Create a user account |
| GET | `/tenants` | Signed in | List all tenants for platform admins, own memberships for other users |
| POST | `/tenants` | Platform administrator | Create a tenant; owner, free trial subscription and audit record are created atomically |
| GET | `/tenants/:tenantId` | Tenant member | Read tenant metadata |
| GET | `/tenants/:tenantId/members` | Tenant member | List tenant memberships |
| POST | `/tenants/:tenantId/members` | Owner or admin | Add an existing account with role `ADMIN`, `BILLING`, `MEMBER` or `VIEWER` |
| PATCH | `/tenants/:tenantId/members/:userId` | Owner or admin | Change a non-owner membership role |
| GET | `/tenants/:tenantId/subscription` | Tenant member | Read plan, status and seat count |
| PUT | `/tenants/:tenantId/subscription` | Owner, admin or billing | Set validated plan, status and seats |
| GET | `/tenants/:tenantId/audit` | Owner or admin | Read the most recent 100 tenant audit events |

Plans: `FREE`, `STARTER`, `GROWTH`, `ENTERPRISE`. Subscription statuses: `TRIAL`, `ACTIVE`, `PAST_DUE`, `CANCELED`. Tenant roles: `OWNER`, `ADMIN`, `BILLING`, `MEMBER`, `VIEWER`. A platform administrator is a separate global role. No route handles real billing or card data.

## Example

```sh
curl -i -c cookies.txt -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.test","password":"use-your-local-bootstrap-password"}' \
  http://127.0.0.1:3000/auth/login
curl -b cookies.txt http://127.0.0.1:3000/tenants
```

The API responds with structured JSON and does not log request bodies, passwords or session tokens. See `README.md` for a full tenant/member/billing walkthrough.
