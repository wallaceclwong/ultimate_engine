
import json
from pathlib import Path

BASE = Path('C:/Users/ASUS/ultimate_engine/data')
pred_dir = BASE / 'predictions'
res_dir  = BASE / 'results'

meetings = {}
total_races = 0
hits = 0
top3_hits = 0
high_conf_hits = 0
high_conf_total = 0
longshot_hits = 0   # winner had odds > 20 and model still had it in top3

def get_winner(res):
    """Extract winner horse_no from results file."""
    # Try dividends WIN field
    divs = res.get('dividends', {})
    win_divs = divs.get('WIN', [])
    if win_divs:
        entry = win_divs[0]
        if isinstance(entry, dict):
            return str(entry.get('combination', ''))
        elif isinstance(entry, str):
            # parse "@{combination=12; dividend=...}"
            import re
            m = re.search(r'combination=(\d+)', entry)
            if m:
                return m.group(1)
    # Try horses list
    for h in res.get('horses', []):
        plc = str(h.get('plc', h.get('finishing_position', h.get('place', ''))))
        if plc == '1':
            return str(h.get('horse_no', h.get('number', '')))
    return ''

def get_winner_odds(res, winner_no):
    """Get the actual win odds of the winner."""
    for h in res.get('horses', []):
        if str(h.get('horse_no', '')) == str(winner_no):
            try:
                return float(h.get('win_odds', 0)) / 10.0
            except (ValueError, TypeError):
                return 0.0
    return 0.0

race_details = []

for pf in sorted(pred_dir.glob('prediction_2026-04-*.json')):
    parts = pf.stem.split('_')
    date_str = parts[1]
    venue    = parts[2]
    race_key = parts[3]
    r_no     = int(race_key[1:])

    try:
        pred = json.loads(pf.read_text())
    except json.JSONDecodeError:
        continue

    # Skip placeholder-odds races (Apr 26+: all horses at 10.0)
    mo = pred.get('market_odds', {})
    if not mo or (len(set(mo.values())) == 1 and list(mo.values())[0] == 10.0):
        continue

    rf = res_dir / f'results_{date_str}_{venue}_{race_key}.json'
    if not rf.exists():
        continue

    try:
        res = json.loads(rf.read_text())
    except json.JSONDecodeError:
        continue

    actual_winner = get_winner(res)
    if not actual_winner:
        continue

    winner_odds = get_winner_odds(res, actual_winner)

    probs = pred.get('probabilities', {})
    if not probs:
        continue

    sorted_picks = sorted(probs.items(), key=lambda x: float(x[1]), reverse=True)
    top1 = sorted_picks[0][0]
    top3 = [p[0] for p in sorted_picks[:3]]
    conf  = float(sorted_picks[0][1])

    # Value: our top pick's market odds vs fair odds
    top1_market_odds = float(mo.get(str(top1), 0))
    top1_fair_prob   = float(probs.get(str(top1), 0))
    top1_fair_odds   = (1.0 / top1_fair_prob) if top1_fair_prob > 0 else 99
    is_value = top1_market_odds > 0 and top1_market_odds > top1_fair_odds

    won_top1 = str(top1) == str(actual_winner)
    in_top3  = str(actual_winner) in [str(x) for x in top3]

    total_races += 1
    if won_top1:
        hits += 1
    if in_top3:
        top3_hits += 1
    if conf > 0.12:
        high_conf_total += 1
        if won_top1:
            high_conf_hits += 1
    if winner_odds > 20:
        longshot_hits += 1

    mk = f'{date_str}_{venue}'
    if mk not in meetings:
        meetings[mk] = {'total':0,'hits':0,'top3':0,'value_hits':0,'value_total':0}
    meetings[mk]['total'] += 1
    if won_top1:
        meetings[mk]['hits'] += 1
    if in_top3:
        meetings[mk]['top3'] += 1
    if is_value:
        meetings[mk]['value_total'] += 1
        if won_top1:
            meetings[mk]['value_hits'] += 1

    race_details.append({
        'race': f'{date_str}_{venue}_{race_key}',
        'top1': top1, 'winner': actual_winner,
        'conf': conf, 'winner_odds': winner_odds,
        'won': won_top1, 'in_top3': in_top3,
        'is_value': is_value
    })

print("=== PREDICTION PERFORMANCE REVIEW (Apr 6 - Apr 22, real odds only) ===")
print()
print(f"Meetings with real odds : {len(meetings)}")
print(f"Races analysed          : {total_races}")
print()
print("--- TOP-1 WIN ACCURACY ---")
r1 = hits/total_races if total_races else 0
print(f"  Hits : {hits}/{total_races}  ({r1*100:.1f}%)")
print(f"  Baseline (1/avg_field) ≈ ~8-9%  (avg field ~12 runners)")
print()
print("--- TOP-3 COVERAGE ---")
r3 = top3_hits/total_races if total_races else 0
print(f"  Hits : {top3_hits}/{total_races}  ({r3*100:.1f}%)")
print(f"  Baseline (3/avg_field) ≈ ~25%")
print()
print("--- HIGH CONFIDENCE (conf > 0.12) ---")
if high_conf_total > 0:
    print(f"  Hits : {high_conf_hits}/{high_conf_total}  ({high_conf_hits/high_conf_total*100:.1f}%)")
else:
    print("  No high-conf races found.")
print()
print(f"--- LONGSHOT POLLUTION (winner odds > 20) ---")
print(f"  Longshot winners : {longshot_hits}/{total_races}  ({longshot_hits/total_races*100:.1f}%)")
print(f"  (Races model is least likely to predict correctly)")
print()
print("--- BY MEETING ---")
print(f"  {'Meeting':<28} {'Races':>5} {'Win':>8} {'Top3':>8} {'Value':>8}")
print("  " + "-"*62)
for k in sorted(meetings):
    v = meetings[k]
    wr = v['hits']/v['total']*100 if v['total'] else 0
    t3 = v['top3']/v['total']*100 if v['total'] else 0
    val = f"{v['value_hits']}/{v['value_total']}" if v['value_total'] else '-'
    print(f"  {k:<28} {v['total']:>5} {v['hits']}/{v['total']} ({wr:>3.0f}%) {v['top3']}/{v['total']} ({t3:>3.0f}%)  val={val}")

print()
print("--- NOTABLE MISSES (model confident, wrong) ---")
for d in race_details:
    if d['conf'] > 0.10 and not d['won']:
        print(f"  {d['race']:30s}  top1=#{d['top1']} (conf={d['conf']:.2f})  actual=#{d['winner']} (odds={d['winner_odds']:.1f})")
