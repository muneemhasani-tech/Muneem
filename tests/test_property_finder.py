import pytest
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
    assert len(scrape.SOURCES) >= 8


def test_store_dedupe_and_price_drop(tmp_path):
    con = store.connect(tmp_path / "t.db")
    base = dict(title="Flat", purpose="sale", ptype="apartment", area="gulshan", price=2e7, size_sqft=1500, beds=3)
    assert store.upsert(con, {**base, "source": "a", "url": "https://a/1"})
    assert store.upsert(con, {**base, "source": "b", "url": "https://b/9"})
    assert not store.upsert(con, {**base, "source": "a", "url": "https://a/1", "price": 1.8e7})
    rows = store.query(con, sort="drop")
    assert {r["sites"] for r in rows} <= {2, 1} and any(r["dropped"] for r in rows)


def test_web_roundtrip(tmp_path, monkeypatch):
    import http.cookiejar
    from property_finder import auth
    monkeypatch.setattr(store, "DB", tmp_path / "w.db")
    monkeypatch.setattr(store.connect, "__defaults__", (tmp_path / "w.db",))
    con = store.connect()
    auth.create_user(con, "a@mra.test", "Admin", "long enough pw", role="admin", status="approved", by="test")
    con.close()
    srv = web.serve(0, open_browser=False)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_port}"
    with pytest.raises(urllib.error.HTTPError):  # signed out: no data
        urllib.request.urlopen(base + "/api/config")
    assert b"Request access" in urllib.request.urlopen(base + "/").read()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    op.open(urllib.request.Request(base + "/api/auth/login", json.dumps({"email": "a@mra.test", "password": "long enough pw"}).encode(),
                                   {"Content-Type": "application/json"}))
    assert json.load(op.open(base + "/api/config"))["areas"]["bashundhara"]
    assert json.load(op.open(base + "/api/listings"))["rows"] == []
    assert b"/static/logo-navy.png" in op.open(base + "/").read()
    assert urllib.request.urlopen(base + "/static/logo.png").read()[:4] == b"\x89PNG"
    assert json.load(op.open(base + "/api/assumptions"))["growth_pct"] == 6
    assert op.open(base + "/api/export.csv").read().decode("utf-8-sig").startswith("Name,Phone")
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
    txt = "User-agent: *\nAllow: /\n\nUser-agent: ClaudeBot\nDisallow: /\n"
    monkeypatch.setenv("CLAUDECODE", "1")
    assert scrape.may_fetch("https://a.bd/flats")[0] is False  # an AI agent at the wheel obeys AI-bot bans
    monkeypatch.delenv("CLAUDECODE")
    scrape._ROBOTS.clear()
    assert scrape.may_fetch("https://a.bd/flats")[0] is True   # the user's own runs follow the * rules
    scrape._ROBOTS.clear()
    monkeypatch.setattr(scrape, "fetch", lambda u, t=20: (0, ""))
    assert scrape.may_fetch("https://b.bd/x")[0] is False  # unknown robots.txt means no crawl
    scrape._ROBOTS.clear()
    monkeypatch.setattr(scrape, "fetch", lambda u, t=20: (404, ""))
    assert scrape.may_fetch("https://c.bd/x")[0] is True


def test_probe_blocked_robots(monkeypatch, tmp_path):
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    monkeypatch.setattr(scrape, "fetch", lambda u, t=20: (200, "User-agent: *\nDisallow: /\n") if u.endswith("robots.txt") else (200, ""))
    monkeypatch.setattr(scrape.time, "sleep", lambda s: None)
    scrape._ROBOTS.clear()
    monkeypatch.setattr(store.connect, "__defaults__", (tmp_path / "p.db",))
    rows = scrape.probe()
    from property_finder import websearch
    assert len(rows) == len(scrape.SOURCES) + len(websearch.QUERIES)
    assert all(r["verdict"].startswith(("BLOCKED", "NEEDS A SEARCH API KEY")) for r in rows)


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


