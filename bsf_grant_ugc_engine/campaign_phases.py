#!/usr/bin/env python3
"""
campaign_phases.py — 4-Phase Progression Controller for the 30-Day Campaign.
Ensures early-stage tasks (e.g. cold exploratory scouting) evolve into deal progression,
follow-ups, and contract closing as the month advances. Tasks that only served early context
are phased out to protect the owner's strict 2-task daily cap.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
import memory
import campaign_tracker

BASE_DIR = Path(__file__).resolve().parent

PHASE_DEFINITIONS = {
    1: {
        "name": "Phase 1: Pipeline Seeding & Cold Outreach",
        "day_range": (1, 7),
        "primary_focus": "Cold prospecting across 3 verticals; seeding 14 grants and 14 lab targets.",
        "skip_raw_scouting": False,
        "active_layers": ["layer1", "layer2", "layer3"]
    },
    2: {
        "name": "Phase 2: Response Handling & Follow-Up Cadence",
        "day_range": (8, 15),
        "primary_focus": "Systematic follow-ups on unresponded leads; handling CoA/sample requests.",
        "skip_raw_scouting": True,  # Throttle raw scouting; shift daily review to warm follow-ups
        "active_layers": ["layer3", "layer4_followup"]
    },
    3: {
        "name": "Phase 3: Deal Terms, MoU & Grant Retainer Negotiation",
        "day_range": (16, 22),
        "primary_focus": "Issuing Preliminary Royalty Term Sheets to labs and $2,000+ Grant Retainer MoUs to NGOs.",
        "skip_raw_scouting": True,
        "active_layers": ["layer4_followup", "layer5_closer"]
    },
    4: {
        "name": "Phase 4: Contract Finalization, UGC Filming Lock-in & Master Portfolio",
        "day_range": (23, 30),
        "primary_focus": "Closing 1-2 recurring nonprofit clients and 1-2 lab dealership agreements with UGC filming dates.",
        "skip_raw_scouting": True,
        "active_layers": ["layer5_closer", "master_portfolio"]
    }
}


def get_current_phase(day: int = None) -> dict:
    if day is None:
        prog = campaign_tracker.get_progress()
        day = prog.get("current_day", 1)
    
    for phase_num, info in PHASE_DEFINITIONS.items():
        start, end = info["day_range"]
        if start <= day <= end:
            info_copy = dict(info)
            info_copy["phase_number"] = phase_num
            info_copy["current_day"] = day
            return info_copy
            
    # Default to Phase 4 if beyond 30
    fallback = dict(PHASE_DEFINITIONS[4])
    fallback["phase_number"] = 4
    fallback["current_day"] = day
    return fallback


def evaluate_daily_execution_plan(day: int = None) -> dict:
    phase = get_current_phase(day)
    day = phase["current_day"]
    
    plan = {
        "day": day,
        "phase_number": phase["phase_number"],
        "phase_name": phase["name"],
        "focus": phase["primary_focus"],
        "should_run_layer1_browser_scout": not phase["skip_raw_scouting"],
        "should_run_layer2_cold_scraper": not phase["skip_raw_scouting"],
        "should_run_layer4_followups": phase["phase_number"] >= 2,
        "should_run_layer5_closing_terms": phase["phase_number"] >= 3,
        "actions_today": []
    }
    
    if phase["phase_number"] == 1:
        plan["actions_today"] = [
            "Execute Layer 1 browser scout (2 tabs max)",
            "Execute Layer 2 deep scraper for #1 Grant and #1 Lab",
            "Generate daily cold grant draft and UGC royalty pitch"
        ]
    elif phase["phase_number"] == 2:
        plan["actions_today"] = [
            "Prioritize Day 3 & Day 7 follow-ups on unresponded prospects",
            "Issue technical CoA / specification sheets to inquiring labs",
            "Maintain strict 2-task owner limit by substituting cold scout with high-leverage follow-up"
        ]
    elif phase["phase_number"] == 3:
        plan["actions_today"] = [
            "Generate formal Preliminary Royalty & Regional Dealership Term Sheet",
            "Issue discounted Grant-Writing-as-a-Service retainer MoU ($2,000+ monthly model)",
            "Review compliance documentation with shortlisted NGOs"
        ]
    else:
        plan["actions_today"] = [
            "Lock in 1–2 final nonprofit retainer contracts",
            "Lock in 1–2 lab UGC on-camera filming schedules in Dhaka",
            "Compile 30-Day Master Campaign Portfolio Report"
        ]
        
    return plan


if __name__ == "__main__":
    for d in [1, 8, 16, 25, 30]:
        p = evaluate_daily_execution_plan(d)
        print(f"Day {d:02d} -> Phase {p['phase_number']} ({p['phase_name']}) | Skip Cold Scout: {not p['should_run_layer1_browser_scout']}")
