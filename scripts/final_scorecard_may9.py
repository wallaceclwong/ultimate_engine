import sys, json, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services.memory_service import MemoryService

m = MemoryService()

print("=== MAY 9 SCORECARD (ST — Wet/Yielding) ===\n")
print(f"{'':2} {'R':<3} {'Predicted':<26} {'Edge':>7}  {'Actual WIN':<26} {'Finish':<8} {'Result'}")
print("-" * 88)

total = hits = near_misses = 0
best_bets = []

for r in range(1, 12):
    pred_raw = m._execute_cmd(f"cat /root/ultimate_engine/data/predictions/prediction_2026-05-09_ST_R{r}.json 2>/dev/null")
    res_raw  = m._execute_cmd(f"cat /root/ultimate_engine/data/results/results_2026-05-09_ST_R{r}.json 2>/dev/null")

    pred_no = "?"; pred_horse = "?"; edge_str = "?"; is_best = False
    actual_no = "?"; actual_name = "?"; time_str = "?"; pred_finish = "?"

    if pred_raw:
        try:
            d = json.loads(pred_raw)
            is_best = d.get("is_best_bet", False)
            rec = d.get("recommended_bet", "")
            pred_no = rec.replace("WIN ", "").strip() if rec else "?"
            analysis = d.get("analysis_markdown", "")
            m2 = re.search(r'\*\*#\d+ ([A-Z ]+)\*\*', analysis)
            if m2: pred_horse = m2.group(1).strip()[:24]
            m3 = re.search(r'Edge \+?([\d.]+)%', analysis)
            if m3: edge_str = f"+{m3.group(1)}%"
        except (json.JSONDecodeError, KeyError, AttributeError): pass

    if res_raw:
        try:
            rd = json.loads(res_raw)
            results = rd.get("results", [])
            # Winner (plc=1)
            winner = next((x for x in results if x.get("plc") == "1"), None)
            if winner:
                actual_no = winner.get("horse_no", "?")
                actual_name = re.sub(r'\(.*?\)', '', winner.get("horse", "?")).strip()[:24]
                time_str = winner.get("finish_time", "?")
            # Find where our pick finished
            if pred_no != "?":
                our = next((x for x in results if x.get("horse_no") == pred_no), None)
                if our:
                    pred_finish = f"#{our.get('plc','?')}"
        except (json.JSONDecodeError, KeyError, AttributeError): pass

    total += 1
    hit = (pred_no != "?" and actual_no != "?" and pred_no == actual_no)
    if hit: hits += 1
    near = (pred_finish in ["#2", "#3"]) and not hit
    if near: near_misses += 1

    icon = "⭐" if is_best else "  "
    result = "✅ WIN" if hit else (f"🔵 {pred_finish}" if pred_finish not in ["?","#1"] else ("❌" if pred_no != "?" else "  —"))
    print(f"{icon} R{r:<3} #{pred_no:<3} {pred_horse:<24} {edge_str:>8}  #{actual_no:<3} {actual_name:<24} {time_str:<9} {result}")

    if is_best:
        best_bets.append({"r": r, "pred_no": pred_no, "horse": pred_horse,
                          "finish": pred_finish, "winner": actual_name, "hit": hit})

print("-" * 88)
print(f"\nAll tips:  {hits}/{total} wins  ({near_misses} placed 2nd/3rd)")
print(f"\n=== ⭐ BEST BETS ===")
for b in best_bets:
    icon = "✅" if b["hit"] else "❌"
    fin = b["finish"] if b["finish"] != "?" else "unplaced"
    print(f"  {icon} R{b['r']} #{b['pred_no']} {b['horse']:<26} → finished {fin}  (won: {b['winner']})")
