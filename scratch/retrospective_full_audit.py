import json
import asyncio
import pandas as pd
from pathlib import Path
from datetime import datetime

# Settings
BASE_DIR = Path("c:/Users/ASUS/ultimate_engine")
ODDS_DIR = BASE_DIR / "data" / "odds"
DATE_STR = "2026-04-22"
DATE_COMPACT = "20260422"
VENUE = "HV"

async def retrospective_audit():
    results = []
    
    # Add project root to path
    import sys
    sys.path.append(str(BASE_DIR))
    from consensus_agent import consensus_agent
    
    for r in range(1, 10):
        # 1. Load Baseline (Noon)
        pattern = f"snapshot_{DATE_COMPACT}_R{r}_*.json"
        files = sorted(ODDS_DIR.glob(pattern), key=lambda x: x.stat().st_mtime)
        if len(files) < 2: continue
        
        with open(files[0], 'r') as f:
            baseline = json.load(f).get('win_odds', {})
            
        # 2. Load T-15 Snapshot
        # Audit window is T-16 to T-14. 
        # We'll take the snapshot that was likely the trigger.
        with open(files[-1], 'r') as f: 
            current = json.load(f).get('win_odds', {})
            
        # 3. Load Race Data for Audit
        file_path = BASE_DIR / "data" / "processed" / f"features_{DATE_STR}_{VENUE}_R{r}.parquet"
        if not file_path.exists(): continue
        race_data = pd.read_parquet(file_path)
        
        # 4. Check all horses for >3% shortening
        for h, odds in current.items():
            b_odds = baseline.get(h)
            if not b_odds or b_odds <= 0: continue
            
            movement_pct = (odds - b_odds) / b_odds
            
            if movement_pct < -0.03:
                print(f"[RETR] Race {r} Horse #{h}: {b_odds} -> {odds} ({movement_pct:+.1%}). Running mock audit...")
                
                market_context = {'movement': movement_pct, 'trend': 'shorten'}
                verdict, reasoning = await consensus_agent.get_consensus(race_data, h, market_context)
                
                results.append({
                    "race": r,
                    "horse": h,
                    "movement": movement_pct,
                    "verdict": verdict,
                    "reasoning": reasoning
                })
                
    return results

if __name__ == "__main__":
    import asyncio
    findings = asyncio.run(retrospective_audit())
    
    print("\n" + "="*60)
    print("RETROSPECTIVE REPORT (3% Threshold)")
    print("="*60)
    for f in findings:
        print(f"Race {f['race']} #{f['horse']} | {f['movement']:+.1%} | {f['verdict']}")
        print(f"Reason: {f['reasoning']}")
        print("-" * 60)
