"""
Ultimate Engine V3: System Health Audit
========================================
Comprehensive diagnostic tool to verify all components of the race-day pipeline.
"""
import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.append(os.getcwd())

from services.firestore_service import FirestoreService
from consensus_agent import consensus_agent
from config.settings import Config

def log(msg, symbol="[INFO]"):
    print(f"{symbol} {msg}")

async def run_audit():
    print("="*60)
    print(f"ULTIMATE ENGINE DIAGNOSTIC AUDIT: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # 1. AI Connectivity (DeepSeek)
    log("Checking DeepSeek AI Connectivity...")
    ds_ok = await consensus_agent.check_health()
    if ds_ok:
        log("DeepSeek-R1 (Reasoner): ONLINE", "[PASS]")
    else:
        log("DeepSeek-R1 (Reasoner): OFFLINE / TIMEOUT", "[FAIL]")

    # 2. Cloud Sync (Firestore)
    log("Checking Firestore Cloud Sync...")
    try:
        fs = FirestoreService()
        # Test query for today's weather
        today_iso = datetime.now().strftime("%Y-%m-%d")
        weather = fs.get_document("weather_intel", f"{today_iso}_HV")
        if weather:
            log(f"Firestore Sync: OK (Found weather for {today_iso})", "[PASS]")
        else:
            log("Firestore Sync: WARNING (Connected, but no weather found for today)", "[WARN]")
    except Exception as e:
        log(f"Firestore Sync: FAILED ({e})", "[FAIL]")

    # 3. Memory Warehouse (MemPalace)
    log("Checking MemPalace Connectivity...")
    try:
        consensus_agent.reload_pedigree()
        log("MemPalace: ONLINE (Pedigree cache accessible)", "[PASS]")
    except Exception as e:
        log(f"MemPalace: ERROR ({e})", "[FAIL]")

    # 4. Data Integrity (JSON Predictions)
    log("Checking Data Integrity (Today's Predictions)...")
    pred_dir = Path("data/predictions")
    preds = list(pred_dir.glob(f"prediction_{today_iso}_HV_R*.json"))
    if len(preds) >= 8:
        log(f"Predictions: OK ({len(preds)} races found)", "[PASS]")
    else:
        log(f"Predictions: INCOMPLETE ({len(preds)}/9 races found)", "[WARN]")

    # 5. Local Storage (Odds Snapshots)
    log("Checking Odds Snapshot Flow...")
    odds_dir = Path("data/odds")
    latest_odds = list(odds_dir.glob(f"snapshot_{today_iso.replace('-', '')}_R*.json"))
    if latest_odds:
        latest = max(latest_odds, key=lambda p: p.stat().st_mtime)
        delta_min = (datetime.now().timestamp() - latest.stat().st_mtime) / 60
        if delta_min < 10:
            log(f"Odds Inflow: ACTIVE (Last update {delta_min:.1f}m ago)", "[PASS]")
        else:
            log(f"Odds Inflow: STALLED? (Last update {delta_min:.1f}m ago)", "[WARN]")
    else:
        log("Odds Inflow: NO DATA for today found in data/odds", "[FAIL]")

    print("="*60)
    print("AUDIT COMPLETE")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(run_audit())
