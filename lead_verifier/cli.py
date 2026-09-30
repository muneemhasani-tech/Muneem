"""`lead-verifier` command line."""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional

import httpx
import typer

from .cache import Cache
from .config import load_config, secrets
from .io_csv import OUT_COLS, build_leads, read_csv, write_outputs
from .pipeline import Pipeline, RunSummary
from .quota import Quota

app = typer.Typer(help="Grade raw leads by contactability before they enter the CRM.", no_args_is_help=True)
cache_app = typer.Typer(help="Manage the lookup cache.", no_args_is_help=True)
app.add_typer(cache_app, name="cache")

DEFERRED_REASONS = {"quota_exhausted", "provider_error"}


def _logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    # httpx logs full request URLs at INFO, which contain emails and API keys.
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)


def _execute(headers, rows, out_dir: Path, stem: str, cfg_path, offline_only: bool):
    cfg = load_config(cfg_path)
    cache = Cache(cfg["cache"]["path"])
    quota = Quota(cache, cfg["providers"], cfg["timezone"])
    leads = build_leads(headers, rows)

    async def go() -> RunSummary:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0)) as client:
            return await Pipeline(cfg, cache, quota, client, secrets(), offline_only=offline_only).run(leads)

    summary = asyncio.run(go())
    files = write_outputs(headers, leads, out_dir, stem)
    cache.close()
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
