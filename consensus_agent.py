import os
import json
import asyncio
import re
from pathlib import Path
<<<<<<< HEAD
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from openai import AsyncOpenAI, APIError, APITimeoutError
=======
from openai import AsyncOpenAI
>>>>>>> 85f74059cc4211783be2a1b259a9ef24c87ae229
from dotenv import load_dotenv

# ─── Config ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.absolute()
DATA_DIR = BASE_DIR / "data"
DOTENV_FILE = BASE_DIR / ".env"
PEDIGREE_FILE = DATA_DIR / "pedigree_cache.json"
load_dotenv(DOTENV_FILE)

# ─── DeepSeek Reasoning Client ───────────────────────────────────────────────
# Note: Use the project's standard API key
client = AsyncOpenAI(api_key=os.getenv('DEEPSEEK_API_KEY'), base_url='https://api.deepseek.com')

class ConsensusAgent:
    """
    Expert Reasoning 'War Room' that audits statistical picks using multi-agent simulation.
    """
    def __init__(self):
        self.model = "deepseek-reasoner" # Using R1 (Reasoner)
        self.pedigree_cache = {}
        self._load_pedigree()

    def _load_pedigree(self):
        if PEDIGREE_FILE.exists():
            try:
                with open(PEDIGREE_FILE, 'r') as f:
                    self.pedigree_cache = json.load(f)
            except:
                self.pedigree_cache = {}

<<<<<<< HEAD
    @retry(
        stop=stop_after_attempt(3), 
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((APIError, APITimeoutError))
    )
    async def get_consensus(self, race_data, tip_horse_no, market_context=None):
        """
        Runs a Multi-Agent 'War Room' Audit on the provided tip.
        Supports optional live market_context for late-money detection.
=======
    async def get_consensus(self, race_data, tip_horse_no):
        """
        Runs a Multi-Agent 'War Room' Audit on the provided tip.
>>>>>>> 85f74059cc4211783be2a1b259a9ef24c87ae229
        """
        # Find the horse being tipped
        df_target = race_data[race_data["horse_no"].astype(str) == str(tip_horse_no)]
        if df_target.empty: return "VETO", "Horse not found in race data."
        
        target = df_target.iloc[0].to_dict()
        horse_id = target.get("horse_id", "Unknown")
        
        # 1. Gather Pedigree Context
        pedigree = self.pedigree_cache.get(horse_id, {"sire": "Unknown", "dam": "Unknown"})
        
        # 2. Gather Field Context (Top 5 + Context)
        field_context = []
        for _, h in race_data.iterrows():
            field_context.append({
                "no": h["horse_no"],
                "name": h["horse_name"],
                "odds": round(h["win_odds"], 1),
                "draw": h["draw"],
                "rank": h["rank"],
                "fair_odds": round(h.get("fair_odds", 10.0), 1),
                "value_mult": round(h.get("value_mult", 1.0), 2)
            })

<<<<<<< HEAD
        # 3. Market Momentum Context
        market_str = "No live market data provided."
        if market_context:
            movement = market_context.get('movement', 0)
            trend = market_context.get('trend', 'stable')
            market_str = f"LATE MONEY TREND: {trend.upper()} ({movement:+.1%})."

        # 4. The 'War Room' Multi-Agent Prompt
=======
        # 3. The 'War Room' Multi-Agent Prompt
>>>>>>> 85f74059cc4211783be2a1b259a9ef24c87ae229
        prompt = f"""
Act as the 'LUNAR LEAP' STRATEGIC ADVISORY for HKJC.
Audit the following High-Value Trade using a MULTI-AGENT simulation.

### THE TARGET (Statistical Favorite)
- Horse: {target['horse_name']} (#{target['horse_no']})
- ID: {horse_id}
- Lineage: Sire: {pedigree['sire']} | Dam: {pedigree['dam']}
- Stats: Odds {target['win_odds']:.1f} (Fair: {target.get('fair_odds', 'N/A')}), Mult: {target.get('value_mult', 'N/A')}x
- Logistics: Draw {target['draw']}, Race {target.get('race', 'N/A')} at {target.get('venue', 'N/A')}

<<<<<<< HEAD
### MARKET MOMENTUM (Live T-15 Sniff)
{market_str}

=======
>>>>>>> 85f74059cc4211783be2a1b259a9ef24c87ae229
### FIELD CONTEXT
{json.dumps(field_context[:14], indent=2)}

### WAR ROOM ROLES:
1. **AGENT TACTICIAN**: Analyze the 'Pace' and 'Draw'. Can this horse stay clear or will it be trapped?
<<<<<<< HEAD
2. **AGENT GENETICIST**: Analyze the Sire/Dam. Is this horse bred for {target['track_type']} conditions today?
3. **AGENT MARKET-ANALYST**: Analyze the LATE MONEY TREND. Is this 'Smart Money' (informed) or 'Market Noise' (emotional)?
4. **AGENT VALUE-ORACLE**: Compare Public Odds vs Fair Odds. Is the profit margin worth the risk?
=======
2. **AGENT GENETICIST**: Analyze the Sire/Dam. Is this horse bred for {target['distance']}m on {target['track_type']}?
3. **AGENT VALUE-ORACLE**: Compare Public Odds ({target['win_odds']}) vs Fair Odds ({target.get('fair_odds', 'N/A')}). Is the profit margin worth the risk?
>>>>>>> 85f74059cc4211783be2a1b259a9ef24c87ae229

### OUTPUT FORMAT:
Respond with a JSON block followed by a brief 'Expert Note'.
{{
  "verdict": "CONFIRMED" | "CAUTION" | "VETO",
  "conviction_grade": "S" | "A" | "B",
<<<<<<< HEAD
  "market_signal": "Brief analysis of the odds movement validity",
=======
>>>>>>> 85f74059cc4211783be2a1b259a9ef24c87ae229
  "tactical_scenario": "2-sentence prediction of the race jump",
  "reasoning_path": "3-sentence chain of thought",
  "expert_note": "A final 1-sentence tactical summary for the user"
}}
"""

        try:
            resp = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a Multi-Agent Strategic Auditor for HKJC. You provide high-conviction 'Lunar Leap' audits for statistical models."},
                    {"role": "user", "content": prompt}
                ],
                timeout=55
            )
            
            full_content = resp.choices[0].message.content
            # Extraction logic
            json_match = re.search(r'\{.*\}', full_content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(0))
                return result.get("verdict", "CAUTION"), (
                    f"Grade [{result.get('conviction_grade', '?')}] — "
<<<<<<< HEAD
                    f"SIGNAL: {result.get('market_signal')} — "
=======
                    f"Scenario: {result.get('tactical_scenario')} — "
>>>>>>> 85f74059cc4211783be2a1b259a9ef24c87ae229
                    f"REASON: {result.get('reasoning_path')} — "
                    f"NOTE: {result.get('expert_note')}"
                )
            else:
                return "CAUTION", f"DeepSeek-R1 (War Room): {full_content[:200]}..."
                
        except Exception as e:
            return "ERROR", f"War Room Audit failed: {str(e)}"

consensus_agent = ConsensusAgent()
