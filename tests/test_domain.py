from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx

from conftest import KEYS, with_client
from lead_verifier.checks.domain import DomainChecker, extract_domain

WR = "https://webrisk.googleapis.com/v1/uris:search"
UH = "https://urlhaus-api.abuse.ch/v1/host/"


@pytest.mark.parametrize("raw,want", [
    ("https://www.shop.example.com.bd/x?y=1", "example.com.bd"),
    ("WWW.Example.COM", "example.com"),
    ("rahim@mail.example.org", "example.org"),
    ("example.co.uk/path", "example.co.uk"),
    ("", None), ("not a domain", None), ("localhost", None),
])
def test_extract_domain(raw, want):
    assert extract_domain(raw) == want


def checker(client, cfg, cache, quota, age=lambda d: None, **sec):
    return DomainChecker(client, cache, quota, cfg, {**KEYS, **sec}, age)


def rep(cfg, cache, quota, domain="evil.com", **sec):
    return with_client(lambda c: checker(c, cfg, cache, quota, **sec).check_reputation(domain))


@respx.mock
def test_webrisk_flags_and_sends_uri_and_key(cfg, cache, quota):
    w = respx.get(WR).respond(200, json={"threat": {"threatTypes": ["MALWARE"]}})
    respx.post(UH).respond(200, json={"query_status": "no_results"})
    r = rep(cfg, cache, quota)
    assert r.flagged is True and r.sources == ["webrisk"]
    q = w.calls[0].request.url.params
    assert q["uri"] == "http://evil.com/" and q["key"] == "wk" and "MALWARE" in q.get_list("threatTypes")


@respx.mock
def test_urlhaus_flags_with_auth_header(cfg, cache, quota):
    respx.get(WR).respond(200, json={})
    u = respx.post(UH).respond(200, json={"query_status": "ok", "url_count": "3", "urls_online": "1"})
    r = rep(cfg, cache, quota)
    assert r.flagged is True and r.sources == ["urlhaus"]
    assert u.calls[0].request.headers["Auth-Key"] == "uk"


@respx.mock
def test_both_flag(cfg, cache, quota):
    respx.get(WR).respond(200, json={"threat": {}})
    respx.post(UH).respond(200, json={"query_status": "ok", "url_count": "3", "urls_online": "2"})
    assert rep(cfg, cache, quota).sources == ["webrisk", "urlhaus"]


@respx.mock
def test_clean_only_when_both_answered(cfg, cache, quota):
    respx.get(WR).respond(200, json={})
    respx.post(UH).respond(200, json={"query_status": "no_results"})
    assert rep(cfg, cache, quota).flagged is False


@respx.mock
def test_offline_history_only_flagged_if_configured(cfg, cache, quota):
    respx.get(WR).respond(200, json={})
    respx.post(UH).respond(200, json={"query_status": "ok", "url_count": "5", "urls_online": "0"})
    assert rep(cfg, cache, quota).flagged is False
    cfg["domain"]["urlhaus_require_online"] = False
    cache.clear()
    assert rep(cfg, cache, quota).flagged is True


@respx.mock
def test_one_provider_down_gives_unknown_and_caches_the_other(cfg, cache, quota):
    w = respx.get(WR).respond(200, json={})
    u = respx.post(UH).respond(500)
    r = rep(cfg, cache, quota)
    assert r.flagged is None
    r = rep(cfg, cache, quota)          # second run: webrisk answered from cache
    assert w.call_count == 1 and u.call_count == 6


@respx.mock
def test_one_provider_down_but_other_flags(cfg, cache, quota):
    respx.get(WR).respond(200, json={"threat": {}})
    respx.post(UH).respond(500)
    assert rep(cfg, cache, quota).flagged is True


@respx.mock
def test_missing_keys_skip_providers_silently(cfg, cache, quota):
    r = rep(cfg, cache, quota, webrisk_api_key="", urlhaus_auth_key="")
    assert r.flagged is None and not r.deferred


@respx.mock
def test_quota_exhausted_defers_and_skips_network(cfg, cache, quota):
    cfg["providers"]["webrisk"]["daily_limit"] = 0
    u = respx.post(UH).respond(200, json={"query_status": "no_results"})
    r = rep(cfg, cache, quota)
    assert r.deferred and r.flagged is None and u.call_count == 1


@respx.mock
def test_webrisk_429_exhausts_provider(cfg, cache, quota):
    respx.get(WR).respond(429)
    respx.post(UH).respond(200, json={"query_status": "no_results"})
    r = rep(cfg, cache, quota)
    assert r.deferred and quota.remaining("webrisk") == 0


# ---- age ------------------------------------------------------------------------------

def age(cfg, cache, quota, backend, domain="x.com"):
    return with_client(lambda c: checker(c, cfg, cache, quota, age=backend).check_age(domain))


def test_age_days_and_cached_by_date(cfg, cache, quota):
    calls = []

    def backend(d):
        calls.append(d)
        return datetime.now(timezone.utc) - timedelta(days=100, hours=1)

    assert age(cfg, cache, quota, backend) == 100
    assert age(cfg, cache, quota, backend) == 100
    assert len(calls) == 1 and quota.used("rdap") == 1


def test_naive_datetime_ok(cfg, cache, quota):
    assert age(cfg, cache, quota, lambda d: datetime.utcnow() - timedelta(days=5, hours=1)) == 5


def test_age_failure_is_none_never_raises(cfg, cache, quota):
    def boom(d):
        raise RuntimeError("rdap down")

    assert age(cfg, cache, quota, boom) is None
    assert age(cfg, cache, quota, lambda d: None) is None
    assert quota.used("rdap") == 0  # failures refunded
