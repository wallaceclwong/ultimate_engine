import json
from pathlib import Path

pred_dir = Path("data/predictions")
data_dir = Path("data")

files = sorted(pred_dir.glob("prediction_2026-05-03_*.json"))
print(f"Found {len(files)} prediction files for 2026-05-03 ST\n")

header = f"{'Race':<5} {'#':<4} {'Horse':<24} {'Prob':>6} {'Odds':>7} {'Kelly':>9} {'Best?':<6} {'Conf':>6}"
print(header)
print("-" * 70)

for f in sorted(files, key=lambda x: int(str(x).split("_R")[-1].replace(".json", ""))):
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
        race_no = str(f).split("_R")[-1].replace(".json", "")
        probs  = d.get("probabilities", {})
        kelly  = d.get("kelly_stakes", {})
        odds   = d.get("market_odds", {})
        conf   = d.get("confidence_score", 0)
        best   = "BET" if d.get("is_best_bet") else ""

        if not probs:
            print(f"R{race_no:<4} (no probabilities)")
            continue

        top_h = max(probs, key=probs.get)
        top_p = probs[top_h]
        top_o = odds.get(top_h, "?")
        top_k = kelly.get(top_h, 0)

        # Lookup horse name from racecard
        horse_name = f"#{top_h}"
        rc_files = sorted(data_dir.glob(f"racecard_20260503_R{race_no}.json"))
        if rc_files:
            rc = json.loads(rc_files[0].read_text(encoding="utf-8"))
            for h in rc.get("horses", []):
                if str(h.get("saddle_number", "")) == str(top_h):
                    horse_name = h.get("horse_name", horse_name)[:23]
                    break

        odds_str = f"{top_o:.1f}" if isinstance(top_o, (int, float)) else str(top_o)
        kelly_str = f"HK${top_k:.0f}" if top_k else "  -"
        print(f"R{race_no:<4} #{top_h:<3} {horse_name:<24} {top_p:>5.1%} {odds_str:>7} {kelly_str:>9} {best:<6} {conf:>5.0%}")

    except Exception as e:
        print(f"  R{str(f).split('_R')[-1].replace('.json','')}: ERROR {e}")

# Summary
print("\n--- BETS TODAY ---")
bets = []
for f in sorted(files, key=lambda x: int(str(x).split("_R")[-1].replace(".json", ""))):
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
        if not d.get("is_best_bet"):
            continue
        race_no = str(f).split("_R")[-1].replace(".json", "")
        kelly   = d.get("kelly_stakes", {})
        odds    = d.get("market_odds", {})
        probs   = d.get("probabilities", {})
        top_h   = max(kelly, key=kelly.get)
        horse_name = f"#{top_h}"
        rc_files = sorted(data_dir.glob(f"racecard_20260503_R{race_no}.json"))
        if rc_files:
            rc = json.loads(rc_files[0].read_text(encoding="utf-8"))
            for h in rc.get("horses", []):
                if str(h.get("saddle_number", "")) == str(top_h):
                    horse_name = h.get("horse_name", horse_name)
                    break
        stake = kelly[top_h]
        top_o = odds.get(top_h, "?")
        bets.append((race_no, top_h, horse_name, stake, top_o))
    except:
        pass

if bets:
    for r, h, name, stake, o in bets:
        print(f"  R{r}: WIN #{h} {name} @ {o} — stake HK${stake:.0f}")
else:
    print("  No is_best_bet races flagged yet (re-run after 09:30 odds refresh).")
