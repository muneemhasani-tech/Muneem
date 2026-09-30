"""Shared entry points used by the CLI and the web UI: grade leads, describe one lead as JSON."""
from __future__ import annotations

import asyncio

import httpx

from .cache import Cache
from .config import secrets as load_secrets
from .models import Lead
from .pipeline import Pipeline, RunSummary
from .quota import Quota


def grade_leads(leads: list[Lead], cfg: dict, offline_only: bool = False) -> RunSummary:
    """Blocking. Opens its own cache connection, so it is safe to call from any thread."""
    cache = Cache(cfg["cache"]["path"])
    try:
        quota = Quota(cache, cfg["providers"], cfg["timezone"])

        async def go() -> RunSummary:
            async with httpx.AsyncClient(timeout=httpx.Timeout(20.0)) as client:
                p = Pipeline(cfg, cache, quota, client, load_secrets(), offline_only=offline_only)
                return await p.run(leads)

        return asyncio.run(go())
    finally:
        cache.close()


def check_one(phone: str, email: str, website: str, cfg: dict, offline_only: bool = False) -> tuple[Lead, RunSummary]:
    lead = Lead(row_num=1, cells=[], phone_raw=phone.strip(), email_raw=email.strip(), website_raw=website.strip())
    return lead, grade_leads([lead], cfg, offline_only)


def keys_configured() -> dict[str, bool]:
    s = load_secrets()
    return {
        "email_check": bool(s["qev_api_key"]),
        "email_fallback": bool(s["verifalia_username"] and s["verifalia_password"]),
        "webrisk": bool(s["webrisk_api_key"]),
        "urlhaus": bool(s["urlhaus_auth_key"]),
    }


def lead_json(l: Lead) -> dict:
    d = l.domain
    return {
        "row": l.row_num, "name": l.name, "grade": l.grade, "reasons": l.reasons,
        "phone": {"input": l.phone_raw, "e164": l.phone.e164, "valid": l.phone.valid,
                  "type": l.phone.type, "carrier": l.phone.carrier, "reason": l.phone.reason},
        "email": {"input": l.email_raw, "status": l.email_result.status, "reason": l.email_result.reason,
                  "provider": l.email_result.provider, "deferred": l.email_result.deferred},
        "domain": {"name": d.domain, "flagged": d.flagged, "sources": d.sources,
                   "age_days": d.age_days, "checked": d.checked},
        "duplicate_of": l.duplicate_of, "checked_at": l.checked_at,
    }
