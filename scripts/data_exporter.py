import json
import os
from pathlib import Path
from datetime import datetime

import sys
# Add project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import Config

def export_stats():
    base_dir = Config.BASE_DIR
    predictions_dir = base_dir / "data/predictions"
    results_dir = base_dir / "data/results"
    output_path = base_dir / "dashboard/src/data/stats.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    prediction_files = list(predictions_dir.glob("prediction_*.json"))
    
    stats = {
        "summary": {
            "total_races": 0,
            "wins": 0,
            "total_stake": 0,
            "total_return": 0,
            "net_profit": 0,
            "roi": 0,
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M")
        },
        "daily_performance": [] # {date, profit, cum_profit}
    }

    daily_data = {} # date -> {profit, return, stake}

    for p_file in prediction_files:
        with open(p_file, 'r', encoding='utf-8') as f:
            prediction = json.load(f)
        
        race_id = prediction["race_id"]
        # Extract date from race_id: 2025-01-01_ST_R1
        date_str = race_id.split('_')[0]
        
        # Find corresponding result
        result_file = results_dir / f"results_{race_id}.json"
        if not result_file.exists():
            continue
            
        with open(result_file, 'r', encoding='utf-8') as f:
            result = json.load(f)
            
        # Betting logic: $10 on recommended_bet
        recommended = prediction.get("recommended_bet", "")
        if "WIN" not in recommended:
            continue
            
        horse_no = recommended.split(" ")[-1]
        
        stake = 10
        returns = 0
        is_win = False
        
        # Check results
        for r in result.get("results", []):
            if str(r["horse_no"]) == horse_no and str(r.get("plc", r.get("placing", ""))) == "1":
                # Find dividend

                dividend = 0
                for div in result.get("dividends", {}).get("WIN", []):
                    if str(div["combination"]) == horse_no:
                        dividend = float(div["dividend"].replace(',', ''))
                        break
                returns = (dividend / 10) * stake
                is_win = True
                break
        
        profit = returns - stake
        
        # Aggregate
        stats["summary"]["total_races"] += 1
        if is_win: stats["summary"]["wins"] += 1
        stats["summary"]["total_stake"] += stake
        stats["summary"]["total_return"] += returns
        
        if date_str not in daily_data:
            daily_data[date_str] = {"profit": 0, "stake": 0, "return": 0}
        
        daily_data[date_str]["profit"] += profit
        daily_data[date_str]["stake"] += stake
        daily_data[date_str]["return"] += returns

    # Calculate ROI
    if stats["summary"]["total_stake"] > 0:
        stats["summary"]["net_profit"] = stats["summary"]["total_return"] - stats["summary"]["total_stake"]
        stats["summary"]["roi"] = round((stats["summary"]["net_profit"] / stats["summary"]["total_stake"]) * 100, 1)

    # Sort daily performance
    sorted_dates = sorted(daily_data.keys())
    cum_profit = 0
    for d in sorted_dates:
        cum_profit += daily_data[d]["profit"]
        stats["daily_performance"].append({
            "date": d,
            "profit": round(daily_data[d]["profit"], 2),
            "cum_profit": round(cum_profit, 2)
        })

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2)
    
    print(f"Stats exported to {output_path}")

if __name__ == "__main__":
    export_stats()
