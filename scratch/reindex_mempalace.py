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

    # 1. Clear old wing (DANGEROUS but necessary for stability)
    # We do this by deleting the chroma collection dir if it exists
    print("--- 1. Wiping old MemPalace Chroma DB ---")
    run_remote(ssh, "rm -rf /root/.mempalace/palace/chroma.sqlite3")
    
    # 2. Deploy updated files
    print("\n--- 2. Deploying updated files ---")
    sftp = ssh.open_sftp()
    sftp.put("c:/Users/ASUS/ultimate_engine/services/memory_service.py", "/root/ultimate_engine/services/memory_service.py")
    sftp.put("c:/Users/ASUS/ultimate_engine/scripts/mempalace_narrator.py", "/root/ultimate_engine/scripts/mempalace_narrator.py")
    sftp.close()

    # 3. Generate fresh narratives on VM
    print("\n--- 3. Generating fresh narratives on VM ---")
    out, err = run_remote(ssh, "cd /root/ultimate_engine && /usr/bin/python3 scripts/mempalace_narrator.py")
    print(out)

    # 4. Initialize and Mine ONLY the narrative room
    print("\n--- 4. Initializing and Mining Narratives ---")
    # First, we need to create a mempalace.yaml that focuses only on narratives to save RAM
    yaml_content = """project_name: ultimate_engine
rooms:
  - name: narrative_room
    path: data/narratives
    include: ['*.txt']
"""
    run_remote(ssh, f"echo '{yaml_content}' > /root/ultimate_engine/mempalace.yaml")
    
    # Run the mine (direct CLI to avoid SSH-to-self overhead during heavy indexing)
    print("Starting mine operation (may take 2-3 mins)...")
    out, err = run_remote(ssh, "cd /root/ultimate_engine && /root/mempalace_venv/bin/python -m mempalace.cli mine data/narratives --wing ultimate_engine_2026")
    print(out)
    if err: print(f"Error: {err}")

    # 5. Final status check
    print("\n--- 5. Final Status Check ---")
    out, err = run_remote(ssh, "/root/mempalace_venv/bin/python -m mempalace.cli status")
    print(out)

    ssh.close()

if __name__ == "__main__":
    main()
