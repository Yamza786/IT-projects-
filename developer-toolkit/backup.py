#!/usr/bin/env python3
"""Create a timestamped ZIP backup with a SHA-256 manifest."""

import argparse
import hashlib
import json
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from jsonl_log import append_event


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--log-jsonl", type=Path, help="append private operational events to this JSONL file")
    args = parser.parse_args()
    source = args.source.expanduser().resolve()
    destination = args.destination.expanduser().resolve()
    if not source.is_dir():
        parser.error(f"source is not a directory: {source}")
    if destination == source or source in destination.parents:
        parser.error("destination must be outside the source directory")
    files = sorted((p for p in source.rglob("*") if p.is_file()), key=lambda p: str(p).casefold())
    if not files:
        parser.error("source contains no files")
    destination.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive = destination / f"{source.name}-{stamp}.zip"
    manifest = []
    try:
        with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as bundle:
            for path in files:
                relative = path.relative_to(source).as_posix()
                bundle.write(path, arcname=relative)
                manifest.append({"path": relative, "size": path.stat().st_size, "sha256": digest(path)})
        sidecar = archive.with_suffix(".manifest.json")
        sidecar.write_text(json.dumps({"created_utc": stamp, "source": str(source), "files": manifest}, indent=2) + "\n", encoding="utf-8")
    except (OSError, zipfile.BadZipFile) as exc:
        if archive.exists():
            archive.unlink()
        print(f"Backup failed: {exc}")
        append_event(args.log_jsonl,"backup_failed",source=source.name,error_type=type(exc).__name__)
        return 1
    append_event(args.log_jsonl,"backup_created",source=source.name,files=len(manifest),archive_bytes=archive.stat().st_size,archive_sha256=digest(archive))
    print(f"Archive: {archive}")
    print(f"Manifest: {sidecar}")
    print(f"Files: {len(manifest)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
