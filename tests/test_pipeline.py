import csv
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import respx
from typer.testing import CliRunner

from conftest import KEYS, fake_mx, make_cfg, run, with_client
from lead_verifier import cli
from lead_verifier.cache import Cache
from lead_verifier.io_csv import build_leads, read_csv, write_outputs
from lead_verifier.pipeline import Pipeline
from lead_verifier.quota import Quota

FIX = Path(__file__).parent / "fixtures" / "sample_leads.csv"
QEV = "https://api.quickemailverification.com/v1/verify"
WR = "https://webrisk.googleapis.com/v1/uris:search"
UH = "https://urlhaus-api.abuse.ch/v1/host/"
OLD = lambda d: datetime.now(timezone.utc) - timedelta(days=2000)  # noqa: E731


def leads():
    h, rows = read_csv(FIX)
    return h, build_leads(h, rows)


def execute(cfg, cache, secrets=KEYS, offline=False, ls=None):
    quota = Quota(cache, cfg["providers"])
    ls = ls or leads()[1]

    async def go(client):
        p = Pipeline(cfg, cache, quota, client, secrets, offline_only=offline, mx_lookup=fake_mx, age_backend=OLD)
        return await p.run(ls)

    return with_client(go), ls, quota


def by_row(ls):
    return {l.row_num: l for l in ls}


def mock_all_ok():
    respx.get(QEV).respond(200, json={"success": "true", "result": "valid", "reason": "accepted_email",
                                      "accept_all": "false", "role": "false", "disposable": "false"})
    respx.get(WR).respond(200, json={})
    respx.post(UH).respond(200, json={"query_status": "no_results"})


@respx.mock  # no routes registered: any HTTP call would raise
def test_offline_only_makes_no_network_calls_and_grades_sample(cfg, cache):
    s, ls, _ = execute(cfg, cache, secrets={k: "" for k in KEYS}, offline=True)
    r = by_row(ls)
    assert s.rows_in == 12 and s.credits == {}
    assert r[1].phone.e164 == "+8801711223344" and r[1].phone.carrier == "Grameenphone"
    assert r[1].grade == "B" and r[1].email_result.reason == "not_api_checked"  # email unverified offline
    assert r[3].grade == "A"                                    # mobile, no email
    assert r[4].duplicate_of == 1 and r[4].grade == "REJECT"    # same phone as row 1
    assert r[11].duplicate_of == 2 and r[11].duplicate_kind == "email"
    assert r[5].phone.type == "fixed_line" and r[5].grade == "C"
    assert r[6].grade == "REJECT" and r[6].email_result.reason == "disposable"
    assert r[7].grade == "REJECT" and r[7].email_result.reason == "invalid_syntax"
    assert r[8].grade == "REJECT"
    assert r[12].phone.valid and r[12].grade == "A"


@respx.mock
def test_offline_only_domain_derivation(cfg, cache):
    _, ls, _ = execute(cfg, cache, offline=True)
    r = by_row(ls)
    assert r[1].domain.domain == "rahimproperties.com.bd"       # website beats email domain
    assert r[2].domain.domain == ""                             # gmail is free-mail
    assert r[3].domain.domain == "salmarealty.com"
    assert r[10].domain.domain == "example.net"                 # facebook skipped -> email domain


@respx.mock
def test_full_run_then_rerun_costs_zero(cfg, cache):
    mock_all_ok()
    s, ls, q = execute(cfg, cache)
    assert s.grades["A"] >= 3 and s.deferred == 0
    assert q.run_used["quickemailverification"] > 0
    calls = sum(r.call_count for r in respx.routes)
    # lead 1: mobile + valid email + old domain -> A
    assert by_row(ls)[1].grade == "A" and by_row(ls)[1].domain.age_days > 1000

    s2, _, q2 = execute(cfg, cache)
    assert sum(r.call_count for r in respx.routes) == calls and dict(q2.run_used) == {}
    assert s2.grades == s.grades


