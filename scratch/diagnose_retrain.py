"""
diagnose_retrain.py - Check why race_id fix isn't working on VM
"""
import paramiko

VM_IP = "45.32.255.155"
VM_USER = "root"
VM_PASS = "6{tJs[Dhe,jv3@_G"

def run_ssh(ssh, cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd)
    return stdout.read().decode(errors="ignore").strip(), stderr.read().decode(errors="ignore").strip()

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(VM_IP, username=VM_USER, password=VM_PASS, timeout=10)
    print("[OK] Connected.\n")

    # 1. Check the actual file on VM
    print("=== VM train_model.py race_id lines ===")
    out, _ = run_ssh(ssh, "grep -n 'race_id' /root/ultimate_engine/train_model.py | head -10")
    print(out)

    # 2. Check the dtype in training_data_hybrid.parquet
    script = (
        "import pandas as pd\n"
        "df = pd.read_parquet('/root/ultimate_engine/training_data_hybrid.parquet')\n"
        "print('race_id dtype:', df['race_id'].dtype)\n"
        "print('sample:', df['race_id'].iloc[0], type(df['race_id'].iloc[0]))\n"
        "print('mixed?', df['race_id'].apply(type).nunique() > 1)\n"
    )
    # Write script to /tmp and run it
    sftp = ssh.open_sftp()
    with sftp.file('/tmp/check_dtype.py', 'w') as f:
        f.write(script)
    sftp.close()

    print("\n=== race_id dtype in training parquet ===")
    out, err = run_ssh(ssh, "/root/ultimate_engine/.venv/bin/python3 /tmp/check_dtype.py")
    print(out)
    if err: print("[ERR]", err[:300])

    # 3. Check where the error actually originates in train_model.py
    script2 = (
        "import pandas as pd\n"
        "df = pd.read_parquet('/root/ultimate_engine/training_data_hybrid.parquet')\n"
        "df['date'] = pd.to_datetime(df['date'])\n"
        "df['race_id'] = df['race_id'].astype(str)\n"
        "print('After cast:', df['race_id'].dtype)\n"
        "df.to_parquet('/tmp/test_write.parquet', index=False)\n"
        "print('Write: OK')\n"
    )
    with open('/tmp/test_cast.py', 'w') as f:
        f.write(script2)

    sftp = ssh.open_sftp()
    sftp.put('/tmp/test_cast.py', '/tmp/test_cast.py')
    sftp.close()

    print("\n=== Testing fixed cast pipeline ===")
    out, err = run_ssh(ssh, "/root/ultimate_engine/.venv/bin/python3 /tmp/test_cast.py")
    print(out)
    if err: print("[ERR]", err[:300])

    ssh.close()

if __name__ == "__main__":
    main()
