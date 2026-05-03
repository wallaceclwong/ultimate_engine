import json
import pandas as pd
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent.parent
DATE_STR = "2026-04-29"
VENUE = "HV"

def compare_race(r_no):
    pred_file = BASE_DIR / "data" / "predictions" / f"prediction_{DATE_STR}_{VENUE}_R{r_no}.json"
    result_file = BASE_DIR / "data" / "results" / f"results_{DATE_STR}_{VENUE}_R{r_no}.json"
    
    if not pred_file.exists():
        return None
    if not result_file.exists():
        return None
    
    with open(pred_file, encoding='utf-8') as f:
        pred = json.load(f)
    with open(result_file, encoding='utf-8') as f:
        result = json.load(f)
    
    # Build comparison table
    rows = []
    probs = pred.get("probabilities", {})
    market_odds = pred.get("market_odds", {})
    
    # Build results lookup
    results_map = {str(r["horse_no"]): r for r in result.get("results", [])}
    
    for h_no_str, prob in probs.items():
        h_no = int(h_no_str)
        mkt_odds = market_odds.get(h_no_str, 0)
        fair_odds = 1 / prob if prob > 0 else 0
        value_mult = mkt_odds / fair_odds if fair_odds > 0 else 0
        
        r_horse = results_map.get(h_no_str)
        
        if r_horse:
            rows.append({
                "#": h_no,
                "Horse": r_horse.get("horse", "").split("\u00a0")[0][:20],
                "Pred Prob": f"{prob:.1%}",
                "Fair Odds": f"{fair_odds:.1f}",
                "Market Odds": f"{mkt_odds:.1f}",
                "Value": f"{value_mult:.2f}",
                "Act Fin": r_horse.get("plc", ""),
                "Act Odds": f"{float(r_horse.get('win_odds', 0)):.1f}"
            })
    
    df = pd.DataFrame(rows)
    if df.empty:
        return None
    
    # Sort by prediction probability (highest first = top pick)
    df = df.sort_values("Pred Prob", ascending=False)
    return df

def main():
    print(f"\n{'='*80}")
    print(f"ULTIMATE ENGINE v3 - Prediction vs Results: {DATE_STR} {VENUE}")
    print(f"{'='*80}\n")
    
    all_correct = 0
    total_picks = 0
    
    for r_no in range(1, 10):
        df = compare_race(r_no)
        if df is None:
            continue
        
        print(f"RACE {r_no}")
        print("-" * 80)
        print(df.to_string(index=False))
        print()
        
        # Check if top pick won
        top_pick = df.iloc[0]
        if top_pick["Act Fin"] == "1":
            print(f"✅ TOP PICK WON: #{top_pick['#']} {top_pick['Horse']}")
            all_correct += 1
        else:
            print(f"❌ Top pick finished {top_pick['Act Fin']}")
        
        total_picks += 1
        print()
    
    print("="*80)
    print(f"SUMMARY: {all_correct}/{total_picks} top picks correct ({all_correct/total_picks*100:.1f}%)")
    print("="*80)

if __name__ == "__main__":
    main()
