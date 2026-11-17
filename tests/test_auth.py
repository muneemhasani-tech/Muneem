import http.client
import json
import threading

import pytest

from property_finder import auth, store, web


@pytest.fixture()
def server(monkeypatch, tmp_path):
    monkeypatch.setattr(store.connect, "__defaults__", (tmp_path / "a.db",))
    con = store.connect()
    auth.create_user(con, "boss@mra.test", "Boss", "correct horse battery", role="admin", status="approved", by="test")
    store.upsert(con, {"source": "s", "url": "https://x/1", "title": "Flat", "purpose": "sale", "ptype": "apartment", "area": "gulshan",
                       "price": 30_000_000.0, "size_sqft": 1800.0, "phone": "01700000001", "poster": "Owner"})
    con.commit()
    srv = web.serve(0, open_browser=False)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv.server_port
    srv.shutdown()


def call(port, method, path, body=None, cookie=None, origin=None):
    c = http.client.HTTPConnection("127.0.0.1", port)
    h = {"Content-Type": "application/json"}
    if cookie:
        h["Cookie"] = cookie
    if origin:
        h["Origin"] = origin
    c.request(method, path, json.dumps(body) if body is not None else None, h)
    r = c.getresponse()
    data = r.read()
    ck = r.getheader("Set-Cookie")
    return r.status, (json.loads(data) if data[:1] in (b"{", b"[") else data), ck


def sign_in(port, email, pw):
    st, d, ck = call(port, "POST", "/api/auth/login", {"email": email, "password": pw})
    return st, d, (ck.split(";")[0] if ck else None)


def test_no_data_without_sign_in(server):
    for path in ("/api/listings", "/api/export.csv", "/api/config", "/api/assumptions", "/api/job", "/api/websearch", "/api/admin/users"):
        assert call(server, "GET", path)[0] == 401, path
    assert call(server, "POST", "/api/lead", {"id": "x", "status": "won"})[0] == 401
    st, page, _ = call(server, "GET", "/")
    assert st == 200 and b"Request access" in page and b"01700000001" not in page


def test_request_approve_revoke(server):
    st, d, _ = call(server, "POST", "/api/auth/signup", {"name": "Rina", "email": "rina@x.test", "phone": "01711111111", "password": "a long password"})
    assert st == 200
    st, d, ck = sign_in(server, "rina@x.test", "a long password")
    assert st == 400 and "waiting for approval" in d["error"] and ck is None  # pending: no session
    st, _, admin = sign_in(server, "boss@mra.test", "correct horse battery")
    assert st == 200
    uid = [u for u in call(server, "GET", "/api/admin/users", cookie=admin)[1]["users"] if u["email"] == "rina@x.test"][0]["id"]
    assert call(server, "POST", "/api/admin/status", {"id": uid, "status": "approved"}, cookie=admin)[0] == 200
    st, _, member = sign_in(server, "rina@x.test", "a long password")
    assert st == 200
    rows = call(server, "GET", "/api/listings", cookie=member)[1]["rows"]
    assert rows[0]["phone"] == "01700000001" and rows[0]["url"] and rows[0]["size_sqft"] == 1800 and rows[0]["price"] == 30_000_000
    # members cannot search, change assumptions, see API keys or manage members
    assert call(server, "POST", "/api/search", {}, cookie=member)[0] == 403
    assert call(server, "GET", "/api/websearch", cookie=member)[0] == 403
    assert call(server, "GET", "/api/admin/users", cookie=member)[0] == 403
    assert call(server, "POST", "/api/admin/status", {"id": uid, "status": "approved"}, cookie=member)[0] == 403
    call(server, "POST", "/api/admin/status", {"id": uid, "status": "revoked"}, cookie=admin)
    assert call(server, "GET", "/api/listings", cookie=member)[0] == 401  # revoked: existing session is dead


def test_wrong_password_and_lockout(server):
    for _ in range(5):
        st, d, _ = sign_in(server, "boss@mra.test", "nope nope nope")
        assert st == 400 and d["error"] == "Email or password is not right."
    st, d, _ = sign_in(server, "boss@mra.test", "correct horse battery")
    assert st == 400 and "Too many attempts" in d["error"]


def test_signup_rules(server):
    assert call(server, "POST", "/api/auth/signup", {"name": "A", "email": "bad", "phone": "1", "password": "a long password"})[0] == 400
    assert call(server, "POST", "/api/auth/signup", {"name": "A", "email": "a@x.test", "phone": "1", "password": "short"})[0] == 400
    assert call(server, "POST", "/api/auth/signup", {"name": "A", "email": "a@x.test", "password": "a long password"})[0] == 400  # phone needed
    ok = {"name": "A", "email": "a@x.test", "phone": "1", "password": "a long password"}
    assert call(server, "POST", "/api/auth/signup", ok)[0] == 200
    assert call(server, "POST", "/api/auth/signup", ok)[0] == 400  # duplicate


def test_cross_site_post_refused_and_logout(server):
    st, _, admin = sign_in(server, "boss@mra.test", "correct horse battery")
    assert call(server, "POST", "/api/lead", {"id": "x", "status": "won"}, cookie=admin, origin="https://evil.example")[0] == 403
    call(server, "POST", "/api/auth/logout", {}, cookie=admin)
    assert call(server, "GET", "/api/listings", cookie=admin)[0] == 401


def test_passwords_are_hashed(server):
    con = store.connect()
    row = con.execute("SELECT pw_hash FROM users WHERE email='boss@mra.test'").fetchone()
    assert "correct horse" not in row[0] and len(row[0]) == 64


def test_reset_password_ends_sessions_and_lockout(server):
    st, _, admin = sign_in(server, "boss@mra.test", "correct horse battery")
    assert st == 200
    for _ in range(5):
        sign_in(server, "boss@mra.test", "wrong wrong wrong")
    con = store.connect()
    auth.set_password(con, "boss@mra.test", "a brand new passphrase")
    con.close()
    assert call(server, "GET", "/api/listings", cookie=admin)[0] == 401          # old session ended
    assert sign_in(server, "boss@mra.test", "correct horse battery")[0] == 400   # old password dead
    assert sign_in(server, "boss@mra.test", "a brand new passphrase")[0] == 200  # lockout cleared
    with pytest.raises(auth.AuthError):
        auth.set_password(store.connect(), "ghost@x.test", "a brand new passphrase")
