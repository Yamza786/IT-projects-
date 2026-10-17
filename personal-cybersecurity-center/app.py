#!/usr/bin/env python3
"""Local alert notebook backed by the existing offline SSH/PAM analyzer."""
import argparse
import hashlib
import importlib.util
import json
import os
import sqlite3
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("auth_analyzer", BASE / "security-log-analyzer" / "analyze.py")
analyzer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analyzer)

def connect():
    db = sqlite3.connect(os.environ.get("SECURITY_CENTER_DB", "security-center.db"))
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE IF NOT EXISTS batches (id INTEGER PRIMARY KEY, sha256 TEXT UNIQUE, source TEXT, imported_at TEXT DEFAULT CURRENT_TIMESTAMP)")
    db.execute("CREATE TABLE IF NOT EXISTS alerts (id INTEGER PRIMARY KEY, batch_id INTEGER, rule TEXT, source TEXT, severity TEXT, detail TEXT, status TEXT DEFAULT 'open', note TEXT DEFAULT '', FOREIGN KEY(batch_id) REFERENCES batches(id))")
    return db

def ingest(path):
    raw = Path(path).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    result = analyzer.analyze(Path(path), threshold=5)
    with connect() as db:
        cur = db.execute("INSERT OR IGNORE INTO batches(sha256,source) VALUES (?,?)", (digest, Path(path).name))
        if cur.rowcount == 0:
            print("Already imported", digest)
            return
        bid = cur.lastrowid
        for item in result["alerts"]:
            db.execute("INSERT INTO alerts(batch_id,rule,source,severity,detail) VALUES (?,?,?,?,?)", (bid, item["rule"], item["source"], item["severity"], json.dumps(item, sort_keys=True)))
        print(f"Imported {Path(path).name}: {len(result['alerts'])} alerts; sha256={digest}")

def main():
    p = argparse.ArgumentParser(description=__doc__); sub = p.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("ingest"); i.add_argument("logfile")
    sub.add_parser("alerts")
    n = sub.add_parser("note"); n.add_argument("id", type=int); n.add_argument("text")
    a = p.parse_args()
    if a.cmd == "ingest": ingest(a.logfile)
    elif a.cmd == "alerts":
        for row in connect().execute("SELECT id, severity, rule, source, status FROM alerts WHERE status='open' ORDER BY id"):
            print(f"#{row['id']} [{row['severity']}] {row['rule']} {row['source']}")
    else:
        with connect() as db:
            cur = db.execute("UPDATE alerts SET status='reviewed', note=? WHERE id=?", (a.text, a.id))
            print("Alert reviewed" if cur.rowcount else "Alert not found")

if __name__ == "__main__": main()
