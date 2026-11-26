"""The lean daily process: targeted Google searches only, new listings only.

    python -m property_finder scout --seen seen.tsv --out out

One run = about 20 searches (2 per area every day for Facebook groups, plus a rotating slice of
site:bproperty.com / site:bikroy.com / bdHousing / Bdstall / plot / Marketplace searches). Results are
read from Google's title and snippet, so no site is crawled. A listing is new only if neither its URL
nor its fingerprint (phone, size + price, or the post's text) is in the master list; reposts of the same
ad in other Facebook groups count as duplicates. Writes leads-DATE.csv (today's new only), a short digest
with today's 3 calls and ready WhatsApp drafts, and seen.tsv: the only memory a cloud run needs, small enough
to carry between days (hashes of the last 14 days). `--master master.csv` still works for a full history.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import json
import random
import re
from pathlib import Path

from . import parse, roi, scrape, store, websearch
from .scrape import AREAS

CONF = json.loads((Path(__file__).parent / "scout.json").read_text(encoding="utf-8"))
COLS = ["date", "area", "type", "title", "price_bdt", "size_sqft", "price_per_sqft", "gross_yield_pct", "phone",
        "site", "url", "snippet", "query", "fingerprints", "known_seller", "via", "contact_name", "contact_how"]


SITE_SLOTS = 2  # rotating searches handed to proven directory sites (the daily total stays the same)


def is_facebook(r: dict) -> bool:
    """Facebook, or a Google redirect whose real site is hidden (a social post shown as "7 likes"): it must not count as a non-Facebook lead."""
    via = r.get("via", "")
    return (r["site"].startswith("Facebook") or "facebook.com" in r["url"] + via
            or ("google.com/goto" in r["url"] and not via))


def balance_plan(day: dt.date, sites: list[str] | None = None):
    """Non-Facebook searches, deepest pages last: (spec, page). Used after the daily plan until the portals and the open web
    have found as many new listings as Facebook did. Each round gives every template one area; pages 1..max_page are
    read across all templates before the next round moves every template to the next area."""
    conf = CONF["balance"]
    name = {"baridhara": "Baridhara Diplomatic"}
    from .sites import clean
    temps = list(conf["queries"]) + [{"label": f"Directory: {d}", "q": f'site:{d} "{{area}}" {{variant}}', "tbs": ""}
                                     for d in (sites or []) if clean(d) == d]
    areas, o = list(AREAS), day.toordinal()
    for rnd in range(len(areas)):
        picked = []
        for i, t in enumerate(temps):
            a = areas[(o + i + rnd) % len(areas)]
            v = CONF["variants"][(o + 2 * i + rnd) % len(CONF["variants"])]
            q = t["q"].format(area=name.get(a, a.capitalize()), area_bn=websearch.AREA_BN[a], variant=v)
            picked.append({"label": t["label"], "area": a, "q": q, "tbs": t.get("tbs", "")})
        for page in range(1, conf["max_page"] + 1):
            for spec in picked:
                yield spec, page


def plan(day: dt.date, extra: int | None = None, sites: list[str] | None = None) -> list[dict]:
    """Today's searches: the daily ones for every area, then a fresh slice of the rotating pool."""
    extra = CONF["extra_per_day"] if extra is None else extra
    name = {"baridhara": "Baridhara Diplomatic"}  # never Baridhara DOHS
    fill = lambda t, a, v="", k="": t.format(area=name.get(a, a.capitalize()), area_bn=websearch.AREA_BN[a], variant=v, katha=k)
    out = [{**d, "area": a, "q": fill(d["q"], a)} for d in CONF["daily"] for a in AREAS]
    pool = []
    for p in CONF["pool"]:
        for a in AREAS:
            if "{katha}" in p["q"]:
                pool += [{**p, "area": a, "q": fill(p["q"], a, k=k)} for k in CONF["katha"]]
            elif "{variant}" in p["q"]:
                pool += [{**p, "area": a, "q": fill(p["q"], a, v=v)} for v in CONF["variants"]]
            else:
                pool.append({**p, "area": a, "q": fill(p["q"], a)})
    random.Random(7).shuffle(pool)  # fixed order, so consecutive days take consecutive, different slices
    start = (day.toordinal() * extra) % len(pool)
    areas = list(AREAS)
    ordinal = day.toordinal()
    for i, p in enumerate(CONF.get("portal_daily", [])):  # every portal, every day; area and keyword move with the date
        a = areas[(ordinal + i) % len(areas)]
        v = CONF["variants"][(ordinal * 3 + i) % len(CONF["variants"])]
        out.append({**p, "area": a, "q": fill(p["q"], a, v=v)})
    from .sites import clean
    sites = [d for d in (sites or []) if clean(d) == d]  # validated domains only; the query is built here, never read from the registry
    slots = min(SITE_SLOTS, len(sites), extra)
    extras = [pool[(start + i) % len(pool)] for i in range(min(extra, len(pool)) - slots)]
    for i in range(slots):
        d = sites[(ordinal * SITE_SLOTS + i) % len(sites)]
        a = areas[(ordinal + i + 2) % len(areas)]
        v = CONF["variants"][(ordinal + i) % len(CONF["variants"])]
        extras.append({"label": f"Directory: {d}", "area": a, "tbs": "", "q": f'site:{d} "{a.capitalize()}" {v}'})
    return out + extras


