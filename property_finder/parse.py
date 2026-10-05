"""Site-agnostic listing extraction. Tries embedded JSON first, then falls back to link-card text."""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from urllib.parse import urljoin

PHONE = re.compile(r"(?<!\d)(?:\+?88)?[\s-]?(01[3-9][\s-]?\d{2}[\s-]?\d{6})(?!\d)")
PRICE = re.compile(r"(?:৳|tk\.?|bdt|taka)\s*([\d,]+(?:\.\d+)?)\s*(crore|cr|lakh|lac|lakhs|k)?|([\d,]+(?:\.\d+)?)\s*(crore|cr|lakh|lac|lakhs)\b|([\d,]{6,})\s*(?:tk|bdt|taka)", re.I)
SIZE = re.compile(r"([\d,]+(?:\.\d+)?)\s*(?:sq\.?\s?-?ft|sqft|sft|square\s*feet)", re.I)
BEDS = re.compile(r"(\d{1,2})\s*(?:bed(?:room)?s?|br\b)", re.I)
BATHS = re.compile(r"(\d{1,2})\s*(?:bath(?:room)?s?)", re.I)
MULT = {"crore": 1e7, "cr": 1e7, "lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "k": 1e3}


def clean_phone(s: str) -> str:
    m = PHONE.search(s or "")
    return "0" + re.sub(r"[\s-]", "", m.group(1))[1:] if m else ""


def parse_price(text: str) -> float | None:
    for m in PRICE.finditer(text or ""):
        num, unit = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4)) if m.group(3) else (m.group(5), None)
        try:
            v = float(num.replace(",", "")) * MULT.get((unit or "").lower(), 1)
        except ValueError:
            continue
        if v >= 1000:
            return v
    return None


PPSF = re.compile(r"per\s*(?:sft|sqft|sq\.?\s*ft)[^\d]{0,12}([\d,]+(?:\.\d+)?)|([\d,]+(?:\.\d+)?)\s*(?:tk|bdt|taka|৳)?\s*(?:/|per)\s*(?:sft|sqft|sq\.?\s*ft)", re.I)


def facts(text: str) -> dict:
    size, beds, baths = SIZE.search(text), BEDS.search(text), BATHS.search(text)
    low = text.lower()
    price = parse_price(text)
    pp = PPSF.search(text)
    if pp and size:  # "15,000 per sqft" with a known size: the total is what matters
        rate = float((pp.group(1) or pp.group(2)).replace(",", ""))
        if 1000 <= rate <= 100000 and (price is None or price == rate):
            price = rate * float(size.group(1).replace(",", ""))
    return {
        "price": price,
        "size_sqft": float(size.group(1).replace(",", "")) if size else None,
        "beds": int(beds.group(1)) if beds else None,
        "baths": int(baths.group(1)) if baths else None,
        "phone": clean_phone(text),
        "is_owner": 1 if re.search(r"\bowner\b|by owner|individual", low) else (0 if re.search(r"agent|agency|developer|realtor|properties ltd", low) else None),
    }


