#!/usr/bin/env python3
"""Forward hub events to an explicitly configured HTTPS JSON webhook."""

import json
import hashlib
import os
import sys
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None


def deliver(event: dict, destination: str, token: str = "") -> None:
    body={key:event[key] for key in ("source","external_id","kind","occurred_at","payload")}
    digest=hashlib.sha256(event["idempotency_key"].encode()).hexdigest()
    headers={"Content-Type":"application/json","Idempotency-Key":f"hub-{digest}"}
    if token:
        headers["Authorization"]="Bearer "+token
    with build_opener(NoRedirect).open(Request(destination,data=json.dumps(body,separators=(",",":" )).encode(),headers=headers,method="POST"),timeout=20) as response:
        if not 200<=response.status<300:
            raise RuntimeError(f"destination returned HTTP {response.status}")


def save_cursor(path: Path, event_id: int) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,temp_name=tempfile.mkstemp(prefix=path.name+".",dir=path.parent)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as stream:
            json.dump({"after_id":event_id},stream);stream.write("\n");stream.flush();os.fsync(stream.fileno())
        os.replace(temp_name,path)
    except Exception:
        try: os.unlink(temp_name)
        except OSError: pass
        raise


def main() -> int:
    source=os.environ.get("HUB_URL","http://127.0.0.1:8000").rstrip("/")
    destination=os.environ.get("HUB_OUTBOUND_URL","").strip()
    read_key=os.environ.get("HUB_READ_KEY","")
    if not destination or not read_key:
        print("Set HUB_OUTBOUND_URL and HUB_READ_KEY before dispatching.",file=sys.stderr);return 2
    parsed=urlparse(destination)
    local_hosts={"localhost","127.0.0.1","::1"}
    if parsed.username or parsed.password or (parsed.scheme!="https" and not (parsed.scheme=="http" and parsed.hostname in local_hosts)):
        print("Destination must use HTTPS (HTTP is allowed for loopback testing only).",file=sys.stderr);return 2
    cursor_path=Path(os.environ.get("HUB_OUTBOUND_CURSOR","hub-outbound-cursor.json"))
    try:
        cursor=json.loads(cursor_path.read_text(encoding="utf-8")).get("after_id",0) if cursor_path.exists() else 0
        if isinstance(cursor,bool) or not isinstance(cursor,int) or cursor<0: raise ValueError("invalid cursor")
    except (OSError,json.JSONDecodeError,ValueError) as exc:
        print(f"Cannot read dispatch cursor: {exc}",file=sys.stderr);return 2
    opener=build_opener(NoRedirect)
    try:
        request=Request(f"{source}/api/v1/events?after_id={cursor}&limit=100",headers={"X-API-Key":read_key})
        with opener.open(request,timeout=15) as response:
            events=json.loads(response.read(2_000_000))
        for event in events:
            token=os.environ.get("HUB_OUTBOUND_TOKEN","")
            deliver(event,destination,token)
            save_cursor(cursor_path,event["id"])
            cursor=event["id"]
    except (OSError,HTTPError,URLError,TimeoutError,ValueError,RuntimeError,KeyError) as exc:
        print(f"Dispatch stopped at event {cursor}: {type(exc).__name__}; retry is safe with the same idempotency key.",file=sys.stderr)
        return 1
    print(f"Delivered through event {cursor}.")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
