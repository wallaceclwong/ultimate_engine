import json
import sys
from pathlib import Path

root_dir = str(Path(__file__).resolve().parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

DATA_DIR = Path(root_dir) / "data"

def evaluate(date_str, venue):
    print(f"\n{'='*60}")
    print(f"  PREDICTION EVALUATION: {date_str} {venue}")
    print(f"{'='*60}")

    total = 0
    top1_correct = 0
    top3_correct = 0

    for race_no in range(1, 12):
        pred_file = DATA_DIR / "predictions" / f"prediction_{date_str}_{venue}_R{race_no}.json"
        result_file = DATA_DIR / "results" / f"results_{date_str}_{venue}_R{race_no}.json"

        if not pred_file.exists() or not result_file.exists():
            continue

        with open(pred_file) as f:
            pred = json.load(f)
        with open(result_file) as f:
            result = json.load(f)

        # Get actual winner (finishing position 1)
        results_list = result.get("results", [])
        winner = None
        placed = []
        for r in results_list:
            pos = str(r.get("plc", r.get("position", ""))).strip()
            horse_no = str(r.get("horse_no", r.get("saddle_no", ""))).strip()
            if pos == "1":
                winner = horse_no
            if pos in ["1", "2", "3"]:
                placed.append(horse_no)

        if not winner:
            print(f"\nR{race_no}: Could not determine winner")
            continue

        # Get model's top prediction
        probs = pred.get("probabilities", {})
        if not probs:
            continue

        top_pick = max(probs, key=lambda k: probs[k])
        top3_picks = sorted(probs, key=lambda k: probs[k], reverse=True)[:3]
        
        win_odds = pred.get("market_odds", {}).get(winner, "?")
        top_odds = pred.get("market_odds", {}).get(top_pick, "?")

        top1_hit = top_pick == winner
        top3_hit = winner in top3_picks
        
        if top1_hit:
            top1_correct += 1
        if top3_hit:
            top3_correct += 1
        total += 1

        status = "✅ HIT" if top1_hit else ("🔵 TOP3" if top3_hit else "❌ MISS")
        print(f"\nR{race_no}: {status}")
        print(f"  Model #1 pick: #{top_pick} (odds {top_odds}) | Actual winner: #{winner} (odds {win_odds})")
        print(f"  Model top 3: {', '.join(['#'+p for p in top3_picks])}")

    print(f"\n{'='*60}")
    print(f"  SUMMARY")
    print(f"{'='*60}")
    if total > 0:
        print(f"  Races evaluated : {total}")
        print(f"  Top-1 correct   : {top1_correct}/{total} ({100*top1_correct/total:.0f}%)")
        print(f"  Top-3 correct   : {top3_correct}/{total} ({100*top3_correct/total:.0f}%)")
    else:
        print("  No data to evaluate.")

if __name__ == "__main__":
    date_str = sys.argv[1] if len(sys.argv) > 1 else "2026-05-03"
    venue = sys.argv[2] if len(sys.argv) > 2 else "ST"
    evaluate(date_str, venue)
