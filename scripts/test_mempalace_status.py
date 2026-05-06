import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services.memory_service import MemoryService

m = MemoryService()

print("\n--- Raw get_status() output ---")
status = m._execute_cmd("/root/mempalace_venv/bin/python -m mempalace.cli status 2>&1")
print(repr(status))

print("\n--- List wings ---")
out = m._execute_cmd("/root/mempalace_venv/bin/python -m mempalace.cli list-wings 2>&1")
print(out if out else "(no output)")

print("\n--- mempalace.cli --help ---")
out = m._execute_cmd("/root/mempalace_venv/bin/python -m mempalace.cli --help 2>&1 | head -20")
print(out if out else "(no output)")
