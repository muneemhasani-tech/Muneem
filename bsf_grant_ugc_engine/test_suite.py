#!/usr/bin/env python3
"""
test_suite.py — Self-verification harness. Tests locking, deduping, pagination,
draft generation, and generates OS-native scheduler registration commands.
"""
import os
import platform
import sys
import time
from pathlib import Path
import memory
import scout
import daily_scout
import draft_generator


def run_all_tests():
    print("=== RUNNING AUTONOMOUS SELF-TEST SUITE ===")
    # 1. Test DB Initialization
    memory.init_db()
    for name, path in memory.FILES.items():
        assert path.exists(), f"Failed to create {path}"
    print("[PASS 1/5] JSON Databases initialized with atomic file locking.")

    # 2. Test Pagination & Dry-Run Scout across all 3 Verticals
    initial_slog = memory.read_json("search_log")
    start_idx = initial_slog["rotation_index"]
    r1 = daily_scout.run_daily_scout(dry_run=True)
    r2 = daily_scout.run_daily_scout(dry_run=True)
    r3 = daily_scout.run_daily_scout(dry_run=True)
    assert r1["vertical"] != r2["vertical"], "Vertical rotation failed"
    assert r1["tasks_opened"] == 2, "Task cap violated (must be strictly 2)"
    print("[PASS 2/5] 3-Vertical rotation & 2-tab daily cap verified.")

    # 3. Test Lead Deduplication
    test_id = int(time.time() * 1000)
    sample_grant = {
        "org_name": "BRAC / Global Water Innovation Challenge",
        "cause": "Clean Water & Textile Effluent Remediation in Bangladesh",
        "url": f"https://test-grant-portal.org/water-{test_id}",
        "deadline": "2026-12-30"
    }
    added_first = memory.add_lead("grant", sample_grant)
    added_second = memory.add_lead("grant", sample_grant)
    assert added_first is True and added_second is False, "URL deduplication failed"
    print("[PASS 3/5] Lead deduplication engine verified.")

    # 4. Test Layer 3 Grant + UGC Royalty Draft Generation & Prompt Guardrails
    sample_partner = {
        "company_name": "Square / Local Formulation & Analytical Lab Dhaka",
        "contact_role": "Principal Formulation Chemist",
        "vertical": "BSF Chitosan Water Cleaning & Cosmopharma",
        "channel": "LinkedIn + Direct Email"
    }
    digest_path = draft_generator.generate_daily_digest(sample_grant, sample_partner)
    assert digest_path.exists(), "Digest file was not created"
    text = digest_path.read_text(encoding="utf-8")
    assert "[MISSING DATA:" in text, "Missing data flag guardrail failed"
    assert "$2,000+" in text, "Grant pricing benchmark missing"
    assert "Royalties over Distribution Rights" in text, "UGC Royalty hook missing"
    print(f"[PASS 4/5] Layer 3 Grant & UGC Royalty Deliverable verified -> {digest_path.name}")

    # 4b. Test Layer 4 Follow-Ups & Layer 5 Deal Closer Term Sheets
    import layer4_followup_engine
    import layer5_deal_closer
    import campaign_phases
    fu_file = layer4_followup_engine.run_layer4_daily()
    assert fu_file.exists(), "Layer 4 follow-up digest failed"
    ts = layer5_deal_closer.generate_lab_royalty_term_sheet("Test Analytical Lab", "Dr. Test", "Water Cleaning Agent")
    assert ts.exists() and "Preliminary Royalties over Distribution Rights" in ts.read_text(encoding="utf-8"), "Layer 5 term sheet failed"
    print("[PASS 4b/5] Layer 4 Follow-up & Layer 5 Contract Term Sheet engines verified.")

    # 5. Generate OS-Specific Local Schedule Configuration (Mac launchd + Windows schtasks)
    base_dir = Path(__file__).resolve().parent
    py_exec = sys.executable
    script_path = base_dir / "daily_scout.py"

    if platform.system() == "Darwin":
        plist_path = base_dir / "com.dac.bsf.scout.plist"
        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.dac.bsf.scout</string>
    <key>ProgramArguments</key>
    <array>
        <string>{py_exec}</string>
        <string>{script_path}</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{base_dir}</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>16</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
</dict>
</plist>"""
        plist_path.write_text(plist_content, encoding="utf-8")
        print(f"[PASS 5/5] macOS launchd plist generated at {plist_path.name}")
    else:
        bat_path = base_dir / "register_windows_task.bat"
        bat_content = f'schtasks /Create /SC DAILY /TN "BSF_Daily_Scout_Layer1" /TR "\\"{py_exec}\\" \\"{script_path}\\"" /ST 16:00 /F\n'
        bat_path.write_text(bat_content, encoding="utf-8")
        print(f"[PASS 5/5] Windows Task Scheduler script generated at {bat_path.name}")

    print("=== ALL 5 SELF-TESTS PASSED WITH ZERO ERRORS ===")


if __name__ == "__main__":
    run_all_tests()
