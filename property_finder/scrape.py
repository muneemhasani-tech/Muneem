"""Runs searches across sources politely (thread pool, per-source delay) and reports per-source health."""
from __future__ import annotations

import json
import os
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


AI_AGENTS = ("ClaudeBot", "Claude-User", "anthropic-ai")  # honoured too whenever an AI agent is driving the tool
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
        if not rp.can_fetch(UA, url):
            return False, "disallowed by robots.txt"
        if os.environ.get("CLAUDECODE") and not all(rp.can_fetch(a, url) for a in AI_AGENTS):
            return False, "robots.txt bans AI crawlers (run it on your own computer)"
        return True, "allowed by robots.txt"
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


def link_outs(areas: list[str], purpose: str, ptype: str, q: str = "") -> list[dict]:  # sale searches only
    """Search links for sites we can't or shouldn't scrape (Facebook, Google, developer sites)."""
    out = []
    for s in SOURCES.values():
        if s["mode"] == "link":
            for a in areas or ["dhaka"]:
                out.append({"source": s["id"], "name": s["name"], "kind": s["kind"], "area": a,
                            "url": build_url(s, q or a, purpose, ptype)})
    return out


AREA_RX = {"gulshan": r"gulshan|গুলশান", "banani": r"banani|বনানী", "purbachal": r"purbachal|পূর্বাচল",
           "uttara": r"uttara|uttra|uttora|উত্তরা", "dhanmondi": r"dhanmondi|dhanmandi|ধানমন্ডি|ধানমণ্ডি",
           "bashundhara": r"bashundhara|basundhara|bosundhora|বসুন্ধরা"}


def _area_in(text: str, fallback: str | None) -> str | None:
    """The area a listing is in, read from the listing itself. Falls back only when the URL already proved it."""
    low = (text or "").lower()
    for slug, rx in AREA_RX.items():
        if re.search(rx, low):
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
        r.update(source=src["id"], purpose=purpose, ptype=ptype, area=_area_in(r["title"] + " " + r.get("text", ""), None))
        if not r["area"]:
            continue  # outside MRA's six areas
        if purpose == "rent":  # benchmark only: feeds the ROI projection, never shown
            store.add_rent(con, r)
            res["new"] += 1
            continue
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


_SITEMAPS: dict[str, tuple[float, list[tuple[str, str]]]] = {}


def sitemap_urls(src: dict) -> tuple[list[tuple[str, str]], str]:
    """(url, lastmod) pairs from the site's own sitemap (cached 1 hour), following sitemap indexes one level."""
    sm = src["sitemap"]
    hit = _SITEMAPS.get(sm)
    if hit and time.time() - hit[0] < 3600:
        return hit[1], ""
    ok, why = may_fetch(sm)
    if not ok:
        return [], "skipped: " + why
    status, xml = fetch(sm, 60)
    if status != 200:
        return [], "sitemap: " + block_reason(status, xml)
    locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>(?:\s*<lastmod>\s*([^<\s]*))?", xml)
    if "<sitemapindex" in xml[:500]:
        sub = []
        for u, _ in locs[:20]:
            if may_fetch(u)[0]:
                st, x = fetch(u, 60)
                sub += re.findall(r"<loc>\s*([^<\s]+)\s*</loc>(?:\s*<lastmod>\s*([^<\s]*))?", x) if st == 200 else []
                time.sleep(1.5)
        locs = sub
    locs = [(u, m) for u, m in locs if src.get("match", "") in u]
    _SITEMAPS[sm] = (time.time(), locs)
    return locs, ""


