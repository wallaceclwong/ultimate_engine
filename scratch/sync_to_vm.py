import os
import sys
import paramiko
from pathlib import Path

# VM Configuration
VM_IP = "45.32.255.155"
VM_USER = "root"
VM_PASS = "6{tJs[Dhe,jv3@_G"
VM_ROOT = "/root/ultimate_engine"

# Local Paths
BASE_DIR = Path(__file__).parent.parent.absolute()
PARQUET_FILES = [
    "training_data_hybrid.parquet",
    "final_feature_matrix.parquet"
]
RESULTS_GLOB = "data/results/results_2026-04-08_HV_R*.json"

def get_ssh_client():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {VM_IP}...")
    client.connect(VM_IP, username=VM_USER, password=VM_PASS, timeout=10)
    return client

def sync():
    ssh = None
    try:
        ssh = get_ssh_client()
        sftp = ssh.open_sftp()
        
        # 1. Git Pull
        print("--- Step 1: Git Pull on VM ---")
        stdin, stdout, stderr = ssh.exec_command(f"cd {VM_ROOT} && git pull origin main")
        out = stdout.read().decode()
        err = stderr.read().decode()
        print(f"STDOUT: {out}")
        if err: print(f"STDERR: {err}")

        # 2. Check and Sync Results Files
        print("--- Step 2: Checking/Syncing Results JSON ---")
        local_results = list(BASE_DIR.glob(RESULTS_GLOB))
        for lr in local_results:
            remote_path = f"{VM_ROOT}/data/results/{lr.name}"
            # Check if exists
            try:
                sftp.stat(remote_path)
                print(f"  [OK] {lr.name} exists.")
            except FileNotFoundError:
                print(f"  [MISSING] Uploading {lr.name}...")
                sftp.put(str(lr), remote_path)

        # 3. Upload Parquet Files
        print("--- Step 3: Uploading Parquet Matrices ---")
        for pf in PARQUET_FILES:
            local_path = BASE_DIR / pf
            remote_path = f"{VM_ROOT}/{pf}"
            print(f"  Uploading {pf}...")
            # We use a temporary name and rename to ensure atomic overwrite
            temp_path = f"{remote_path}.tmp"
            sftp.put(str(local_path), temp_path)
            try:
                sftp.remove(remote_path)
            except: pass
            sftp.rename(temp_path, remote_path)

        # 4. Final Verification
        print("--- Step 4: Final Verification ---")
        stdin, stdout, stderr = ssh.exec_command(f"ls -lh {VM_ROOT}/*.parquet")
        print(stdout.read().decode())
        
        print("\n[SUCCESS] SYNC COMPLETE!")

    except Exception as e:
        print(f"[ERROR] {e}")
    finally:
        if ssh:
            ssh.close()

if __name__ == "__main__":
    sync()
