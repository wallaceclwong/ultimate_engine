import sys
from pathlib import Path

root_dir = str(Path(__file__).resolve().parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from services.memory_service import MemoryService

def verify():
    m = MemoryService()
    print("\n=== VM Setup Verification ===\n")

    checks = [
        ("Git version", "cd /root/ultimate_engine && git log --oneline -1"),
        ("predict_today fix 1", "grep -c 'sort_values.*rank' /root/ultimate_engine/predict_today.py"),
        ("predict_today fix 2", "grep -c 'skip empty snapshots' /root/ultimate_engine/predict_today.py"),
        ("Playwright version", "/root/ultimate_engine/.venv/bin/python -m playwright --version 2>&1"),
        ("Cron jobs count", "crontab -l | grep ultimate_scheduler_vm | wc -l"),
        ("Scheduler --noon", "grep -c 'elif mode.*noon' /root/ultimate_engine/ultimate_scheduler_vm.py"),
        ("Scheduler --odds", "grep -c 'elif mode.*odds' /root/ultimate_engine/ultimate_scheduler_vm.py"),
        ("Scheduler --predict", "grep -c 'elif mode.*predict' /root/ultimate_engine/ultimate_scheduler_vm.py"),
        ("Scheduler --learn", "grep -c 'elif mode.*learn' /root/ultimate_engine/ultimate_scheduler_vm.py"),
        ("Disk free", "df -h / | tail -1 | awk '{print $4\" free (\"$5\" used)\"}'"),
        ("RAM free", "free -h | grep Mem | awk '{print $7\" available\"}'"),
    ]

    all_ok = True
    for label, cmd in checks:
        out = m._execute_cmd(cmd).strip()
        ok = out and out != "0" and "error" not in out.lower() and "not found" not in out.lower()
        status = "✓" if ok else "✗"
        if not ok:
            all_ok = False
        print(f"  {status} {label}: {out if out else 'NO OUTPUT'}")

    print(f"\n{'✅ All checks passed' if all_ok else '⚠️  Some checks need attention'}")

if __name__ == "__main__":
    verify()
