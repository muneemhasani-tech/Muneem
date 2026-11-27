"""Site contact tool: how to reach the seller of each listing, site by site.

    python -m property_finder contacts leads-DATE.csv --out leads-with-contacts.csv [--cap 25]

For each listing without a phone number it either reads the seller's contact from the listing page, where that
site's robots.txt allows our bot (and AI agents), or records the exact step an associate takes on that site.
It never logs in, never fills a form, never sends a message and never works around a block: Bikroy and Bdstall
refuse automated access, Bproperty's robots.txt bans AI agents, and Facebook needs a person. Those listings get a
`contact_how` step instead ("open the ad, tap Show phone number").

Adapters:
- bdhousing.com: the seller card (`mobile_diealer` tel: link, person and company name). The page also carries
  bdHousing's own hotline in its JSON-LD contactPoint; that number is never taken as the seller's.
- any other allowed site (agency, developer, small classifieds found on the open web): tel: and wa.me links on
  the listing page, skipping the site's JSON-LD company number; a number the site shows on every listing is
  recorded with contact_name "site number" so nobody mistakes an agency switchboard for an owner.
"""
from __future__ import annotations

import csv
import re
import time
from concurrent.futures import ThreadPoolExecutor
import urllib.parse
from pathlib import Path

from . import parse, scrape

# site -> what an associate does when the tool may not read the page (shown in the emails)
HOW = {
    "bikroy.com": "Open the ad and tap 'Show phone number' or 'Chat' (Bikroy blocks automated access)",
    "bproperty.com": "Open the listing and tap 'Call' or 'WhatsApp' on the agent card",
    "bdstall.com": "Open the ad and tap 'Show number'",
    "facebook.com": "Open the post and message the seller on Messenger",
    "instagram.com": "Open the post and send a direct message",
    "bdhousing.com": "Open the listing; the seller's number is on the right",
}
NO_FETCH = re.compile(r"(?:^|\.)(?:bikroy\.com|bdstall\.com|bproperty\.com|facebook\.com|instagram\.com|google\.[a-z.]+|youtube\.com|youtu\.be)$")
FETCH_TIMEOUT = 150  # bdHousing can take two minutes to start sending a listing page
WORKERS = 4  # pages read at the same time (still a gentle load: a few requests a minute per site)
PHONE = re.compile(r"(?:\+?88)?0?1[3-9]\d{8}")


def _bd(num: str) -> str:
    d = re.sub(r"\D", "", num or "")
    d = d[2:] if d.startswith("88") else d
    d = "0" + d if len(d) == 10 and d.startswith("1") else d
    return d if re.fullmatch(r"01[3-9]\d{8}", d) else ""


def _jsonld_numbers(page: str) -> set[str]:
    """Company numbers in structured data (contactPoint/telephone): the site's own hotline, not a seller."""
    out = set()
    for block in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', page, re.S | re.I):
        out |= {_bd(m) for m in re.findall(r'"telephone"\s*:\s*"([^"]+)"', block)}
    return out - {""}


def bdhousing(page: str) -> dict:
    hotline = _jsonld_numbers(page)
    nums = [_bd(m) for m in re.findall(r'class="mobile_diealer"\s+href="tel:\'?([^"\']+)', page)]
    nums = [n for n in nums if n and n not in hotline]
    if not nums:
        return {}
    person = re.search(r'pop-up-info-area"><i class="glyphicon glyphicon-user"></i>\s*([^<]{2,60})<', page)
    company = re.search(r'class="user_info_view">\s*<a href="[^"]*">\s*<span class="pop-up-info-area">\s*([^<]{2,80})<', page)
    name = " · ".join(x.group(1).strip() for x in (person, company) if x)
    return {"phone": nums[0], "contact_name": name}


def generic(page: str) -> dict:
    hotline = _jsonld_numbers(page)
    links = re.findall(r'href=["\'](?:tel:|https?://(?:wa\.me|api\.whatsapp\.com/send\?phone=))([^"\'&]+)', page, re.I)
    nums = list(dict.fromkeys(n for n in (_bd(x) for x in links) if n and n not in hotline))
    if not nums:
        return {}
    return {"phone": nums[0], "contact_name": "site number" if len(nums) > 2 else ""}


ADAPTERS = {"bdhousing.com": bdhousing}


def host_of(r: dict) -> str:
    """The real site: Google redirect links carry it in `via`."""
    h = urllib.parse.urlparse(r["url"]).netloc.lower().removeprefix("www.")
    return (r.get("via") or h) if h in ("google.com", "") else h


def how_for(host: str) -> str:
    for k, v in HOW.items():
        if host == k or host.endswith("." + k):
            return v
    return "Open the listing and use the contact details on the page"


def page_url(r: dict) -> str:
    """The listing page to read: the URL itself, or for a Google redirect link the address Google showed for it."""
    if "google.com/goto" in r["url"]:
        u = r.get("via_url") or ""
        return u if re.search(r"/details/\d+|/property/|/ad/|/listing", u) else ""
    return r["url"]


def readable(r: dict) -> bool:
    return bool(page_url(r)) and not NO_FETCH.search(host_of(r))


def read(r: dict) -> dict:
    """Seller contact from one listing page, or {} when not allowed or not found. Also fills a missing price/size."""
    host, url = host_of(r), page_url(r)
    if not url or NO_FETCH.search(host):
        return {}
    ok, _why = scrape.may_fetch(url)
    if not ok:
        return {}
    time.sleep(max(1.5, scrape.crawl_delay(url)))
    st, page = scrape.fetch(url, FETCH_TIMEOUT)
    if st != 200 or not page:
        return {}
    adapter = next((f for k, f in ADAPTERS.items() if host == k or host.endswith("." + k)), generic)
    out = adapter(page)
    try:
        d = parse.detail_record(page, url) or {}
    except Exception:  # noqa: BLE001  a page the parser does not know
        d = {}
    if not r.get("price_bdt") and d.get("price") and 500_000 <= d["price"] <= 5e9:
        out["price_bdt"] = int(d["price"])
    if not r.get("size_sqft") and d.get("size_sqft"):
        out["size_sqft"] = int(d["size_sqft"])
    return out


def enrich(rows: list[dict], cap: int = 25, budget_s: float = 360) -> dict:
    """Fill phone/contact_name where a page may be read (at most `cap` pages, a few at a time, within about `budget_s`
    seconds); every row without a phone gets `contact_how`. Rows from sites with a dedicated adapter go first."""
    t0 = time.time()
    todo = [r for r in rows if not r.get("phone")]
    todo.sort(key=lambda r: (host_of(r) not in ADAPTERS, not readable(r)))
    picks = [r for r in todo if readable(r)][:cap]
    found = 0

    def one(r):
        if time.time() - t0 > budget_s:  # out of time: leave the rest for the associates
            return r, {}
        try:
            return r, read(r)
        except Exception:  # noqa: BLE001  one bad page never stops the run
            return r, {}
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for r, got in pool.map(one, picks):
            for k, v in got.items():
                if v and not r.get(k):
                    r[k] = v
            found += bool(got.get("phone"))
    for r in todo:
        if not r.get("phone"):
            r["contact_how"] = how_for(host_of(r))
    return {"pages_read": len(picks), "phones_found": found, "seconds": round(time.time() - t0)}


def run_file(path: str, out: str, cap: int = 25) -> dict:
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    stats = enrich(rows, cap=cap, budget_s=10_000)
    cols = list(rows[0].keys()) if rows else []
    cols += [c for c in ("contact_name", "contact_how") if c not in cols]
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    return stats
