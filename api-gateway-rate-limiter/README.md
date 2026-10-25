# API Gateway and Rate Limiting Service

A small Java 21 HTTP gateway with explicit route configuration, bounded request forwarding, persisted per-client quotas, and a SQLite request audit. It is designed as a local demonstration service and binds to loopback by default.

## Run

Start an HTTP backend on `127.0.0.1:8081`, then run:

```sh
gradle test
gradle run
```

The default route forwards `/api/...` to `http://127.0.0.1:8081/...`. Configure it with environment variables:

| Variable | Default | Bounds / meaning |
| --- | --- | --- |
| `GATEWAY_PORT` | `8080` | Listener port, 1–65535 |
| `GATEWAY_UPSTREAM` | `http://127.0.0.1:8081` | Configured HTTP(S) backend URL, no credentials/query |
| `GATEWAY_PREFIX` | `/api` | Allowed incoming path prefix |
| `GATEWAY_RATE_LIMIT` | `60` | Requests allowed per client and route window |
| `GATEWAY_WINDOW_SECONDS` | `60` | Fixed quota window in seconds, 1–86400 |
| `GATEWAY_DATABASE` | `data/gateway.sqlite` | Private SQLite quota and audit database |

The gateway selects the remote socket address as the client identity. It forwards `Authorization` and other end-to-end headers, does not follow upstream redirects, limits request bodies to 1 MiB, and times out upstream requests. Quota state and response-status audit records survive restarts. If running behind a reverse proxy, the gateway will count that proxy as the client; do not trust caller-supplied forwarding headers.

## Verification

`gradle test` covers quota burst/expiry and client isolation, credential forwarding, route validation, and HTTP 429 behavior using local fixtures. GitHub Actions runs the same test suite with Java 21.

## Limits

This is a single-process prototype. SQLite coordination is adequate for one instance; it is not a distributed limiter. The route is intentionally configured by process environment rather than a dynamic control plane. Bind/firewall policy, TLS termination, authentication policy, upstream allowlisting, distributed quotas, operational metrics, and production deployment review are required before internet exposure. The configured upstream is trusted operator input; never expose route selection to an untrusted caller.