def test_web_search_results_become_listings(tmp_path, monkeypatch):
    from property_finder import websearch
    monkeypatch.setattr(store.connect, "__defaults__", (tmp_path / "w.db",))
    monkeypatch.setattr(scrape, "fetch", lambda u, t=20: (404, ""))
    monkeypatch.setattr(websearch.time, "sleep", lambda s: None)
    monkeypatch.setenv("SERPER_API_KEY", "test-key")
    hits = [
        {"title": "3 bed flat for sale in Gulshan 2 | Facebook", "url": "https://www.facebook.com/groups/1/posts/2",
         "snippet": "1850 sqft, south facing, price 3.2 crore. Call 01711-223344", "date": ""},
        {"title": "Need a flat in Gulshan", "url": "https://www.facebook.com/groups/1/posts/3", "snippet": "Looking for 3 bed, sale", "date": ""},
        {"title": "Flat for sale in Mirpur", "url": "https://www.facebook.com/groups/1/posts/4", "snippet": "1200 sqft", "date": ""},
    ]
    calls = []
    monkeypatch.setattr(websearch, "run_query", lambda p, k, q: (calls.append(q), (200, hits))[1])
    monkeypatch.setattr(websearch, "QUERIES", [{"id": "fb_groups", "name": "Facebook groups", "q": "site:facebook.com/groups \"{area}\" flat sale"}])
    res = websearch.search_web(["gulshan"])
    assert calls == ['site:facebook.com/groups "Gulshan" flat sale'] and res[0]["new"] == 1
    r = store.query(store.connect())[0]
    assert r["title"] == "3 bed flat for sale in Gulshan 2" and r["price"] == 3.2e7 and r["phone"] == "01711223344"
    assert r["found_via"].startswith("Google (Serper): site:facebook.com/groups") and "1850 sqft" in r["snippet"]
    assert websearch.search_web(["gulshan"])[0]["new"] == 0 and len(calls) == 1  # same query not repeated within 20h
    monkeypatch.delenv("SERPER_API_KEY")
    assert "API key" in websearch.search_web(["gulshan"])[0]["error"]


def test_bangla_and_fancy_text():
    assert parse.facts("𝟐𝟒𝟐𝟎 𝐒𝐅𝐓 দাম ২ কোটি ৫০ লাখ")["price"] == 2.5e7
    assert parse.facts("𝟐𝟒𝟐𝟎 𝐒𝐅𝐓")["size_sqft"] == 2420
    assert parse.facts("৳ ৩.৫ কোটি")["price"] == 3.5e7


def test_search_result_filter():
    from property_finder.websearch import is_listing
    assert is_listing("https://www.facebook.com/groups/1/posts/2/")
    assert is_listing("https://www.facebook.com/marketplace/item/123/")
    assert not is_listing("https://www.facebook.com/groups/1/")                       # a whole group
    assert is_listing("https://bikroy.com/en/ad/3-bed-flat-for-sale-gulshan-for-sale-dhaka")
    assert not is_listing("https://bikroy.com/bn/gulshan/houses-apartments-for-sale")  # category page
    assert not is_listing("https://www.zameen.com/Flats_Apartments/Karachi_Gulshan_e_Iqbal-1.html")
    assert not is_listing("https://www.assuregroupbd.com/property-for-sale")
    assert not is_listing("https://x.com/flats-in-gulshan-123", "18+ Flats for Sale in Gulshan")
    assert not is_listing("https://www.bproperty.com/property/x-1")                     # already crawled directly


def test_web_hit_filters():
    from property_finder import websearch as w
    fb = {"id": "fb_groups", "host": r"(^|\.)facebook\.com$", "engine_label": "x"}
    hit = {"title": "Flat for sale in Gulshan 2", "url": "https://www.facebook.com/groups/1/posts/2", "snippet": "3 bed 2456 sqft, price 3 crore"}
    assert w.to_listing(hit, fb, "q", "gulshan")["size_sqft"] == 2456
    assert w.to_listing({**hit, "url": "https://bikroy.com/x"}, fb, "q", "gulshan") is None  # wrong host
    assert w.to_listing({**hit, "title": "Flat for sale in Gulshan e Iqbal"}, fb, "q", "gulshan") is None
    dev = {"id": "dev_rangs", "host": r"rangsproperties\.com$", "engine_label": "x"}
    page = {"title": "Diorama in Gulshan", "snippet": "Project", "url": "https://rangsproperties.com/projects/Diorama"}
    assert w.to_listing(page, dev, "q", "gulshan")  # no "for sale" needed for a developer
    assert w.to_listing({**page, "url": "https://rangsproperties.com/about-us"}, dev, "q", "gulshan") is None


