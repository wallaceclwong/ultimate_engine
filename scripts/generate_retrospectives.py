import sys
import os
import json
import pandas as pd
from pathlib import Path
from datetime import datetime
import asyncio
from openai import AsyncOpenAI
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PROCESSED_DIR = DATA_DIR / "processed"
RESULTS_DIR = DATA_DIR / "results"
NARR_DIR = DATA_DIR / "narratives"
DOTENV_FILE = BASE_DIR / ".env"

load_dotenv(DOTENV_FILE)
client = AsyncOpenAI(api_key=os.getenv('DEEPSEEK_API_KEY'), base_url='https://api.deepseek.com')

async def analyze_failure(row, results_meta):
    """Asks DeepSeek why the model failed on this horse."""
    prompt = f"""
Act as a professional horse racing analyst reviewing a failed prediction.
Our system predicted high value (EV: {row.get('ev', 'N/A'):.2f}, Expected Win Prob: {row.get('pred_prob', 'N/A'):.2f}) for:
Horse: {row['horse_name']} (#{row['horse_no']})
Stats: Odds {row['win_odds']}, Draw {row['draw']}, Jockey: {row['jockey_win_rate']}
Track Condition: {row.get('track_condition', 'Unknown')}
But it actually finished position: {row['plc']}.

Provide a brief, 3-sentence "Lesson Learnt" focusing on tactical or track condition reasons that might explain why this statistical model failed today. Avoid generic statements, focus on the facts provided.
"""
    try:
        resp = await client.chat.completions.create(
            model="deepseek-reasoner",
            messages=[{"role": "user", "content": prompt}],
            timeout=55
        )
        # Deepseek R1 returns reasoning in the content
        content = resp.choices[0].message.content
        import re
        clean_content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
        return clean_content
    except Exception as e:
        print(f"Failed to generate retrospective for {row['horse_name']}: {e}")
        return None

async def run_retrospectives(date_str, venue):
    print(f"--- Generating Retrospectives for {date_str} ({venue}) ---")
    NARR_DIR.mkdir(exist_ok=True)
    count = 0

    for f in PROCESSED_DIR.glob(f'features_{date_str}_{venue}_R*.parquet'):
        race_no = int(f.name.split('_R')[-1].replace('.parquet', ''))
        df_feat = pd.read_parquet(f)
        
        res_file = RESULTS_DIR / f'results_{date_str}_{venue}_R{race_no}.json'
        if not res_file.exists():
            continue
            
        with open(res_file, 'r', encoding='utf-8') as rfile:
            res_data = json.load(rfile)
            results_dict = {str(r['horse_no']): r['plc'] for r in res_data['results']}
            
            df_feat['plc'] = df_feat['horse_no'].astype(str).map(results_dict)
            df_feat = df_feat[df_feat['plc'].notnull()]
            # Filter non-numeric placements
            df_feat = df_feat[df_feat['plc'].astype(str).str.isdigit()]
            df_feat['plc'] = df_feat['plc'].astype(int)
            
            # Find failures: High EV (>1.25) but finished worse than 3rd
            failures = df_feat[(df_feat['ev'] > 1.25) & (df_feat['plc'] > 3)]
            
            for _, row in failures.iterrows():
                print(f"  [AUDIT] {row['horse_name']} (EV: {row['ev']:.2f}, Plc: {row['plc']})")
                lesson = await analyze_failure(row, res_data)
                if lesson:
                    narrative = f"LESSON LEARNT RETROSPECTIVE FOR {row['horse_name']} on {date_str}:\n"
                    narrative += f"Our model highly tipped this horse but it failed (finished {row['plc']}).\n"
                    narrative += f"Analysis: {lesson}\n"
                    
                    out_path = NARR_DIR / f"retro_{date_str}_{row['horse_name'].replace(' ', '_')}.txt"
                    out_path.write_text(narrative, encoding='utf-8')
                    count += 1
                    
    print(f"Retrospectives generated: {count}")

if __name__ == "__main__":
    date = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime('%Y-%m-%d')
    venue = sys.argv[2] if len(sys.argv) > 2 else 'ST'
    asyncio.run(run_retrospectives(date, venue))
