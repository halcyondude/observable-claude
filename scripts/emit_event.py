#!/usr/bin/env python3
"""Command fallback hook for CC Observer.

Reads hook payload from stdin, appends to fallback JSONL, and attempts
HTTP delivery to the collector. Always exits 0 to avoid blocking Claude Code.
"""

import json
import os
import sys
import time
from urllib.request import Request, urlopen
from urllib.error import URLError

COLLECTOR_URL = "http://localhost:4001/events"
HTTP_TIMEOUT = 1  # seconds
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "data")
FALLBACK_PATH = os.path.join(DATA_DIR, "fallback.jsonl")


def main():
    try:
        event_type = sys.argv[1] if len(sys.argv) > 1 else "Unknown"

        raw = sys.stdin.read()
        try:
            payload = json.loads(raw) if raw.strip() else {}
        except (json.JSONDecodeError, ValueError):
            payload = {"_raw": raw}

        payload["event_type"] = event_type
        payload["_fallback_ts"] = time.time()

        line = json.dumps(payload, separators=(",", ":"))

        os.makedirs(DATA_DIR, exist_ok=True)
        with open(FALLBACK_PATH, "a") as f:
            f.write(line + "\n")

        body = json.dumps(payload).encode("utf-8")
        req = Request(
            COLLECTOR_URL,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            resp = urlopen(req, timeout=HTTP_TIMEOUT)
            resp.read()
            resp.close()
        except (URLError, OSError, TimeoutError):
            pass  # JSONL backup already written

    except Exception:
        pass  # never block Claude Code

    sys.exit(0)


if __name__ == "__main__":
    main()
