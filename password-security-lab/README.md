# Password Security Lab

An interactive command-line lab demonstrating password hashing and verification with Argon2id (preferred when installed), bcrypt, or the Python-standard-library scrypt fallback. It does not save or transmit passwords. You can hash a test phrase or verify one against an encoded hash.

## Setup and use

```sh
python password_lab.py hash
python password_lab.py verify '$argon2id$...'
```

The password is entered using a hidden prompt. Automatic mode uses Argon2id if `argon2-cffi` is installed and otherwise uses scrypt; install `argon2-cffi` to exercise Argon2id. `--backend bcrypt` selects bcrypt if `bcrypt` is installed, and `--backend scrypt` forces the built-in fallback. For a policy-only strength assessment, run `python password_lab.py check`; it does not claim to detect breached passwords.

## Limits

This is educational code, not an authentication service. Production authentication also needs safe account recovery, rate limits, MFA options, session security, and tested parameter upgrades. Never commit sample hashes derived from real credentials.
