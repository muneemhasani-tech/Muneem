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
           "dhanmondi": "ধানমন্ডি", "bashundhara": "বসুন্ধরা", "baridhara": "বারিধারা ডিপ্লোমেটিক"}
SALE = re.compile(r"sale|sell|selling|বিক্রি|বিক্রয়|বিক্রয়", re.I)  # not "buy": that is a buyer's post
WANTED = re.compile(r"\bwant(?:ed)?\b|looking (?:for|to buy|to purchase)|need (?:a|an)\b|need (?:flat|plot|land|apartment|house)|"
                    r"\b(?:want|wish|planning) to (?:buy|purchase)|\bbuyer (?:needed|wanted)|\brequire(?:d|ment)?\b|"
                    r"কিনতে চাই|কিনতে আগ্রহী|কিনবো|কিনব\b|কিনতে|খুঁজছি|খুজছি|লাগবে|প্রয়োজন|প্রয়োজন|চাই|"
                    r"(?:মিডিয়া|এজেন্ট|লোক) দরকার|কারণ কী|কারন কী|করতে চান\s*\?", re.I)  # buyers' and other non-listing posts; "টাকার দরকার" stays
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


def provider_from_env() -> tuple[str, str]:
    for name, env in (("serper", "SERPER_API_KEY"), ("brave", "BRAVE_API_KEY")):
        if os.environ.get(env):
            return name, os.environ[env]
    return "", ""


def run_query(prov: str, key: str, q: str, tbs: str = "") -> tuple[int, list[dict]]:
    """[{title, url, snippet, date}] from the engine. tbs: Google time filter (qdr:d, qdr:w, qdr:m)."""
    if prov == "serper":
        body = {"q": q, "gl": "bd", "num": 10}
        if tbs:
            body["tbs"] = tbs
        st, d = _http("https://google.serper.dev/search", json.dumps(body).encode(),  # free accounts allow 10 per query
                      {"X-API-KEY": key, "Content-Type": "application/json"})
        items = d.get("organic", [])
        return st, [{"title": i.get("title", ""), "url": i.get("link", ""), "snippet": i.get("snippet", ""),
                     "date": i.get("date", "")} for i in items]
    st, d = _http("https://api.search.brave.com/res/v1/web/search?" + urllib.parse.urlencode({"q": q, "count": 20, "country": "BD"}),
                  None, {"X-Subscription-Token": key, "Accept": "application/json"})
    items = (d.get("web") or {}).get("results", [])  # Brave has no exact equivalent of tbs; it is ignored
    return st, [{"title": i.get("title", ""), "url": i.get("url", ""), "snippet": re.sub(r"<[^>]+>", "", i.get("description", "")),
                 "date": i.get("age", "")} for i in items]


def expand(areas: list[str]) -> list[tuple[dict, str, str]]:
    """(query spec, area, query text) for every template x area."""
    out = []
    for spec in QUERIES:
        for a in areas:
            out.append((spec, a, spec["q"].format(area=a.capitalize(), area_bn=AREA_BN.get(a, a))))
    return out


CRAWLED = re.compile(r"(?:^|\.)(bproperty\.com|bdhousing\.com|aabason\.com|homefairbd\.com|propertyfinderbd\.com|concordcps\.com)$")
NOT_A_LISTING = re.compile(
    r"youtube\.com|youtu\.be|wikipedia\.org|/(?:areas?|locations?|service-area|types?|phases?|category|categories|"
    r"pages|tags?|blog|news|search)(?:/|$)|bikroy\.com/(?:bn|en)/(?!ad/)[^/]+/[^/]*for-(?:sale|rent)|[?&]q=", re.I)


FOREIGN = re.compile(r"karachi|lahore|islamabad|pakistan|kolkata|calcutta|india\b|₹|\brs\.?\s?\d|gulshan[\s-]*e[\s-]*(?:iqbal|maymar)|maymar|rajarhat|new town,? kol|\d?\s?bhk\b|\bgaz\b|\bandal\b|kanker|\bmumbai\b|\bdelhi\b|\bkarachi\b", re.I)
PROPERTY_WORD = re.compile(r"flat|apartment|plot|land|katha|kata\b|sq\.? ?ft|sqft|\bsft\b|duplex|house|building|penthouse|ফ্ল্যাট|প্লট|জমি|কাঠা|বাড়ি|ভবন|বিক্রি|বিক্রয়", re.I)
FOREIGN_HOSTS = re.compile(r"\.pk$|\.in$|(?:^|\.)(?:zameen\.com|magicbricks\.com|99acres\.com|housing\.com|nobroker\.in|graana\.com|olx\.com\.pk)$")
GENERIC_SLUG = re.compile(r"^(?:(?:property|properties|for|sale|flats?|apartments?|dhaka|bangladesh|buy|residential|commercial|ready|all|in)[-_]?)+$", re.I)
CATEGORY_TITLE = re.compile(r"^\s*\d+\+|^\s*(?:flats|apartments|properties|plots|houses|lands)\b|price list|দাম ২০", re.I)


