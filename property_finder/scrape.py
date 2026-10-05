"""Runs searches across sources politely (thread pool, per-source delay) and reports per-source health."""
from __future__ import annotations

import json
import re
import threading
import time
import urllib.error
import urllib.request
import urllib.robotparser
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote_plus, urlparse

from . import parse, store

CONF = json.loads((Path(__file__).parent / "sources.json").read_text(encoding="utf-8"))
AREAS: dict[str, str] = CONF["areas"]
SOURCES: dict[str, dict] = {s["id"]: s for s in CONF["sources"]}
UA = "MRA-PropertyFinder/1.0 (lead research; mrarealestatebd.com)"  # honest bot name, so robots.txt rules for it apply
PTYPES = ["apartment", "house", "land", "commercial"]


def fetch(url: str, timeout: int = 20) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en", "Accept": "text/html,text/plain"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(3_000_000).decode(r.headers.get_content_charset() or "utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        try:
            return e.code, e.read(200_000).decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            return e.code, ""
    except Exception:  # noqa: BLE001  network failure is reported as status 0
        return 0, ""


_ROBOTS: dict[str, tuple[str, urllib.robotparser.RobotFileParser | None]] = {}
_RLOCK = threading.Lock()


def robots(url: str) -> tuple[str, urllib.robotparser.RobotFileParser | None]:
    """(state, parser) per host. state: ok | none (404/410, everything allowed) | unreachable | error (5xx: treated as closed)."""
    host = urlparse(url)
    key = f"{host.scheme}://{host.netloc}"
    with _RLOCK:
        if key in _ROBOTS:
            return _ROBOTS[key]
    status, body = fetch(key + "/robots.txt", 15)
    rp = urllib.robotparser.RobotFileParser()
    if status == 200 and "<html" not in body[:300].lower():
        rp.parse(body.splitlines())
        out = ("ok", rp)
    elif status in (404, 410) or (status == 200):
        out = ("none", None)
    elif status == 0:
        out = ("unreachable", None)
    elif status in (401, 403):
        out = ("blocked", None)  # the site refuses even robots.txt: treat as a no
    else:
        out = ("error", None)
    with _RLOCK:
        _ROBOTS[key] = out
    return out


def may_fetch(url: str) -> tuple[bool, str]:
    """Is our bot allowed to request this exact URL? Unknown means no."""
    state, rp = robots(url)
    if state == "none":
        return True, "no robots.txt (allowed)"
    if state == "ok":
        return (True, "allowed by robots.txt") if rp.can_fetch(UA, url) else (False, "disallowed by robots.txt")
    return False, {"unreachable": "robots.txt unreachable", "blocked": "site refuses robots.txt", "error": "robots.txt server error"}[state]


def crawl_delay(url: str) -> float:
    _, rp = robots(url)
    d = rp.crawl_delay(UA) if rp else None
    return float(d) if d else 0.0


def block_reason(status: int, body: str) -> str:
    low = body[:4000].lower()
    if status in (403, 429, 503) and any(w in low for w in ("cloudflare", "captcha", "just a moment", "access denied", "bot")):
        return "anti-bot wall (Cloudflare/captcha)"
    return {0: "no connection (blocked network or dead domain)", 403: "blocked (403)", 429: "rate limited (429)", 404: "page not found"}.get(status, f"HTTP {status}")


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
    ok, why = may_fetch(url)
    if not ok:
        res["error"] = "skipped: " + why
        return res
    time.sleep(crawl_delay(url))
    status, html = fetch(url)
    res["status"] = status
    if status != 200:
        res["error"] = block_reason(status, html) + (" - fix URL in sources.json" if status == 404 else "")
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
            if not may_fetch(r["url"])[0]:
                continue
            time.sleep(max(1.0, crawl_delay(r["url"])))
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
    """Test all sources. Verdict per site: CRAWLABLE, BLOCKED (robots.txt), BLOCKED (anti-bot), DEAD, NO LISTINGS FOUND, LINK-OUT."""
    out = []
    for s in SOURCES.values():
        row = {"source": s["id"], "name": s["name"], "robots": "", "status": "", "listings": 0, "verdict": ""}
        if s["mode"] != "scrape":
            row.update(verdict="LINK-OUT (never crawled; you open it yourself)")
            out.append(row)
            continue
        p = next(iter(s.get("purposes", {"sale": 1})))
        t = next(iter(s["types"])) if s.get("types") else "apartment"
        url = build_url(s, "gulshan", p, t) or ""
        ok, why = may_fetch(url)
        row["robots"] = why + (f", crawl-delay {crawl_delay(url):g}s" if crawl_delay(url) else "")
        if not ok:
            row["verdict"] = "BLOCKED: " + why
            out.append(row)
            continue
        status, html = fetch(url)
        row["status"] = status
        if status == 200:
            row["listings"] = len(parse.extract(html, url))
            row["verdict"] = "CRAWLABLE" if row["listings"] else "REACHABLE BUT NO LISTINGS RECOGNISED (needs parser/URL fix or JS rendering)"
        else:
            row["verdict"] = "BLOCKED/DEAD: " + block_reason(status, html)
        out.append(row)
        time.sleep(1.5)
    return out
