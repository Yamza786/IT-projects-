"""Append private, machine-readable operational events for local toolkit runs."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path


def append_event(path: Path | None, event: str, **fields) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    record={"timestamp":datetime.now(timezone.utc).isoformat(timespec="milliseconds"),"event":event,**fields}
    encoded=(json.dumps(record,ensure_ascii=False,separators=(",",":"))+"\n").encode("utf-8")
    descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)
    try:
        if hasattr(os,"fchmod"):
            os.fchmod(descriptor,0o600)
        os.write(descriptor,encoded)
    finally:
        os.close(descriptor)
