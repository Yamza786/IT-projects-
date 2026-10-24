CREATE TABLE users (
  id TEXT PRIMARY KEY,
  email TEXT NOT NULL UNIQUE COLLATE NOCASE,
  password_hash TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE sessions (
  token_hash TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX sessions_expiry_idx ON sessions(expires_at);

CREATE TABLE stores (
  id TEXT PRIMARY KEY,
  owner_user_id TEXT NOT NULL UNIQUE REFERENCES users(id),
  name TEXT NOT NULL CHECK(length(trim(name)) BETWEEN 2 AND 100),
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE products (
  id TEXT PRIMARY KEY,
  store_id TEXT NOT NULL REFERENCES stores(id),
  name TEXT NOT NULL CHECK(length(trim(name)) BETWEEN 2 AND 120),
  description TEXT NOT NULL DEFAULT '' CHECK(length(description) <= 2000),
  price_cents INTEGER NOT NULL CHECK(price_cents BETWEEN 1 AND 100000000),
  inventory INTEGER NOT NULL CHECK(inventory BETWEEN 0 AND 1000000),
  status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE', 'ARCHIVED')),
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX products_listing_idx ON products(status, created_at DESC);
CREATE INDEX products_store_idx ON products(store_id, created_at DESC);

CREATE TABLE cart_items (
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  product_id TEXT NOT NULL REFERENCES products(id),
  quantity INTEGER NOT NULL CHECK(quantity BETWEEN 1 AND 100),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  PRIMARY KEY(user_id, product_id)
);

CREATE TABLE orders (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id),
  idempotency_key TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('PLACED', 'CANCELLED')),
  payment_status TEXT NOT NULL CHECK(payment_status = 'SIMULATED_UNPAID'),
  total_cents INTEGER NOT NULL CHECK(total_cents > 0),
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  UNIQUE(user_id, idempotency_key)
);
CREATE INDEX orders_user_idx ON orders(user_id, created_at DESC);

CREATE TABLE order_items (
  order_id TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  product_id TEXT NOT NULL REFERENCES products(id),
  product_name TEXT NOT NULL,
  store_id TEXT NOT NULL REFERENCES stores(id),
  quantity INTEGER NOT NULL CHECK(quantity BETWEEN 1 AND 100),
  unit_price_cents INTEGER NOT NULL CHECK(unit_price_cents > 0),
  PRIMARY KEY(order_id, product_id)
);
CREATE INDEX order_items_store_idx ON order_items(store_id, order_id);

CREATE TABLE audit_events (
  id TEXT PRIMARY KEY,
  actor_user_id TEXT REFERENCES users(id),
  action TEXT NOT NULL,
  target_id TEXT,
  details_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX audit_events_created_idx ON audit_events(created_at DESC);

PRAGMA user_version = 1;
