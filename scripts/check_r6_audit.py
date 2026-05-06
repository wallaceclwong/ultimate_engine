import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services.memory_service import MemoryService

m = MemoryService()

print("--- warroom_start.log from 20:55 onwards ---")
out = m._execute_cmd("grep -A 200 'FINAL VERDICT.*R6' /root/ultimate_engine/warroom_start.log | head -80")
print(out if out else "(nothing)")

print("\n--- Any R6 errors or Telegram sends ---")
out = m._execute_cmd("grep -i 'R6\\|telegram\\|audit\\|deepseek\\|error\\|exception' /root/ultimate_engine/warroom_start.log | grep -E '20:5|21:0' | head -30")
print(out if out else "(nothing)")
