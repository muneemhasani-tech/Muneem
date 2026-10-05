"""Investment projections for properties for sale. Rent is used here and nowhere else."""
from __future__ import annotations

import json
import statistics

DEFAULTS = {
    "rent_psf": {"gulshan": 55, "banani": 50, "dhanmondi": 45, "bashundhara": 35, "uttara": 32, "purbachal": 28},  # ৳ per sqft per month, placeholders
    "vacancy_months": 1, "cost_pct": 15, "growth_pct": 6, "years": 5,
}
MIN_OBS = 5  # rent observations needed before a measured benchmark replaces the placeholder


def load(con) -> dict:
    a = json.loads(json.dumps(DEFAULTS))
    row = con.execute("SELECT value FROM settings WHERE key='assumptions'").fetchone()
    if row:
        saved = json.loads(row[0])
        a["rent_psf"].update({k: float(v) for k, v in saved.get("rent_psf", {}).items() if v not in (None, "")})
        for k in ("vacancy_months", "cost_pct", "growth_pct"):
            if saved.get(k) not in (None, ""):
                a[k] = float(saved[k])
    return a


def save(con, a: dict) -> None:
    clean = {"rent_psf": {k: float(v) for k, v in (a.get("rent_psf") or {}).items() if str(v) != ""},
             **{k: float(a[k]) for k in ("vacancy_months", "cost_pct", "growth_pct") if a.get(k) not in (None, "")}}
    con.execute("INSERT INTO settings(key,value) VALUES('assumptions',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (json.dumps(clean),))
    con.commit()


def benchmarks(con) -> dict[str, tuple[float, int]]:
    """Measured median rent per sqft per area from rent pages we crawled (never shown as listings)."""
    by: dict[str, list[float]] = {}
    for area, psf in con.execute("SELECT area, rent/size_sqft FROM rent_obs WHERE size_sqft>0 AND rent/size_sqft BETWEEN 8 AND 400"):
        by.setdefault(area, []).append(psf)
    return {a: (statistics.median(v), len(v)) for a, v in by.items() if len(v) >= MIN_OBS}


def project(r: dict, a: dict, bench: dict) -> dict:
    """Gross yield, net yield and total return over `years` for one sale listing."""
    price, size, area = r.get("price") or 0, r.get("size_sqft") or 0, r.get("area")
    g, yrs = a["growth_pct"] / 100, int(a["years"])
    growth = ((1 + g) ** yrs - 1) * 100
    out = {"rent_est": None, "gross": None, "net": None, "total": round(growth, 1) if price else None,
           "rent_basis": "", "growth_only": r.get("ptype") == "land"}
    if not price or not size or r.get("ptype") == "land":
        return out
    if area in bench:
        psf, basis = bench[area][0], f"measured from {bench[area][1]} rent ads"
    else:
        psf, basis = a["rent_psf"].get(area, 0), "your assumption"
    rent = size * psf
    if rent * 12 / price > 0.25:  # a 25%+ gross yield means the advertised price is wrong (often per sqft or a typo)
        out.update(rent_basis="price looks wrong, check the listing", total=None)
        return out
    net_year = rent * (12 - a["vacancy_months"]) * (1 - a["cost_pct"] / 100)
    out.update(rent_est=round(rent), rent_basis=basis, gross=round(rent * 12 / price * 100, 2),
               net=round(net_year / price * 100, 2), total=round((net_year * yrs / price + (1 + g) ** yrs - 1) * 100, 1))
    return out
