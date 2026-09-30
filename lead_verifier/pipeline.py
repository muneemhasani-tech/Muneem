"""Per-row orchestration: cheapest checks first, short-circuit as soon as a row is doomed."""
from __future__ import annotations

import asyncio
import logging
from collections import Counter
from dataclasses import dataclass, field

import httpx

from .cache import Cache
from .checks import domain as dom
from .checks import email as em
from .checks.phone import parse_phone
from .checks.whatsapp import WhatsAppChecker, make_checker
from .models import EmailResult, Lead
from .quota import Quota
from .scoring import email_usable, grade_lead
from .util import InFlight, now_iso

log = logging.getLogger(__name__)

PENDING = EmailResult("unknown", "not_api_checked")


@dataclass
class RunSummary:
    rows_in: int = 0
    grades: Counter = field(default_factory=Counter)
    credits: dict[str, int] = field(default_factory=dict)
    deferred: int = 0


class Pipeline:
    def __init__(self, cfg: dict, cache: Cache, quota: Quota, client: httpx.AsyncClient, secrets: dict,
                 offline_only: bool = False, mx_lookup: em.MxLookup | None = None,
                 age_backend=None, whatsapp: WhatsAppChecker | None = None) -> None:
        self.cfg, self.cache, self.quota = cfg, cache, quota
        self.offline_only = offline_only
        self.mx_lookup = mx_lookup or (lambda d: em.dns_mx(d))
        self.skip = {d.lower() for d in cfg["domain"]["skip_domains"]}
        self.verifier = em.EmailVerifier(client, cache, quota, cfg, secrets)
        self.domains = dom.DomainChecker(client, cache, quota, cfg, secrets,
                                         age_backend or (lambda d: dom.lookup_creation_date(d)))
        self.wa = whatsapp or make_checker(cfg)
        self.wa_enabled = bool(cfg["whatsapp"]["enabled"])
        self.inflight = InFlight()
        self.rows_sem = asyncio.Semaphore(64)

    # ---- phase A: offline, sequential (dedupe needs the whole file) -----------------------

    def prepare(self, leads: list[Lead]) -> None:
        seen_phone: dict[str, int] = {}
        seen_email: dict[str, int] = {}
        region = self.cfg["region"]
        for l in leads:
            l.phone = parse_phone(l.phone_raw, region)                         # 1-2
            l.email = em.normalise_email(l.email_raw)
            final = em.check_offline(l.email)                                  # 4 (syntax, disposable)
            l.email_result, l.email_final = (final, True) if final else (PENDING, False)
            l.domain.domain = self._derive_domain(l)                           # 6 (derivation only)

            if l.phone.valid and l.phone.e164 in seen_phone:                   # 3
                l.duplicate_of, l.duplicate_kind = seen_phone[l.phone.e164], "phone"
            elif l.email and em.valid_syntax(l.email) and l.email in seen_email:
                l.duplicate_of, l.duplicate_kind = seen_email[l.email], "email"
            else:
                if l.phone.valid:
                    seen_phone[l.phone.e164] = l.row_num
                if l.email and em.valid_syntax(l.email):
                    seen_email[l.email] = l.row_num

    def _derive_domain(self, l: Lead) -> str:
        cands = [l.website_raw]
        if l.email and em.valid_syntax(l.email):
            cands.append(l.email)
        for c in cands:
            d = dom.extract_domain(c)
            if d and d not in self.skip:
                return d
        return ""

    # ---- phase B: network, concurrent per row ---------------------------------------------

    async def _network(self, l: Lead) -> None:
        if l.duplicate_of is not None:
            return
        phone_ok = bool(l.phone.valid)

        if not l.email_final:                                                   # 4 (MX)
            mx = await em.check_mx(l.email.split("@")[1], self.cache,
                                   self.cfg["cache"]["ttl_days"]["mx"], self.mx_lookup)
            if mx and mx.status == "invalid":
                l.email_result, l.email_final = mx, True
            elif mx:                                                            # DNS trouble
                l.email_result = mx
        if not phone_ok and not email_usable(l):                                # early REJECT
            return
        if self.offline_only:
            return

        if not l.email_final:                                                   # 5 (API)
            l.email_result = await self.inflight.once(
                ("email", l.email), lambda: self.verifier.check_api(l.email))
            l.email_final = True
            if not phone_ok and not email_usable(l):
                return

        if l.domain.domain:                                                     # 7-8
            d = l.domain.domain
            rep, age = await asyncio.gather(
                self.inflight.once(("rep", d), lambda: self.domains.check_reputation(d)),
                self.inflight.once(("age", d), lambda: self.domains.check_age(d)),
            )
            l.domain.flagged, l.domain.sources = rep.flagged, rep.sources
            l.domain.deferred, l.domain.age_days, l.domain.checked = rep.deferred, age, True

        if self.wa_enabled and phone_ok and l.phone.type == "mobile":           # 9
            l.whatsapp = await self.wa.is_registered(l.phone.e164)

    async def _safe_network(self, l: Lead) -> None:
        async with self.rows_sem:
            try:
                await self._network(l)
            except Exception as exc:  # noqa: BLE001  one bad row must never sink the run
                log.error("row %s failed in network stage: %s", l.row_num, type(exc).__name__)

    # ---- run ------------------------------------------------------------------------------

    async def run(self, leads: list[Lead]) -> RunSummary:
        self.prepare(leads)
        await asyncio.gather(*(self._safe_network(l) for l in leads))
        s = RunSummary(rows_in=len(leads))
        stamp = now_iso(self.cfg["timezone"])
        for l in leads:                                                         # 10
            l.grade, l.reasons = grade_lead(l, self.cfg["scoring"]["min_domain_age_days"])
            l.checked_at = stamp
            s.grades[l.grade] += 1
            s.deferred += int(l.email_result.deferred or l.domain.deferred)
        s.credits = dict(self.quota.run_used)
        return s
