"""Site directory: other websites that list Dhaka properties MRA wants, found and tested weekly, used by the scout once proven.

The weekly manager runs  python -m property_finder sites --registry OLD.json --leads leads-*.csv --out NEW.json [--add domain ...]
and uploads NEW.json to Drive as sites-YYYY-MM-DD.json. The scout reads the newest one with --sites.

Rules (deterministic, so the manager cannot talk a site in):
- candidates come from hosts already seen in the scout's leads, 3 fixed discovery searches a week, and --add (domain names only);
- each week up to PROBE_CAP candidate/active sites get 2 Google site: searches, counted through the scout's own listing filter;
- a candidate becomes ACTIVE after 2 consecutive weekly probes that each keep >= 3 listings in the 6 areas;
- a site is DROPPED after 3 consecutive probes that keep 0.
Only a validated domain is ever stored; the scout builds its query from a fixed template, never from text in this file.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import re
import urllib.parse
from pathlib import Path

from . import websearch

DOMAIN = re.compile(r"^(?=.{4,60}$)[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+$")
# already searched every day, social networks, search engines and sites that never list single Dhaka properties
COVERED = re.compile(r"(^|\.)(facebook|fb|bproperty|bikroy|bdhousing|bdstall|google|instagram|youtube|tiktok|linkedin|twitter|x|"
                     r"pinterest|wikipedia|reddit|quora|whatsapp|telegram|amazon|daraz)\.", re.I)
AREAS = ["gulshan", "banani", "purbachal", "uttara", "dhanmondi", "bashundhara", "baridhara"]
PROBE_CAP = 6          # sites probed a week (2 searches each)
PROMOTE_KEPT, PROMOTE_WEEKS, DROP_WEEKS = 3, 2, 3
DISCOVERY = [  # fixed queries: listings outside the portals already covered
    '"{area}" flat for sale -site:facebook.com -site:bproperty.com -site:bikroy.com -site:bdhousing.com -site:bdstall.com',
    '"{area}" plot sale katha -site:facebook.com -site:bproperty.com -site:bikroy.com -site:bdhousing.com -site:bdstall.com',
    '"{area}" apartment sale Dhaka real estate listing -site:facebook.com -site:bproperty.com -site:bikroy.com -site:bdhousing.com',
]


def clean(host: str) -> str | None:
    h = (host or "").lower().strip().removeprefix("www.").split(":")[0]
    return h if DOMAIN.match(h) and not COVERED.search("." + h + ".") and not websearch.FOREIGN_HOSTS.search(h) else None


def load(path: str | None) -> dict:
    try:
        d = json.loads(Path(path).read_text(encoding="utf-8")) if path else {}
    except (OSError, ValueError):
        d = {}
    sites = {k: v for k, v in (d.get("sites") or {}).items() if clean(k) == k and isinstance(v, dict)}
    return {"updated": d.get("updated", ""), "sites": sites}


def active(path: str | None) -> list[str]:
    return sorted(k for k, v in load(path)["sites"].items() if v.get("status") == "active")


def _kept(prov, key, q, area, label) -> tuple[int, list[str]]:
    code, hits = websearch.run_query(prov, key, q, "")
    if code != 200:
        return -1, []
    n, hosts = 0, []
    for h in hits:
        r = websearch.to_listing(h, {"id": label, "engine_label": "Google", "portals_ok": True}, q, area)
        if r and r["purpose"] == "sale":
            n += 1
            hosts.append(urllib.parse.urlparse(r["url"]).netloc)
    return n, hosts


def update(registry: str | None, leads: list[str], add: list[str], day: dt.date | None = None) -> dict:
    day = day or dt.date.today()
    reg = load(registry)
    sites = reg["sites"]
    key = os.environ.get("SERPER_API_KEY", "")
    log = {"discovered": [], "probed": {}, "promoted": [], "dropped": [], "searches": 0}

    def note(host, via):
        h = clean(host)
        if h and h not in sites:
            sites[h] = {"status": "candidate", "found_via": via, "first_seen": day.isoformat(), "probes": []}
            log["discovered"].append(h)

    for p in leads:  # hosts the scout already met on the open web
        try:
            for r in csv.DictReader(open(p, encoding="utf-8-sig")):
                note(urllib.parse.urlparse(r["url"]).netloc, "seen in scout results")
        except OSError:
            continue
    for d in add:
        note(d, "added by manager")
    if not key:
        reg.update(updated=day.isoformat(), log={**log, "error": "SERPER_API_KEY missing: no searches run"})
        return reg

    week = day.toordinal() // 7
    for i, q in enumerate(DISCOVERY):
        area = AREAS[(week + i) % len(AREAS)]
        n, hosts = _kept("serper", key, q.format(area=area.capitalize()), area, "Open web")
        log["searches"] += 1
        for h in hosts:
            note(h, "discovery search")

    queue = sorted((k for k, v in sites.items() if v["status"] in ("candidate", "active")),
                   key=lambda k: (sites[k]["probes"][-1]["date"] if sites[k]["probes"] else "", k))[:PROBE_CAP]
    for j, h in enumerate(queue):  # least recently probed first
        total = 0
        for a in (AREAS[(week + j) % len(AREAS)], AREAS[(week + j + 3) % len(AREAS)]):
            n, _ = _kept("serper", key, f'site:{h} "{a.capitalize()}" sale', a, f"Directory: {h}")
            log["searches"] += 1
            total += max(n, 0)
        s = sites[h]
        s["probes"] = (s["probes"] + [{"date": day.isoformat(), "kept": total}])[-8:]
        log["probed"][h] = total
        last = [p["kept"] for p in s["probes"]]
        if s["status"] == "candidate" and len(last) >= PROMOTE_WEEKS and all(k >= PROMOTE_KEPT for k in last[-PROMOTE_WEEKS:]):
            s["status"] = "active"
            s["active_since"] = day.isoformat()
            log["promoted"].append(h)
        elif len(last) >= DROP_WEEKS and not any(last[-DROP_WEEKS:]):
            s["status"] = "dropped"
            log["dropped"].append(h)
    reg.update(updated=day.isoformat(), log=log)
    return reg


def write(registry: str | None, leads: list[str], add: list[str], out: str) -> dict:
    reg = update(registry, leads, add)
    Path(out).write_text(json.dumps(reg, ensure_ascii=False, indent=1), encoding="utf-8")
    counts = {s: sum(1 for v in reg["sites"].values() if v["status"] == s) for s in ("active", "candidate", "dropped")}
    return {**counts, **{k: reg["log"][k] for k in ("discovered", "promoted", "dropped", "searches")}}
