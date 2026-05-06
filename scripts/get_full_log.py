import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services.memory_service import MemoryService

m = MemoryService()

print("\n--- Full log from May 6 onwards ---")
out = m._execute_cmd("grep -A2 '2026-05-06' /root/ultimate_engine/automation.log | tail -100")
print(out if out else "(no output)")

print("\n--- Any errors today ---")
out = m._execute_cmd("grep -i 'error\\|traceback\\|failed\\|exception' /root/ultimate_engine/automation.log | grep '2026-05-06' | tail -30")
print(out if out else "(no errors found)")

print("\n--- Log file size and last modified ---")
out = m._execute_cmd("ls -lh /root/ultimate_engine/automation.log && wc -l /root/ultimate_engine/automation.log")
print(out if out else "(no output)")
