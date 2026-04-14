"""
lunar_rest_day.py
=================
Automated Non-Race Day Orchestrator for the Vultr VM.
Runs intense computational and optimization functions that are not
appropriate to run during live market fetching.
"""

import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PYTHON_EXEC = sys.executable

def run_cmd(cmd, label):
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] {'='*50}")
    print(f"[{label}] Executing: {' '.join(cmd)}")
    print("=" * 50)
    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(BASE_DIR),
            universal_newlines=True
        )
        
        for line in process.stdout:
            print(f"[{label}] {line.strip()}")
            
        process.wait()
        
        if process.returncode != 0:
            print(f"\n[ERROR] '{label}' EXITED WITH CODE {process.returncode}")
            return False
        return True
            
    except Exception as e:
        print(f"\n[FATAL] '{label}' FAILED: {e}")
        return False

def main():
    print(f"\n{'#'*60}")
    print(f"# LUNAR LEAP - REST DAY OPTIMIZATION CYCLE")
    print(f"# Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*60}")
    
    # 1. Train Models
    script_train = BASE_DIR / "train_model.py"
    if not run_cmd([PYTHON_EXEC, str(script_train)], "ML_TRAINING"):
        print("\nStopping Rest Day cycle due to Training failure.")
        return

    # 2. Modern Season Backtest Validation
    script_backtest = BASE_DIR / "scripts" / "run_modern_backtest.py"
    if not run_cmd([PYTHON_EXEC, str(script_backtest)], "BACKTEST"):
        print("\nStopping Rest Day cycle due to Backtest failure.")
        return
        
    # 3. Agent Dream State (MemPalace Consolidation)
    script_dream = BASE_DIR / "scripts" / "mempalace_dream.py"
    if not run_cmd([PYTHON_EXEC, str(script_dream)], "DREAM_STATE"):
        print("\nDream state encountered issues, continuing anyway.")

    print(f"\n{'#'*60}")
    print(f"# REST DAY OPTIMIZATION COMPLETE")
    print(f"# Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*60}\n")

if __name__ == "__main__":
    main()
