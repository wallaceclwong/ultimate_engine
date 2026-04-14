"""
fix_mempalace_v4.py
Skip the interactive `init` entirely.
Just SFTP a mempalace.yaml into the target dirs and mine immediately.
"""
import paramiko, time, io

VM_IP = "45.32.255.155"
VM_USER = "root"
VM_PASS = "6{tJs[Dhe,jv3@_G"
VM_ROOT = "/root/ultimate_engine"
VENV_BIN = "/root/mempalace_venv/bin"
WING = "ultimate_engine_2026"

# Minimal mempalace.yaml needed to satisfy the `mine` command's directory check
NARR_YAML = """project_name: ultimate_engine_narratives
rooms:
  - name: general
    path: .
    include: ['*.txt']
"""

REPORTS_YAML = """project_name: ultimate_engine_reports
rooms:
  - name: reports
    path: .
    include: ['*.md', '*.txt']
"""

def run_ssh(ssh, cmd, timeout=180):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="ignore").strip()
    err = stderr.read().decode(errors="ignore").strip()
    return out, err

def sftp_write(ssh, remote_path, content):
    sftp = ssh.open_sftp()
    with sftp.file(remote_path, 'w') as f:
        f.write(content)
    sftp.close()

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(VM_IP, username=VM_USER, password=VM_PASS, timeout=10)
    print("[OK] Connected.\n")

    base_env = "export OMP_NUM_THREADS=1; export MKL_NUM_THREADS=1"

    # Step 1: Drop mempalace.yaml directly into narratives dir via SFTP
    print("=== Step 1: Deploying mempalace.yaml into narratives dir ===")
    sftp_write(ssh, f"{VM_ROOT}/data/narratives/mempalace.yaml", NARR_YAML)
    print("  narratives/mempalace.yaml written.")
    sftp_write(ssh, f"{VM_ROOT}/data/reports/mempalace.yaml", REPORTS_YAML)
    print("  reports/mempalace.yaml written.")

    # Step 2: Mine narratives with --wing
    print("\n=== Step 2: Mining narratives (60-120s) ===")
    out, err = run_ssh(ssh,
        f"cd {VM_ROOT} && {base_env}; "
        f"{VENV_BIN}/python -m mempalace.cli mine data/narratives --wing {WING}",
        timeout=180)
    lines = [l for l in out.splitlines() if l.strip()]
    for l in lines[-12:]: print(l)
    errs = [l for l in err.splitlines() if l.strip() and "Warning" not in l and "frozen" not in l and "RuntimeWarning" not in l]
    if errs: print("[ERR]", "\n".join(errs[:3]))

    # Step 3: Mine reports
    print("\n=== Step 3: Mining reports ===")
    out, _ = run_ssh(ssh,
        f"cd {VM_ROOT} && {base_env}; "
        f"{VENV_BIN}/python -m mempalace.cli mine data/reports --wing {WING}",
        timeout=90)
    lines = [l for l in out.splitlines() if l.strip()]
    for l in lines[-5:]: print(l)

    # Step 4: Palace status
    print("\n=== Step 4: Status ===")
    time.sleep(3)
    out, _ = run_ssh(ssh, f"{base_env}; {VENV_BIN}/python -m mempalace.cli status")
    clean = [l for l in out.splitlines() if l.strip() and "Warning" not in l and "telemetry" not in l.lower()]
    for l in clean: print(l)

    # Step 5: Search tests - the same 3 queries from consensus_agent
    print("\n=== Step 5: War Room Search Test ===")
    # Use real horse/jockey names from recent racecards
    out_rc, _ = run_ssh(ssh, f"cat {VM_ROOT}/data/racecard_20260408_HV_R1.json 2>/dev/null | head -20")
    print(f"Sample racecard: {out_rc[:200]}")

    queries = [
        "WIN prediction high confidence best bet",
        "jockey trainer combination race winner Hong Kong",
        "turf track race class form analysis",
    ]
    all_ok = True
    for q in queries:
        print(f"\n  Query: '{q}'")
        out, _ = run_ssh(ssh,
            f"{base_env}; {VENV_BIN}/python -m mempalace.cli search \"{q}\" --wing {WING} --results 3",
            timeout=30)
        clean = [l for l in out.splitlines() if l.strip() and "Warning" not in l and "telemetry" not in l.lower() and "frozen" not in l and "RuntimeWarning" not in l]
        if clean:
            for l in clean[:6]: print(f"    {l}")
        else:
            all_ok = False
            print("    [NO RESULTS]")

    if all_ok:
        print("\n✅ MemPalace search is working! War Room will now receive historical context.")
    else:
        print("\n⚠️  Some queries still return empty — narratives may need more content.")

    ssh.close()

if __name__ == "__main__":
    main()
