#!/usr/bin/env python3
"""
layer2_scout.py — Cloud Intelligence Scraper (Layer 2 Runner).
Runs at 4:30 PM BDT (10:30 UTC) daily.
Determines today's active vertical, selects the #1 Grant/NGO target and #1 Chemist/Lab target,
deduplicates via memory.py, and stages today_leads.json for Layer 3.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
import memory
import scout
import campaign_tracker

BASE_DIR = Path(__file__).resolve().parent
TODAY_LEADS_FILE = BASE_DIR / "today_leads.json"

# Curated High-Yield Directory Matrix for Bangladesh & Global Verticals
CURATED_TARGET_POOL = [
    # Vertical 0: Water Cleaning Flocculants
    {
        "grants": [
            {"org_name": "UNDP Bangladesh Water & Climate Resilient Ecosystems", "cause": "Industrial & Textile Effluent Water Remediation", "url": "https://www.undp.org/bangladesh/projects/water-effluent-remediation", "deadline": "Rolling / Call 2026-Q4"},
            {"org_name": "ADB Water Innovation Trust Fund (Bangladesh Pilot)", "cause": "Circular Wastewater Treatment with Bio-flocculants", "url": "https://www.adb.org/what-we-do/funds/water-financing-partnership-facility", "deadline": "Rolling / Bi-annual"},
            {"org_name": "PKSF Community Water Quality Enhancement Fund", "cause": "Municipal and Aquaculture Clean Water Treatment", "url": "https://pksf.org.bd/water-quality-initiatives", "deadline": "Open Call"}
        ],
        "partners": [
            {"company_name": "Dhaka Analytical Services & ETP Solutions", "contact_role": "Chief Formulation Chemist", "vertical": "Water Cleaning Agent (Chitosan Flocculant)", "channel": "LinkedIn + Direct WhatsApp / Email"},
            {"company_name": "BCSIR Industrial Chemistry & Water Quality Division", "contact_role": "Senior Research Scientist & Lab Head", "vertical": "Water Cleaning Agent (Chitosan Flocculant)", "channel": "Direct Laboratory Visit / Email"},
            {"company_name": "Textile Effluent Treatment Formulators Ltd (Gazipur)", "contact_role": "Head of Technical R&D", "vertical": "Water Cleaning Agent (Chitosan Flocculant)", "channel": "LinkedIn + WhatsApp"}
        ]
    },
    # Vertical 1: Cosmopharma & Skincare Biopolymers
    {
        "grants": [
            {"org_name": "Horizon Europe Bio-based Circular Materials Call", "cause": "High-Value Insect Chitosan Dermal & Medical Hydrogels", "url": "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/programmes/horizon", "deadline": "Quarterly Submission"},
            {"org_name": "Bill & Melinda Gates Global Health Innovation Challenge", "cause": "Low-Cost Antimicrobial Wound Dressings in Emerging Markets", "url": "https://www.gatesfoundation.org/ideas/grant-opportunities", "deadline": "Open Window"},
            {"org_name": "Bangladesh Biotech Development Board Innovation Grant", "cause": "Indigenous Biopolymer Production for Pharma Applications", "url": "https://biotech.gov.bd/grants", "deadline": "Annual Call"}
        ],
        "partners": [
            {"company_name": "Square Formulations & Analytical QC Laboratory Dhaka", "contact_role": "Principal Formulation Scientist (Cosmeceuticals)", "vertical": "Cosmopharma & Biopolymer Skincare", "channel": "LinkedIn + Executive Email"},
            {"company_name": "Incepta Bio-R&D Special Products Division", "contact_role": "Head of Biopolymer Sourcing & R&D", "vertical": "Cosmopharma & Biopolymer Skincare", "channel": "Corporate LinkedIn / Email"},
            {"company_name": "Apex Cosmeceuticals R&D Facility (Tejgaon)", "contact_role": "Lead Product Development Chemist", "vertical": "Cosmopharma & Biopolymer Skincare", "channel": "WhatsApp + Direct Pitch"}
        ]
    },
    # Vertical 2: BSF Insect Pet Food & Prebiotic Chitin
    {
        "grants": [
            {"org_name": "Global Sustainable Aquaculture & Protein Innovation Fund", "cause": "Alternative Insect Protein & Prebiotic Gut Health for Fish/Pets", "url": "https://sustainableaquaculture.fund/grants-2026", "deadline": "Rolling"},
            {"org_name": "World Bank / Bangladesh Livestock & Dairy Development Project (LDDP)", "cause": "Sustainable Non-Soy Non-Fishmeal Animal Nutrition", "url": "https://lddp.mofl.gov.bd/grants", "deadline": "Annual Tranche"},
            {"org_name": "Good Food Institute (GFI) Alternative Protein Grant", "cause": "Insect Prebiotic Fiber & Defatted Meal Nutrition Science", "url": "https://gfi.org/researchgrants", "deadline": "Rolling Cycle"}
        ],
        "partners": [
            {"company_name": "Bengal Feed & Nutrition Mills (Pet & Aqua Division)", "contact_role": "Chief Animal Nutritionist & Formulation Director", "vertical": "BSF Insect Pet Food & Prebiotic Chitin", "channel": "Direct Call / LinkedIn"},
            {"company_name": "Nourish Pet Care & Companion Nutrition Lab", "contact_role": "Head of New Product Development", "vertical": "BSF Insect Pet Food & Prebiotic Chitin", "channel": "LinkedIn + Direct WhatsApp"},
            {"company_name": "Quality Feeds R&D Center (Savar, Dhaka)", "contact_role": "Technical Director (Aqua & Pet SKU Development)", "vertical": "BSF Insect Pet Food & Prebiotic Chitin", "channel": "Email / Dealership Meeting"}
        ]
    }
]


def run_layer2(day: int = None, force_refresh: bool = True):
    memory.init_db()
    prog = campaign_tracker.get_progress()
    if day is None:
        day = prog.get("current_day", 1)
    
    vertical_idx = (day - 1) % len(CURATED_TARGET_POOL)
    active_pool = CURATED_TARGET_POOL[vertical_idx]
    
    # Select first unseen grant and unseen partner
    res_data = memory.read_json("research")
    seen_urls = set(res_data.get("seen_urls", []))
    
    selected_grant = None
    for g in active_pool["grants"]:
        if g["url"].lower() not in seen_urls:
            selected_grant = g
            break
    if not selected_grant:
        selected_grant = active_pool["grants"][(day - 1) % len(active_pool["grants"])]
    
    selected_partner = None
    for p in active_pool["partners"]:
        # create synthetic tracking identifier
        p_id = f"partner_{p['company_name'].lower().replace(' ', '_')}"
        if p_id not in seen_urls:
            selected_partner = p
            break
    if not selected_partner:
        selected_partner = active_pool["partners"][(day - 1) % len(active_pool["partners"])]
    
    # Add to memory research db
    memory.add_lead("grant", selected_grant)
    memory.add_lead("partner", selected_partner)
    
    handoff = {
        "day": day,
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "vertical_index": vertical_idx,
        "vertical_name": scout.QUERY_MATRIX[vertical_idx]["vertical"],
        "grant_lead": selected_grant,
        "partner_lead": selected_partner
    }
    
    with open(TODAY_LEADS_FILE, "w", encoding="utf-8") as f:
        json.dump(handoff, f, indent=2, ensure_ascii=False)
        
    # Synchronize search_log rotation index
    slog = memory.read_json("search_log")
    slog["rotation_index"] = (vertical_idx + 1) % len(scout.QUERY_MATRIX)
    memory.write_json("search_log", slog)
        
    memory.log_task(f"Layer 2 Scout complete for Day {day}: Selected Grant '{selected_grant['org_name']}' & Partner '{selected_partner['company_name']}'", agent="LAYER_2")
    print(f"[LAYER 2 OK] Day {day}/30 | Vertical: {handoff['vertical_name']}")
    print(f"  #1 Grant: {selected_grant['org_name']}")
    print(f"  #1 Partner: {selected_partner['company_name']}")
    return handoff


if __name__ == "__main__":
    run_layer2()
