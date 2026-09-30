"""`lead-verifier` command line."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import typer

from .cache import Cache
from .config import load_config
from .io_csv import OUT_COLS, build_leads, read_csv, write_outputs
from .pipeline import RunSummary
from .quota import Quota
from .service import check_one, grade_leads, keys_configured

app = typer.Typer(help="Grade raw leads by contactability before they enter the CRM.", no_args_is_help=True)
cache_app = typer.Typer(help="Manage the lookup cache.", no_args_is_help=True)
app.add_typer(cache_app, name="cache")

DEFERRED_REASONS = {"quota_exhausted", "provider_error"}


def _logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    # httpx logs full request URLs at INFO, which contain emails and API keys.
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)
    for name in ("urllib3", "whoisit", "whois"):  # retry chatter from the RDAP/WHOIS libraries
        logging.getLogger(name).setLevel(logging.ERROR)


def _execute(headers, rows, out_dir: Path, stem: str, cfg_path, offline_only: bool):
    cfg = load_config(cfg_path)
    leads = build_leads(headers, rows)
    summary = grade_leads(leads, cfg, offline_only)
    files = write_outputs(headers, leads, out_dir, stem)
    _report(summary, files, offline_only)


def _report(s: RunSummary, files: dict, offline_only: bool) -> None:
    g = s.grades
    typer.echo(f"\nRows in: {s.rows_in}")
    typer.echo(f"A: {g['A']}   B: {g['B']}   C: {g['C']}   REJECT: {g['REJECT']}")
    used = ", ".join(f"{k}={v}" for k, v in sorted(s.credits.items() )) or "none"
    typer.echo(f"Credits used this run: {used}" + ("  (offline-only)" if offline_only else ""))
    typer.echo(f"Rows deferred: {s.deferred}" + ("  -> run `lead-verifier resume <graded.csv>` later" if s.deferred else ""))
    for path in files.values():
        typer.echo(f"  wrote {path}")


@app.command()
def run(
    input_csv: Path = typer.Argument(..., exists=True, dir_okay=False),
    offline_only: bool = typer.Option(False, "--offline-only", help="Phone + syntax + MX only; zero API credits."),
    limit: Optional[int] = typer.Option(None, "--limit", min=1, help="Only the first N rows."),
    out_dir: Path = typer.Option(Path("data/output"), "--out-dir"),
    config: Optional[Path] = typer.Option(None, "--config"),
) -> None:
    """Grade a raw leads CSV."""
    _logging()
    headers, rows = read_csv(input_csv)
    if not headers:
        raise typer.BadParameter("input CSV is empty")
    _execute(headers, rows[:limit], out_dir, input_csv.stem, config, offline_only)


@app.command()
def resume(
    graded_csv: Path = typer.Argument(..., exists=True, dir_okay=False),
    out_dir: Optional[Path] = typer.Option(None, "--out-dir", help="Defaults to the file's folder."),
    config: Optional[Path] = typer.Option(None, "--config"),
) -> None:
    """Re-check quota-deferred rows of a graded file. Cached answers cost zero credits."""
    _logging()
    headers, rows = read_csv(graded_csv)
    n = len(OUT_COLS)
    tail = [h.removeprefix("lv_") for h in headers[-n:]]
    if tail != OUT_COLS:
        raise typer.BadParameter("not a graded file produced by `lead-verifier run`")
    status_i, reason_i = len(headers) - n + OUT_COLS.index("email_status"), len(headers) - n + OUT_COLS.index("email_reason")
    todo = sum(1 for r in rows if r[status_i] == "unknown" and r[reason_i] in DEFERRED_REASONS)
    if not todo:
        typer.echo("Nothing to resume: no rows are deferred.")
        raise typer.Exit()
    typer.echo(f"Re-checking {todo} deferred row(s); everything already answered comes from cache.")
    stem = graded_csv.stem.removesuffix("_graded")
    _execute(headers[:-n], [r[:-n] for r in rows], out_dir or graded_csv.parent, stem, config, False)


@app.command()
def quota(config: Optional[Path] = typer.Option(None, "--config")) -> None:
    """Show today's usage per provider."""
    cfg = load_config(config)
    cache = Cache(cfg["cache"]["path"])
    q = Quota(cache, cfg["providers"], cfg["timezone"])
    typer.echo(f"{'provider':<24}{'day':<12}{'used':>6}{'limit':>8}{'left':>7}")
    for p in cfg["providers"]:
        typer.echo(f"{p:<24}{q.day(p):<12}{q.used(p):>6}{q.limit(p):>8}{q.remaining(p):>7}")
    cache.close()


