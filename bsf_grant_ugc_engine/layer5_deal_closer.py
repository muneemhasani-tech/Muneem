#!/usr/bin/env python3
"""
layer5_deal_closer.py — Layer 5: Deal Structure, Legal Term Sheet & Retainer MoU Generator.
Active in Phases 3 & 4 (Days 16–30).
Converts interested leads into signed agreements:
1. Preliminary Royalty & Regional Dealership Term Sheet (for Labs/Chemists)
2. Grant-Writing-as-a-Service Retainer MoU ($2,000+/mo structure for NGOs)
"""
from datetime import datetime
from pathlib import Path
import memory

BASE_DIR = Path(__file__).resolve().parent
CONTRACT_DIR = BASE_DIR / "local_drafts" / "contracts"


def generate_lab_royalty_term_sheet(lab_name: str, chemist_name: str, vertical: str) -> Path:
    CONTRACT_DIR.mkdir(parents=True, exist_ok=True)
    today_str = datetime.now().strftime("%Y-%m-%d")
    clean_name = lab_name.replace(" ", "_").replace("/", "_")
    out_file = CONTRACT_DIR / f"TermSheet_Royalty_Dealership_{clean_name}_{today_str}.md"
    
    content = f"""# PRELIMINARY TERM SHEET: BSF CHITOSAN CO-FORMULATION & UGC ROYALTY DEALERSHIP
**Date:** {today_str}
**Parties:** 
1. **Digital Automated Consultancy (InsecTech / BSF Division)** — Dhaka, Bangladesh ("Sponsor/Supplier")
2. **{lab_name}** — Dhaka, Bangladesh (Attn: {chemist_name}) ("Research & Dealership Partner")

---

## 1. OBJECTIVE & RECITALS
The Parties agree to establish an open-ended preliminary partnership to develop, lab-validate, and commercialize innovative biopolymer products based on Black Soldier Fly (BSF) Chitosan for the **{vertical}** vertical in Bangladesh.

## 2. DIVISION OF RESPONSIBILITY
- **Sponsor/Supplier Obligations:**
  1. Supply research-grade / industrial-grade BSF Chitosan and defatted protein inputs at Sponsor's direct cost and independent global supply selection.
  2. Provide standard specification guidelines, deacetylation degree (DDA %) targets, and bulk availability.
  3. Lead national marketing, brand distribution, and dealership network placement in Bangladesh.
- **Partner / Laboratory Obligations:**
  1. Perform benchtop solubility, flocculation/viscosity, and formulation compatibility tests.
  2. Co-produce authentic, short-form User-Generated Content (UGC) video documentation showing real laboratory testing, coagulation, or topical formulation for technical distribution.
  3. Validate end-product Certificates of Analysis (CoA) for regulatory readiness.

## 3. COMMERCIAL CONSIDERATION & ROYALTY STRUCTURE
- **Zero Upfront Consulting Debt:** In lieu of traditional R&D consultancy retainers, Partner receives **Preliminary Royalties over Distribution Rights** consisting of:
  - **Ongoing Royalty:** 5.0% to 8.0% of net wholesale distribution revenue on all commercial SKUs formulated under this collaboration.
  - **Priority Regional Dealership:** Partner retains First Right of Refusal for exclusive regional distribution/dealership rights across their primary Bangladesh territory with preferential tier margins.

## 4. SIGN-OFF & PRELIMINARY ACCEPTANCE
- **For Digital Automated Consultancy:** ___________________________  Date: ____________
- **For {lab_name}:** ___________________________  Date: ____________
"""
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(content)
    memory.log_task(f"Generated Lab Royalty Term Sheet: {out_file.name}", agent="LAYER_5")
    return out_file


def generate_ngo_retainer_agreement(ngo_name: str, director_name: str, target_fund: str) -> Path:
    CONTRACT_DIR.mkdir(parents=True, exist_ok=True)
    today_str = datetime.now().strftime("%Y-%m-%d")
    clean_name = ngo_name.replace(" ", "_").replace("/", "_")
    out_file = CONTRACT_DIR / f"Retainer_Agreement_GrantWriting_{clean_name}_{today_str}.md"
    
    content = f"""# MEMORANDUM OF UNDERSTANDING: GRANT-WRITING-AS-A-SERVICE RETAINER
**Date:** {today_str}
**Parties:**
1. **Digital Automated Consultancy** — Dhaka, Bangladesh ("Technical Grant Writer")
2. **{ngo_name}** — Dhaka, Bangladesh (Attn: {director_name}) ("Implementing Nonprofit")

---

## 1. PURPOSE & ALIGNMENT
The Parties enter into this Agreement to secure competitive non-dilutive grant funding for environmental resilience, circular waste valorization, and clean water access in Bangladesh, targeting the **{target_fund}** and subsequent international calls.

## 2. SERVICES & TWO-TRACK FEE STRUCTURE
1. **Initial Portfolio Application (Introductory Discount):**
   - The first full grant application is drafted by Technical Grant Writer at a **50% introductory portfolio discount** to establish working cadence and demonstrate technical caliber.
2. **Ongoing Monthly Grant Retainer ($2,000+ Model):**
   - Upon completion of the initial application, Implementing Nonprofit engages Technical Grant Writer on a recurring retainer of **$2,000 per comprehensive proposal cycle**.
   - Scope includes active funder identification, strict compliance alignment, narrative and technical drafting, budget narrative design, and audit of required institutional metrics.
3. **Strict Compliance Guardrail:**
   - Technical Grant Writer operates under the directive: *"Draft this grant application using the info and the funder's guidelines — follow their required structure exactly, and flag anything missing instead of making it up."* All missing institutional metrics (`[MISSING DATA]`) are flagged for Nonprofit verification.

## 3. SIGN-OFF
- **For Digital Automated Consultancy:** ___________________________  Date: ____________
- **For {ngo_name}:** ___________________________  Date: ____________
"""
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(content)
    memory.log_task(f"Generated NGO Retainer MoU: {out_file.name}", agent="LAYER_5")
    return out_file


if __name__ == "__main__":
    t1 = generate_lab_royalty_term_sheet("Sample Analytical Lab Dhaka", "Dr. Farhan", "Water Cleaning Agent")
    t2 = generate_ngo_retainer_agreement("Sample NGO Foundation", "Executive Director", "UNDP Water Innovation Call")
    print(f"[LAYER 5 OK] Term sheets generated:\n  - {t1.name}\n  - {t2.name}")
