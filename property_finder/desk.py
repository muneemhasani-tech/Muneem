"""Lead Desk queue: today's leads with no seller number, as one document for the shared Lead Desk page.

    python -m property_finder desk leads-DATE.csv --routes associates.json --out desk-DATE.json

Associates open each ad on their own logged-in phone, reveal the number and paste it into the Desk; nothing here
logs in to or messages any site. The scout writes the output file to the Desk's database (collection "queue",
document id = the date) with the ArtifactData tool when that tool is available.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from . import contacts, mailer, weekly

AREA = {"gulshan": "Gulshan", "banani": "Banani", "purbachal": "Purbachal", "uttara": "Uttara", "dhanmondi": "Dhanmondi",
        "bashundhara": "Bashundhara", "baridhara": "Baridhara DZ"}
TYPE = {"apartment": "Flat", "land": "Land", "house": "Land + building", "commercial": "Commercial"}


def queue(paths: list[str], routes_path: str) -> dict[str, list[dict]]:
    routes = mailer.load_routes(routes_path)
    seen, out = set(), {}
    for r in weekly.load(paths):
        if r.get("phone"):
            continue
        key = re.sub(r"\W+", " ", mailer.clean_title(r["title"], 200).lower())[:70] + r["area"]
        if key in seen:
            continue
        seen.add(key)
        names = [a["name"] for a in routes if not a.get("all") and mailer.mine([r], a)]
        focus = r["area"] in ("gulshan", "banani", "purbachal") and r["type"] in ("land", "house")
        price = float(r["price_bdt"]) if r.get("price_bdt") and weekly.plausible_price(r) else None
        out.setdefault(r["date"], []).append({
            "id": hashlib.sha1(r["url"].encode()).hexdigest()[:10], "d": r["date"], "a": AREA.get(r["area"], r["area"]),
            "t": TYPE.get(r["type"], r["type"]), "title": mailer.clean_title(r["title"], 100),
            "p": (f"৳{price / 1e7:.2f} Cr" if price >= 1e7 else f"৳{price / 1e5:.0f} Lakh") if price else "",
            "s": f"{int(float(r['size_sqft'])):,} sqft" if r.get("size_sqft") else "", "src": mailer.source_label(r),
            "how": r.get("contact_how") or contacts.how_for(contacts.host_of(r)), "link": mailer.post_link(r)[0],
            "who": (["Muneem"] if focus or not names else []) + names})
    return out


def write(paths: list[str], routes_path: str, out: str) -> dict:
    q = queue(paths, routes_path)
    day = max(q) if q else ""
    Path(out).write_text(json.dumps({"date": day, "items": q.get(day, [])}, ensure_ascii=False), encoding="utf-8")
    return {"date": day, "items": len(q.get(day, []))}
