"""Per-associate lead emails: each associate gets only the leads in their own areas and property types; the owner gets all.

The routing list (names, email addresses, areas, types) is private, so it lives in Drive (MRA Agents Workspace/
MRA Property Scout/associates.json), never in this public repo:
  {"associates": [{"name": "Rahul", "email": "...", "areas": ["bashundhara"], "types": ["apartment", "land"]},
                  {"name": "Owner", "email": "...", "all": true, "focus": {"areas": [...], "types": ["land"]}}]}
types: apartment (flats), land (plots/katha), house (houses/duplexes); an empty or missing list means every type.

python -m property_finder mail --routes associates.json leads-*.csv --out DIR [--label "25 Nov 2026"]
writes DIR/<name>.html, DIR/<name>.txt and DIR/manifest.json (to, subject, files, count) for the sender.
Email clients strip <style> and scripts, so everything is inline styles and tables.
"""
from __future__ import annotations

import collections
import datetime as dt
import html
import json
import re
import urllib.parse
from pathlib import Path

from . import weekly
from .scout import drafts, flag, plausible_price, top_calls

AREA_NAMES = {**weekly.AREA_NAMES, "baridhara": "Baridhara Diplomatic Zone"}
# A whole building for sale is land with a building on it (one product), labelled so buyers who want a ready house see it.
TYPE_NAMES = {"apartment": "Flats", "land": "Plots & land", "house": "Land with building (ready house)", "commercial": "Commercial"}
TYPE_ONE = {"apartment": "Flat", "land": "Plot / land", "house": "Land with building · ready house", "commercial": "Commercial"}
INK, MUTE, LINE, BG, CARD, NAVY, GOLD, SOFT = "#101a3a", "#56607f", "#e3e6ef", "#f6f7fa", "#ffffff", "#0b163e", "#c8922a", "#eef1f8"
SANS = "font-family:'IBM Plex Sans',Segoe UI,Helvetica,Arial,sans-serif"
DISP = "font-family:Outfit,'IBM Plex Sans',Segoe UI,Helvetica,Arial,sans-serif"
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.I)


def _rule(x: dict) -> dict:
    return {"areas": [a.lower() for a in x.get("areas") or []], "types": [t.lower() for t in x.get("types") or []]}


def load_routes(path: str) -> list[dict]:
    """Each associate has one or more rules (areas x types); 'areas'/'types' at the top level are a single rule."""
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    out = []
    for a in d.get("associates", []):
        if not EMAIL.match(a.get("email", "")) or not a.get("name"):
            continue
        rules = [_rule(x) for x in a.get("rules") or []] or ([_rule(a)] if not a.get("all") else [])
        out.append({"name": str(a["name"])[:40], "email": a["email"].strip(), "all": bool(a.get("all")), "rules": rules,
                    "focus": _rule(a["focus"]) if a.get("focus") else {}})
    return out


def matches(r: dict, areas: list[str], types: list[str]) -> bool:
    t = r["type"]
    wanted = set(types) | ({"house"} if "land" in types else set())  # land with a building counts as land
    return (not areas or r["area"] in areas) and (not types or t in wanted)


def mine(rows: list[dict], a: dict) -> list[dict]:
    if a["all"]:
        return list(rows)
    return [r for r in rows if any(matches(r, x["areas"], x["types"]) for x in a["rules"])]


def _wa_text(r: dict) -> str:
    """Short ready message for the WhatsApp link (the full drafts stay in the Call-first cards)."""
    kind = {"apartment": "flat", "land": "plot", "house": "property", "commercial": "commercial space"}.get(r["type"], "property")
    return (f"Assalamu alaikum. I am from MRA Real Estate. I saw your {kind} for sale in {AREA_NAMES.get(r['area'], r['area'].title())}. "
            "Is it still available? Could you share the final price, size and papers?")


def _wa(phone: str, text: str) -> str:
    digits = re.sub(r"\D", "", phone)
    intl = "880" + digits[1:] if digits.startswith("0") else digits
    return f"https://wa.me/{intl}?text={urllib.parse.quote(text)}"


