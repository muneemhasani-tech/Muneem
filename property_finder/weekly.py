"""Weekly summary for the associates: one email-safe HTML page built from the week's leads-YYYY-MM-DD.csv files.

Email clients strip <style>, scripts and most CSS, so everything is inline styles and tables; bars are table cells.
python -m property_finder weekly leads-*.csv --out weekly.html
"""
from __future__ import annotations

import collections
import csv
import datetime as dt
import html
import json
from pathlib import Path

from . import parse
from .scout import plausible_price, top_calls

AREA_NAMES = {"gulshan": "Gulshan", "banani": "Banani", "purbachal": "Purbachal", "uttara": "Uttara",
              "dhanmondi": "Dhanmondi", "bashundhara": "Bashundhara R/A"}
TYPES = [("apartment", "Flats", "#0b163e"), ("land", "Plots", "#c8922a"), ("house", "Houses", "#8a93b8")]
INK, MUTE, LINE, BG, CARD, NAVY, GOLD = "#101a3a", "#56607f", "#d5d9e6", "#f6f7fa", "#ffffff", "#0b163e", "#c8922a"
SANS = "font-family:'IBM Plex Sans',Segoe UI,Helvetica,Arial,sans-serif"   # the Property Hunt page's type; falls back where fonts are blocked
DISP = "font-family:Outfit,'IBM Plex Sans',Segoe UI,Helvetica,Arial,sans-serif"


def load(paths: list[str]) -> list[dict]:
    rows, seen = [], set()
    for p in sorted(paths):
        for r in csv.DictReader(open(p, encoding="utf-8-sig")):
            if r["url"] not in seen:  # the scout never repeats, but a re-run day must not count twice
                seen.add(r["url"])
                tp = parse.parse_price(parse.norm(r["title"]))  # older days were read by an older parser; the title is the surest price
                if tp and plausible_price({**r, "price_bdt": tp}):
                    r["price_bdt"] = str(int(tp))
                rows.append(r)
    return rows


def _money(v: float) -> str:
    return f"৳{v / 1e7:.2f} Cr" if v >= 1e7 else f"৳{v / 1e5:.0f} Lakh"


def _bar(parts: list[tuple[int, str]], total: int, width: int = 100) -> str:
    """A horizontal bar of coloured cells; width is the bar's share of the row in percent."""
    cells = "".join(f'<td width="{max(1, round(100 * n / total))}%" style="background:{c};height:12px;font-size:0;line-height:0">&nbsp;</td>'
                    for n, c in parts if n)
    return (f'<table role="presentation" cellpadding="0" cellspacing="0" width="{max(2, width)}%" style="border-collapse:collapse">'
            f"<tr>{cells}</tr></table>")


def _h(title: str) -> str:
    return f'<div style="{DISP};font-size:16px;font-weight:700;color:{NAVY};margin:0 0 10px">{title}</div>'


def _rows(items: list[tuple[str, list[tuple[int, str]], int]], peak: int, label_w: int = 110) -> str:
    out = "".join(
        f'<tr><td style="padding:4px 10px 4px 0;font-size:13px;color:{INK};white-space:nowrap" width="{label_w}">{lab}</td>'
        f'<td style="padding:4px 0">{_bar(parts, n, round(100 * n / peak))}</td>'
        f'<td style="padding:4px 0 4px 10px;font-weight:600;font-size:13px;color:{INK};font-variant-numeric:tabular-nums" width="28" align="right">{n}</td></tr>'
        for lab, parts, n in items)
    return f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{out}</table>'


