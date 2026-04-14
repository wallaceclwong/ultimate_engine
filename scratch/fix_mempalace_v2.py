"""
fix_mempalace_v2.py
Correct sequence: init narratives room → mine → test search
"""
import paramiko, time

VM_IP = "45.32.255.155"
VM_USER = "root"
VM_PASS = "6{tJs[Dhe,jv3@_G"
VM_ROOT = "/root/ultimate_engine"
VENV_BIN = "/root/mempalace_venv/bin"
WING = "ultimate_engine_2026"

def run_ssh(ssh, cmd, timeout=120):
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

    # Step 1: Verify narratives exist
    print("=== Step 1: Verifying narratives ===")
    out, _ = run_ssh(ssh, f"ls {VM_ROOT}/data/narratives/ | wc -l")
    print(f"Narrative files: {out}")
    out, _ = run_ssh(ssh, f"head -5 {VM_ROOT}/data/narratives/racecard_2026-04-08_HV_R1.txt 2>/dev/null || ls {VM_ROOT}/data/narratives/ | head -5")
    print(out)

    # Step 2: Init the narratives room (creates mempalace.yaml inside it)
    print("\n=== Step 2: Init narratives room ===")
    out, err = run_ssh(ssh,
        f"cd {VM_ROOT} && {base_env}; "
        f"{VENV_BIN}/python -m mempalace.cli init data/narratives --wing {WING}")
    print(out or "[empty]")
    if err:
        filtered = [l for l in err.splitlines() if "Warning" not in l and "telemetry" not in l.lower()]
        if filtered: print("[WARN]", "\n".join(filtered[:3]))

    # Step 3: Also init reports room
    print("\n=== Step 3: Init reports room ===")
    out, err = run_ssh(ssh,
        f"cd {VM_ROOT} && {base_env}; "
        f"{VENV_BIN}/python -m mempalace.cli init data/reports --wing {WING}")
    print(out or "[empty]")

    # Step 4: Mine narratives
    print("\n=== Step 4: Mining narratives (30-90 seconds) ===")
    out, err = run_ssh(ssh,
        f"cd {VM_ROOT} && {base_env}; "
        f"{VENV_BIN}/python -m mempalace.cli mine data/narratives --wing {WING}",
        timeout=180)
    lines = [l for l in out.splitlines() if l.strip()]
    for l in lines[-10:]:
        print(l)

    # Step 5: Mine reports
    print("\n=== Step 5: Mining reports ===")
    out, _ = run_ssh(ssh,
        f"cd {VM_ROOT} && {base_env}; "
        f"{VENV_BIN}/python -m mempalace.cli mine data/reports --wing {WING}",
        timeout=90)
    lines = [l for l in out.splitlines() if l.strip()]
    for l in lines[-5:]:
        print(l)

    # Step 6: Final status
    print("\n=== Step 6: Final Status ===")
    time.sleep(3)
    out, _ = run_ssh(ssh,
        f"{base_env}; {VENV_BIN}/python -m mempalace.cli status")
    lines = [l for l in out.splitlines() if l.strip() and "Warning" not in l and "telemetry" not in l.lower()]
    for l in lines:
        print(l)

    # Step 7: Test search
    print("\n=== Step 7: Search test ===")
    queries = [
        "horse prediction confidence WIN",
        "jockey trainer race winner",
        "turf 1200m Sha Tin form",
    ]
    for q in queries:
        print(f"\n  Query: '{q}'")
        out, _ = run_ssh(ssh,
            f"{base_env}; "
            f"{VENV_BIN}/python -m mempalace.cli search \"{q}\" --wing {WING}",
            timeout=25)
        clean = [l for l in out.splitlines() if l.strip() and "Warning" not in l and "telemetry" not in l.lower() and "frozen" not in l]
        if clean:
            for l in clean[:6]:
                print(f"    {l}")
        else:
            print("    [NO RESULTS]")

    ssh.close()
    print("\nDone.")

if __name__ == "__main__":
    main()
