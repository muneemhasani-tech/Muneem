"""Send the built emails through the owner's own Gmail via a small Google Apps Script web app (docs/MRA_MAILER.gs).

The script runs as the owner, sends with GmailApp (so the owner's Gmail is the sender), refuses any recipient that is not on
its own allow-list, refuses subjects that do not start with "MRA", and skips an email already sent in the last two days.
The web-app URL is read from the MRA_MAILER_URL environment variable; it is never stored in this public repo.

python -m property_finder send --manifest mail_out/manifest.json [--png onepager.png]
"""
from __future__ import annotations

import base64
import json
import os
import time
import urllib.request
from pathlib import Path


def post(url: str, payload: dict, timeout: int = 60) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # Apps Script answers through a redirect; urllib follows it
        body = r.read().decode("utf-8", "replace")
    try:
        return json.loads(body)
    except ValueError:
        return {"ok": False, "error": "unexpected reply: " + body[:200]}


def send_manifest(manifest: str, png: str | None = None, url: str | None = None, pause: float = 1.0) -> list[dict]:
    url = url or os.environ.get("MRA_MAILER_URL", "")
    if not url.startswith("https://script.google.com/"):
        return [{"to": "-", "ok": False, "error": "MRA_MAILER_URL is not set to the Apps Script web-app URL"}]
    base = Path(manifest).parent
    entries = json.loads(Path(manifest).read_text(encoding="utf-8"))
    inline = base64.b64encode(Path(png).read_bytes()).decode() if png and Path(png).exists() else ""
    out = []
    for e in entries:
        if not e.get("count") and not e.get("all"):
            out.append({"to": e["to"], "subject": e["subject"], "ok": True, "skipped": "no listings in their areas"})
            continue
        payload = {"to": e["to"], "subject": e["subject"], "html": (base / e["html"]).read_text(encoding="utf-8"),
                   "text": (base / e["text"]).read_text(encoding="utf-8")[:20000]}
        if inline:
            payload["inline_png"] = inline
        try:
            res = post(url, payload)
        except Exception as ex:  # noqa: BLE001
            res = {"ok": False, "error": f"{type(ex).__name__}: {ex}"[:200]}
        out.append({"to": e["to"], "subject": e["subject"], **res})
        time.sleep(pause)
    return out
