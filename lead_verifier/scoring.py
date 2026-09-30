"""Contactability grade (A / B / C / REJECT). Not buyer intent; sits next to HOT/WARM/COLD."""
from __future__ import annotations

from .models import Lead

USABLE_EMAIL = {"valid", "risky", "unknown"}


def email_usable(l: Lead) -> bool:
    """Passed offline checks and not invalid/disposable/absent. Used for the REJECT rules."""
    r = l.email_result
    return r.status in USABLE_EMAIL and r.reason != "disposable"


def grade_lead(l: Lead, min_age_days: int = 90) -> tuple[str, list[str]]:
    p, e, d = l.phone, l.email_result, l.domain
    if l.duplicate_of is not None:
        return "REJECT", [f"duplicate_{l.duplicate_kind}_of_row_{l.duplicate_of}"]
    if d.flagged:
        return "REJECT", [f"domain_flagged:{'+'.join(d.sources)}"]

    phone_ok = bool(p.valid)
    mobile = phone_ok and p.type == "mobile"
    if e.reason == "disposable" and not phone_ok:
        return "REJECT", ["disposable_email_no_valid_phone"]
    if not phone_ok and not email_usable(l):
        why = e.reason or e.status
        return "REJECT", ["no_valid_contact", f"email_{why}"] if l.email else ["no_valid_contact"]

    reasons: list[str] = []
    es = e.status
    if mobile:
        reasons.append("valid_mobile")
        if es in ("valid", "skipped"):
            grade = "A"
            reasons.append("email_valid" if es == "valid" else "no_email")
        elif es in ("risky", "unknown"):
            grade = "B"
            reasons.append(f"email_{es}" + (f"({e.reason})" if e.reason else ""))
        else:  # invalid email, working mobile
            grade = "B"
            reasons.append(f"email_invalid({e.reason})" if e.reason else "email_invalid")
    elif phone_ok:
        reasons.append(f"phone_{p.type or 'unknown'}_only")
        if es == "valid":
            grade = "B"
            reasons.append("email_valid")
        else:
            grade = "C"
            if es != "skipped":
                reasons.append(f"email_{es}")
    else:  # no valid phone; email usable
        if es == "valid":
            grade = "B"
            reasons += ["no_valid_phone", "email_valid"]
        else:
            grade = "C"
            reasons += ["no_valid_phone", f"email_{es}"]

    if e.deferred:
        reasons.append("email_deferred")
    if d.checked and d.flagged is None:
        reasons.append("domain_unverified")
    if d.age_days is not None and d.age_days < min_age_days:
        if grade in ("A", "B"):
            grade = "C"
        reasons.append(f"domain_age_{d.age_days}d")
    if l.whatsapp is False:
        reasons.append("whatsapp_not_registered")
    return grade, reasons
