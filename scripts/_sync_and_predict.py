import subprocess
from pathlib import Path

VM_HOST = "root@100.109.76.69"
VM_PATH = "/root/ultimate_engine"

extra_files = [
    ("config/settings.py",  f"{VM_PATH}/config/settings.py"),
    ("telegram_service.py", f"{VM_PATH}/telegram_service.py"),
]

print("Syncing config/telegram to VM...")
for local, remote in extra_files:
    r = subprocess.run(
        ["scp", "-o", "ConnectTimeout=10", local, f"{VM_HOST}:{remote}"],
        capture_output=True, text=True, timeout=30
    )
    status = "OK" if r.returncode == 0 else ("FAIL: " + r.stderr.strip()[:50])
    print(f"  {local}: {status}")

print()
print("Re-running VM predictions (2026-05-03 ST)...")
cmd = (
    f"cd {VM_PATH} && export PYTHONPATH={VM_PATH} && "
    f"set -a && . {VM_PATH}/.env && set +a && "
    f"python3 scripts/vm_predict.py --date 2026-05-03 --venue ST 2>&1 | tail -40"
)
r = subprocess.run(
    ["ssh", "-o", "ConnectTimeout=15", VM_HOST, cmd],
    capture_output=True, text=True, timeout=700,
    encoding="utf-8", errors="replace"
)
out = (r.stdout or "") + (r.stderr or "")
print(out[-4000:] if out else "(no output)")
print(f"Exit: {r.returncode}")
