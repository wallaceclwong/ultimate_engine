"""
Check what's actually stored in MemPalace drawers
to understand why search returns no results.
"""
import paramiko

VM_IP = "45.32.255.155"
VM_USER = "root"
VM_PASS = "6{tJs[Dhe,jv3@_G"

def run_ssh(ssh, cmd, timeout=20):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode(errors="ignore").strip()

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(VM_IP, username=VM_USER, password=VM_PASS, timeout=10)
    print("[OK] Connected.\n")

    # Check where mempalace stores its data on disk
    print("=== MemPalace Data Location ===")
    out = run_ssh(ssh, "find /root -name 'mempalace.yaml' -o -name '*.palace' 2>/dev/null | head -5")
    print(out or "[NOT FOUND]")

    print("\n=== MemPalace Config ===")
    out = run_ssh(ssh, "cat /root/ultimate_engine/mempalace.yaml 2>/dev/null || cat /root/mempalace.yaml 2>/dev/null || echo 'No config found'")
    print(out)

    print("\n=== MemPalace DB Files ===")
    out = run_ssh(ssh, "find /root -name '*.db' -o -name '*.chroma' -o -name '*.lance' 2>/dev/null | head -10")
    print(out or "[NO DB FILES FOUND]")

    # Try a raw search with a simpler query to see if any results come back
    print("\n=== Raw Search: 'race' ===")
    out = run_ssh(ssh,
        "export OMP_NUM_THREADS=1; export MKL_NUM_THREADS=1; "
        "/root/mempalace_venv/bin/python -m mempalace.cli search 'race' --wing ultimate_engine_2026",
        timeout=20)
    print(out[:800] if out else "[EMPTY]")

    # Check the actual drawer content
    print("\n=== Sample Drawer Content ===")
    out = run_ssh(ssh, "find /root -name '*.json' -path '*/ultimate_engine_2026/*' | head -3")
    print(out or "[NO JSON FILES IN PALACE]")

    # Also check if the search CLI has a different output format
    print("\n=== MemPalace CLI help ===")
    out = run_ssh(ssh,
        "/root/mempalace_venv/bin/python -m mempalace.cli search --help 2>&1 | head -20", timeout=10)
    print(out)

    ssh.close()

if __name__ == "__main__":
    main()
