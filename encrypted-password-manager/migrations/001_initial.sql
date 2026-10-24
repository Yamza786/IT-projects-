CREATE TABLE vault_metadata (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  format_version INTEGER NOT NULL CHECK (format_version = 1),
  salt BLOB NOT NULL CHECK (length(salt) = 16),
  verifier_nonce BLOB NOT NULL CHECK (length(verifier_nonce) = 12),
  verifier_ciphertext BLOB NOT NULL CHECK (length(verifier_ciphertext) >= 16)
);

CREATE TABLE entries (
  id TEXT PRIMARY KEY,
  service TEXT NOT NULL CHECK (length(service) BETWEEN 1 AND 120),
  nonce BLOB NOT NULL CHECK (length(nonce) = 12),
  ciphertext BLOB NOT NULL CHECK (length(ciphertext) >= 16),
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX entries_service_idx ON entries(service COLLATE NOCASE);

PRAGMA user_version = 1;
