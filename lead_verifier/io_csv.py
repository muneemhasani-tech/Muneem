"""CSV in/out: alias-based column mapping, original columns preserved verbatim."""
from __future__ import annotations

import csv
import io
from pathlib import Path

from .models import Lead

ALIASES = {
    "name": ["name", "full_name", "full name", "client"],
    "phone": ["phone", "mobile", "number", "contact", "whatsapp"],
    "email": ["email", "e-mail", "mail"],
    "website": ["website", "url", "site", "domain"],
    "source": ["source", "platform", "origin"],
}

OUT_COLS = [
    "phone_e164", "phone_valid", "phone_type", "phone_carrier", "phone_duplicate_of",
    "email_status", "email_reason", "domain", "domain_flagged", "domain_flag_source",
    "domain_age_days", "grade", "grade_reasons", "checked_at",
]


def read_csv(path: str | Path) -> tuple[list[str], list[list[str]]]:
    """Returns (headers, rows). Rows are padded to header width; fully blank lines dropped."""
    return read_csv_text(Path(path).read_bytes())


def read_csv_text(raw: bytes) -> tuple[list[str], list[list[str]]]:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252", errors="replace")
    rows = list(csv.reader(io.StringIO(text, newline="")))
    if not rows:
        return [], []
    headers, body = rows[0], [r for r in rows[1:] if any(c.strip() for c in r)]
    width = max([len(headers)] + [len(r) for r in body])
    headers = headers + [f"column_{i + 1}" for i in range(len(headers), width)]
    return headers, [r + [""] * (width - len(r)) for r in body]


def map_columns(headers: list[str]) -> dict[str, list[int]]:
    """canonical -> column indexes (alias order first, then left-to-right)."""
    low = [h.strip().lower() for h in headers]
    out: dict[str, list[int]] = {}
    for canon, aliases in ALIASES.items():
        idx: list[int] = []
        for a in aliases:
            idx += [i for i, h in enumerate(low) if h == a and i not in idx]
        out[canon] = idx
    return out


def build_leads(headers: list[str], rows: list[list[str]]) -> list[Lead]:
    cmap = map_columns(headers)

    def pick(cells: list[str], canon: str) -> str:
        for i in cmap[canon]:
            if cells[i].strip():
                return cells[i].strip()
        return ""

    return [
        Lead(
            row_num=n, cells=cells, name=pick(cells, "name"), phone_raw=pick(cells, "phone"),
            email_raw=pick(cells, "email"), website_raw=pick(cells, "website"),
            source=pick(cells, "source"),
        )
        for n, cells in enumerate(rows, start=1)
    ]


def out_headers(headers: list[str]) -> list[str]:
    """Appended column names; on collision with an input header, prefix with `lv_`."""
    existing = {h.strip().lower() for h in headers}
    return [f"lv_{c}" if c in existing else c for c in OUT_COLS]


def _b(v: bool | None) -> str:
    return "" if v is None else ("true" if v else "false")


def lead_values(l: Lead) -> list[str]:
    d = l.domain
    src = "" if not d.flagged else ("both" if len(d.sources) > 1 else d.sources[0])
    return [
        l.phone.e164, _b(l.phone.valid), l.phone.type, l.phone.carrier,
        "" if l.duplicate_of is None else str(l.duplicate_of),
        l.email_result.status, l.email_result.reason, d.domain, _b(d.flagged), src,
        "" if d.age_days is None else str(d.age_days), l.grade, ";".join(l.reasons), l.checked_at,
    ]


def _write(path: Path, headers: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # utf-8-sig: BOM makes Google Sheets/Excel read Bangla text correctly.
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(headers)
        w.writerows(rows)


def write_outputs(
    headers: list[str], leads: list[Lead], out_dir: str | Path, stem: str
) -> dict[str, Path]:
    """Writes <stem>_graded.csv plus <stem>_A_B / _C / _REJECT splits."""
    out = Path(out_dir)
    hdr = headers + out_headers(headers)
    rows = [(l.grade, l.cells + lead_values(l)) for l in leads]
    files = {
        "graded": (out / f"{stem}_graded.csv", [r for _, r in rows]),
        "A_B": (out / f"{stem}_A_B.csv", [r for g, r in rows if g in ("A", "B")]),
        "C": (out / f"{stem}_C.csv", [r for g, r in rows if g == "C"]),
        "REJECT": (out / f"{stem}_REJECT.csv", [r for g, r in rows if g == "REJECT"]),
    }
    for path, body in files.values():
        _write(path, hdr, body)
    return {k: p for k, (p, _) in files.items()}


def write_plain(path: str | Path, headers: list[str], rows: list[list[str]]) -> None:
    _write(Path(path), headers, rows)
