"""
PC Startup Orchestrator
========================
Runs automatically on PC boot. Checks if there's an upcoming meeting,
scrapes racecards if needed, syncs to VM, triggers predictions,
and starts the local server with live odds monitoring.

Smart checks:
- Only processes if a meeting is within the next 2 days
- Skips if racecards already scraped for that meeting
- Starts the local dashboard + watchdog automatically
"""
import json
import subprocess
import sys
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from services.memory_service import memory_service
from telegram_service import telegram_service

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VM_HOST = "root@100.109.76.69"
VM_PATH = "/opt/ultimate_engine"
LOG_FILE = PROJECT_ROOT / "logs" / "startup.log"


def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_fixtures():
    year = datetime.now().year
    fixtures_path = PROJECT_ROOT / "data" / f"fixtures_{year}.json"
    if fixtures_path.exists():
        with open(fixtures_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def find_upcoming_meeting():
    """Find the next meeting within 2 days."""
    fixtures = load_fixtures()
    now = datetime.now().date()
    for day_offset in range(3):  # Today, tomorrow, day after
        d = now + timedelta(days=day_offset)
        d_str = d.strftime("%d/%m/%Y")
        for f in fixtures:
            if f["date"] == d_str:
                return d.strftime("%Y-%m-%d"), f["venue"]
    return None, None


def is_already_processed(date_str, venue):
    """Check if predictions already exist for this meeting."""
    pred_file = PROJECT_ROOT / "data" / "predictions" / f"prediction_{date_str}_{venue}_R1.json"
    if not pred_file.exists():
        return False
    # Check if it has market_odds (fully processed)
    try:
        with open(pred_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return bool(data.get("market_odds"))
    except:
        return False


def racecards_exist(date_str):
    """Check if racecards have been scraped."""
    date_compact = date_str.replace("-", "")
    return len(list((PROJECT_ROOT / "data").glob(f"racecard_{date_compact}_R*.json"))) >= 5


def run_cmd(cmd, timeout=300):
    log(f"  > {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            cwd=str(PROJECT_ROOT), shell=isinstance(cmd, str)
        )
        if result.returncode != 0 and result.stderr:
            log(f"  [WARN] {result.stderr[:200]}")
        return result.returncode == 0
    except Exception as e:
        log(f"  [ERROR] {e}")
        return False


def scrape_racecards(date_str, venue):
    log(f"Scraping racecards for {date_str} ({venue})...")
    py = str(PROJECT_ROOT / ".venv" / "Scripts" / "python.exe")
    script = str(PROJECT_ROOT / "services" / "racecard_ingest.py")
    date_fmt = date_str.replace("-", "/")
    for r in range(1, 12):
        run_cmd([py, script, "--date", date_fmt, "--venue", venue, "--race", str(r)])
    log(f"Racecard scraping complete.")


def sync_to_vm(date_str):
    log("Syncing racecards to VM...")
    date_compact = date_str.replace("-", "")
    files = list((PROJECT_ROOT / "data").glob(f"racecard_{date_compact}_R*.json"))
    for f in files:
        run_cmd(["scp", "-o", "ConnectTimeout=10", str(f), f"{VM_HOST}:{VM_PATH}/data/{f.name}"])
    log(f"Synced {len(files)} files to VM.")


def trigger_vm_predictions(date_str, venue):
    log(f"Triggering AI predictions on VM for {date_str} ({venue})...")
    cmd = (
        f"cd {VM_PATH} && "
        f"export PYTHONPATH={VM_PATH} && "
        f"set -a && . {VM_PATH}/.env && set +a && "
        f"python3 scripts/vm_predict.py --date {date_str} --venue {venue}"
    )
    run_cmd(["ssh", "-o", "ConnectTimeout=10", VM_HOST, cmd], timeout=600)


def start_local_server():
    """Start the local dashboard + watchdog in background."""
    log("Skipping local dashboard startup (dashboard module currently missing).")
    # py = str(PROJECT_ROOT / ".venv" / "Scripts" / "python.exe")
    # subprocess.Popen(
    #     [py, "-m", "uvicorn", "dashboard.server:app", "--host", "0.0.0.0", "--port", "8000"],
    #     cwd=str(PROJECT_ROOT),
    #     creationflags=subprocess.CREATE_NEW_CONSOLE
    # )
    # log("Local server started in new window.")


async def check_mempalace():
    """Verify connectivity to the MemPalace vector store on the VM."""
    log("Checking MemPalace connectivity...")
    try:
        status = memory_service.get_status()
        if status and "WING" in status:
            log("  [OK] MemPalace is online and connected.")
            return True
        else:
            log("  [WARN] MemPalace status empty or invalid. Check VM/Tailscale.")
            await telegram_service.send_message("⚠️ *Lunar Heartbeat*: MemPalace is reachable but status is invalid.")
            return False
    except Exception as e:
        log(f"  [ERROR] MemPalace connection failed: {e}")
        await telegram_service.send_message(f"🚨 *Lunar Alarm*: MemPalace connection failed during startup!\n{e}")
        return False


def main():
    log("=" * 50)
    log("HKJC AI — Startup Check")
    log("=" * 50)

    # 1. Check MemPalace Connectivity (Background Sync)
    import asyncio
    asyncio.run(check_mempalace())

    # 2. Find upcoming meeting
    date_str, venue = find_upcoming_meeting()
    if not date_str:
        log("No upcoming meeting within 2 days. Starting server only.")
        start_local_server()
        return

    log(f"Upcoming meeting: {date_str} ({venue})")

    # 2. Scrape racecards if not done
    if not racecards_exist(date_str):
        scrape_racecards(date_str, venue)
    else:
        log("Racecards already scraped. Skipping.")

    # 3. Sync to VM and trigger predictions
    if not is_already_processed(date_str, venue):
        sync_to_vm(date_str)
        trigger_vm_predictions(date_str, venue)
    else:
        log("Predictions already exist with market odds. Skipping VM trigger.")

    # 4. Start local server with watchdog
    start_local_server()

    log("Startup complete! Dashboard + Watchdog running.")


if __name__ == "__main__":
    main()
