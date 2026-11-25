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

AREA_NAMES = {**weekly.AREA_NAMES, "baridhara": "Baridhara DOHS & Diplomatic Zone"}
TYPE_NAMES = {"apartment": "Flats", "land": "Plots & land", "house": "Houses & duplexes"}
TYPE_ONE = {"apartment": "Flat", "land": "Plot / land", "house": "House"}
INK, MUTE, LINE, BG, CARD, NAVY, GOLD, SOFT = "#101a3a", "#56607f", "#e3e6ef", "#f6f7fa", "#ffffff", "#0b163e", "#c8922a", "#eef1f8"
SANS = "font-family:'IBM Plex Sans',Segoe UI,Helvetica,Arial,sans-serif"
DISP = "font-family:Outfit,'IBM Plex Sans',Segoe UI,Helvetica,Arial,sans-serif"
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.I)


def load_routes(path: str) -> list[dict]:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    out = []
    for a in d.get("associates", []):
        if not EMAIL.match(a.get("email", "")) or not a.get("name"):
            continue
        out.append({"name": str(a["name"])[:40], "email": a["email"].strip(), "all": bool(a.get("all")),
                    "areas": [x.lower() for x in a.get("areas") or []], "types": [x.lower() for x in a.get("types") or []],
                    "focus": a.get("focus") or {}})
    return out


def matches(r: dict, areas: list[str], types: list[str]) -> bool:
    return (not areas or r["area"] in areas) and (not types or r["type"] in types)


def mine(rows: list[dict], a: dict) -> list[dict]:
    return list(rows) if a["all"] else [r for r in rows if matches(r, a["areas"], a["types"])]


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
        buttons += _btn("tel:" + r["phone"], "Call " + e(r["phone"])) + _btn(_wa(r["phone"], en), "WhatsApp")
    draft = (f'<div style="margin-top:10px;font-size:12px;color:{MUTE};line-height:1.5;border-left:3px solid {LINE};padding-left:10px">'
             f'<b style="color:{INK}">Message (EN):</b> {e(en)}<br><b style="color:{INK}">বার্তা (BN):</b> {e(bn)}</div>' if with_draft else "")
    return (f'<tr><td style="padding:6px 0"><div style="background:{CARD};border:1px solid {LINE};border-radius:12px;padding:14px 16px">'
            f'<div style="font-size:15px;font-weight:600;color:{INK};line-height:1.35">{tag}{title}</div>'
            f'<div style="font-size:13px;color:{MUTE};margin-top:4px">{_facts(r)}</div>'
            f'{note_html}<div>{buttons}</div>{draft}</div></td></tr>')


def _row(r: dict) -> str:
    """A light listing row (the bulk of the email): title link, one facts line, plain text links."""
    e = html.escape
    note = _note(flag(r))
    links = [f'<a href="{e(r["url"])}" style="color:{NAVY};font-weight:600">View post</a>']
    if r.get("phone"):
        en, _ = drafts(r)
        links += [f'<a href="tel:{e(r["phone"])}" style="color:{NAVY}">Call {e(r["phone"])}</a>',
                  f'<a href="{e(_wa(r["phone"], en))}" style="color:{NAVY}">WhatsApp</a>']
    n = f'<div style="font-size:12px;color:#8a5a00">{e(note)}</div>' if note else ""
    return (f'<tr><td style="padding:10px 2px;border-top:1px solid {LINE}"><div style="font-size:15px;font-weight:600;color:{INK}">'
            f'{e(r["title"][:90])}</div><div style="font-size:13px;color:{MUTE}">{_facts(r)}</div>{n}'
            f'<div style="font-size:13px;margin-top:3px">{" &nbsp;·&nbsp; ".join(links)}</div></td></tr>')


def _section(title: str, count: int, body: str) -> str:
    return (f'<tr><td style="padding:20px 0 4px"><div style="{DISP};font-size:17px;font-weight:700;color:{NAVY}">{html.escape(title)}'
            f' <span style="color:{MUTE};font-weight:400;font-size:14px">· {count}</span></div></td></tr>{body}')


