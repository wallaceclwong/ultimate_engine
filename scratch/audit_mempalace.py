import paramiko
import os

VM_IP = "45.32.255.155"
VM_USER = "root"
VM_PASS = "6{tJs[Dhe,jv3@_G"

def run_remote(ssh, cmd):
    print(f"Executing: {cmd}")
    stdin, stdout, stderr = ssh.exec_command(f"export OMP_NUM_THREADS=1; export MKL_NUM_THREADS=1; {cmd}")
    out = stdout.read().decode(errors='ignore')
    err = stderr.read().decode(errors='ignore')
    return out, err

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(VM_IP, username=VM_USER, password=VM_PASS)

    print("--- MemPalace Status ---")
    out, err = run_remote(ssh, "/root/mempalace_venv/bin/python -m mempalace.cli status")
    print(out)
    if err: print(f"Error: {err}")

    print("\n--- Testing Search (General) ---")
    out, err = run_remote(ssh, "/root/mempalace_venv/bin/python -m mempalace.cli search 'horse' --wing ultimate_engine_2026")
    print("Search Results for 'horse':")
    print(out if out.strip() else "[No results]")

    print("\n--- Checking for Narrative Files ---")
    out, err = run_remote(ssh, "ls -l /root/ultimate_engine/data/narratives/ | head -n 5")
    print(out)

    print("\n--- Mining Narratives Room ---")
    # We need to make sure be in the right directory or provide the full path to a palace
    out, err = run_remote(ssh, "cd /root/ultimate_engine && /root/mempalace_venv/bin/python -m mempalace.cli mine data/narratives --wing ultimate_engine_2026")
    print(out)
    if err: print(f"Error: {err}")

    print("\n--- Searching for 'SPICY SPANGLE' (from a known narrative) ---")
    out, err = run_remote(ssh, "/root/mempalace_venv/bin/python -m mempalace.cli search 'SPICY SPANGLE' --wing ultimate_engine_2026")
    print("Search Results for 'SPICY SPANGLE':")
    print(out if out.strip() else "[No results]")

    ssh.close()

if __name__ == "__main__":
    main()
