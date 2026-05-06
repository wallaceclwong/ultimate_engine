import sys, json
sys.argv = ['predict_today.py', '2026-04-29', 'HV']
import predict_today as pt

for r in [1, 2, 3]:
    df = pt.predict_race('2026-04-29', 'HV', r)
    if df is None:
        continue
    top = df.iloc[0]
    pred_file = pt.DATA_DIR / 'predictions' / f'prediction_2026-04-29_HV_R{r}.json'
    data = json.loads(pred_file.read_text())
    edge = data['confidence_score']
    bet  = data['recommended_bet']
    ib   = data['is_best_bet']
    print(f"R{r}: #{int(top['horse_no'])} {top['horse_name']} "
          f"| odds={top['win_odds']:.1f} | fair={top['fair_odds']:.1f} "
          f"| edge={edge:+.3f} | is_best_bet={ib} | bet={bet}")
