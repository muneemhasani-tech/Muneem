"""SQLite store: dedupes across sites, tracks price changes and lead status."""
from __future__ import annotations

import hashlib
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
CREATE INDEX IF NOT EXISTS ix_area ON listings(area, purpose);
CREATE INDEX IF NOT EXISTS ix_dup ON listings(dup_key);
"""


def connect(path: Path | str = DB) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path), check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


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
    lid = hashlib.sha1((r["source"] + "|" + r["url"].split("?")[0]).encode()).hexdigest()[:16]
    old = con.execute("SELECT price FROM listings WHERE id=?", (lid,)).fetchone()
    dk = dup_key(r)
    if old is None:
        con.execute(
            "INSERT INTO listings(id,dup_key,source,url,title,purpose,ptype,area,price,size_sqft,beds,baths,phone,poster,is_owner,image,first_seen,last_seen)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (lid, dk, r["source"], r["url"], r["title"], r.get("purpose"), r.get("ptype"), r.get("area"), r.get("price"),
             r.get("size_sqft"), r.get("beds"), r.get("baths"), r.get("phone", ""), r.get("poster", ""), r.get("is_owner"),
             r.get("image", ""), now, now))
        return True
    prev = old["price"] if r.get("price") and old["price"] and r["price"] != old["price"] else None
    con.execute("UPDATE listings SET last_seen=?, dup_key=?, price=COALESCE(?,price), price_prev=COALESCE(?,price_prev),"
                " phone=CASE WHEN ?!='' THEN ? ELSE phone END, poster=CASE WHEN ?!='' THEN ? ELSE poster END WHERE id=?",
                (now, dk, r.get("price"), prev, r.get("phone", ""), r.get("phone", ""), r.get("poster", ""), r.get("poster", ""), lid))
    return False


def query(con, area="", purpose="", ptype="", q="", min_price=None, max_price=None, owner_only=False,
          status="", sort="new", limit=500) -> list[dict]:
    w, a = ["1=1"], []
    for col, v in (("area", area), ("purpose", purpose), ("ptype", ptype), ("status", status)):
        if v:
            w.append(f"{col}=?")
            a.append(v)
    if q:
        w.append("(title LIKE ? OR poster LIKE ?)")
        a += [f"%{q}%"] * 2
    if min_price:
        w.append("price>=?"); a.append(min_price)
    if max_price:
        w.append("price<=?"); a.append(max_price)
    if owner_only:
        w.append("is_owner=1")
    order = {"new": "first_seen DESC", "cheap": "price ASC", "dear": "price DESC", "drop": "(price_prev-price) DESC"}.get(sort, "first_seen DESC")
    rows = [dict(r) for r in con.execute(f"SELECT * FROM listings WHERE {' AND '.join(w)} ORDER BY {order} LIMIT ?", a + [limit])]
    counts = {r[0]: r[1] for r in con.execute("SELECT dup_key, COUNT(DISTINCT source) FROM listings WHERE dup_key!='' GROUP BY dup_key")}
    for r in rows:
        r["sites"] = counts.get(r["dup_key"], 1)
        r["ppsf"] = round(r["price"] / r["size_sqft"]) if r["price"] and r["size_sqft"] and r["purpose"] == "sale" else None
        r["dropped"] = bool(r["price_prev"] and r["price"] and r["price"] < r["price_prev"])
    return rows


def set_lead(con, lid: str, status: str | None, notes: str | None) -> None:
    if status in STATUSES:
        con.execute("UPDATE listings SET status=? WHERE id=?", (status, lid))
    if notes is not None:
        con.execute("UPDATE listings SET notes=? WHERE id=?", (notes[:2000], lid))
    con.commit()


def stats(con) -> list[dict]:
    """Median-ish market view: avg price per sqft (sale) and avg monthly rent, per area."""
    return [dict(r) for r in con.execute(
        "SELECT area, purpose, COUNT(*) n, ROUND(AVG(price)) avg_price,"
        " ROUND(AVG(CASE WHEN purpose='sale' AND size_sqft>0 THEN price/size_sqft END)) avg_ppsf,"
        " SUM(is_owner=1) owners FROM listings WHERE price>0 GROUP BY area, purpose ORDER BY area")]
