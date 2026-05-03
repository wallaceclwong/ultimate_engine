import os
import sys
import psutil
import shutil
import asyncio
import subprocess
import json
from datetime import datetime, timedelta
from pathlib import Path
import pytz

# Configuration
HKT = pytz.timezone('Asia/Hong_Kong')
BASE_DIR = Path(__file__).resolve().parent.parent
LOG_FILE = BASE_DIR / "logs" / "automation.log"
FIXTURES_FILE = BASE_DIR / "data" / "fixtures_2026.json"
STATE_FILE = BASE_DIR / "logs" / "heartbeat_state.json"
THRESHOLD_DISK = 90  # Percent
THRESHOLD_RAM = 95   # Percent
SCHEDULER_SCRIPT = "ultimate_scheduler_vm.py"
PYTHON_EXEC = sys.executable

# Import Telegram service
sys.path.append(str(BASE_DIR))
try:
    from telegram_service import telegram_service
except ImportError:
    class MockTelegram:
        async def send_message(self, msg): print(f"[MOCK TELEGRAM] {msg}")
    telegram_service = MockTelegram()

def get_last_disk_alert():
    """Reads the last disk alert time from state file."""
    try:
        if STATE_FILE.exists():
            with open(STATE_FILE, "r") as f:
                state = json.load(f)
                dt_str = state.get("last_disk_alert")
                if dt_str:
                    return datetime.fromisoformat(dt_str).replace(tzinfo=HKT)
    except: pass
    return None

def save_disk_alert_time(dt):
    """Saves the current disk alert time to state file."""
    try:
        state = {}
        if STATE_FILE.exists():
            with open(STATE_FILE, "r") as f:
                state = json.load(f)
        state["last_disk_alert"] = dt.isoformat()
        os.makedirs(STATE_FILE.parent, exist_ok=True)
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
    except: pass

def get_today_fixture():
    """Checks if today is a race day based on the season fixtures."""
    if not FIXTURES_FILE.exists():
        return None
        
    now = datetime.now(HKT)
    d, m, y = now.day, now.month, now.year
    possible_dates = [
        f"{d}/{m:02d}/{y}",
        f"{d:02d}/{m:02d}/{y}",
        f"{d}/{m}/{y}",
        f"{d:02d}/{m}/{y}"
    ]
    
    try:
        with open(FIXTURES_FILE, "r") as f:
            fixtures = json.load(f)
            for fxt in fixtures:
                if fxt["date"] in possible_dates:
                    return fxt
    except: pass
    return None

def is_scheduler_running():
    """Checks if the ultimate_scheduler_vm.py is currently active."""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info.get('cmdline')
            if cmdline and any(SCHEDULER_SCRIPT in arg for arg in cmdline):
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False

def clean_stale_lock():
    """Removes the scheduler lock if it's orphaned."""
    lock_file = BASE_DIR / "ultimate_scheduler.lock"
    if lock_file.exists():
        if not is_scheduler_running():
            print(f"  [CLEANUP] Removing orphaned lock file: {lock_file}")
            try:
                os.remove(lock_file)
            except: pass

async def heal_scheduler():
    """Relaunches the scheduler in --live mode."""
    py_path = str(BASE_DIR / ".venv" / "Scripts" / "python.exe")
    script_path = str(BASE_DIR / SCHEDULER_SCRIPT)
    print(f"  [HEAL] Executing: {py_path} {script_path} --live")
    
    # Detached process for Windows (CREATE_NEW_CONSOLE)
    creation_flags = 0
    if os.name == 'nt':
        # CREATE_NEW_CONSOLE starts the process in a new window
        creation_flags = subprocess.CREATE_NEW_CONSOLE
        
    try:
        # Start detached
        subprocess.Popen(
            [py_path, script_path, "--live"],
            cwd=str(BASE_DIR),
            creationflags=creation_flags
        )
        return True
    except Exception as e:
        print(f"  [ERROR] Failed to relaunch scheduler: {e}")
        return False

async def check_system_vitals():
    alerts = []
    
    # 1. Disk Check
    disk = shutil.disk_usage("/")
    disk_p = (disk.used / disk.total) * 100
    if disk_p > THRESHOLD_DISK:
        alerts.append(f"⚠️ LOW DISK: {disk_p:.1f}% used on /")

    # 2. RAM Check
    ram = psutil.virtual_memory()
    if ram.percent > THRESHOLD_RAM:
        alerts.append(f"⚠️ HIGH RAM: {ram.percent:.1f}% used")

    return alerts

async def check_connectivity():
    """Checks if the system can reach the internet"""
    try:
        import socket
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        return True
    except:
        return False