def test_absurd_values_are_kept_and_flagged(tmp_path):
    con = store.connect(tmp_path / "f.db")
    r = {"source": "s", "url": "https://x/1", "title": "t", "purpose": "sale", "ptype": "apartment", "area": "gulshan",
         "price": 1250.0, "size_sqft": 2.0}
    assert store.upsert(con, r)
    row = con.execute("SELECT price, size_sqft, data_flags FROM listings").fetchone()
    assert row["price"] == 1250 and row["size_sqft"] == 2  # shown as found
    assert "price 1,250 BDT looks absurd" in row["data_flags"] and "size 2 sqft looks absurd" in row["data_flags"]
    r2 = dict(r, url="https://x/2", price=None, size_sqft=None)
    store.upsert(con, r2)
    assert "price missing" in con.execute("SELECT data_flags FROM listings WHERE url='https://x/2'").fetchone()[0]


def test_job_survives_a_crashing_source(tmp_path, monkeypatch):
    monkeypatch.setattr(store.connect, "__defaults__", (tmp_path / "j.db",))
    monkeypatch.setattr(scrape.time, "sleep", lambda s: None)
    def boom(*a, **k):
        raise RuntimeError("database is locked")
    monkeypatch.setattr(scrape, "search_list", boom)
    job = scrape.Job()
    job.start(["gulshan"], ["apartment"], ["aabason"], web=False, benchmark=False)
    import time as _t
    end = _t.monotonic() + 10  # sleep is patched out, so wait on the clock
    while job.snapshot()["running"] and _t.monotonic() < end:
        pass
    s = job.snapshot()
    assert not s["running"] and "crashed: database is locked" in s["results"][0]["error"]


def test_scout_plan_dedupe_and_filters(tmp_path, monkeypatch):
    import datetime as dt
    from property_finder import scout, websearch as w
    a, b = scout.plan(dt.date(2026, 11, 18)), scout.plan(dt.date(2026, 11, 19))
    assert len(a) == 2 * len(scout.AREAS) + len(scout.CONF["portal_daily"]) + scout.CONF["extra_per_day"]
    assert not {x["q"] for x in a[16:]} & {x["q"] for x in b[16:]}          # a different rotating slice each day
    assert w.is_listing("https://www.bdhousing.com/details/245411/2390-sqft-used-apartment-banani", "2390 sqft", portals_ok=True)  # not "housing.com"
    assert w.is_listing("https://bikroy.com/gulshan/houses-apartments-for-sale/3bdrm-apartment-in-gulshan", portals_ok=True)
    assert not w.is_listing("https://bikroy.com/gulshan/houses-apartments-for-sale", portals_ok=True)
    hits = [{"title": "Flat sale in Gulshan 2", "url": "https://www.facebook.com/groups/1/posts/2/",
             "snippet": "Ready flat for sale at North Gulshan, 2650 sft, 4th floor, 3 bed, price 3.5 crore, call 01711348757 now please"},
            {"title": "Flat sale Gulshan North", "url": "https://www.facebook.com/groups/9/posts/8/",       # same ad, another group
             "snippet": "Ready flat for sale at North Gulshan, 2650 sft, 4th floor, 3 bed, price 3.5 crore, call 01711348757 now please"}]
    monkeypatch.setenv("SERPER_API_KEY", "k")
    monkeypatch.setattr(w, "run_query", lambda p, k, q, tbs="": (200, hits))
    r1 = scout.run(None, out=str(tmp_path / "d1"), extra=0, day=dt.date(2026, 11, 18))
    assert r1["new"] == 1 and r1["duplicates"] >= 1                          # the repost is caught
    r2 = scout.run(None, out=str(tmp_path / "d2"), extra=0, day=dt.date(2026, 11, 19), seen=r1["seen"])
    assert r2["new"] == 0                                                     # nothing repeats the next day


