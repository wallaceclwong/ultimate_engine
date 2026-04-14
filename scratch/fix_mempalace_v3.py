"""
fix_mempalace_v3.py
Correct MemPalace workflow:
- mempalace.yaml at project root defines rooms
- `mine .` mines all rooms defined in yaml
- No --wing on init command
"""
import paramiko, time

VM_IP = "45.32.255.155"
VM_USER = "root"
VM_PASS = "6{tJs[Dhe,jv3@_G"
VM_ROOT = "/root/ultimate_engine"
VENV_BIN = "/root/mempalace_venv/bin"
WING = "ultimate_engine_2026"

def run_ssh(ssh, cmd, timeout=180):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="ignore").strip()
    err = stderr.read().decode(errors="ignore").strip()
    return out, err

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(VM_IP, username=VM_USER, password=VM_PASS, timeout=10)
    print("[OK] Connected.\n")

    base_env = "export OMP_NUM_THREADS=1; export MKL_NUM_THREADS=1"

    # Step 1: Check what init actually accepts
    print("=== Step 1: MemPalace init --help ===")
    out, _ = run_ssh(ssh, f"{VENV_BIN}/python -m mempalace.cli init --help 2>&1 | head -20", timeout=10)
    print(out)

    print("\n=== Step 2: MemPalace mine --help ===")
    out, _ = run_ssh(ssh, f"{VENV_BIN}/python -m mempalace.cli mine --help 2>&1 | head -20", timeout=10)
    print(out)

    # Step 3: Write the updated mempalace.yaml with narratives + reports rooms
    print("\n=== Step 3: Writing mempalace.yaml with narratives room ===")
    # Write to root of project
    new_yaml = """project_name: ultimate_engine
rooms:
  - name: code
    path: .
    include: ['*.py']
  - name: data
    path: data
    include: ['*.json']
  - name: general
    path: data/narratives
    include: ['*.txt']
  - name: reports
    path: data/reports
    include: ['*.md', '*.txt']
"""
    sftp = ssh.open_sftp()
    with sftp.file(f"{VM_ROOT}/mempalace.yaml", 'w') as f:
        f.write(new_yaml)
    sftp.close()
    print("mempalace.yaml updated.")

    # Step 4: Try init on just the narratives dir (no --wing)
    print("\n=== Step 4: Init narratives dir ===")
    out, err = run_ssh(ssh, f"cd {VM_ROOT} && {base_env}; {VENV_BIN}/python -m mempalace.cli init data/narratives", timeout=30)
    print(out or "[empty]")
    if err:
        errs = [l for l in err.splitlines() if "Warning" not in l and "telemetry" not in l.lower() and "frozen" not in l]
        if errs: print("[WARN]", "\n".join(errs[:3]))

    # Step 5: Mine narratives (no --wing)
    print("\n=== Step 5: Mining narratives dir (may take 60s) ===")
    out, err = run_ssh(ssh, f"cd {VM_ROOT} && {base_env}; {VENV_BIN}/python -m mempalace.cli mine data/narratives", timeout=180)
    lines = [l for l in out.splitlines() if l.strip()]
    for l in lines[-8:]:
        print(l)
    if err:
        errs = [l for l in err.splitlines() if "Warning" not in l and "telemetry" not in l.lower() and "frozen" not in l]
        if errs: print("[WARN]", "\n".join(errs[:3]))

    # Step 6: Mine reports dir
    print("\n=== Step 6: Mining reports dir ===")
    out2, _ = run_ssh(ssh, f"cd {VM_ROOT} && {base_env}; {VENV_BIN}/python -m mempalace.cli init data/reports && {VENV_BIN}/python -m mempalace.cli mine data/reports", timeout=90)
    lines2 = [l for l in out2.splitlines() if l.strip()]
    for l in lines2[-5:]:
        print(l)

    # Step 7: Status
    print("\n=== Step 7: Final Palace Status ===")
    time.sleep(3)
    out, _ = run_ssh(ssh, f"{base_env}; {VENV_BIN}/python -m mempalace.cli status")
    clean = [l for l in out.splitlines() if l.strip() and "Warning" not in l and "telemetry" not in l.lower()]
    for l in clean:
        print(l)

    # Step 8: Test search
    print("\n=== Step 8: Search test ===")
    queries = ["WIN prediction high confidence", "turf 1200m form"]
    for q in queries:
        print(f"\n  '{q}':")
        out, _ = run_ssh(ssh,
            f"{base_env}; {VENV_BIN}/python -m mempalace.cli search \"{q}\"",
            timeout=25)
        clean = [l for l in out.splitlines() if l.strip() and "Warning" not in l and "telemetry" not in l.lower() and "frozen" not in l]
        if clean:
            for l in clean[:5]: print(f"    {l}")
        else:
            print("    [NO RESULTS]")

    ssh.close()
    print("\nDone.")

if __name__ == "__main__":
    main()