@cache_app.command("clear")
def cache_clear(
    kind: Optional[str] = typer.Option(None, "--kind", help="email | reputation | age | mx | whatsapp (default: all)"),
    config: Optional[Path] = typer.Option(None, "--config"),
) -> None:
    """Delete cached lookups (quota counters are kept)."""
    cfg = load_config(config)
    cache = Cache(cfg["cache"]["path"])
    typer.echo(f"Deleted {cache.clear(kind)} cached lookup(s)" + (f" of kind '{kind}'." if kind else "."))
    cache.close()


EMAIL_HUMAN = {
    "valid": "the mailbox exists",
    "invalid_syntax": "not a valid email format (typo?)",
    "no_mx": "this domain can't receive mail",
    "mailbox_not_found": "this mailbox doesn't exist",
    "disposable": "throwaway address",
    "accept_all": "can't confirm the inbox (domain accepts everything)",
    "role_address": "shared inbox (info@, sales@ ...)",
    "not_api_checked": "format and mail server OK, mailbox not confirmed",
    "no_api_key": "format and mail server OK, mailbox not confirmed (add QEV_API_KEY to confirm)",
    "quota_exhausted": "today's email checks are used up, try again tomorrow",
    "mx_check_failed": "couldn't reach DNS, check your internet",
    "no_email": "no email given",
}

GRADE_TEXT = {
    "A": "A  -  Call this lead now",
    "B": "B  -  Good lead, worth a call",
    "C": "C  -  Weak contact, low priority",
    "REJECT": "REJECT  -  Do not add to the CRM",
}


@app.command()
def check(
    phone: str = typer.Option("", "--phone", "-p"),
    email: str = typer.Option("", "--email", "-e"),
    website: str = typer.Option("", "--website", "-w"),
    offline_only: bool = typer.Option(False, "--offline-only"),
    config: Optional[Path] = typer.Option(None, "--config"),
) -> None:
    """Check a single lead and print a plain-English report."""
    _logging()
    lead, s = check_one(phone, email, website, load_config(config), offline_only)
    p, e, d = lead.phone, lead.email_result, lead.domain
    typer.echo(f"\n  RESULT: {GRADE_TEXT[lead.grade]}\n")
    if phone:
        detail = f"{p.e164}  {p.type.replace('_', ' ')}  {p.carrier}".strip() if p.valid else f"not a valid number ({p.reason})"
        typer.echo(f"  Phone    {'OK  ' if p.valid else 'FAIL'} {detail}")
    if email:
        mark = {"valid": "OK  ", "invalid": "FAIL", "risky": "WARN"}.get(e.status, "?   ")
        typer.echo(f"  Email    {mark} {EMAIL_HUMAN.get(e.reason if e.status != 'valid' else 'valid', e.reason)}")
    if lead.domain.domain:
        flag = {True: "FLAGGED on " + "+".join(d.sources), False: "safe (no blocklist hits)",
                None: "safety not checked (needs GOOGLE_WEBRISK_API_KEY / URLHAUS_AUTH_KEY)"}[d.flagged]
        age = f"{d.age_days} days old" if d.age_days is not None else "age unknown"
        typer.echo(f"  Website  {'FAIL' if d.flagged else 'OK  ' if d.flagged is False else '?   '} {d.domain}: {flag}; {age}")
    typer.echo(f"\n  Why: {'; '.join(lead.reasons)}")
    used = ", ".join(f"{k}={v}" for k, v in sorted(s.credits.items()) if v) or "none"
    typer.echo(f"  Paid lookups used: {used}\n")


@app.command()
def ui(
    port: int = typer.Option(8765, "--port"),
    no_browser: bool = typer.Option(False, "--no-browser"),
    config: Optional[Path] = typer.Option(None, "--config"),
) -> None:
    """Open the point-and-click web app (runs only on this computer)."""
    from .web import serve

    _logging()
    srv = serve(load_config(config), port, open_browser=not no_browser)
    typer.echo(f"Lead Verifier is running at http://127.0.0.1:{srv.server_port}  (Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        typer.echo("Stopped.")
