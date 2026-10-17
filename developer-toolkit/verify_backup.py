#!/usr/bin/env python3
"""Verify a toolkit ZIP backup against its SHA-256 sidecar manifest."""

import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath

MAX_FILES=100_000
MAX_TOTAL_BYTES=5_000_000_000


def safe_member_name(name: str) -> str:
    if not name or "\\" in name or name.startswith("/"):
        raise ValueError(f"Unsafe archive path: {name!r}")
    parts=name.rstrip("/").split("/")
    if any(part in {"",".",".."} for part in parts) or ":" in parts[0]:
        raise ValueError(f"Unsafe archive path: {name!r}")
    return PurePosixPath(*parts).as_posix()


def verify_archive(archive_path: Path, manifest_path: Path | None=None) -> dict:
    manifest_path=manifest_path or archive_path.with_suffix(".manifest.json")
    manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
    entries=manifest.get("files") if isinstance(manifest,dict) else None
    if not isinstance(entries,list) or len(entries)>MAX_FILES:
        raise ValueError("Manifest has no valid files list or exceeds the file limit")
    expected={}
    for entry in entries:
        if not isinstance(entry,dict) or not isinstance(entry.get("path"),str):
            raise ValueError("Manifest contains a malformed file record")
        path=safe_member_name(entry["path"])
        if path in expected:
            raise ValueError(f"Manifest lists a duplicate path: {path}")
        if isinstance(entry.get("size"),bool) or not isinstance(entry.get("size"),int) or entry["size"]<0:
            raise ValueError(f"Manifest has an invalid byte count for {path}")
        digest=entry.get("sha256")
        if not isinstance(digest,str) or len(digest)!=64 or any(c not in "0123456789abcdef" for c in digest.lower()):
            raise ValueError(f"Manifest has an invalid SHA-256 value for {path}")
        expected[path]=entry
    total=0
    with zipfile.ZipFile(archive_path) as archive:
        actual={}
        for info in archive.infolist():
            name=safe_member_name(info.filename)
            if info.is_dir():
                continue
            mode=(info.external_attr>>16)&0o170000
            if mode not in (0,stat.S_IFREG):
                raise ValueError(f"Unsupported non-regular archive member: {name}")
            if name in actual:
                raise ValueError(f"Archive contains a duplicate path: {name}")
            actual[name]=info
        if set(actual)!=set(expected):
            missing=sorted(set(expected)-set(actual)); extra=sorted(set(actual)-set(expected))
            raise ValueError(f"Archive/manifest file list differs (missing={missing[:3]}, extra={extra[:3]})")
        for name,info in actual.items():
            record=expected[name]
            if info.file_size!=record["size"]:
                raise ValueError(f"Byte count mismatch for {name}")
            total+=info.file_size
            if total>MAX_TOTAL_BYTES:
                raise ValueError("Backup exceeds the 5 GB verification limit")
            digest=hashlib.sha256();count=0
            with archive.open(info) as stream:
                for block in iter(lambda:stream.read(1024*1024),b""):
                    count+=len(block);digest.update(block)
            if count!=record["size"] or digest.hexdigest()!=record["sha256"].lower():
                raise ValueError(f"SHA-256 mismatch for {name}")
    return {"files":len(expected),"bytes":total,"created_utc":manifest.get("created_utc")}


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive",type=Path)
    parser.add_argument("--manifest",type=Path,help="sidecar manifest; defaults to ARCHIVE.manifest.json")
    args=parser.parse_args()
    try:
        result=verify_archive(args.archive,args.manifest)
    except (OSError,ValueError,KeyError,json.JSONDecodeError,zipfile.BadZipFile,RuntimeError) as exc:
        parser.error(f"Backup verification failed: {exc}")
    print(f"Verified {result['files']} file(s), {result['bytes']} bytes; created {result['created_utc']}.")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
