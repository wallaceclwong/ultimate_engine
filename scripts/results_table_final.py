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

    probs      = p.get('probabilities', {})
    market     = p.get('market_odds', {})
    kelly      = p.get('kelly_stakes', {})
    rec        = str(p.get('recommended_bet', '') or '')

    # Top model pick
    top = max(probs, key=probs.get) if probs else '?'
    odds_val = market.get(top, '?')
    fair_val = round(1.0 / probs[top], 2) if top in probs and probs[top] > 0 else '?'
    edge_val = round((float(odds_val) / float(fair_val) - 1) * 100, 1) if odds_val != '?' and fair_val != '?' else '?'
    edge_str = f'+{edge_val}%' if isinstance(edge_val, float) and edge_val > 0 else (f'{edge_val}%' if isinstance(edge_val, float) else '?')

    # Winner from results
    winner = '?'
    win_name = ''
    if rf.exists():
        with open(rf) as f:
            rd = json.load(f)
        for h in rd.get('horses', []):
            pos = h.get('finish_position') or h.get('position') or h.get('placing')
            if str(pos) == '1':
                winner = str(h.get('horse_no') or h.get('saddle_number', '?'))
                win_name = h.get('horse_name', '') or h.get('horse', '')
                break

    hit = 'WIN' if winner != '?' and str(top) == str(winner) else ('---' if winner == '?' else 'MISS')
    rows.append((r, top, odds_val, edge_str, winner, win_name[:15], hit))

print(f"{'R':<3} {'Tip':>4} {'Odds':>6} {'Edge':>8}   {'Winner':>4} {'Horse':<16} {'Result'}")
print('-' * 58)
wins = sum(1 for row in rows if row[6] == 'WIN')
for r, tip, odds, edge, winner, wname, hit in rows:
    marker = '<< WIN' if hit == 'WIN' else ''
    print(f"R{r:<2} #{tip:>3} {str(odds):>6} {edge:>8}   #{winner:<4} {wname:<16} {hit} {marker}")

print('-' * 58)
print(f"WIN rate: {wins}/{len(rows)} races ({100*wins//len(rows) if rows else 0}%)")
"""

m._execute_cmd("cat > /tmp/table.py << 'PYEOF'\n" + script + "\nPYEOF")
out = m._execute_cmd("/root/ultimate_engine/.venv/bin/python /tmp/table.py 2>&1")
print(out if out else "(no output)")
