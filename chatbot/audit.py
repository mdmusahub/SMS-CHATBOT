"""Append-only JSONL audit trail. Logs ids and decisions, never message text or passwords."""
import json
import threading
import time
from pathlib import Path

_lock = threading.Lock()


def audit(path: str, event: str, **fields) -> None:
    rec = {"ts": round(time.time(), 3), "event": event, **fields}
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with _lock, p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, default=str) + "\n")
    except OSError:
        pass  # auditing must never break a chat turn
