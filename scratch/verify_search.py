import paramiko

VM_IP = "45.32.255.155"
VM_USER = "root"
VM_PASS = "6{tJs[Dhe,jv3@_G"

def run_remote(ssh, cmd):
    stdin, stdout, stderr = ssh.exec_command(f"export OMP_NUM_THREADS=1; export MKL_NUM_THREADS=1; {cmd}")
    return stdout.read().decode(errors='ignore')

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(VM_IP, username=VM_USER, password=VM_PASS)

    print("--- Testing Search (Final Verification) ---")
    out = run_remote(ssh, "/root/mempalace_venv/bin/python -m mempalace.cli search 'SPICY SPANGLE' --wing ultimate_engine_2026")
    print(out)
    
    ssh.close()

if __name__ == "__main__":
    main()