def test_scout_seen_file_calls_and_drafts(tmp_path):
    import datetime as dt
    from property_finder import scout
    day = dt.date(2026, 11, 20)
    p = tmp_path / "seen.tsv"
    p.write_text("aaaaaaaa\t2026-11-19\nbbbbbbbb\t2026-09-01\n", encoding="utf-8")
    _, keep = scout.read_seen(str(p), day)
    assert list(keep) == ["aaaaaaaa"]                                   # old hashes are forgotten, so the file stays small
    row = lambda **k: {"title": "Flat sale", "snippet": "", "area": "gulshan", "type": "apartment", "phone": "", "price_bdt": 3e7,
                       "size_sqft": 1800, "gross_yield_pct": "", **k}
    rows = [row(phone="017", snippet="owner direct"), row(phone="017"), row(phone="018"), row()]
    calls = scout.top_calls(rows)
    assert [r["phone"] for r in calls] == ["017", "018", ""] and calls[0]["snippet"] == "owner direct"   # one call per number
    en, bn = scout.drafts(calls[0])
    assert "MRA Real Estate" in en and "গুলশান" in bn and "Flat sale" in en
    assert scout.flag(row(price_bdt="", size_sqft="")) == "price missing - ask seller; size missing - ask seller"


def test_scout_fresh_mode_asks_google_for_the_last_day(tmp_path, monkeypatch):
    import datetime as dt
    from property_finder import scout, websearch as w
    seen = []
    monkeypatch.setenv("SERPER_API_KEY", "k")
    monkeypatch.setattr(w, "run_query", lambda p, k, q, tbs="": (seen.append(tbs), (200, []))[1])
    scout.run(None, out=str(tmp_path), extra=4, day=dt.date(2026, 11, 18), fresh=True)
    assert "qdr:d" in seen and "" in seen  # Facebook searches ask for the last day; portal searches are not forced to
    assert seen.count("qdr:d") < len(seen)


def test_scout_rejects_foreign_and_non_property_results():
    from property_finder import websearch as w
    spec = {"id": "Facebook groups", "engine_label": "Google", "portals_ok": True}
    bad = [("Flat Available For Sale Gulshan-e-Maymar Sector X-4", "flat sale karachi"),
           ("2 BHK Semi-Furnished Flat for Sale in Purbachal, Rajarhat", "flat sale"),
           ("Price Not Fixt Basey Pore Ache Ami New Monitor Kinsi", "monitor Gulshan sale")]
    for t, sn in bad:
        assert w.to_listing({"title": t, "url": "https://www.facebook.com/groups/1/posts/2/", "snippet": sn}, spec, "q", "gulshan") is None
    ok = w.to_listing({"title": "Flat sale in Gulshan 2", "url": "https://www.facebook.com/groups/1/posts/3/",
                       "snippet": "Ready flat for sale at Gulshan, 2650 sft, price 3.5 crore"}, spec, "q", "gulshan")
    assert ok and ok["price"] == 35_000_000


def test_scout_seen_file_holds_no_phone_derived_hash(tmp_path, monkeypatch):
    import datetime as dt
    from property_finder import scout, websearch as w
    hit = {"title": "Flat sale in Gulshan 2", "url": "https://www.facebook.com/groups/1/posts/2/",
           "snippet": "Ready flat for sale at Gulshan, 2650 sft, price 3.5 crore, call 01711348757 now please"}
    monkeypatch.setenv("SERPER_API_KEY", "k")
    monkeypatch.setattr(w, "run_query", lambda p, k, q, tbs="": (200, [hit]))
    r = scout.run(None, out=str(tmp_path), extra=0, day=dt.date(2026, 11, 18), seen=None)
    keys = {line.split("\t")[0] for line in open(r["seen"]).read().splitlines()}
    assert scout._h("u" + hit["url"]) in keys and len(keys) >= 2
    phone_fp = scout._h("p:01711348757:gulshan:2650")
    assert phone_fp not in keys


