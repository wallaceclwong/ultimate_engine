import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services.memory_service import MemoryService

m = MemoryService()

print("\n--- Adding --status cron to VM ---")
existing = m._execute_cmd("crontab -l 2>/dev/null || echo ''")

if "ultimate_status" in existing:
    print("Status cron already exists.")
else:
    lines = [l for l in existing.splitlines() if l.strip()]
    lines.append("# ultimate_status — daily 9am HKT morning briefing")
    lines.append("0 1 * * * /root/ultimate_engine/.venv/bin/python /root/ultimate_engine/ultimate_scheduler_vm.py --status >> /root/ultimate_engine/automation.log 2>&1")
    new_crontab = "\n".join(lines) + "\n"
    m._execute_cmd(f"printf '%s\n' '{new_crontab}' | crontab -")
    print("Done. Verifying...")

out = m._execute_cmd("crontab -l | grep -E 'status|Schedule'")
print(out if out else "(no match)")