def fingerprints(r: dict) -> list[str]:
    """Ways the same property shows up again under another URL."""
    fps = []
    if r.get("phone"):
        fps.append(f"p:{r['phone']}:{r['area']}:{int(r.get('size_sqft') or 0)}")
    if r.get("size_sqft") and r.get("price"):
        fps.append(f"s:{r['area']}:{round(r['size_sqft'] / 10)}:{round(r['price'] / 1e5)}")
    words = re.sub(r"[^a-z0-9ঀ-৿]+", "", (r.get("snippet") or "").lower())[:120]
    if len(words) > 60:
        fps.append("t:" + hashlib.sha1(words.encode()).hexdigest()[:16])
    return fps


SEEN_DAYS = 14


def _h(x: str) -> str:
    return hashlib.sha1(x.encode()).hexdigest()[:8]


def read_seen(path: str | None, day: dt.date) -> tuple[set[str], dict[str, str]]:
    """Hashes of listings found in the last SEEN_DAYS days: {hash} and {hash: date} to write back."""
    keep = {}
    if path and Path(path).exists():
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            k, _, d = line.partition("\t")
            if k and d and (day - dt.date.fromisoformat(d)).days <= SEEN_DAYS:
                keep[k] = d
    return set(keep), keep


def write_seen(path: Path, keep: dict[str, str]) -> None:
    path.write_text("".join(f"{k}\t{d}\n" for k, d in sorted(keep.items())), encoding="utf-8")


def read_master(path: str | None) -> tuple[list[dict], set[str], set[str]]:
    if not path or not Path(path).exists():
        return [], set(), set()
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    return rows, {r["url"] for r in rows}, {fp for r in rows for fp in (r.get("fingerprints") or "").split("|") if fp}


