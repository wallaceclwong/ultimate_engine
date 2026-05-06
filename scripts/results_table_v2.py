import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services.memory_service import MemoryService

m = MemoryService()

script = r"""
import json
from pathlib import Path

data_dir = Path('/root/ultimate_engine/data')
pred_dir = data_dir / 'predictions'
res_dir  = data_dir / 'results'

rows = []
for r in range(1, 12):
    pf = pred_dir / f'prediction_2026-05-06_ST_R{r}.json'
    rf = res_dir  / f'results_2026-05-06_ST_R{r}.json'
    if not pf.exists():
        continue

    with open(pf) as f:
        p = json.load(f)

    probs  = p.get('probabilities', {})
    market = p.get('market_odds', {})
    top    = max(probs, key=probs.get) if probs else '?'
    odds_v = market.get(top, '?')
    fair_v = round(1.0 / probs[top], 2) if top in probs and probs[top] > 0 else None
    edge_v = round((float(odds_v) / fair_v - 1) * 100, 1) if fair_v and odds_v != '?' else None
    edge_s = (f'+{edge_v}%' if edge_v and edge_v > 0 else f'{edge_v}%') if edge_v is not None else '?'

    winner = '?'; win_name = ''; win_odds = '?'
    if rf.exists():
        with open(rf) as f:
            rd = json.load(f)
        for h in rd.get('results', []):
            if str(h.get('plc', '')) == '1':
                winner   = str(h.get('horse_no', '?'))
                win_name = h.get('horse', '').split('\xa0')[0]
                win_odds = h.get('win_odds', '?')
                break

    hit = 'WIN ✅' if winner != '?' and str(top) == str(winner) else ('---' if winner == '?' else 'MISS ❌')
    rows.append((r, top, odds_v, edge_s, winner, win_name[:14], win_odds, hit))

print(f"{'R':<3} {'Tip':>4} {'FairOdds':>9} {'Edge':>8}  {'#Win':>4} {'Winner':<15} {'WinOdds':>8}  Result")
print('-' * 72)
wins = 0
for r, tip, odds, edge, winner, wname, wodds, hit in rows:
    if 'WIN' in hit: wins += 1
    print(f"R{r:<2} #{tip:>3}  {str(odds):>8} {edge:>8}  #{winner:<4} {wname:<15} {str(wodds):>8}  {hit}")

print('-' * 72)
total = len(rows)
print(f"WIN rate: {wins}/{total}  ({100*wins//total if total else 0}%)")
"""

m._execute_cmd("cat > /tmp/table2.py << 'PYEOF'\n" + script + "\nPYEOF")
out = m._execute_cmd("/root/ultimate_engine/.venv/bin/python /tmp/table2.py 2>&1")
print(out if out else "(no output)")
