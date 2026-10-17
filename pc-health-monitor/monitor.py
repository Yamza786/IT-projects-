#!/usr/bin/env python3
"""Local cross-platform host health snapshot and history."""
import argparse, json, os, platform, sqlite3, time
from datetime import datetime, timezone

def snapshot():
    data={"captured_at":datetime.now(timezone.utc).isoformat(),"platform":platform.platform(),"hostname":platform.node()}
    try:
        import psutil
        data.update(cpu_percent=psutil.cpu_percent(interval=0.3),memory_percent=psutil.virtual_memory().percent,disk_percent=psutil.disk_usage(os.path.abspath(os.sep)).percent,boot_time=psutil.boot_time())
        data["alerts"]=[f"{k} at {data[k]:.1f}%" for k,limit in (("cpu_percent",90),("memory_percent",90),("disk_percent",95)) if data[k]>=limit]
    except ImportError: data["metrics_note"]="Install psutil for CPU, memory and disk metrics."
    return data
def save(data):
    c=sqlite3.connect(os.environ.get("PC_HEALTH_DB","pc-health.db")); c.execute("CREATE TABLE IF NOT EXISTS snapshots(id INTEGER PRIMARY KEY, captured_at TEXT, data TEXT)");c.execute("INSERT INTO snapshots(captured_at,data) VALUES(?,?)",(data["captured_at"],json.dumps(data)));c.commit();c.close()
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--samples",type=int,default=1);p.add_argument("--interval",type=float,default=2);p.add_argument("--history",action="store_true");a=p.parse_args()
    if a.samples<1 or a.samples>60 or not 0<=a.interval<=300:p.error("samples must be 1..60 and interval 0..300 seconds")
    if a.history:
        c=sqlite3.connect(os.environ.get("PC_HEALTH_DB","pc-health.db"))
        try:
            for row in c.execute("SELECT captured_at,data FROM snapshots ORDER BY id DESC LIMIT 20"):print(row[0],row[1])
        except sqlite3.OperationalError:print("No history yet")
        return
    for ix in range(a.samples):
        data=snapshot();save(data);print(json.dumps(data,indent=2))
        if ix+1<a.samples:time.sleep(a.interval)
if __name__=="__main__":main()
