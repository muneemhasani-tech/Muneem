"""Optional WhatsApp-presence module. Interface + no-op stub only, disabled by default.

No scraper is pinned: every available checker automates WhatsApp Web, which breaks often and
risks the account used. Implement `WhatsAppChecker` yourself if you accept that.
"""
from __future__ import annotations

from typing import Protocol


class WhatsAppChecker(Protocol):
    async def is_registered(self, e164: str) -> bool | None: ...


class DisabledChecker:
    async def is_registered(self, e164: str) -> bool | None:
        return None


def make_checker(cfg: dict) -> WhatsAppChecker:
    if cfg.get("whatsapp", {}).get("enabled"):
        raise NotImplementedError(
            "whatsapp.enabled is true but no checker ships. Implement WhatsAppChecker "
            "(lead_verifier/checks/whatsapp.py) or set whatsapp.enabled: false."
        )
    return DisabledChecker()
