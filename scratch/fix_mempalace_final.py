"""
fix_mempalace_final.py
Correct approach:
- `init --yes` for non-interactive
- `mine data/narratives --wing ultimate_engine_2026` (mine DOES accept --wing)
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

    # Init narratives dir non-interactively
    print("=== Step 1: Init narratives (--yes) ===")
    out, err = run_ssh(ssh,
        f"cd {VM_ROOT} && {base_env}; "
        f"{VENV_BIN}/python -m mempalace.cli init data/narratives --yes",
        timeout=60)
    print(out or "[empty]")
    errs = [l for l in err.splitlines() if "Warning" not in l and "telemetry" not in l.lower() and "frozen" not in l and "RuntimeWarning" not in l]
    if errs: print("[ERR]", "\n".join(errs[:3]))

    # Mine narratives with --wing
    print("\n=== Step 2: Mine narratives into MemPalace (60-120s) ===")
    out, err = run_ssh(ssh,
        f"cd {VM_ROOT} && {base_env}; "
        f"{VENV_BIN}/python -m mempalace.cli mine data/narratives --wing {WING}",
        timeout=180)
    lines = [l for l in out.splitlines() if l.strip()]
    for l in lines[-10:]:
        print(l)
    errs = [l for l in err.splitlines() if "Warning" not in l and "telemetry" not in l.lower() and "frozen" not in l and "RuntimeWarning" not in l]
    if errs: print("[ERR]", "\n".join(errs[:3]))

    # Mine reports too
    print("\n=== Step 3: Mine reports ===")
    out, err = run_ssh(ssh,
        f"cd {VM_ROOT} && {base_env}; "
        f"{VENV_BIN}/python -m mempalace.cli init data/reports --yes && "
        f"{VENV_BIN}/python -m mempalace.cli mine data/reports --wing {WING}",
        timeout=120)
    lines = [l for l in out.splitlines() if l.strip()]
    for l in lines[-5:]: print(l)

    # Final status
    print("\n=== Step 4: Palace Status ===")
    time.sleep(3)
    out, _ = run_ssh(ssh, f"{base_env}; {VENV_BIN}/python -m mempalace.cli status")
    clean = [l for l in out.splitlines() if l.strip() and "Warning" not in l and "telemetry" not in l.lower()]
    for l in clean: print(l)

    # Test search
    print("\n=== Step 5: Search Test ===")
    queries = [
        "WIN prediction confidence horse",
        "jockey trainer turf race",
        "1200m Sha Tin form analysis",
    ]
    for q in queries:
        print(f"\n  '{q}':")
        out, _ = run_ssh(ssh,
            f"{base_env}; {VENV_BIN}/python -m mempalace.cli search \"{q}\" --wing {WING} --results 3",
            timeout=25)
        clean = [l for l in out.splitlines() if l.strip() and "Warning" not in l and "telemetry" not in l.lower() and "frozen" not in l and "RuntimeWarning" not in l]
        if clean:
            for l in clean[:6]: print(f"    {l}")
        else:
            print("    [NO RESULTS]")

    ssh.close()
    print("\nDone.")

if __name__ == "__main__":
    main()
