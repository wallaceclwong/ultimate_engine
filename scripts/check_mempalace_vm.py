import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services.memory_service import MemoryService

m = MemoryService()
print("\n--- MemPalace process status ---")
out = m._execute_cmd("ps aux | grep -i mempalace | grep -v grep")
print(out if out else "(not running)")

print("\n--- Quick CLI test ---")
out = m._execute_cmd("/root/ultimate_engine/.venv/bin/python -m mempalace.cli status 2>&1 | head -20")
print(out if out else "(no output)")

print("\n--- mempalace installed? ---")
out = m._execute_cmd("/root/ultimate_engine/.venv/bin/pip show mempalace 2>&1")
print(out if out else "(no output)")