# Bikroy's category and filter pages ("4 Bedrooms Flat for sale in basundhara - Dhaka", "Property in Gulshan for rent & sale")
PORTAL_CATEGORY = re.compile(r"^\s*(?:\d+\+?\s+|\d+\s+bedrooms?\s+)?(?:furnished\s+)?(?:houses\s*&\s*apartments|flats?|apartments?|land\s*&\s*plots|"
                             r"commercial\s+land|plots?|property|properties)\s+for\s+(?:sale|rent)\s+in\s+[\w ]+(?:\s*-\s*dhaka)?\s*(?:\.{3}|…)?\s*$"
                             r"|for\s+rent\s*&\s*sale", re.I)


def is_listing(url: str, title: str = "", dev: bool = False, portals_ok: bool = False) -> bool:
    """One property in Bangladesh: not a category page, an area guide, a whole group or a foreign site."""
    u = urllib.parse.urlparse(url)
    host, path = u.netloc.lower().removeprefix("www."), u.path.rstrip("/")
    if (CRAWLED.search(host) and not portals_ok) or FOREIGN_HOSTS.search(host) or NOT_A_LISTING.search(url) or CATEGORY_TITLE.search(title):
        return False
    if host == "google.com" and path == "/goto":  # Google wraps some portal ads (Bikroy) in its own redirect link
        return portals_ok and not PORTAL_CATEGORY.search(title)
    if "facebook.com" in host:  # a post, a permalink or a Marketplace item; never a bare group or page
        return bool(re.search(r"/posts/|/permalink/|/marketplace/item/|story_fbid|/photos?/", url))
    if "bikroy.com" in host:  # Google indexes ads as /<area>/<category>/<ad-slug>; shorter paths are category pages
        segs = [x for x in path.split("/") if x]
        return "/ad/" in path or (len(segs) >= 3 and len(segs[-1]) >= 20 and segs[-1] not in ("furnished",))
    last = path.rsplit("/", 1)[-1]
    if GENERIC_SLUG.match(last):
        return False
    if dev:  # developer project pages often have short names (/projects/Diorama)
        return bool(last)
    return len(last) >= 12 or bool(re.search(r"\d", last))  # a real listing has a long or numbered slug


def same_post(title: str, snippet: str, strict: bool = True) -> bool:
    """True only when the preview text is clearly about the post named in the title. Google often splices a neighbouring
    post into a Facebook preview, and its phone, price and size then belong to someone else.
    Different post if: sizes or prices disagree, three or more phone numbers, or different block letters.
    Same post (strict, for Google redirect links): the preview repeats most of the title's first words, or states the same size."""
    t, sn = parse.facts(title), parse.facts(snippet)
    tn, snl = parse.norm(title).lower(), parse.norm(snippet).lower()
    if t["size_sqft"] and sn["size_sqft"] and abs(t["size_sqft"] - sn["size_sqft"]) > 0.1 * t["size_sqft"]:
        return False
    tp = parse.parse_price(parse.norm(title))
    if tp and sn["price"] and abs(tp - sn["price"]) > 0.1 * tp:
        return False
    if len({re.sub(r"\D", "", m.group(1))[-10:] for m in parse.PHONE.finditer(parse.norm(snippet))}) > 2:
        return False
    blk = lambda x: set(re.findall(r"\bblock[\s:#-]*([a-p])\b|\b([a-p])[\s-]*block\b", x))
    tb, sb = {a or b for a, b in blk(tn)}, {a or b for a, b in blk(snl)}
    if tb and sb and not tb & sb:
        return False
    if not strict:
        return True  # a direct post link: its preview comes from that post, so no contradiction is enough
    words = re.findall(r"[a-z0-9ঀ-৿]{2,}", tn)[:4]
    if len(words) >= 3 and sum(w in snl for w in words) >= 3:
        return True
    return bool(t["size_sqft"] and sn["size_sqft"])  # same size stated (a different one returned False above)


