"""Members-only access. People request access; an admin approves them. Nothing under /api is served without an approved session."""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import sqlite3
import time

ITER = 260_000
SESSION_DAYS = 14
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_FAILS = 5          # wrong passwords per email in WINDOW
MAX_FAILS_IP = 25      # wrong passwords per address in WINDOW
WINDOW = 15 * 60


class AuthError(Exception):
    """Message is safe to show the person."""


def _hash(pw: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), salt, ITER).hex()


def _tok(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _clean_email(email: str) -> str:
    email = (email or "").strip().lower()
    if not EMAIL.match(email) or len(email) > 200:
        raise AuthError("Enter a valid email address.")
    return email


def _check_pw(pw: str) -> None:
    if len(pw or "") < 10:
        raise AuthError("Use a password of at least 10 characters.")


def create_user(con: sqlite3.Connection, email: str, name: str, pw: str, phone: str = "", note: str = "",
                role: str = "member", status: str = "pending", by: str = "") -> int:
    email = _clean_email(email)
    _check_pw(pw)
    name = (name or "").strip()[:100]
    if not name:
        raise AuthError("Enter your name.")
    if con.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
        raise AuthError("That email already has an account or a pending request.")
    salt = secrets.token_bytes(16)
    now = time.time()
    cur = con.execute(
        "INSERT INTO users(email,name,phone,note,pw_hash,salt,role,status,created,decided_by,decided_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (email, name, (phone or "").strip()[:30], (note or "").strip()[:300], _hash(pw, salt), salt.hex(), role, status, now,
         by, now if status == "approved" else None))
    con.commit()
    return cur.lastrowid


def request_access(con, email, name, pw, phone="", note="") -> None:
    if not (phone or "").strip():
        raise AuthError("Enter a phone number so MRA can verify you.")
    create_user(con, email, name, pw, phone, note)


def _blocked(con, key: str, limit: int) -> bool:
    n = con.execute("SELECT COUNT(*) FROM attempts WHERE k=? AND ts>?", (key, time.time() - WINDOW)).fetchone()[0]
    return n >= limit


def login(con, email: str, pw: str, ip: str = "") -> tuple[str, dict]:
    """Returns (session token, user). Wrong details and unknown emails give the same message."""
    email = (email or "").strip().lower()
    if _blocked(con, "e:" + email, MAX_FAILS) or _blocked(con, "i:" + ip, MAX_FAILS_IP):
        raise AuthError("Too many attempts. Wait 15 minutes and try again.")
    row = con.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    salt = bytes.fromhex(row["salt"]) if row else b"\0" * 16
    ok = hmac.compare_digest(_hash(pw or "", salt), row["pw_hash"] if row else "0" * 64) and row is not None
    if not ok:
        con.executemany("INSERT INTO attempts(k,ts) VALUES(?,?)", [("e:" + email, time.time()), ("i:" + ip, time.time())])
        con.commit()
        raise AuthError("Email or password is not right.")
    if row["status"] == "pending":
        raise AuthError("Your request is waiting for approval from MRA.")
    if row["status"] != "approved":
        raise AuthError("Access was not granted for this account. Contact MRA.")
    token = secrets.token_urlsafe(32)
    now = time.time()
    con.execute("INSERT INTO sessions(token_hash,user_id,created,expires) VALUES(?,?,?,?)",
                (_tok(token), row["id"], now, now + SESSION_DAYS * 86400))
    con.execute("DELETE FROM sessions WHERE expires<?", (now,))
    con.commit()
    return token, public(row)


def user_for(con, token: str | None) -> dict | None:
    if not token:
        return None
    row = con.execute("SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires>? AND u.status='approved'",
                      (_tok(token), time.time())).fetchone()
    return public(row) if row else None


def logout(con, token: str | None) -> None:
    if token:
        con.execute("DELETE FROM sessions WHERE token_hash=?", (_tok(token),))
        con.commit()


def public(row) -> dict:
    return {k: row[k] for k in ("id", "email", "name", "phone", "note", "role", "status")}


def list_users(con) -> list[dict]:
    return [{**public(r), "created": r["created"], "decided_by": r["decided_by"], "decided_at": r["decided_at"]}
            for r in con.execute("SELECT * FROM users ORDER BY CASE status WHEN 'pending' THEN 0 WHEN 'approved' THEN 1 ELSE 2 END, created DESC")]


def set_status(con, user_id: int, status: str, by: str) -> None:
    """approved / rejected / revoked. Revoking ends every session of that person at once."""
    if status not in ("approved", "rejected", "revoked"):
        raise AuthError("Unknown status.")
    row = con.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not row:
        raise AuthError("No such person.")
    if row["role"] == "admin" and status != "approved":
        raise AuthError("An admin cannot be removed here.")
    con.execute("UPDATE users SET status=?, decided_by=?, decided_at=? WHERE id=?", (status, by, time.time(), user_id))
    if status != "approved":
        con.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
    con.commit()


def find(con, email: str) -> dict | None:
    row = con.execute("SELECT * FROM users WHERE email=?", ((email or "").strip().lower(),)).fetchone()
    return public(row) if row else None
