"""Email checks: offline (syntax, disposable, MX) then API (QuickEmailVerification -> Verifalia)."""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Awaitable, Callable

import httpx
from disposable_email_domains import blocklist

from ..cache import Cache
from ..http import request
from ..models import EmailResult
from ..quota import Quota
from ..util import mask_email

log = logging.getLogger(__name__)

QEV = "quickemailverification"
VERIFALIA = "verifalia"

_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_LOCAL = re.compile(r"^[a-z0-9!#$%&'*+/=?^_`{|}~.-]+$")


def normalise_email(raw: str) -> str:
    return (raw or "").strip().strip("<>").strip().lower()


def valid_syntax(email: str) -> bool:
    if email.count("@") != 1 or len(email) > 254:
        return False
    local, dom = email.split("@")
    if not local or len(local) > 64 or not _LOCAL.match(local):
        return False
    if local.startswith(".") or local.endswith(".") or ".." in local:
        return False
    labels = dom.split(".")
    return len(labels) >= 2 and all(_LABEL.match(x) for x in labels) and labels[-1].isalpha() \
        and len(labels[-1]) >= 2


def is_disposable(domain: str) -> bool:
    parts = domain.split(".")
    return any(".".join(parts[i:]) in blocklist for i in range(len(parts) - 1))


def check_offline(email: str) -> EmailResult | None:
    """Syntax then disposable list. Returns a FINAL result if the email fails, else None."""
    if not email:
        return EmailResult("skipped", "no_email")
    if not valid_syntax(email):
        return EmailResult("invalid", "invalid_syntax")
    if is_disposable(email.split("@")[1]):
        return EmailResult("risky", "disposable")
    return None


# ---- MX ---------------------------------------------------------------------------------

MxLookup = Callable[[str], Awaitable[str]]  # domain -> "ok" | "no_mx" | "error"


def _dns_mx_sync(domain: str, timeout: float = 5.0) -> str:
    import dns.exception
    import dns.resolver

    res = dns.resolver.Resolver()
    res.lifetime = timeout
    try:
        answers = res.resolve(domain, "MX")
        hosts = [str(r.exchange).rstrip(".") for r in answers]
        return "ok" if any(hosts) else "no_mx"  # null MX (".") means "accepts no mail"
    except dns.resolver.NXDOMAIN:
        return "no_mx"
    except dns.resolver.NoAnswer:
        # RFC 5321: no MX -> mail goes to the A record if there is one.
        try:
            res.resolve(domain, "A")
            return "ok"
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
            return "no_mx"
        except Exception:  # noqa: BLE001
            return "error"
    except Exception:  # noqa: BLE001  (timeouts, no resolver configured, ...)
        return "error"


async def dns_mx(domain: str) -> str:
    return await asyncio.to_thread(_dns_mx_sync, domain)


async def check_mx(
    domain: str, cache: Cache, ttl_days: float, lookup: MxLookup = dns_mx
) -> EmailResult | None:
    """None = domain can receive mail. Cached only when DNS gave a definite answer."""
    cached = cache.get("mx", domain, ttl_days)
    outcome = cached["r"] if cached else await lookup(domain)
    if not cached and outcome in ("ok", "no_mx"):
        cache.set("mx", domain, {"r": outcome})
    if outcome == "ok":
        return None
    if outcome == "no_mx":
        return EmailResult("invalid", "no_mx")
    return EmailResult("unknown", "mx_check_failed")  # DNS trouble is not evidence of a bad email


# ---- API providers ----------------------------------------------------------------------

def _truthy(v) -> bool:
    return v is True or str(v).lower() == "true"


def map_qev(data: dict) -> EmailResult:
    """QuickEmailVerification -> shared vocabulary."""
    result, reason = str(data.get("result", "")).lower(), str(data.get("reason", "")).lower()
    if result == "valid":
        if _truthy(data.get("disposable")):
            return EmailResult("risky", "disposable", QEV)
        if _truthy(data.get("accept_all")):
            return EmailResult("risky", "accept_all", QEV)
        if _truthy(data.get("role")):
            return EmailResult("risky", "role_address", QEV)
        return EmailResult("valid", reason or "accepted_email", QEV)
    if result == "invalid":
        return EmailResult("invalid", {"rejected_email": "mailbox_not_found"}.get(reason, reason or "invalid"), QEV)
    return EmailResult("unknown", reason or "unknown", QEV)


def map_verifalia(entry: dict) -> EmailResult:
    cls = str(entry.get("classification", "")).lower()
    raw = str(entry.get("status", ""))
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", raw).lower()
    if cls == "deliverable":
        return EmailResult("valid", "deliverable", VERIFALIA)
    if cls == "undeliverable":
        return EmailResult("invalid", "mailbox_not_found" if snake == "mailbox_does_not_exist" else snake or "undeliverable", VERIFALIA)
    if cls == "risky":
        return EmailResult("risky", "accept_all" if "catch_all" in snake else snake or "risky", VERIFALIA)
    return EmailResult("unknown", snake or "unknown", VERIFALIA)