def test_scout_every_portal_is_searched_every_day():
    import datetime as dt
    from property_finder import scout
    for n in range(14):
        labels = {x["label"] for x in scout.plan(dt.date(2026, 11, 1) + dt.timedelta(days=n))}
        assert {"Bproperty", "Bikroy", "bdHousing", "Bdstall"} <= labels, n
    assert len(scout.plan(dt.date(2026, 11, 20))) == 2 * len(scout.AREAS) + 4 + scout.CONF["extra_per_day"] == 26


def test_scout_writes_a_small_stats_file_for_the_manager(tmp_path, monkeypatch):
    import datetime as dt
    import json as _j
    from property_finder import scout, websearch as w
    hit = {"title": "Flat sale in Gulshan 2", "url": "https://www.facebook.com/groups/1/posts/2/",
           "snippet": "Ready flat for sale at Gulshan, 2650 sft, price 3.5 crore, call 01711348757 now please"}
    monkeypatch.setenv("SERPER_API_KEY", "k")
    monkeypatch.setattr(w, "run_query", lambda p, k, q, tbs="": (200, [hit]) if "Gulshan" in q else (200, []))
    r = scout.run(None, out=str(tmp_path), extra=0, day=dt.date(2026, 11, 18), enrich_top=0)
    st = _j.loads(open(r["stats"]).read())
    assert st["new"] == 1 and st["with_phone"] == 1 and st["with_price"] == 1 and st["memory_used"] is False
    assert st["zero_result_searches"] and not st["errored_searches"] and len(open(r["stats"]).read()) < 4000


def test_scout_absurd_price_does_not_win_a_call_slot():
    from property_finder import scout
    row = lambda **k: {"title": "Flat sale", "snippet": "", "area": "gulshan", "type": "apartment", "phone": "", "price_bdt": "",
                       "size_sqft": 1800, "gross_yield_pct": "", **k}
    calls = scout.top_calls([row(phone="011", price_bdt=5000), row(phone="012", price_bdt=25_000_000)], n=1)
    assert calls[0]["phone"] == "012"


def test_price_word_formats():
    from property_finder import parse
    assert parse.parse_price("Total Price- 2.00.00.000/-") == 2e7
    assert parse.parse_price(parse.norm("দাম 1,20,00,000 টাকা")) == 1.2e7
    assert parse.parse_price("asking price 2.5 crore") == 2.5e7
    assert parse.parse_price("Price: 01711348757") is None  # a phone, not a price


def test_title_price_beats_snippet():
    from property_finder import websearch
    hit = {"title": "3 Katha Plot Sale Purbachal Sector-2 | 26000000", "url": "https://www.bproperty.com/property/3-katha-plot-sale-purbachal",
           "snippet": "Purbachal; 3 Katha Plot Sale Purbachal Sector-2. Residential Sale. Flat with in Baridhara Diplomatic. BDT 10,000."}
    r = websearch.to_listing(hit, {"id": "Bproperty", "engine_label": "Google", "portals_ok": True}, "q", "purbachal")
    assert r and r["price"] == 26_000_000


def test_crore_typos_and_per_katha():
    from property_finder import parse, websearch
    assert parse.parse_price("Price:- 1 Core 60 Lakh") == 1.6e7
    assert parse.parse_price(parse.norm("1কটি 25লক্ষ টাকায়")) == 1.25e7
    hit = {"title": "North facing 10 katha sale at Rajuk Purbachal sector 5", "url": "https://www.bproperty.com/property/north-facing-10-katha",
           "snippet": "Sector #05, Rajuk Purbachal, Dhaka. BDT 90,00,000 per katha."}
    r = websearch.to_listing(hit, {"id": "Bproperty", "engine_label": "Google", "portals_ok": True}, "q", "purbachal")
    assert r and r["price"] == 9e7


def test_absurd_price_per_sqft_is_flagged_and_loses_call_slot():
    from property_finder import scout
    bad = {"price_bdt": 1731600000, "size_sqft": 1332, "phone": "01778617330", "title": "Used Flat for Sale at Bashundhara R/A",
           "snippet": "", "gross_yield_pct": "", "type": "apartment"}
    good = {**bad, "price_bdt": 17316000, "phone": "01711111111", "title": "Flat sale"}
    assert not scout.plausible_price(bad) and scout.plausible_price(good)
    assert scout.top_calls([bad, good], 1)[0] is good
    assert "per sqft" in scout.flag(bad)


