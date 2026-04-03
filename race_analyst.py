import re
import os
import json
import pandas as pd
import numpy as np
from pathlib import Path
from openai import OpenAI
import time

# --- Paths ---
# Auto-detect VM vs Local
if Path("/opt/hkjc").exists():
    BASE_DIR     = Path("/root/ultimate_engine")
    PROJECT_ROOT = Path("/opt/hkjc")
else:
    PROJECT_ROOT = Path(r"c:\Users\ASUS\hkjc")
    BASE_DIR     = PROJECT_ROOT / "ultimate_engine"

INCIDENTS_FILE= BASE_DIR / 'incidents_data.parquet'
TRAINING_FILE = BASE_DIR / 'training_data.parquet'
CACHE_FILE    = BASE_DIR / 'ai_sentiment_cache.json'
DOTENV_FILE   = BASE_DIR / '.env'

# --- Load Environment ---
def load_key():
    if not DOTENV_FILE.exists(): return None
    with open(DOTENV_FILE, 'r') as f:
        for line in f:
            if line.startswith('DEEPSEEK_API_KEY='):
                return line.split('=')[1].strip()
    return None

api_key = load_key()
if not api_key:
    print("CRITICAL ERROR: No API Key found in .env")
    exit(1)

client = OpenAI(api_key=api_key, base_url='https://api.deepseek.com')

# --- Load Data ---
df_inc = pd.read_parquet(INCIDENTS_FILE)
df_inc['date'] = pd.to_datetime(df_inc['date'])
df_inc = df_inc.sort_values('date', ascending=False)

if CACHE_FILE.exists():
    try:
        with open(CACHE_FILE, 'r') as f:
            sentiment_cache = json.load(f)
    except:
        sentiment_cache = {}
else:
    sentiment_cache = {}

# --- AI Scoring Logic ---
def get_ai_score(horse_name, incidents):
    filtered = [inc for inc in incidents if len(str(inc).strip()) > 10 and 'no report' not in str(inc).lower()]
    if not filtered:
        return 1.0, 'No significant incidents found'

    incident_text = '\n'.join([f'- {inc}' for inc in filtered[:3]])

    prompt = f"""
    Analyze HKJC steward reports for '{horse_name}'.
    Reports:
    {incident_text}

    Score 0.8 (Poor/No excuse) to 1.2 (Extremely unlucky). 1.0 = Fair.
    Respond ONLY in JSON: {{"score": 1.XX, "reason": "Short reason"}}
    """

    try:
        # Use deepseek-chat (V3) for reliable JSON following
        response = client.chat.completions.create(
            model='deepseek-chat', 
            messages=[
                {'role': 'system', 'content': 'You are a racing data analyst. You MUST return ONLY a JSON object.'},
                {'role': 'user', 'content': prompt}
            ],
            response_format={'type': 'json_object'},
            max_tokens=300
        )
        data = json.loads(response.choices[0].message.content)
        return float(data.get('score', 1.0)), data.get('reason', 'N/A')
    except Exception as e:
        return 1.0, f'API Error: {str(e)}'

# --- Main Processing ---
def process(year=2025, max_calls=150):
    print(f'\n--- AI Analyst (V5: DeepSeek-V3 JSON Mode) ---')
    
    df_train = pd.read_parquet(TRAINING_FILE)
    df_train['date'] = pd.to_datetime(df_train['date'])
    target_horses = df_train[df_train['date'].dt.year >= year]['horse_name'].unique()
    target_horses = [h for h in target_horses if h and str(h).strip()]
    
    df_inc['horse_name_clean'] = df_inc['horse_name'].str.strip().str.upper()
    processed = 0
    new_scores = 0

    print(f"Total Target Horses: {len(target_horses)}")

    for horse in target_horses:
        horse_key = str(horse).strip().upper()
        
        # FIX: Check if we should skip
        if horse_key in sentiment_cache:
            entry = sentiment_cache[horse_key]
            reason = entry.get('reason', '')
            score = entry.get('score', 1.0)
            
            # Skip if successful analysis exists
            # (If it has a real score != 1.0, it was definitely successful)
            if score != 1.0:
                processed += 1
                continue
            
            # If it's 1.0 but "No significant incidents" or "No historical incidents", skip
            if 'significant incidents' in reason or 'historical incidents' in reason:
                processed += 1
                continue
                
            # If we're here, it's 1.0 but might be a "No JSON" or "API Error" attempt.
            # Only skip if it's NOT a failure reason.
            if 'JSON' not in reason and 'Error' not in reason and 'API Error' not in reason:
                processed += 1
                continue
            
            # Otherwise, we RE-ANALYZE this failure.
            pass

        horse_incidents = df_inc[df_inc['horse_name_clean'] == horse_key]['incident'].tolist()
        valid = [str(i).strip() for i in horse_incidents if i and len(str(i).strip()) > 5]
        
        if not valid:
            sentiment_cache[horse_key] = {'score': 1.0, 'reason': 'No historical incidents found', 'updated': str(pd.Timestamp.now())}
            processed += 1
            continue
        
        # --- CALL THE AI ---
        print(f'  >> ({new_scores+1}/{max_calls}) Analyzing {horse_key} ({len(valid)} runs)...')
        score, reason = get_ai_score(horse_key, valid)
        sentiment_cache[horse_key] = {'score': score, 'reason': reason, 'updated': str(pd.Timestamp.now())}
        
        new_scores += 1
        processed += 1

        if new_scores >= max_calls: break
        if new_scores % 5 == 0:
            with open(CACHE_FILE, 'w') as f:
                json.dump(sentiment_cache, f, indent=2)
            time.sleep(0.5)

    with open(CACHE_FILE, 'w') as f:
        json.dump(sentiment_cache, f, indent=2)
    print(f'\n--- DONE ---')
    print(f'Added {new_scores} new scores. Total: {len(sentiment_cache)}')

if __name__ == '__main__':
    process(year=2025, max_calls=2000)
