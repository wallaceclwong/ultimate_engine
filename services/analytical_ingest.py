import asyncio
from playwright.async_api import async_playwright
from datetime import datetime
import json
import os
import sys
import re

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.browser_manager import BrowserManager

class AnalyticalIngest:
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
            # Strategy 1: Look for a link/button whose ENTIRE text is the race number
            all_links = await page.query_selector_all("a, button")
            for link in all_links:
                txt = (await link.inner_text()).strip()
                # Exact match only — avoid "1" matching "10", "11", "12"
                if txt == str(race_no):
                    await link.click()
                    await page.wait_for_timeout(2000)
                    return True

            # Strategy 2: Try clicking a tab via its href containing RaceNo=N
            tab = await page.query_selector(f"a[href*='RaceNo={race_no}']")
            if tab:
                await tab.click()
                await page.wait_for_timeout(2000)
                return True

        except Exception as e:
            print(f"Race tab click failed: {e}")
        return False

    async def fetch_analytical_data(self, date_str, venue="ST", race_no=1, page=None):
        """
        Extracts sectional times and horse weights from the results page.
        """
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        
        # Guard: Don't fetch results for future dates
        if dt.date() > datetime.now().date():
            print(f"Skipping analytical data: {date_str} is in the future.")
            return None

        formatted_date = dt.strftime("%Y/%m/%d")
        # Modern URL format
        url = f"https://racing.hkjc.com/en-us/local/information/localresults?racedate={formatted_date}&Racecourse={venue}&RaceNo={race_no}"
        
        own_page = False
        if not page:
            page = await self.browser_mgr.get_page()
            own_page = True
        
        try:
            # OPTIMIZATION: Check if we are already on the meeting page
            current_url = page.url
            target_date_param = f"RaceDate={formatted_date}"
            target_course_param = f"Racecourse={venue}"
            
            needs_nav = True
            if target_date_param in current_url and target_course_param in current_url:
                # We specifically check for information/localresults OR analytical part
                # The HKJC site often stays on localresults and just updates the view
                print(f"Already on meeting page for {formatted_date} {venue}. Skipping full navigation...")
                needs_nav = False

            force_tab_click = not needs_nav
            if needs_nav:
                # Standard headers
                await page.set_extra_http_headers({
                    "Accept-Language": "en-US,en;q=0.9",
                    "Referer": "https://racing.hkjc.com/racing/information/english/Racing/LocalResults.aspx"
                })
                
                # Navigate — use domcontentloaded and catch timeout gracefully
                print(f"Navigating to {url}...")
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                except Exception as e:
                    print(f"Warning: Navigation timed out ({str(e)[:80]}), proceeding to parse...")

            # Check if the page actually has the requested date
            page_content = await page.content()
            page_date_pattern = dt.strftime("%d/%m/%Y")
            if page_date_pattern not in page_content:
                print(f"Warning: Requested date {page_date_pattern} not found on page. Skipping.")
                if own_page:
                    await page.close()
                return None

            # Try to find the performance table — if not there, click the race tab
            table_found = False
            try:
                # If we skipped navigation, we MUST click the tab because the page might be on the wrong race
                if force_tab_click:
                    raise Exception("Force tab click requested")

                await page.wait_for_selector("table.performance, div.performance table", timeout=8000)
                table_found = True
                print("Performance table already present.")
            except Exception:
                print("Clicking race selection to trigger load...")
                clicked = await self._click_race_tab(page, race_no)
                if clicked:
                    try:
                        await page.wait_for_selector("table.performance, div.performance table", timeout=12000)
                        table_found = True
                        print("Performance table loaded after tab click.")
                    except Exception:
                        print("Performance table still not found after tab click.")
                else:
                    print("Could not click race tab.")

            # 1. Extract Race Sectionals (from summary table)
            times = []
            tables = await page.query_selector_all("table")
            for table in tables:
                text = await table.inner_text()
                if "Sectional Time" in text:
                    time_cols = await table.query_selector_all("td.f_tac")
                    for col in time_cols:
                        t_txt = (await col.inner_text()).strip()
                        main_time = t_txt.split('\n')[0].strip()
                        if main_time and (main_time.replace('.', '').isdigit()):
                            times.append(main_time)
                    if times:
                        break
            
            # 2. Extract Horse-specific Analytics
            horse_analytics = []
            if table_found:
                performance_div = await page.query_selector("div.performance")
                if performance_div:
                    performance_table = await performance_div.query_selector("table")
                    if performance_table:
                        rows = await performance_table.query_selector_all("tbody tr")
                        print(f"Analyzing {len(rows)} potential horse rows...")
                        for row in rows:
                            cols = await row.query_selector_all("td")
                            if len(cols) >= 11:
                                horse_no_raw = (await cols[1].inner_text()).strip()
                                horse_no = horse_no_raw.split()[0] if horse_no_raw else ""
                                if not horse_no.isdigit():
                                    continue
                                act_wt = (await cols[5].inner_text()).strip()
                                decl_wt = (await cols[6].inner_text()).strip()
                                pos_col = cols[9]
                                pos_divs = await pos_col.query_selector_all("div div")
                                positions = []
                                for div in pos_divs:
                                    p_txt = (await div.inner_text()).strip()
                                    if p_txt:
                                        positions.append(p_txt)
                                sectional_pos = " ".join(positions)
                                horse_analytics.append({
                                    "horse_no": horse_no,
                                    "act_weight": act_wt,
                                    "decl_weight": decl_wt,
                                    "sectional_pos": sectional_pos
                                })
                else:
                    print("Performance div NOT found for horse analytics.")
            
            # 3. Extract Granular Sectional Times (non-blocking, short timeout)
            try:
                d_obj = datetime.strptime(date_str, "%Y-%m-%d")
                ddmmyyyy_date = d_obj.strftime("%d/%m/%Y")
                sectional_url = f"https://racing.hkjc.com/en-us/local/information/displaysectionaltime?racedate={ddmmyyyy_date}&RaceNo={race_no}"

                print(f"Fetching Granular Sectionals: {sectional_url}")
                try:
                    await page.goto(sectional_url, wait_until="domcontentloaded", timeout=30000)
                    await page.wait_for_selector("table.table_bd.race_table", timeout=20000)

                    sectional_rows = await page.query_selector_all("table.table_bd.race_table tbody tr")
                    print(f"Found {len(sectional_rows)} sectional rows.")
                    
                    for s_row in sectional_rows:
                        s_cols = await s_row.query_selector_all("td")
                        if len(s_cols) >= 3:
                            h_no_raw = (await s_cols[1].inner_text()).strip()
                            if h_no_raw.isdigit():
                                for b_horse in horse_analytics:
                                    if b_horse["horse_no"] == h_no_raw:
                                        ind_times = []
                                        for idx in range(3, len(s_cols)):
                                            cell_text = (await s_cols[idx].inner_text()).strip()
                                            cell_class = (await s_cols[idx].get_attribute("class") or "")
                                            if "f_tar" in cell_class:
                                                continue
                                            lines = [line.strip() for line in cell_text.split('\n') if line.strip()]
                                            for line in lines:
                                                if re.match(r'^\d+\.\d+$', line):
                                                    ind_times.append(line)
                                                    break
                                        b_horse["individual_sectionals"] = ind_times
                                        break
                except Exception as e:
                    print(f"Warning: Could not fetch granular sectionals. {str(e)[:80]}")
            except Exception as e:
                print(f"Warning: Sectional URL generation failed. {str(e)[:80]}")

            if own_page:
                await page.close()
            return {
                "race_id": f"{date_str}_{venue}_R{race_no}",
                "race_sectionals": times,
                "horse_analytics": horse_analytics
            }
        except Exception as e:
            print(f"Error fetching analytical data: {e}")
            if own_page:
                await page.close()
            return None

async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Ingest HKJC Analytical Data")
    parser.add_argument("--date", type=str, default="2026-03-11", help="Date in YYYY-MM-DD format")
    parser.add_argument("--venue", type=str, default="HV", help="Venue (ST or HV)")
    parser.add_argument("--race", type=int, default=1, help="Race number")
    args = parser.parse_args()

    ingest = AnalyticalIngest()
    print(f"Fetching analytical data for {args.date} {args.venue} R{args.race}...")
    data = await ingest.fetch_analytical_data(args.date, venue=args.venue, race_no=args.race)
    
    if data:
        print(f"Successfully fetched analytical data for {data['race_id']}")
        os.makedirs("data/analytical", exist_ok=True)
        filename = f"data/analytical/analytical_{data['race_id']}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"Analytical data saved to {filename}")
    else:
        print("Failed to fetch analytical data.")

if __name__ == "__main__":
    asyncio.run(main())