def kill_zombie_processes():
    """Kills lingering chromium processes to prevent memory leaks (Only targets automation browsers)"""
    import time
    killed = 0
    # Add 'exe' to attributes to check the path
    for proc in psutil.process_iter(['pid', 'name', 'create_time', 'exe']):
        try:
            exe = (proc.info.get('exe') or "").lower()
            name = (proc.info.get('name') or "").lower()
            
            # Check if it's a known automation browser name
            if 'chromium' in name or 'playwright' in name or 'chrome' in name:
                # CRITICAL: Only kill if it's inside the ms-playwright folder
                # This prevents killing the user's personal Google Chrome
                if 'ms-playwright' in exe:
                    # If running for more than 2 hours, it's likely a leaked automation instance
                    if time.time() - proc.info['create_time'] > 7200:
                        proc.kill()
                        killed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return killed

def auto_clean_workspace():
    """Performs a light cleanup of logs and caches."""
    print("  [DISC] Threshold exceeded. Performing auto-clean...")
    count = 0
    # 1. Clean __pycache__
    for path in BASE_DIR.rglob("__pycache__"):
        try:
            shutil.rmtree(path)
            count += 1
        except: pass
    
    # 2. Clean old logs (> 3 days for auto-clean)
    for log_file in BASE_DIR.glob("*.log"):
        if log_file.name == "automation.log": continue
        try:
            if (datetime.now() - datetime.fromtimestamp(log_file.stat().st_mtime)).days > 3:
                os.remove(log_file)
                count += 1
        except: pass
    
    return count

async def run_heartbeat():
    now_hkt = datetime.now(HKT)
    print(f"--- Starting Lunar Heartbeat (HKT: {now_hkt.strftime('%H:%M')}) ---")
    
    # 1. Connectivity Check
    if not await check_connectivity():
        print("  [ERROR] No Internet Connectivity.")
    
    # 2. Vitals & Cleanup
    alerts = await check_system_vitals()
    zombies = kill_zombie_processes()
    if zombies > 0:
        print(f"  [FIXED] Terminated {zombies} zombie processes.")
        if zombies > 15:
             alerts.append(f"🚨 RESOURCE LEAK: Cleaned {zombies} hanging processes.")

    # Disk Cleanup Trigger
    disk = shutil.disk_usage("/")
    disk_p = (disk.used / disk.total) * 100
    if disk_p > 95:
        cleaned = auto_clean_workspace()
        if cleaned > 0:
            print(f"  [OK] Auto-cleaned {cleaned} items to reclaim space.")

    # 3. SELF-HEALING: Scheduler Recovery
    fixture = get_today_fixture()
    if fixture:
        venue = fixture['venue']
        print(f"  [INFO] Today is a Race Day ({venue}). Checking scheduler...")
        
        if not is_scheduler_running():
            clean_stale_lock()
            success = await heal_scheduler()
            if success:
                msg = f"🛡️ *Self-Healing*: Ultimate Engine was missing and has been RELAUNCHED for {venue} meeting."
                await telegram_service.send_message(msg)
                print("  [HEALED] Scheduler relaunched successfully.")
            else:
                alerts.append(f"🚨 CRITICAL: Scheduler is missing for {venue} and RELAUNCH FAILED.")
        else:
            print("  [OK] Scheduler is active and monitored.")
    else:
        print("  [OK] No race today. Scheduler monitoring suspended.")
        # Optional: Ensure scheduler is NOT running on non-race days if preferred
        # clean_stale_lock()

    # 4. Alerting & Throttling
    if alerts:
        # Check if we should throttle the 'LOW DISK' alert
        disk_alert = next((a for a in alerts if "LOW DISK" in a), None)
        if disk_alert:
            last_alert = get_last_disk_alert()
            # 4 hours = 14400 seconds
            if last_alert and (now_hkt - last_alert).total_seconds() < 14400:
                print(f"  [THROTTLED] Skipping 'LOW DISK' Telegram alert (last sent {last_alert.strftime('%H:%M')})")
                # Remove disk alert from list but KEEP others
                alerts = [a for a in alerts if "LOW DISK" not in a]
            else:
                save_disk_alert_time(now_hkt)

    if alerts:
        msg = "💓 [LUNAR HEARTBEAT ALERT]\n" + "\n".join(alerts)
        try:
            print(msg)
        except UnicodeEncodeError:
            print(msg.encode('ascii', 'ignore').decode('ascii'))
        await telegram_service.send_message(msg)
    else:
        print("  [OK] System Vitals are within normal range.")

if __name__ == '__main__':
    asyncio.run(run_heartbeat())
