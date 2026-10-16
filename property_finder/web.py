"""Dashboard server (stdlib only). Members-only: every /api route needs an approved sign-in."""
from __future__ import annotations

import csv
import io
import json
import os
import threading
import webbrowser
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import auth, roi, scrape, store, websearch

JOB = scrape.Job()
PAGE = Path(__file__).parent / "static" / "index.html"
LOGIN = Path(__file__).parent / "static" / "login.html"
COOKIE = "pf_session"
ADMIN_GET = {"/api/websearch", "/api/admin/users"}
ADMIN_POST = {"/api/search", "/api/assumptions", "/api/websearch", "/api/admin/status"}
CSV_COLS = ["Name", "Phone", "Email", "Website", "Source", "Notes"]
STATIC = Path(__file__).parent / "static"


def to_csv(rows: list[dict]) -> str:
    """Column names match lead-verifier's input, so exports go straight into `lead-verifier run`."""
    buf = io.StringIO()
    wr = csv.writer(buf, lineterminator="\n")
    wr.writerow(CSV_COLS + ["Area", "Type", "Price", "SizeSqft", "Beds", "Owner", "GrossYieldPct", "NetYieldPct", "TotalReturnPct", "Status", "Evidence", "FoundVia", "Snippet", "DataFlags"])
    for r in rows:
        note = f"{r['title'][:90]} | {r['status']} | {r['notes']}".strip(" |")
        wr.writerow([r["poster"], r["phone"], "", r["url"], r["source"], note, r["area"], r["ptype"], r["price"], r["size_sqft"],
                     r["beds"], {1: "owner", 0: "agent"}.get(r["is_owner"], ""), r["gross"], r["net"], r["total"], r["status"],
                     r.get("evidence") or "listing page", r.get("found_via") or "", r.get("snippet") or "", r.get("data_flags") or ""])
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
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code, obj):
            self._send(code, json.dumps(obj).encode())

        def _token(self):
            c = SimpleCookie(self.headers.get("Cookie", ""))
            return c[COOKIE].value if COOKIE in c else None

        def _ip(self):
            if os.environ.get("PF_TRUST_PROXY") == "1" and self.headers.get("X-Forwarded-For"):
                return self.headers["X-Forwarded-For"].split(",")[-1].strip()
            return self.client_address[0]

        def _cookie(self, token, age):
            secure = self.headers.get("X-Forwarded-Proto") == "https" or os.environ.get("PF_SECURE_COOKIES") == "1"
            return {"Set-Cookie": f"{COOKIE}={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={age}" + ("; Secure" if secure else "")}

        def _user(self):
            con = store.connect()
            try:
                return auth.user_for(con, self._token())
            finally:
                con.close()

        def _gate(self, path, admin_paths):
            """The signed-in member, or None after sending 401/403. Nothing under /api is public except sign-in itself."""
            user = self._user()
            if not user:
                self._json(401, {"error": "Sign in required."})
                return None
            if path in admin_paths and user["role"] != "admin":
                self._json(403, {"error": "Only an MRA admin can do this."})
                return None
            return user

        def do_GET(self):
            u = urlparse(self.path)
            qs = {k: v[0] for k, v in parse_qs(u.query).items()}
            if u.path == "/":
                page = PAGE if self._user() else LOGIN
                self._send(200, page.read_bytes(), "text/html; charset=utf-8")
                return
            if u.path in ("/static/logo.png", "/static/logo-navy.png"):
                self._send(200, (STATIC / u.path.rsplit("/", 1)[1]).read_bytes(), "image/png")
                return
            if not u.path.startswith("/api/"):
                self._json(404, {"error": "not found"})
                return
            if not self._gate(u.path, ADMIN_GET):
                return
            if u.path == "/api/auth/me":
                self._json(200, self._user())
            elif u.path == "/api/admin/users":
                con = store.connect()
                self._json(200, {"users": auth.list_users(con)})
                con.close()
            elif u.path == "/api/assumptions":
                con = store.connect()
                self._json(200, roi.load(con))
                con.close()
            elif u.path == "/api/websearch":
                con = store.connect()
                self._json(200, websearch.status(con))
                con.close()
            elif u.path == "/api/config":
                self._json(200, {"areas": scrape.AREAS, "ptypes": ["apartment", "house", "land"], "statuses": store.STATUSES,
                                 "sources": [{k: s[k] for k in ("id", "name", "kind", "mode", "confidence")} for s in scrape.SOURCES.values()]
                                 + [{"id": q["id"], "name": q["name"], "kind": "search", "mode": "search", "confidence": ""} for q in websearch.QUERIES]})
            elif u.path == "/api/job":
                self._json(200, JOB.snapshot())
            elif u.path in ("/api/listings", "/api/export.csv"):
                con = store.connect()
                rows = store.query(con, area=qs.get("area", ""), ptype=qs.get("ptype", ""), q=qs.get("q", ""),
                                   max_price=float(qs["max"]) if qs.get("max") else None,
                                   min_roi=float(qs["minroi"]) if qs.get("minroi") else None, owner_only=qs.get("owner") == "1",
                                   status=qs.get("status", ""), sort=qs.get("sort", "roi"), limit=3000)
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
            origin = self.headers.get("Origin")
            if origin and urlparse(origin).netloc != self.headers.get("Host"):
                self._json(403, {"error": "Cross-site request refused."})
                return
            try:
                b = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length") or 0), 100_000)) or b"{}")
                if u.path in ("/api/auth/login", "/api/auth/signup", "/api/auth/logout"):
                    self._auth_post(u.path, b)
                    return
                user = self._gate(u.path, ADMIN_POST)
                if not user:
                    return
                if u.path == "/api/admin/status":
                    con = store.connect()
                    auth.set_status(con, int(b.get("id", 0)), str(b.get("status", "")), user["email"])
                    self._json(200, {"users": auth.list_users(con)})
                    con.close()
                elif u.path == "/api/search":
                    areas = [a for a in b.get("areas", []) if a in scrape.AREAS] or list(scrape.AREAS)
                    ok = JOB.start(areas, [t for t in b.get("ptypes", []) if t in scrape.PTYPES] or ["apartment", "house", "land"],
                                   b.get("sources") or list(scrape.SOURCES), (b.get("q") or "")[:80],
                                   min(int(b.get("details") or 0), 40), b.get("benchmark", True) is not False,
                                   b.get("web", True) is not False)
                    self._json(200 if ok else 409, {"started": ok})
                elif u.path == "/api/assumptions":
                    con = store.connect()
                    roi.save(con, b)
                    self._json(200, roi.load(con))
                    con.close()
                elif u.path == "/api/websearch":
                    con = store.connect()
                    websearch.save_key(con, str(b.get("provider", "serper")), str(b.get("key", "")), b.get("budget"))
                    self._json(200, websearch.status(con))
                    con.close()
                elif u.path == "/api/lead":
                    con = store.connect()
                    store.set_lead(con, str(b.get("id", "")), b.get("status"), b.get("notes"))
                    con.close()
                    self._json(200, {"ok": True})
                else:
                    self._json(404, {"error": "not found"})
            except auth.AuthError as e:
                self._json(400, {"error": str(e)})
            except Exception:  # noqa: BLE001
                self._json(400, {"error": "bad request"})

        def _auth_post(self, path, b):
            con = store.connect()
            try:
                if path == "/api/auth/signup":
                    auth.request_access(con, b.get("email"), b.get("name"), str(b.get("password", "")), b.get("phone", ""), b.get("note", ""))
                    self._json(200, {"ok": True, "message": "Request sent. MRA will approve it after verifying you."})
                elif path == "/api/auth/login":
                    token, user = auth.login(con, b.get("email"), str(b.get("password", "")), self._ip())
                    self._send(200, json.dumps(user).encode(), extra=self._cookie(token, auth.SESSION_DAYS * 86400))
                else:
                    auth.logout(con, self._token())
                    self._send(200, b"{}", extra=self._cookie("", 0))
            finally:
                con.close()
    return H


def serve(port=8770, open_browser=True, host="127.0.0.1") -> ThreadingHTTPServer:
    srv = ThreadingHTTPServer((host, port), handler())
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(f"http://127.0.0.1:{srv.server_port}")).start()
    return srv
