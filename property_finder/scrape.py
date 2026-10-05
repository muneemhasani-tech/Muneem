"""Runs searches across sources politely (thread pool, per-source delay) and reports per-source health."""
from __future__ import annotations

import json
import re
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote_plus

from . import parse, store

CONF = json.loads((Path(__file__).parent / "sources.json").read_text(encoding="utf-8"))
AREAS: dict[str, str] = CONF["areas"]
SOURCES: dict[str, dict] = {s["id"]: s for s in CONF["sources"]}
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
PTYPES = ["apartment", "house", "land", "commercial"]


def fetch(url: str, timeout: int = 20) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en", "Accept": "text/html"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(3_000_000).decode(r.headers.get_content_charset() or "utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:  # noqa: BLE001  network failure is reported as status 0
        return 0, ""


def build_url(src: dict, area: str, purpose: str, ptype: str, q: str = "") -> str | None:
    if purpose not in src.get("purposes", {"sale": "sale", "rent": "rent"}):
        return None
    types = src.get("types")
    if types is not None and ptype not in types:
        return None
    path_slug = "-in-{area}" in src["url"]  # slug URLs can't take free text, so keep the area there
    term = quote_plus(q) if q and not path_slug else area
    return src["url"].format(area=term, purpose=src.get("purposes", {}).get(purpose, purpose),
                             type=(types or {}).get(ptype, ptype), q=quote_plus(q))


def link_outs(areas: list[str], purpose: str, ptype: str, q: str = "") -> list[dict]:
    """Search links for sites we can't or shouldn't scrape (Facebook, Google, developer sites)."""
    out = []
    for s in SOURCES.values():
        if s["mode"] == "link":
            for a in areas or ["dhaka"]:
                out.append({"source": s["id"], "name": s["name"], "kind": s["kind"], "area": a,
                            "url": build_url(s, q or a, purpose, ptype)})
    return out


def _area_in(text: str, fallback: str) -> str:
    for slug, label in AREAS.items():
        if re.search(rf"\b{slug}\b", text, re.I):
            return slug
    return fallback


def search_source(src: dict, area: str, purpose: str, ptype: str, q: str, details: int) -> dict:
    url = build_url(src, area, purpose, ptype, q)
    res = {"source": src["id"], "url": url, "status": 0, "found": 0, "new": 0, "error": ""}
    if not url:
        res["error"] = "unsupported combo"
        return res
    status, html = fetch(url)
    res["status"] = status
    if status != 200:
        res["error"] = {0: "network blocked/timeout", 403: "blocked (403)", 404: "page not found - fix URL in sources.json"}.get(status, f"HTTP {status}")
        return res
    rows = parse.extract(html, url)
    res["found"] = len(rows)
    if not rows:
        res["error"] = "page loaded but no listings recognised (site may render in JS) - use link-out"
    con = store.connect()
    fetched = 0
    for r in rows:
        r.update(source=src["id"], purpose=purpose, ptype=ptype, area=_area_in(r["title"], area))
        if details and not r.get("phone") and fetched < details:
            time.sleep(1.0)
            st, page = fetch(r["url"])
            fetched += 1
            if st == 200:
                r.update({k: v for k, v in parse.detail_contact(page).items() if v})
        res["new"] += store.upsert(con, r)
    con.commit()
    con.close()
    return res


class Job:
    def __init__(self):
        self.lock, self.state = threading.Lock(), {"running": False, "done": 0, "total": 0, "results": [], "links": []}

    def start(self, areas, purposes, ptypes, sources, q="", details=0) -> bool:
        with self.lock:
            if self.state["running"]:
                return False
            tasks = [(SOURCES[s], a, p, t) for s in sources if s in SOURCES and SOURCES[s]["mode"] == "scrape"
                     for a in areas for p in purposes for t in ptypes]
            self.state = {"running": True, "done": 0, "total": len(tasks), "results": [],
                          "links": link_outs(areas, purposes[0] if purposes else "sale", ptypes[0] if ptypes else "apartment", q)}
        threading.Thread(target=self._run, args=(tasks, q, details), daemon=True).start()
        return True

    def _run(self, tasks, q, details):
        by_src: dict[str, threading.Lock] = {}
        for t in tasks:
            by_src.setdefault(t[0]["id"], threading.Lock())

        def one(t):
            src, a, p, ty = t
            with by_src[src["id"]]:  # one request at a time per site, with a pause
                r = search_source(src, a, p, ty, q, details)
                time.sleep(1.5)
            with self.lock:
                self.state["results"].append({**r, "area": a, "purpose": p, "ptype": ty})
                self.state["done"] += 1

        with ThreadPoolExecutor(max_workers=8) as ex:
            list(ex.map(one, tasks))
        with self.lock:
            self.state["running"] = False

    def snapshot(self) -> dict:
        with self.lock:
            return json.loads(json.dumps(self.state))


def probe() -> list[dict]:
    """Health check for every scrapeable source: does it respond, and do we recognise listings?"""
    out = []
    for s in SOURCES.values():
        if s["mode"] != "scrape":
            continue
        p = next(iter(s.get("purposes", {"sale": 1})))
        t = next(iter(s["types"])) if s.get("types") else "apartment"
        status, html = fetch(build_url(s, "gulshan", p, t) or "")
        out.append({"source": s["id"], "status": status, "listings": len(parse.extract(html, s["url"])) if html else 0})
    return out
