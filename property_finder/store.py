"""SQLite store: dedupes across sites, tracks price changes and lead status."""
from __future__ import annotations

import hashlib
import re
import sqlite3
import time
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "property" / "listings.db"
STATUSES = ["new", "contacted", "replied", "viewing", "won", "lost", "ignore"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings(
  id TEXT PRIMARY KEY, dup_key TEXT, source TEXT, url TEXT, title TEXT, purpose TEXT, ptype TEXT, area TEXT,
  price REAL, price_prev REAL, size_sqft REAL, beds INT, baths INT, phone TEXT, poster TEXT, is_owner INT,
  image TEXT, first_seen REAL, last_seen REAL, status TEXT DEFAULT 'new', notes TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS rent_obs(url TEXT PRIMARY KEY, source TEXT, area TEXT, rent REAL, size_sqft REAL, seen REAL);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS crawled(url TEXT PRIMARY KEY, lastmod TEXT, seen REAL);
CREATE TABLE IF NOT EXISTS web_queries(q TEXT, ts REAL, month TEXT, results INT);
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE, name TEXT, phone TEXT, note TEXT, pw_hash TEXT, salt TEXT,
  role TEXT DEFAULT 'member', status TEXT DEFAULT 'pending', created REAL, decided_by TEXT, decided_at REAL);
CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY, user_id INT, created REAL, expires REAL);
CREATE TABLE IF NOT EXISTS attempts(k TEXT, ts REAL);
CREATE INDEX IF NOT EXISTS ix_area ON listings(area, purpose);
CREATE INDEX IF NOT EXISTS ix_dup ON listings(dup_key);
"""


def connect(path: Path | str = DB) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path), check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    have = {r[1] for r in con.execute("PRAGMA table_info(listings)")}
    for col in ("snippet", "found_via", "evidence", "data_flags"):  # added later; older databases get them on open
        if col not in have:
            con.execute(f"ALTER TABLE listings ADD COLUMN {col} TEXT DEFAULT ''")
    return con


def data_flags(r: dict) -> str:
    """Odd or missing details to clear with the seller. Listings are never dropped for these:
    sellers often hide the real price or size so that interested buyers have to call."""
    f, price, size = [], r.get("price"), r.get("size_sqft")
    if not price:
        f.append("price missing - ask seller")
    elif price < 500_000:
        f.append(f"price {price:,.0f} BDT looks absurd - clear with seller")
    elif price > 5_000_000_000:
        f.append(f"price {price:,.0f} BDT looks absurd - clear with seller")
    if not size:
        f.append("size missing - ask seller")
    else:
        lo, hi = (200, 20000) if (r.get("ptype") or "apartment") in ("apartment", "house") else (360, 400000)
        if not lo <= size <= hi:
            f.append(f"size {size:,.0f} sqft looks absurd - clear with seller")
    if price and size and 200 <= size and price / size < 1000:
        f.append(f"price per sqft {price / size:,.0f} BDT is implausibly low - clear with seller")
    return "; ".join(f)


def dup_key(r: dict) -> str:
    """Same flat on two sites = same area+purpose+beds+size(±5)+price(±3%). Phone wins if known."""
    if r.get("phone"):
        return "p:" + r["phone"] + (r.get("area") or "") + str(r.get("beds") or "")
    if not (r.get("price") and r.get("size_sqft")):
        return ""
    return "f:%s|%s|%s|%d|%d" % (r.get("area"), r.get("purpose"), r.get("beds"), round(r["size_sqft"] / 5),
                                  round(__import__("math").log(r["price"]) / 0.03))


def upsert(con: sqlite3.Connection, r: dict) -> bool:
    """Returns True if the listing is new."""
    now = time.time()
    if r.get("price"):
        r["price"] = float(round(r["price"]))
    lid = hashlib.sha1((r["source"] + "|" + r["url"].split("?")[0]).encode()).hexdigest()[:16]
    old = con.execute("SELECT price FROM listings WHERE id=?", (lid,)).fetchone()
    dk = dup_key(r)
    if old is None:
        con.execute(
            "INSERT INTO listings(id,dup_key,source,url,title,purpose,ptype,area,price,size_sqft,beds,baths,phone,poster,is_owner,image,"
            "first_seen,last_seen,snippet,found_via,evidence,data_flags) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (lid, dk, r["source"], r["url"], r["title"], r.get("purpose"), r.get("ptype"), r.get("area"), r.get("price"),
             r.get("size_sqft"), r.get("beds"), r.get("baths"), r.get("phone", ""), r.get("poster", ""), r.get("is_owner"),
             r.get("image", ""), now, now, r.get("snippet", ""), r.get("found_via", ""), r.get("evidence", "listing page"), data_flags(r)))
        return True
    prev = old["price"] if r.get("price") and old["price"] and r["price"] != old["price"] else None
    con.execute("UPDATE listings SET data_flags=?, last_seen=?, dup_key=?, price=COALESCE(?,price), price_prev=COALESCE(?,price_prev),"
                " phone=CASE WHEN ?!='' THEN ? ELSE phone END, poster=CASE WHEN ?!='' THEN ? ELSE poster END WHERE id=?",
                (data_flags(r), now, dk, r.get("price"), prev, r.get("phone", ""), r.get("phone", ""), r.get("poster", ""), r.get("poster", ""), lid))
    return False


def add_rent(con, r: dict) -> None:
    """Rent ads are stored only as price-per-sqft evidence for ROI. They are never listed or exported."""
    if re.search(r"office|shop|room|sublet|commercial|space|hostel|mess", (r.get("title") or "").lower()):
        return  # only whole homes say anything about residential rent
    if r.get("price") and r.get("size_sqft") and r.get("ptype") in (None, "apartment", "house"):
        con.execute("INSERT OR REPLACE INTO rent_obs(url,source,area,rent,size_sqft,seen) VALUES(?,?,?,?,?,?)",
                    (r["url"].split("?")[0], r["source"], r.get("area"), r["price"], r["size_sqft"], time.time()))


def query(con, area="", ptype="", q="", max_price=None, min_roi=None, owner_only=False,
          status="", sort="roi", limit=500) -> list[dict]:
    from . import roi
    w, a = ["purpose='sale'"], []
    for col, v in (("area", area), ("ptype", ptype), ("status", status)):
        if v:
            w.append(f"{col}=?")
            a.append(v)
    if q:
        w.append("(title LIKE ? OR poster LIKE ?)")
        a += [f"%{q}%"] * 2
    if max_price:
        w.append("price<=?"); a.append(max_price)
    if owner_only:
        w.append("is_owner=1")
    rows = [dict(r) for r in con.execute(f"SELECT * FROM listings WHERE {' AND '.join(w)} LIMIT 5000", a)]
    counts = {r[0]: r[1] for r in con.execute("SELECT dup_key, COUNT(DISTINCT source) FROM listings WHERE dup_key!='' GROUP BY dup_key")}
    assume, bench = roi.load(con), roi.benchmarks(con)
    for r in rows:
        r.update(roi.project(r, assume, bench))
        r["sites"] = counts.get(r["dup_key"], 1)
        r["ppsf"] = round(r["price"] / r["size_sqft"]) if r["price"] and r["size_sqft"] else None
        r["dropped"] = bool(r["price_prev"] and r["price"] and r["price"] < r["price_prev"])
    if min_roi:
        rows = [r for r in rows if (r["total"] or 0) >= min_roi]
    key = {"roi": lambda r: -(r["total"] or -1), "yield": lambda r: -(r["gross"] or -1), "cheap": lambda r: r["price"] or 1e18,
           "drop": lambda r: -((r["price_prev"] or 0) - (r["price"] or 0)), "new": lambda r: -r["first_seen"]}.get(sort, lambda r: -(r["total"] or -1))
    rows.sort(key=key)
    return rows[:limit]


def set_lead(con, lid: str, status: str | None, notes: str | None) -> None:
    if status in STATUSES:
        con.execute("UPDATE listings SET status=? WHERE id=?", (status, lid))
    if notes is not None:
        con.execute("UPDATE listings SET notes=? WHERE id=?", (notes[:2000], lid))
    con.commit()


def stats(con) -> list[dict]:
    """Per area, sale only: listings, average price per sqft and average gross yield."""
    from . import roi
    assume, bench = roi.load(con), roi.benchmarks(con)
    by: dict[str, list[dict]] = {}
    for r in con.execute("SELECT * FROM listings WHERE purpose='sale' AND price>0"):
        r = dict(r)
        r.update(roi.project(r, assume, bench))
        by.setdefault(r["area"], []).append(r)
    out = []
    for area, rs in sorted(by.items()):
        pp = [r["price"] / r["size_sqft"] for r in rs if r["size_sqft"]]
        gy = [r["gross"] for r in rs if r["gross"]]
        out.append({"area": area, "n": len(rs), "avg_ppsf": round(sum(pp) / len(pp)) if pp else None,
                    "avg_yield": round(sum(gy) / len(gy), 1) if gy else None, "owners": sum(1 for r in rs if r["is_owner"] == 1),
                    "rent_basis": f"measured ({bench[area][1]} ads)" if area in bench else "assumed"})
    return out
