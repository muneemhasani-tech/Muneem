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
TYPES = [("apartment", "Flats", "#1f3a8a"), ("land", "Plots / land", "#c8922a"), ("house", "Houses / duplexes", "#2a9d8f")]
INK, MUTE, LINE, BG, CARD, NAVY = "#101a3a", "#56607f", "#d5d9e6", "#f3f4f8", "#ffffff", "#0b163e"
FONT = "font-family:Segoe UI,Helvetica,Arial,sans-serif"


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
    cells = "".join(f'<td width="{max(1, round(100 * n / total))}%" style="background:{c};height:14px;font-size:0;line-height:0">&nbsp;</td>'
                    for n, c in parts if n)
    return (f'<table role="presentation" cellpadding="0" cellspacing="0" width="{max(2, width)}%" style="border-collapse:collapse">'
            f"<tr>{cells}</tr></table>")


def _section(title: str, body: str, note: str = "") -> str:
    n = f'<p style="margin:6px 0 0;color:{MUTE};font-size:13px">{note}</p>' if note else ""
    return (f'<tr><td style="padding:22px 24px 0"><h2 style="margin:0 0 12px;font-size:17px;color:{NAVY}">{title}</h2>'
            f"{body}{n}</td></tr>")


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
                              ("Other websites" if r["site"].startswith("Open web") else r["site"]) for r in rows)
    e = html.escape

    def tile(num, label, sub=""):
        s = f'<div style="color:{MUTE};font-size:12px;margin-top:2px">{sub}</div>' if sub else ""
        return (f'<td width="25%" style="padding:6px"><div style="background:{CARD};border:1px solid {LINE};border-radius:8px;padding:12px 10px">'
                f'<div style="font-size:26px;font-weight:700;color:{INK}">{num}</div>'
                f'<div style="color:{MUTE};font-size:13px">{label}</div>{s}</div></td>')

    tiles = (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
             f'{tile(total, "new properties", f"{len(days)} days, no repeats")}'
             f'{tile(f"{round(100 * by_type["apartment"] / total)}%", "are flats", f"{by_type["land"]} plots, {by_type["house"]} houses")}'
             f'{tile(phone, "with a phone", f"{round(100 * phone / total)}% of all")}'
             f'{tile(priced, "with a price", f"{round(100 * priced / total)}% of all")}</tr></table>')

    peak = max(by_day.values())
    day_rows = "".join(
        f'<tr><td style="padding:4px 10px 4px 0;color:{MUTE};font-size:13px;white-space:nowrap" width="70">'
        f'{dt.date.fromisoformat(d).strftime("%a %d %b")}</td>'
        f'<td style="padding:4px 0">{_bar([(by_day[d], NAVY)], by_day[d], round(100 * by_day[d] / peak))}</td>'
        f'<td style="padding:4px 0 4px 10px;font-weight:600;font-size:13px;color:{INK}" width="30" align="right">{by_day[d]}</td></tr>'
        for d in days)
    daily = f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{day_rows}</table>'

    legend = " &nbsp; ".join(f'<span style="display:inline-block;width:10px;height:10px;background:{c};border-radius:2px"></span>'
                             f' <span style="font-size:12px;color:{MUTE}">{n}</span>' for _, n, c in TYPES)
    top = by_area.most_common(1)[0][1]
    area_rows = "".join(
        f'<tr><td style="padding:5px 10px 5px 0;font-size:13px;color:{INK};white-space:nowrap" width="110">{AREA_NAMES.get(a, a.title())}</td>'
        f'<td style="padding:5px 0">{_bar([(cell[(a, t)], c) for t, _, c in TYPES], n, round(100 * n / top))}</td>'
        f'<td style="padding:5px 0 5px 10px;font-weight:600;font-size:13px;color:{INK}" width="30" align="right">{n}</td></tr>'
        for a, n in by_area.most_common())
    area_chart = (f'<div style="margin-bottom:8px">{legend}</div>'
                  f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{area_rows}</table>')

    th = f'style="padding:7px 8px;border-bottom:2px solid {LINE};font-size:12px;color:{MUTE};text-align:right;font-weight:600"'
    td = f'style="padding:7px 8px;border-bottom:1px solid {LINE};font-size:13px;color:{INK};text-align:right"'
    head = (f'<tr><th {th.replace("text-align:right", "text-align:left")}>Area</th>'
            + "".join(f"<th {th}>{n}</th>" for _, n, _ in TYPES) + f"<th {th}>Total</th></tr>")
    body = "".join(
        f'<tr><td {td.replace("text-align:right", "text-align:left")}>{AREA_NAMES.get(a, a.title())}</td>'
        + "".join(f"<td {td}>{cell[(a, t)] or '–'}</td>" for t, _, _ in TYPES) + f"<td {td}><b>{n}</b></td></tr>"
        for a, n in by_area.most_common())
    foot = (f'<tr><td {td.replace("text-align:right", "text-align:left")}><b>All areas</b></td>'
            + "".join(f"<td {td}><b>{by_type[t]}</b></td>" for t, _, _ in TYPES) + f"<td {td}><b>{total}</b></td></tr>")
    table = f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse">{head}{body}{foot}</table>'

    stop = src.most_common(1)[0][1]
    src_rows = "".join(
        f'<tr><td style="padding:4px 10px 4px 0;font-size:13px;color:{INK};white-space:nowrap" width="110">{e(s)}</td>'
        f'<td style="padding:4px 0">{_bar([(n, "#7a86b8")], n, round(100 * n / stop))}</td>'
        f'<td style="padding:4px 0 4px 10px;font-weight:600;font-size:13px;color:{INK}" width="30" align="right">{n}</td></tr>'
        for s, n in src.most_common())
    sources = f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{src_rows}</table>'

    best = "".join(
        f'<tr><td style="padding:8px 0;border-bottom:1px solid {LINE};font-size:13px;color:{INK}">'
        f'<a href="{e(r["url"])}" style="color:{NAVY};font-weight:600;text-decoration:none">{e(r["title"][:80])}</a><br>'
        f'<span style="color:{MUTE}">{AREA_NAMES.get(r["area"], r["area"].title())} · '
        f'{_money(float(r["price_bdt"])) if plausible_price(r) else "price not given"}'
        f'{f" · {int(float(r["size_sqft"])):,} sqft" if r["size_sqft"] else ""} · {e(r["phone"]) or "message on post"}</span></td></tr>'
        for r in top_calls(rows, 5))
    best_t = f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{best}</table>'

    lead_area, lead_n = by_area.most_common(1)[0]
    plots = collections.Counter(r["area"] for r in rows if r["type"] == "land").most_common(2)
    takeaways = [
        f"<b>{AREA_NAMES.get(lead_area, lead_area)}</b> had the most new listings ({lead_n} of {total}).",
        "Plots and katha land are concentrated in " + " and ".join(f"<b>{AREA_NAMES.get(a, a)}</b> ({n})" for a, n in plots) + ".",
        f"{total - phone} listings show no phone number: message the seller on the post.",
    ]
    tk = "".join(f'<li style="margin:0 0 6px">{t}</li>' for t in takeaways)

    period = f'{start.strftime("%d %b")} – {end.strftime("%d %b %Y")}'
    sections = (
        _section("This week at a glance", tiles)
        + _section("Key points", f'<ul style="margin:0;padding-left:18px;color:{INK};font-size:14px;line-height:1.5">{tk}</ul>')
        + _section("New properties by area and type", area_chart)
        + _section("The numbers", table)
        + _section("New properties per day", daily, "Each day counts only listings never sent before.")
        + _section("Where they were found", sources)
        + _section("5 strongest leads of the week", best_t, "Ranked by: phone number shown, owner selling, a realistic price, size stated.")
    )
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MRA weekly property summary</title></head>
<body style="margin:0;padding:0;background:{BG};{FONT}">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{BG}"><tr><td align="center" style="padding:20px 10px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:640px;background:{CARD};border:1px solid {LINE};border-radius:10px;{FONT}">
<tr><td style="background:{NAVY};padding:20px 24px;border-radius:10px 10px 0 0">
<div style="color:#c8922a;font-size:12px;letter-spacing:1.5px;font-weight:700">MRA REAL ESTATE · PROPERTY SCOUT</div>
<div style="color:#ffffff;font-size:22px;font-weight:700;margin-top:4px">Weekly summary</div>
<div style="color:#c9cfe6;font-size:14px;margin-top:2px">{period} · Gulshan, Banani, Purbachal, Uttara, Dhanmondi, Bashundhara</div></td></tr>
{sections}
<tr><td style="padding:22px 24px 24px;color:{MUTE};font-size:12px;line-height:1.5">Found by daily Google searches of Bproperty, Bikroy, bdHousing,
Bdstall and Facebook groups. Prices and sizes are as the seller posted them: confirm on the call. The full daily lists are in your
daily "MRA fresh leads" emails.</td></tr>
</table></td></tr></table></body></html>"""


def write(paths: list[str], out: str) -> dict:
    rows = load(paths)
    Path(out).write_text(build(rows), encoding="utf-8")
    return {"rows": len(rows), "out": out}
