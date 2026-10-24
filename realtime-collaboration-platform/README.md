# Real-Time Collaboration Platform

A Phoenix Channels and PostgreSQL service for scoped collaboration rooms. It solves the need for authenticated presence, durable room messages, and reconnect history without trusting client-supplied user or room identities.

## Features

- Short-lived Phoenix signed tokens scoped to exactly one member and room.
- WebSocket-only `room:*` channels; a token cannot join a different room.
- Presence heartbeats and a room-scoped history snapshot of the 50 latest persisted events.
- Bounded message validation, server-assigned identity, client event IDs for idempotent persistence, and database constraints.
- Health endpoint, Compose development deployment, and Postgres-backed CI tests.

## Local setup

Requires Elixir 1.17+, Erlang/OTP 27+, PostgreSQL 16+, and Docker Compose (optional). Copy `.env.example` and replace its local-only values if using your own database. The sample password is for a disposable local database only.

```sh
mix local.hex --force
mix local.rebar --force
mix deps.get
mix ecto.create
mix ecto.migrate
mix format --check-formatted
mix test
mix phx.server
```

For a containerized local demo, run `docker compose up --build`; the service binds to loopback port 4000 and Postgres data uses a named volume. Check `GET http://127.0.0.1:4000/health` for `{"status":"ok"}`. Stop with `docker compose down`; `docker compose down -v` also deletes the local sample database volume.

## Channel API

Issue a short-lived demo token only after the application can connect to its configured database:

```sh
mix collab.issue_token demo-member demo-room
```

Connect a Phoenix Channels client to `ws://localhost:4000/socket/websocket?token=TOKEN&vsn=2.0.0`. Production deployments must use `wss://`; keep tokens out of access logs, screenshots, shell history, and URLs copied into third-party tools. Tokens expire after one hour. A production identity service should issue them after its own authentication and room-membership authorization checks. This repository has no user registration/password database and the local token task is a demonstration issuer.

Join topic `room:demo-room`. The server sends `presence_state` and a `history` event containing up to 50 stored messages. Send a `message` event:

```json
{"body":"Review the migration plan","client_event_id":"a valid UUID"}
```

The server validates a 1–4,000-byte body, assigns the authenticated member and scoped room, writes the event before broadcasting, and returns an acknowledgement. Re-sending the same client event ID for that member and room returns the original persisted event.

## Architecture and security boundaries

```text
Phoenix Endpoint / UserSocket -> token verification -> RoomChannel
                                                  |-> Presence (PubSub)
                                                  |-> RoomEvent -> PostgreSQL
```

The channel authorizes room membership from the signed token scope. Database constraints enforce message size, event kind and idempotency. Production requires `COLLAB_SECRET_KEY_BASE` and `DATABASE_URL`; configure TLS at a trusted ingress, restrict database network access, rotate signing keys, and use a production identity issuer. No credentials or user data are included in this repository.

This is an MVP, not a complete collaborative editor. It provides durable chat-like room events and presence, not CRDT/document synchronization, user lifecycle, fine-grained room ACL storage, abuse/rate controls, retention policy, or horizontal deployment/load-tested guarantees. Persisted message bodies are plain text in PostgreSQL; operators must apply database access, encryption-at-rest, backup retention and privacy controls appropriate to their environment. Docker Compose is a local demo, not a production deployment. No production deploy was performed.

## Tests and contribution

ExUnit covers token integrity, payload bounds, channel room authorization, persisted/broadcast messages and duplicate IDs. GitHub Actions runs formatting, warning-free compilation, migration and tests against a temporary PostgreSQL service. The local Termux environment does not have Elixir/Erlang installed; installing the packages needs about 141 MB additional space while only about 25 MB is free, so local execution is pending. Keep fixtures synthetic and run `mix format`, `mix compile --warnings-as-errors`, `mix ecto.migrate`, and `mix test` before submitting changes.
