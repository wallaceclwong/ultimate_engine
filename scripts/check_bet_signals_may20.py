import paramiko
import json

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('100.109.76.69', username='root', password='6{tJs[Dhe,jv3@_G', timeout=20)

print("=== MAY 20 BET SIGNAL ANALYSIS ===\n")

# Check which version of predict_today.py is running
stdin, stdout, stderr = ssh.exec_command('grep -n "TEMPERATURE\\|MARKET_BLEND\\|prob_gap\\|edge_threshold" /root/ultimate_engine/predict_today.py', timeout=15)
print("Code version check:")
print(stdout.read().decode())

# Check each prediction file
for race_num in range(1, 10):
    stdin, stdout, stderr = ssh.exec_command(f'cat /root/ultimate_engine/data/predictions/prediction_2026-05-20_HV_R{race_num}.json 2>/dev/null', timeout=15)
    pred_out = stdout.read().decode()
    if not pred_out:
        continue
    
    pred = json.loads(pred_out)
    
    is_best = pred.get('is_best_bet', False)
    rec_bet = pred.get('recommended_bet', 'N/A')
    confidence = pred.get('confidence_score', 0)
    model = pred.get('model_name') or pred.get('gemini_model', 'N/A')
    market_odds = pred.get('market_odds', {})
    probs = pred.get('probabilities', {})
    
    # Top pick
    if probs:
        top_pick = max(probs, key=probs.get)
        top_prob = probs[top_pick]
        sorted_p = sorted(probs.values(), reverse=True)
        prob_gap = sorted_p[0] - sorted_p[1] if len(sorted_p) >= 2 else 0
        top_odds = market_odds.get(top_pick, 'N/A')
    else:
        top_pick = "?"
        top_prob = 0
        prob_gap = 0
        top_odds = "?"
    
    print(f"R{race_num}: is_best_bet={is_best} | rec={rec_bet}")
    print(f"  model={model} | conf={confidence:.4f} | top=#{top_pick} ({top_prob*100:.1f}%) @{top_odds} | gap={prob_gap*100:.1f}pp")

ssh.close()
