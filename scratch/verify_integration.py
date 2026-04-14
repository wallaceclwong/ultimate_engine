import os
import sys
import asyncio
import pandas as pd
import json
from pathlib import Path

# Add project root to path
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))

from consensus_agent import consensus_agent

async def run_integration_check():
    print("=== LUNAR LEAP: INTEGRATION HANDSHAKE TEST ===")
    
    # 1. Load data for a real horse from tomorrow's racecard (Sha Tin R1)
    rc_file = root_dir / "data" / "racecard_20260412_R1.json"
    if not rc_file.exists():
        print(f"Error: {rc_file} not found.")
        return

    with open(rc_file, "r") as f:
        rc_data = json.load(f)
    
    # Normalize horses into a DataFrame that ConsensusAgent expects
    df = pd.DataFrame(rc_data["horses"])
    
    # Add dummy/mock columns that might be missing in raw racecard but needed for audit
    if "win_odds" not in df.columns: df["win_odds"] = 10.0
    if "fair_odds" not in df.columns: df["fair_odds"] = 7.0
    if "rank" not in df.columns: df["rank"] = 4
    if "value_mult" not in df.columns: df["value_mult"] = 1.43
    if "horse_no" not in df.columns: df["horse_no"] = range(1, len(df)+1)
    
    target_horse_no = 3 # SILVERY KNIGHT
    
    print(f"Step 1: Auditing Horse #{target_horse_no} (SILVERY KNIGHT)...")
    
    # 2. Trigger the Consensus Agent (Integration Point)
    # This will:
    #   - Query MemPalace (via memory_service)
    #   - Call DeepSeek-R1 (via AsyncOpenAI)
    #   - Parse the response
    
    try:
        verdict, reasoning = await consensus_agent.get_consensus(df, target_horse_no)
        
        print("\n--- INTEGRATION RESULTS ---")
        print(f"VERDICT: {verdict}")
        print(f"REASONING: {reasoning}")
        print("--------------------------")
        
        if verdict in ["CONFIRMED", "CAUTION", "VETO"]:
            print("SUCCESS: DeepSeek-R1 correctly analyzed the integration context.")
        else:
            print("WARNING: Unexpected verdict format.")
            
    except Exception as e:
        import traceback
        print(f"INTEGRATION FAILED: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_integration_check())
