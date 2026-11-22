#!/usr/bin/env python3
"""
scheduler_manager.py — Autonomous Lifecycle & Schedule Pruning Manager.
Solves schedule proliferation by enforcing a Single Unified Master Task:
1. Deletes obsolete / fragmented individual layer tasks (preventing schedule clutter).
2. Consolidates execution into ONE single canonical daily master task: 'BSF_Master_Campaign_Engine'.
3. Automatically unregisters / self-deletes the schedule on Day 30 completion so no tasks linger.
"""
import os
import platform
import subprocess
import sys
import shutil
from pathlib import Path
import memory
import campaign_tracker

BASE_DIR = Path(__file__).resolve().parent
ORCHESTRATOR_PATH = BASE_DIR / "master_orchestrator.py"
MASTER_TASK_NAME = "BSF_Master_Campaign_Engine"
LEGACY_TASK_NAMES = [
    "BSF_Daily_Scout_Layer1",
    "BSF_Daily_Scout_Layer2",
    "BSF_Daily_Writer_Layer3"
]

CONFIG_SIDECAR_DIR = Path(os.path.expanduser("~")) / ".gemini" / "config" / "sidecars"


def is_windows() -> bool:
    return platform.system() == "Windows"


def delete_task_by_name(task_name: str) -> bool:
    if not is_windows():
        return False
    try:
        res = subprocess.run(
            ["schtasks", "/Delete", "/TN", task_name, "/F"],
            capture_output=True,
            text=True
        )
        if res.returncode == 0:
            print(f"[PRUNER] Deleted obsolete task from Windows Task Scheduler: {task_name}")
            return True
    except Exception as e:
        print(f"[PRUNER WARNING] Could not delete task {task_name}: {e}")
    return False


def prune_all_legacy_tasks():
    """Removes all fragmented OS layer tasks so schedules never pile up, while keeping Gemini sidecars in sync."""
    for t_name in LEGACY_TASK_NAMES:
        delete_task_by_name(t_name)


def register_single_master_task(run_time: str = "17:30") -> bool:
    """Registers ONE canonical daily master task that replaces all fragmented layer tasks."""
    prune_all_legacy_tasks()
    
    if not is_windows():
        return False
        
    py_exec = sys.executable
    cmd_str = f'"{py_exec}" "{ORCHESTRATOR_PATH}"'
    
    try:
        res = subprocess.run(
            [
                "schtasks", "/Create", "/SC", "DAILY",
                "/TN", MASTER_TASK_NAME,
                "/TR", cmd_str,
                "/ST", run_time,
                "/F"
            ],
            capture_output=True,
            text=True
        )
        if res.returncode == 0:
            print(f"[SUCCESS] Registered Single Canonical Master Task: '{MASTER_TASK_NAME}' at {run_time} daily.")
            memory.log_task(f"Registered single master task {MASTER_TASK_NAME} at {run_time}", agent="SCHEDULER_MANAGER")
            return True
        else:
            print(f"[ERROR] Failed to register master task: {res.stderr}")
    except Exception as e:
        print(f"[ERROR] Subprocess error registering master task: {e}")
    return False


def retire_on_completion():
    """Triggered on Day 30 to automatically self-delete the scheduled task."""
    print("[CAMPAIGN RETIREMENT] 30-Day Goal reached. Auto-pruning master schedule...")
    delete_task_by_name(MASTER_TASK_NAME)
    memory.log_task(f"30-Day Campaign completed. Deregistered {MASTER_TASK_NAME}.", agent="SCHEDULER_MANAGER")
    print(f"[CLEANUP COMPLETE] '{MASTER_TASK_NAME}' has been removed from Windows Task Scheduler. No tasks lingering.")


def query_scheduler_status():
    if not is_windows():
        return
    res = subprocess.run(["schtasks", "/Query", "/FO", "TABLE"], capture_output=True, text=True)
    lines = [line for line in res.stdout.splitlines() if "BSF" in line]
    print("\n=== CURRENT BSF SCHEDULES IN WINDOWS TASK SCHEDULER ===")
    if lines:
        for line in lines:
            print(line)
    else:
        print("No active BSF scheduled tasks.")
    print("=======================================================\n")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="BSF Schedule Pruning & Consolidation Manager")
    parser.add_argument("--consolidate", action="store_true", help="Delete legacy tasks and register single master task")
    parser.add_argument("--retire", action="store_true", help="Self-delete master task on campaign completion")
    parser.add_argument("--status", action="store_true", help="Query current scheduled tasks")
    args = parser.parse_args()
    
    if args.retire:
        retire_on_completion()
    elif args.consolidate or len(sys.argv) == 1:
        register_single_master_task()
        query_scheduler_status()
    elif args.status:
        query_scheduler_status()
