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
    b = scrape.build_url(scrape.SOURCES["bikroy"], "gulshan", "sale", "apartment")
    assert b == "https://bikroy.com/en/ads/dhaka/property?query=gulshan+apartment+sale"
    assert scrape.build_url(scrape.SOURCES["bikroy"], "gulshan", "rent", "apartment") is None
    assert len(scrape.SOURCES) >= 19


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
    assert b"/static/logo.png" in urllib.request.urlopen(base + "/").read()
    assert urllib.request.urlopen(base + "/static/logo.png").read()[:4] == b"\x89PNG"
    assert json.load(urllib.request.urlopen(base + "/api/assumptions"))["growth_pct"] == 6
    assert urllib.request.urlopen(base + "/api/export.csv").read().decode("utf-8-sig").startswith("Name,Phone")
    srv.shutdown()


def test_robots_gate(monkeypatch):
    txt = "User-agent: *\nDisallow: /search\nCrawl-delay: 3\n"
    calls = []

    def fake_fetch(url, timeout=20):
        calls.append(url)
        return (200, txt) if url.endswith("/robots.txt") else (200, "<html></html>")

    monkeypatch.setattr(scrape, "fetch", fake_fetch)
    scrape._ROBOTS.clear()
    assert scrape.may_fetch("https://a.bd/search?q=x") == (False, "disallowed by robots.txt")
    assert scrape.may_fetch("https://a.bd/flats/gulshan")[0] is True
    assert scrape.crawl_delay("https://a.bd/x") == 3.0
    scrape._ROBOTS.clear()
    monkeypatch.setattr(scrape, "fetch", lambda u, t=20: (0, ""))
    assert scrape.may_fetch("https://b.bd/x")[0] is False  # unknown robots.txt means no crawl
    scrape._ROBOTS.clear()
    monkeypatch.setattr(scrape, "fetch", lambda u, t=20: (404, ""))
    assert scrape.may_fetch("https://c.bd/x")[0] is True


def test_probe_blocked_robots(monkeypatch):
    monkeypatch.setattr(scrape, "fetch", lambda u, t=20: (200, "User-agent: *\nDisallow: /\n") if u.endswith("robots.txt") else (200, ""))
    monkeypatch.setattr(scrape.time, "sleep", lambda s: None)
    scrape._ROBOTS.clear()
    rows = scrape.probe()
    assert len(rows) == len(scrape.SOURCES)
    assert all(r["verdict"].startswith(("BLOCKED", "LINK-OUT")) for r in rows)


def test_roi_math_and_rent_hidden(tmp_path):
    from property_finder import roi
    con = store.connect(tmp_path / "r.db")
    store.upsert(con, dict(source="a", url="https://a/1", title="Flat", purpose="sale", ptype="apartment", area="gulshan",
                           price=32_000_000, size_sqft=1850, beds=3))
    store.upsert(con, dict(source="a", url="https://a/2", title="Plot", purpose="sale", ptype="land", area="purbachal",
                           price=14_500_000, size_sqft=3600))
    store.upsert(con, dict(source="a", url="https://a/9", title="Rent flat", purpose="rent", ptype="apartment", area="gulshan",
                           price=90000, size_sqft=1800))  # a rent ad must never appear as a listing
    con.commit()
    rows = {r["title"]: r for r in store.query(con)}
    assert "Rent flat" not in rows and len(rows) == 2
    f = rows["Flat"]                      # 1850 sqft x 55 = 101,750 a month
    assert f["rent_est"] == 101750 and f["gross"] == round(101750 * 12 / 32e6 * 100, 2)
    assert f["net"] < f["gross"] and f["total"] > f["net"] * 5 - 1
    assert rows["Plot"]["rent_est"] is None and rows["Plot"]["total"] == round((1.06 ** 5 - 1) * 100, 1)
    assert store.query(con, min_roi=999) == []
    for i in range(5):                    # enough rent ads: measured benchmark replaces the placeholder
        store.add_rent(con, dict(url=f"https://a/r{i}", source="a", area="gulshan", price=2000 * 100, size_sqft=2000))
    assert roi.benchmarks(con)["gulshan"][0] == 100
    assert {r["title"]: r for r in store.query(con)}["Flat"]["rent_est"] == 185000
    roi.save(con, {"growth_pct": 10})
    assert roi.load(con)["growth_pct"] == 10


FLIGHT = ('<script>self.__next_f.push([1,"20:T2e,<p>Lovely flat of 1,450 sqft, 3 beds.</p>\\n"])</script>'
          '<script>self.__next_f.push([1,"9:{\\"title\\":\\"Lake flat Gulshan 2\\",\\"slug\\":\\"lake-flat-1\\",\\"price\\":18500000,'
          '\\"status\\":\\"Sale\\",\\"hide_price\\":false,\\"description\\":\\"$20\\",\\"userName\\":\\"Sample Owner\\",'
          '\\"tags\\":\\"[\\\\\\"Apartment\\\\\\",\\\\\\"Gulshan\\\\\\"]\\",\\"detail\\":{\\"bathrooms\\":\\"3\\"}}\\n"])</script>')


def test_detail_record_from_flight_data():
    r = parse.detail_record(FLIGHT, "https://x.bd/property/lake-flat-1")
    assert r["title"] == "Lake flat Gulshan 2" and r["price"] == 18500000 and r["purpose"] == "sale"
    assert r["ptype"] == "apartment" and r["baths"] == 3 and r["size_sqft"] == 1450 and r["beds"] == 3
    assert "Gulshan" in r["tags"]


def test_sitemap_crawl(tmp_path, monkeypatch):
    monkeypatch.setattr(store.connect, "__defaults__", (tmp_path / "s.db",))
    xml = ("<urlset><url><loc>https://x.bd/property/lake-flat-gulshan-1</loc><lastmod>2026-10-01</lastmod></url>"
           "<url><loc>https://x.bd/property/other-uttara-9</loc><lastmod>2026-10-02</lastmod></url>"
           "<url><loc>https://x.bd/news/gulshan-guide</loc><lastmod>2026-10-02</lastmod></url></urlset>")
    pages = {"https://x.bd/robots.txt": "User-agent: *\nAllow: /\n", "https://x.bd/sitemap.xml": xml,
             "https://x.bd/property/lake-flat-gulshan-1": FLIGHT.replace("lake-flat-1", "lake-flat-gulshan-1")}
    monkeypatch.setattr(scrape, "fetch", lambda u, t=20: (200, pages[u]) if u in pages else (404, ""))
    monkeypatch.setattr(scrape.time, "sleep", lambda s: None)
    scrape._ROBOTS.clear(); scrape._SITEMAPS.clear()
    src = {"id": "x", "sitemap": "https://x.bd/sitemap.xml", "match": "/property/"}
    res = scrape.search_sitemap(src, "gulshan", 0)
    assert res["found"] == 1 and res["new"] == 1
    assert scrape.search_sitemap(src, "gulshan", 0)["found"] == 0  # unchanged pages are not fetched twice
    rows = store.query(store.connect())
    assert rows[0]["title"] == "Lake flat Gulshan 2" and rows[0]["area"] == "gulshan"
