import sys, json, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services.memory_service import MemoryService

m = MemoryService()

print("=== MAY 9 SCORECARD — PREDICTION vs ACTUAL ===\n")
print(f"{'R':<3} {'Predicted':<28} {'Odds':>5}  {'Actual WIN':<28} {'Result'}")
print("-" * 80)

best_bet_results = []

for r in range(1, 12):
    pred_raw = m._execute_cmd(f"cat /root/ultimate_engine/data/predictions/prediction_2026-05-09_ST_R{r}.json 2>/dev/null")
    res_raw  = m._execute_cmd(f"cat /root/ultimate_engine/data/results/results_2026-05-09_ST_R{r}.json 2>/dev/null")

    pred_horse = "?"
    pred_no = "?"
    pred_odds = "?"
    is_best = False
    actual_winner = "?"
    actual_no = "?"

    if pred_raw:
        try:
            d = json.loads(pred_raw)
            is_best = d.get("is_best_bet", False)
            rec = d.get("recommended_bet", "")
            pred_no = rec.replace("WIN ", "").strip() if rec else "?"
            analysis = d.get("analysis_markdown", "")
            mkt = d.get("market_odds", {})
            pred_odds = mkt.get(str(pred_no), "?")
            for line in analysis.split("\n"):
                if "**#" in line and pred_no in line:
                    m2 = re.search(r'\*\*#\d+ ([A-Z ]+)\*\*', line)
                    if m2:
                        pred_horse = m2.group(1).strip()[:26]
                        break
        except (json.JSONDecodeError, KeyError, AttributeError): pass

    if res_raw:
        try:
            rd = json.loads(res_raw)
            # Try common result keys
            winner = rd.get("winner") or rd.get("first") or {}
            if isinstance(winner, dict):
                actual_no = str(winner.get("horse_number", winner.get("number", "?")))
                actual_winner = winner.get("horse_name", winner.get("name", "?"))[:26]
            elif isinstance(winner, str):
                actual_winner = winner[:26]
            # Also try places list
            places = rd.get("places") or rd.get("results") or []
            if places and actual_winner == "?":
                first = places[0] if places else {}
                actual_no = str(first.get("horse_number", first.get("number", "?")))
                actual_winner = first.get("horse_name", first.get("name", "?"))[:26]
        except (json.JSONDecodeError, KeyError, AttributeError): pass

    hit = "✅ WIN" if (pred_no != "?" and actual_no != "?" and pred_no == actual_no) else ("❌" if actual_no != "?" else "—")
    best_flag = "⭐" if is_best else "  "
    print(f"{best_flag}R{r:<2} #{pred_no:<3} {pred_horse:<26} @{str(pred_odds):>5}  #{actual_no:<3} {actual_winner:<26} {hit}")

    if is_best:
        best_bet_results.append({
            "race": r, "pred_no": pred_no, "horse": pred_horse,
            "odds": pred_odds, "actual_no": actual_no,
            "hit": pred_no == actual_no
        })

print("\n=== BEST BETS SUMMARY ===")
hits = sum(1 for b in best_bet_results if b["hit"])
print(f"Best bets: {len(best_bet_results)}  |  Hits: {hits}")
for b in best_bet_results:
    icon = "✅" if b["hit"] else "❌"
    print(f"  {icon} R{b['race']} #{b['pred_no']} {b['horse']} @ {b['odds']}")
