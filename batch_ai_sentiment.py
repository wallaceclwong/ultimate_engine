import os
import json
import asyncio
import pandas as pd
from pathlib import Path
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()
client = AsyncOpenAI(api_key=os.getenv('DEEPSEEK_API_KEY'), base_url='https://api.deepseek.com')

BASE_DIR = Path('/root/ultimate_engine')
DATA_DIR = Path('/root/data')
RESULTS_DIR = DATA_DIR / 'results'
CACHE_PATH = DATA_DIR / 'ai_sentiment_cache.parquet'

async def get_ai_score(race_id, report):
    if not report or len(report) < 10: return []
    try:
        resp = await client.chat.completions.create(
            model='deepseek-chat',
            messages=[
                {'role': 'system', 'content': 'You are a master HKJC analyst. Rate the "Bad Luck" level of runners (1-10) based on stewards reports. Return a JSON object mapping horse_no to ai_unlucky_score.'},
                {'role': 'user', 'content': f'Race: {race_id}\nReport: {report}'}
            ],
            response_format={'type': 'json_object'},
            timeout=30
        )
        scores = json.loads(resp.choices[0].message.content)
        return [{'race_id': race_id, 'horse_no': hno, 'ai_unlucky_score': float(sc)} for hno, sc in scores.items()]
    except Exception as e:
        print(f"Error fetching score for {race_id}: {e}")
        return []

async def process_batch(tasks):
    all_results = []
    # Process in chunks of 50 for speed (DeepSeek-V3 is fast)
    batch_size = 50
    for i in range(0, len(tasks), batch_size):
        chunk = tasks[i:i+batch_size]
        print(f'  Processing Chunk {i//batch_size + 1}/{(len(tasks)//batch_size)+1}...')
        batch_res = await asyncio.gather(*[get_ai_score(rid, rep) for rid, rep in chunk])
        
        for res in batch_res:
            if isinstance(res, list): all_results.extend(res)
        
        # Incremental Save
        if all_results:
            new_df = pd.DataFrame(all_results)
            if CACHE_PATH.exists():
                old_df = pd.read_parquet(CACHE_PATH)
                final_df = pd.concat([old_df, new_df]).drop_duplicates(['race_id', 'horse_no'])
                final_df.to_parquet(CACHE_PATH, index=False)
            else:
                new_df.to_parquet(CACHE_PATH, index=False)
            all_results = []
        await asyncio.sleep(0.3)

async def run_batch():
    print('Starting DeepSeek Sync (Incremental)...')
    existing_ids = set()
    if CACHE_PATH.exists():
        existing_ids = set(pd.read_parquet(CACHE_PATH)['race_id'].astype(str).unique())
    
    all_files = list(RESULTS_DIR.glob('results_*.json'))
    tasks = []
    for f in all_files:
        rid = f.stem.replace('results_', '')
        if rid not in existing_ids:
            try:
                with open(f, 'r', encoding='utf-8') as j:
                    data = json.load(j)
                    tasks.append((rid, data.get('stewards_report', '')))
            except: continue
            
    if not tasks:
        print('No missing races found. Coverage is 100%.')
        return
        
    print(f'Gap found: {len(tasks)} races missing from cache. Starting analysis...')
    await process_batch(tasks)
    print('DeepSeek Sync Complete.')

if __name__ == '__main__':
    asyncio.run(run_batch())
