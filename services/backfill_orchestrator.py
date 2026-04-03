import asyncio
import json
import os
import time
import sys
from pathlib import Path
from datetime import datetime
import re

# Ensure project root is in path for services imports
sys.path.append(str(Path(__file__).parent.parent))

from services.results_ingest import ResultsIngest
from services.analytical_ingest import AnalyticalIngest
from services.browser_manager import BrowserManager

class BackfillOrchestrator:
    def __init__(self):
        self.base_dir = Path(__file__).resolve().parent.parent
        self.fixtures_2026 = self.base_dir / "data/fixtures_2026.json"
        self.fixtures_2025 = self.base_dir / "data/fixtures_2025.json"
        self.fixtures_2024 = self.base_dir / "data/fixtures_2024.json"
        self.fixtures_2023 = self.base_dir / "data/fixtures_2023.json"
        self.fixtures_2022 = self.base_dir / "data/fixtures_2022.json"
        self.fixtures_2021 = self.base_dir / "data/fixtures_2021.json"
        self.fixtures_2020 = self.base_dir / "data/fixtures_2020.json"
        self.fixtures_2019 = self.base_dir / "data/fixtures_2019.json"
        self.fixtures_2018 = self.base_dir / "data/fixtures_2018.json"
        self.progress_file = self.base_dir / "data/backfill_status.json"
        self.brain_progress = Path(r"C:\Users\ASUS\.gemini\antigravity\brain\507cc95c-e002-4b14-9a57-11e186b21f50\backfill_progress.md")
        self.results_dir = self.base_dir / "data/results"
        self.analytical_dir = self.base_dir / "data/analytical"
        
        # We don't initialize ingests with default mgr here, we'll pass it per meeting
        self.semaphore = asyncio.Semaphore(2)

    async def run_overnight_backfill(self, limit_meetings=None):
        print("Starting Overnight Absolute Legacy Backfill (2018-2026)...")
        
        fixture_configs = [
            (self.fixtures_2026, "2026"), (self.fixtures_2025, "2025"),
            (self.fixtures_2024, "2024"), (self.fixtures_2023, "2023"),
            (self.fixtures_2022, "2022"), (self.fixtures_2021, "2021"),
            (self.fixtures_2020, "2020"), (self.fixtures_2019, "2019"),
            (self.fixtures_2018, "2018")
        ]

        processed_count = 0
        try:
            for fixture_file, year in fixture_configs:
                fixtures_processed = await self.process_fixtures(fixture_file, year, limit=limit_meetings, current_count=processed_count)
                processed_count += fixtures_processed
                if limit_meetings and processed_count >= limit_meetings:
                    print(f"Reached limit of {limit_meetings} meetings. Stopping...")
                    break
            self.update_progress("COMPLETED")
        except Exception as e:
            print(f"Backfill fatal error: {e}")
            self.update_progress(f"CRASHED: {e}")

    async def process_fixtures(self, fixture_file, year, limit=None, current_count=0):
        print(f"--- Processing {year} ---")
        with open(fixture_file, "r") as f:
            fixtures = json.load(f)

        if limit:
            remaining_limit = max(0, limit - current_count)
            fixtures = fixtures[:remaining_limit]
            if not fixtures: return 0

        total = len(fixtures)
        tasks = []
        for i, fixture in enumerate(fixtures):
            tasks.append(self.process_meeting_with_timeout(fixture, i, total, year))
        
        await asyncio.gather(*tasks)
        return len(fixtures)

    async def process_meeting_with_timeout(self, fixture, i, total, year):
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                # 30 minute timeout per meeting
                await asyncio.wait_for(
                    self.process_meeting_semaphore(fixture, i, total, year), 
                    timeout=1800
                )
                return # Success
            except asyncio.TimeoutError:
                date_str = fixture.get("date", "Unknown")
                if attempt < max_retries:
                    print(f"Warning: Meeting {date_str} timed out (Attempt {attempt+1}/{max_retries+1}). Retrying...")
                    await asyncio.sleep(10) # Wait a bit before retry
                else:
                    print(f"CRITICAL: Meeting {date_str} timed out after 30 minutes. Skipping...")
            except Exception as e:
                print(f"Error processing meeting {fixture.get('date')}: {e}")
                if attempt == max_retries: break
                await asyncio.sleep(5)

    async def process_meeting_semaphore(self, fixture, index, total, year):
        async with self.semaphore:
            date_str = fixture["date"]
            try:
                dt = datetime.strptime(date_str, "%d/%m/%Y")
            except:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
            
            formatted_date = dt.strftime("%Y-%m-%d")
            venue = fixture["venue"]
            
            # Check if meeting is already fully processed
            race_id_check = f"{formatted_date}_{venue}_R9"
            if (self.results_dir / f"results_{race_id_check}.json").exists() and \
               (self.analytical_dir / f"analytical_{race_id_check}.json").exists():
                return

            # Update progress AS SOON AS WE START so heartbeat is fresh for dashboard
            self.update_progress(f"Starting {formatted_date}")
            print(f"[{index+1}/{total}] Processing {formatted_date} ({venue})...")
            
            async with BrowserManager(headless=True) as mgr:
                page = await mgr.get_page()
                res_ingest = ResultsIngest(browser_mgr=mgr)
                ana_ingest = AnalyticalIngest(browser_mgr=mgr)

                for race_no in range(1, 13):
                    race_id = f"{formatted_date}_{venue}_R{race_no}"
                    results_path = self.results_dir / f"results_{race_id}.json"
                    analytical_path = self.analytical_dir / f"analytical_{race_id}.json"
                    
                    # 1. Handle Results
                    results_found = False
                    if results_path.exists():
                        try:
                            with open(results_path, "r") as f:
                                res_data = json.load(f)
                                if res_data.get("results"):
                                    results_found = True
                        except:
                            pass
                    if not results_found:
                        try:
                            # 2 minute timeout per race fetch
                            data = await asyncio.wait_for(
                                res_ingest.fetch_results(formatted_date, venue=venue, race_no=race_no, page=page),
                                timeout=120
                            )
                            if data and data.get("results"):
                                os.makedirs(self.results_dir, exist_ok=True)
                                with open(results_path, "w", encoding="utf-8") as f:
                                    json.dump(data, f, indent=2)
                                results_found = True
                            else:
                                # If R1 fails or R9+ is empty, meeting likely ended/didn't happen
                                if race_no == 1 or race_no >= 9: break
                                continue # Skip analytical if result fetch returned nothing but we keep going
                        except asyncio.TimeoutError:
                            print(f"  Warning: Race {race_no} results fetch timed out.")
                            continue
                        except Exception as e:
                            print(f"  Error in Race {race_no} results: {e}")
                            continue

                    # 2. Handle Analytical (only if results exist for this race)
                    if results_found:
                        if not analytical_path.exists():
                            try:
                                a_data = await asyncio.wait_for(
                                    ana_ingest.fetch_analytical_data(formatted_date, venue=venue, race_no=race_no, page=page),
                                    timeout=120
                                )
                                if a_data:
                                    os.makedirs(self.analytical_dir, exist_ok=True)
                                    with open(analytical_path, "w", encoding="utf-8") as f:
                                        json.dump(a_data, f, indent=2)
                            except asyncio.TimeoutError:
                                print(f"  Warning: Race {race_no} analytical fetch timed out.")
                            except Exception as e:
                                print(f"  Error in Race {race_no} analytical: {e}")
                    
                    self.update_progress(f"{formatted_date} R{race_no}")
            
            await asyncio.sleep(1)

    def calculate_total_goal(self):
        total = 0
        fixture_files = [
            self.fixtures_2026, self.fixtures_2025, self.fixtures_2024,
            self.fixtures_2023, self.fixtures_2022, self.fixtures_2021,
            self.fixtures_2020, self.fixtures_2019, self.fixtures_2018
        ]
        for f_path in fixture_files:
            if f_path.exists():
                try:
                    with open(f_path, "r") as f:
                        data = json.load(f)
                        total += len(data)
                except:
                    pass
        return total

    def update_progress(self, current_task="Idle"):
        # Count unique dates in results directory
        files = list(self.results_dir.glob("results_*.json"))
        unique_dates = set()
        for f in files:
            date_match = re.search(r"results_(\d{4}-\d{2}-\d{2})", f.name)
            if date_match:
                unique_dates.add(date_match.group(1))
        
        results_count = len(unique_dates)
        total_goal = self.calculate_total_goal()
        
        # Calculate ETA (roughly 1.5 mins per remaining meeting with 8 streams + optimizations)
        remaining = max(0, total_goal - results_count)
        eta_hours = (remaining * 1.5) / 60
        eta_str = f"{round(eta_hours, 1)} hours (~{round(eta_hours/24, 1)} days)"

        content = f"""# 📊 Backfill Progress (Absolute Legacy)
**Updated:** `{datetime.now().strftime("%H:%M:%S")}`
**Current Task:** `{current_task}`
**Estimated ETA:** `{eta_str}`

| Status | Count |
|---|---|
| ✅ **Meetings Done** | **{results_count}** |
| ⏳ **Meetings Left** | **{remaining}** |
| Legacy Goal | **{total_goal} Total Meetings** |

---
*Phase 4: 8-Year Historical Data Ingestion in progress.*
"""
        # Update progress in BOTH project data and current brain
        progress_files = [
            self.brain_progress
        ]
        
        for p_file in progress_files:
            try:
                os.makedirs(p_file.parent, exist_ok=True)
                with open(p_file, "w", encoding="utf-8") as f:
                    f.write(content)
            except:
                pass

        # Write Heartbeat for Dashboard
        try:
            with open(self.progress_file, "w", encoding="utf-8") as f:
                json.dump({
                    "status": "ACTIVE",
                    "current_task": current_task,
                    "meetings_done": results_count,
                    "meetings_left": remaining,
                    "eta": eta_str,
                    "timestamp": datetime.now().timestamp()
                }, f)
        except:
            pass

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="HKJC Legacy Backfill Orchestrator")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of meetings to process")
    args = parser.parse_args()

    orchestrator = BackfillOrchestrator()
    asyncio.run(orchestrator.run_overnight_backfill(limit_meetings=args.limit))
