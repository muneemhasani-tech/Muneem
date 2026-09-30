"""Offline phone validation with `phonenumbers` (free, no network)."""
from __future__ import annotations

import re

import phonenumbers
from phonenumbers import PhoneNumberType, carrier

from ..models import PhoneResult

_TYPE = {
    PhoneNumberType.MOBILE: "mobile",
    PhoneNumberType.FIXED_LINE: "fixed_line",
    PhoneNumberType.VOIP: "voip",
}


def _candidates(raw: str) -> list[str]:
    """One cell can hold several numbers ('017.. / 018..'); return each as cleaned text."""
    out = []
    for part in re.split(r"[/,;|\n]", raw):
        s = part.strip()
        if not s:
            continue
        plus = s.startswith("+")
        digits = re.sub(r"\D", "", s)
        if not digits:
            continue
        if digits.startswith("00"):            # 0088... international prefix
            digits, plus = digits[2:], True
        if not plus and digits.startswith("880") and len(digits) == 13:
            plus = True                         # 8801711223344 (no plus)
        if not plus and len(digits) == 10 and digits.startswith("1"):
            digits = "0" + digits               # 1711223344 (leading 0 lost, e.g. in Excel)
        out.append(("+" if plus else "") + digits)
    return out


def parse_phone(raw: str, default_region: str = "BD") -> PhoneResult:
    raw = (raw or "").strip()
    if not raw:
        return PhoneResult()
    cands = _candidates(raw)
    if not cands:
        return PhoneResult(raw=raw, valid=False, type="unknown", reason="unparseable")
    fallback: PhoneResult | None = None
    for c in cands:
        try:
            n = phonenumbers.parse(c, default_region)
        except phonenumbers.NumberParseException:
            fallback = fallback or PhoneResult(raw=raw, valid=False, type="unknown", reason="unparseable")
            continue
        typ = _TYPE.get(phonenumbers.number_type(n), "unknown")
        if phonenumbers.is_valid_number(n):
            return PhoneResult(
                raw=raw,
                e164=phonenumbers.format_number(n, phonenumbers.PhoneNumberFormat.E164),
                valid=True,
                type=typ,
                carrier=carrier.name_for_number(n, "en"),  # as returned; no hardcoded prefix table
            )
        fallback = fallback or PhoneResult(raw=raw, valid=False, type="unknown", reason="invalid_number")
    return fallback or PhoneResult(raw=raw, valid=False, type="unknown", reason="unparseable")


def is_valid_mobile(p: PhoneResult) -> bool:
    return bool(p.valid) and p.type == "mobile"
