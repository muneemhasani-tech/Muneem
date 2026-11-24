"""Weekly summary for the associates: one email-safe HTML page built from the week's leads-YYYY-MM-DD.csv files.

Email clients strip <style>, scripts and most CSS, so everything is inline styles and tables; bars are table cells.
python -m property_finder weekly leads-*.csv --out weekly.html
"""
from __future__ import annotations

import collections
import csv
import datetime as dt
import html
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
