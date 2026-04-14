"""
deploy_and_retrain.py - Directly SFTP train_model.py to VM and launch retrain
"""
import paramiko
import time
from pathlib import Path

VM_IP = "45.32.255.155"
VM_USER = "root"
VM_PASS = "6{tJs[Dhe,jv3@_G"
VM_ROOT = "/root/ultimate_engine"
LOCAL_TRAIN = str(Path(__file__).parent.parent / "train_model.py")

def run_ssh(ssh, cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd)
    return stdout.read().decode(errors="ignore").strip()

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(VM_IP, username=VM_USER, password=VM_PASS, timeout=10)
    print("[OK] Connected.\n")

    # 1. SFTP the fixed train_model.py directly
    print("[1] Uploading fixed train_model.py via SFTP...")
    sftp = ssh.open_sftp()
    sftp.put(LOCAL_TRAIN, f"{VM_ROOT}/train_model.py")
    sftp.close()
    print("    Upload complete.")

    # 2. Verify the fix is there
    print("[2] Verifying fix...")
    check = run_ssh(ssh, f"grep -n 'race_id.*astype' {VM_ROOT}/train_model.py")
    if check:
        print(f"    Fix confirmed: {check}")
    else:
        print("    ERROR: Fix not found!")
        ssh.close()
        return

    # 3. Clear pycache to prevent stale bytecode
    run_ssh(ssh, f"find {VM_ROOT} -name '*.pyc' -delete 2>/dev/null; true")
    print("[3] Cleared Python bytecode cache.")

    # 4. Launch retrain
    print("[4] Launching retrain in background...")
    pid_out = run_ssh(ssh, f"cd {VM_ROOT} && nohup ./.venv/bin/python3 train_model.py > /tmp/retrain.log 2>&1 & echo $!")
    pid = pid_out.strip()
    print(f"    Training PID: {pid}")

    # 5. Monitor
    print("\n[5] Monitoring progress (30s intervals)...")
    for i in range(20):
        time.sleep(30)
        status = run_ssh(ssh, f"ps -p {pid} > /dev/null 2>&1 && echo RUNNING || echo DONE")
        log = run_ssh(ssh, "tail -n 6 /tmp/retrain.log")
        elapsed = (i + 1) * 30
        print(f"\n  [{elapsed}s] {status}")
        print(f"  {log}")
        if status == "DONE":
            break

    # 6. Final results
    print("\n[6] Final training log:")
    print(run_ssh(ssh, "tail -n 25 /tmp/retrain.log"))
    print("\n[7] New model file timestamps:")
    print(run_ssh(ssh, f"ls -lh {VM_ROOT}/models/*.txt {VM_ROOT}/models/*.json {VM_ROOT}/models/*.cbm 2>/dev/null"))
    ssh.close()
    print("\nDone.")

if __name__ == "__main__":
    main()
