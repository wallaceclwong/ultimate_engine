import time
import subprocess
import sys
import os
from datetime import datetime
from loguru import logger

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.firestore_service import FirestoreService
from config.settings import Config

class SafeRunner:
    def __init__(self, task_name: str):
        self.task_name = task_name
        self.firestore = FirestoreService()
        self.log_file = f"data/logs/{task_name.lower().replace(' ', '_')}.log"
        os.makedirs("data/logs", exist_ok=True)
        logger.add(self.log_file, rotation="10 MB")

    def heartbeat(self, status: str, details: str = ""):
        data = {
            "status": status,
            "details": details,
            "last_heartbeat": datetime.now().isoformat(),
            "task": self.task_name
        }
        logger.info(f"[HEARTBEAT] {status}: {details}")
        try:
            self.firestore.upsert("system_status", self.task_name, data)
        except Exception as e:
            logger.error(f"Failed to send heartbeat: {e}")

    def run_with_retries(self, command: list, max_retries: int = 3, delay: int = 30):
        attempt = 0
        while attempt < max_retries:
            attempt += 1
            self.heartbeat("RUNNING", f"Attempt {attempt}/{max_retries}")
            
            try:
                process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
                
                for line in process.stdout:
                    print(line.strip())
                    if "Error" in line or "Exception" in line:
                        logger.warning(f"[SUBPROCESS] {line.strip()}")
                
                process.wait()
                
                if process.returncode == 0:
                    self.heartbeat("COMPLETED", f"Command finished successfully")
                    return True
                else:
                    logger.error(f"Command failed with exit code {process.returncode}")
                    self.heartbeat("ERROR", f"Failed with exit code {process.returncode}")
            
            except Exception as e:
                logger.error(f"Execution exception: {e}")
                self.heartbeat("EXCEPTION", str(e))
            
            if attempt < max_retries:
                logger.info(f"Retrying in {delay} seconds...")
                time.sleep(delay)
        
        return False

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python safe_runner.py <task_name> <command_args...>")
        sys.exit(1)
    
    task = sys.argv[1]
    cmd = sys.argv[2:]
    runner = SafeRunner(task)
    runner.run_with_retries(cmd)
