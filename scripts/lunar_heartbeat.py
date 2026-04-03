import os
import sys
import psutil
import shutil
import asyncio
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

# Configuration
DATA_DIR = Path('/root/ultimate_engine')
LOG_FILE = DATA_DIR / "automation.log"
THRESHOLD_DISK = 90  # Percent
THRESHOLD_RAM = 95   # Percent

# Import Telegram service
sys.path.append(str(DATA_DIR))
try:
    from services.telegram_service import telegram_service
except ImportError:
    class MockTelegram:
        async def send_message(self, msg): print(f"[MOCK TELEGRAM] {msg}")
    telegram_service = MockTelegram()

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
    """Checks if the VM can reach the outside world"""
    try:
        # Ping Google DNS
        subprocess.check_call(["ping", "-c", "1", "8.8.8.8"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except:
        return False

def kill_zombie_chrome():
    """Kills lingering chromium processes to prevent memory leaks"""
    import time
    killed = 0
    for proc in psutil.process_iter(['pid', 'name', 'create_time']):
        try:
            if 'chromium' in proc.info['name'].lower() or 'playwright' in proc.info['name'].lower():
                # If running for more than 45 mins, kill it
                if time.time() - proc.info['create_time'] > 2700:
                    proc.kill()
                    killed += 1
        except:
            continue
    return killed

async def run_heartbeat():
    print(f"--- Starting Lunar Heartbeat ({datetime.now().strftime('%H:%M')}) ---")
    
    # 1. Connectivity Check (Restart Mechanism)
    if not await check_connectivity():
        print("  [ERROR] No Internet Connectivity. Attempting Tailscale Reset...")
        os.system("systemctl restart tailscaled")
        # Critical alert if internet is down (using local log if Telegram fails)
        with open("/root/emergency.log", "a") as f:
            f.write(f"[{datetime.now()}] CRITICAL: Internet/Connectivity Failure. Restarted Tailscale.\n")

    # 2. Vitals
    alerts = await check_system_vitals()
    
    # 3. Process Healing (Restart Mechanism)
    zombies = kill_zombie_chrome()
    if zombies > 0:
        print(f"  [FIXED] Terminated {zombies} zombie processes.")
        if zombies > 10:
             alerts.append(f"🚨 RESOURCE LEAK: Cleaned {zombies} hanging processes.")

    # 4. Missed Job Recovery (Logic)
    # If it's a race day and certain logs are missing, we could trigger a re-run here.
    # Currently, we focus on the recovery of the system state.

    # 5. Alerting (Error-only as per User request)
    if alerts:
        msg = "💓 [LUNAR HEARTBEAT ALERT]\n" + "\n".join(alerts)
        print(msg)
        await telegram_service.send_message(msg)
    else:
        print("  [OK] System Vitals are within normal range.")

if __name__ == '__main__':
    asyncio.run(run_heartbeat())