def run(master: str | None, out: str = "out", extra: int | None = None, day: dt.date | None = None, seen: str | None = None,
        enrich_top: int = 3, fresh: bool = False, sites: str | None = None, balance: int | None = None) -> dict:
    """fresh=True: no memory needed. Facebook searches ask Google for the last 24 hours only (that filter works there; portals are rarely indexed that fast, so they keep their own rotating keywords and pages)."""
    day = day or dt.date.today()
    old, seen_urls, seen_fps = read_master(master)
    seen_h, seen_keep = read_seen(seen, day)
    prov, key = websearch.provider_from_env()
    if not key:
        raise SystemExit("Set SERPER_API_KEY (or BRAVE_API_KEY) first.")
    new, dups, log = [], 0, []
    from . import sites as site_dir
    active = site_dir.active(sites)

    def take(spec: dict, page: int = 1) -> int:
        nonlocal dups
        tbs = "qdr:d" if fresh and spec["label"].startswith("Facebook") else (spec.get("tbs") or "")
        code, hits = websearch.run_query(prov, key, spec["q"], tbs, **({"page": page} if page > 1 else {}))
        kept = 0
        for h in hits if code == 200 else []:
            r = websearch.to_listing(h, {"id": spec["label"], "engine_label": "Google", "portals_ok": True}, spec["q"], spec["area"])
            if not r or r["purpose"] != "sale":
                continue
            fps = fingerprints(r)
            hs = [_h("u" + r["url"])] + [_h(fp) for fp in fps]
            if r["url"] in seen_urls or any(fp in seen_fps for fp in fps) or any(x in seen_h for x in hs):
                dups += 1
                continue
            seller = _h("k:" + r["phone"]) if r.get("phone") else ""
            known = bool(seller) and seller in seen_h  # this number sent us a listing on an earlier day: same seller, not a stranger
            seen_urls.add(r["url"])
            seen_fps.update(fps)
            seen_h.update(hs)
            # the memory now lives privately in Drive; it holds only short one-way hashes, never a phone number itself
            seen_keep.update({_h(f): day.isoformat() for f in ["u" + r["url"]] + [fp for fp in fps if not fp.startswith("p:")]})
            if seller:
                seen_keep[seller] = day.isoformat()
            p = roi.project(r, roi.DEFAULTS, {})
            new.append({"date": day.isoformat(), "area": r["area"], "type": r["ptype"], "title": r["title"],
                        "price_bdt": int(r["price"]) if r.get("price") else "", "size_sqft": int(r["size_sqft"]) if r.get("size_sqft") else "",
                        "price_per_sqft": round(r["price"] / r["size_sqft"]) if r.get("price") and r.get("size_sqft") else "",
                        "gross_yield_pct": p["gross"] or "", "phone": r.get("phone") or "", "site": spec["label"], "known_seller": "yes" if known else "",
                        "url": r["url"], "snippet": r.get("snippet", ""), "query": spec["q"], "fingerprints": "|".join(fps),
                        "via": websearch.via_host(h.get("via", "")) if "google.com/goto" in r["url"] else ""})
            kept += 1
        log.append((spec["label"] + (f" (page {page})" if page > 1 else ""), spec["q"], code, len(hits), kept))
        return len(hits) if code == 200 else -1

    for spec in plan(day, extra, active):
        take(spec)
    daily_log = len(log)
    # balance: keep searching portals, directory sites and the open web (next Google pages included) until they have
    # found as many new listings as Facebook did, within a fixed search budget
    fb = lambda: sum(1 for r in new if is_facebook(r))
    budget, done, ended = balance if balance is not None else CONF["balance"]["max_searches"], 0, set()
    for spec, page in balance_plan(day, active):
        if done >= budget or len(new) - fb() >= fb():
            break
        if spec["q"] in ended:  # an earlier page of this search came back short: there is no next page
            continue
        n = take(spec, page)
        done += 1
        if n < 8:
            ended.add(spec["q"])
    outdir = Path(out)
    outdir.mkdir(parents=True, exist_ok=True)
    paths = {"leads": outdir / f"leads-{day}.csv", "master": outdir / "master.csv", "digest": outdir / f"digest-{day}.md",
             "seen": outdir / "seen.tsv"}
    for r in [r for r in top_calls(new)[:enrich_top] if "bdhousing.com" not in r["url"]]:  # bdHousing: the contact tool reads its seller card
        fill_from_page(r)
    # the site contact tool: the seller's number from listing pages where the site allows it (bdHousing first),
    # otherwise the exact step an associate takes on that site; it also fills a missing price or size
    from . import contacts
    cstats = contacts.enrich(new, cap=CONF.get("contact_pages", 25))
    write_csv(paths["leads"], new)
    if master:
        write_csv(paths["master"], old + new)  # optional full history; the seen file is all a daily run needs
    write_seen(paths["seen"], seen_keep)
    paths["digest"].write_text(digest(day, new, dups, log, len(old) + len(new)), encoding="utf-8")
    # a few hundred bytes the weekly manager reads instead of re-running searches
    by_site: dict[str, int] = {}
    for r in new:
        by_site[r["site"]] = by_site.get(r["site"], 0) + 1
    paths["stats"] = outdir / f"stats-{day}.json"
    paths["stats"].write_text(json.dumps({
        "date": str(day), "new": len(new), "repeats_skipped": dups, "searches": len(log),
        "with_phone": sum(1 for r in new if r["phone"]), "with_price": sum(1 for r in new if plausible_price(r)),
        "by_site": by_site, "memory_used": bool(seen), "contact_pages": cstats["pages_read"], "contact_phones": cstats["phones_found"],
        "facebook": fb(), "other": len(new) - fb(), "balance_searches": done, "balanced": len(new) - fb() >= fb(),
        "zero_result_searches": [q for _, q, code, n, _ in log[:daily_log] if code == 200 and n == 0],  # balance pages often end empty by design
        "errored_searches": [q for _, q, code, _, _ in log if code != 200]}, ensure_ascii=False), encoding="utf-8")
    return {"new": len(new), "duplicates": dups, "searches": len(log), **{k: str(v) for k, v in paths.items()}}


