import pytest

from lead_verifier.models import DomainResult, EmailResult, Lead, PhoneResult
from lead_verifier.scoring import grade_lead

MOBILE = PhoneResult("x", "+8801711223344", True, "mobile", "GP")
LANDLINE = PhoneResult("x", "+88029123456", True, "fixed_line")
NOPHONE = PhoneResult()
BADPHONE = PhoneResult("x", "", False, "unknown", reason="invalid_number")


def lead(phone=NOPHONE, email=("skipped", "no_email"), flagged=None, age=None, domain="", dup=None,
         has_email=None, deferred=False, checked=False):
    l = Lead(1, [])
    l.phone = phone
    l.email = "a@x.com" if (has_email if has_email is not None else email[0] != "skipped") else ""
    l.email_result = EmailResult(email[0], email[1], deferred=deferred)
    l.domain = DomainResult(domain=domain, flagged=flagged, sources=["webrisk"] if flagged else [], age_days=age, checked=checked)
    if dup:
        l.duplicate_of, l.duplicate_kind = dup, "phone"
    return l


@pytest.mark.parametrize("kw,grade", [
    # A
    (dict(phone=MOBILE, email=("valid", "ok")), "A"),
    (dict(phone=MOBILE), "A"),                                           # mobile, no email given
    (dict(phone=MOBILE, email=("valid", "ok"), domain="x.com", flagged=False, age=400), "A"),
    # B
    (dict(phone=MOBILE, email=("risky", "accept_all")), "B"),
    (dict(phone=MOBILE, email=("unknown", "not_api_checked")), "B"),
    (dict(phone=MOBILE, email=("invalid", "mailbox_not_found")), "B"),
    (dict(phone=NOPHONE, email=("valid", "ok")), "B"),
    (dict(phone=LANDLINE, email=("valid", "ok")), "B"),
    (dict(phone=BADPHONE, email=("valid", "ok")), "B"),
    # C
    (dict(phone=LANDLINE), "C"),
    (dict(phone=LANDLINE, email=("risky", "role_address")), "C"),
    (dict(phone=NOPHONE, email=("risky", "accept_all")), "C"),
    (dict(phone=NOPHONE, email=("unknown", "mx_check_failed")), "C"),
    (dict(phone=MOBILE, email=("valid", "ok"), domain="x.com", flagged=False, age=30), "C"),  # young domain
    # REJECT
    (dict(), "REJECT"),
    (dict(phone=BADPHONE), "REJECT"),
    (dict(phone=BADPHONE, email=("invalid", "invalid_syntax"), has_email=True), "REJECT"),
    (dict(phone=NOPHONE, email=("invalid", "no_mx")), "REJECT"),
    (dict(phone=NOPHONE, email=("risky", "disposable")), "REJECT"),
    (dict(phone=MOBILE, email=("valid", "ok"), flagged=True, domain="x.com"), "REJECT"),
    (dict(phone=MOBILE, email=("valid", "ok"), dup=3), "REJECT"),
])
def test_grade(kw, grade):
    assert grade_lead(lead(**kw))[0] == grade


def test_disposable_with_valid_phone_is_not_rejected():
    g, r = grade_lead(lead(phone=MOBILE, email=("risky", "disposable")))
    assert g == "B" and any("disposable" in x for x in r)


def test_reasons_recorded():
    g, r = grade_lead(lead(phone=MOBILE, email=("valid", "ok")))
    assert r == ["valid_mobile", "email_valid"]
    _, r = grade_lead(lead(phone=MOBILE, email=("valid", "ok"), domain="x.com", flagged=False, age=30))
    assert "domain_age_30d" in r


def test_threshold_is_configurable():
    l = lead(phone=MOBILE, email=("valid", "ok"), domain="x.com", flagged=False, age=30)
    assert grade_lead(l, min_age_days=20)[0] == "A"


def test_duplicate_reason_points_to_kept_row():
    assert grade_lead(lead(phone=MOBILE, dup=7))[1] == ["duplicate_phone_of_row_7"]


def test_deferred_and_unverified_domain_noted_not_punished():
    g, r = grade_lead(lead(phone=MOBILE, email=("unknown", "quota_exhausted"), deferred=True,
                           domain="x.com", flagged=None, checked=True))
    assert g == "B" and "email_deferred" in r and "domain_unverified" in r
