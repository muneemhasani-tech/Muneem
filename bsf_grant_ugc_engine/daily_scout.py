#!/usr/bin/env python3
"""
daily_scout.py — Layer 1 Local Runner.
Selects today's vertical, advances pagination, opens strictly 2 tabs (1 Grant + 1 Partner)
unless --dry-run is passed, and logs the execution to daily_log.json.
"""
import argparse
import webbrowser
from datetime import datetime, timezone
import memory
import scout
import campaign_phases


def run_daily_scout(dry_run: bool = False):
    memory.init_db()
    
    # Check if Phase allows raw browser scouting (Phase 1 only)
    plan = campaign_phases.evaluate_daily_execution_plan()
    if not plan["should_run_layer1_browser_scout"]:
        msg = f"[PHASE PRUNING] Day {plan['day']} is in {plan['phase_name']}. Raw browser scouting retired; focus shifted to warm follow-ups."
        print(msg)
        memory.log_task(msg, agent="LAYER_1_PRUNER")
        return {
            "status": "PRUNED_RETIRED",
            "message": msg,
            "tasks_opened": 0
        }

    slog = memory.read_json("search_log")
    dlog = memory.read_json("daily_log")

    idx = slog.get("rotation_index", (plan["day"] - 1)) % len(scout.QUERY_MATRIX)
    active_pair = scout.QUERY_MATRIX[idx]

    g_key = active_pair["grant_key"]
    p_key = active_pair["partner_key"]

    g_page = slog["queries"][g_key]["page"]
    p_page = slog["queries"][p_key]["page"]

    g_url = scout.build_google_url(active_pair["grant_query"], g_page)
    p_url = scout.build_google_url(active_pair["partner_query"], p_page)

    now_iso = datetime.now(timezone.utc).isoformat()

    if not dry_run:
        webbrowser.open_new_tab(g_url)
        webbrowser.open_new_tab(p_url)

    # Advance pagination for next cycle
    slog["queries"][g_key]["page"] = g_page + 1
    slog["queries"][g_key]["last_run"] = now_iso
    slog["queries"][p_key]["page"] = p_page + 1
    slog["queries"][p_key]["last_run"] = now_iso
    slog["rotation_index"] = (idx + 1) % len(scout.QUERY_MATRIX)
    memory.write_json("search_log", slog)

    run_record = {
        "timestamp": now_iso,
        "vertical": active_pair["vertical"],
        "dry_run": dry_run,
        "tasks_opened": 2,
        "grant_search": {"key": g_key, "page_searched": g_page, "url": g_url},
        "partner_search": {"key": p_key, "page_searched": p_page, "url": p_url},
        "status": "SUCCESS"
    }
    dlog["runs"].append(run_record)
    memory.write_json("daily_log", dlog)
    memory.log_task(f"Layer 1 executed ({active_pair['vertical']}) [dry_run={dry_run}]", agent="LAYER_1")
    return run_record


def show_history():
    dlog = memory.read_json("daily_log")
    for r in dlog.get("runs", [])[-10:]:
        print(f"[{r['timestamp']}] Vertical: {r['vertical']} | Grant Pg: {r['grant_search']['page_searched']} | Partner Pg: {r['partner_search']['page_searched']} | Status: {r['status']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Layer 1 Daily BSF Grant & Partner Scout")
    parser.add_argument("--dry-run", action="store_true", help="Run logic and pagination without opening browser tabs")
    parser.add_argument("--history", action="store_true", help="Print last 10 runs")
    args = parser.parse_args()

    if args.history:
        show_history()
    else:
        res = run_daily_scout(dry_run=args.dry_run)
        print(f"[LAYER 1 OK] Vertical: {res['vertical']} | Opened 2 targeted searches (Grant pg {res['grant_search']['page_searched']}, Partner pg {res['partner_search']['page_searched']}).")
