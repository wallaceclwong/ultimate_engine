import sys
import os
import json
import subprocess
from pathlib import Path

def run_cmd(cmd):
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return res.returncode, res.stdout.strip(), res.stderr.strip()
    except Exception as e:
        return 1, "", str(e)

def audit():
    print("="*60)
    print("ULTIMATE ENGINE: VM EXPERT AUDIT")
    print("="*60)
    
    # 1. System Health
    rc, out, err = run_cmd("uptime")
    print(f"[SYSTEM] Uptime: {out}")
    
    # 2. Process Check
    print("\n[PROCESSES] Active Services:")
    rc, out, err = run_cmd("ps aux | grep -E 'python|docker|mempalace' | grep -v grep")
    if out:
        for line in out.split('\n')[:5]:
            print(f"  - {line}")
    else:
        print("  [WARN] No relevant processes found!")

    # 3. Data Integrity
    print("\n[DATA] Ingestion Check:")
    data_dir = Path("/root/ultimate_engine/data")
    if data_dir.exists():
        rcs = list(data_dir.glob("racecard_*.json"))
        results = list((data_dir / "results").glob("results_*.json"))
        print(f"  - Racecards found: {len(rcs)}")
        print(f"  - Results found: {len(results)}")
        
        matrix = Path("/root/ultimate_engine/training_data_hybrid.parquet")
        if matrix.exists():
            size = matrix.stat().st_size / (1024*1024)
            mtime = datetime.fromtimestamp(matrix.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
            print(f"  - Master Matrix: ONLINE ({size:.2f} MB, Last Updated: {mtime})")
        else:
            print("  [ERROR] Master Matrix MISSING!")
    else:
        print("  [ERROR] Data Directory MISSING!")

    # 4. Expert: MemPalace
    print("\n[EXPERT] MemPalace Status:")
    venv_py = "/root/mempalace_venv/bin/python"
    rc, out, err = run_cmd(f"{venv_py} -m mempalace.cli status")
    if rc == 0:
        print(f"  - {out}")
    else:
        print(f"  [ERROR] MemPalace check failed: {err}")

    # 5. Expert: DeepSeek Connectivity
    print("\n[EXPERT] AI Reasoning (DeepSeek) Connectivity:")
    # Simple check for the consensus_agent health via python
    check_code = "import asyncio; from consensus_agent import consensus_agent; print(asyncio.run(consensus_agent.check_health()))"
    rc, out, err = run_cmd(f"cd /root/ultimate_engine && export PYTHONPATH=. && python3 -c '{check_code}'")
    if "True" in out:
        print("  - [OK] DeepSeek API Bridge is alive.")
    else:
        print(f"  - [ERROR] DeepSeek Connectivity failed: {out} {err}")

if __name__ == "__main__":
    from datetime import datetime
    audit()
