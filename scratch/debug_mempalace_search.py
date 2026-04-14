"""
debug_mempalace_search.py
Deep diagnostic on why search returns nothing despite 10,000 drawers.
"""
import paramiko

VM_IP = "45.32.255.155"
VM_USER = "root"
VM_PASS = "6{tJs[Dhe,jv3@_G"
VM_ROOT = "/root/ultimate_engine"
VENV_BIN = "/root/mempalace_venv/bin"
WING = "ultimate_engine_2026"

def run_ssh(ssh, cmd, timeout=30):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="ignore")
    err = stderr.read().decode(errors="ignore")
    return out, err

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(VM_IP, username=VM_USER, password=VM_PASS, timeout=10)
    print("[OK] Connected.\n")

    base_env = "export OMP_NUM_THREADS=1; export MKL_NUM_THREADS=1"

    # 1. Try search WITHOUT --wing (no wing filter)
    print("=== 1. Search WITHOUT --wing ===")
    out, err = run_ssh(ssh,
        f"{base_env}; {VENV_BIN}/python -m mempalace.cli search \"race\"",
        timeout=25)
    print("STDOUT:", out[:800] or "[EMPTY]")
    filtered_err = [l for l in err.splitlines() if "Warning" not in l and "telemetry" not in l.lower() and "frozen" not in l and "RuntimeWarning" not in l and "capture" not in l]
    if filtered_err:
        print("ERR:", "\n".join(filtered_err[:5]))

    # 2. Try with --results 1
    print("\n=== 2. Search with --results 1 ===")
    out, _ = run_ssh(ssh,
        f"{base_env}; {VENV_BIN}/python -m mempalace.cli search \"race winner\" --results 1",
        timeout=25)
    print("STDOUT:", out[:500] or "[EMPTY]")

    # 3. Check if mempalace has a Python API we can call directly
    print("\n=== 3. Direct Python API search ===")
    py_script = (
        "import sys; sys.path.insert(0, '/root/mempalace_venv/lib/python3.12/site-packages'); "
        "import mempalace; "
        "print(dir(mempalace)); "
    )
    out, err = run_ssh(ssh, f"{base_env}; {VENV_BIN}/python -c \"{py_script}\"", timeout=15)
    print("STDOUT:", out[:400] or "[EMPTY]")

    # 4. Inspect mempalace package structure
    print("\n=== 4. MemPalace package structure ===")
    out, _ = run_ssh(ssh, f"ls {VENV_BIN}/../lib/python3.12/site-packages/mempalace/ 2>/dev/null | head -20")
    print(out or "[NOT FOUND]")

    # 5. Look at what the search command actually does
    print("\n=== 5. MemPalace CLI search source ===")
    out, _ = run_ssh(ssh, f"grep -n 'def search\\|Results for\\|print' {VENV_BIN}/../lib/python3.12/site-packages/mempalace/cli.py 2>/dev/null | head -20")
    print(out or "[NOT FOUND]")

    # 6. Where is the vector DB stored?
    print("\n=== 6. Vector DB location ===")
    out, _ = run_ssh(ssh, "find /root /home -name 'chroma.sqlite3' -o -name '*.faiss' -o -name 'index.annoy' 2>/dev/null | head -5")
    print(out or "[NO VECTOR DB FILES]")
    out2, _ = run_ssh(ssh, "find /root /home -name '*.palace' 2>/dev/null | head -5")
    print(out2 or "[NO .palace FILES]")
    out3, _ = run_ssh(ssh, "find /root -type d -name 'ultimate_engine_2026' 2>/dev/null")
    print(out3 or "[NO WING DIR]")

    ssh.close()

if __name__ == "__main__":
    main()
