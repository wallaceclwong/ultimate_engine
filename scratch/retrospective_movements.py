import json
from pathlib import Path
from datetime import datetime

ODDS_DIR = Path("c:/Users/ASUS/ultimate_engine/data/odds")
DATE_STR = "2026-04-22"
DATE_COMPACT = "20260422"

def analyze_movements():
    results = []
    for r in range(1, 10):
        # Earliest snapshot (Noon baseline)
        pattern = f"snapshot_{DATE_COMPACT}_R{r}_*.json"
        files = sorted(ODDS_DIR.glob(pattern), key=lambda x: x.stat().st_mtime)
        
        if len(files) < 2: continue
        
        with open(files[0], 'r') as f:
            baseline = json.load(f).get('win_odds', {})
            
        # Find snapshot closest to T-15 (e.g. if jump is 18:40, look for 18:25)
        # For simplicity, we'll use the one around the 18:25 range for R1, etc.
        # Actually, let's just use the LAST snapshot before the race gap (which is the T-15 audit one)
        # In scheduler_state.json, we saw the timestamps of the audits.
        
        with open(files[-1], 'r') as f: # Last one captured before jump
            current = json.load(f).get('win_odds', {})
            
        movements = {}
        for h, odds in current.items():
            b_odds = baseline.get(h)
            if b_odds and b_odds > 0:
                move = (odds - b_odds) / b_odds
                movements[h] = move
                
        results.append({"race": r, "movements": movements})
        
    return results

if __name__ == "__main__":
    movements = analyze_movements()
    
    # Let's check our winners' movements specifically
    winners = {1: "4", 2: "1", 3: "11", 4: "5", 5: "2", 6: "3", 7: "9", 8: "2", 9: "6"}
    
    print(f"{'Race':<5} | {'Winner':<7} | {'Movement':<10} | {'Status'}")
    print("-" * 40)
    for res in movements:
        r = res["race"]
        w = winners.get(r)
        m = res["movements"].get(w, 0)
        
        status = "IGNORE"
        if m < -0.05: status = "TRIGGER (5%)"
        elif m < -0.03: status = "TRIGGER (3%)"
        
        print(f"{r:<5} | #{w:<6} | {m:>+9.1%} | {status}")
