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


def facts(text: str) -> dict:
    size, beds, baths = SIZE.search(text), BEDS.search(text), BATHS.search(text)
    low = text.lower()
    return {
        "price": parse_price(text),
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
