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
SA_KEY = "config/ultimate-engine-sa-key.json"
ENV_VARS = [
    "GCP_PROJECT_ID=ultimate-engine-2026",
    "GCP_REGION=asia-east1",
    "FIRESTORE_DATABASE=(default)",
    "GCS_BUCKET_NAME=ultimate-engine-2026-vault",
    "GOOGLE_APPLICATION_CREDENTIALS=config/ultimate-engine-sa-key.json"
]

def get_ssh_client():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {VM_IP}...")
    client.connect(VM_IP, username=VM_USER, password=VM_PASS, timeout=10)
    return client

def sync_vm_isolation():
    ssh = None
    try:
        ssh = get_ssh_client()
        sftp = ssh.open_sftp()
        
        # 1. Upload Service Account Key
        print("--- Step 1: Uploading Service Account Key ---")
        local_key = BASE_DIR / SA_KEY
        remote_key = f"{VM_ROOT}/{SA_KEY}"
        # Ensure config dir exists
        ssh.exec_command(f"mkdir -p {VM_ROOT}/config")
        print(f"  Uploading {SA_KEY}...")
        sftp.put(str(local_key), remote_key)

        # 2. Git Pull (Get sanitized scripts)
        print("--- Step 2: Git Pull on VM ---")
        stdin, stdout, stderr = ssh.exec_command(f"cd {VM_ROOT} && git pull origin main")
        print(f"  STDOUT: {stdout.read().decode()}")
        print(f"  STDERR: {stderr.read().decode()}")

        # 3. Update .env
        print("--- Step 3: Updating VM .env ---")
        remote_env = f"{VM_ROOT}/.env"
        # Read current .env
        stdin, stdout, stderr = ssh.exec_command(f"cat {remote_env}")
        current_content = stdout.read().decode()
        
        # Append missing vars
        lines = current_content.splitlines()
        existing_keys = [line.split("=")[0] for line in lines if "=" in line]
        
        added_count = 0
        for env_var in ENV_VARS:
            key = env_var.split("=")[0]
            if key not in existing_keys:
                print(f"  Adding {env_var}...")
                lines.append(env_var)
                added_count += 1
        
        if added_count > 0:
            new_content = "\n".join(lines) + "\n"
            with sftp.file(remote_env, 'w') as f:
                f.write(new_content)
            print(f"  Successfully updated .env with {added_count} new variables.")
        else:
            print("  .env already has all critical isolation variables.")

        # 4. Verification
        print("--- Step 4: Final VM Health Check ---")
        # Run check mode on VM
        cmd = f"cd {VM_ROOT} && ./.venv/bin/python3 ultimate_scheduler_vm.py --check"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        print(stdout.read().decode())
        
        print("\n✅ VM ISOLATION SYNC COMPLETE!")

    except Exception as e:
        print(f"❌ ERROR: {e}")
    finally:
        if ssh:
            ssh.close()

if __name__ == "__main__":
    sync_vm_isolation()
