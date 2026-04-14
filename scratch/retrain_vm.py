"""
retrain_vm.py — Fixed version with proper string quoting
"""
import paramiko
import time

VM_IP = "45.32.255.155"
VM_USER = "root"
VM_PASS = "6{tJs[Dhe,jv3@_G"
VM_ROOT = "/root/ultimate_engine"
VENV = f"{VM_ROOT}/.venv/bin/python3"

def run_ssh(ssh, cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd)
    return stdout.read().decode(errors="ignore").strip()

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print("Connecting to VM...")
    ssh.connect(VM_IP, username=VM_USER, password=VM_PASS, timeout=10)
    print("[OK] Connected.")

    # Pull the latest train_model.py fix
    print("\n[1] Pulling latest train_model.py fix...")
    out = run_ssh(ssh, "cd /root/ultimate_engine && git checkout origin/main -- train_model.py && echo OK")
    print(f"  Git checkout: {out}")

    # Launch training in background
    print("\n[2] Launching retrain (background)...")
    pid_out = run_ssh(ssh, "cd /root/ultimate_engine && nohup ./.venv/bin/python3 train_model.py > /tmp/retrain.log 2>&1 & echo $!")
    pid = pid_out.strip()
    print(f"  Training PID: {pid}")

    # Monitor for up to 8 minutes
    print("\n[3] Monitoring (30s intervals)...")
    for i in range(16):
        time.sleep(30)
        status = run_ssh(ssh, f"ps -p {pid} > /dev/null 2>&1 && echo RUNNING || echo DONE")
        log = run_ssh(ssh, "tail -n 5 /tmp/retrain.log")
        elapsed = (i + 1) * 30
        print(f"\n  [{elapsed}s] {status}")
        print(f"  {log}")
        if status == "DONE":
            break

    # Final summary
    print("\n[4] Final training log:")
    print(run_ssh(ssh, "tail -n 30 /tmp/retrain.log"))
    print("\n[5] Model files:")
    print(run_ssh(ssh, f"ls -lh {VM_ROOT}/models/*.txt {VM_ROOT}/models/*.json {VM_ROOT}/models/*.cbm 2>/dev/null"))
    ssh.close()
    print("\nDone.")

if __name__ == "__main__":
    main()
