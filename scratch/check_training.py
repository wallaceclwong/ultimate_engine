import pandas as pd, json
from pathlib import Path

BASE = Path('C:/Users/ASUS/ultimate_engine')

# Check training matrix for Apr 8 data
td = pd.read_parquet(BASE / 'training_data.parquet')
print(f'training_data.parquet  total rows: {len(td)}')
print(f'  date column dtype: {td["date"].dtype}')

# Find Apr 8
mask = td['date'].astype(str).str.contains('2026-04-08', na=False)
mask2 = td['race_id'].astype(str).str.contains('20260408', na=False) if 'race_id' in td.columns else mask
apr8 = td[mask | mask2]
print(f'  Apr 8 rows in training_data: {len(apr8)}')

# Check final matrix
fm = pd.read_parquet(BASE / 'final_feature_matrix.parquet')
print(f'\nfinal_feature_matrix.parquet total rows: {len(fm)}')
mask_fm = fm['date'].astype(str).str.contains('2026-04-08', na=False)
mask_fm2 = fm['race_id'].astype(str).str.contains('20260408', na=False) if 'race_id' in fm.columns else mask_fm
apr8_fm = fm[mask_fm | mask_fm2]
print(f'  Apr 8 rows in final_matrix: {len(apr8_fm)}')
if len(apr8_fm) > 0:
    cols = [c for c in ['race_id','date','horse_no','won'] if c in apr8_fm.columns]
    print(apr8_fm[cols].head(10).to_string())

# Model meta
meta = json.loads((BASE / 'models/model_meta.json').read_text())
print(f'\nmodel_meta.json keys: {list(meta.keys())}')
for k,v in meta.items():
    print(f'  {k}: {v}')
