"""Search-engine results as listings: Facebook groups/Marketplace posts, developer sites and the open web.

Facebook and Google forbid crawling their pages, so this never fetches them. It asks an official search
API (Brave Search or Serper.dev, which returns Google results) and reads the title and snippet the engine
returns. Developer and other pages found this way are then opened only when their robots.txt allows it.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from . import parse, store

CONF = json.loads((Path(__file__).parent / "sources.json").read_text(encoding="utf-8"))
QUERIES: list[dict] = CONF.get("web_queries", [])
AREA_BN = {"gulshan": "গুলশান", "banani": "বনানী", "purbachal": "পূর্বাচল", "uttara": "উত্তরা",
           "dhanmondi": "ধানমন্ডি", "bashundhara": "বসুন্ধরা"}
SALE = re.compile(r"sale|sell|selling|buy|বিক্রি|বিক্রয়|বিক্রয়", re.I)
WANTED = re.compile(r"\bwant(?:ed)?\b|looking for|need (?:a|an)\b|প্রয়োজন|চাই", re.I)  # buyers' posts, not listings
RENT = re.compile(r"\brent\b|to-let|to let|ভাড়া|ভাড়া|sublet|bachelor", re.I)


def provider(con) -> tuple[str, str]:
    """(provider, key) from env first, then the key saved in the dashboard."""
    for name, env in (("serper", "SERPER_API_KEY"), ("brave", "BRAVE_API_KEY")):
        if os.environ.get(env):
            return name, os.environ[env]
    row = con.execute("SELECT value FROM settings WHERE key='websearch'").fetchone()
    if row:
        cfg = json.loads(row[0])
        if cfg.get("key"):
            return cfg.get("provider", "serper"), cfg["key"]
    return "", ""


def save_key(con, prov: str, key: str, budget: int | None = None) -> None:
    cur = json.loads((con.execute("SELECT value FROM settings WHERE key='websearch'").fetchone() or ['{}'])[0])
    cur.update(provider=prov if prov in ("serper", "brave") else "serper")
    if key:
        cur["key"] = key.strip()
    if budget:
        cur["budget"] = int(budget)
    con.execute("INSERT INTO settings(key,value) VALUES('websearch',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (json.dumps(cur),))
    con.commit()


def status(con) -> dict:
    prov, key = provider(con)
    cur = json.loads((con.execute("SELECT value FROM settings WHERE key='websearch'").fetchone() or ['{}'])[0])
    month = time.strftime("%Y-%m")
    used = con.execute("SELECT COUNT(*) FROM web_queries WHERE month=?", (month,)).fetchone()[0]
    return {"provider": prov, "configured": bool(key), "key_hint": ("…" + key[-4:]) if key else "",
            "budget": int(cur.get("budget", 300)), "used_this_month": used}


def _http(url: str, data: bytes | None, headers: dict) -> tuple[int, dict]:
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return e.code, {}
    except Exception:  # noqa: BLE001
        return 0, {}


def run_query(prov: str, key: str, q: str) -> tuple[int, list[dict]]:
    """[{title, url, snippet, date}] from the engine."""
    if prov == "serper":
        st, d = _http("https://google.serper.dev/search", json.dumps({"q": q, "gl": "bd", "num": 20}).encode(),
                      {"X-API-KEY": key, "Content-Type": "application/json"})
        items = d.get("organic", [])
        return st, [{"title": i.get("title", ""), "url": i.get("link", ""), "snippet": i.get("snippet", ""),
                     "date": i.get("date", "")} for i in items]
    st, d = _http("https://api.search.brave.com/res/v1/web/search?" + urllib.parse.urlencode({"q": q, "count": 20, "country": "BD"}),
                  None, {"X-Subscription-Token": key, "Accept": "application/json"})
    items = (d.get("web") or {}).get("results", [])
    return st, [{"title": i.get("title", ""), "url": i.get("url", ""), "snippet": re.sub(r"<[^>]+>", "", i.get("description", "")),
                 "date": i.get("age", "")} for i in items]


def expand(areas: list[str]) -> list[tuple[dict, str, str]]:
    """(query spec, area, query text) for every template x area."""
    out = []
    for spec in QUERIES:
        for a in areas:
            out.append((spec, a, spec["q"].format(area=a.capitalize(), area_bn=AREA_BN.get(a, a))))
    return out


def to_listing(hit: dict, spec: dict, query: str, area_hint: str) -> dict | None:
    from .scrape import _area_in  # same area rule as every other source
    host = urllib.parse.urlparse(hit["url"]).netloc.lower()
    if spec.get("host") and not re.search(spec["host"], host):  # free Serper tier rejects site:, so filter here
        return None
    if spec.get("exclude") and re.search(spec["exclude"], host):
        return None
    text = f"{hit['title']} {hit['snippet']}"
    path = urllib.parse.urlparse(hit["url"]).path.lower()
    if spec["id"].startswith("dev_") and (path in ("", "/") or re.search(r"/(about|blog|news|career|contact|csr|gallery)", path)
                or re.search(r"^(projects?|residential|commercial)\b.*\b(projects?|masterpieces)\b|full of quality", hit["title"], re.I)):
        return None  # a company page, not a project
    dev = spec["id"].startswith("dev_")  # developers sell by definition; their pages seldom say "for sale"
    if (not dev and not SALE.search(text)) or WANTED.search(text):
        return None
    area = _area_in(text, None)
    if not area:
        return None
    if re.search(r"iqbal|karachi|uttar badda|north badda", text, re.I):  # name clashes with other places
        return None
    f = parse.facts(text)
    katha = re.search(r"(\d+(?:\.\d+)?)\s*(?:katha|kata|kotha|কাঠা)", text, re.I)
    ptype = parse._ptype(text) or "apartment"
    if dev and not re.search(r"plot|land|katha|কাঠা", hit["title"] + hit["url"], re.I):
        ptype = "commercial" if re.search(r"commercial|office", hit["title"] + hit["url"], re.I) else "apartment"
    size = f["size_sqft"] or (float(katha.group(1)) * 720 if katha else None)
    # No value is dropped for looking odd: sellers hide details on purpose. store.data_flags marks them to clear.
    return {**f, "title": re.sub(r"\s*[|\-–]\s*Facebook\s*$", "", hit["title"])[:200], "url": hit["url"],
            "source": spec["id"], "area": area, "purpose": "rent" if RENT.search(hit["title"]) else "sale",
            "ptype": ptype, "image": "", "size_sqft": size,
            "snippet": hit["snippet"][:600], "found_via": f"{spec['engine_label']}: {query}", "evidence": "search result"}


def search_web(areas: list[str], max_queries: int | None = None, enrich: int = 10) -> list[dict]:
    """Run the query library within this month's budget. Returns one result row per channel."""
    from .scrape import may_fetch, fetch, crawl_delay
    con = store.connect()
    prov, key = provider(con)
    if not key:
        con.close()
        return [{"source": s["id"], "status": 0, "found": 0, "new": 0,
                 "error": "add a Serper.dev or Brave Search API key under Web search"} for s in QUERIES]
    st_ = status(con)
    left = max(0, st_["budget"] - st_["used_this_month"])
    if max_queries is not None:
        left = min(left, max_queries)
    recent = {q for (q,) in con.execute("SELECT q FROM web_queries WHERE ts > ?", (time.time() - 20 * 3600,))}
    res: dict[str, dict] = {s["id"]: {"source": s["id"], "status": 200, "found": 0, "new": 0, "error": ""} for s in QUERIES}
    for spec, area, q in expand(areas):
        if q in recent:
            continue
        if left <= 0:
            res[spec["id"]]["error"] = res[spec["id"]]["error"] or "monthly search budget used up"
            continue
        left -= 1
        code, hits = run_query(prov, key, q)
        con.execute("INSERT INTO web_queries(q, ts, month, results) VALUES(?,?,?,?)", (q, time.time(), time.strftime("%Y-%m"), len(hits)))
        if code != 200:
            res[spec["id"]].update(status=code, error={400: "query rejected by the search plan (site:/-site: need a paid Serper plan)", 401: "API key rejected", 403: "API key rejected", 429: "search API rate limit"}.get(code, f"search API error {code}"))
            continue
        for h in hits:
            r = to_listing(h, {**spec, "engine_label": "Google (Serper)" if prov == "serper" else "Brave Search"}, q, area)
            if not r:
                continue
            host = urllib.parse.urlparse(r["url"]).netloc.lower()
            # Open the page itself only when it is not Facebook/Google and robots.txt allows it.
            if enrich > 0 and not re.search(r"facebook\.com|fb\.com|google\.", host) and may_fetch(r["url"])[0]:
                enrich -= 1
                time.sleep(max(1.5, crawl_delay(r["url"])))
                st, page = fetch(r["url"])
                d = parse.detail_record(page, r["url"]) if st == 200 else None
                if d and d.get("price"):
                    r.update({k: d[k] for k in ("price", "size_sqft", "beds", "baths") if d.get(k)})
                    r["phone"] = r.get("phone") or d.get("phone", "")
                    r["evidence"] = "search result + listing page"
            res[spec["id"]]["found"] += 1
            if r["purpose"] == "rent":
                store.add_rent(con, r)
            else:
                res[spec["id"]]["new"] += store.upsert(con, r)
        con.commit()
        time.sleep(0.5)
    con.commit()
    con.close()
    return list(res.values())
