import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services.memory_service import MemoryService

m = MemoryService()

print("--- Run predict for today ---")
m._execute_cmd(
    "nohup /root/ultimate_engine/.venv/bin/python "
    "/root/ultimate_engine/predict_today.py 2026-05-06 ST "
    "> /root/ultimate_engine/predict_now.log 2>&1 &"
)
print("Predict launched. Waiting 60s...")
time.sleep(60)

print("\n--- Predict log ---")
out = m._execute_cmd("tail -20 /root/ultimate_engine/predict_now.log 2>/dev/null")
print(out if out else "(no log)")

print("\n--- Predictions created ---")
out = m._execute_cmd("ls /root/ultimate_engine/data/predictions/ | grep 20260506")
print(out if out else "(none)")

print("\n--- Schedule now available? ---")
script = (
    "import sys\n"
    "sys.path.insert(0, '/root/ultimate_engine')\n"
    "from ultimate_scheduler_vm import get_dynamic_schedule\n"
    "print(get_dynamic_schedule())\n"
)
m._execute_cmd("cat > /tmp/sched2.py << 'EOF'\n" + script + "\nEOF")
out = m._execute_cmd("/root/ultimate_engine/.venv/bin/python /tmp/sched2.py 2>&1")
print(out if out else "(empty)")