@respx.mock
def test_shared_domain_is_looked_up_once(cfg, cache):
    mock_all_ok()
    h, rows = read_csv(FIX)
    rows = [["A", f"01711{i:06d}", f"u{i}@shared-agency.com", "", "", ""] for i in range(10, 20)]
    execute(cfg, cache, ls=build_leads(h, rows))
    assert respx.routes[1].call_count == 1 and respx.routes[2].call_count == 1  # webrisk, urlhaus


@respx.mock
def test_flagged_domain_rejects(cfg, cache):
    respx.get(QEV).respond(200, json={"success": "true", "result": "valid"})
    respx.get(WR).respond(200, json={"threat": {"threatTypes": ["SOCIAL_ENGINEERING"]}})
    respx.post(UH).respond(200, json={"query_status": "no_results"})
    _, ls, _ = execute(cfg, cache)
    r = by_row(ls)[1]
    assert r.grade == "REJECT" and r.domain.sources == ["webrisk"]


@respx.mock
def test_every_provider_down_still_completes(cfg, cache):
    respx.get(QEV).respond(503)
    respx.get(WR).respond(500)
    respx.post(UH).mock(side_effect=httpx.ConnectError("down"))
    respx.post("https://api.verifalia.com/v2.6/email-validations").respond(503)
    s, ls, _ = execute(cfg, cache)
    assert s.rows_in == 12 and sum(s.grades.values()) == 12
    assert s.deferred > 0
    assert by_row(ls)[1].grade == "B"          # mobile + unknown email; domain unverified, not punished


@respx.mock
def test_quota_exhaustion_defers_then_next_run_pays_only_for_deferred(cache):
    mock_all_ok()
    cfg = make_cfg()
    cfg["providers"]["quickemailverification"]["daily_limit"] = 2
    s, ls, q = execute(cfg, cache, secrets={**KEYS, "verifalia_username": ""})
    assert q.run_used["quickemailverification"] == 2 and s.deferred > 0
    deferred = [l for l in ls if l.email_result.deferred]
    assert all(l.email_result.reason == "quota_exhausted" for l in deferred)

    cfg["providers"]["quickemailverification"]["daily_limit"] = 100
    s2, _, q2 = execute(cfg, cache)
    assert s2.deferred == 0 and q2.run_used["quickemailverification"] == len(deferred)


@respx.mock
def test_row_exception_does_not_sink_run(cfg, cache):
    mock_all_ok()

    def bad_age(d):
        raise RuntimeError("x")

    async def go(client):
        p = Pipeline(cfg, cache, Quota(cache, cfg["providers"]), client, KEYS, mx_lookup=fake_mx, age_backend=bad_age)
        async def boom(*a, **k):
            raise ValueError("kaboom")
        p.verifier.check_api = boom
        return await p.run(leads()[1])

    s = with_client(go)
    assert sum(s.grades.values()) == 12


# ---- I/O ---------------------------------------------------------------------------------

def test_round_trip_unchanged(tmp_path):
    h, rows = read_csv(FIX)
    out = tmp_path / "rt.csv"
    from lead_verifier.io_csv import write_plain
    write_plain(out, h, rows)
    h2, rows2 = read_csv(out)
    assert (h2, rows2) == (h, rows)
    assert rows[-1][0] == "Rafi, Jr." and 'comma, and "quotes"' in rows[-1][5]


def test_outputs_preserve_original_columns_and_split(tmp_path, cfg, cache):
    h, _ = read_csv(FIX)
    _, ls, _ = execute(cfg, cache, offline=True)
    files = write_outputs(h, ls, tmp_path, "sample")
    assert files["graded"].read_bytes().startswith(b"\xef\xbb\xbf")   # BOM for Sheets
    gh, grows = read_csv(files["graded"])
    assert gh[:6] == h and gh[6] == "phone_e164" and gh[-1] == "checked_at" and len(grows) == 12
    orig = read_csv(FIX)[1]
    assert [r[:6] for r in grows] == orig
    n = {k: len(read_csv(files[k])[1]) for k in ("A_B", "C", "REJECT")}
    assert sum(n.values()) == 12 and n["REJECT"] >= 5


