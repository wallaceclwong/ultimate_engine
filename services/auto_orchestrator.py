import time
import subprocess
import sys
import os
import json
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.firestore_service import FirestoreService
from config.settings import Config

class AutoOrchestrator:
    def __init__(self):
        self.firestore = FirestoreService()
        self.base_dir = Config.BASE_DIR
        self.fixtures_path = self.base_dir / "data" / "fixtures_2026.json"
        self.last_check = None

    def log(self, msg):
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [ORCHESTRATOR] {msg}")

    def update_heartbeat(self, status, next_task=None):
        """Updates Firestore with the current status of the orchestrator."""
        hb = {
            "status": status,
            "next_task": next_task,
            "timestamp": datetime.now().timestamp(),
            "last_active": datetime.now().strftime("%H:%M:%S")
        }
        try:
            self.firestore.upsert("system_status", "orchestrator", hb)
        except: pass

    def run_task(self, command, cwd=None):
        """Runs a subprocess and waits for completion."""
        self.log(f"Executing: {' '.join(command)}")
        try:
            process = subprocess.run(command, cwd=cwd or str(self.base_dir), capture_output=True, text=True)
            if process.returncode == 0:
                self.log("Task completed successfully.")
                return True
            else:
                self.log(f"Task failed with code {process.returncode}")
                # Log first 5 lines of stderr
                for line in process.stderr.splitlines()[:5]:
                    self.log(f"  ERR: {line}")
                return False
        except Exception as e:
            self.log(f"Exception during task: {e}")
            return False

    def get_session_time(self, venue, date_obj):
        """
        Determines meeting start time.
        Rule of thumb:
        - Wednesday = Night (18:45)
        - Sunday = Day (12:30)
        - Others (Public Holidays) = Usually Day
        """
        weekday = date_obj.weekday() # 0=Mon, 2=Wed, 6=Sun
        
        if weekday == 2: # Wednesday
            return "18:45:00"
        return "12:30:00"

    def check_and_run(self):
        """The core logic to check and trigger tasks."""
        if not self.fixtures_path.exists():
            self.log("Fixtures file not found!")
            return

        with open(self.fixtures_path, "r", encoding="utf-8") as f:
            fixtures = json.load(f)

        now = datetime.now()
        today_str = now.strftime("%d/%m/%Y")
        tomorrow_str = (now + timedelta(days=1)).strftime("%d/%m/%Y")
        yesterday_str = (now - timedelta(days=1)).strftime("%d/%m/%Y")

        # 1. Check for TODAY'S meeting (Live Betting)
        today_meeting = next((f for f in fixtures if f["date"] == today_str), None)
        if today_meeting:
            iso_today = now.strftime("%Y-%m-%d")
            start_time = self.get_session_time(today_meeting["venue"], now)
            target_dt_str = f"{iso_today} {start_time}"
            
            # If we are before the start time, start the live orchestrator
            if now < datetime.strptime(target_dt_str, "%Y-%m-%d %H:%M:%S") + timedelta(hours=6):
                # Start live monitor - we use Popen so it doesn't block the orchestrator loop
                self.log(f"Meeting TODAY at {today_meeting['venue']}. Starting Live Orchestrator for {target_dt_str}")
                cmd = [
                    sys.executable, "services/live_betting_orchestrator.py",
                    "--date", now.strftime("%Y/%m/%d"),
                    "--venue", today_meeting["venue"],
                    "--target-time", target_dt_str
                ]
                # Log to a specific file
                log_file = self.base_dir / "data" / f"live_{now.strftime('%Y%m%d')}.log"
                with open(log_file, "a") as f:
                    subprocess.Popen(cmd, stdout=f, stderr=f, cwd=str(self.base_dir))
                self.update_heartbeat("LIVE_MONITORING", next_task=f"Betting for {iso_today}")

        # 2. Check for TOMORROW'S meeting (Preparation & Early Odds)
        tomorrow_meeting = next((f for f in fixtures if f["date"] == tomorrow_str), None)
        if tomorrow_meeting:
            iso_tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")
            compact_tomorrow = iso_tomorrow.replace("-", "")
            
            # Check for existing data
            has_racecards = list(self.base_dir.glob(f"data/racecard_{compact_tomorrow}_R1.json"))
            has_early_odds = list(self.base_dir.glob(f"data/odds/snapshot_{compact_tomorrow}_R1_*.json"))
            
            # Condition: If racecards are missing OR (after 2 PM and early odds are missing)
            if not has_racecards or (not has_early_odds and now.hour >= 14):
                status_msg = "Initial Prep" if not has_racecards else "Early Odds Sweep"
                self.log(f"Meeting TOMORROW at {tomorrow_meeting['venue']}. Running {status_msg}...")
                self.run_task([sys.executable, "services/daily_runner.py", "--date", iso_tomorrow])

        # 3. Check for YESTERDAY'S meeting (Settlement)
        yesterday_meeting = next((f for f in fixtures if f["date"] == yesterday_str), None)
        if yesterday_meeting:
            iso_yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
            # If results don't exist yet, run results/settlement
            if not list(self.base_dir.glob(f"data/results/results_{iso_yesterday}_*.json")):
                self.log(f"Meeting YESTERDAY at {yesterday_meeting['venue']}. Running settlement & learning...")
                self.run_task([sys.executable, "services/daily_runner.py", "--date", iso_yesterday])
                
                # Trigger RL Recalibration specifically
                self.run_task([sys.executable, "services/rl_optimizer.py", "--days", "7"])
                self.log("Recalibration complete for the past week.")

        self.update_heartbeat("IDLE", next_task="Calendar check in 1 hour")

    def run_forever(self):
        self.log("Starting Full-Cycle Orchestrator...")
        while True:
            try:
                self.check_and_run()
                time.sleep(3600) # Check every hour
            except KeyboardInterrupt:
                break
            except Exception as e:
                self.log(f"CRITICAL ERROR: {e}")
                time.sleep(300)

if __name__ == "__main__":
    orch = AutoOrchestrator()
    orch.run_forever()
