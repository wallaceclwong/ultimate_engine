import os
import json
import asyncio
import re
from pathlib import Path
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from openai import AsyncOpenAI, APIError, APITimeoutError
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

    async def check_health(self):
        """Verifies API connectivity with a minimal prompt."""
        try:
            resp = await client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=10,
                timeout=10
            )
            return True if resp.choices else False
        except Exception as e:
            print(f"[API HEALTH ERROR] DeepSeek unreachable: {e}")
            return False

    def reload_pedigree(self):
        self._load_pedigree()

    def _load_pedigree(self):
        if PEDIGREE_FILE.exists():
            try:
                with open(PEDIGREE_FILE, 'r') as f:
                    self.pedigree_cache = json.load(f)
            except:
                self.pedigree_cache = {}

    @retry(
        stop=stop_after_attempt(3), 
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((APIError, APITimeoutError))
    )
    async def get_consensus(self, race_data, tip_horse_no, market_context=None):
        """
        Runs a Multi-Agent 'War Room' Audit on the provided tip.
        Supports optional live market_context for late-money detection.
        """
        # Find the horse being tipped
        # Tip horse number could be int or string, ensure comparison works
        df_target = race_data[race_data["horse_no"].astype(str) == str(tip_horse_no)]
        if df_target.empty: return "VETO", "Horse not found in race data."
        
        target = df_target.iloc[0].to_dict()
        horse_id = target.get("horse_id", "Unknown")
        
        # 1. Gather Pedigree Context
        pedigree = self.pedigree_cache.get(horse_id, {"sire": "Unknown", "dam": "Unknown"})
        
        # If unknown, try to look up parenthetically if ID was passed as string
        if pedigree["sire"] == "Unknown" and "(" in str(target.get("horse", "")):
             match = re.search(r'\(([A-Z0-9]+)\)', target["horse"])
             if match:
                 h_id = match.group(1)
                 pedigree = self.pedigree_cache.get(h_id, {"sire": "Unknown", "dam": "Unknown"})

        # Final check: If still unknown, DeepSeek will flag it, but the nightly scraper 
        # will have caught most of them.
        
        # 2. Gather Field Context (Top 14 + Context)
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

        # 3. Market Momentum Context
        market_str = "No live market data provided."
        if market_context:
            movement = market_context.get('movement', 0)
            trend = market_context.get('trend', 'stable')
            market_str = f"LATE MONEY TREND: {trend.upper()} ({movement:+.1%})."

        # 4. Historical Context (Multi-Dimensional Vector Memory)
        from services.memory_service import memory_service
        memory_str = "No specific historical intelligence found in Palace."
        try:
            # Query 1: Horse Performance history
            res_bio = memory_service.search(f"{target['horse_name']} performance history")
            
            # Query 2: Trainer/Jockey Synergy
            trainer_name = target.get('trainer', 'Unknown')
            jockey_name = target.get('jockey', 'Unknown')
            res_synergy = memory_service.search(f"{trainer_name} and {jockey_name} combination Hong Kong ROI")
            
            # Query 3: Surface & Conditions (Track Intelligence)
            venue = target.get('venue', 'HV')
            dist = target.get('distance', 1200)
            res_track = memory_service.search(f"{venue} {dist}m track characteristics and bias")
            
            # Query 4: Lesson Learnt Retrospective
            res_retro = memory_service.search(f"{target['horse_name']} LESSON LEARNT retrospective failed prediction")
            
            # Query 5: Pedigree Characteristics
            res_ped = memory_service.search(f"PEDIGREE for horse {horse_id} sired by {pedigree['sire']}")

            # Aggregate context
            mem_bits = []
            if "Results for" in res_bio: mem_bits.append(f"--- Horse Bio ---\n{res_bio}")
            if "Results for" in res_synergy: mem_bits.append(f"--- Synergy Intel ---\n{res_synergy}")
            if "Results for" in res_track: mem_bits.append(f"--- Track Intel ---\n{res_track}")
            if "Results for" in res_retro: mem_bits.append(f"--- FAIL RETROSPECTIVE ---\n{res_retro}")
            if "Results for" in res_ped: mem_bits.append(f"--- PEDIGREE INTEL ---\n{res_ped}")
            
            if mem_bits:
                memory_str = "\n".join(mem_bits)
        except Exception as e:
            print(f"[MEMORY WARN] Multi-search failed: {e}")

        # 5. The 'War Room' Multi-Agent Prompt
        prompt = f"""
Act as the 'LUNAR LEAP' STRATEGIC ADVISORY for HKJC.
Audit the following High-Value Trade using a MULTI-AGENT simulation.

### THE TARGET (Statistical Favorite)
- Horse: {target['horse_name']} (#{target['horse_no']})
- ID: {horse_id}
- Lineage: Sire: {pedigree['sire']} | Dam: {pedigree['dam']}
- Stats: Odds {target['win_odds']:.1f} (Fair: {target.get('fair_odds', 'N/A')}), Mult: {target.get('value_mult', 'N/A')}x
- Logistics: Draw {target['draw']}, Race {target.get('race', 'N/A')} at {target.get('venue', 'N/A')}

### LUNAR INTELLIGENCE (Historical Memory)
{memory_str}

### MARKET MOMENTUM (Live T-15 Sniff)
{market_str}

### FIELD CONTEXT
{json.dumps(field_context[:14], indent=2)}

### WAR ROOM ROLES:
1. **AGENT TACTICIAN**: Analyze the 'Pace' and 'Draw'. Can this horse stay clear or will it be trapped?
2. **AGENT GENETICIST**: Analyze the Sire/Dam. Is this horse bred for {target.get('distance', 'N/A')}m on {target.get('track_type', 'N/A')} conditions today?
3. **AGENT MARKET-ANALYST**: Analyze the LATE MONEY TREND. Is this 'Smart Money' (informed) or 'Market Noise' (emotional)?
4. **AGENT VALUE-ORACLE**: Compare Public Odds vs Fair Odds. Is the profit margin worth the risk?

### OUTPUT FORMAT:
Respond with a JSON block followed by a brief 'Expert Note'.
{{
  "verdict": "CONFIRMED" | "CAUTION" | "VETO",
  "conviction_grade": "S" | "A" | "B",
  "market_signal": "Brief analysis of the odds movement validity",
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
            
            # --- Robust EXTRACTION LOGIC ---
            # 1. Remove <think> tags if present
            clean_content = re.sub(r'<think>.*?</think>', '', full_content, flags=re.DOTALL)
            
            # 2. Try to find markdown JSON block
            json_block_match = re.search(r'```json\s*(\{.*?\})\s*```', clean_content, re.DOTALL)
            if json_block_match:
                result_str = json_block_match.group(1)
            else:
                # 3. Fallback to raw braces
                json_match = re.search(r'\{.*\}', clean_content, re.DOTALL)
                result_str = json_match.group(0) if json_match else None

            if result_str:
                result = json.loads(result_str)
                return result.get("verdict", "CAUTION"), (
                    f"Grade [{result.get('conviction_grade', '?')}] — "
                    f"SIGNAL: {result.get('market_signal')} — "
                    f"REASON: {result.get('reasoning_path')} — "
                    f"NOTE: {result.get('expert_note')}"
                )
            else:
                # Log the raw content for debugging if extraction fails
                print(f"[DEBUG] Extraction failed. Raw: {full_content[:300]}...")
                return "CAUTION", "DeepSeek-R1: Failed to parse strategic JSON."
                
        except Exception as e:
            return "ERROR", f"War Room Audit failed: {str(e)}"

consensus_agent = ConsensusAgent()
