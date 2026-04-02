import sys
import os
import json
import pandas as pd
from pathlib import Path
from datetime import datetime

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

# Constants
PROCESSED_DIR = Path('/root/data/processed')
RESULTS_DIR = DATA_DIR = Path('/root/data/results')
MATRIX_FILE = Path('/root/ultimate_engine/training_data_hybrid.parquet')

def update_learning(date_str, venue):
    print(f'--- Starting Learning Logic: {date_str} ({venue}) ---')
    
    if not MATRIX_FILE.exists():
        print(f'  [ERROR] Matrix not found at {MATRIX_FILE}')
        return
        
    master_df = pd.read_parquet(MATRIX_FILE)
    print(f'  Loaded master matrix with {len(master_df)} rows.')
    
    new_rows = []
    
    # 1. Process each feature file for the date
    for f in PROCESSED_DIR.glob(f'features_{date_str}_{venue}_R*.parquet'):
        race_no = int(f.name.split('_R')[-1].replace('.parquet', ''))
        df_feat = pd.read_parquet(f)
        
        # 2. Find matching results file
        res_file = RESULTS_DIR / f'results_{date_str}_{venue}_R{race_no}.json'
        if not res_file.exists():
            print(f'  [SKIP] R{race_no}: Results file missing at {res_file.name}')
            continue
            
        with open(res_file, 'r') as rfile:
            res_data = json.load(rfile)
            
            # 3. Join PLC to features
            results_dict = {str(r['horse_no']): r['plc'] for r in res_data['results']}
            
            # Map placements
            df_feat['plc'] = df_feat['horse_no'].map(results_dict)
            
            # Clean PLC: keep only digits
            df_feat = df_feat[df_feat['plc'].notnull()]
            df_feat = df_feat[df_feat['plc'].str.isdigit()]
            df_feat['plc'] = df_feat['plc'].astype(int)
            
            # Add is_win, is_place
            df_feat['is_win'] = (df_feat['plc'] == 1).astype(int)
            df_feat['is_place'] = (df_feat['plc'] <= 3).astype(int)
            
            print(f'  [R{race_no}] Labeled {len(df_feat)} runners.')
            new_rows.append(df_feat)
            
    if new_rows:
        df_new = pd.concat(new_rows)
        # 4. Append to Master Matrix
        # Ensure columns match (drop any prediction-only columns like 'rank' or 'prob')
        common_cols = [c for c in master_df.columns if c in df_new.columns]
        df_final = pd.concat([master_df, df_new[common_cols]], ignore_index=True)
        
        df_final.to_parquet(MATRIX_FILE)
        print(f'  [SUCCESS] Appended {len(df_new)} labeled rows to {MATRIX_FILE.name}')
        print(f'  New matrix size: {len(df_final)} rows.')
    else:
        print('  [FAILED] No new rows were labeled.')

if __name__ == '__main__':
    date = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime('%Y-%m-%d')
    venue = sys.argv[2] if len(sys.argv) > 2 else 'ST'
    update_learning(date, venue)
