"""One-file members-only page for ordinary web hosting (cPanel).

A static page has no server, so access is enforced by encryption: the listings are AES-256-GCM encrypted inside the HTML and
each member's own email and password unlock a private copy of the key (PBKDF2-SHA256, 600,000 rounds). Without a valid login the
file contains no readable listings, phone numbers or URLs. Admins add, reset and remove members in the page and download the
updated file to upload again.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import time
import zlib
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from . import scrape, store, websearch

ITER = 600_000
TEMPLATE = Path(__file__).parent / "static" / "vault.html"
STATIC = Path(__file__).parent / "static"
TYPES = {"apartment": "apt", "house": "house", "land": "land", "commercial": "commercial"}


def b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


def member_id(email: str) -> str:
    return hashlib.sha256(("pf-id:" + email.strip().lower()).encode()).hexdigest()


def wrap(info: dict, password: str) -> dict:
    """Lock a member's key material under their own password."""
    salt, iv = os.urandom(16), os.urandom(12)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITER, 32)
    ct = AESGCM(key).encrypt(iv, json.dumps(info).encode(), None)
    return {"id": member_id(info["email"]), "salt": b64(salt), "iv": b64(iv), "ct": b64(ct)}


def rows_from(con) -> tuple[list, str]:
    names = {k: v["name"] for k, v in scrape.SOURCES.items()} | {q["id"]: q["name"] for q in websearch.QUERIES}
    rows = store.query(con, sort="new", limit=10000)
    out = []
    for r in sorted(rows, key=lambda r: (r["area"], r["source"], r["title"])):
        out.append([names.get(r["source"], r["source"]), r["title"], r["area"], TYPES.get(r["ptype"], "apt"), r["price"], r["size_sqft"],
                    r["beds"], r["baths"], r["phone"] or "", r["poster"] or "", r["is_owner"],
                    "other sites" if r["sites"] > 1 else "", r["url"], r.get("data_flags") or "",
                    r.get("evidence") or "listing page", (r.get("snippet") or "")[:220]])
    seen = max((r["first_seen"] for r in rows), default=time.time())
    return out, time.strftime("%-d %B %Y", time.gmtime(seen))


def build(con, out: Path, email: str, name: str, password: str) -> dict:
    if len(password) < 12:
        raise ValueError("Use an admin password of at least 12 characters: it is the only thing protecting the data.")
    rows, stamp = rows_from(con)
    k, ka = os.urandom(32), os.urandom(32)
    iv, div = os.urandom(12), os.urandom(12)
    payload = zlib.compress(json.dumps({"rows": rows, "stamp": stamp}, ensure_ascii=False, separators=(",", ":")).encode(), 9)
    directory = [{"email": email.lower(), "name": name, "role": "admin", "added": time.strftime("%Y-%m-%d")}]
    vault = {"v": 1, "iter": ITER, "iv": b64(iv), "data": b64(AESGCM(k).encrypt(iv, payload, None)),
             "div": b64(div), "dir": b64(AESGCM(ka).encrypt(div, json.dumps(directory).encode(), None)),
             "members": [wrap({"email": email.lower(), "name": name, "role": "admin", "k": b64(k), "ka": b64(ka)}, password)]}
    html = TEMPLATE.read_text(encoding="utf-8")
    for key, f in (("__LOGO_NAVY__", "logo-navy.png"),):
        html = html.replace(key, "data:image/png;base64," + b64((STATIC / f).read_bytes()))
    html = html.replace("__VAULT__", json.dumps(vault, separators=(",", ":")))
    out.write_text(html, encoding="utf-8")
    return {"listings": len(rows), "bytes": len(html), "stamp": stamp}
