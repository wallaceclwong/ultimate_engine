import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))
from predict_today import predict_race

print('--- Starting Feature Capture: 2026-04-01 (ST) ---')
for r in range(1, 11):
    print(f'R{r}... ', end='', flush=True)
    try:
        predict_race('2026-04-01', 'ST', r)
        print('OK')
    except Exception as e:
        print(f'FAILED: {e}')
print('--- Capture Complete ---')