def _btn(href: str, label: str, solid: bool = False) -> str:
    style = (f"background:{NAVY};color:#ffffff;border:1px solid {NAVY}" if solid else f"background:#ffffff;color:{NAVY};border:1px solid #c9cfe0")
    return (f'<a href="{html.escape(href)}" style="{style};display:inline-block;padding:7px 12px;border-radius:8px;'
            f'font-size:13px;font-weight:600;text-decoration:none;margin:6px 6px 0 0">{label}</a>')


def _facts(r: dict) -> str:
    bits = [weekly._money(float(r["price_bdt"])) if plausible_price(r) else "Price on call"]
    if r.get("size_sqft"):
        bits.append(f"{int(float(r['size_sqft'])):,} sqft")
    bits.append(TYPE_ONE.get(r["type"], r["type"].title()))
    bits.append(r["site"].split(" (")[0].split(":")[0])
    return " · ".join(html.escape(b) for b in bits)


def _note(raw: str) -> str:
    """'price missing - ask seller; size missing - ask seller' -> 'Ask the seller for: price, size'."""
    parts = [p.strip() for p in (raw or "").split(";") if p.strip()]
    missing = [m.group(1) for p in parts if (m := re.match(r"(\w[\w ]*?) missing", p))]
    other = [p for p in parts if not re.match(r"\w[\w ]*? missing", p)]
    out = (["Ask the seller for: " + ", ".join(missing)] if missing else []) + other
    return " · ".join(out)


def _card(r: dict, rank: int | None = None, with_draft: bool = False) -> str:
    e = html.escape
    title = e(r["title"][:90])
    tag = (f'<span style="display:inline-block;background:{GOLD};color:#ffffff;font-size:11px;font-weight:700;'
           f'border-radius:6px;padding:2px 7px;margin-right:6px">#{rank}</span>' if rank else "")
    note = _note(flag(r))
    note_html = (f'<div style="margin-top:6px;font-size:12px;color:#8a5a00;background:#fff6e5;border-radius:6px;padding:5px 8px">'
                 f'{e(note)}</div>' if note else "")
    en, bn = drafts(r)
    buttons = _btn(r["url"], "View post", solid=True)
    if r.get("phone"):
        buttons += _btn("tel:" + r["phone"], "Call " + e(r["phone"])) + _btn(_wa(r["phone"], _wa_text(r)), "WhatsApp")
    draft = (f'<div style="margin-top:10px;font-size:12px;color:{MUTE};line-height:1.5;border-left:3px solid {LINE};padding-left:10px">'
             f'<b style="color:{INK}">Message (EN):</b> {e(en)}<br><b style="color:{INK}">বার্তা (BN):</b> {e(bn)}</div>' if with_draft else "")
    return (f'<tr><td style="padding:6px 0"><div style="background:{CARD};border:1px solid {LINE};border-radius:12px;padding:14px 16px">'
            f'<div style="font-size:15px;font-weight:600;color:{INK};line-height:1.35">{tag}{title}</div>'
            f'<div style="font-size:13px;color:{MUTE};margin-top:4px">{_facts(r)}</div>'
            f'{note_html}<div>{buttons}</div>{draft}</div></td></tr>')


import unicodedata


def clean_title(t: str, n: int = 90) -> str:
    """Readable everywhere: fancy Facebook letters made plain, emoji/symbols and stray markup removed, cut on a word."""
    t = unicodedata.normalize("NFKC", t or "")
    t = "".join(ch for ch in t if unicodedata.category(ch) not in ("So", "Sk", "Cs", "Co", "Cn")
                and ch not in "\ufffd\ufe0f\ufe0e*#|" and (unicodedata.category(ch) != "Cf" or ch in "\u200c\u200d"))
    t = re.sub(r"\s+", " ", re.sub(r"\.{2,}|…", " ", t)).strip(" -–:,.")
    if len(t) > n:
        t = t[:n].rsplit(" ", 1)[0] + " …"
    return t or "Property for sale"


