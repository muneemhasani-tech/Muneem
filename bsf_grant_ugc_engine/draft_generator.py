#!/usr/bin/env python3
"""
draft_generator.py — Validates and generates the exact 2-Task Daily Deliverable markdown
used by Layer 3 Cloud Agents, enforcing the Grant Writing Rules and UGC Royalty structure.
"""
from datetime import datetime
from pathlib import Path
import memory

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "local_drafts"


def generate_daily_digest(grant_lead: dict, partner_lead: dict) -> Path:
    OUTPUT_DIR.mkdir(exist_ok=True)
    today_str = datetime.now().strftime("%Y-%m-%d")
    out_file = OUTPUT_DIR / f"BSF_Outreach — {today_str}.md"

    missing_flags = grant_lead.get("missing_flags", [
        "[MISSING DATA: Audited 2025-2026 Financial Statement / Balance Sheet]",
        "[MISSING DATA: Lab Certificate of Analysis (CoA) showing Chitosan DDA % and heavy metal ppm]",
        "[MISSING DATA: Signed MoU or Letter of Intent from local Bangladesh pilot partner]"
    ])
    flags_formatted = "\n".join(f"- {flag}" for flag in missing_flags)

    content = f"""# BSF & Chitosan Daily Execution Brief — {today_str}
**Workload Cap:** Strictly 2 High-Leverage Actions Today (1 Grant + 1 UGC/Royalty Partner)

---

## TASK 1 OF 2: GRANT APPLICATION & NONPROFIT RETAINER PITCH
- **Target Organization / Funder:** {grant_lead.get('org_name', 'Bangladesh Climate & Water Innovation Fund')}
- **Cause Alignment:** {grant_lead.get('cause', 'Industrial Water Purification & Circular Bio-Waste Valorization')}
- **Portal / URL:** {grant_lead.get('url', 'https://example.org/grant-portal')}
- **Deadline:** {grant_lead.get('deadline', 'Rolling / Verify on Portal')}

### A. Strict Funder-Aligned Grant Draft
> *System Directive Applied: "You are an expert grant writer. Draft this grant application using the info and the funder's guidelines — follow their required structure exactly, and flag anything missing instead of making it up."*

1. **Executive Summary & Cause Alignment:**
   Digital Automated Consultancy proposes deploying biopolymer Chitosan extracted from Black Soldier Fly (BSF) pupal exuviae as a biodegradable, non-toxic flocculant for Bangladesh's textile and municipal water systems.
2. **Technical Methodology & Local Execution:**
   Raw high-DDA chitosan (sourced via our vetted supply chain) is formulated into an organic water-clarifying agent and validated alongside local analytical laboratories in Dhaka.
3. **Budget & Commercial Sustainability:**
   Grant capital funds local analytical validation, pilot effluent trials, and open-access efficacy documentation.
4. **MANDATORY AUDIT — FLAGGED MISSING ITEMS (DO NOT FABRICATE):**
{flags_formatted}

### B. B2B Grant-Writing Retainer Pitch (If Approaching a Nonprofit Partner)
**Subject:** Co-Application & Discounted First Grant Portfolio Offer — {grant_lead.get('org_name', 'Partner NGO')}
"Hi [Director Name], we deeply care about your work in {grant_lead.get('cause', 'water & environmental sustainability')}. To build a joint portfolio piece around BSF Chitosan water/bio-solutions, we are offering to research and draft your next major technical grant application at a heavy introductory discount. While our standard rate scales to an estimated $2,000+ per comprehensive application, our goal is to prove our value first and support 1 to 2 core nonprofit partners on repeat monthly applications to unlock consistent funding for your field programs."

---

## TASK 2 OF 2: CHEMIST / LAB DEALERSHIP & UGC ROYALTY PITCH
- **Target Partner:** {partner_lead.get('company_name', 'Dhaka Analytical & Formulation Lab')}
- **Decision Maker / Role:** {partner_lead.get('contact_role', 'Head of R&D / Chief Formulation Chemist')}
- **Product Vertical:** {partner_lead.get('vertical', 'Chitosan Water Flocculant / Cosmopharma / BSF Pet Nutrition')}
- **Channel:** {partner_lead.get('channel', 'LinkedIn + Direct Email / WhatsApp')}

### Message A: UGC R&D Collaboration + Royalty Over Distribution Rights Pitch
**Subject:** Preliminary Royalty Partnership: Co-Formulating BSF Chitosan ({partner_lead.get('vertical', 'Bio-Solutions')}) on Camera
"Assalamu Alaikum [Name],

I lead Digital Automated Consultancy in Dhaka. We have secured a dedicated supply of pharmaceutical/technical-grade Black Soldier Fly (BSF) Chitosan—where we handle and select the raw chemical supply directly—and we are launching three high-margin product lines in Bangladesh:
1. Organic Water Cleaning & Effluent Flocculants
2. Cosmopharma Antimicrobial & Wound-Care Combinations
3. High-Protein BSF + Prebiotic Chitin Pet & Aqua Nutrition

Rather than a traditional agency campaign, our marketing strategy is built entirely on **authentic lab-grade User-Generated Content (UGC)**. We want to team up with your chemists and lab facility to formulate, test, and benchmark these solutions on camera—showing real coagulation tests, viscosity checks, and formulation steps for short-form social distribution.

**The Partnership Offer (Open-Ended Preliminary Stage):**
- We supply the specialized BSF Chitosan inputs at our cost.
- Your team co-develops the local formulation and appears in short-form R&D validation clips.
- In exchange, we offer **preliminary Royalties over Distribution Rights** on every unit sold through our dealership network, plus priority dealership rights for your own distribution channels.

Are you open to a 10-minute call this week to review our raw Chitosan specifications and discuss a preliminary royalty split?"
"""
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(content)
    memory.log_task(f"Generated daily 2-task digest: {out_file.name}", agent="LAYER_3_LOCAL")
    return out_file
