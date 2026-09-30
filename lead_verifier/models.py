"""Shared dataclasses."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PhoneResult:
    raw: str = ""
    e164: str = ""
    valid: bool | None = None  # None = no phone supplied
    type: str = ""             # mobile / fixed_line / voip / unknown
    carrier: str = ""
    reason: str = ""


@dataclass
class EmailResult:
    status: str = "unknown"    # valid / invalid / risky / unknown / skipped
    reason: str = ""
    provider: str = ""
    deferred: bool = False     # quota/provider trouble: worth retrying on `resume`


@dataclass
class DomainResult:
    domain: str = ""
    flagged: bool | None = None
    sources: list[str] = field(default_factory=list)
    age_days: int | None = None
    deferred: bool = False
    checked: bool = False      # reputation lookup was attempted (False in --offline-only)


@dataclass
class Lead:
    row_num: int                       # 1-based data row (header excluded)
    cells: list[str]                   # original cells, untouched
    name: str = ""
    phone_raw: str = ""
    email_raw: str = ""
    website_raw: str = ""
    source: str = ""

    phone: PhoneResult = field(default_factory=PhoneResult)
    email: str = ""                    # normalised (trimmed, lowercased)
    email_result: EmailResult = field(default_factory=lambda: EmailResult("skipped", "no_email"))
    email_final: bool = False          # True once no further email stage should run
    domain: DomainResult = field(default_factory=DomainResult)
    duplicate_of: int | None = None
    duplicate_kind: str = ""           # phone / email
    whatsapp: bool | None = None

    grade: str = ""
    reasons: list[str] = field(default_factory=list)
    checked_at: str = ""
