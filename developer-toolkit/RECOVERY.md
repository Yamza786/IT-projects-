# Backup recovery guide

`backup.py` writes a ZIP archive and a sibling JSON manifest containing each file's path, byte count, and SHA-256 digest. Keep both files together and store a copy outside the device or host being backed up.

## Verify before restoring

1. Work from a copy of the archive and manifest.
2. Run `python verify_backup.py backup.zip`; the command verifies the archive contents and all manifest digests without extracting files.
3. If verification fails, quarantine the archive and use another dated copy. A changed digest means the archive no longer matches its manifest.
4. Restore into a new empty directory first. Never extract an untrusted ZIP directly over a live project: archive paths can contain traversal entries.
5. Open representative files and run the application's normal health checks before replacing any working copy.

## Recovery expectations

- A backup only contains files present when the ZIP was created; open databases may need an application-aware snapshot or the application stopped briefly.
- Symbolic links are skipped rather than followed, to avoid copying data outside the selected source tree.
- The manifest detects accidental changes but is not a signature and does not prove who created the archive.
- Keep several dated copies and periodically perform a restore drill. A backup that has never been restored is unverified.
