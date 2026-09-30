"""Domain checks: extraction, reputation (Web Risk + URLhaus, concurrent), age (RDAP/WHOIS)."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

import httpx
import tldextract

from ..cache import Cache
from ..http import request
from ..models import DomainResult
from ..quota import Quota

log = logging.getLogger(__name__)

# Bundled public-suffix snapshot: no network fetch at startup.
_extract = tldextract.TLDExtract(suffix_list_urls=())

WEBRISK = "webrisk"
URLHAUS = "urlhaus"
RDAP = "rdap"


def extract_domain(website_or_email: str) -> str | None:
    """Registrable domain only ('https://www.shop.example.com.bd/x' -> 'example.com.bd')."""
    s = (website_or_email or "").strip().lower()
    if not s:
        return None
    if "@" in s:
        s = s.rsplit("@", 1)[1]
    ext = _extract(s)
    new = hasattr(type(ext), "top_domain_under_public_suffix")
    return (ext.top_domain_under_public_suffix if new else ext.registered_domain) or None


@dataclass
class Outcome:
    flagged: bool | None  # None = unknown
    deferred: bool = False


# ---- age backends -----------------------------------------------------------------------

_bootstrapped = False
_rdap_broken = False  # bootstrap failed once (offline / IANA unreachable): don't retry per domain


def lookup_creation_date(domain: str) -> datetime | None:
    """Blocking. RDAP via whoisit; python-whois fallback (.bd has no RDAP). None on any failure."""
    global _bootstrapped, _rdap_broken
    if not _rdap_broken:
        try:
            import whoisit

            if not _bootstrapped:
                try:
                    whoisit.bootstrap()
                except Exception:  # noqa: BLE001
                    _rdap_broken = True
                    raise
                _bootstrapped = True
            d = whoisit.domain(domain).get("registration_date")
            if isinstance(d, datetime):
                return d
        except Exception as exc:  # noqa: BLE001  (unsupported TLD such as .bd, network, parse ...)
            log.debug("rdap failed for %s: %s", domain, type(exc).__name__)
    try:
        import whois

        d = whois.whois(domain).creation_date
        d = min(d) if isinstance(d, list) and d else d
        return d if isinstance(d, datetime) else None
    except Exception as exc:  # noqa: BLE001
        log.debug("whois failed for %s: %s", domain, type(exc).__name__)
        return None


def age_days(created: datetime, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return max(0, (now - created).days)


class DomainChecker:
    WEBRISK_URL = "https://webrisk.googleapis.com/v1/uris:search"
    URLHAUS_URL = "https://urlhaus-api.abuse.ch/v1/host/"

    def __init__(self, client: httpx.AsyncClient, cache: Cache, quota: Quota, cfg: dict, secrets: dict,
                 age_backend: Callable[[str], datetime | None] = lookup_creation_date) -> None:
        self.client, self.cache, self.quota, self.s = client, cache, quota, secrets
        self.retry = cfg["retry"]
        self.ttl = cfg["cache"]["ttl_days"]
        self.require_online = cfg["domain"]["urlhaus_require_online"]
        self.age_backend = age_backend
        self.sems = {p: asyncio.Semaphore(int(cfg["providers"].get(p, {}).get("concurrency", 1)))
                     for p in (WEBRISK, URLHAUS, RDAP)}

    # -- reputation -----------------------------------------------------------------

    async def check_reputation(self, domain: str) -> DomainResult:
        """Web Risk and URLhaus concurrently. Flagged if either lists it. flagged=False only
        when both answered clean; otherwise None (unknown) unless one already flagged."""
        wr, uh = await asyncio.gather(self._webrisk(domain), self._urlhaus(domain))
        sources = [n for n, o in ((WEBRISK, wr), (URLHAUS, uh)) if o.flagged]
        if sources:
            flagged: bool | None = True
        elif wr.flagged is False and uh.flagged is False:
            flagged = False
        else:
            flagged = None
        return DomainResult(domain=domain, flagged=flagged, sources=sources,
                            deferred=wr.deferred or uh.deferred)

    async def _guarded(self, provider: str, domain: str, ready: bool, call) -> Outcome:
        key = f"{provider}|{domain}"
        cached = self.cache.get("reputation", key, self.ttl["reputation"])
        if cached is not None:
            return Outcome(cached["flagged"])
        if not ready:
            return Outcome(None)
        if not self.quota.reserve(provider):
            return Outcome(None, deferred=True)
        try:
            async with self.sems[provider]:
                flagged = await call()
        except Exception:  # noqa: BLE001  never leave a credit spent for a call that died
            self.quota.refund(provider)
            raise
        if flagged == "quota":
            self.quota.exhaust(provider)
            return Outcome(None, deferred=True)
        if flagged is None:
            self.quota.refund(provider)
            return Outcome(None)
        self.cache.set("reputation", key, {"flagged": flagged})
        return Outcome(flagged)

    async def _webrisk(self, domain: str) -> Outcome:
        async def call():
            r = await request(
                self.client, "GET", self.WEBRISK_URL, self.retry,
                params=[("threatTypes", t) for t in ("MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE")]
                + [("uri", f"http://{domain}/"), ("key", self.s["webrisk_api_key"])],
            )
            if r is None or r.status_code >= 500:
                return None
            if r.status_code == 429:
                return "quota"
            if r.status_code != 200:
                log.warning("Web Risk HTTP %s (key invalid or API not enabled?)", r.status_code)
                return None
            try:
                return "threat" in r.json()  # clean domain -> empty {}
            except ValueError:
                return None

        return await self._guarded(WEBRISK, domain, bool(self.s["webrisk_api_key"]), call)

    async def _urlhaus(self, domain: str) -> Outcome:
        async def call():
            r = await request(self.client, "POST", self.URLHAUS_URL, self.retry, data={"host": domain},
                              headers={"Auth-Key": self.s["urlhaus_auth_key"]})
            if r is None or r.status_code >= 500:
                return None
            if r.status_code == 429:
                return "quota"
            if r.status_code != 200:
                log.warning("URLhaus HTTP %s (Auth-Key invalid?)", r.status_code)
                return None
            try:
                data = r.json()
            except ValueError:
                return None
            status = data.get("query_status")
            if status == "no_results":
                return False
            if status != "ok":
                return None
            field = "urls_online" if self.require_online else "url_count"
            try:
                return int(data.get(field) or 0) > 0
            except (TypeError, ValueError):
                return None

        return await self._guarded(URLHAUS, domain, bool(self.s["urlhaus_auth_key"]), call)

    # -- age ------------------------------------------------------------------------

    async def check_age(self, domain: str) -> int | None:
        """Days since creation. Any failure -> None; never raises. Cache holds the creation
        DATE so the age stays correct for the whole 180-day TTL."""
        try:
            cached = self.cache.get("age", domain, self.ttl["age"])
            if cached:
                return age_days(datetime.fromisoformat(cached["created"]))
            if not self.quota.reserve(RDAP):
                return None
            try:
                async with self.sems[RDAP]:
                    created = await asyncio.to_thread(self.age_backend, domain)
            except Exception:  # noqa: BLE001
                self.quota.refund(RDAP)
                raise
            if created is None:
                self.quota.refund(RDAP)
                return None
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            self.cache.set("age", domain, {"created": created.isoformat()})
            return age_days(created)
        except Exception as exc:  # noqa: BLE001
            log.debug("age check failed for %s: %s", domain, type(exc).__name__)
            return None
