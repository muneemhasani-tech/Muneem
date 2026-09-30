"""Config loading: built-in defaults <- config.yaml <- environment (.env for secrets)."""
from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

DEFAULTS: dict[str, Any] = {
    "region": "BD",
    "timezone": "Asia/Dhaka",
    "providers": {
        "quickemailverification": {"daily_limit": 100, "concurrency": 2, "reset_tz": "Asia/Dhaka"},
        "verifalia": {"daily_limit": 25, "concurrency": 1, "reset_tz": "UTC"},
        "webrisk": {"daily_limit": 3000, "concurrency": 4, "reset_tz": "Asia/Dhaka"},
        "urlhaus": {"daily_limit": 5000, "concurrency": 4, "reset_tz": "Asia/Dhaka"},
        "rdap": {"daily_limit": 5000, "concurrency": 2, "reset_tz": "Asia/Dhaka"},
    },
    "whatsapp": {"enabled": False},
    "retry": {"attempts": 3, "backoff_seconds": [2, 8, 30]},
    "cache": {
        "path": "cache.db",
        "ttl_days": {"email": 30, "reputation": 7, "age": 180, "mx": 7, "whatsapp": 30},
    },
    "scoring": {"min_domain_age_days": 90},
    "domain": {
        "urlhaus_require_online": True,
        "skip_domains": [
            "gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com",
            "facebook.com", "fb.com", "fb.me", "instagram.com", "linkedin.com",
            "youtube.com", "youtu.be", "wa.me", "whatsapp.com", "t.me",
            "tiktok.com", "x.com", "twitter.com",
        ],
    },
}


def _merge(base: dict, over: dict) -> dict:
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _merge(base[k], v)
        else:
            base[k] = v
    return base


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    load_dotenv()
    cfg = copy.deepcopy(DEFAULTS)
    p = Path(path) if path else Path("config.yaml")
    if p.exists():
        _merge(cfg, yaml.safe_load(p.read_text(encoding="utf-8")) or {})
    elif path:
        raise FileNotFoundError(f"config file not found: {p}")
    return cfg


def secrets() -> dict[str, str]:
    """API credentials from the environment. Empty string = not configured."""
    g = lambda k: os.environ.get(k, "").strip()  # noqa: E731
    return {
        "qev_api_key": g("QEV_API_KEY"),
        "verifalia_username": g("VERIFALIA_USERNAME"),
        "verifalia_password": g("VERIFALIA_PASSWORD"),
        "webrisk_api_key": g("GOOGLE_WEBRISK_API_KEY"),
        "urlhaus_auth_key": g("URLHAUS_AUTH_KEY"),
    }
