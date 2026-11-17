"""One unattended daily run: crawl every source, run web searches for today's areas, write a digest and a CSV.

Built for a scheduled cloud agent. The database is empty in a fresh session, so "new" means
"not in yesterday's CSV" when one is given (pass it with --seen), otherwise "found in this run".
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import time
from pathlib import Path

from . import scrape, store, web, websearch

AREAS = list(scrape.AREAS)


def todays_web_areas(n: int, day: dt.date | None = None) -> list[str]:
    """Rotate web searches through the areas, n per day, so the search budget lasts (6 areas, 2 a day = all every 3 days)."""
    if n >= len(AREAS):
        return AREAS
    day = day or dt.date.today()
    start = (day.toordinal() * n) % len(AREAS)
    return [AREAS[(start + i) % len(AREAS)] for i in range(n)]


def read_seen(path: str | None) -> set[str]:
    if not path or not Path(path).exists():
        return set()
    with open(path, encoding="utf-8-sig", newline="") as f:
        return {row.get("Website", "") for row in csv.DictReader(f)}


def run(web_areas: int = 2, seen: str | None = None, out: str = ".", details: int = 15, do_web: bool = True) -> dict:
    t0 = time.time()
    job = scrape.Job()
    job.start(AREAS, ["apartment", "house", "land"], list(scrape.SOURCES), details=details, benchmark=True, web=False)
    while job.snapshot()["running"]:
        time.sleep(5)
    results = job.snapshot()["results"]
    areas_today = todays_web_areas(web_areas) if do_web else []
    if areas_today:
        results += websearch.search_web(areas_today, max_queries=len(websearch.QUERIES) * len(areas_today))
    con = store.connect()
    rows = store.query(con, limit=5000)
    seen_urls = read_seen(seen)
    for r in rows:
        r["is_new"] = (r["url"] not in seen_urls) if seen_urls else r["first_seen"] >= t0 - 1
    day = dt.date.today().isoformat()
    outdir = Path(out)
    outdir.mkdir(parents=True, exist_ok=True)
    md, csv_path = outdir / f"mra-property-hunt-{day}.md", outdir / f"mra-property-hunt-{day}.csv"
    md.write_text(digest(rows, results, areas_today, day, bool(seen_urls), websearch.status(con)), encoding="utf-8")
    csv_path.write_text(web.to_csv(rows), encoding="utf-8-sig")
    con.close()
    return {"digest": str(md), "csv": str(csv_path), "listings": len(rows), "new": sum(r["is_new"] for r in rows)}


def _money(n) -> str:
    if not n:
        return "-"
    return f"৳{n / 1e7:.2f} Cr" if n >= 1e7 else f"৳{n / 1e5:.1f} Lakh"


def _line(r) -> str:
    bits = [f"**{r['title'][:90]}**", r["area"].capitalize(), _money(r["price"])]
    if r.get("size_sqft"):
        bits.append(f"{r['size_sqft']:,.0f} sqft")
    if r.get("total") is not None and r.get("gross"):
        bits.append(f"yield {r['gross']:.1f}%, 5-yr {r['total']:.0f}%")
    contact = " ".join(x for x in (r.get("poster"), r.get("phone")) if x) or "contact on listing"
    return f"- {' · '.join(bits)} · {contact} · [{r['source']}]({r['url']})"


def digest(rows, results, areas_today, day, had_seen, ws) -> str:
    new = [r for r in rows if r["is_new"]]
    out = io.StringIO()
    w = out.write
    w(f"# MRA Property Hunt — {day}\n\n")
    w(f"**{len(new)} new** of {len(rows)} for-sale listings in Gulshan, Banani, Purbachal, Uttara, Dhanmondi and Bashundhara."
      f"{'' if had_seen else ' (No previous CSV given, so every listing counts as new today.)'}\n")
    if areas_today:
        w(f"Web search today: {', '.join(a.capitalize() for a in areas_today)} "
          f"({ws['used_this_month']} searches used this month).\n")
    w("\n## Today's 3 to call\n")
    callable_ = sorted([r for r in new if r.get("phone")], key=lambda r: (r.get("is_owner") != 1, -(r.get("total") or 0)))
    for r in callable_[:3]:
        w(_line(r) + "\n")
    if not callable_:
        w("- No new listing with a phone number today. Start with the top of the next list and open the listing.\n")
    w("\n## Best projected returns (new, priced)\n")
    for r in sorted([r for r in new if r.get("total") is not None and r.get("gross")], key=lambda r: -r["total"])[:10]:
        w(_line(r) + "\n")
    drops = [r for r in rows if r.get("dropped")]
    if drops:
        w("\n## Price drops\n")
        for r in drops[:10]:
            w(_line(r) + f" (was {_money(r['price_prev'])})\n")
    owners = [r for r in new if r.get("is_owner") == 1]
    w(f"\n## Owner-posted (new): {len(owners)}\n")
    for r in owners[:10]:
        w(_line(r) + "\n")
    social = [r for r in new if (r.get("evidence") or "").startswith("search")]
    w(f"\n## From Facebook and web search (new): {len(social)}\n")
    for r in social[:15]:
        w(_line(r) + (f"\n  > {r['snippet'][:220]}" if r.get("snippet") else "") + "\n")
    w("\n## Per area\n\n| Area | New | All | Avg ৳/sqft |\n|---|---|---|---|\n")
    for a in AREAS:
        ar = [r for r in rows if r["area"] == a]
        pp = [r["ppsf"] for r in ar if r.get("ppsf")]
        w(f"| {a.capitalize()} | {sum(r['is_new'] for r in ar)} | {len(ar)} | {round(sum(pp) / len(pp)):,} |\n" if pp else
          f"| {a.capitalize()} | {sum(r['is_new'] for r in ar)} | {len(ar)} | - |\n")
    w("\n## Source health\n\n| Source | Found | Note |\n|---|---|---|\n")
    agg: dict[str, dict] = {}
    for r in results:
        a = agg.setdefault(r["source"], {"found": 0, "err": ""})
        a["found"] += r.get("found", 0)
        a["err"] = a["err"] or (r.get("error") or "")
    for s, a in sorted(agg.items()):
        w(f"| {s} | {a['found']} | {a['err'][:80]} |\n")
    w("\nProjected returns use the placeholder rent assumptions unless enough rent ads were found; check before quoting them.\n")
    return out.getvalue()