OWNER = re.compile(r"\bowner\b|direct|no broker|without broker|মালিক", re.I)


def plausible_price(r: dict) -> bool:
    """A price that can be a real Dhaka sale price: ৳5 lakh to ৳500 crore, and ৳2,000 (land ৳300) to 150,000 per sqft when the size is known."""
    p, s = float(r.get("price_bdt") or 0), float(r.get("size_sqft") or 0)
    low = 300 if r.get("type") in ("land", "house") else 2_000  # land sells far cheaper per sqft than flats (5 katha for 65 lakh)
    return 500_000 <= p <= 5e9 and (not s or low <= p / s <= 150_000)


def top_calls(new: list[dict], n: int = 3) -> list[dict]:
    """Whom to call first: a number to ring, owner wording, a stated price and size. One call per number: one agent can own dozens of ads."""
    def score(r):
        priced = plausible_price(r)  # an absurd price must not win a call slot
        return 3 * bool(r["phone"]) + 2 * bool(OWNER.search(r["title"] + " " + r["snippet"])) + 2 * priced + bool(r["size_sqft"])
    out, used = [], set()
    for r in sorted(new, key=lambda r: (-score(r), -float(r["gross_yield_pct"] or 0))):
        if r["phone"] and r["phone"] in used:
            continue
        used.add(r["phone"])
        out.append(r)
        if len(out) == n:
            break
    return out


def fill_from_page(r: dict) -> None:
    """Open the listing page, only where the site's robots.txt allows it, for a phone or price the snippet lacked."""
    if re.search(r"facebook\.com|google\.|bproperty\.com|bikroy\.com", r["url"]):
        return  # these block crawlers: Google's snippet is all we use
    try:
        if not scrape.may_fetch(r["url"])[0]:
            return
        import time
        time.sleep(max(1.5, scrape.crawl_delay(r["url"])))
        st, page = scrape.fetch(r["url"])
        d = parse.detail_record(page, r["url"]) if st == 200 else None
    except Exception:  # noqa: BLE001
        return
    if d:
        r["phone"] = r["phone"] or d.get("phone", "")
        # a page price under 5 lakh or over 500 crore is a placeholder ("call for price", 5,000), not a price
        if not r["price_bdt"] and d.get("price") and 500_000 <= d["price"] <= 5e9:
            r["price_bdt"] = int(d["price"])
        r["size_sqft"] = r["size_sqft"] or (int(d["size_sqft"]) if d.get("size_sqft") else "")


