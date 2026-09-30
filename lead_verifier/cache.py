"""SQLite lookup cache (stdlib sqlite3). One file, two tables: lookups and quota."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS lookups (
  kind       TEXT NOT NULL,
  key        TEXT NOT NULL,
  result     TEXT NOT NULL,
  checked_at TEXT NOT NULL,
  PRIMARY KEY (kind, key)
);
CREATE TABLE IF NOT EXISTS quota (
  provider TEXT NOT NULL,
  day      TEXT NOT NULL,
  used     INTEGER NOT NULL,
  PRIMARY KEY (provider, day)
);
"""


class Cache:
    def __init__(self, path: str | Path = "cache.db") -> None:
        self.path = str(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def get(self, kind: str, key: str, ttl_days: float) -> Any | None:
        """Cached JSON value, or None if missing or older than ttl_days."""
        row = self.conn.execute(
            "SELECT result, checked_at FROM lookups WHERE kind=? AND key=?", (kind, key)
        ).fetchone()
        if not row:
            return None
        checked = datetime.fromisoformat(row[1])
        if datetime.now(timezone.utc) - checked > timedelta(days=ttl_days):
            return None
        return json.loads(row[0])

    def set(self, kind: str, key: str, result: Any) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO lookups (kind, key, result, checked_at) VALUES (?,?,?,?)",
            (kind, key, json.dumps(result), datetime.now(timezone.utc).isoformat()),
        )
        self.conn.commit()

    def clear(self, kind: str | None = None) -> int:
        cur = self.conn.execute(
            "DELETE FROM lookups" + (" WHERE kind=?" if kind else ""), (kind,) if kind else ()
        )
        self.conn.commit()
        return cur.rowcount

    def close(self) -> None:
        self.conn.close()
