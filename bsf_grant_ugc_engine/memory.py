#!/usr/bin/env python3
"""
memory.py — Cross-platform (Mac/Linux/Windows) safe JSON read/write API with 5s file locking.
Prevents race conditions between local schedulers and CLI agents.
"""
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LOCK_TIMEOUT = 5.0

FILES = {
    "research": BASE_DIR / "research_data.json",
    "search_log": BASE_DIR / "search_log.json",
    "task_log": BASE_DIR / "task_log.json",
    "daily_log": BASE_DIR / "daily_log.json",
}

DEFAULT_SCHEMAS = {
    "research": {
        "grants": [],
        "partners": [],
        "seen_urls": []
    },
    "search_log": {
        "rotation_index": 0,
        "queries": {
            "grant_water_bd": {"page": 1, "last_run": None},
            "grant_climate_ngo": {"page": 1, "last_run": None},
            "grant_bioeconomy": {"page": 1, "last_run": None},
            "partner_water_lab_bd": {"page": 1, "last_run": None},
            "partner_cosmo_chemist_bd": {"page": 1, "last_run": None},
            "partner_petfood_mill_bd": {"page": 1, "last_run": None}
        }
    },
    "task_log": {"entries": []},
    "daily_log": {"runs": []}
}


class FileLock:
    """Atomic directory/file lock compatible with macOS, Linux, and Windows."""
    def __init__(self, target_path: Path, timeout: float = LOCK_TIMEOUT):
        self.lock_path = target_path.with_suffix(target_path.suffix + ".lock")
        self.timeout = timeout
        self.fd = None

    def __enter__(self):
        start = time.time()
        while True:
            try:
                self.fd = os.open(str(self.lock_path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
                os.write(self.fd, f"{os.getpid()}".encode("utf-8"))
                return self
            except FileExistsError:
                # Clear stale locks older than 30 seconds
                try:
                    if time.time() - os.path.getmtime(self.lock_path) > 30:
                        os.remove(self.lock_path)
                        continue
                except OSError:
                    pass
                if (time.time() - start) >= self.timeout:
                    raise TimeoutError(f"Lock timeout ({self.timeout}s) exceeded for {self.lock_path.name}")
                time.sleep(0.1)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
        try:
            if self.lock_path.exists():
                os.remove(self.lock_path)
        except OSError:
            pass


def init_db():
    """Initializes all JSON state files if they do not exist."""
    for key, path in FILES.items():
        if not path.exists():
            with FileLock(path):
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(DEFAULT_SCHEMAS[key], f, indent=2, ensure_ascii=False)


def read_json(key: str) -> dict:
    init_db()
    path = FILES[key]
    with FileLock(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)


def write_json(key: str, data: dict):
    init_db()
    path = FILES[key]
    temp_path = path.with_suffix(".tmp")
    with FileLock(path):
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(temp_path, path)


def log_task(message: str, agent: str = "SYSTEM"):
    data = read_json("task_log")
    data["entries"].append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": agent,
        "message": message
    })
    write_json("task_log", data)


def add_lead(category: str, lead: dict) -> bool:
    """Adds a grant or partner lead if URL is not already in seen_urls."""
    data = read_json("research")
    url = lead.get("url", "").strip().lower()
    if url and url in data["seen_urls"]:
        return False
    if url:
        data["seen_urls"].append(url)
    lead["discovered_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if category == "grant":
        data["grants"].append(lead)
    else:
        data["partners"].append(lead)
    write_json("research", data)
    return True


if __name__ == "__main__":
    init_db()
    if len(sys.argv) >= 3 and sys.argv[1] == "log":
        msg = " ".join(sys.argv[2:])
        log_task(msg, agent="CLI")
        print(f"[OK] Logged to task_log.json: {msg}")
    elif len(sys.argv) == 2 and sys.argv[1] == "status":
        res = read_json("research")
        slog = read_json("search_log")
        print(f"Grants stored: {len(res['grants'])} | Partners stored: {len(res['partners'])} | Rotation Index: {slog['rotation_index']}")
    else:
        print("Usage: python3 memory.py [init | status | log '<message>']")
