import paramiko
import sys
from pathlib import Path

VM_IP = "45.32.255.155"
VM_USER = "root"
VM_PASS = "6{tJs[Dhe,jv3@_G"
VM_ROOT = "/root/ultimate_engine"
VENV = f"{VM_ROOT}/.venv/bin/python3"

def run(ssh, label, cmd, timeout=30):
    print(f"\n{'='*55}")
    print(f"  {label}")
    print(f"{'='*55}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors='ignore').strip()
    err = stderr.read().decode(errors='ignore').strip()
    if out: print(out)
    if err: print(f"[STDERR] {err}")
    return out

def dry_run():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print("Connecting to VM at 45.32.255.155...")
    ssh.connect(VM_IP, username=VM_USER, password=VM_PASS, timeout=10)
    print("[OK] Connected.\n")

    # 1. Git status
    run(ssh, "1. CODE: Git Status & Latest Commit",
        f"cd {VM_ROOT} && git log --oneline -3 && echo '---' && git status --short")

    # 2. Environment
    run(ssh, "2. ISOLATION: Environment Variables",
        f"cat {VM_ROOT}/.env")

    # 3. Service Account Key
    run(ssh, "3. CREDENTIALS: Service Account Key",
        f"python3 -c \"import json; d=json.load(open('{VM_ROOT}/config/ultimate-engine-sa-key.json')); print(f\\\"Project: {{d['project_id']}}\\\\nClient: {{d['client_email']}}\\\")\"")

    # 4. Intelligence files
    run(ssh, "4. INTELLIGENCE: Matrix Files",
        f"ls -lh {VM_ROOT}/*.parquet")

    # 5. Scheduler check (fixture + state)
    run(ssh, "5. SCHEDULER: Health Check & State",
        f"cd {VM_ROOT} && {VENV} ultimate_scheduler_vm.py --check && echo '---STATE---' && cat data/scheduler_state.json")

    # 6. MemPalace connectivity
    run(ssh, "6. MEMPALACE: Connectivity & Wing Status",
        f"export OMP_NUM_THREADS=1; export MKL_NUM_THREADS=1; /root/mempalace_venv/bin/python3 -m mempalace.cli status",
        timeout=20)

    # 7. MemPalace search test
    run(ssh, "7. MEMPALACE: Semantic Search Test Query",
        f"export OMP_NUM_THREADS=1; export MKL_NUM_THREADS=1; /root/mempalace_venv/bin/python3 -m mempalace.cli search 'Sha Tin 1200m turf fast track' --wing ultimate_engine_2026 --limit 2",
        timeout=20)

    # 8. Heartbeat log
    run(ssh, "8. RESILIENCE: Last Heartbeat & Watchdog Logs",
        f"tail -n 15 {VM_ROOT}/automation.log")

    # 9. System vitals
    run(ssh, "9. SYSTEM: VM Vitals (Disk, RAM, CPU)",
        "df -h / && echo '---' && free -h && echo '---' && uptime")

    print(f"\n{'='*55}")
    print("  DRY RUN COMPLETE")
    print(f"{'='*55}\n")
    ssh.close()

if __name__ == "__main__":
    dry_run()
