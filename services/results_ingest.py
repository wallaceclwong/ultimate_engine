import asyncio
import re
import json
import os
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.browser_manager import BrowserManager

try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class ResultsIngest:
    def __init__(self, headless=True, browser_mgr=None):
        self.headless = headless
        self.browser_mgr = browser_mgr or BrowserManager(headless=headless)

    async def _click_race_tab(self, page, race_no: int) -> bool:
        """
        Clicks the race number tab on the HKJC results page.
        Uses exact text match to avoid ambiguity (e.g. "1" matching "10", "11").
        Returns True if clicked successfully.
        """
        try:
            # Strategy 1: Exact text match on links/buttons
            all_links = await page.query_selector_all("a, button")
            for link in all_links:
                txt = (await link.inner_text()).strip()
                if txt == str(race_no):
                    await link.click()
                    await page.wait_for_timeout(2000)
                    return True

            # Strategy 2: href containing RaceNo=N
            tab = await page.query_selector(f"a[href*='RaceNo={race_no}']")
            if tab:
                await tab.click()
                await page.wait_for_timeout(2000)
                return True

        except Exception as e:
            print(f"Race tab click failed: {e}")
        return False

    async def fetch_results(self, date_str, venue="ST", race_no=1, page=None):
        """
        Fetches race results, dividends, and incidents.
        """
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        
        if dt.date() > datetime.now().date():
            print(f"Skipping results: {date_str} is in the future.")
            return None

        formatted_date = dt.strftime("%Y/%m/%d")
        url = f"https://racing.hkjc.com/en-us/local/information/localresults?racedate={formatted_date}&Racecourse={venue}&RaceNo={race_no}"
        
        own_page = False
        if not page:
            page = await self.browser_mgr.get_page()
            own_page = True
        
        print(f"Fetching Results: {url}")
        try:
            # OPTIMIZATION: Check if we are already on the meeting page
            current_url = page.url
            target_date_param = f"RaceDate={formatted_date}"
            target_course_param = f"Racecourse={venue}"
            
            needs_nav = True
            if target_date_param in current_url and target_course_param in current_url:
                print(f"Already on meeting page for {formatted_date} {venue}. Skipping full navigation...")
                needs_nav = False
            
            force_tab_click = not needs_nav
            if needs_nav:
                print(f"Navigating to {url}...")
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                except Exception as e:
                    print(f"Warning: Navigation timed out ({str(e)[:80]}), proceeding to parse...")
            
            # Check if page has the right date
            page_content = await page.content()
            page_date_pattern = dt.strftime("%d/%m/%Y")
            if page_date_pattern not in page_content:
                print(f"Warning: Expected date {page_date_pattern} not found on page.")

            results = []
            dividends = {"WIN": [], "PLACE": [], "QUINELLA": [], "QUINELLA PLACE": []}
            incidents = []
            stewards_report = ""

            # Try to find performance table — if not there, click race tab
            table_found = False
            try:
                # If we skipped navigation, we MUST click the tab because the page might be on the wrong race
                if force_tab_click:
                    raise Exception("Force tab click requested")
                
                await page.wait_for_selector("div.performance, table.performance", timeout=8000)
                table_found = True
                print("Waiting 1s for rendering...")
                await page.wait_for_timeout(1000)
            except Exception:
                print("Clicking race selection to trigger load...")
                clicked = await self._click_race_tab(page, race_no)
                if clicked:
                    try:
                        await page.wait_for_selector("div.performance, table.performance", timeout=12000)
                        table_found = True
                        print("Performance table loaded after race tab click.")
                    except Exception:
                        print("Performance table still not found after race tab click.")

            # 1. Scrape Results Table — try multiple selectors
            row_selectors = [
                "div.performance tbody tr",
                "table.performance tbody tr",
                "div[class*='performance'] tbody tr",
            ]
            rows = []
            for sel in row_selectors:
                rows = await page.query_selector_all(sel)
                if rows:
                    break

            for row in rows:
                cols = await row.query_selector_all("td")
                if len(cols) >= 10:
                    try:
                        results.append({
                            "plc": (await cols[0].inner_text()).strip(),
                            "horse_no": (await cols[1].inner_text()).strip(),
                            "horse": (await cols[2].inner_text()).strip(),
                            "jockey": (await cols[3].inner_text()).strip(),
                            "trainer": (await cols[4].inner_text()).strip(),
                            "actual_wt": (await cols[5].inner_text()).strip(),
                            "declar_wt": (await cols[6].inner_text()).strip(),
                            "draw": (await cols[7].inner_text()).strip(),
                            "lbw": (await cols[8].inner_text()).strip(),
                            "finish_time": (await cols[10].inner_text()).strip() if len(cols) > 10 else "",
                            "win_odds": (await cols[11].inner_text()).strip() if len(cols) > 11 else ""
                        })
                    except:
                        continue

            # Retry once on empty results
            if not results and table_found:
                print("Empty results on first parse — waiting 3s and retrying...")
                await page.wait_for_timeout(3000)
                for sel in row_selectors:
                    rows = await page.query_selector_all(sel)
                    if rows:
                        break
                for row in rows:
                    cols = await row.query_selector_all("td")
                    if len(cols) >= 10:
                        try:
                            results.append({
                                "plc": (await cols[0].inner_text()).strip(),
                                "horse_no": (await cols[1].inner_text()).strip(),
                                "horse": (await cols[2].inner_text()).strip(),
                                "jockey": (await cols[3].inner_text()).strip(),
                                "trainer": (await cols[4].inner_text()).strip(),
                                "actual_wt": (await cols[5].inner_text()).strip(),
                                "declar_wt": (await cols[6].inner_text()).strip(),
                                "draw": (await cols[7].inner_text()).strip(),
                                "lbw": (await cols[8].inner_text()).strip(),
                                "finish_time": (await cols[10].inner_text()).strip() if len(cols) > 10 else "",
                                "win_odds": (await cols[11].inner_text()).strip() if len(cols) > 11 else ""
                            })
                        except:
                            continue

            # 2. Scrape Dividends - Parse from text content
            content = await page.inner_text("body")
            lines = content.split('\n')
            
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                
                # Look for dividend section
                if line == "Dividend":
                    # Next line should be the table header
                    if i + 1 < len(lines) and "Pool" in lines[i + 1]:
                        # Skip header line
                        i += 2
                        # Now parse the dividend rows
                        while i < len(lines):
                            row = lines[i].strip()
                            if not row or row == "Dividend Note:":
                                break
                            
                            parts = row.split()
                            if len(parts) >= 3:
                                # Check if first part is a pool type
                                if parts[0] in ["WIN", "PLACE", "QUINELLA", "QUINELLA PLACE"]:
                                    pool = parts[0]
                                    if pool == "WIN":
                                        if len(parts) >= 3:
                                            comb = parts[1]
                                            div = parts[2]
                                            dividends["WIN"].append({"combination": comb, "dividend": div})
                                    elif pool == "PLACE":
                                        # PLACE has multiple combinations
                                        j = 1
                                        while j < len(parts) - 1:
                                            comb = parts[j]
                                            div = parts[j + 1]
                                            dividends["PLACE"].append({"combination": comb, "dividend": div})
                                            j += 2
                                    elif pool == "QUINELLA":
                                        if len(parts) >= 3:
                                            comb = parts[1]
                                            div = parts[2]
                                            dividends["QUINELLA"].append({"combination": comb, "dividend": div})
                                    elif pool == "QUINELLA PLACE":
                                        # QUINELLA PLACE has multiple combinations
                                        j = 1
                                        while j < len(parts) - 1:
                                            comb = parts[j]
                                            div = parts[j + 1]
                                            dividends["QUINELLA PLACE"].append({"combination": comb, "dividend": div})
                                            j += 2
                            i += 1
                    else:
                        i += 1
                else:
                    i += 1

            # 3. Stewards Report
            report_div = await page.query_selector("div.race_incident_report")
            if report_div:
                stewards_report = (await report_div.inner_text()).strip()
                incident_table = await report_div.query_selector("table")
                if incident_table:
                    inc_rows = await incident_table.query_selector_all("tr")
                    for r in inc_rows:
                        c = await r.query_selector_all("td")
                        if len(c) >= 4:
                            h_no = (await c[1].inner_text()).strip()
                            if h_no.isdigit():
                                incidents.append({
                                    "horse_no": h_no,
                                    "incident": (await c[3].inner_text()).strip()
                                })

            print(f"Scraped {len(results)} results for {date_str}_{venue}_R{race_no}.")
            if own_page:
                await page.close()
            return {
                "race_id": f"{date_str}_{venue}_R{race_no}",
                "results": results,
                "dividends": dividends,
                "incidents": incidents,
                "stewards_report": stewards_report
            }

        except Exception as e:
            print(f"Error fetching results: {e}")
            if own_page:
                try:
                    await page.close()
                except:
                    pass
            return None

async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Ingest HKJC Race Results")
    parser.add_argument("--date", type=str, required=True)
    parser.add_argument("--venue", type=str, default="ST")
    parser.add_argument("--race", type=int, default=1)
    args = parser.parse_args()

    ingest = ResultsIngest()
    print(f"Fetching results for {args.date} {args.venue} R{args.race}...")
    data = await ingest.fetch_results(args.date, venue=args.venue, race_no=args.race)
    if data:
        print(f"Success: {data['race_id']} — {len(data['results'])} horses")
        os.makedirs("data/results", exist_ok=True)
        filename = f"data/results/results_{data['race_id']}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"Results saved to {filename}")
    else:
        print("Failed to fetch results.")

if __name__ == "__main__":
    asyncio.run(main())
