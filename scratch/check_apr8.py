import json, re, sys
from pathlib import Path

BASE = Path('C:/Users/ASUS/ultimate_engine/data')

print('=== APR 8 HV: Predictions vs Results ===')
print()
for r in range(1, 10):
    pf = BASE / 'predictions' / f'prediction_2026-04-08_HV_R{r}.json'
    rf = BASE / 'results'     / f'results_2026-04-08_HV_R{r}.json'
    if not pf.exists() or not rf.exists():
        continue

    pred = json.loads(pf.read_text())
    res  = json.loads(rf.read_text())

    probs = pred.get('probabilities', {})
    top_pick = max(probs, key=lambda k: probs[k]) if probs else '?'

    winner = '?'
    divs = res.get('dividends', {})
    win_divs = divs.get('WIN', [])
    if win_divs:
        entry = win_divs[0]
        if isinstance(entry, str):
            m = re.search(r'combination=(\d+)', entry)
            if m: winner = m.group(1)
        elif isinstance(entry, dict):
            winner = str(entry.get('combination', '?'))

    winner_name = '?'
    winner_odds = '?'
    for h in res.get('horses', []):
        if str(h.get('horse_no','')) == winner:
            winner_name = h.get('horse', h.get('horse_name','?'))[:20]
            winner_odds = h.get('win_odds', '?')
            break

    hit = 'HIT' if top_pick == winner else 'MISS'
    print(f'R{r}: ML_top=#{top_pick}  actual_winner=#{winner} {winner_name}  odds={winner_odds}  [{hit}]')
