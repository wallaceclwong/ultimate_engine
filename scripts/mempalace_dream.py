import sys
import os
import asyncio
from pathlib import Path
from datetime import datetime
from openai import AsyncOpenAI
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
NARR_DIR = DATA_DIR / "narratives"
DOTENV_FILE = BASE_DIR / ".env"

load_dotenv(DOTENV_FILE)
client = AsyncOpenAI(api_key=os.getenv('DEEPSEEK_API_KEY'), base_url='https://api.deepseek.com')

async def generate_golden_rule(retrospectives):
    """Asks DeepSeek to synthesize a golden rule from failed retrospectives."""
    retrospectives_str = '\n- '.join(retrospectives)
    prompt = f"""
Act as a Master Strategist for Hong Kong Horse Racing.
I am providing you with multiple "Lesson Learnt" failure reports from our statistical model. 
These are situations where our model was highly confident, but visually/tactically failed.

Reports:
- {retrospectives_str}

Synthesize these failures into a single, highly concentrated "GOLDEN RULE META-STRATEGY". 
Do not restate the individual horse names. Look for underlying macro trends (e.g. "Avoid inside barriers for fast starters on yielding tracks").
Output 3-5 sentences maximum.
"""
    try:
        resp = await client.chat.completions.create(
            model="deepseek-reasoner",
            messages=[{"role": "user", "content": prompt}],
            timeout=120
        )
        content = resp.choices[0].message.content
        import re
        clean_content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
        return clean_content
    except Exception as e:
        print(f"Failed to generate dream rule: {e}")
        return None

async def run_dream_state():
    print("============================================================")
    print(" LUNAR LEAP - MEMPALACE DREAM STATE OPTIMIZATION ")
    print("============================================================")
    
    if not NARR_DIR.exists():
        print("No narratives directory found.")
        return

    # Gather all individual failure retrospectives
    retro_files = list(NARR_DIR.glob("retro_*.txt"))
    if not retro_files:
        print("No failure retrospectives to synthesize today. Sleeping.")
        return

    print(f"Found {len(retro_files)} failure chunks to synthesize in Dream State...")
    summaries = []
    
    # Read the contents
    for f in retro_files:
        try:
            summaries.append(f.read_text(encoding='utf-8').strip())
        except Exception as e:
            print(f"Error reading {f.name}: {e}")

    # Process in batches to avoid context overflow if there are too many
    BATCH_SIZE = 15
    new_rules = 0
    today_str = datetime.now().strftime("%Y-%m-%d")

    for i in range(0, len(summaries), BATCH_SIZE):
        batch = summaries[i:i+BATCH_SIZE]
        print(f"Synthesizing batch {i//BATCH_SIZE + 1}...")
        
        golden_rule = await generate_golden_rule(batch)
        if golden_rule:
            rule_text = f"GOLDEN RULE META-STRATEGY (Synthesized {today_str}):\n{golden_rule}\n"
            out_path = NARR_DIR / f"dream_rule_{today_str}_B{i//BATCH_SIZE}.txt"
            out_path.write_text(rule_text, encoding='utf-8')
            new_rules += 1

    # Cleanup individual files to reduce vector bloat
    print("Cleaning up old retrospective fragments to prevent vector bloat...")
    for f in retro_files:
        try:
            f.unlink()
        except:
            pass
            
    print(f"Dream State complete. Created {new_rules} Golden Rules.")

if __name__ == "__main__":
    asyncio.run(run_dream_state())
