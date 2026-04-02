import asyncio
import os
import sys
import re
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.schemas import RaceCard, HorseEntry
from services.browser_manager import BrowserManager

class RacecardIngest:
    def __init__(self, headless=True, browser_mgr=None):
        self.headless = headless
        self.browser_mgr = browser_mgr or BrowserManager(headless=headless)

    async def fetch_racecard(self, date_str: str, venue: str, race_no: int, page=None) -> Optional[RaceCard]:
        """
        Fetches racecard data from HKJC website.
        date_str: DD/MM/YYYY or YYYY-MM-DD
        venue: ST or HV
        race_no: int
        """
        # Convert to YYYY/MM/DD format for HKJC URL
        if "/" in date_str:
            # DD/MM/YYYY -> YYYY/MM/DD
            parts = date_str.split("/")
            if len(parts[0]) == 4:  # Already YYYY/MM/DD
                formatted_date = date_str
            else:  # DD/MM/YYYY
                formatted_date = f"{parts[2]}/{parts[1]}/{parts[0]}"
        else:
            # YYYY-MM-DD -> YYYY/MM/DD
            formatted_date = date_str.replace("-", "/")
        
        dt_iso = formatted_date.replace("/", "-")
        url = f"https://racing.hkjc.com/en-us/local/information/racecard?racedate={formatted_date}&Racecourse={venue}&RaceNo={race_no}"
        
        own_page = False
        context = None
        if not page:
            # use persistent context to avoid bot detection
            context, page = await self.browser_mgr.get_persistent_context("ingest")
            own_page = True
            
        try:
            print(f"[RACECARD] Navigating to {url}...")
            await page.goto(url, wait_until="domcontentloaded", timeout=90000)
            
            # Wait for any of the known table selectors
            table_selectors = ["table.starter", "table.table_bd.racecard", "#racecardlist table"]
            table_found = False
            for sel in table_selectors:
                try:
                    await page.wait_for_selector(sel, timeout=10000)
                    print(f"[RACECARD] Found horse table with selector: {sel}")
                    table_found = True
                    break
                except:
                    continue
            
            if not table_found:
                # Last ditch: look for any table with "Horse No."
                tables = await page.query_selector_all("table")
                for t in tables:
                    text = await t.inner_text()
                    if "Horse No." in text and "Jockey" in text:
                        print("[RACECARD] Found horse table by text content analysis.")
                        table_found = True
                        break
            
            if not table_found:
                raise Exception("Could not locate horse table on page.")

            # --- Base Race Info ---
            content_text = await page.inner_text("#innerContent, .p_line, body")
            
            distance = 1200
            track_type = "Turf"
            course = "A"
            race_class = "Class 4"

            # Parse Distance info
            dist_match = re.search(r'(\d+)M', content_text)
            if dist_match:
                distance = int(dist_match.group(1))
            
            if "All Weather" in content_text or "AWT" in content_text:
                track_type = "All Weather Track"
            elif "Turf" in content_text:
                track_type = "Turf"

            # Parse Class/Rating
            class_match = re.search(r'(Class \d|Griffin|Group \d)', content_text)
            if class_match:
                race_class = class_match.group(1)

            # --- Ultra-Resilient Global Row Scan ---
            horses_data = await page.evaluate(r'''() => {
                const allRows = Array.from(document.querySelectorAll('tr'));
                return allRows.map(row => {
                    const cols = Array.from(row.querySelectorAll('td')).map(td => td.innerText.trim());
                    if (cols.length < 5) return null;

                    const saddle = cols.find(c => /^\d+$/.test(c));
                    if (!saddle) return null;

                    // Heuristic Content Detection - Relaxed to handle VM's "Lite" layout
                    const horse = cols.find(c => /[A-Z]{3,}/.test(c) && c === c.toUpperCase());
                    const last_6 = cols.find(c => c.includes('/') || (c.length > 3 && /^[\d\-W/]+$/.test(c)));
                    const weight = cols.find(c => /^\d{3}$/.test(c) && parseInt(c) > 100 && parseInt(c) < 155);

                    if (!horse || !saddle) return null;

                    const horseIdx = cols.indexOf(horse);
                    return {
                        saddle: saddle,
                        horse: horse,
                        last_6: last_6 || "",
                        weight: weight || "",
                        jockey: cols[horseIdx + 2] || cols[horseIdx + 1] || "",
                        draw: cols[horseIdx + 3] || "",
                        trainer: cols[horseIdx + 4] || cols[cols.length - 1] || ""
                    };
                }).filter(h => h !== null);
            }''')

            horses = []
            for h in horses_data:
                saddle_number = int(h['saddle'])
                last_6 = [r.strip() for r in h['last_6'].split('/') if r.strip()]
                
                horse_name = h['horse'].split('(')[0].strip()
                brand_id = "N/A"
                brand_match = re.search(r'\(([^)]+)\)', h['horse'])
                if brand_match:
                    brand_id = brand_match.group(1)
                
                jockey = re.sub(r'\(-?\d+\)', '', h['jockey']).strip() # Remove allowance
                
                try:
                    weight = float(h['weight'])
                except:
                    weight = 133.0
                    
                try:
                    draw = int(h['draw'])
                except:
                    draw = 0
                
                entry = HorseEntry(
                    horse_id=brand_id,
                    horse_name=horse_name,
                    owner="",
                    saddle_number=saddle_number,
                    draw=draw,
                    jockey=jockey,
                    trainer=h['trainer'],
                    weight=weight,
                    last_6_runs=last_6,
                    gear=""
                )
                horses.append(entry)

            if not horses:
                print(f"[ERROR] No horses found for R{race_no}.")
                if own_page: await page.close()
                return None

            race_id = f"{dt_iso}_{venue}_R{race_no}"
            
            card = RaceCard(
                race_id=race_id,
                date=datetime.strptime(dt_iso, "%Y-%m-%d"),
                race_number=race_no,
                distance=distance,
                track_type=track_type,
                course=course,
                race_class=race_class,
                horses=horses
            )
            
            print(f"[RACECARD] Successfully scraped {len(horses)} horses for {race_id}")
            if own_page:
                await page.close()
            return card
            
        except Exception as e:
            print(f"[RACECARD] Extraction ERROR: {e}")
            if page:
                try:
                    debug_path = f"tmp/racecard_error_R{race_no}.png"
                    await page.screenshot(path=debug_path)
                    print(f"[RACECARD] Saved debug screenshot to {debug_path}")
                except: pass
            if own_page:
                await page.close()
            return None

async def main():
    import argparse
    parser = argparse.ArgumentParser(description="HKJC Racecard Ingestor")
    parser.add_argument("--date", type=str, required=True, help="YYYY-MM-DD")
    parser.add_argument("--venue", type=str, default="ST", help="ST or HV")
    parser.add_argument("--race", type=int, default=1)
    args = parser.parse_args()

    ingest = RacecardIngest(headless=True)
    card = await ingest.fetch_racecard(args.date, args.venue, args.race)
    if card:
        os.makedirs("data", exist_ok=True)
        date_clean = args.date.replace("-", "").replace("/", "")
        filename = f"data/racecard_{date_clean}_R{args.race}.json"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(card.model_dump_json(indent=2))
        print(f"Racecard saved to {filename}")
    else:
        print("Scrape FAILED.")
    
    await ingest.browser_mgr.stop()

if __name__ == "__main__":
    asyncio.run(main())
