import json
import threading
import urllib.request

import pytest

from conftest import fake_mx, make_cfg
from lead_verifier.web import serve

SAMPLE = b"Name,Phone,Email\nRahim,01711-223344,\nBad,123,\n\xe0\xa6\xb0\xe0\xa6\xb9\xe0\xa6\xbf\xe0\xa6\xae,01811223344,\n"


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setattr("lead_verifier.checks.email.dns_mx", fake_mx)
    for k in ("QEV_API_KEY", "VERIFALIA_USERNAME", "VERIFALIA_PASSWORD", "GOOGLE_WEBRISK_API_KEY", "URLHAUS_AUTH_KEY"):
        monkeypatch.setenv(k, "")
    cfg = make_cfg()
    cfg["cache"]["path"] = str(tmp_path / "cache.db")
    srv = serve(cfg, port=0, open_browser=False)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def call(url, data=None):
    req = urllib.request.Request(url, data=data, method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def test_page_served_and_bound_locally(server):
    code, body = call(server + "/")
    assert code == 200 and b"Lead Verifier" in body and server.startswith("http://127.0.0.1")


def test_check_one_lead(server):
    code, body = call(server + "/api/check?offline=1", json.dumps({"phone": "01676728214", "email": "a@gmail.com", "website": ""}).encode())
    j = json.loads(body)
    assert code == 200 and j["phone"]["e164"] == "+8801676728214" and j["phone"]["valid"]
    assert j["grade"] in "AB"


def test_upload_returns_grades_and_csv_with_bangla_intact(server):
    code, body = call(server + "/api/upload?offline=1", SAMPLE)
    j = json.loads(body)
    assert code == 200 and j["summary"]["rows"] == 3
    assert j["summary"]["grades"] == {"A": 2, "REJECT": 1}
    assert "রহিম" in j["csv"] and j["csv"].splitlines()[0].endswith("checked_at")


def test_errors_are_friendly_not_tracebacks(server):
    code, body = call(server + "/api/upload", b"")
    assert code == 400 and "empty" in json.loads(body)["error"]
    code, body = call(server + "/api/check", b"{not json")
    assert code == 400 and "Traceback" not in body.decode()


def test_status_reports_keys_without_leaking_them(server):
    code, body = call(server + "/api/status")
    j = json.loads(body)
    assert j["keys"]["webrisk"] is False and "quota" in j
