import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services.memory_service import MemoryService

m = MemoryService()

print("\n--- Current crontab ---")
out = m._execute_cmd("crontab -l")
print(out if out else "(empty)")

print("\n--- Today's automation log ---")
out = m._execute_cmd("grep '2026-05-06\\|06/05\\|today' /root/ultimate_engine/automation.log 2>/dev/null | tail -60")
if not out:
    out = m._execute_cmd("tail -80 /root/ultimate_engine/automation.log 2>/dev/null")
print(out if out else "(no log)")
