import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services.memory_service import MemoryService

m = MemoryService()

NEW_CRONTAB = """# ===== HKJC ULTIMATE ENGINE (LUNAR LEAP v3) — HKT TIMES =====
0 3 * * 1 /usr/bin/python3 /root/ultimate_engine/scripts/vm_housekeeping.py >> /root/ultimate_engine/automation.log 2>&1
0 * * * * /usr/bin/python3 /root/ultimate_engine/scripts/soft_data_watchdog.py >> /root/ultimate_engine/automation.log 2>&1
*/30 * * * * /root/ultimate_engine/.venv/bin/python /root/ultimate_engine/scripts/lunar_heartbeat.py >> /root/ultimate_engine/automation.log 2>&1
# ultimate_status — daily 9am HKT morning briefing
0 9 * * * /root/ultimate_engine/.venv/bin/python /root/ultimate_engine/ultimate_scheduler_vm.py --status >> /root/ultimate_engine/automation.log 2>&1
# ultimate_odds_refresh — 9:30am HKT
30 9 * * * /root/ultimate_engine/.venv/bin/python /root/ultimate_engine/ultimate_scheduler_vm.py --odds >> /root/ultimate_engine/automation.log 2>&1
# ultimate_noon_scrape — 12:00pm HKT
0 12 * * * /root/ultimate_engine/.venv/bin/python /root/ultimate_engine/ultimate_scheduler_vm.py --noon >> /root/ultimate_engine/automation.log 2>&1
# ultimate_predict — 1:00pm HKT
0 13 * * * /root/ultimate_engine/.venv/bin/python /root/ultimate_engine/ultimate_scheduler_vm.py --predict >> /root/ultimate_engine/automation.log 2>&1
# ultimate_live — 1:10pm HKT (war room, 5 min after predict)
10 13 * * * /root/ultimate_engine/.venv/bin/python /root/ultimate_engine/ultimate_scheduler_vm.py --live >> /root/ultimate_engine/automation.log 2>&1
# ultimate_learn — 11:30pm HKT
30 23 * * * /root/ultimate_engine/.venv/bin/python /root/ultimate_engine/ultimate_scheduler_vm.py --learn >> /root/ultimate_engine/automation.log 2>&1
# ultimate_restday — 10:00am HKT
0 10 * * * /root/ultimate_engine/.venv/bin/python /root/ultimate_engine/ultimate_scheduler_vm.py --restday >> /root/ultimate_engine/automation.log 2>&1
"""

print("--- Writing corrected HKT crontab ---")
m._execute_cmd(f"printf '%s' '{NEW_CRONTAB}' | crontab -")

print("\n--- Verifying new crontab ---")
out = m._execute_cmd("crontab -l")
print(out if out else "(empty)")
