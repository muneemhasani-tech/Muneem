import json
import threading
import urllib.request

from property_finder import parse, scrape, store, web

CARDS = """<html><body>
<a href="/en/ad/flat-1"><img src="/i.jpg"><h2>3 Bed Apartment for sale in Gulshan 2</h2> 2,100 sqft 3 beds 3 baths ৳ 2.5 Crore by Owner 01711-223344</a>
<a href="/en/ad/flat-2">Spacious 1800 sq ft flat in Banani, 3 bedrooms, Tk 1,20,00,000 agent Rangs Properties</a>
<a href="/about">About us and many other words to pass the length check but no price anywhere here</a></body></html>"""
LD = """<script type="application/ld+json">{"@type":"ItemList","itemListElement":[{"name":"Plot in Purbachal","url":"/p/9","offers":{"price":"9500000"}}]}</script>"""


def test_card_extraction():
    rows = {r["url"]: r for r in parse.extract(CARDS, "https://x.bd/")}
    a = rows["https://x.bd/en/ad/flat-1"]
    assert a["price"] == 2.5e7 and a["size_sqft"] == 2100 and a["beds"] == 3 and a["is_owner"] == 1
    assert a["phone"] == "01711223344" and a["image"] == "https://x.bd/i.jpg"
    assert len(rows) == 2


def test_jsonld_extraction():
    r = parse.extract(LD, "https://x.bd/")[0]
    assert r["price"] == 9500000 and r["url"] == "https://x.bd/p/9"


def test_price_units():
    assert parse.parse_price("৳ 85 lakh") == 8.5e6
    assert parse.parse_price("Tk 45,000") == 45000


def test_url_building():
    b = scrape.build_url(scrape.SOURCES["bproperty"], "gulshan", "sale", "apartment")
    assert b == "https://www.bproperty.com/en/dhaka/flats-apartments-for-sale-in-gulshan/"
    assert scrape.build_url(scrape.SOURCES["tolet"], "gulshan", "sale", "apartment") is None
    assert len(scrape.SOURCES) >= 20


def test_store_dedupe_and_price_drop(tmp_path):
    con = store.connect(tmp_path / "t.db")
    base = dict(title="Flat", purpose="sale", ptype="apartment", area="gulshan", price=2e7, size_sqft=1500, beds=3)
    assert store.upsert(con, {**base, "source": "a", "url": "https://a/1"})
    assert store.upsert(con, {**base, "source": "b", "url": "https://b/9"})
    assert not store.upsert(con, {**base, "source": "a", "url": "https://a/1", "price": 1.8e7})
    rows = store.query(con, sort="drop")
    assert {r["sites"] for r in rows} <= {2, 1} and any(r["dropped"] for r in rows)


def test_web_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB", tmp_path / "w.db")
    monkeypatch.setattr(store.connect, "__defaults__", (tmp_path / "w.db",))
    srv = web.serve(0, open_browser=False)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_port}"
    assert json.load(urllib.request.urlopen(base + "/api/config"))["areas"]["bashundhara"]
    assert json.load(urllib.request.urlopen(base + "/api/listings"))["rows"] == []
    assert urllib.request.urlopen(base + "/api/export.csv").read().decode("utf-8-sig").startswith("Name,Phone")
    srv.shutdown()
