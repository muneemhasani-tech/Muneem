#!/usr/bin/env python3
"""
master_orchestrator.py — Adaptive Master Campaign Orchestrator.
Dynamically coordinates all layers (1 through 5) based on campaign phase.
Prunes redundant early-phase tasks (e.g. cold scouting) as the pipeline advances into
follow-ups, deal term sheets, and month-end contract closing.
Always enforces the strict 2-Task Daily Owner Review limit.
"""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
import memory
import campaign_tracker
import campaign_phases
import layer2_scout
import layer3_engine
import layer4_followup_engine
import layer5_deal_closer
import daily_scout
import scheduler_manager

BASE_DIR = Path(__file__).resolve().parent


def run_orchestrator(force_day: int = None, dry_run: bool = False):
    memory.init_db()
    prog = campaign_tracker.get_progress()
    day = force_day if force_day is not None else prog.get("current_day", 1)
    
    plan = campaign_phases.evaluate_daily_execution_plan(day)
    phase_num = plan["phase_number"]
    
    print("=" * 70)
    print(f"BSF ADAPTIVE ORCHESTRATOR — DAY {day}/30 | {plan['phase_name'].upper()}")
    print(f"Primary Focus: {plan['focus']}")
    print("=" * 70)
    
    results = {
        "day": day,
        "phase": phase_num,
        "tasks_executed": [],
        "digest_created": None
    }
    
    # PHASE 1 (Days 1–7): Pipeline Seeding & Cold Outreach
    if phase_num == 1:
        print("[ORCHESTRATION: PHASE 1] Executing full discovery & cold outreach pipeline...")
        # Layer 1: Browser scout
        scout_res = daily_scout.run_daily_scout(dry_run=dry_run)
        results["tasks_executed"].append(f"Layer 1 Scout ({scout_res['vertical']})")
        # Layer 2 & 3: Cloud scraper & grant draft
        l3_res = layer3_engine.run_layer3(day=day, force_refresh=True, dry_run=dry_run)
        results["tasks_executed"].append("Layer 2/3 Cold Grant Draft & UGC Royalty Pitch")
        results["digest_created"] = l3_res["digest_path"]
        
    # PHASE 2 (Days 8–15): Warm Follow-Ups & Sample Requests
    elif phase_num == 2:
        print("[ORCHESTRATION: PHASE 2] Pruning cold browser scout tabs. Activating Layer 4 follow-ups...")
        fu_file = layer4_followup_engine.run_layer4_daily()
        # Also run Layer 3 to record today's lead progression without opening extra browser tabs
        l3_res = layer3_engine.run_layer3(day=day, force_refresh=True, dry_run=dry_run)
        results["tasks_executed"].append("Layer 4 Day 3/7 Follow-Up Engine")
        results["tasks_executed"].append("Layer 3 Lead Progression (Cold scouting bypassed)")
        results["digest_created"] = str(fu_file)
        
    # PHASE 3 (Days 16–22): Deal Terms, MoU & Retainer Negotiation
    elif phase_num == 3:
        print("[ORCHESTRATION: PHASE 3] Cold scouting completely retired. Activating Layer 5 contract closer...")
        # Generate formal term sheets for today's active candidates
        leads_data = layer2_scout.run_layer2()
        p_name = leads_data["partner_lead"]["company_name"]
        g_name = leads_data["grant_lead"]["org_name"]
        t1 = layer5_deal_closer.generate_lab_royalty_term_sheet(p_name, "Chief Formulation Chemist", leads_data["partner_lead"]["vertical"])
        t2 = layer5_deal_closer.generate_ngo_retainer_agreement(g_name, "Executive Director", leads_data["grant_lead"]["cause"])
        results["tasks_executed"].append(f"Layer 5 Lab Royalty Term Sheet -> {t1.name}")
        results["tasks_executed"].append(f"Layer 5 NGO Retainer Agreement -> {t2.name}")
        # Run follow-ups to maintain momentum
        layer4_followup_engine.run_layer4_daily()
        results["digest_created"] = str(t1)
        
    # PHASE 4 (Days 23–30): Final Contract Closing & 30-Day Master Portfolio
    else:
        print("[ORCHESTRATION: PHASE 4] Final Closing & 30-Day Master Milestone compilation...")
        leads_data = layer2_scout.run_layer2()
        layer3_engine.run_layer3()
        if day >= 30:
            milestone_file = campaign_tracker.generate_30_day_milestone_report(prog)
            print(f"[CAMPAIGN COMPLETED] 30-Day Master Portfolio compiled at {milestone_file}")
            results["digest_created"] = str(milestone_file)
            results["tasks_executed"].append("Day 30 Master Portfolio Consolidation")
            # Auto-prune the master schedule so no tasks linger after campaign completion
            scheduler_manager.retire_on_completion()
        else:
            results["tasks_executed"].append("Phase 4 Closing Protocol Active")
            
    memory.log_task(f"Master Orchestrator ran for Day {day} (Phase {phase_num})", agent="ORCHESTRATOR")
    print(f"\n[DONE] Today's tasks executed: {', '.join(results['tasks_executed'])}")
    print(f"Owner Deliverable: {results['digest_created']}")
    print("=" * 70)
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BSF Master Adaptive Orchestrator")
    parser.add_argument("--day", type=int, default=None, help="Force a specific campaign day (1-30) for testing")
    parser.add_argument("--dry-run", action="store_true", help="Bypass browser tab opening")
    args = parser.parse_args()
    
    run_orchestrator(force_day=args.day, dry_run=args.dry_run)