def test_appended_column_collision_gets_prefix():
    from lead_verifier.io_csv import out_headers
    assert out_headers(["Name", "Domain"])[7] == "lv_domain"


def test_alias_mapping():
    h = ["Client", "Mobile", "E-mail", "Site", "Platform"]
    l = build_leads(h, [["A", "01711223344", "a@b.com", "b.com", "FB"]])[0]
    assert (l.name, l.phone_raw, l.email_raw, l.website_raw, l.source) == ("A", "01711223344", "a@b.com", "b.com", "FB")


# ---- CLI ---------------------------------------------------------------------------------

def _cli_env(monkeypatch, tmp_path, keys=True):
    monkeypatch.chdir(tmp_path)
    for env, k in (("QEV_API_KEY", "qev_api_key"), ("GOOGLE_WEBRISK_API_KEY", "webrisk_api_key"),
                   ("URLHAUS_AUTH_KEY", "urlhaus_auth_key"), ("VERIFALIA_USERNAME", ""), ("VERIFALIA_PASSWORD", "")):
        monkeypatch.setenv(env, KEYS.get(k, "") if keys else "")
    monkeypatch.setattr("lead_verifier.checks.email.dns_mx", fake_mx)
    monkeypatch.setattr("lead_verifier.checks.domain.lookup_creation_date", OLD)
    monkeypatch.setattr("lead_verifier.pipeline.dom.lookup_creation_date", OLD)


@respx.mock
def test_cli_offline_only_without_any_keys(monkeypatch, tmp_path):
    _cli_env(monkeypatch, tmp_path, keys=False)
    shutil.copy(FIX, tmp_path / "leads.csv")
    res = CliRunner().invoke(cli.app, ["run", "leads.csv", "--offline-only", "--out-dir", "out"])
    assert res.exit_code == 0, res.output
    assert "Rows in: 12" in res.output and "Credits used this run: none" in res.output
    assert {p.name for p in (tmp_path / "out").iterdir()} == {
        "leads_graded.csv", "leads_A_B.csv", "leads_C.csv", "leads_REJECT.csv"}


@respx.mock
def test_cli_limit_quota_resume_and_cache_clear(monkeypatch, tmp_path):
    _cli_env(monkeypatch, tmp_path)
    mock_all_ok()
    shutil.copy(FIX, tmp_path / "leads.csv")
    (tmp_path / "config.yaml").write_text(
        "providers:\n  quickemailverification: {daily_limit: 1}\nretry: {backoff_seconds: [0, 0, 0]}\n")
    runner = CliRunner()
    res = runner.invoke(cli.app, ["run", "leads.csv", "--limit", "6", "--out-dir", "out"])
    assert res.exit_code == 0, res.output
    assert "Rows in: 6" in res.output and "quickemailverification=1" in res.output
    assert "Rows deferred: 0" not in res.output

    res = runner.invoke(cli.app, ["quota"])
    assert "quickemailverification" in res.output and "webrisk" in res.output

    (tmp_path / "config.yaml").write_text("retry: {backoff_seconds: [0, 0, 0]}\n")  # quota back to 100
    res = runner.invoke(cli.app, ["resume", "out/leads_graded.csv"])
    assert res.exit_code == 0, res.output
    assert "Rows deferred: 0" in res.output
    _, rows = read_csv(tmp_path / "out" / "leads_graded.csv")
    assert not any(r[-9] == "unknown" and r[-8] == "quota_exhausted" for r in rows)
    assert len(rows) == 6

    res = runner.invoke(cli.app, ["resume", "out/leads_graded.csv"])
    assert "Nothing to resume" in res.output

    res = runner.invoke(cli.app, ["cache", "clear", "--kind", "email"])
    assert res.exit_code == 0 and "Deleted" in res.output


def test_resume_rejects_non_graded_file(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    shutil.copy(FIX, tmp_path / "leads.csv")
    res = CliRunner().invoke(cli.app, ["resume", "leads.csv"])
    assert res.exit_code != 0
