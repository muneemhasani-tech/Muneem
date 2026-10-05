"""Local dashboard server (stdlib only, 127.0.0.1)."""
from __future__ import annotations

import csv
import io
import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import scrape, store

JOB = scrape.Job()
PAGE = Path(__file__).parent / "static" / "index.html"
CSV_COLS = ["Name", "Phone", "Email", "Website", "Source", "Notes"]


def to_csv(rows: list[dict]) -> str:
    """Column names match lead-verifier's input, so exports go straight into `lead-verifier run`."""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(CSV_COLS + ["Area", "Purpose", "Type", "Price", "SizeSqft", "Beds", "Owner", "Status"])
    for r in rows:
        note = f"{r['title'][:90]} | {r['status']} | {r['notes']}".strip(" |")
        w.writerow([r["poster"], r["phone"], "", r["url"], r["source"], note, r["area"], r["purpose"], r["ptype"],
                    r["price"], r["size_sqft"], r["beds"], {1: "owner", 0: "agent"}.get(r["is_owner"], ""), r["status"]])
    return buf.getvalue()


def handler():
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body: bytes, ctype="application/json", extra=None):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code, obj):
            self._send(code, json.dumps(obj).encode())

        def do_GET(self):
            u = urlparse(self.path)
            qs = {k: v[0] for k, v in parse_qs(u.query).items()}
            if u.path == "/":
                self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
            elif u.path == "/api/config":
                self._json(200, {"areas": scrape.AREAS, "ptypes": scrape.PTYPES, "statuses": store.STATUSES,
                                 "sources": [{k: s[k] for k in ("id", "name", "kind", "mode", "confidence")} for s in scrape.SOURCES.values()]})
            elif u.path == "/api/job":
                self._json(200, JOB.snapshot())
            elif u.path in ("/api/listings", "/api/export.csv"):
                con = store.connect()
                rows = store.query(con, area=qs.get("area", ""), purpose=qs.get("purpose", ""), ptype=qs.get("ptype", ""),
                                   q=qs.get("q", ""), min_price=float(qs["min"]) if qs.get("min") else None,
                                   max_price=float(qs["max"]) if qs.get("max") else None, owner_only=qs.get("owner") == "1",
                                   status=qs.get("status", ""), sort=qs.get("sort", "new"))
                if u.path == "/api/export.csv":
                    self._send(200, to_csv(rows).encode("utf-8-sig"), "text/csv; charset=utf-8",
                               {"Content-Disposition": "attachment; filename=property-leads.csv"})
                else:
                    self._json(200, {"rows": rows, "stats": store.stats(con)})
                con.close()
            else:
                self._json(404, {"error": "not found"})

        def do_POST(self):
            u = urlparse(self.path)
            try:
                b = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
                if u.path == "/api/search":
                    areas = [a for a in b.get("areas", []) if a in scrape.AREAS] or list(scrape.AREAS)
                    ok = JOB.start(areas, b.get("purposes") or ["sale", "rent"], b.get("ptypes") or ["apartment"],
                                   b.get("sources") or list(scrape.SOURCES), (b.get("q") or "")[:80],
                                   min(int(b.get("details") or 0), 40))
                    self._json(200 if ok else 409, {"started": ok})
                elif u.path == "/api/lead":
                    con = store.connect()
                    store.set_lead(con, str(b.get("id", "")), b.get("status"), b.get("notes"))
                    con.close()
                    self._json(200, {"ok": True})
                else:
                    self._json(404, {"error": "not found"})
            except Exception:  # noqa: BLE001
                self._json(400, {"error": "bad request"})
    return H


def serve(port=8770, open_browser=True) -> ThreadingHTTPServer:
    srv = ThreadingHTTPServer(("127.0.0.1", port), handler())
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(f"http://127.0.0.1:{srv.server_port}")).start()
    return srv
