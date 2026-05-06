import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services.memory_service import MemoryService

m = MemoryService()

print("\n--- Check results files ---")
out = m._execute_cmd("ls /root/ultimate_engine/data/results/ | grep 20260506 | head -20")
print(out if out else "(no results yet)")

print("\n--- Check prediction files ---")
out = m._execute_cmd("ls /root/ultimate_engine/data/predictions/ | grep 2026-05-06 | head -20")
print(out if out else "(no predictions)")

print("\n--- Read all predictions (top pick per race) ---")
script = """
import json, os
from pathlib import Path

data_dir = Path('/root/ultimate_engine/data')
pred_dir = data_dir / 'predictions'
res_dir = data_dir / 'results'

rows = []
for r in range(1, 12):
    pf = pred_dir / f'prediction_2026-05-06_ST_R{r}.json'
    if not pf.exists():
        continue
    with open(pf) as f:
        p = json.load(f)
    
    probs = p.get('probabilities', {})
    if not probs:
        continue
    top_horse = max(probs, key=probs.get)
    
    # Get Kelly picks
    kelly = p.get('kelly_picks', [])
    bet_horse = kelly[0]['horse'] if kelly else top_horse
    bet_odds = kelly[0].get('odds', '?') if kelly else '?'
    edge = kelly[0].get('edge_pct', '?') if kelly else '?'
    
    # Check result
    result = None
    rf = res_dir / f'results_2026-05-06_ST_R{r}.json'
    if rf.exists():
        with open(rf) as f:
            rd = json.load(f)
        winner = None
        for h in rd.get('horses', []):
            if h.get('finish_position') == 1 or h.get('position') == 1:
                winner = str(h.get('horse_no') or h.get('saddle_number','?'))
                break
        result = winner
    
    hit = '✅' if result and str(bet_horse) == str(result) else ('❌' if result else '⏳')
    rows.append((r, bet_horse, bet_odds, edge, result or '?', hit))

print('R | Tip | Odds | Edge | Winner | Hit')
print('-' * 45)
for r, h, o, e, w, hit in rows:
    edge_str = f'+{e:.1f}%' if isinstance(e, float) else str(e)
    print(f'R{r} | #{h} | {o} | {edge_str} | #{w} | {hit}')
"""
m._execute_cmd("cat > /tmp/results_table.py << 'EOF'\n" + script + "\nEOF")
out = m._execute_cmd("/root/ultimate_engine/.venv/bin/python /tmp/results_table.py 2>&1")
print(out if out else "(no output)")
