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

            # Parse Track Condition (Going)
            # HKJC uses: GOOD, GOOD TO YIELDING, YIELDING, SOFT, WET, GOOD TO FIRM
            track_condition = "Good"  # Default
            going_match = re.search(
                r'Going[:\s]*([A-Z][A-Z\s]{2,25})',
                content_text,
                re.IGNORECASE
            )
            if going_match:
                raw_going = going_match.group(1).strip().upper()
                # Normalize to our model's known categories
                if "WET" in raw_going:
                    track_condition = "Wet"
                elif "SOFT" in raw_going:
                    track_condition = "Soft"
                elif "FIRM" in raw_going:
                    track_condition = "Good"  # Map Good to Firm -> Good
                elif "YIELDING" in raw_going:
                    track_condition = "Yielding"
                else:
                    track_condition = "Good"
                print(f"[RACECARD] Track condition: {track_condition} (raw: '{raw_going}')")
            else:
                print("[RACECARD] Going not found on page; defaulting to 'Good'.")

            # Parse Jump Time (e.g., '1:00 PM' or '13:00')
            jump_time = "13:00"
            time_match = re.search(r'(\d{1,2}:\d{2}\s?(?:AM|PM)?)', content_text)
            if time_match:
                jump_time = time_match.group(1)

            # --- Precise HKJC Layout Extraction ---
            horses_data = await page.evaluate(r'''() => {
                const results = [];
                // Target the main racecard table specifically
                const tables = Array.from(document.querySelectorAll('table.starter, table.table_bd.racecard, #racecardlist table'));
                
                for (const table of tables) {
                    const rows = Array.from(table.querySelectorAll('tr'));
                    let headerFound = false;
                    let mapping = { saddle: 0, last_6: 1, horse: 3, weight: 4, jockey: 5, draw: 6, trainer: 7 };

                    for (const row of rows) {
                        const cells = Array.from(row.querySelectorAll('td, th'));
                        const cellTexts = cells.map(c => c.innerText.trim());
                        
                        // Identify Header Row
                        if (!headerFound && cellTexts.includes('Horse No.') && cellTexts.includes('Jockey')) {
                            headerFound = true;
                            mapping.saddle = cellTexts.indexOf('Horse No.');
                            mapping.horse = cellTexts.indexOf('Horse');
                            mapping.weight = cellTexts.indexOf('Wt.');
                            mapping.jockey = cellTexts.indexOf('Jockey');
                            mapping.draw = cellTexts.indexOf('Draw');
                            mapping.trainer = cellTexts.indexOf('Trainer');
                            mapping.last_6 = cellTexts.indexOf('Last 6 Runs');
                            continue;
                        }

                        // Process Data Rows
                        if (headerFound && cellTexts.length >= 8) {
                            const saddle = cellTexts[mapping.saddle];
                            if (!saddle || !/^\d+$/.test(saddle)) continue;

                            const horse = cellTexts[mapping.horse] ? cellTexts[mapping.horse].split('\n')[0].trim() : "";
                            if (!horse || horse === 'Horse') continue;

                            results.push({
                                saddle: saddle,
                                horse: horse,
                                last_6: cellTexts[mapping.last_6] || "",
                                weight: cellTexts[mapping.weight] || "",
                                jockey: cellTexts[mapping.jockey] || "",
                                draw: cellTexts[mapping.draw] || "",
                                trainer: cellTexts[mapping.trainer] || ""
                            });
                        }
                    }
                    if (results.length > 0) break; // Found the main table
                }
                return results;
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
                track_condition=track_condition,
                jump_time=jump_time,
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
