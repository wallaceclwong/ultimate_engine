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
                # New HKJC website structure: need to click "SETUP MY STARTER LIST" button
                # Find button containing "SETUP" or "STARTER"
                try:
                    buttons = await page.query_selector_all('a, button, div[onclick], span')
                    for btn in buttons:
                        btn_text = await btn.inner_text()
                        if 'SETUP' in btn_text and 'STARTER' in btn_text:
                            print("[RACECARD] Found SETUP MY STARTER LIST button, clicking...")
                            await btn.click()
                            await page.wait_for_timeout(3000)
                            break
                except Exception as e:
                    print(f"[RACECARD] Setup button click failed: {e}")
                
                # Check again for tables after click
                tables = await page.query_selector_all("table")
                for t in tables:
                    text = await t.inner_text()
                    if "Horse No." in text and "Jockey" in text:
                        print("[RACECARD] Found horse table after setup button click.")
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

            # --- Extract race header from confirmed HKJC selector div.f_fs13 ---
            # Format: 'Turf, "B" Course, 1200M, Good' (no 'Going:' prefix on live site)
            race_header_text = ""
            try:
                header_el = await page.query_selector("div.f_fs13")
                if header_el:
                    race_header_text = (await header_el.inner_text()).strip()
                    print(f"[RACECARD] Race header: {race_header_text!r}")
            except Exception as e:
                print(f"[RACECARD] Could not extract race header element: {e}")

            # --- Parse Distance from header (e.g. '1200M') or fall back to body text ---
            dist_match = re.search(r'(\d{3,5})M', race_header_text or content_text, re.IGNORECASE)
            distance = int(dist_match.group(1)) if dist_match else 1200

            # --- Parse Track Type from header ---
            if "All Weather" in (race_header_text or content_text) or "AWT" in (race_header_text or content_text):
                track_type = "All Weather Track"
            elif "Turf" in (race_header_text or content_text):
                track_type = "Turf"

            # --- Parse Course letter (A / B / C / C+3) ---
            course_match = re.search(r'"([A-C](?:\+\d)?)"\s*Course', race_header_text or content_text, re.IGNORECASE)
            if course_match:
                course = course_match.group(1).upper()

            # --- Parse Class/Rating ---
            class_match = re.search(r'(Class \d|Griffin|Group \d)', race_header_text or content_text)
            if class_match:
                race_class = class_match.group(1)

            # --- Parse Track Condition (Going) ---
            # Strategy 1: last comma-separated token on the header line (confirmed HKJC format)
            GOING_KEYWORDS = {
                "WET FAST": "Wet",
                "WET SLOW": "Wet",
                "WET":      "Wet",
                "SOFT":     "Soft",
                "YIELDING": "Yielding",
                "GOOD TO YIELDING": "Yielding",
                "GOOD TO FIRM": "Good",
                "FIRM":     "Good",
                "GOOD":     "Good",
            }
            track_condition = "Unknown"
            if race_header_text:
                # The header can span multiple lines; going is on the line with the distance
                for line in race_header_text.splitlines():
                    if re.search(r'\d+M', line, re.IGNORECASE):   # distance line
                        tokens = [t.strip(' "') for t in line.split(',')]
                        # Try longest match first (e.g. 'GOOD TO YIELDING' before 'GOOD')
                        joined = " ".join(tokens).upper()
                        for kw, norm in sorted(GOING_KEYWORDS.items(), key=lambda x: -len(x[0])):
                            if kw in joined:
                                track_condition = norm
                                break
                        break

            # Strategy 2: regex fallback on full body text
            if track_condition == "Unknown":
                going_patterns = [
                    r'Going\s*:?\s*([A-Z][A-Z\s]{2,20})',      # 'Going: GOOD' or 'Going GOOD'
                    r'(?:^|,|\s)((?:WET FAST|WET SLOW|WET|GOOD TO YIELDING|GOOD TO FIRM|YIELDING|SOFT|FIRM|GOOD))(?=,|\s|$)',
                ]
                for pat in going_patterns:
                    m = re.search(pat, content_text, re.IGNORECASE | re.MULTILINE)
                    if m:
                        raw = m.group(1).strip().upper()
                        for kw, norm in sorted(GOING_KEYWORDS.items(), key=lambda x: -len(x[0])):
                            if kw in raw:
                                track_condition = norm
                                break
                        if track_condition != "Unknown":
                            break

            if track_condition == "Unknown":
                track_condition = "Good"   # final safe default
                print("[RACECARD] Going not detected; defaulting to 'Good'.")
            else:
                print(f"[RACECARD] Track condition: {track_condition}")

            # --- Parse Jump Time ---
            jump_time = "13:00"
            time_match = re.search(r'(\d{1,2}:\d{2}\s?(?:AM|PM)?)', race_header_text or content_text)
            if time_match:
                jump_time = time_match.group(1).strip()

            # --- Precise HKJC Layout Extraction ---
            horses_data = await page.evaluate(r'''() => {
                const results = [];
                // Target the main racecard table specifically
                const tables = Array.from(document.querySelectorAll('table.starter, table.table_bd.racecard, #racecardlist table'));
                
                for (const table of tables) {
                    const rows = Array.from(table.querySelectorAll('tr'));
                    let headerFound = false;
                    let mapping = { saddle: 0, last_6: 1, horse: 3, weight: 4, jockey: 5, draw: 6, trainer: 7, gear: -1 };

                    for (const row of rows) {
                        const cells = Array.from(row.querySelectorAll('td, th'));
                        const cellTexts = cells.map(c => c.innerText.trim());
                        
                        // Identify Header Row
                        if (!headerFound && cellTexts.includes('Horse No.') && cellTexts.includes('Jockey')) {
                            headerFound = true;
                            mapping.saddle = cellTexts.indexOf('Horse No.');
                            mapping.horse  = cellTexts.indexOf('Horse');
                            mapping.weight = cellTexts.indexOf('Wt.');
                            mapping.jockey = cellTexts.indexOf('Jockey');
                            mapping.draw   = cellTexts.indexOf('Draw');
                            mapping.trainer = cellTexts.indexOf('Trainer');
                            mapping.last_6 = cellTexts.indexOf('Last 6 Runs');
                            // Gear column header varies: "Gear", "Equipment", "Rtg."
                            const gearIdx = cellTexts.findIndex(t => t === 'Gear' || t === 'Equipment');
                            if (gearIdx !== -1) mapping.gear = gearIdx;
                            continue;
                        }

                        // Process Data Rows
                        if (headerFound && cellTexts.length >= 8) {
                            const saddle = cellTexts[mapping.saddle];
                            if (!saddle || !/^\d+$/.test(saddle)) continue;

                            const horse = cellTexts[mapping.horse] ? cellTexts[mapping.horse].split('\n')[0].trim() : "";
                            if (!horse || horse === 'Horse') continue;

                            // Gear: grab text content; also try to read img alt tags for icon-only cells
                            let gearText = mapping.gear >= 0 ? (cellTexts[mapping.gear] || "") : "";
                            if (!gearText && mapping.gear >= 0) {
                                // Fallback: read alt attributes from gear icons
                                const gearCell = cells[mapping.gear];
                                if (gearCell) {
                                    const imgs = gearCell.querySelectorAll('img[alt]');
                                    gearText = Array.from(imgs).map(i => i.alt.trim()).filter(Boolean).join(",");
                                }
                            }

                            results.push({
                                saddle:  saddle,
                                horse:   horse,
                                last_6:  cellTexts[mapping.last_6] || "",
                                weight:  cellTexts[mapping.weight] || "",
                                jockey:  cellTexts[mapping.jockey] || "",
                                draw:    cellTexts[mapping.draw] || "",
                                trainer: cellTexts[mapping.trainer] || "",
                                gear:    gearText,
                            });
                        }
                    }
                    if (results.length > 0) break; // Found the main table
                }
                return results;
            }''')

            # Known HKJC gear codes and their meanings (for AI prompt context)
            GEAR_CODES = {
                "B":  "Blinkers",
                "BO": "Blinkers Off",
                "CO": "Cap Off",
                "CP": "Cheek Pieces",
                "E":  "Ear Muffs",
                "HS": "Hood (Start)",
                "P":  "Pacifiers",
                "PC": "Pacifiers+Cheek Pieces",
                "SR": "Shadow Roll",
                "TT": "Tongue Tie",
                "V":  "Visor",
                "VO": "Visor Off",
                "XB": "Cross Blinkers",
            }

            horses = []
            for h in horses_data:
                saddle_number = int(h['saddle'])
                last_6 = [r.strip() for r in h['last_6'].split('/') if r.strip()]

                # Horse name and HKJC brand ID (e.g. "ALWAYS FLUKE (H256)")
                horse_name = h['horse'].split('(')[0].strip()
                brand_id = "N/A"
                brand_match = re.search(r'\(([^)]+)\)', h['horse'])
                if brand_match:
                    raw_id = brand_match.group(1)
                    brand_id = raw_id  # Keep as-is (e.g. "H256" or "CTC")

                # Detect Conghua Training Centre horses — they carry "(CTC)" in name
                training_location = "CTC" if "CTC" in h['horse'].upper() else "HK"

                # Jockey allowance — extract BEFORE stripping (e.g. "H Bentley(-3)" → -3)
                jockey_raw = h['jockey']
                allowance = 0
                allowance_match = re.search(r'\((-?\d+)\)', jockey_raw)
                if allowance_match:
                    allowance = int(allowance_match.group(1))
                jockey = re.sub(r'\(-?\d+\)', '', jockey_raw).strip()

                # Gear — expand codes to human-readable string for AI
                raw_gear = h.get('gear', '').strip()
                if raw_gear:
                    # Some pages show comma-separated codes, some show concatenated ("BTT")
                    codes = [c.strip().upper() for c in re.split(r'[,/\s]+', raw_gear) if c.strip()]
                    expanded = [GEAR_CODES.get(c, c) for c in codes if c]
                    gear_str = ", ".join(expanded) if expanded else raw_gear
                else:
                    gear_str = ""

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
                    weight_allowance=allowance,
                    trainer=h['trainer'],
                    weight=weight,
                    last_6_runs=last_6,
                    gear=gear_str,
                    training_location=training_location,
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
