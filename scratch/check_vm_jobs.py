import paramiko
import sys

VM_IP = "45.32.255.155"
VM_USER = "root"
VM_PASS = "6{tJs[Dhe,jv3@_G"

def run_cmd_remote(client, cmd):
    print(f"\n--- Running: {cmd} ---")
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        print(out)
    if err:
        print(f"ERROR: {err}")

def verify_jobs():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        print(f"Connecting to {VM_IP}...")
        client.connect(VM_IP, username=VM_USER, password=VM_PASS, timeout=10)
        
        # Check running processes
        run_cmd_remote(client, "ps aux | grep -E 'python|cron|mempalace|deepseek' | grep -v grep")
        
        # Check cronjobs
        run_cmd_remote(client, "crontab -l")

        # Check systemd services if any
        run_cmd_remote(client, "systemctl list-timers --all")

        # Run the expert audit script on the VM if it exists
        run_cmd_remote(client, "python /root/ultimate_engine/scripts/vm_expert_audit.py")

        # Check the VM logs
        run_cmd_remote(client, "tail -n 20 /root/ultimate_engine/data/automation.log")
        run_cmd_remote(client, "tail -n 20 /root/ultimate_engine/automation.log")

    except Exception as e:
        print(f"Failed to connect or execute: {e}")
    finally:
        client.close()

if __name__ == '__main__':
    verify_jobs()
