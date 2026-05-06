import json
import os
import pandas as pd
from pathlib import Path

BASE_DIR = Path("c:/Users/ASUS/ultimate_engine")
PREDICTIONS_DIR = BASE_DIR / "data" / "predictions"
RESULTS_DIR = BASE_DIR / "data" / "results"
DATE = "2026-04-22"
VENUE = "HV"

def summarize_day():
    summary = []
    total_races = 0
    top1_wins = 0
    top3_wins = 0
    total_roi = 0.0
    
    for r in range(1, 10):
        pred_file = PREDICTIONS_DIR / f"prediction_{DATE}_{VENUE}_R{r}.json"
        res_file = RESULTS_DIR / f"results_{DATE}_{VENUE}_R{r}.json"
        
        if not pred_file.exists() or not res_file.exists():
            continue
            
        total_races += 1
        with open(pred_file, "r") as f:
            pred = json.load(f)
        with open(res_file, "r") as f:
            res = json.load(f)
            
        # Get winner
        winner_no = None
        for r_entry in res.get("results", []):
            if r_entry.get("plc") == "1":
                winner_no = str(r_entry.get("horse_no"))
                win_odds = float(r_entry.get("win_odds", 1.0))
                break
        
        if not winner_no:
            continue
            
        # Get top 3 predicted
        probs = pred.get("probabilities", {})
        sorted_probs = sorted(probs.items(), key=lambda x: x[1], reverse=True)
        top1 = str(sorted_probs[0][0]) if len(sorted_probs) > 0 else None
        top3 = [str(x[0]) for x in sorted_probs[:3]]
        
        is_top1 = (winner_no == top1)
        is_top3 = (winner_no in top3)
        
        if is_top1: top1_wins += 1
        if is_top3: top3_wins += 1
        
        summary.append({
            "race": r,
            "winner": winner_no,
            "odds": win_odds,
            "top1": top1,
            "is_top1": is_top1,
            "is_top3": is_top3,
            "top3": top3
        })
        
    return {
        "total_races": total_races,
        "top1_wins": top1_wins,
        "top3_wins": top3_wins,
        "summary": summary
    }

if __name__ == "__main__":
    report = summarize_day()
    print(json.dumps(report, indent=2))
