#!/usr/bin/env python3
"""
layer4_followup_engine.py — Layer 4: Follow-Up & Response Engine.
Active in Phases 2–4 (Days 8–30).
Replaces cold exploratory searches with high-leverage follow-ups and inbound response handling.
Prevents early prospecting tasks from accumulating when attention must shift to active leads.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
import memory
import campaign_tracker

BASE_DIR = Path(__file__).resolve().parent
FOLLOWUP_LOG = BASE_DIR / "followup_log.json"

DEFAULT_FOLLOWUP_LOG = {
    "pending_followups": [],
    "active_dialogues": [],
    "completed_followups": []
}


def init_followup_log():
    if not FOLLOWUP_LOG.exists():
        with open(FOLLOWUP_LOG, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_FOLLOWUP_LOG, f, indent=2, ensure_ascii=False)


def generate_followup_templates(target_name: str, target_type: str, vertical: str, cadence: str) -> dict:
    if target_type == "lab":
        if cadence == "day_3_bump":
            subject = f"Re: Preliminary Royalty & BSF Chitosan Co-Formulation — {target_name}"
            body = f"""Assalamu Alaikum,

Following up on my message regarding co-formulating pure BSF Chitosan for {vertical} on camera. 

We are finalizing our Q1 laboratory collaboration partners in Dhaka this week to allocate raw biopolymer batches for local testing. We provide the chemical inputs at our cost and share preliminary Royalties over Distribution Rights on every formulated unit sold.

Would you be open to a brief 10-minute introductory call this Wednesday or Thursday to review the raw material Certificate of Analysis (CoA)?"""
        else:  # day_7_final
            subject = f"Final Note: Regional Dealership Priority & Lab UGC Partnership — {target_name}"
            body = f"""Assalamu Alaikum,

I wanted to send a final note regarding the BSF Chitosan {vertical} formulation initiative before we lock in regional dealership agreements. 

If your R&D facility has bandwidth to validate and test the bio-flocculant / topical hydrogel on camera for short-form technical UGC distribution, we would be delighted to prioritize your facility for preliminary distribution royalties. 

If this timing doesn't align with your current research calendar, no problem at all—feel free to reach back out whenever capacity opens up."""
    else:  # NGO / Grant target
        if cadence == "day_3_bump":
            subject = f"Re: Co-Application & Discounted First Grant Proposal — {target_name}"
            body = f"""Hi [Director Name],

Following up on our offer to draft your upcoming technical grant application for sustainable water / bio-economy initiatives. 

As shared, we are offering our first comprehensive application draft at a heavy introductory discount to build a joint portfolio piece before transitioning to our standard $2,000+ retainer model for repeat funders. 

Would you have 10 minutes this week to align on your highest-priority upcoming grant deadlines?"""
        else:  # day_7_final
            subject = f"Grant Window Check: Technical Bio-Economy Co-Application — {target_name}"
            body = f"""Hi [Director Name],

Reaching out before our Q1 grant co-application roster closes. We are committing dedicated technical writing and research bandwidth to 1–2 select nonprofit partners operating in Bangladesh to secure circular bio-economy and water innovation funding.

If you have an active call for proposals under review, we remain ready to draft the technical proposal under our introductory portfolio discount."""

    return {"subject": subject, "body": body}


def run_layer4_daily():
    init_followup_log()
    prog = campaign_tracker.get_progress()
    day = prog.get("current_day", 1)
    
    # Analyze recent outreach history (from 3 and 7 days ago)
    history = prog.get("history", [])
    
    due_followups = []
    for h in history:
        diff_days = day - h["day"]
        if diff_days == 3:
            due_followups.append({"lead": h, "cadence": "day_3_bump"})
        elif diff_days == 7:
            due_followups.append({"lead": h, "cadence": "day_7_final"})
            
    # Output top 1 Grant follow-up and top 1 Lab follow-up (respecting 2-task cap)
    selected_lab_fu = next((fu for fu in due_followups if fu["lead"].get("partner_target")), None)
    selected_grant_fu = next((fu for fu in due_followups if fu["lead"].get("grant_target")), None)
    
    out_dir = BASE_DIR / "local_drafts" / "followups"
    out_dir.mkdir(parents=True, exist_ok=True)
    today_str = datetime.now().strftime("%Y-%m-%d")
    out_file = out_dir / f"BSF_Followups_Day_{day}_{today_str}.md"
    
    content = f"""# BSF Campaign Follow-Up Digest — Day {day} ({today_str})
**Phase Context:** Layer 4 Warm Pipeline Follow-Up (Replacing Cold Prospecting Tasks)
**Owner Workload Limit:** Strictly 2 Quick Follow-Up Actions

---
"""
    if selected_grant_fu:
        g_lead = selected_grant_fu["lead"]
        tpl = generate_followup_templates(g_lead["grant_target"], "grant", g_lead["vertical"], selected_grant_fu["cadence"])
        content += f"""## TASK 1 OF 2: GRANT / NGO FOLLOW-UP ({selected_grant_fu['cadence'].replace('_', ' ').upper()})
- **Organization:** {g_lead['grant_target']}
- **Original Pitch Day:** Day {g_lead['day']}
- **Subject:** {tpl['subject']}

```text
{tpl['body']}
```

---
"""
    else:
        content += """## TASK 1 OF 2: GRANT PIPELINE STATUS
*No grant follow-ups due today. Bandwidth allocated to active proposal review.*

---
"""

    if selected_lab_fu:
        p_lead = selected_lab_fu["lead"]
        tpl = generate_followup_templates(p_lead["partner_target"], "lab", p_lead["vertical"], selected_lab_fu["cadence"])
        content += f"""## TASK 2 OF 2: CHEMIST / LAB DEALERSHIP FOLLOW-UP ({selected_lab_fu['cadence'].replace('_', ' ').upper()})
- **Target Lab:** {p_lead['partner_target']}
- **Original Outreach Day:** Day {p_lead['day']}
- **Subject:** {tpl['subject']}

```text
{tpl['body']}
```
"""
    else:
        content += """## TASK 2 OF 2: LAB DEALERSHIP PIPELINE STATUS
*No lab follow-ups due today. Bandwidth allocated to active partnership term sheets.*
"""

    with open(out_file, "w", encoding="utf-8") as f:
        f.write(content)
        
    memory.log_task(f"Layer 4 Follow-Up Digest generated for Day {day}: {out_file.name}", agent="LAYER_4")
    print(f"[LAYER 4 OK] Follow-Up digest created -> {out_file.name}")
    return out_file


if __name__ == "__main__":
    run_layer4_daily()
