"""The lean daily process: targeted Google searches only, new listings only.

    python -m property_finder scout --master master.csv --out out

One run = about 20 searches (2 per area every day for Facebook groups, plus a rotating slice of
site:bproperty.com / site:bikroy.com / bdHousing / Bdstall / plot / Marketplace searches). Results are
read from Google's title and snippet, so no site is crawled. A listing is new only if neither its URL
nor its fingerprint (phone, size + price, or the post's text) is in the master list; reposts of the same
ad in other Facebook groups count as duplicates. Writes leads-DATE.csv (today's new only), the updated
master CSV and a short digest.
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

from . import parse, roi, websearch
from .scrape import AREAS

CONF = json.loads((Path(__file__).parent / "scout.json").read_text(encoding="utf-8"))
COLS = ["date", "area", "type", "title", "price_bdt", "size_sqft", "price_per_sqft", "gross_yield_pct", "phone",
        "site", "url", "snippet", "query", "fingerprints"]


def plan(day: dt.date, extra: int | None = None) -> list[dict]:
    """Today's searches: the daily ones for every area, then a fresh slice of the rotating pool."""
    extra = CONF["extra_per_day"] if extra is None else extra
    fill = lambda t, a, v="", k="": t.format(area=a.capitalize(), area_bn=websearch.AREA_BN[a], variant=v, katha=k)
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
    return out + [pool[(start + i) % len(pool)] for i in range(min(extra, len(pool)))]


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


def read_master(path: str | None) -> tuple[list[dict], set[str], set[str]]:
    if not path or not Path(path).exists():
        return [], set(), set()
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    return rows, {r["url"] for r in rows}, {fp for r in rows for fp in (r.get("fingerprints") or "").split("|") if fp}


def run(master: str | None, out: str = "out", extra: int | None = None, day: dt.date | None = None) -> dict:
    day = day or dt.date.today()
    old, seen_urls, seen_fps = read_master(master)
    prov, key = websearch.provider_from_env()
    if not key:
        raise SystemExit("Set SERPER_API_KEY (or BRAVE_API_KEY) first.")
    new, dups, log = [], 0, []
    for spec in plan(day, extra):
        code, hits = websearch.run_query(prov, key, spec["q"], spec.get("tbs") or "")
        kept = 0
        for h in hits if code == 200 else []:
            r = websearch.to_listing(h, {"id": spec["label"], "engine_label": "Google", "portals_ok": True}, spec["q"], spec["area"])
            if not r or r["purpose"] != "sale":
                continue
            fps = fingerprints(r)
            if r["url"] in seen_urls or any(fp in seen_fps for fp in fps):
                dups += 1
                continue
            seen_urls.add(r["url"])
            seen_fps.update(fps)
            p = roi.project(r, roi.DEFAULTS, {})
            new.append({"date": day.isoformat(), "area": r["area"], "type": r["ptype"], "title": r["title"],
                        "price_bdt": int(r["price"]) if r.get("price") else "", "size_sqft": int(r["size_sqft"]) if r.get("size_sqft") else "",
                        "price_per_sqft": round(r["price"] / r["size_sqft"]) if r.get("price") and r.get("size_sqft") else "",
                        "gross_yield_pct": p["gross"] or "", "phone": r.get("phone") or "", "site": spec["label"],
                        "url": r["url"], "snippet": r.get("snippet", ""), "query": spec["q"], "fingerprints": "|".join(fps)})
            kept += 1
        log.append((spec["label"], spec["q"], code, len(hits), kept))
    outdir = Path(out)
    outdir.mkdir(parents=True, exist_ok=True)
    paths = {"leads": outdir / f"leads-{day}.csv", "master": outdir / "master.csv", "digest": outdir / f"digest-{day}.md"}
    write_csv(paths["leads"], new)
    write_csv(paths["master"], old + new)
    paths["digest"].write_text(digest(day, new, dups, log, len(old) + len(new)), encoding="utf-8")
    return {"new": len(new), "duplicates": dups, "searches": len(log), **{k: str(v) for k, v in paths.items()}}


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
    w(f"# MRA Property Scout — {day}\n\n**{len(new)} new** listings ({dups} repeats skipped) from {len(log)} Google searches. Master list: {total}.\n\n")
    calls, used = [], set()
    for r in sorted([r for r in new if r["phone"]], key=lambda r: (not r["price_bdt"], -float(r["gross_yield_pct"] or 0))):
        if r["phone"] not in used:
            calls.append(r)
            used.add(r["phone"])
    w("## Today's 3 to call\n")
    w("".join(_line(r) + "\n" for r in calls[:3]) or "- No new listing with a phone number today; open the posts below.\n")
    w("\n## New by area\n\n| Area | New | With phone | Median ৳/sqft |\n|---|---|---|---|\n")
    for a in AREAS:
        ar = [r for r in new if r["area"] == a]
        pp = sorted(r["price_per_sqft"] for r in ar if r["price_per_sqft"] and 2000 <= r["price_per_sqft"] <= 150000)
        w(f"| {a.capitalize()} | {len(ar)} | {sum(1 for r in ar if r['phone'])} | {f'{pp[len(pp) // 2]:,}' if pp else '-'} |\n")
    for title, keep in (("From Facebook", lambda r: r["site"].startswith("Facebook")),
                        ("From property portals and the web", lambda r: not r["site"].startswith("Facebook"))):
        part = [r for r in new if keep(r)]
        w(f"\n## {title}: {len(part)}\n")
        for r in part[:15]:
            w(_line(r) + (f"\n  > {r['snippet'][:200]}" if r["snippet"] else "") + "\n")
    w("\n## Searches\n\n| Label | Query | Results | New |\n|---|---|---|---|\n")
    for label, q, code, n, kept in log:
        w(f"| {label} | `{q}` | {n if code == 200 else f'error {code}'} | {kept} |\n")
    return b.getvalue()
