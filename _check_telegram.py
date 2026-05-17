import sys
sys.stdout.reconfigure(encoding='utf-8')

from services.memory_service import memory_service
from datetime import datetime
import pytz

HKT = pytz.timezone('Asia/Hong_Kong')
now = datetime.now(HKT)
print(f"HKT: {now.strftime('%H:%M:%S')}")

# Check war room log for any verdict activity
print("\n=== Verdict/Telegram activity in war room log ===")
args = ["bash", "-c", "grep -i 'verdict\\|FINAL\\|NO BET\\|best_bet\\|CONFIRMED\\|Telegram\\|send_message' /root/ultimate_engine/warroom_start.log 2>/dev/null"]
result = memory_service._execute_ssh(args)
print(result if result.strip() else "(no verdict activity yet)")

# Check scheduler state
print("\n=== Scheduler state ===")
args = ["cat", "/root/ultimate_engine/data/scheduler_state.json"]
result = memory_service._execute_ssh(args)
print(result)

# Check final_predictions.log
print("\n=== Last 20 lines of final_predictions.log ===")
args = ["bash", "-c", "tail -20 /root/ultimate_engine/final_predictions.log 2>/dev/null"]
result = memory_service._execute_ssh(args)
print(result if result.strip() else "(empty or not found)")

# Check all prediction files for R5 and R6 (most recent races)
for r in [5, 6]:
    print(f"\n=== R{r} prediction summary ===")
    args = ["bash", "-c", f"cat /root/ultimate_engine/data/predictions/prediction_2026-05-17_ST_R{r}.json 2>/dev/null"]
    result = memory_service._execute_ssh(args)
    if result.strip():
        import json
        try:
            pred = json.loads(result)
            print(f"  is_best_bet: {pred.get('is_best_bet')}")
            print(f"  confidence_score: {pred.get('confidence_score')}")
            print(f"  wet_track: {pred.get('wet_track')}")
            print(f"  recommended_bet: {pred.get('recommended_bet')}")
            probs = pred.get('probabilities', {})
            if probs:
                top = max(probs, key=probs.get)
                print(f"  top horse: #{top} prob={probs[top]:.1%}")
        except json.JSONDecodeError:
            print(f"  (parse error)")
    else:
        print("  (file not found)")

# Check for R5 verdict specifically (jumped at 15:10)
print("\n=== R5 specific lines from war room log ===")
args = ["bash", "-c", "grep 'R5' /root/ultimate_engine/warroom_start.log 2>/dev/null"]
result = memory_service._execute_ssh(args)
print(result if result.strip() else "(no R5 lines)")
