import os
import json
import asyncio
import re
from pathlib import Path
from openai import AsyncOpenAI
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

    async def get_consensus(self, race_data, tip_horse_no):
        """
        Runs a Multi-Agent 'War Room' Audit on the provided tip.
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

        # 3. The 'War Room' Multi-Agent Prompt
        prompt = f"""
Act as the 'LUNAR LEAP' STRATEGIC ADVISORY for HKJC.
Audit the following High-Value Trade using a MULTI-AGENT simulation.

### THE TARGET (Statistical Favorite)
- Horse: {target['horse_name']} (#{target['horse_no']})
- ID: {horse_id}
- Lineage: Sire: {pedigree['sire']} | Dam: {pedigree['dam']}
- Stats: Odds {target['win_odds']:.1f} (Fair: {target.get('fair_odds', 'N/A')}), Mult: {target.get('value_mult', 'N/A')}x
- Logistics: Draw {target['draw']}, Race {target.get('race', 'N/A')} at {target.get('venue', 'N/A')}

### FIELD CONTEXT
{json.dumps(field_context[:14], indent=2)}

### WAR ROOM ROLES:
1. **AGENT TACTICIAN**: Analyze the 'Pace' and 'Draw'. Can this horse stay clear or will it be trapped?
2. **AGENT GENETICIST**: Analyze the Sire/Dam. Is this horse bred for {target['distance']}m on {target['track_type']}?
3. **AGENT VALUE-ORACLE**: Compare Public Odds ({target['win_odds']}) vs Fair Odds ({target.get('fair_odds', 'N/A')}). Is the profit margin worth the risk?

### OUTPUT FORMAT:
Respond with a JSON block followed by a brief 'Expert Note'.
{{
  "verdict": "CONFIRMED" | "CAUTION" | "VETO",
  "conviction_grade": "S" | "A" | "B",
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
                    f"Scenario: {result.get('tactical_scenario')} — "
                    f"REASON: {result.get('reasoning_path')} — "
                    f"NOTE: {result.get('expert_note')}"
                )
            else:
                return "CAUTION", f"DeepSeek-R1 (War Room): {full_content[:200]}..."
                
        except Exception as e:
            return "ERROR", f"War Room Audit failed: {str(e)}"

consensus_agent = ConsensusAgent()
