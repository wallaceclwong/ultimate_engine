import json, glob, os, sys

sys.stdout.reconfigure(encoding='utf-8')

files = sorted(glob.glob('data/predictions/prediction_2026-04-15_HV_R*.json'))
print(f'== 2026-04-15 | HV | {len(files)} Races ==\n')
for f in files:
    d = json.load(open(f, encoding='utf-8'))
    race = os.path.basename(f).replace('prediction_2026-04-15_HV_','').replace('.json','')
    conf = d.get('confidence_score', '?')
    best = d.get('is_best_bet', False)
    probs = d.get('probabilities', {})
    top3 = sorted(probs.items(), key=lambda x: x[1], reverse=True)[:3]
    top3_str = ', '.join([f'{h} ({p:.0%})' for h,p in top3]) if top3 else '--'
    kelly = d.get('kelly_stakes', {})
    stake_total = sum(kelly.values()) if kelly else 0
    flag = ' [BEST BET]' if best else ''
    print(f'  {race} | conf={conf}{flag}')
    print(f'       Top: {top3_str}')
    if stake_total > 0:
        print(f'       Kelly: {dict(list(kelly.items())[:3])}')
    print()
