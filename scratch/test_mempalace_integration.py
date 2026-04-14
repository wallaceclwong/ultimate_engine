"""
test_mempalace_integration.py
Full end-to-end test of MemPalace integration from the VM.
Tests: connectivity, search quality, and the consensus_agent War Room query chain.
"""
import paramiko, sys

VM_IP = "45.32.255.155"
VM_USER = "root"
VM_PASS = "6{tJs[Dhe,jv3@_G"
VENV_BIN = "/root/mempalace_venv/bin"
WING = "ultimate_engine_2026"

def run_ssh(ssh, cmd, timeout=20):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode(errors="ignore").strip(), stderr.read().decode(errors="ignore").strip()

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(VM_IP, username=VM_USER, password=VM_PASS, timeout=10)
    print("[OK] Connected to VM.\n")

    # 1. Status check
    print("=" * 55)
    print("1. MEMPALACE STATUS")
    print("=" * 55)
    out, err = run_ssh(ssh,
        f"export OMP_NUM_THREADS=1; export MKL_NUM_THREADS=1; "
        f"{VENV_BIN}/python -m mempalace.cli status", timeout=20)
    print(out if out else "[EMPTY]")

    # 2. Real search queries (same ones the consensus_agent uses at race time)
    queries = [
        "Golden Sixty performance history",
        "Douglas Whyte and Frankie Lor combination Hong Kong ROI",
        "Sha Tin 1200m turf track bias good going",
    ]

    print("\n" + "=" * 55)
    print("2. SEARCH QUALITY TEST (3 War Room queries)")
    print("=" * 55)
    for i, q in enumerate(queries, 1):
        print(f"\n  [{i}] Query: '{q}'")
        out, err = run_ssh(ssh,
            f"export OMP_NUM_THREADS=1; export MKL_NUM_THREADS=1; "
            f"{VENV_BIN}/python -m mempalace.cli search \"{q}\" --wing {WING}",
            timeout=20)
        lines = [l.strip() for l in out.splitlines() if l.strip()][:5]
        if lines:
            for l in lines:
                print(f"      {l}")
        else:
            print("      [NO RESULTS - wing may be empty or query too specific]")
        if err:
            errs = [l for l in err.splitlines() if "Warning" not in l and "telemetry" not in l.lower()]
            if errs:
                print(f"      [WARN] {errs[0][:120]}")

    # 3. Integration route check - does consensus_agent.py import memory_service?
    print("\n" + "=" * 55)
    print("3. INTEGRATION: consensus_agent.py -> memory_service.py")
    print("=" * 55)
    out, _ = run_ssh(ssh, "grep -n 'memory_service\\|MemoryService' /root/ultimate_engine/consensus_agent.py")
    if out:
        for line in out.splitlines():
            print(f"  {line}")
        print("  [OK] consensus_agent imports memory_service correctly.")
    else:
        print("  [WARN] memory_service NOT imported in consensus_agent!")

    # 4. Check the IP the memory_service uses
    print("\n" + "=" * 55)
    print("4. MEMORY SERVICE CONFIG")
    print("=" * 55)
    out, _ = run_ssh(ssh, "grep -n 'vm_ip\\|100\\.' /root/ultimate_engine/services/memory_service.py | head -5")
    print(out)
    # The VM connects to itself — check if localhost would be better
    out2, _ = run_ssh(ssh, "hostname -I | awk '{print $1}'")
    print(f"  VM IP: {out2}")
    print(f"  Note: memory_service uses SSH tunnel — it SSHes into itself from within the scheduler.")

    ssh.close()
    print("\n" + "=" * 55)
    print("MEMPALACE INTEGRATION TEST COMPLETE")
    print("=" * 55)

if __name__ == "__main__":
    main()