def post_link(r: dict) -> tuple[str, str]:
    """Google's redirect links (google.com/goto) are tied to one search session and can open a different post later,
    so for those we link a search for this exact post instead."""
    if "google.com/goto" in r["url"]:
        site = r.get("via") or ("facebook.com" if r["site"].startswith("Facebook") else {"Bikroy": "bikroy.com"}.get(r["site"], ""))
        q = f'"{" ".join(clean_title(r["title"], 70).replace(" …", "").split()[:9])}"' + (f" site:{site}" if site else "")
        return "https://www.google.com/search?q=" + urllib.parse.quote(q), "Find post →"
    return r["url"], "See post →"


def _row(r: dict, first: bool = False, same_seller: int = 0) -> str:
    """One listing: title, one facts line, an ask-the-seller note when something is missing, then plain links
    (plain links render the same in every mail app; filled buttons can show up blank)."""
    e = html.escape
    note = _note(flag(r))
    href, label = post_link(r)
    links = [f'<a href="{e(href)}" style="color:{NAVY};font-weight:700">{label}</a>']
    if r.get("phone"):
        links += [f'<a href="tel:{e(r["phone"])}" style="color:{NAVY}">Call {e(r["phone"])}</a>',
                  f'<a href="{e(_wa(r["phone"], _wa_text(r)))}" style="color:{NAVY}">WhatsApp</a>']
    chip = lambda txt, bg: (f'<span style="display:inline-block;background:{bg};color:#ffffff;font-size:10px;font-weight:700;'
                            f'letter-spacing:.5px;border-radius:4px;padding:1px 6px;margin:0 4px 4px 0">{txt}</span>')
    tags = (chip("CALL FIRST", GOLD) if first else "") + (chip(f"SAME SELLER · {same_seller} LISTINGS", "#4a5a9c") if same_seller > 1 else "") \
        + (chip("SELLER SEEN BEFORE", "#8a93b8") if r.get("known_seller") else "")
    tag = tags + "<br>" if tags else ""
    n = f'<div style="font-size:12px;color:#8a5a00;margin-top:2px">{e(note)}</div>' if note else ""
    if r.get("contact_name") and r.get("phone"):
        n += f'<div style="font-size:12px;color:{MUTE};margin-top:2px">Seller: {e(r["contact_name"][:80])}</div>'
    elif r.get("contact_how") and not r.get("phone"):
        n += f'<div style="font-size:12px;color:{MUTE};margin-top:2px">How to reach: {e(r["contact_how"])}</div>'

    edge = f"border-left:3px solid {GOLD};padding-left:10px;" if first else "padding-left:2px;"
    return (f'<tr><td style="padding:12px 0 12px;border-top:1px solid {LINE}"><div style="{edge}">{tag}'
            f'<div style="font-size:15px;font-weight:600;color:{INK};line-height:1.35">{e(clean_title(r["title"]))}</div>'
            f'<div style="font-size:13px;color:{MUTE};margin-top:2px">{_facts(r)}</div>{n}'
            f'<div style="font-size:13px;margin-top:5px">{" &nbsp;·&nbsp; ".join(links)}</div></div></td></tr>')


def _area_band(area: str, n: int, cont: bool = False) -> str:
    name = AREA_NAMES.get(area, area.title()).replace(" R/A", "") + (" (continued)" if cont else "")
    return (f'<tr><td style="padding:22px 0 6px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
            f'<tr><td bgcolor="{NAVY}" style="background:{NAVY};border-radius:10px;padding:11px 14px;{DISP};font-size:17px;'
            f'font-weight:700;color:#ffffff">{html.escape(name)} <span style="color:{GOLD}">· {n}</span></td></tr></table></td></tr>')


def _type_label(t: str, n: int) -> str:
    return (f'<tr><td style="padding:12px 0 2px;font-size:11px;font-weight:700;letter-spacing:1.2px;color:{MUTE}">'
            f'{html.escape(TYPE_NAMES.get(t, t).upper())} · {n}</td></tr>')


