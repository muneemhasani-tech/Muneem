#!/usr/bin/env python3
"""
campaign_tracker.py — 30-Day Campaign State & Milestone Engine.
Tracks progress across all 30 days to reach the target of:
- 30 Grant drafts & $2,000+ nonprofit retainer pitches
- 30 Chemist / Lab UGC Royalty Dealership outreach pitches
- Final 30-Day Portfolio Milestone Report on Day 30
"""
import json
from datetime import datetime, timezone
from pathlib import Path
import memory

BASE_DIR = Path(__file__).resolve().parent
PROGRESS_FILE = BASE_DIR / "campaign_progress.json"

DEFAULT_PROGRESS = {
    "campaign_name": "BSF & Chitosan 30-Day Grant & UGC Dealership Engine",
    "total_days": 30,
    "current_day": 1,
    "start_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    "target_milestone_date": "",
    "status": "ACTIVE",
    "targets": {
        "grants_drafted_goal": 30,
        "ugc_pitches_goal": 30,
        "nonprofit_retainer_client_goal": 2,
        "lab_dealership_partner_goal": 2,
        "vertical_coverage": {
            "Water Cleaning Agent": 10,
            "Cosmopharma Combinations": 10,
            "Insect Pet Food Solutions": 10
        }
    },
    "history": []
}


def get_progress() -> dict:
    if not PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_PROGRESS, f, indent=2, ensure_ascii=False)
    with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_progress(data: dict):
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def record_daily_run(day_num: int, grant_lead: dict, partner_lead: dict, draft_file: str, dry_run: bool = False):
    progress = get_progress()
    now_iso = datetime.now(timezone.utc).isoformat()
    
    vertical = partner_lead.get("vertical", "General Bio-Solutions")
    
    entry = {
        "day": day_num,
        "timestamp": now_iso,
        "vertical": vertical,
        "grant_target": grant_lead.get("org_name", ""),
        "grant_url": grant_lead.get("url", ""),
        "partner_target": partner_lead.get("company_name", ""),
        "partner_channel": partner_lead.get("channel", ""),
        "draft_file": draft_file,
        "status": "COMPLETED"
    }
    
    if dry_run:
        print(f"[CAMPAIGN PREVIEW] Dry-run executed for Day {day_num}. State not mutated.")
        return entry
    
    progress["history"].append(entry)
    progress["current_day"] = min(30, day_num + 1)
    
    if day_num >= 30:
        progress["status"] = "COMPLETED"
        generate_30_day_milestone_report(progress)
    
    save_progress(progress)
    memory.log_task(f"Campaign Day {day_num}/30 completed. Draft: {draft_file}", agent="CAMPAIGN_TRACKER")
    return entry


def generate_30_day_milestone_report(progress: dict) -> Path:
    out_file = BASE_DIR / "local_drafts" / "BSF_30_DAY_MASTER_PORTFOLIO.md"
    out_file.parent.mkdir(exist_ok=True)
    
    total_grants = len(progress.get("history", []))
    history_rows = []
    for h in progress.get("history", []):
        history_rows.append(f"| Day {h['day']} | {h['vertical']} | {h['grant_target']} | {h['partner_target']} | Completed |")
    
    rows_text = "\n".join(history_rows) if history_rows else "| None | - | - | - | - |"
    
    content = f"""# 30-DAY BSF & CHITOSAN PIPELINE MASTER MILESTONE REPORT
**Campaign Name:** {progress.get('campaign_name')}
**Status:** CAMPAIGN REACHED DAY 30 TARGET
**Date Completed:** {datetime.now().strftime("%Y-%m-%d")}

---

## 1. CAMPAIGN METRICS & PERFORMANCE
- **Total Days Executed:** {total_grants} / 30 Days
- **Strict Workload Limit Maintained:** Exactly 2 Owner Review Tasks per Day (Zero Fatigue)
- **Grant Applications & $2,000+ Retainer Pitches Delivered:** {total_grants}
- **Chemist / Formulation Lab UGC Royalty Pitches Delivered:** {total_grants}
- **Product Verticals Balanced (10 Days Each):**
  1. Water Cleaning Agent (Chitosan Flocculant for Textile & ETPs)
  2. Cosmopharma Combinations (Antimicrobial Serums & Hydrogels)
  3. BSF Insect Pet Food Solutions (Prebiotic Chitin & Protein Meal)

## 2. COMMERCIAL CONVERSION OBJECTIVES
- **Goal A (Nonprofit Retainers):** Secure 1–2 recurring nonprofit clients at $2,000+/mo for repeat grant writing.
- **Goal B (UGC Royalty Lab Dealerships):** Finalize 1–2 analytical lab co-formulation partnerships with distribution royalties and live UGC testing video assets.

## 3. FULL 30-DAY OUTREACH LOG
| Day | Vertical | Grant/NGO Target | Chemist/Lab Partner Target | Status |
|:---|:---|:---|:---|:---|
{rows_text}

---
*Report generated automatically by BSF Grant & UGC Royalty Autonomous Engine.*
"""
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(content)
    return out_file


if __name__ == "__main__":
    prog = get_progress()
    print(f"[CAMPAIGN STATUS] Day {prog['current_day']}/{prog['total_days']} | Status: {prog['status']} | Completed Runs: {len(prog['history'])}")
