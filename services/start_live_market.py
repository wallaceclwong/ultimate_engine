import asyncio
import subprocess
import sys
import os
from datetime import datetime

async def start_watchdog(race_no, venue="HV"):
    print(f"[WATCHDOG] Starting Live Monitoring for Race {race_no}...")
    # We call the script directly to run in its own process
    cmd = [
        "python", "services/market_watchdog.py",
        # We'll need a way to pass race_no to the main block of market_watchdog if we want it to run-loop
    ]
    # Actually, let's just modify market_watchdog.py to be more easily orchestratable 
    # OR write a wrapper that calls its internal methods.
    
    # For now, let's just run a subprocess that calls a specific function
    # Or better yet, just run it via python -c for simplicity in this bridge
    
    script = f"""
import asyncio
from services.market_watchdog import MarketWatchdog
async def run():
    dog = MarketWatchdog(drop_threshold=0.15)
    await dog.run_loop(race_no={race_no}, venue='{venue}', interval=180)
asyncio.run(run())
"""
    process = await asyncio.create_subprocess_exec(
        "python", "-c", script,
        cwd=r"c:\Users\ASUS\ultimate_engine"
    )
    return process

async def main():
    venue = "HV"
    # Start watchdog for all 9 races of the day
    tasks = []
    for r in range(1, 10):
        p = await start_watchdog(r, venue)
        tasks.append(p)
    
    print(f"[SYSTEM] 9 Live Market Watchdogs initiated for {venue}. Monitoring every 3 minutes.")
    
    # Keep the orchestrator alive
    while True:
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