def flag(r: dict) -> str:
    if r.get("price_bdt") and r.get("size_sqft") and not plausible_price(r):
        rate = float(r["price_bdt"]) / float(r["size_sqft"])
        return f"price works out to ৳{rate:,.0f} per sqft, which cannot be right - ask the seller for the real total price"
    return store.data_flags({"price": float(r["price_bdt"] or 0) or None, "size_sqft": float(r["size_sqft"] or 0) or None,
                             "ptype": r["type"]})


def drafts(r: dict) -> tuple[str, str]:
    """Two ready WhatsApp messages (English, Bangla). The owner sends them; nothing is sent automatically."""
    what, area = r["title"][:70], r["area"].capitalize()
    bn = websearch.AREA_BN.get(r["area"], area)
    return (f'Assalamu alaikum. I am from MRA Real Estate. I saw your listing "{what}" in {area}. Is it still available? We work with '
            f"verified buyers. Could you confirm the final price, size and floor, and whether the papers are ready to view?",
            f'আসসালামু আলাইকুম। আমি MRA Real Estate থেকে বলছি। {bn}-এ আপনার "{what}" বিজ্ঞাপনটি দেখেছি। এটি কি এখনও খালি আছে? '
            f"আমাদের যাচাইকৃত ক্রেতা আছে। চূড়ান্ত দাম, সাইজ ও ফ্লোর জানাবেন কি? কাগজপত্র দেখার জন্য প্রস্তুত কি?")


def write_csv(path: Path, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def _money(v) -> str:
    v = float(v) if v not in ("", None) else 0
    return "-" if not v else (f"৳{v / 1e7:.2f} Cr" if v >= 1e7 else f"৳{v / 1e5:.1f} Lakh")


def _line(r: dict) -> str:
    size = f" · {int(r['size_sqft']):,} sqft" if r["size_sqft"] else ""
    return f"- **{r['title'][:90]}** · {r['area'].capitalize()} · {_money(r['price_bdt'])}{size} · {r['phone'] or 'contact on post'} · [{r['site']}]({r['url']})"


def digest(day, new, dups, log, total) -> str:
    b = io.StringIO()
    w = b.write
    w(f"# MRA Property Scout — {day}\n\n**{len(new)} new** listings ({dups} repeats skipped) from {len(log)} Google searches.\n\n")
    calls = top_calls(new)
    w("## Today's 3 to call\n")
    for i, r in enumerate(calls, 1):
        en, bn = drafts(r)
        w(f"{i}. {_line(r)[2:]}\n")
        w((f"   - Clear with seller: {flag(r)}\n" if flag(r) else "") + (f"   - No number shown: open the post and message there\n" if not r["phone"] else ""))
        w(f"   > {en}\n   >\n   > {bn}\n")
    if not calls:
        w("- No new listing today. Tomorrow's searches use a different slice.\n")
    w("\n## New by area\n\n| Area | New | With phone | Median ৳/sqft |\n|---|---|---|---|\n")
    for a in AREAS:
        ar = [r for r in new if r["area"] == a]
        pp = sorted(r["price_per_sqft"] for r in ar if r["price_per_sqft"] and 2000 <= r["price_per_sqft"] <= 150000)
        w(f"| {a.capitalize()} | {len(ar)} | {sum(1 for r in ar if r['phone'])} | {f'{pp[len(pp) // 2]:,}' if pp else '-'} |\n")
    for title, keep in (("From Facebook", is_facebook), ("From property portals and the web", lambda r: not is_facebook(r))):
        part = [r for r in new if keep(r)]
        w(f"\n## {title}: {len(part)}\n")
        for r in part[:15]:
            w(_line(r) + (f"\n  > {r['snippet'][:200]}" if r["snippet"] else "") + "\n")
    w("\n## Searches\n\n| Label | Query | Results | New |\n|---|---|---|---|\n")
    for label, q, code, n, kept in log:
        w(f"| {label} | `{q}` | {n if code == 200 else f'error {code}'} | {kept} |\n")
    return b.getvalue()
