#!/usr/bin/env python3
"""
layer3_engine.py — Autonomous Grant Writer & UGC Royalty Dealership Engine (Layer 3 Runner).
Runs at 5:30 PM BDT (11:30 UTC) daily.
Consumes today's leads from Layer 2, generates the exact 2-Task Outreach Markdown digest,
updates 30-day campaign progress, and compiles the 30-Day Master Milestone Report on Day 30.
"""
import json
import sys
from datetime import datetime
from pathlib import Path
import memory
import draft_generator
import campaign_tracker
import layer2_scout

BASE_DIR = Path(__file__).resolve().parent
TODAY_LEADS_FILE = BASE_DIR / "today_leads.json"


def run_layer3(day: int = None, force_refresh: bool = True, dry_run: bool = False):
    memory.init_db()
    prog = campaign_tracker.get_progress()
    if day is None:
        day = prog.get("current_day", 1)
    
    # Ensure fresh, vertical-accurate Layer 2 leads exist for today
    needs_refresh = force_refresh or not TODAY_LEADS_FILE.exists()
    if not needs_refresh:
        try:
            with open(TODAY_LEADS_FILE, "r", encoding="utf-8") as f:
                leads_data = json.load(f)
                if leads_data.get("day") != day:
                    needs_refresh = True
        except Exception:
            needs_refresh = True
            
    if needs_refresh:
        leads_data = layer2_scout.run_layer2(day=day)
    else:
        with open(TODAY_LEADS_FILE, "r", encoding="utf-8") as f:
            leads_data = json.load(f)
            
    grant_lead = leads_data["grant_lead"]
    partner_lead = leads_data["partner_lead"]
    
    # 1. Generate Daily 2-Task Digest
    digest_path = draft_generator.generate_daily_digest(grant_lead, partner_lead)
    
    # 2. Update 30-day Campaign Progress (bypassed on dry_run)
    entry = campaign_tracker.record_daily_run(
        day_num=day,
        grant_lead=grant_lead,
        partner_lead=partner_lead,
        draft_file=str(digest_path.name),
        dry_run=dry_run
    )
    
    memory.log_task(f"Layer 3 Complete for Campaign Day {day}/30. Digest: {digest_path.name}", agent="LAYER_3")
    
    print("=" * 65)
    print(f"[LAYER 3 SUCCESS] CAMPAIGN DAY {day} OF 30 DELIVERED")
    print(f"Digest Path: {digest_path}")
    print(f"Task 1 (Grant): {grant_lead['org_name']}")
    print(f"Task 2 (Partner): {partner_lead['company_name']}")
    print(f"Next Target Day: {min(30, day + 1)}/30")
    if day >= 30:
        print("[MILESTONE ACHIEVED] 30-Day Master Campaign Portfolio compiled!")
    print("=" * 65)
    return {
        "day": day,
        "digest_path": str(digest_path),
        "status": "SUCCESS"
    }


if __name__ == "__main__":
    run_layer3()