def _section(title: str, count: int, body: str) -> str:
    return (f'<tr><td style="padding:20px 0 4px"><div style="{DISP};font-size:17px;font-weight:700;color:{NAVY}">{html.escape(title)}'
            f' <span style="color:{MUTE};font-weight:400;font-size:14px">· {count}</span></div></td></tr>{body}')


def _scope_rule(areas: list[str], types: list[str]) -> str:
    names = ", ".join(AREA_NAMES.get(x, x.title()).replace(" R/A", "") for x in areas) or "All areas"
    if not types:
        return f"{names}: everything"
    kinds = [{"apartment": "flats", "land": "land (incl. land with building)", "house": "land with building", "commercial": "commercial"}.get(t, t) for t in types]
    return f"{names}: " + " & ".join(kinds)


def _scope(a: dict) -> str:
    if a.get("all"):
        return "All areas · all property types"
    return " · ".join(_scope_rule(x["areas"], x["types"]) for x in a["rules"])


LIMIT = 90_000  # Gmail clips an email body over ~102 KB; stay below it and split into parts instead


def _page(a: dict, label: str, n: int, phones: int, part: str, body_rows: str) -> str:
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:{BG};{SANS}">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{BG}"><tr><td align="center" style="padding:18px 10px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;{SANS}">
<tr><td style="padding:4px 2px 8px">
<div style="font-size:11px;letter-spacing:1.6px;font-weight:700;color:{GOLD}">MRA PROPERTY HUNT · FRESH LEADS{html.escape(part.upper())}</div>
<div style="{DISP};font-size:26px;font-weight:700;color:{INK};margin-top:6px;line-height:1.15">{html.escape(a['name'])}, {n} new for you</div>
<div style="font-size:14px;color:{MUTE};margin-top:6px">{html.escape(label)} · {html.escape(_scope(a))}</div>
<div style="font-size:13px;color:{MUTE};margin-top:4px">{phones} with a phone number · tap <b>WhatsApp</b> to open a ready message</div>
</td></tr>
{body_rows}
<tr><td style="padding:18px 2px 6px;color:{MUTE};font-size:12px;line-height:1.5">Prices and sizes are as the seller posted them: confirm on the call.
Found by the MRA Property Scout from public listings.</td></tr>
</table></td></tr></table></body></html>"""


def _text_line(r: dict, first: bool = False) -> str:  # noqa: D401
    price = weekly._money(float(r["price_bdt"])) if plausible_price(r) else "price on call"
    size = f", {int(float(r['size_sqft'])):,} sqft" if r.get("size_sqft") else ""
    return (f"{'CALL FIRST ' if first else ''}- {clean_title(r['title'], 80)}\n  {AREA_NAMES.get(r['area'], r['area'])} · "
            f"{TYPE_ONE.get(r['type'], r['type'])} · {price}{size} · {r.get('phone') or 'message on post'}\n  {post_link(r)[0]}"
            + (f"\n  How to reach: {r['contact_how']}" if r.get("contact_how") and not r.get("phone") else ""))


def build(a: dict, rows: list[dict], label: str) -> list[tuple[str, str, str]]:
    """[(subject, html, text), ...]: one block per area (best leads first, then by property type); numbered parts when long."""
    picks = mine(rows, a)
    n, phones = len(picks), sum(1 for r in picks if r.get("phone"))
    if not n:
        body = f'<tr><td style="padding:18px 0;font-size:15px;color:{INK}">No new listings in your areas today. The scout searches again tomorrow.</td></tr>'
        return [(f"MRA fresh leads {label} · {a['name']} (0 new)", _page(a, label, 0, 0, "", body), f"{a['name']}: no new listings in your areas today.")]
    by_area = collections.defaultdict(list)
    for r in picks:
        by_area[r["area"]].append(r)
    focus = (a.get("focus") or {}).get("areas", [])
    areas = sorted(by_area, key=lambda x: (x not in focus, -len(by_area[x]), x))
    order = {k: i for i, k in enumerate(["apartment", "land", "house", "commercial"])}
    index = " &nbsp;·&nbsp; ".join(f'<b style="color:{INK}">{html.escape(AREA_NAMES.get(x, x.title()).replace(" R/A", ""))}</b> {len(by_area[x])}'
                                   for x in areas)
    head = f'<tr><td style="padding:6px 2px 0;font-size:13px;color:{MUTE}">{index}</td></tr>'
    # each area: its best 2 first (marked), then the rest grouped by type
    units: list[tuple[str, str, list[dict]]] = []  # (area, html piece, rows) in display order
    per_phone = collections.Counter(r["phone"] for r in picks if r.get("phone"))
    for x in areas:
        rs = by_area[x]
        best = top_calls(rs, 2)
        ids = {id(r) for r in best}
        pieces = [(_row(r, first=True, same_seller=per_phone.get(r.get("phone"), 0)), r) for r in best]
        groups = collections.defaultdict(list)
        for r in rs:
            if id(r) not in ids:
                groups[r["type"]].append(r)
        for t in sorted(groups, key=lambda t: order.get(t, 9)):
            pieces.append((_type_label(t, len(groups[t])), None))
            ordered = sorted(groups[t], key=lambda r: (-per_phone.get(r.get("phone"), 0), r.get("phone") or "~"))  # one seller's listings together
            pieces += [(_row(r, same_seller=per_phone.get(r.get("phone"), 0)), r) for r in ordered]
        units.append((x, len(rs), pieces))
    parts: list[tuple[str, list[dict]]] = [(head, [])]
    for x, cnt, pieces in units:
        band, cont = _area_band(x, cnt), False
        body, used = parts[-1]
        if len((body + band).encode()) > LIMIT - 8000 and used:
            parts.append(("", []))
            body, used = parts[-1]
        body += band
        for h, r in pieces:
            if len((body + h).encode()) > LIMIT - 6000 and used:
                parts[-1] = (body, used)
                parts.append((_area_band(x, cnt, cont=True), []))
                body, used = parts[-1]
            body += h
            if r is not None:
                used = used + [r]
        parts[-1] = (body, used)
    out = []
    for i, (body, used) in enumerate(parts):
        tag = f" · part {i + 1} of {len(parts)}" if len(parts) > 1 else ""
        text = "\n".join([f"{a['name']}, {n} new for you · {label} · {_scope(a)}{tag}", ""] + [_text_line(r) for r in used])
        out.append((f"MRA fresh leads {label} · {a['name']} ({n} new){tag}", _page(a, label, n, phones, tag, body), text))
    return out


def make(routes: str, leads: list[str], out_dir: str, label: str | None = None) -> list[dict]:
    rows = weekly.load(leads)
    if label is None:
        days = sorted({r["date"] for r in rows})
        d0, d1 = (dt.date.fromisoformat(days[0]), dt.date.fromisoformat(days[-1])) if days else (dt.date.today(),) * 2
        label = d1.strftime("%d %b %Y") if d0 == d1 else f"{d0.strftime('%d %b')} – {d1.strftime('%d %b %Y')}"
    od = Path(out_dir)
    od.mkdir(parents=True, exist_ok=True)
    manifest = []
    for a in load_routes(routes):
        slug = re.sub(r"[^a-z0-9]+", "-", a["name"].lower()).strip("-") or "associate"
        for i, (subject, page, text) in enumerate(build(a, rows, label)):
            name = slug if i == 0 else f"{slug}-part{i + 1}"
            (od / f"{name}.html").write_text(page, encoding="utf-8")
            (od / f"{name}.txt").write_text(text, encoding="utf-8")
            manifest.append({"name": a["name"], "to": a["email"], "subject": subject, "html": f"{name}.html", "text": f"{name}.txt",
                             "count": len(mine(rows, a)), "all": a["all"]})
    (od / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    return manifest
