# Vaultsmith

Vaultsmith is a local command-line password vault built with Rust, SQLite, and OpenSSL. It addresses the risk of keeping reusable credentials in plaintext notes by encrypting each credential record before SQLite stores it.

## Features

- Passphrase-derived 256-bit key using OpenSSL scrypt (`N=2^15`, `r=8`, `p=1`) and a random 16-byte salt.
- AES-256-GCM authenticated encryption with a random 12-byte nonce; record ID and service label are authenticated as associated data.
- SQLite schema migration, prepared statements, input bounds, generic unlock failures, and private Unix database permissions (`0600`, parent directory `0700` when created).
- Interactive no-echo entry for passphrases and passwords. Secrets are not accepted as command-line arguments.
- JSON-lines-friendly output for scripts; passwords appear only for the explicit `show` command.
- Portable versioned AES-256-GCM backup export/import using an independent backup passphrase; imports atomically re-encrypt records for the destination vault.

## Requirements and setup

Install Rust (edition 2021), a C compiler, OpenSSL 3 development libraries, SQLite 3 development libraries, and `stty`. On Debian/Ubuntu, install `build-essential libssl-dev libsqlite3-dev pkg-config`; on Termux, use the Rust, OpenSSL, and SQLite packages. The program links directly to system `libcrypto` and `libsqlite3`; it has no Rust package dependencies.

```sh
cargo test --all-targets
cargo clippy --all-targets -- -D warnings
cargo build --release
```

Copy `.env.example` values into your shell as needed. Choose a database with `VAULTSMITH_DB=./vaultsmith.sqlite`, or pass `--db PATH`.

## Local demonstration

Run from this directory. These commands prompt interactively; use a unique synthetic passphrase and credentials for a demo.

```sh
cargo run -- --db ./demo-vault.sqlite init
cargo run -- --db ./demo-vault.sqlite add
cargo run -- --db ./demo-vault.sqlite list
cargo run -- --db ./demo-vault.sqlite export ./demo-vault.vsb
# To restore into an initialized destination vault:
cargo run -- --db ./restored-vault.sqlite import ./demo-vault.vsb
# Copy the printed ID, then:
cargo run -- --db ./demo-vault.sqlite show ENTRY_ID
cargo run -- --db ./demo-vault.sqlite remove ENTRY_ID
```

`list` emits one JSON object per record containing ID, service label, and creation time. `show` emits one JSON object containing the requested username and password. Protect terminal output and backups accordingly. No screenshot is included because the application is a terminal workflow; the commands above reproduce the demo.

## Architecture

```text
src/main.rs       CLI and JSON output
src/terminal.rs   bounded input and no-echo secret prompt
src/vault.rs      validation, migration, encrypted record operations
src/crypto.rs     OpenSSL scrypt and AES-256-GCM FFI
src/sqlite.rs     SQLite prepared-statement FFI
migrations/       versioned SQL schema
```

The vault has one encrypted verifier for passphrase validation. Usernames and passwords are packed into an authenticated encrypted payload. Service names, IDs, and timestamps remain visible to support listing and lookup. Foreign processes running as the same OS user may read process memory or invoke the CLI; the vault does not defend against a compromised host, keyloggers, malicious root, or weak user-selected passphrases. Removing a row is not guaranteed secure erasure from SQLite pages, journals, snapshots, or backups. There is no recovery mechanism: losing the passphrase loses access to the data.

## Tests and security notes

Tests cover authenticated-encryption tampering/AAD, short passphrase rejection, vault lifecycle, input validation, ciphertext-at-rest, private file mode, encrypted backup portability, wrong-passphrase rejection, and no-overwrite behavior. SQLite waits up to five seconds for locks. CI runs formatting, unit tests, and Clippy. OpenSSL and SQLite APIs are called through small FFI modules to avoid network-fetched Rust dependencies; changing those interfaces requires careful review. This MVP has not undergone an independent security audit and should not be used as an enterprise password manager. Windows ACL verification remains pending.

## Contribution

See the portfolio root contribution guidance. Keep fixtures synthetic, never commit vault databases or credentials, and run `cargo fmt --all`, `cargo test --all-targets`, and `cargo clippy --all-targets -- -D warnings` before submitting changes.
