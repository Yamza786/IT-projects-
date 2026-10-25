# Desktop Knowledge Manager

An offline-first Flutter desktop app for private notes. Notes stay in a local SQLite database, support substring search across title/body, and can be exported or restored as an authenticated encrypted backup.

## Run

Install Flutter stable and enable the Linux or Windows desktop target:

```sh
flutter config --enable-linux-desktop
flutter pub get
flutter test
flutter run -d linux
```

For Windows, enable `windows-desktop` and use `flutter run -d windows`. Linux stores the database under `${XDG_DATA_HOME:-$HOME/.local/share}/PortfolioKnowledgeManager`; Windows uses `%APPDATA%\PortfolioKnowledgeManager`.

The backup flow derives a 256-bit key with PBKDF2-HMAC-SHA256 (210,000 iterations) and a random 128-bit salt, then encrypts with AES-256-GCM. Backups contain no plaintext note data; import verifies the authentication tag and replaces notes in a transaction after explicit confirmation. Use a unique passphrase of at least 12 characters and keep it separately: it cannot be recovered.

## Verification and limits

Tests cover storage validation, literal search metacharacters, rollback, encrypted round trips, authentication failure, and a widget search workflow. CI runs Linux/Windows tests and desktop build smoke checks. This MVP has no cloud sync, account system, or remote telemetry. Notes are local plaintext in the OS user's data directory; only exported backups are encrypted.