class EmailVerifier:
    """check_api(): cache -> QEV -> Verifalia -> deferred. Quota-caused unknowns are never cached."""

    QEV_URL = "https://api.quickemailverification.com/v1/verify"
    VERIFALIA_URL = "https://api.verifalia.com/v2.6/email-validations"

    def __init__(self, client: httpx.AsyncClient, cache: Cache, quota: Quota, cfg: dict,
                 secrets: dict, inflight_sem: dict[str, asyncio.Semaphore] | None = None) -> None:
        self.client, self.cache, self.quota = client, cache, quota
        self.retry = cfg["retry"]
        self.ttl = cfg["cache"]["ttl_days"]["email"]
        self.s = secrets
        self.sems = inflight_sem if inflight_sem is not None else {
            p: asyncio.Semaphore(int(cfg["providers"].get(p, {}).get("concurrency", 1)))
            for p in (QEV, VERIFALIA)
        }
        self.poll_seconds = 1.5
        self.poll_tries = 20

    async def check_api(self, email: str) -> EmailResult:
        cached = self.cache.get("email", email, self.ttl)
        if cached:
            return EmailResult(**cached)

        exhausted = errored = configured = False
        for provider, ready, fn in (
            (QEV, bool(self.s["qev_api_key"]), self._qev),
            (VERIFALIA, bool(self.s["verifalia_username"] and self.s["verifalia_password"]), self._verifalia),
        ):
            if not ready:
                continue
            configured = True
            if not self.quota.reserve(provider):
                exhausted = True
                continue
            try:
                async with self.sems[provider]:
                    outcome = await fn(email)
            except Exception as exc:  # noqa: BLE001  a crashed call is a provider error, not a spent credit
                log.error("%s call crashed: %s", provider, type(exc).__name__)
                outcome = "error"
            if isinstance(outcome, EmailResult):
                self.cache.set("email", email, outcome.__dict__)
                return outcome
            if outcome == "quota":
                self.quota.exhaust(provider)
                exhausted = True
            else:  # "error": the call never produced an answer, so don't burn the credit
                self.quota.refund(provider)
                errored = True
        if not configured:
            return EmailResult("unknown", "no_api_key")
        log.info("email deferred: %s", mask_email(email))
        return EmailResult("unknown", "quota_exhausted" if exhausted else "provider_error", deferred=True)

    async def _qev(self, email: str) -> EmailResult | str:
        r = await request(self.client, "GET", self.QEV_URL, self.retry,
                          params={"email": email, "apikey": self.s["qev_api_key"]})
        if r is None or r.status_code >= 500:
            return "error"
        if r.status_code in (402, 429):
            return "quota"
        if r.status_code != 200:
            log.warning("QEV HTTP %s (check QEV_API_KEY)", r.status_code)
            return "error"
        try:
            data = r.json()
        except ValueError:
            return "error"
        if str(data.get("success", "true")).lower() == "false":
            msg = str(data.get("message", "")).lower()
            return "quota" if "credit" in msg or "limit" in msg else "error"
        return map_qev(data)

    async def _verifalia(self, email: str) -> EmailResult | str:
        auth = (self.s["verifalia_username"], self.s["verifalia_password"])
        hdr = {"Accept": "application/json"}
        r = await request(self.client, "POST", self.VERIFALIA_URL, self.retry, auth=auth, headers=hdr,
                          json={"entries": [{"inputData": email}]})
        if r is None or r.status_code >= 500:
            return "error"
        if r.status_code in (402, 429):
            return "quota"
        if r.status_code not in (200, 201, 202):
            log.warning("Verifalia HTTP %s (check credentials)", r.status_code)
            return "error"
        try:
            job = r.json()
            jid = job["overview"]["id"]
            job_url = f"{self.VERIFALIA_URL}/{jid}"
            for _ in range(self.poll_tries):
                if str(job.get("overview", {}).get("status", "")).lower() == "completed":
                    break
                await asyncio.sleep(self.poll_seconds)
                g = await request(self.client, "GET", job_url, self.retry, auth=auth, headers=hdr)
                if g is None or g.status_code != 200:
                    return "error"
                job = g.json()
            else:
                return "error"
            entries = job.get("entries")
            entries = entries.get("data") if isinstance(entries, dict) else entries
            if not entries:
                g = await request(self.client, "GET", f"{job_url}/entries", self.retry, auth=auth, headers=hdr)
                if g is None or g.status_code != 200:
                    return "error"
                body = g.json()
                entries = body.get("data") if isinstance(body, dict) else body
            result = map_verifalia(entries[0])
            # Lead data shouldn't sit on a third party longer than needed.
            await request(self.client, "DELETE", job_url, {"attempts": 1}, auth=auth, headers=hdr)
            return result
        except (KeyError, IndexError, TypeError, ValueError):
            return "error"