def price_of(title: str, snippet: str, facts_price: float | None = None) -> float | None:
    """Total asking price: the title's price first (a snippet can quote a neighbouring ad), a bare 7-10 digit title number,
    then the snippet; a per-katha price is multiplied by the katha count."""
    text = f"{title} {snippet}"
    price = facts_price if facts_price is not None else parse.facts(text)["price"]
    tp = parse.parse_price(title)
    if not tp:
        bare = re.search(r"(?<![\d+])([1-9]\d{6,9})(?!\d)", title)  # "3 Katha Plot Sale Purbachal | 26000000"
        tp = float(bare.group(1)) if bare and 5e5 <= float(bare.group(1)) <= 5e9 else None
    if tp:
        price = tp
    katha = re.search(r"(\d+(?:\.\d+)?)\s*(?:katha|kata|kotha|কাঠা)", text, re.I)
    if price and katha and re.search(r"(?:per|/)\s*(?:katha|kata|kotha|কাঠা)|প্রতি কাঠা", text, re.I) and price < 5e7:
        price *= float(katha.group(1))  # "BDT 90,00,000 per katha" for a 10 katha plot
    return price


def to_listing(hit: dict, spec: dict, query: str, area_hint: str) -> dict | None:
    from .scrape import area_of  # same area rule as every other source
    hit = {**hit, "title": parse.norm(hit["title"]), "snippet": parse.norm(hit["snippet"])}
    host = urllib.parse.urlparse(hit["url"]).netloc.lower()
    if spec.get("host") and not re.search(spec["host"], host):  # results are filtered by site here, not with site:
        return None
    if spec.get("exclude") and re.search(spec["exclude"], host):
        return None
    from .scrape import GROUP_NAME
    text = f"{hit['title']} {GROUP_NAME.sub(' ', hit['snippet'])}"  # a group's name ("Flat Buy & Sale") says nothing about the post
    if not is_listing(hit["url"], hit["title"], spec["id"].startswith("dev_"), spec.get("portals_ok", False)) or FOREIGN.search(text) or (not PROPERTY_WORD.search(text) and not spec["id"].startswith("dev_")):
        return None
    path = urllib.parse.urlparse(hit["url"]).path.lower()
    if spec["id"].startswith("dev_") and (path in ("", "/") or re.search(r"/(about|blog|news|career|contact|csr|gallery)", path)
                or re.search(r"^(projects?|residential|commercial)\b.*\b(projects?|masterpieces)\b|full of quality", hit["title"], re.I)):
        return None  # a company page, not a project
    dev = spec["id"].startswith("dev_")  # developers sell by definition; their pages seldom say "for sale"
    if (not dev and not SALE.search(text)) or WANTED.search(text):
        return None
    area = area_of(hit["title"], hit["snippet"])  # the title names the property; snippets often mention nearby areas
    if not area:
        return None
    if re.search(r"iqbal|karachi|uttar badda|north badda", text, re.I):  # name clashes with other places
        return None
    if not re.search(r"facebook|google\.com/goto", hit["url"] + spec["id"], re.I) or same_post(
            hit["title"], hit["snippet"], strict="google.com/goto" in hit["url"]):
        f = parse.facts(text)
        f["price"] = price_of(hit["title"], hit["snippet"], f["price"])
    else:  # Google mixed another post into this Facebook preview: its phone, price and size belong to someone else
        f = parse.facts(hit["title"])
        f["price"] = price_of(hit["title"], "", f["price"])
        text = hit["title"]
    katha = re.search(r"(\d+(?:\.\d+)?)\s*(?:katha|kata|kotha|কাঠা)", text, re.I)
    ptype = parse.ptype_of(hit["title"], hit["snippet"]) or "apartment"
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
        con.execute("INSERT INTO web_queries(q, ts, month, results, hits) VALUES(?,?,?,?,?)",
                    (q, time.time(), time.strftime("%Y-%m"), len(hits), json.dumps(hits, ensure_ascii=False)))
        if code != 200:
            res[spec["id"]].update(status=code, error={400: "query rejected by the search plan (free Serper allows 10 results per search)", 401: "API key rejected", 403: "API key rejected", 429: "search API rate limit"}.get(code, f"search API error {code}"))
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
            if con.execute("SELECT 1 FROM listings WHERE url=?", (r["url"],)).fetchone():
                continue  # the same post found by another query
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


def reprocess() -> int:
    """Re-read every cached search result with the current rules. Costs no searches."""
    con = store.connect()
    con.execute("DELETE FROM listings WHERE evidence LIKE 'search%'")
    specs = {}
    for spec, area, q in expand(list(AREA_BN)):
        specs[q] = (spec, area)
    n = 0
    for q, hits in con.execute("SELECT q, hits FROM web_queries WHERE hits IS NOT NULL ORDER BY ts").fetchall():
        if q not in specs:
            continue
        spec, area = specs[q]
        for h in json.loads(hits):
            r = to_listing(h, {**spec, "engine_label": "Google (Serper)"}, q, area)
            if r and not con.execute("SELECT 1 FROM listings WHERE url=?", (r["url"],)).fetchone():
                n += store.upsert(con, r) if r["purpose"] == "sale" else 0
    con.commit()
    con.close()
    return n