def build(rows: list[dict], start: dt.date | None = None, end: dt.date | None = None) -> str:
    days = sorted({r["date"] for r in rows})
    start = start or dt.date.fromisoformat(days[0])
    end = end or dt.date.fromisoformat(days[-1])
    total = len(rows)
    phone = sum(1 for r in rows if r["phone"])
    priced = sum(1 for r in rows if plausible_price(r))
    by_day = collections.Counter(r["date"] for r in rows)
    by_area = collections.Counter(r["area"] for r in rows)
    by_type = collections.Counter(r["type"] for r in rows)
    cell = collections.Counter((r["area"], r["type"]) for r in rows)
    src = collections.Counter("Facebook" if r["site"].startswith("Facebook") else
                              ("Other sites" if r["site"].startswith("Open web") else r["site"]) for r in rows)
    e = html.escape
    area = lambda a: AREA_NAMES.get(a, a.title())

    def tile(num, label, gold=False):
        border = GOLD if gold else LINE
        return (f'<td width="25%" style="padding:5px"><div style="background:{CARD};border:1px solid {border};border-radius:10px;padding:12px 12px 10px">'
                f'<div style="{DISP};font-size:26px;font-weight:700;color:{INK};line-height:1.1">{num}</div>'
                f'<div style="font-size:11px;letter-spacing:1px;text-transform:uppercase;color:{MUTE};font-weight:600;margin-top:4px">{label}</div></div></td>')

    tiles = (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
             f'{tile(total, "New", True)}{tile(by_type["apartment"], "Flats")}{tile(by_type["land"], "Plots")}{tile(by_type["house"], "Houses")}'
             f'</tr></table>')

    legend = " &nbsp;&nbsp; ".join(f'<span style="display:inline-block;width:9px;height:9px;background:{c};border-radius:2px"></span>'
                                   f' <span style="font-size:12px;color:{MUTE}">{n}</span>' for _, n, c in TYPES)
    areas = _rows([(area(a), [(cell[(a, t)], c) for t, _, c in TYPES], n) for a, n in by_area.most_common()],
                  by_area.most_common(1)[0][1])
    daily = _rows([(dt.date.fromisoformat(d).strftime("%a %d"), [(by_day[d], NAVY)], by_day[d]) for d in days], max(by_day.values()), 64)
    sources = _rows([(e(s), [(n, "#8a93b8")], n) for s, n in src.most_common()], src.most_common(1)[0][1], 90)

    best = "".join(
        f'<tr><td style="padding:9px 0;border-top:1px solid {LINE};font-size:13px;line-height:1.45">'
        f'<a href="{e(r["url"])}" style="color:{NAVY};font-weight:600;text-decoration:none">{e(r["title"][:70])}</a><br>'
        f'<span style="color:{MUTE}">{area(r["area"])} · '
        f'{_money(float(r["price_bdt"])) if plausible_price(r) else "price on call"}'
        f'{f" · {int(float(r["size_sqft"])):,} sqft" if r["size_sqft"] else ""}'
        f'{f" · {e(r["phone"])}" if r["phone"] else ""}</span></td></tr>'
        for r in top_calls(rows, 5))

    card = lambda inner: (f'<tr><td style="padding:0 20px 14px"><div style="background:{CARD};border:1px solid {LINE};border-radius:10px;padding:16px 16px 12px">'
                          f'{inner}</div></td></tr>')
    period = f'{start.strftime("%d")}–{end.strftime("%d %b %Y")}' if start.month == end.month else f'{start.strftime("%d %b")} – {end.strftime("%d %b %Y")}'
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Outfit:wght@500;700&family=IBM+Plex+Sans:wght@400;600&display=swap">
<title>MRA Property Hunt · week of {start.strftime("%d %b")}</title></head>
<body style="margin:0;padding:0;background:{BG};{SANS}">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{BG}"><tr><td align="center" style="padding:24px 8px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;{SANS}">
<tr><td style="padding:0 20px 18px">
<div style="font-size:11px;letter-spacing:1.6px;font-weight:700;color:{GOLD}">MRA PROPERTY HUNT · WEEKLY</div>
<div style="{DISP};font-size:30px;font-weight:700;color:{INK};letter-spacing:-0.5px;margin-top:6px;line-height:1.1">{total} new properties</div>
<div style="font-size:14px;color:{MUTE};margin-top:6px">{period} · {phone} with phone · {priced} with price</div></td></tr>
<tr><td style="padding:0 15px 14px">{tiles}</td></tr>
{card(_h("By area") + f'<div style="margin:-4px 0 8px">{legend}</div>' + areas)}
{card(_h("Call first") + f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{best}</table>')}
{card(_h("Per day") + daily)}
{card(_h("Sources") + sources)}
<tr><td style="padding:4px 20px 0"><div style="border-left:3px solid {GOLD};padding:2px 0 2px 10px;color:{MUTE};font-size:12px">Prices as posted. Confirm on the call.</div></td></tr>
</table></td></tr></table></body></html>"""


def write(paths: list[str], out: str) -> dict:
    rows = load(paths)
    Path(out).write_text(build(rows), encoding="utf-8")
    return {"rows": len(rows), "out": out}


# ---------------------------------------------------------------------------------------------------------------
# One-pager infographic: drawn as SVG, rendered to a PNG (email clients strip SVG), embedded inline in the email.
# Aggregates only: no seller phone numbers in the image, so it is safe to forward.

def load_stats(paths: list[str]) -> dict[str, dict]:
    out = {}
    for p in paths:
        try:
            d = json.loads(Path(p).read_text(encoding="utf-8"))
            out[d["date"]] = d
        except (OSError, ValueError, KeyError):
            continue
    return out


def _t(x, y, s, size=16, w=400, fill=INK, anchor="start", fam="sans"):
    f = "Outfit,'IBM Plex Sans',Segoe UI,Arial,sans-serif" if fam == "disp" else "'IBM Plex Sans',Segoe UI,Arial,sans-serif"
    return (f'<text x="{x}" y="{y}" font-family="{f}" font-size="{size}" font-weight="{w}" fill="{fill}" '
            f'text-anchor="{anchor}">{html.escape(str(s))}</text>')


def _card(y, h, title, inner):
    return (f'<g transform="translate(24,{y})"><rect width="552" height="{h}" rx="14" fill="{CARD}" stroke="{LINE}"/>'
            f'{_t(22, 36, title, 20, 700, NAVY, fam="disp")}{inner}</g>')


PIE = [NAVY, GOLD, "#8a93b8", "#2a9d8f", "#e6c27a", "#4a5a9c", "#c9cfe6"]


def _pie(cx, cy, r, items, labels=True):
    """A pie of (label, value, colour); slices of 8% or more carry their share."""
    import math
    tot = sum(v for _, v, _ in items) or 1
    out, a0 = "", -math.pi / 2
    for lab, v, c in items:
        frac = v / tot
        a1 = a0 + 2 * math.pi * frac
        if frac >= 0.999:
            out += f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{c}"/>'
        else:
            x0, y0, x1, y1 = cx + r * math.cos(a0), cy + r * math.sin(a0), cx + r * math.cos(a1), cy + r * math.sin(a1)
            out += (f'<path d="M{cx},{cy} L{x0:.1f},{y0:.1f} A{r},{r} 0 {1 if frac > 0.5 else 0} 1 {x1:.1f},{y1:.1f} Z" '
                    f'fill="{c}" stroke="#ffffff" stroke-width="2"/>')
        if labels and frac >= 0.08:
            am = (a0 + a1) / 2
            dark = c in (NAVY, "#4a5a9c", "#2a9d8f")
            out += _t(cx + 0.62 * r * math.cos(am), cy + 0.62 * r * math.sin(am) + 5, f"{round(100 * frac)}%", 14, 700,
                      "#ffffff" if dark else INK, "middle")
        a0 = a1
    return out


def onepager_html(rows: list[dict], stats: dict[str, dict]) -> str:
    days = sorted({r["date"] for r in rows})
    start, end = dt.date.fromisoformat(days[0]), dt.date.fromisoformat(days[-1])
    total = len(rows)
    by_type = collections.Counter(r["type"] for r in rows)
    by_area = collections.Counter(r["area"] for r in rows)
    cell = collections.Counter((r["area"], r["type"]) for r in rows)
    by_day = collections.Counter(r["date"] for r in rows)
    phone = sum(1 for r in rows if r["phone"])
    priced = sum(1 for r in rows if plausible_price(r))
    src = collections.Counter("Facebook" if r["site"].startswith("Facebook") else
                              ("Other sites" if r["site"].startswith("Open web") else r["site"]) for r in rows)
    st = [stats[d] for d in days if d in stats]
    parts, y = [], 0

    # header
    period = f'{start.strftime("%d")}–{end.strftime("%d %b %Y")}' if start.month == end.month else f'{start.strftime("%d %b")} – {end.strftime("%d %b %Y")}'
    parts.append(_t(24, 34, "MRA PROPERTY HUNT · WEEKLY", 13, 700, GOLD) + _t(24, 84, f"{total} new properties", 44, 700, INK, fam="disp")
                 + _t(24, 116, f"{period} · 6 areas · no repeats", 17, 400, MUTE))
    y = 140

    # 1. how a lead reaches you (the real pipeline; numbers from the stats files, a node is dropped when its figure is unknown)
    nodes = []
    if st:
        nodes.append((f"{round(sum(s['searches'] for s in st) / len(st))}", "searches", "a day"))
    nodes.append(("6", "areas", "5 sources"))
    if st:
        nodes.append((str(sum(s["repeats_skipped"] for s in st)), "repeats", "removed"))
    nodes += [(str(total), "new", "this week"), ("3", "to call", "every day")]
    n = len(nodes)
    gap = 22
    w = (508 - gap * (n - 1)) / n
    flow = ""
    for i, (num, a, b) in enumerate(nodes):
        x = 22 + i * (w + gap)
        hot = i == n - 1
        flow += (f'<rect x="{x:.0f}" y="58" width="{w:.0f}" height="104" rx="12" fill="{NAVY if hot else BG}" stroke="{GOLD if hot else LINE}"/>'
                 + _t(x + w / 2, 104, num, 30, 700, "#ffffff" if hot else INK, "middle", "disp")
                 + _t(x + w / 2, 130, a, 15, 600, GOLD if hot else INK, "middle") + _t(x + w / 2, 149, b, 13, 400, "#c9cfe6" if hot else MUTE, "middle"))
        if i < n - 1:
            ax = x + w + 4
            flow += f'<path d="M{ax:.0f} 110 h{gap - 10} m-6 -6 l6 6 l-6 6" fill="none" stroke="{GOLD}" stroke-width="2.5" stroke-linecap="round"/>'
    parts.append(_card(y, 184, "How a lead reaches you", flow))
    y += 200

    # 2-6: pie charts, each with a legend of count and share
    def section(title, items, note=""):
        nonlocal y
        items = [(lab, v, PIE[i % len(PIE)] if c is None else c) for i, (lab, v, c) in enumerate(items) if v]
        tot = sum(v for _, v, _ in items)
        leg = ""
        for i, (lab, v, c) in enumerate(items):
            ly = 76 + i * 36
            leg += (f'<rect x="250" y="{ly - 13}" width="16" height="16" rx="4" fill="{c}"/>' + _t(276, ly, lab, 17, 600, INK)
                    + _t(530, ly, f"{v}  ·  {round(100 * v / tot)}%", 17, 600, INK, "end"))
        h = max(250, 96 + 36 * len(items)) + (28 if note else 0)
        body = _pie(122, 56 + (h - (28 if note else 0) - 56) / 2, 92, items) + leg
        if note:
            body += _t(22, h - 18, note, 14, 400, MUTE)
        parts.append(_card(y, h, title, body))
        y += h + 16

    section("What was found", [(name, by_type[t], c) for t, name, c in TYPES])
    section("Where", [(AREA_NAMES.get(a_, a_.title()).replace(" R/A", ""), n_, None) for a_, n_ in by_area.most_common()],
            "Most plots: " + ", ".join(f"{AREA_NAMES.get(a_, a_).replace(' R/A', '')} ({n_})" for a_, n_ in
                                      collections.Counter(r["area"] for r in rows if r["type"] == "land").most_common(2)))

    # ready to call: two pies side by side (phone and price overlap, so they are separate pies, not one)
    pair = ""
    for i, (lab, k, c) in enumerate((("Phone shown", phone, NAVY), ("Price shown", priced, GOLD))):
        cx = 146 + i * 260
        pair += (_pie(cx, 140, 74, [("yes", k, c), ("no", total - k, "#e3e6ef")], labels=False)
                 + _t(cx, 258, f"{round(100 * k / total)}%", 32, 700, INK, "middle", "disp")
                 + _t(cx, 284, lab, 17, 600, INK, "middle") + _t(cx, 306, f"{k} of {total}", 14, 400, MUTE, "middle"))
    pair += _t(22, 346, f"{total - phone} without a number: message the seller on the post.", 14, 400, MUTE)
    parts.append(_card(y, 368, "Ready to call?", pair))
    y += 384

    section("New each day", [(dt.date.fromisoformat(d).strftime("%a %d %b"), by_day[d], None) for d in days])
    section("Sources", [(s_, n_, None) for s_, n_ in src.most_common(6)])

    parts.append(f'<rect x="24" y="{y}" width="3" height="20" fill="{GOLD}"/>' + _t(36, y + 15, "Prices as posted. Confirm on the call.", 14, 400, MUTE))
    y += 40
    return (f'<!doctype html><html><head><meta charset="utf-8">'
            f'<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Outfit:wght@500;700&family=IBM+Plex+Sans:wght@400;600;700&display=swap">'
            f'<style>html,body{{margin:0;background:{BG}}}</style></head><body>'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="600" height="{y}" viewBox="0 0 600 {y}">'
            f'<rect width="600" height="{y}" fill="{BG}"/>{"".join(parts)}</svg></body></html>')


def render_png(page_html: str, png: str) -> bool:
    """Screenshot the one-pager at 2x with the pre-installed Playwright (Node). False if it cannot run."""
    import subprocess
    import tempfile
    src = Path(tempfile.mkdtemp()) / "onepager.html"
    src.write_text(page_html, encoding="utf-8")
    js = ("const {chromium}=require('playwright');(async()=>{const b=await chromium.launch();"
          "const p=await b.newPage({viewport:{width:600,height:800},deviceScaleFactor:2});"
          f"await p.goto('file://{src}',{{waitUntil:'networkidle',timeout:20000}}).catch(()=>{{}});"
          f"await p.locator('svg').screenshot({{path:'{Path(png).resolve()}'}});await b.close()}})()")
    try:
        return subprocess.run(["node", "-e", js], capture_output=True, timeout=90).returncode == 0 and Path(png).exists()
    except (OSError, subprocess.TimeoutExpired):
        return False


def email_html(rows: list[dict], img_src: str | None) -> str:
    """The email body: the one-pager image, then 'Call first' as live text (tappable links and numbers).
    Without an image it is the table-only summary."""
    if not img_src:
        return build(rows)
    e = html.escape
    best = "".join(
        f'<tr><td style="padding:10px 0;border-top:1px solid {LINE};font-size:15px;line-height:1.45">'
        f'<a href="{e(r["url"])}" style="color:{NAVY};font-weight:600;text-decoration:none">{e(r["title"][:70])}</a><br>'
        f'<span style="color:{MUTE}">{AREA_NAMES.get(r["area"], r["area"].title())} · '
        f'{_money(float(r["price_bdt"])) if plausible_price(r) else "price on call"}'
        f'{f" · {int(float(r["size_sqft"])):,} sqft" if r["size_sqft"] else ""}'
        f'{f" · {e(r["phone"])}" if r["phone"] else ""}</span></td></tr>'
        for r in top_calls(rows, 5))
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:{BG};{SANS}">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{BG}"><tr><td align="center" style="padding:12px 0">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;{SANS}">
<tr><td><img src="{e(img_src)}" width="600" alt="MRA Property Hunt weekly: {len(rows)} new properties" style="display:block;width:100%;max-width:600px;height:auto;border:0"></td></tr>
<tr><td style="padding:4px 24px 24px"><div style="background:{CARD};border:1px solid {LINE};border-radius:14px;padding:18px 20px 8px">
<div style="{DISP};font-size:20px;font-weight:700;color:{NAVY};margin-bottom:6px">Call first</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{best}</table></div></td></tr>
</table></td></tr></table></body></html>"""


def make(lead_paths: list[str], stats_paths: list[str], out_dir: str) -> dict:
    """Write onepager.png and email.html (image referenced as cid:att0 for sending) plus preview.html (image by file name)."""
    rows = load(lead_paths)
    od = Path(out_dir)
    od.mkdir(parents=True, exist_ok=True)
    if not rows:  # an empty week still gets a short, honest email
        msg = f'<p style="{SANS};font-size:16px;color:{INK}">MRA Property Hunt: no new properties this week.</p>'
        for f in ("email.html", "preview.html"):
            (od / f).write_text(msg, encoding="utf-8")
        return {"rows": 0, "png": False}
    ok = render_png(onepager_html(rows, load_stats(stats_paths)), str(od / "onepager.png"))
    (od / "email.html").write_text(email_html(rows, "cid:att0" if ok else None), encoding="utf-8")
    (od / "preview.html").write_text(email_html(rows, "onepager.png" if ok else None), encoding="utf-8")
    return {"rows": len(rows), "png": ok}
