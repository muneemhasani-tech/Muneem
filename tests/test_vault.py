import base64
import hashlib
import json
import zlib

import pytest
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from property_finder import store, vault


def _vault_of(html: str) -> dict:
    a = html.index('id="vault">') + len('id="vault">')
    return json.loads(html[a:html.index("</script>", a)])


def _open(v, email, pw):
    m = next(x for x in v["members"] if x["id"] == vault.member_id(email))
    key = hashlib.pbkdf2_hmac("sha256", pw.encode(), base64.b64decode(m["salt"]), v["iter"], 32)
    info = json.loads(AESGCM(key).decrypt(base64.b64decode(m["iv"]), base64.b64decode(m["ct"]), None))
    raw = AESGCM(base64.b64decode(info["k"])).decrypt(base64.b64decode(v["iv"]), base64.b64decode(v["data"]), None)
    return info, json.loads(zlib.decompress(raw))


def test_vault_hides_data_and_opens_only_with_the_password(tmp_path, monkeypatch):
    monkeypatch.setattr(vault, "ITER", 1000)  # speed only
    con = store.connect(tmp_path / "v.db")
    store.upsert(con, {"source": "bproperty", "url": "https://secret.example/listing/777", "title": "Hidden Flat", "purpose": "sale",
                       "ptype": "apartment", "area": "gulshan", "price": 30_000_000.0, "size_sqft": 1800.0, "phone": "01712345678", "poster": "Owner"})
    con.commit()
    out = tmp_path / "index.html"
    info = vault.build(con, out, "Boss@MRA.test", "Boss", "twelve chars ok!")
    html = out.read_text(encoding="utf-8")
    assert info["listings"] == 1
    for secret in ("secret.example", "01712345678", "Hidden Flat", "Boss@MRA.test", "boss@mra.test"):
        assert secret not in html
    v = _vault_of(html)
    who, data = _open(v, "boss@mra.test", "twelve chars ok!")
    assert who["role"] == "admin" and data["rows"][0][12] == "https://secret.example/listing/777" and data["rows"][0][8] == "01712345678"
    with pytest.raises(InvalidTag):
        _open(v, "boss@mra.test", "twelve chars ok?")


def test_vault_needs_a_strong_admin_password(tmp_path):
    with pytest.raises(ValueError):
        vault.build(store.connect(tmp_path / "w.db"), tmp_path / "x.html", "a@b.co", "A", "short")
