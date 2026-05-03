import json
import pandas as pd
from pathlib import Path
from datetime import datetime
from collections import defaultdict

BASE_DIR = Path(__file__).parent.parent

def load_historical_data():
    """Load all historical predictions and results."""
    dates = ["2026-04-06", "2026-04-08", "2026-04-12", "2026-04-15", "2026-04-19", "2026-04-22", "2026-04-26", "2026-04-29"]
    venues = ["ST", "HV"]
    
    data = []
    for date in dates:
        for venue in venues:
            for r_no in range(1, 14):
                pred_file = BASE_DIR / "data" / "predictions" / f"prediction_{date}_{venue}_R{r_no}.json"
                result_file = BASE_DIR / "data" / "results" / f"results_{date}_{venue}_R{r_no}.json"
                
                if not pred_file.exists() or not result_file.exists():
                    continue
                
                try:
                    with open(pred_file, encoding='utf-8') as f:
                        pred = json.load(f)
                    with open(result_file, encoding='utf-8') as f:
                        result = json.load(f)
                    
                    # Build horse data
                    probs = pred.get("probabilities", {})
                    market_odds = pred.get("market_odds", {})
                    results_map = {str(r["horse_no"]): r for r in result.get("results", [])}
                    
                    for h_no_str, prob in probs.items():
                        h_no = int(h_no_str)
                        mkt_odds = market_odds.get(h_no_str, 0)
                        fair_odds = 1 / prob if prob > 0 else 0
                        value_mult = mkt_odds / fair_odds if fair_odds > 0 else 0
                        
                        r_horse = results_map.get(h_no_str)
                        if r_horse:
                            # Determine rank
                            rank_data = sorted([(int(k), v) for k, v in probs.items()], key=lambda x: x[1], reverse=True)
                            rank = next((i+1 for i, (h, p) in enumerate(rank_data) if h == h_no), 99)
                            
                            data.append({
                                "date": date,
                                "venue": venue,
                                "race": r_no,
                                "horse_no": h_no,
                                "prob": prob,
                                "fair_odds": fair_odds,
                                "market_odds": mkt_odds,
                                "value_mult": value_mult,
                                "rank": rank,
                                "finish": r_horse.get("plc", ""),
                                "act_odds": float(r_horse.get("win_odds", 0))
                            })
                except Exception as e:
                    print(f"Error loading {date} {venue} R{r_no}: {e}")
                    continue
    
    return pd.DataFrame(data)

def test_strategy(df, strategy_fn, name):
    """Test a strategy and return results."""
    picks = []
    for (date, venue, race), group in df.groupby(["date", "venue", "race"]):
        pick = strategy_fn(group)
        if pick is not None:
            picks.append(pick)
    
    if not picks:
        return None
    
    picks_df = pd.DataFrame(picks)
    
    # Calculate stats
    total = len(picks_df)
    winners = picks_df[picks_df["finish"] == "1"]
    hit_rate = len(winners) / total if total > 0 else 0
    
    # Calculate ROI (assuming $1 bet on each)
    returns = picks_df.apply(lambda x: x["act_odds"] - 1 if x["finish"] == "1" else -1, axis=1)
    total_return = returns.sum()
    roi_pct = (total_return / total) * 100 if total > 0 else 0
    
    # Average value mult
    avg_mult = picks_df["value_mult"].mean()
    
    return {
        "name": name,
        "total_picks": total,
        "winners": len(winners),
        "hit_rate": hit_rate,
        "total_return": total_return,
        "roi_pct": roi_pct,
        "avg_mult": avg_mult,
        "picks": picks_df
    }

def strategy_current(group):
    """Current: rank-1 AND (mult <= 1.0 OR odds <= 20)"""
    rank1 = group[group["rank"] == 1]
    if rank1.empty:
        return None
    pick = rank1[(rank1["value_mult"] <= 1.0) | (rank1["market_odds"] <= 20)]
    if pick.empty:
        return None
    return pick.iloc[0].to_dict()

def strategy_value(group):
    """Value threshold: mult > 2.0"""
    value = group[group["value_mult"] > 2.0]
    if value.empty:
        return None
    # Pick highest value
    return value.nlargest(1, "value_mult").iloc[0].to_dict()

def strategy_hybrid(group):
    """Hybrid: rank-1 OR mult > 2.0"""
    # First try rank-1 with good value
    rank1 = group[group["rank"] == 1]
    if not rank1.empty:
        rank1_good = rank1[(rank1["value_mult"] <= 1.0) | (rank1["market_odds"] <= 20)]
        if not rank1_good.empty:
            return rank1_good.iloc[0].to_dict()
    
    # Then try value threshold
    value = group[group["value_mult"] > 2.0]
    if not value.empty:
        return value.nlargest(1, "value_mult").iloc[0].to_dict()
    
    return None

def strategy_value_rank1(group):
    """Value rank-1: rank-1 with mult > 1.0 (undervalued favorites)"""
    rank1 = group[group["rank"] == 1]
    if rank1.empty:
        return None
    value_rank1 = rank1[rank1["value_mult"] > 1.0]
    if value_rank1.empty:
        return None
    return value_rank1.nlargest(1, "value_mult").iloc[0].to_dict()

def main():
    print("Loading historical data...")
    df = load_historical_data()
    print(f"Loaded {len(df)} horse-race records\n")
    
    strategies = [
        ("Current (rank-1, mult≤1.0 or odds≤20)", strategy_current),
        ("Value Threshold (mult>2.0)", strategy_value),
        ("Hybrid (rank-1 OR mult>2.0)", strategy_hybrid),
        ("Value Rank-1 (rank-1, mult>1.0)", strategy_value_rank1),
    ]
    
    results = []
    for name, fn in strategies:
        result = test_strategy(df, fn, name)
        if result:
            results.append(result)
    
    # Print summary
    print("="*80)
    print("BACKTEST RESULTS (Historical Performance)")
    print("="*80)
    print()
    
    for r in results:
        print(f"{r['name']}")
        print(f"  Picks: {r['total_picks']}")
        print(f"  Winners: {r['winners']}")
        print(f"  Hit Rate: {r['hit_rate']:.1%}")
        print(f"  Total Return: ${r['total_return']:.2f} (on $1 bets)")
        print(f"  ROI: {r['roi_pct']:+.1f}%")
        print(f"  Avg Value Mult: {r['avg_mult']:.2f}")
        print()
    
    print("="*80)
    print("RECOMMENDATION")
    print("="*80)
    
    best_roi = max(results, key=lambda x: x['roi_pct'])
    best_hit = max(results, key=lambda x: x['hit_rate'])
    
    print(f"Best ROI: {best_roi['name']} ({best_roi['roi_pct']:+.1f}%)")
    print(f"Best Hit Rate: {best_hit['name']} ({best_hit['hit_rate']:.1%})")
    print()

if __name__ == "__main__":
    main()
