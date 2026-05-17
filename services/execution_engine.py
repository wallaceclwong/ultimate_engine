import asyncio
import os
import json
from pathlib import Path
from typing import Optional
import time
import sys

from loguru import logger

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import Config
from services.browser_manager import BrowserManager

class ExecutionEngine:
    def __init__(self, dry_run=True, headless=False, session_id="default"):
        self.dry_run = dry_run
        self.headless = headless
        self.session_id = session_id
        self.browser_mgr = BrowserManager(headless=headless)
        self.login_url = "https://bet.hkjc.com/en/racing/wp/"
        
    async def prepare_bet_slip(self, date_str, venue, race_no, selection: str, stake: float):
        """
        Selection: Horse number (e.g., "5")
        Stake: Dollar amount to bet.
        """
        logger.info(f"Preparing Bet: Race {race_no}, Selection #{selection}, Stake ${stake}...")
        
        context, page = await self.browser_mgr.get_persistent_context(session_id=self.session_id)
        
        try:
            # 1. Navigate to betting page
            # Fixed: Navigate to base URL first to avoid redirects, then handle deep navigation
            base_url = "https://bet.hkjc.com/en/racing/wp/"
            logger.info(f"Navigating to {base_url}...")
            await page.goto(base_url, wait_until="networkidle", timeout=60000)
            await page.bring_to_front()
            
            # Ensure we are on the RACING tab
            logger.info("Verifying Racing tab...")
            try:
                # Top header 'RACING' button - wait for it to be visible
                racing_tab = await page.wait_for_selector(".Header-Menu-Racing", timeout=10000)
                if racing_tab:
                    logger.info("Found Racing tab button. Clicking...")
                    await racing_tab.click(force=True)
                    await asyncio.sleep(3)
            except Exception as e:
                logger.info(f"Racing tab click attempt finished: {e}")
            
            # 2. Handle Login if needed
            logger.info("Checking login status...")
            try:
                login_acc_selector = "#login-account-input"
                login_pwd_selector = "#login-password-input"
                login_btn_selector = "#login-submit"

                await page.wait_for_selector(f"{login_acc_selector}, .account-info", timeout=15000)
                login_input = await page.query_selector(login_acc_selector)
                
                if login_input:
                    logger.info(f"Not logged in. Filling credentials for {Config.HKJC_ACCOUNT[:4]}****...")
                    if Config.HKJC_ACCOUNT and Config.HKJC_ACCOUNT != "YOUR_ACCOUNT_ID":
                        # Type credentials (more reliable than fill for some sites)
                        await page.type(login_acc_selector, Config.HKJC_ACCOUNT, delay=50)
                        await page.type(login_pwd_selector, Config.HKJC_PASSWORD, delay=50)
                        
                        await page.screenshot(path="data/pre_login_click.png")
                        
                        logger.info("Submitting login form via Click...")
                        # Try multiple login button selectors
                        login_selectors = [login_btn_selector, "text='Login'", ".login-btn", "button:has-text('Login')"]
                        clicked = False
                        for sel in login_selectors:
                            try:
                                btn = await page.query_selector(sel)
                                if btn and await btn.is_visible():
                                    logger.info(f"Clicking login button: {sel}")
                                    await btn.click(force=True)
                                    clicked = True
                                    break
                            except Exception: pass
                        
                        if not clicked:
                            logger.warning("Could not find Login button. Attempting Enter key as last resort.")
                            await page.keyboard.press("Enter")
                        
                        # Wait for either navigation or the T&C modal
                        logger.info("Waiting for login response/modals (8s)...")
                        await asyncio.sleep(8)
                        await page.bring_to_front()
                        
                    else:
                        logger.warning("HKJC_ACCOUNT not configured.")
                else:
                    logger.info("Already logged in.")
                
                # Debug screenshot
                await page.screenshot(path="data/login_state.png")
            except Exception as login_e:
                logger.warning(f"Login check error: {login_e}")

            # 2. Wait for Login + Handle T&C
            logger.info("Waiting for login success (OTP or manual)...")
            logged_in = await self.wait_for_login_success(page)
            if not logged_in:
                raise Exception("Login verification failed or timed out.")
            
            # Handle potential T&C/Disclaimer modals that often block betting after login
            await self.handle_tc_modals(page)
            
            # 3. Select Race
            logger.info(f"Verifying Race {race_no}...")
            try:
                # Verified selector: .race-no-item or #raceno_X
                race_selectors = [
                    f"div.race-no-item:has-text('{race_no}')",
                    f"#raceno_{race_no}",
                    f"div.raceno-btn:has-text('{race_no}')",
                    f"text='{race_no}'"
                ]
                race_btn = None
                for sel in race_selectors:
                    try:
                        race_btn = await page.wait_for_selector(sel, timeout=3000)
                        if race_btn: break
                    except Exception: continue

                if race_btn:
                    logger.info(f"Clicking Race {race_no} button...")
                    await race_btn.click(force=True)
                    logger.info(f"Race {race_no} selected.")
                    await asyncio.sleep(3)
                else:
                    logger.warning(f"Could not find Race {race_no} button. Attempting direct URL navigation.")
                
                await asyncio.sleep(2)
            except Exception as race_e:
                logger.error(f"Race selection failed: {race_e}")
            
            # 4. Select Horse
            logger.info(f"Selecting Horse #{selection} in Race {race_no}...")
            try:
                found = False
                for attempt in range(5):
                    # 1. Try precise ID first
                    win_checkbox_sel = f"#wpleg_WIN_{race_no}_{selection}"
                    btn = await page.query_selector(win_checkbox_sel)
                    if btn:
                        logger.info(f"[{attempt}] Found precise Win checkbox: {win_checkbox_sel}")
                        await btn.click(force=True)
                        found = True
                        break
                    
                    # 2. Search row
                    logger.info(f"[{attempt}] searching for horse {selection} via text...")
                    rows = await page.query_selector_all("tr")
                    for row in rows:
                        inner = await row.inner_text()
                        if inner.strip().startswith(str(selection)) or f"\t{selection}\t" in inner:
                            logger.info(f"Found row for Horse {selection}. Clicking...")
                            bet_box = await row.query_selector("div.bet-checkbox, .checkbox-area, td:nth-child(7)")
                            if bet_box:
                                await bet_box.click(force=True)
                            else:
                                await row.click()
                            found = True
                            break
                    if found: break
                    await asyncio.sleep(2)
                
                if not found:
                    raise Exception(f"Could not select Horse #{selection}")

                await asyncio.sleep(2)
            except Exception as horse_e:
                logger.error(f"Horse selection failed: {horse_e}")

            # 5. Set Stake
            logger.info(f"Setting stake to ${stake}...")
            try:
                await asyncio.sleep(3)
                stake_selectors = [
                    "input.unitBetInput",
                    "input.OfInnerInput.unitBetInput",
                    ".unit-bet-input",
                    "#unit-bet",
                    "input[title='Unit Bet']"
                ]
                
                stake_input = None
                for attempt in range(5):
                    for sel in stake_selectors:
                        stake_input = await page.query_selector(sel)
                        if not stake_input:
                            for frame in page.frames:
                                stake_input = await frame.query_selector(sel)
                                if stake_input: break
                        if stake_input and await stake_input.is_visible(): break
                    
                    if stake_input and await stake_input.is_visible():
                        logger.info(f"Found stake input. Filling ${stake}...")
                        await stake_input.click(force=True)
                        await page.keyboard.press("Control+A")
                        await page.keyboard.press("Backspace")
                        await stake_input.type(str(int(stake)), delay=100)
                        await page.keyboard.press("Enter")
                        break
                    await asyncio.sleep(2)
                
                # Add button
                add_btn_sel = ".addSlip, .AddToSlip, .AddBtn, .AddSlipBtn-Content, .btn_add, text='Add', button:has-text('Add')"
                for attempt in range(5):
                    add_btn = await page.query_selector(add_btn_sel)
                    if not add_btn:
                        for frame in page.frames:
                            add_btn = await frame.query_selector(add_btn_sel)
                            if add_btn: break
                    
                    if add_btn and await add_btn.is_visible():
                        logger.info(f"Clicking Add to Slip (Attempt {attempt})...")
                        await add_btn.click(force=True)
                        await asyncio.sleep(3)
                        
                        slip_check = await page.query_selector(".TotalNoOfBets, .bet-count, text='Place Bet', #betslip-container")
                        if slip_check:
                            logger.success("Add confirmed via slip detection.")
                            break
                    await asyncio.sleep(2)
                
                await page.screenshot(path="data/final_slip_check.png")
            except Exception as stake_e:
                logger.error(f"Stake/Add failed: {stake_e}")
            
            if self.dry_run:
                logger.success("DRY RUN: Slip prepared. Browser open for confirmation.")
            else:
                logger.warning("LIVE MODE: (Manual intervention recommended)")
                
        except Exception as e:
            logger.error(f"Error during execution: {e}")
            await page.screenshot(path="data/execution_error.png")
        finally:
            if self.headless:
                await context.close()
            else:
                logger.info("[STAGING COMPLETE] Window left open for manual check (600s).")
                await page.bring_to_front()
                await asyncio.sleep(600)

    async def wait_for_login_success(self, page, timeout=120):
        start_time = time.time()
        while (time.time() - start_time) < timeout:
            try:
                if await page.query_selector(".account-info, #account-balance, .member-info"):
                    logger.success("Login success detected!")
                    return True
                
                otp_indicators = ["text='Verification Code'", "text='SMS OTP'", "#otp_input", ".otp-dialog"]
                for indicator in otp_indicators:
                    if await page.query_selector(indicator):
                        logger.info(f"OTP/Verification screen detected ({indicator}). Waiting for user...")
                        await asyncio.sleep(5)
                        break
            except Exception: pass
            await asyncio.sleep(2)
        return False

    async def handle_tc_modals(self, page):
        logger.info("Checking for blocking modals...")
        tc_selectors = [
            "#btnProceed", "button:has-text('Proceed')", "button:has-text('Agree')", "button:has-text('Confirm')",
            "text='Proceed'", "text='Agree'", "text='Confirm'", ".btn_agree", "#btn-agree"
        ]
        for attempt in range(5):
            found_modal = False
            for frame in page.frames:
                for sel in tc_selectors:
                    try:
                        btn = await frame.query_selector(sel)
                        if btn and await btn.is_visible():
                            logger.info(f"[{attempt}] Found modal button ({sel}). Clicking...")
                            await btn.click(force=True)
                            await asyncio.sleep(3)
                            found_modal = True
                            break
                    except Exception: pass
                if found_modal: break
            if not found_modal: break
            await asyncio.sleep(1)

async def main():
    import argparse
    parser = argparse.ArgumentParser(description="HKJC Betting Execution Engine")
    parser.add_argument("--date", type=str, required=True)
    parser.add_argument("--venue", type=str, default="ST")
    parser.add_argument("--race", type=int, default=1)
    parser.add_argument("--selection", type=str, required=True)
    parser.add_argument("--stake", type=float, default=10.0)
    parser.add_argument("--headless", action="store_true", help="Run in headless mode")
    args = parser.parse_args()

    engine = ExecutionEngine(dry_run=True, headless=args.headless)
    await engine.prepare_bet_slip(args.date, args.venue, args.race, args.selection, args.stake)

if __name__ == "__main__":
    asyncio.run(main())
