#!/usr/bin/env python3
"""Idempotently load a small, English-language set of official SA resource links."""

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB=Path("portal.db")
SEED_FILE=Path(__file__).with_name("sample-resources.json")


def seed(db_path: Path=DEFAULT_DB, seed_file: Path=SEED_FILE) -> int:
    records=json.loads(seed_file.read_text(encoding="utf-8"))
    if not isinstance(records,list): raise ValueError("seed file must contain a JSON array")
    db_path.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(db_path) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS resources(
            id INTEGER PRIMARY KEY,slug TEXT NOT NULL,language TEXT NOT NULL,title TEXT NOT NULL,summary TEXT NOT NULL,
            topic TEXT NOT NULL,source_title TEXT NOT NULL,source_url TEXT NOT NULL,verified_on TEXT NOT NULL,created_at TEXT NOT NULL,
            UNIQUE(slug,language))""")
        now=datetime.now(timezone.utc).isoformat(timespec="seconds")
        before=db.total_changes
        for row in records:
            if not isinstance(row,dict) or row.get("language")!="en" or not row.get("source_url","").startswith("https://"):
                raise ValueError("seed entries must be English records with HTTPS sources")
            db.execute("INSERT INTO resources(slug,language,title,summary,topic,source_title,source_url,verified_on,created_at) VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(slug,language) DO NOTHING",
                       (row["slug"],row["language"],row["title"],row["summary"],row["topic"],row["source_title"],row["source_url"],row["verified_on"],now))
        return db.total_changes-before


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db",type=Path,default=DEFAULT_DB,help="portal SQLite database path")
    args=parser.parse_args()
    try:
        added=seed(args.db)
    except (OSError,sqlite3.Error,json.JSONDecodeError,ValueError,KeyError) as exc:
        parser.error(str(exc))
    print(f"Added {added} English official-source resource(s); existing records were left unchanged.")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