class _Cards(HTMLParser):
    """Collects <a href> blocks with their visible text and any <img src>."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.cards, self._cur, self.jsonld, self.next_data, self._script = [], None, [], [], None
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "title":
            self._in_title = True
        elif tag == "script":
            t = (a.get("type") or "").lower()
            self._script = "ld" if "ld+json" in t else "json" if (a.get("id") == "__NEXT_DATA__" or "json" in t) else None
            self._buf = []
        elif tag == "a" and a.get("href") and self._cur is None:
            self._cur = {"href": a["href"], "text": [], "img": ""}
        elif tag == "img" and self._cur is not None and not self._cur["img"]:
            self._cur["img"] = a.get("src") or a.get("data-src") or ""

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._script:
            self._buf.append(data)
        elif self._cur is not None:
            self._cur["text"].append(data.strip())

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag == "script" and self._script:
            (self.jsonld if self._script == "ld" else self.next_data).append("".join(self._buf))
            self._script = None
        elif tag == "a" and self._cur is not None:
            self._cur["text"] = " ".join(t for t in self._cur["text"] if t)
            self.cards.append(self._cur)
            self._cur = None


def _walk(o, out):
    if isinstance(o, dict):
        title = o.get("title") or o.get("name") or o.get("headline")
        price = o.get("price") or o.get("priceValue") or (o.get("offers") or {}).get("price") if isinstance(o.get("offers", {}), dict) else o.get("price")
        url = o.get("url") or o.get("link") or o.get("href") or o.get("slug") or o.get("permalink")
        if isinstance(title, str) and isinstance(url, str) and price not in (None, "", 0):
            out.append(o)
        for v in o.values():
            _walk(v, out)
    elif isinstance(o, list):
        for v in o:
            _walk(v, out)


def _num(v):
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


def extract(html: str, base_url: str) -> list[dict]:
    """Returns raw listing dicts: title, url, price, size_sqft, beds, baths, phone, is_owner, image."""
    p = _Cards()
    try:
        p.feed(html)
    except Exception:  # noqa: BLE001  broken HTML must not kill a run
        pass
    found: dict[str, dict] = {}

    objs: list[dict] = []
    for blob in p.jsonld + p.next_data:
        try:
            _walk(json.loads(blob), objs)
        except ValueError:
            continue
    for o in objs:
        url = urljoin(base_url, str(o.get("url") or o.get("link") or o.get("href") or o.get("slug") or o.get("permalink")))
        img = o.get("image") or o.get("thumbnail") or ""
        if isinstance(img, list):
            img = img[0] if img else ""
        if isinstance(img, dict):
            img = img.get("url", "")
        off = o.get("offers") if isinstance(o.get("offers"), dict) else {}
        blob = json.dumps(o, ensure_ascii=False)[:1500]
        f = facts(blob)
        f.update({
            "title": str(o.get("title") or o.get("name") or o.get("headline"))[:200],
            "url": url, "image": str(img) if isinstance(img, str) else "",
            "price": _num(off.get("price") or o.get("price") or o.get("priceValue")) or f["price"],
            "size_sqft": _num(o.get("area") or o.get("size") or o.get("floorSize")) if _num(o.get("area") or o.get("size") or o.get("floorSize")) else f["size_sqft"],
            "beds": int(_num(o.get("beds") or o.get("bedrooms") or o.get("numberOfRooms")) or 0) or f["beds"],
            "baths": int(_num(o.get("baths") or o.get("bathrooms")) or 0) or f["baths"],
        })
        found.setdefault(url, f)

    for c in p.cards:
        text = c["text"]
        if not (30 <= len(text) <= 700):
            continue
        f = facts(text)
        if f["price"] is None:
            continue
        url = urljoin(base_url, c["href"])
        if url.rstrip("/") == base_url.rstrip("/") or url in found:
            continue
        f.update({"title": text[:140], "url": url, "image": urljoin(base_url, c["img"]) if c["img"] else ""})
        found[url] = f
    return list(found.values())


def detail_contact(html: str) -> dict:
    """Pull poster phone/name from a listing detail page (tel: links, JSON, or visible text)."""
    out = {"phone": "", "poster": ""}
    m = re.search(r'href=["\']tel:([^"\']+)', html)
    out["phone"] = clean_phone(m.group(1)) if m else ""
    if not out["phone"]:
        out["phone"] = clean_phone(re.sub(r"<[^>]+>", " ", html))
    n = re.search(r'"(?:sellerName|posterName|contactName|agentName|ownerName)"\s*:\s*"([^"]{2,60})"', html)
    out["poster"] = n.group(1) if n else ""
    return out


# ---- Structured records (Next.js flight data, __NEXT_DATA__, JSON-LD) on listing detail pages ----

PTYPE_WORDS = [("land", ("land", "plot")), ("commercial", ("commercial", "office", "shop", "warehouse", "factory")),
               ("house", ("house", "building", "duplex", "villa")), ("apartment", ("apartment", "flat", "condo"))]


def flight_text(html: str) -> str:
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', html, re.S)
    return "".join(json.loads('"' + c + '"') if '\\' in c else c for c in chunks) if chunks else ""


def records(html: str) -> list[dict]:
    """Every JSON object on the page that looks like a property record (has a title and a price)."""
    blobs = [flight_text(html)]
    p = _Cards()
    try:
        p.feed(html)
    except Exception:  # noqa: BLE001
        pass
    blobs += p.jsonld + p.next_data
    dec, out = json.JSONDecoder(), []
    for b in blobs:
        for m in re.finditer(r'"price"\s*:', b):
            depth, i = 0, m.start()
            while i > 0:  # walk back to the brace that opens this object
                i -= 1
                if b[i] == "}":
                    depth += 1
                elif b[i] == "{":
                    if depth == 0:
                        break
                    depth -= 1
            try:
                o, _ = dec.raw_decode(b, i)
            except ValueError:
                continue
            if isinstance(o, dict) and (o.get("title") or o.get("name")):
                out.append(o)
    return out


def flight_ref(flight: str, ref) -> str:
    """Resolve a flight reference like "$20" to its text chunk ("20:T<hexlen>,<text>")."""
    if not (isinstance(ref, str) and ref.startswith("$")):
        return ref if isinstance(ref, str) else ""
    m = re.search(r"(?:^|\n|\})" + re.escape(ref[1:]) + r":T([0-9a-f]+),", flight)
    return flight[m.end():m.end() + int(m.group(1), 16)] if m else ""


def _ptype(words: str) -> str:
    low = words.lower()
    for t, keys in PTYPE_WORDS:
        if any(k in low for k in keys):
            return t
    return ""


def _strip(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()


def detail_html(html: str, url: str) -> dict | None:
    """Plain HTML listing page: read the heading and the text right after it (not the sidebars or footer)."""
    body = re.sub(r"<!--.*?-->", " ", html, flags=re.S)
    body = re.sub(r"<(script|style|nav|header|footer|aside|noscript)\b.*?</\1>", " ", body, flags=re.S | re.I)
    if re.search(r"\boops\b|page not found|ad (?:is )?(?:not available|expired|removed)", _strip(body)[:3000], re.I):
        return None  # deleted or expired ad
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", body, re.S)
    og = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', html)
    title = _strip(h1.group(1)) if h1 and _strip(h1.group(1)) else (og.group(1) if og else "")
    slug = re.sub(r"[-_]+", " ", url.rstrip("/").rsplit("/", 1)[-1])
    if not h1 and len(slug) > 15:  # sites without a heading usually have a descriptive URL
        title = slug.strip().capitalize()
    if not title:
        return None
    window = body[h1.end():h1.end() + 30000] if h1 else body
    text = _strip(window)[:5000]
    f = facts(title + " " + text)
    tel = re.search(r'href=["\']tel:([^"\']+)', window)
    head = (title + " " + url).lower()
    purpose = "rent" if re.search(r"\brent\b|to-let|to let|sublet", head) else "sale" if re.search(r"sale|sell|buy", head + text[:400].lower()) else ""
    katha = re.search(r"(\d+(?:\.\d+)?)\s*(?:katha|kata|kotha)", title + " " + text[:1500], re.I)
    size = f["size_sqft"] or (float(katha.group(1)) * 720 if katha else None)
    return {"title": title[:200], "url": url, "price": f["price"], "purpose": purpose, "ptype": _ptype(title) or _ptype(text[:300]) or "apartment",
            "size_sqft": size, "beds": f["beds"], "baths": f["baths"], "phone": clean_phone(tel.group(1)) if tel else f["phone"],
            "poster": "", "is_owner": f["is_owner"], "image": "", "tags": title + " " + text[:600]}


def detail_record(html: str, url: str) -> dict | None:
    """One listing from its detail page: title, price, purpose, type, size, beds, baths, poster, phone, tags."""
    recs = [r for r in records(html) if isinstance(r.get("price"), (int, float, str))]
    if not recs:
        return detail_html(html, url)
    slug = url.rstrip("/").rsplit("/", 1)[-1]
    mine = [r for r in recs if r.get("slug") == slug] or recs
    rec = max(mine, key=lambda r: (isinstance(r.get("detail"), dict), len(r)))  # prefer the copy with details inline
    det = rec.get("detail") if isinstance(rec.get("detail"), dict) else {}
    tags = rec.get("tags")
    if isinstance(tags, str):
        try:
            tags = json.loads(tags)
        except ValueError:
            tags = [tags]
    tag_text = " ".join(map(str, tags or []))
    status = str(rec.get("status") or rec.get("purpose") or "").lower()
    size = next((_num(det.get(k)) for k in ("builtup_area", "size", "area_sqft", "land_area") if _num(det.get(k))), None)
    text = f"{rec.get('title', '')} {tag_text} {rec.get('address', '')}"
    f = facts(text)
    if not size or not f["beds"]:  # fall back to the listing's own description, never the rest of the page
        desc = re.sub(r"<[^>]+>", " ", flight_ref(flight_text(html), rec.get("description")) or "")
        fd = facts(desc)
        f = {k: f[k] or fd[k] for k in f}
    phone = clean_phone(str(rec.get("userPhone") or rec.get("phone") or ""))
    katha = re.search(r"(\d+(?:\.\d+)?)\s*(?:katha|kata|kotha)", text, re.I)
    if not size and katha:
        size = float(katha.group(1)) * 720  # 1 katha = 720 sqft
    price = None if rec.get("hide_price") else (_num(rec.get("price")) or None)
    postfix = str(rec.get("price_postfix") or rec.get("pricePostfix") or "").lower()
    if "call" in postfix:
        price = None
    elif price and re.search(r"sq|sft|per\s*s", postfix):  # quoted per sqft: convert to a total when size is known
        price = price * (size or f["size_sqft"]) if (size or f["size_sqft"]) else None
    return {
        "title": str(rec.get("title") or rec.get("name"))[:200], "url": url,
        "price": price,
        "purpose": "rent" if "rent" in status else "sale" if "sale" in status or "sell" in status else "",
        "ptype": _ptype(str(rec.get("title"))) or _ptype(tag_text) or "apartment",  # the seller's own title wins over tags
        "size_sqft": size or f["size_sqft"],
        "beds": int(_num(det.get("Bedrooms") or det.get("bedrooms") or rec.get("bedrooms")) or 0) or f["beds"],
        "baths": int(_num(det.get("Bathrooms") or det.get("bathrooms") or rec.get("bathrooms")) or 0) or f["baths"],
        "phone": phone, "poster": str(rec.get("userName") or rec.get("agentName") or "")[:80],
        "is_owner": f["is_owner"], "image": "", "tags": text,
    }


def extract_cards(html: str, base_url: str, detail: str) -> list[dict]:
    """Listing cards where the link and the details sit in different elements: each card is the
    stretch of HTML from one listing link to the next different listing link."""
    links = [(m.start(), urljoin(base_url, m.group(1))) for m in re.finditer(r'href="([^"]+)"', html)
             if re.search(detail, m.group(1))]
    starts, seen = [], set()
    for pos, url in links:
        if url not in seen:
            seen.add(url)
            starts.append((pos, url))
    out = []
    for i, (pos, url) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else pos + 6000
        chunk = html[max(0, html.rfind("<", 0, pos)):min(end, pos + 6000)]
        title_m = re.search(r'title="([^"]{8,200})"', chunk) or re.search(r"<h[1-6][^>]*>(.*?)</h[1-6]>", chunk, re.S)
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", chunk)).strip()
        title = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", title_m.group(1))).strip() if title_m else text[:120]
        f = facts(text)
        img = re.search(r'<img[^>]+src="([^"]+)"', chunk)
        f.update(title=title[:200], url=url, image=urljoin(base_url, img.group(1)) if img else "", text=text[:1500])
        out.append(f)
    return out