def _scope(a: dict) -> str:
    if a["all"]:
        return "All areas · all property types"
    areas = ", ".join(AREA_NAMES.get(x, x.title()).replace(" R/A", "") for x in a["areas"]) or "All areas"
    types = " & ".join(TYPE_NAMES.get(t, t).lower() for t in a["types"]) if a["types"] else "all property types"
    return f"{areas} · {types}"


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


def _text_line(r: dict, first: bool = False) -> str:
    price = weekly._money(float(r["price_bdt"])) if plausible_price(r) else "price on call"
    size = f", {int(float(r['size_sqft'])):,} sqft" if r.get("size_sqft") else ""
    return (f"{'CALL FIRST ' if first else ''}- {r['title'][:80]}\n  {AREA_NAMES.get(r['area'], r['area'])} · "
            f"{TYPE_ONE.get(r['type'], r['type'])} · {price}{size} · {r.get('phone') or 'message on post'}\n  {r['url']}")


def build(a: dict, rows: list[dict], label: str) -> list[tuple[str, str, str]]:
    """[(subject, html, text), ...] for one associate: one email, or numbered parts when it would be too long for Gmail."""
    picks = mine(rows, a)
    first = top_calls(picks, 3)
    seen = {id(r) for r in first}
    rest = [r for r in picks if id(r) not in seen]
    blocks: list[tuple[str, list[dict]]] = []
    if a["all"] and a["focus"]:
        fa, ft = [x.lower() for x in a["focus"].get("areas", [])], [x.lower() for x in a["focus"].get("types", [])]
        f = [r for r in rest if matches(r, fa, ft)]
        if f:
            blocks.append(("Your focus: " + _scope({"all": False, "areas": fa, "types": ft}), f))
            ids = {id(r) for r in f}
            rest = [r for r in rest if id(r) not in ids]
    groups = collections.defaultdict(list)
    for r in rest:
        groups[(r["area"], r["type"])].append(r)
    per_area = collections.Counter(r["area"] for r in rest)
    order = {k: i for i, k in enumerate(["apartment", "land", "house"])}
    for (area, t), rs in sorted(groups.items(), key=lambda kv: (-per_area[kv[0][0]], kv[0][0], order.get(kv[0][1], 9))):
        blocks.append((f"{AREA_NAMES.get(area, area.title()).replace(' R/A', '')} · {TYPE_NAMES.get(t, t)}", rs))
    n, phones = len(picks), sum(1 for r in picks if r.get("phone"))
    if not n:
        body = f'<tr><td style="padding:18px 0;font-size:15px;color:{INK}">No new listings in your areas today. The scout searches again tomorrow.</td></tr>'
        return [(f"MRA fresh leads {label} · {a['name']} (0 new)", _page(a, label, 0, 0, "", body), f"{a['name']}: no new listings in your areas today.")]
    # pack sections (split inside a section when needed) into parts that stay under LIMIT
    parts: list[tuple[str, list[dict]]] = [(_section("Call first", len(first), "".join(_card(r, i + 1, with_draft=True) for i, r in enumerate(first))), list(first))]
    for title, rs in blocks:
        rows_html = [(_row(r), r) for r in rs]
        while rows_html:
            body, used = parts[-1]
            head = _section(title, len(rs), "")
            take, size = [], len((body + head).encode())
            for h, r in rows_html:
                if take and size + len(h.encode()) > LIMIT - 6000:
                    break
                take.append((h, r))
                size += len(h.encode())
            if not take or (size > LIMIT - 6000 and used):
                parts.append(("", []))
                continue
            parts[-1] = (body + _section(title if not used or title not in body else title + " (cont.)", len(rs), "".join(h for h, _ in take)), used + [r for _, r in take])
            rows_html = rows_html[len(take):]
            if rows_html:
                parts.append(("", []))
    out = []
    for i, (body, used) in enumerate(parts):
        tag = f" · part {i + 1} of {len(parts)}" if len(parts) > 1 else ""
        text = "\n".join([f"{a['name']}, {n} new for you · {label} · {_scope(a)}{tag}", ""] +
                         [_text_line(r, i == 0 and j < len(first)) for j, r in enumerate(used)])
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
                             "count": len(mine(rows, a))})
    (od / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    return manifest