def test_size_restated_as_per_sqft_is_not_a_rate():
    from property_finder import parse
    f = parse.facts("SOUTH/EAST CORNER PLOT 3380 SQFT APARTMENT FOR SALE IN BASHUNDHARA RA Building G+9 Double Unit 3380/SQFT 15 Katha Land")
    assert f["size_sqft"] == 3380 and f["price"] is None
    assert parse.facts("1500 sqft flat, 12,000 per sqft")["price"] == 18_000_000


def test_crore_then_bare_lakh_figure():
    from property_finder import parse
    assert parse.parse_price("Flat Sell Gulshan-1 Nearby lake 3 cr 80 ...") == 3.8e7
    assert parse.parse_price("price 1.20 cr 2 car parking") == 1.2e7
    assert parse.parse_price("3 cr 5 katha plot") == 3e7


def test_weekly_summary_builds(tmp_path):
    import csv
    from property_finder import weekly, scout
    rows = [{"date": f"2026-11-2{i % 3}", "area": a, "type": t, "title": f"{t} in {a}", "price_bdt": 20_000_000 if i % 2 else "",
             "size_sqft": 1500, "price_per_sqft": "", "gross_yield_pct": "", "phone": "01711111111" if i % 3 == 0 else "",
             "site": "Facebook groups", "url": f"https://x/{i}", "snippet": "", "query": "", "fingerprints": ""}
            for i, (a, t) in enumerate([("gulshan", "apartment"), ("uttara", "land"), ("banani", "house"), ("gulshan", "land")])]
    p = tmp_path / "leads.csv"
    with open(p, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=scout.COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    out = tmp_path / "w.html"
    assert weekly.write([str(p)], str(out))["rows"] == 4
    h = out.read_text(encoding="utf-8")
    assert "new properties" in h and "<script" not in h and "<style" not in h
    page = weekly.onepager_html(weekly.load([str(p)]), {})
    assert "<svg" in page and "How a lead reaches you" in page and "01711111111" not in page  # aggregates only, safe to forward
    assert "cid:att0" in weekly.email_html(weekly.load([str(p)]), "cid:att0")
    empty = tmp_path / "empty.csv"
    empty.write_text(",".join(scout.COLS) + "\n", encoding="utf-8")
    assert weekly.make([str(empty)], [], str(tmp_path / "e"))["rows"] == 0


def test_google_wrapped_bikroy_ads_are_listings_but_category_pages_are_not():
    from property_finder import websearch as w
    g = "https://www.google.com/goto?url=CAESpAEBxCJF1"
    assert w.is_listing(g, "3 Katha Near 300 Feet Jalshari Plot Sale Rajuk Purbachal", False, True)
    assert w.is_listing(g, "4 Bedroom Apartment in Gulshan 2 Estate for sale", False, True)
    assert not w.is_listing(g, "4 Bedrooms Flat for sale in basundhara - Dhaka", False, True)
    assert not w.is_listing(g, "Property in Gulshan for rent & sale ...", False, True)
    assert not w.is_listing(g, "3 Katha Plot Sale Purbachal", False, False)  # only for portal searches


def test_site_directory_promotes_after_two_good_weeks_and_scout_uses_only_active(tmp_path, monkeypatch):
    import datetime as dt, json
    from property_finder import sites, websearch, scout
    assert sites.clean("www.PBazaar.com") == "pbazaar.com"
    assert sites.clean("bikroy.com") is None and sites.clean('evil.com" OR site:x') is None
    hit = lambda i: {"title": f"3 Katha Plot Sale Gulshan {i}", "url": f"https://pbazaar.com/listing/plot-sale-gulshan-{i:04d}",
                     "snippet": "3 katha plot for sale in Gulshan, price 5 crore"}
    monkeypatch.setenv("SERPER_API_KEY", "k")
    monkeypatch.setattr(websearch, "run_query", lambda prov, key, q, tbs="": (200, [hit(i) for i in range(4)] if "site:" in q else []))
    reg = tmp_path / "r.json"
    reg.write_text(json.dumps(sites.update(None, [], ["pbazaar.com"], dt.date(2026, 11, 27))), encoding="utf-8")
    assert sites.active(str(reg)) == []  # one good week is not enough
    reg.write_text(json.dumps(sites.update(str(reg), [], [], dt.date(2026, 12, 4))), encoding="utf-8")
    assert sites.active(str(reg)) == ["pbazaar.com"]
    p = scout.plan(dt.date(2026, 12, 5), sites=sites.active(str(reg)) + ['bad" OR site:x'])
    assert len(p) == 26 and sum(x["label"].startswith("Directory:") for x in p) == 1
    assert all("bad" not in x["q"] for x in p)


def test_foreign_and_discussion_posts_are_dropped_but_urgent_sellers_kept():
    from property_finder import websearch as w
    bad = ["1350 sqft 3bhk flat sale near andal airport", "Luxury Duplex 110 gaz only 78 lakh near kanker Khera",
           "PAC তেহ জমির দাম এত বেশি হবার কারন কী?", "বসুন্ধরায় ফ্ল্যাট বিক্রি করার জন্য কিছু কমিশন ভিত্তিক মিডিয়া দরকার।"]
    assert all(w.FOREIGN.search(t) or w.WANTED.search(t) for t in bad)
    assert not w.WANTED.search("জরুরি ভিত্তিতে টাকার দরকার পূর্বাচলে 3 কাঠা প্লট বিক্রি করা হবে।")


def test_associate_emails_route_by_area_and_type(tmp_path):
    import csv, json
    from property_finder import mailer, scout
    rows = [{"date": "2026-11-25", "area": a, "type": t, "title": f"{t} sale {a} {i}", "price_bdt": 15_000_000, "size_sqft": 1500,
             "price_per_sqft": "", "gross_yield_pct": "", "phone": "01711111111" if i == 0 else "", "site": "Facebook groups",
             "url": f"https://x/{i}", "snippet": "", "query": "", "fingerprints": ""}
            for i, (a, t) in enumerate([("bashundhara", "apartment"), ("bashundhara", "house"), ("gulshan", "land"), ("dhanmondi", "house")])]
    p = tmp_path / "leads.csv"
    with open(p, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=scout.COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    routes = tmp_path / "r.json"
    routes.write_text(json.dumps({"associates": [
        {"name": "Owner", "email": "o@example.com", "all": True, "focus": {"areas": ["gulshan"], "types": ["land"]}},
        {"name": "A", "email": "a@example.com", "areas": ["bashundhara"], "types": ["apartment", "land"]},
        {"name": "B", "email": "b@example.com", "areas": ["dhanmondi"], "types": []},
        {"name": "Bad", "email": "not-an-email", "areas": []}]}), encoding="utf-8")
    m = {x["name"]: x for x in mailer.make(str(routes), [str(p)], str(tmp_path / "out"), "25 Nov 2026")}
    assert set(m) == {"Owner", "A", "B"} and (m["Owner"]["count"], m["A"]["count"], m["B"]["count"]) == (4, 2, 1)  # A's land includes land with building
    h = (tmp_path / "out" / m["A"]["html"]).read_text(encoding="utf-8")
    assert "wa.me/8801711111111?text=" in h and "<script" not in h and "Land with building" in h
    assert mailer._note("price missing - ask seller; size missing - ask seller") == "Ask the seller for: price, size"


def test_property_type_reads_title_first_and_bangla():
    from property_finder import parse
    assert parse.ptype_of("জমি বিক্রয় | বসুন্ধরা আবাসিক এলাকা") == "land"
    assert parse.ptype_of("ফ্ল্যাট বিক্রয়") == "apartment"
    assert parse.ptype_of("বাড়ি বিক্রি হবে") == "house"
    assert parse.ptype_of("Flat with 3 katha land") == "apartment"
    assert parse.ptype_of("Ready flat sale", "Land: 3 katha, G+6") == "apartment"
    assert parse.ptype_of("Urgent sale Purbachal", "3 katha plot, sector 18") == "land"


def test_baridhara_area_and_multi_rule_routes(tmp_path):
    import json
    from property_finder import scrape, mailer
    assert scrape._area_in("3 katha plot sale Baridhara Diplomatic Zone", None) == "baridhara"
    assert scrape._area_in("Flat sale Baridhara J Block", None) != "baridhara"
    assert scrape._area_in("5 katha plot sale Baridhara DOHS", None) != "baridhara"
    assert scrape._area_in("ঢাকা বারিধারা ডিওএইচএস প্লট বিক্রি", None) != "baridhara"
    assert scrape._area_in("Plot in Baridhara Diplomatic Zone, near DOHS", None) == "baridhara"
    assert any('"Baridhara Diplomatic"' in x["q"] for x in __import__("property_finder.scout", fromlist=["plan"]).plan(__import__("datetime").date(2026, 11, 26)))
    r = tmp_path / "r.json"
    r.write_text(json.dumps({"associates": [{"name": "S", "email": "s@example.com", "rules": [
        {"areas": ["gulshan"], "types": ["apartment"]}, {"areas": ["uttara"], "types": ["apartment", "land"]}]}]}), encoding="utf-8")
    a = mailer.load_routes(str(r))[0]
    rows = [{"area": "gulshan", "type": "apartment"}, {"area": "gulshan", "type": "land"}, {"area": "uttara", "type": "house"}]
    assert mailer.mine(rows, a) == [rows[0], rows[2]]


def test_sendmail_posts_each_email_and_skips_empty(tmp_path, monkeypatch):
    import json
    from property_finder import sendmail
    (tmp_path / "a.html").write_text("<p>a</p>", encoding="utf-8")
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "manifest.json").write_text(json.dumps([
        {"to": "a@example.com", "subject": "MRA fresh leads x", "html": "a.html", "text": "a.txt", "count": 3, "all": False},
        {"to": "b@example.com", "subject": "MRA fresh leads y", "html": "a.html", "text": "a.txt", "count": 0, "all": False}]), encoding="utf-8")
    sent = []
    monkeypatch.setattr(sendmail, "post", lambda url, p, timeout=60: sent.append(p) or {"ok": True, "sent": True})
    res = sendmail.send_manifest(str(tmp_path / "manifest.json"), url="https://script.google.com/macros/s/x/exec", pause=0)
    assert [p["to"] for p in sent] == ["a@example.com"] and res[1]["skipped"]
    assert not sendmail.send_manifest(str(tmp_path / "manifest.json"), url="")[0]["ok"]


def test_area_rules_rajuk_purbachal_badda_and_near():
    from property_finder.scrape import area_of
    assert area_of("I Ext South Lake Face 3 Katha Plot Sale Tk. 98 lac", "near Purbachal 300 feet") == "bashundhara"
    assert area_of("বাড়ি বিক্রি হবে** লোকেশন: গুলশান গুুদারাঘাট বাড্ডা লিংক") is None
    assert area_of("3 Katha Plot Sale Purbachal Sector-2") == "purbachal"
    assert area_of("রাজউক পূর্বাচলে 3 কাঠা প্লট বিক্রি করা হবে") == "purbachal"
    assert area_of("Purbachal American City Plot") is None and area_of("পূর্বাচল বানিজ্য মেলার পাশেই তিন কাঠার প্লট") is None
    assert area_of("Flat for sale", "Gulshan 2 road 59, near Banani") == "gulshan"
    assert area_of("Plot sale", "Rajuk Purbachal sector 18, 10 minutes from Bashundhara") == "purbachal"


def test_facebook_group_name_is_not_the_area():
    from property_finder.scrape import area_of
    assert area_of("3 +3 = 6 কাঠার প্লট বিক্রি করা হবে।",
                   "Gulshan 1/ 2 Flat, Land Buy & Sale (গুলশানে ফ্ল্যাট/ জমি ক্রয়-বিক্রয়) ... দাম -কোটি 17 লাখ টাকা।") is None
    assert area_of("3 +3 = 6 কাঠার প্লট বিক্রি করা হবে।", "লোকেশন : উত্তরা সেক্টর 17, ব্লক - বি") == "uttara"
