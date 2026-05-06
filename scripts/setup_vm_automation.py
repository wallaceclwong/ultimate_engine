import sys
from pathlib import Path

root_dir = str(Path(__file__).resolve().parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from services.memory_service import MemoryService

def setup():
    m = MemoryService()
    
    print("\n=== Setting Up VM Automation ===")
    print("=" * 60)

    # Step 1: Git pull latest fixes
    print("\n--- Step 1: Git pull latest fixes ---")
    out = m._execute_cmd("cd /root/ultimate_engine && git fetch origin main && git reset --hard origin/main 2>&1")
    print(out if out else "(no output)")

    # Step 2: Verify key fixes are present
    print("\n--- Step 2: Verify fixes ---")
    out = m._execute_cmd("cd /root/ultimate_engine && grep -n 'sort_values.*rank' predict_today.py | head -3")
    print(f"top_pick fix: {out.strip() if out else 'NOT FOUND'}")
    out = m._execute_cmd("cd /root/ultimate_engine && grep -n 'skip empty snapshots' predict_today.py | head -3")
    print(f"load_odds fix: {out.strip() if out else 'NOT FOUND'}")

    # Step 3: Install dependencies if needed
    print("\n--- Step 3: Check dependencies ---")
    out = m._execute_cmd("/root/ultimate_engine/.venv/bin/pip install -q -r /root/ultimate_engine/requirements.txt 2>&1 | tail -5")
    print(out if out else "(done)")

    # Step 4: Set up cron jobs
    print("\n--- Step 4: Setting up cron jobs ---")

    # Read existing crontab
    existing = m._execute_cmd("crontab -l 2>/dev/null || echo ''")

    # Define cron jobs (HKT = UTC+8, so subtract 8 for UTC)
    cron_jobs = {
        "ultimate_noon_scrape":     "0 4 * * *",   # 12:00 HKT = 04:00 UTC
        "ultimate_odds_refresh":    "30 1 * * *",   # 09:30 HKT = 01:30 UTC
        "ultimate_predict":         "0 5 * * *",    # 13:00 HKT = 05:00 UTC
        "ultimate_learn":           "0 13 * * *",   # 21:00 HKT = 13:00 UTC
        "ultimate_restday":         "0 2 * * *",    # 10:00 HKT = 02:00 UTC
    }

    cron_commands = {
        "ultimate_noon_scrape":  "/root/ultimate_engine/.venv/bin/python /root/ultimate_engine/ultimate_scheduler_vm.py --noon >> /root/ultimate_engine/automation.log 2>&1",
        "ultimate_odds_refresh": "/root/ultimate_engine/.venv/bin/python /root/ultimate_engine/ultimate_scheduler_vm.py --odds >> /root/ultimate_engine/automation.log 2>&1",
        "ultimate_predict":      "/root/ultimate_engine/.venv/bin/python /root/ultimate_engine/ultimate_scheduler_vm.py --predict >> /root/ultimate_engine/automation.log 2>&1",
        "ultimate_learn":        "/root/ultimate_engine/.venv/bin/python /root/ultimate_engine/ultimate_scheduler_vm.py --learn >> /root/ultimate_engine/automation.log 2>&1",
        "ultimate_restday":      "/root/ultimate_engine/.venv/bin/python /root/ultimate_engine/ultimate_scheduler_vm.py --restday >> /root/ultimate_engine/automation.log 2>&1",
    }

    # Build new crontab (remove old ultimate_engine jobs, add fresh ones)
    lines = [l for l in existing.splitlines() if "ultimate_scheduler_vm" not in l and l.strip()]
    lines.append("")
    lines.append("# Ultimate Engine Race Day Automation")
    for name, schedule in cron_jobs.items():
        lines.append(f"# {name}")
        lines.append(f"{schedule} {cron_commands[name]}")
    
    new_crontab = "\n".join(lines) + "\n"

    # Write crontab
    write_cmd = f"echo '{new_crontab}' | crontab -"
    m._execute_cmd(write_cmd)

    print("Cron jobs installed:")
    out = m._execute_cmd("crontab -l | grep -A1 'Ultimate Engine'")
    print(out if out else "(checking...)")
    
    # Show full crontab
    print("\n--- Full crontab ---")
    out = m._execute_cmd("crontab -l")
    print(out if out else "(empty)")

    # Step 5: Verify scheduler modes exist
    print("\n--- Step 5: Verify scheduler modes ---")
    for mode in ["--noon", "--odds", "--predict", "--learn", "--restday"]:
        out = m._execute_cmd(f"grep -c '{mode}' /root/ultimate_engine/ultimate_scheduler_vm.py")
        count = out.strip() if out else "0"
        status = "✓" if int(count) > 0 else "✗"
        print(f"  {status} {mode}")

    print("\n=== VM Automation Setup Complete ===")
    print("\nSchedule (HKT):")
    print("  09:30  Morning odds scrape + prediction patch")
    print("  12:00  Noon racecard scrape")
    print("  13:00  Predictions run")
    print("  21:00  Post-race learning")
    print("  10:00  Rest day operations")

if __name__ == "__main__":
    setup()