def search_sitemap(src: dict, area: str, details: int) -> dict:
    """Fetch the newest not-yet-seen listing pages for one area. Sale goes to listings, rent only to the ROI benchmark."""
    res = {"source": src["id"], "url": src["sitemap"], "status": 200, "found": 0, "new": 0, "error": ""}
    locs, err = sitemap_urls(src)
    if err:
        res.update(error=err, status=0)
        return res
    con = store.connect()
    seen = {u: m for u, m in con.execute("SELECT url, lastmod FROM crawled")}
    fresh = sorted((x for x in locs if area in x[0].lower() and seen.get(x[0]) != x[1]), key=lambda x: x[1], reverse=True)
    rentish = re.compile(r"rent|sublet|to-let|tolet|room|hostel|mess")
    sale = [x for x in fresh if not rentish.search(x[0].rsplit("/", 1)[-1])]
    rent = [x for x in fresh if re.search(r"(flat|apartment|bed)", x[0]) and re.search(r"rent", x[0])
            and not re.search(r"office|shop|sublet|room|commercial|space", x[0])]
    todo = sale[: int(src.get("per_run", 40))] + rent[: int(src.get("rent_per_run", 8))]
    for url, lastmod in todo:
        if not may_fetch(url)[0]:
            continue
        time.sleep(max(1.5, crawl_delay(url)))
        st, page = fetch(url)
        con.execute("INSERT OR REPLACE INTO crawled(url,lastmod,seen) VALUES(?,?,?)", (url, lastmod, time.time()))
        r = parse.detail_record(page, url) if st == 200 else None
        if not r or not r["purpose"]:
            continue
        res["found"] += 1
        r.update(source=src["id"], area=_area_in(r.pop("tags") + " " + url, area))
        if r["purpose"] == "rent":
            store.add_rent(con, r)
        else:
            res["new"] += store.upsert(con, r)
        con.commit()
    con.commit()
    con.close()
    if not todo:
        res["error"] = "" if locs else "sitemap has no listing pages"
    return res


RENT_WORDS = re.compile(r"\b(?:for rent|to-let|to let|rent)\b|sublet|bachelor", re.I)


def search_list(src: dict, details: int) -> dict:
    """Walk a site's own listing pages (newest first), keep only cards in MRA's areas."""
    res = {"source": src["id"], "url": src["list"][0], "status": 200, "found": 0, "new": 0, "error": ""}
    con = store.connect()
    for tmpl in src["list"]:
        purpose_hint = "rent" if "/rent" in tmpl.lower() else "sale"
        prev: set[str] = set()
        for page in range(1, int(src.get("max_pages", 5)) + 1):
            url = tmpl.format(page=page)
            ok, why = may_fetch(url)
            if not ok:
                res["error"] = "skipped: " + why
                break
            time.sleep(max(1.5, crawl_delay(url)))
            st, html = fetch(url)
            if st != 200:
                res.update(status=st, error=block_reason(st, html))
                break
            cards = parse.extract_cards(html, url, src["detail"]) if src.get("detail") else parse.extract(html, url)
            urls = {c["url"] for c in cards}
            if not urls or urls <= prev:
                break  # ran out of pages
            prev = urls
            for c in cards:
                text = c["title"] + " " + c.get("text", "")
                area = _area_in(text, None)
                if not area:
                    continue
                purpose = "rent" if RENT_WORDS.search(c["title"]) else purpose_hint
                c.update(source=src["id"], area=area, purpose=purpose, ptype=parse._ptype(c["title"]) or "apartment")
                res["found"] += 1
                if details and purpose == "sale" and not c.get("phone") and may_fetch(c["url"])[0]:
                    details -= 1
                    time.sleep(max(1.5, crawl_delay(c["url"])))
                    st2, page = fetch(c["url"])
                    if st2 == 200:
                        c.update({k: v for k, v in parse.detail_contact(page).items() if v})
                if purpose == "rent":
                    store.add_rent(con, c)
                else:
                    res["new"] += store.upsert(con, c)
            con.commit()
    con.close()
    if not res["found"] and not res["error"]:
        res["error"] = "no listings in MRA's areas on the pages checked"
    return res


