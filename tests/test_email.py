import httpx
import pytest
import respx

from conftest import KEYS, fake_mx, run, with_client
from lead_verifier.checks import email as em
from lead_verifier.checks.email import EmailVerifier, check_mx, check_offline, map_qev

QEV = "https://api.quickemailverification.com/v1/verify"
VF = "https://api.verifalia.com/v2.6/email-validations"


def qev_body(**kw):
    base = {"success": "true", "result": "valid", "reason": "accepted_email",
            "accept_all": "false", "role": "false", "disposable": "false"}
    return {**base, **kw}


# ---- offline ---------------------------------------------------------------------------

@pytest.mark.parametrize("e", ["a@b", "fahim@", "@x.com", "a b@x.com", "a@@x.com", "a..b@x.com",
                               "a@x.c", "a@-x.com", ".a@x.com"])
def test_bad_syntax(e):
    r = check_offline(e)
    assert r.status == "invalid" and r.reason == "invalid_syntax"


def test_disposable_incl_subdomain():
    assert check_offline("x@mailinator.com").reason == "disposable"
    assert check_offline("x@foo.mailinator.com").status == "risky"


def test_good_and_blank():
    assert check_offline("rahim@example.com") is None
    assert check_offline("").status == "skipped"


def test_mx_outcomes_and_caching(cache):
    calls = []

    async def lk(d):
        calls.append(d)
        return {"ok.com": "ok", "dead.com": "no_mx", "flaky.com": "error"}[d]

    assert run(check_mx("ok.com", cache, 7, lk)) is None
    assert run(check_mx("ok.com", cache, 7, lk)) is None
    assert run(check_mx("dead.com", cache, 7, lk)).reason == "no_mx"
    flaky = run(check_mx("flaky.com", cache, 7, lk))
    assert (flaky.status, flaky.reason) == ("unknown", "mx_check_failed")  # DNS trouble != bad email
    run(check_mx("flaky.com", cache, 7, lk))
    assert calls == ["ok.com", "dead.com", "flaky.com", "flaky.com"]  # errors are not cached


# ---- provider mapping ------------------------------------------------------------------

def test_map_qev_vocabulary():
    assert map_qev(qev_body()).status == "valid"
    assert (map_qev(qev_body(accept_all="true")).status, map_qev(qev_body(accept_all=True)).reason) == ("risky", "accept_all")
    assert map_qev(qev_body(role="true")).reason == "role_address"
    assert map_qev(qev_body(disposable="true")).reason == "disposable"
    inv = map_qev(qev_body(result="invalid", reason="rejected_email"))
    assert (inv.status, inv.reason) == ("invalid", "mailbox_not_found")
    assert map_qev(qev_body(result="unknown", reason="timeout")).status == "unknown"
    assert map_qev({}).status == "unknown"


def verifier(cfg, cache, quota, **secret_over):
    async def mk(client):
        v = EmailVerifier(client, cache, quota, cfg, {**KEYS, **secret_over})
        v.poll_seconds = 0
        return v
    return mk


def check(cfg, cache, quota, email="a@example.com", **secret_over):
    async def go(client):
        v = await verifier(cfg, cache, quota, **secret_over)(client)
        return await v.check_api(email)
    return with_client(go)


def vf_done(cls="Deliverable", status="Success"):
    return httpx.Response(200, json={"overview": {"id": "j1", "status": "Completed"},
                                     "entries": {"data": [{"classification": cls, "status": status}]}})


# ---- API flow --------------------------------------------------------------------------

@respx.mock
def test_qev_valid_then_cache_hit(cfg, cache, quota):
    route = respx.get(QEV).respond(200, json=qev_body())
    assert check(cfg, cache, quota).status == "valid"
    assert check(cfg, cache, quota).status == "valid"
    assert route.call_count == 1 and quota.used("quickemailverification") == 1
    assert route.calls[0].request.url.params["email"] == "a@example.com"


@respx.mock
def test_402_falls_back_to_verifalia_and_stops_qev_for_the_day(cfg, cache, quota):
    respx.get(QEV).respond(402, json={"success": "false", "message": "insufficient credits"})
    respx.post(VF).mock(return_value=vf_done())
    respx.delete(VF + "/j1").respond(200)
    r = check(cfg, cache, quota)
    assert (r.status, r.provider) == ("valid", "verifalia")
    assert quota.remaining("quickemailverification") == 0


@respx.mock
def test_429_retries_then_treated_as_exhausted(cfg, cache, quota):
    route = respx.get(QEV).respond(429)
    r = check(cfg, cache, quota, verifalia_username="", verifalia_password="")
    assert route.call_count == 3
    assert (r.status, r.reason, r.deferred) == ("unknown", "quota_exhausted", True)


@respx.mock
def test_both_exhausted_defers_and_does_not_cache(cfg, cache, quota):
    respx.get(QEV).respond(402)
    respx.post(VF).respond(402)
    r = check(cfg, cache, quota)
    assert (r.status, r.reason, r.deferred) == ("unknown", "quota_exhausted", True)
    assert cache.get("email", "a@example.com", 30) is None


@respx.mock
def test_own_quota_blocks_call_without_touching_network(cfg, cache, quota):
    cfg["providers"]["quickemailverification"]["daily_limit"] = 0
    route = respx.get(QEV).respond(200, json=qev_body())
    r = check(cfg, cache, quota, verifalia_username="")
    assert route.call_count == 0 and r.deferred


@respx.mock
def test_5xx_retried_and_is_provider_error_not_cached(cfg, cache, quota):
    route = respx.get(QEV).respond(503)
    r = check(cfg, cache, quota, verifalia_username="")
    assert route.call_count == 3 and r.reason == "provider_error" and r.deferred
    assert quota.used("quickemailverification") == 0  # credit refunded
    assert cache.get("email", "a@example.com", 30) is None


@respx.mock
def test_401_is_not_retried(cfg, cache, quota):
    route = respx.get(QEV).respond(401)
    check(cfg, cache, quota, verifalia_username="")
    assert route.call_count == 1


@respx.mock
def test_timeout_retried(cfg, cache, quota):
    route = respx.get(QEV).mock(side_effect=httpx.ConnectTimeout("t"))
    r = check(cfg, cache, quota, verifalia_username="")
    assert route.call_count == 3 and r.reason == "provider_error"


def test_no_keys_is_no_api_key_not_deferred(cfg, cache, quota):
    r = check(cfg, cache, quota, qev_api_key="", verifalia_username="", verifalia_password="")
    assert (r.reason, r.deferred) == ("no_api_key", False)


@respx.mock
def test_verifalia_polls_until_complete_and_maps_undeliverable(cfg, cache, quota):
    respx.get(QEV).respond(402)
    respx.post(VF).respond(202, json={"overview": {"id": "j1", "status": "InProgress"}})
    respx.get(VF + "/j1").mock(side_effect=[
        httpx.Response(200, json={"overview": {"id": "j1", "status": "InProgress"}}),
        httpx.Response(200, json={"overview": {"id": "j1", "status": "Completed"},
                                  "entries": {"data": [{"classification": "Undeliverable",
                                                        "status": "MailboxDoesNotExist"}]}}),
    ])
    dele = respx.delete(VF + "/j1").respond(200)
    r = check(cfg, cache, quota)
    assert (r.status, r.reason, r.provider) == ("invalid", "mailbox_not_found", "verifalia")
    assert dele.called
