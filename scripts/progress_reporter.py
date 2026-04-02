import os
import json
from datetime import datetime
from pathlib import Path

def generate_report():
    base_dir = Path(__file__).resolve().parent.parent
    results_dir = base_dir / "data/results"
    # Current active brain path
    artifact_path = Path(r"C:\Users\ASUS\.gemini\antigravity\brain\507cc95c-e002-4b14-9a57-11e186b21f50\backfill_progress.md")
    
    # Static counts for complete legacy project (2018-2026)
    # Approx 88 meetings per year * 9 years = 792 + some 2026 meetings
    TOTAL_MEETINGS = 820 
    
    # Count unique dates processed
    try:
        processed_dates = set(f.name.split('_')[1] for f in results_dir.glob("results_*.json"))
        done = len(processed_dates)
    except Exception:
        done = 60 # Fallback to last known
        
    left = max(0, TOTAL_MEETINGS - done)
    percentage = (done / TOTAL_MEETINGS) * 100
    timestamp = datetime.now().strftime("%H:%M")
    
    report_content = f"""# 📊 Backfill Progress
**Updated:** `{timestamp}`

| Status | Count |
|---|---|
| ✅ **Meetings Done** | **{done}** |
| ⏳ **Meetings Left** | **{left}** |
| 📈 **Completion** | **{percentage:.1f}%** |

---
*Refreshing every 30 mins.*
"""
    
    with open(artifact_path, "w", encoding="utf-8") as f:
        f.write(report_content)
    
    with open(artifact_path, "w", encoding="utf-8") as f:
        f.write(report_content)
    
    print(f"Report generated at {artifact_path}")

if __name__ == "__main__":
    generate_report()