class Job:
    def __init__(self):
        self.lock, self.state = threading.Lock(), {"running": False, "done": 0, "total": 0, "results": [], "links": []}

    def start(self, areas, ptypes, sources, q="", details=0, benchmark=True) -> bool:
        """Sale searches for the chosen types, plus (optionally) apartment rent pages used only to measure rent per sqft."""
        with self.lock:
            if self.state["running"]:
                return False
            live = [SOURCES[s] for s in sources if s in SOURCES and SOURCES[s]["mode"] == "scrape"]
            maps = [SOURCES[s] for s in sources if s in SOURCES and SOURCES[s]["mode"] == "sitemap"]
            lists = [SOURCES[s] for s in sources if s in SOURCES and SOURCES[s]["mode"] == "list"]
            tasks = [(s, a, "sale", t) for s in live for a in areas for t in ptypes if "sale" in s.get("purposes", {"sale": 1})]
            if benchmark and not q:
                tasks += [(s, a, "rent", "apartment") for s in live for a in areas if "rent" in s.get("purposes", {})]
            tasks += [(s, a, "sitemap", "") for s in maps for a in areas]
            tasks += [(s, "", "list", "") for s in lists]
            self.state = {"running": True, "done": 0, "total": len(tasks), "results": [],
                          "links": link_outs(areas, "sale", ptypes[0] if ptypes else "apartment", q)}
        threading.Thread(target=self._run, args=(tasks, q, details), daemon=True).start()
        return True

    def _run(self, tasks, q, details):
        by_src: dict[str, threading.Lock] = {}
        for t in tasks:
            by_src.setdefault(t[0]["id"], threading.Lock())

        def one(t):
            src, a, p, ty = t
            with by_src[src["id"]]:  # one request at a time per site, with a pause
                r = (search_sitemap(src, a, details) if p == "sitemap" else search_list(src, details) if p == "list"
                     else search_source(src, a, p, ty, q, details))
                time.sleep(1.5)
            with self.lock:
                self.state["results"].append({**r, "area": a, "purpose": p, "ptype": ty, "benchmark": p == "rent"})
                self.state["done"] += 1

        with ThreadPoolExecutor(max_workers=8) as ex:
            list(ex.map(one, tasks))
        with self.lock:
            self.state["running"] = False

    def snapshot(self) -> dict:
        with self.lock:
            return json.loads(json.dumps(self.state))


class _null_store:
    """Probe runs must not write test results into the real lead database."""
    def __enter__(self):
        import tempfile
        self._old = store.connect.__defaults__
        store.connect.__defaults__ = (Path(tempfile.mkdtemp()) / "probe.db",)

    def __exit__(self, *a):
        store.connect.__defaults__ = self._old


def probe() -> list[dict]:
    """Test all sources. Verdict per site: CRAWLABLE, BLOCKED (robots.txt), BLOCKED (anti-bot), DEAD, NO LISTINGS FOUND, LINK-OUT."""
    out = []
    for s in SOURCES.values():
        row = {"source": s["id"], "name": s["name"], "robots": "", "status": "", "listings": 0, "verdict": ""}
        if s["mode"] == "link":
            row.update(verdict="LINK-OUT (never crawled; you open it yourself)")
            out.append(row)
            continue
        if s["mode"] == "list":
            one = dict(s, max_pages=1)
            with _null_store():
                r = search_list(one, 0)
            row.update(robots="checked per page", status=r["status"], listings=r["found"],
                       verdict=f"CRAWLABLE via listing pages ({r['found']} in our areas on page 1)" if r["found"] else "BLOCKED/DEAD: " + r["error"])
            out.append(row)
            continue
        if s["mode"] == "sitemap":
            ok, why = may_fetch(s["sitemap"])
            row["robots"] = why
            s = dict(s)
            locs, err = sitemap_urls(s) if ok else ([], why)
            hits = [u for u, _ in locs if any(a in u.lower() for a in AREAS)]
            row["status"] = 200 if locs else 0
            if not hits:
                row["verdict"] = "BLOCKED/DEAD: " + (err or "no listing pages for our areas in sitemap")
            else:
                st, page = fetch(hits[0]) if may_fetch(hits[0])[0] else (0, "")
                rec = parse.detail_record(page, hits[0]) if st == 200 else None
                row["listings"] = len(hits)
                row["verdict"] = f"CRAWLABLE via sitemap ({len(hits)} listing pages in our areas)" if rec else "SITEMAP OK BUT LISTING PAGE NOT PARSED"
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
