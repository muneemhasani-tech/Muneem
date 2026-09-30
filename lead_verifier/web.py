"""Local web UI (stdlib only). Binds to 127.0.0.1 so lead data never leaves the machine."""
from __future__ import annotations

import csv
import io
import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .config import load_config
from .io_csv import build_leads, lead_values, out_headers, read_csv_text
from .quota import Quota
from .cache import Cache
from .service import check_one, grade_leads, keys_configured, lead_json

MAX_UPLOAD = 20 * 1024 * 1024
MAX_ROWS_UI = 2000


def make_handler(cfg: dict):
    page = (Path(__file__).parent / "static" / "index.html").read_bytes()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # never log request lines (they could carry lead data)
            pass

        def _send(self, code: int, body: bytes, ctype: str = "application/json") -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, obj) -> None:
            self._send(code, json.dumps(obj).encode())

        def _body(self) -> bytes:
            n = int(self.headers.get("Content-Length") or 0)
            if n > MAX_UPLOAD:
                raise ValueError("file too large (20 MB max)")
            return self.rfile.read(n)

        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/":
                self._send(200, page, "text/html; charset=utf-8")
            elif path == "/api/status":
                cache = Cache(cfg["cache"]["path"])
                q = Quota(cache, cfg["providers"], cfg["timezone"])
                usage = {p: {"used": q.used(p), "limit": q.limit(p)} for p in cfg["providers"]}
                cache.close()
                self._json(200, {"keys": keys_configured(), "quota": usage})
            else:
                self._json(404, {"error": "not found"})

        def do_POST(self):
            url = urlparse(self.path)
            offline = parse_qs(url.query).get("offline", ["0"])[0] == "1"
            try:
                if url.path == "/api/check":
                    b = json.loads(self._body() or b"{}")
                    lead, _ = check_one(b.get("phone", ""), b.get("email", ""), b.get("website", ""), cfg, offline)
                    self._json(200, lead_json(lead))
                elif url.path == "/api/upload":
                    headers, rows = read_csv_text(self._body())
                    if not headers:
                        raise ValueError("that file looks empty")
                    truncated = len(rows) > MAX_ROWS_UI
                    leads = build_leads(headers, rows[:MAX_ROWS_UI])
                    s = grade_leads(leads, cfg, offline)
                    buf = io.StringIO()
                    w = csv.writer(buf, lineterminator="\n")
                    w.writerow(headers + out_headers(headers))
                    w.writerows(l.cells + lead_values(l) for l in leads)
                    self._json(200, {
                        "leads": [lead_json(l) for l in leads],
                        "summary": {"rows": s.rows_in, "grades": dict(s.grades), "credits": s.credits,
                                    "deferred": s.deferred, "truncated": truncated},
                        "csv": buf.getvalue(),
                    })
                else:
                    self._json(404, {"error": "not found"})
            except Exception as exc:  # noqa: BLE001  show a friendly message, never a traceback
                self._json(400, {"error": str(exc) if isinstance(exc, ValueError) else "Something went wrong while checking. Please try again."})

    return Handler


def serve(cfg: dict, port: int = 8765, open_browser: bool = True) -> ThreadingHTTPServer:
    srv = ThreadingHTTPServer(("127.0.0.1", port), make_handler(cfg))
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(f"http://127.0.0.1:{srv.server_port}")).start()
    return srv
