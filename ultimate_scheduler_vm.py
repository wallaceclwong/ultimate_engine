import os
import sys
import json
import asyncio
import subprocess
from datetime import datetime
from pathlib import Path
import pandas as pd
from telegram_service import telegram_service
from consensus_agent import consensus_agent
from services.memory_service import memory_service
import pytz

# Configuration
HKT = pytz.timezone('Asia/Hong_Kong')
BASE_DIR = Path(__file__).parent.absolute()
FIXTURES_FILE = BASE_DIR / "data" / "fixtures_season.json"
PYTHON_EXEC = sys.executable  # Cross-platform (Windows/Linux)
STATE_FILE = BASE_DIR / "data" / "scheduler_state.json"
LOCK_FILE = BASE_DIR / "ultimate_scheduler.lock"

def acquire_lock():
    """Single-instance guard for --live mode.
    - Kills any non-venv Python duplicates immediately.
    - Yields to an existing venv instance (lowest PID wins).
    """
    import psutil
    current_pid = os.getpid()
    try:
        parent_pid = psutil.Process(current_pid).ppid()
    except:
        parent_pid = -1

    venv_py = str(BASE_DIR / ".venv" / "Scripts" / "python.exe").lower()
    venv_rivals = []

    for proc in psutil.process_iter(['pid', 'cmdline', 'exe']):
        try:
            if proc.info['pid'] in (current_pid, parent_pid):
                continue
            cmd = " ".join(proc.info['cmdline'] or [])
            if 'ultimate_scheduler_vm' not in cmd or '--live' not in cmd:
                continue
            exe = (proc.info.get('exe') or '').lower()
            if exe != venv_py:
                proc.kill()
                print(f"[FIX] Killed non-venv war room duplicate PID {proc.info['pid']} ({exe})")
            else:
                venv_rivals.append(proc.info['pid'])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if venv_rivals and min(venv_rivals) < current_pid:
        print(f"[EXIT] Venv war room already running (PID {min(venv_rivals)}). Duplicate suppressed.")
        sys.exit(0)

    LOCK_FILE.write_text(str(current_pid))
    return True

def load_scheduler_state():
    today = datetime.now(HKT).strftime("%Y-%m-%d")
    default_state = {"audited_races": [], "audited_horses": {}, "learned_today": False, "last_reset_date": today}
    if STATE_FILE.exists():
        with open(STATE_FILE, "r") as f:
            try:
                state = json.load(f)
                # Ensure new key exists
                if "audited_horses" not in state:
                    state["audited_horses"] = {}
                # Reset if it's a new day
                if state.get("last_reset_date") != today:
                    print(f"[SYSTEM] New day detected ({today}): Resetting scheduler state.")
                    return default_state
                return state
            except: pass
    return default_state

def save_scheduler_state(state):
    os.makedirs(STATE_FILE.parent, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def get_dynamic_schedule():
    """Reads all racecard files for today to build a jump-time map."""
    today_compact = datetime.now(HKT).strftime("%Y%m%d")
    schedule = {}
    for r in range(1, 14):
        rc_file = BASE_DIR / "data" / f"racecard_{today_compact}_R{r}.json"
        if rc_file.exists():
            try:
                with open(rc_file, "r") as f:
                    data = json.load(f)
                    jt = data.get("jump_time")
                    if jt:
                        schedule[r] = jt
            except: pass
    return schedule

def get_today_fixture():
    """Checks if today is a race day based on the season fixtures."""
    if not FIXTURES_FILE.exists():
        print(f"[ERROR] Fixtures file not found: {FIXTURES_FILE}")
        return None
        
    now = datetime.now(HKT)
    # Format options to match fixtures like "8/04/2026" or "08/04/2026"
    d, m, y = now.day, now.month, now.year
    possible_dates = [
        f"{d}/{m:02d}/{y}",   # 8/04/2026
        f"{d:02d}/{m:02d}/{y}", # 08/04/2026
        f"{d}/{m}/{y}",       # 8/4/2026
        f"{d:02d}/{m}/{y}"    # 08/4/2026
    ]
    
    with open(FIXTURES_FILE, "r") as f:
        fixtures = json.load(f)
        for fxt in fixtures:
            if fxt["date"] in possible_dates:
                print(f"[DEBUG] Fixture found: {fxt['venue']} on {fxt['date']}")
                return fxt
    print(f"[DEBUG] No fixture match for possible dates: {possible_dates}")
    return None

async def run_final_war_room_verdict(r_no, today_iso, venue, j_time):
    """
    Final War Room Verdict: fires EXACTLY ONE alert per race at T-15 minutes.
    If the top Kelly pick clears the threshold, runs DeepSeek and sends a BET alert.
    Otherwise, sends a NO BET alert.
    """
    try:
        state = load_scheduler_state()
        final_verdict_key = f"final_verdict_R{r_no}"
        if state.get(final_verdict_key):
            return  # Already fired for this race

        # ── Load prediction JSON (primary data source) ──────────────────────
        pred_file = BASE_DIR / "data" / "predictions" / f"prediction_{today_iso}_{venue}_R{r_no}.json"
        if not pred_file.exists():
            print(f"[FINAL VERDICT] R{r_no}: prediction file missing, skipping.")
            return

        with open(pred_file, "r", encoding="utf-8") as f:
            pred = json.load(f)

        market_odds = pred.get("market_odds", {})
        kelly_stakes = pred.get("kelly_stakes", {})
        probabilities = pred.get("probabilities", {})

        # Check for Kelly stake
        has_kelly = any(v >= 10 for v in kelly_stakes.values())
        top_kelly_horse = None
        edge = 0.0
        odds = 0.0
        prob = 0.0

        if has_kelly:
            top_kelly_horse = max(kelly_stakes, key=kelly_stakes.get)
            odds = float(market_odds.get(top_kelly_horse, 0))
            prob = float(probabilities.get(top_kelly_horse, 0))
            edge = prob * odds - 1 if odds > 1 else -1.0

        if not has_kelly or edge <= 0.05 or odds <= 6.0:
            print(f"[FINAL VERDICT] R{r_no}: NO BET (below threshold).")
            state[final_verdict_key] = True
            save_scheduler_state(state)
            await telegram_service.send_message(
                f"⛔ *WAR ROOM VERDICT: {venue} R{r_no}*\n"
                f"⏱ *Jump:* {j_time} HKT\n\n"
                f"No horses meet the value/edge threshold. *NO BET*."
            )
            return

        # ── Load racecard to build the DataFrame consensus_agent needs ──────
        today_compact = today_iso.replace("-", "")
        rc_file = BASE_DIR / "data" / f"racecard_{today_compact}_R{r_no}.json"
        if not rc_file.exists():
            print(f"[FINAL VERDICT] R{r_no}: racecard missing, cannot build field context.")
            return

        with open(rc_file, "r", encoding="utf-8") as f:
            rc = json.load(f)

        horses = rc.get("horses", [])
        rows = []
        for h in horses:
            h_no = str(h.get("horse_no") or h.get("saddle_number", ""))
            h_prob = float(probabilities.get(h_no, 0))
            h_odds = float(market_odds.get(h_no, 0)) if market_odds.get(h_no) else 99.0
            fair_odds = round(1 / h_prob, 1) if h_prob > 0 else 99.0
            value_mult = round(h_odds / fair_odds, 2) if fair_odds > 0 else 99.0

            rows.append({
                "horse_no": h_no,
                "horse_name": h.get("horse_name", h.get("name", f"Horse {h_no}")),
                "horse_id":   h.get("horse_id", ""),
                "win_odds":   h_odds,
                "fair_odds":  fair_odds,
                "value_mult": value_mult,
                "draw":       h.get("draw", h.get("barrier", 0)),
                "rank":       1 if h_no == top_kelly_horse else 0,
                "jockey":     h.get("jockey", ""),
                "trainer":    h.get("trainer", ""),
                "venue":      venue,
                "distance":   rc.get("distance", 1200),
                "track_type": rc.get("track_type", ""),
                "race":       r_no,
            })

        if not rows:
            print(f"[FINAL VERDICT] R{r_no}: no runners found in racecard.")
            return

        df = pd.DataFrame(rows)
        horse_name = df[df["horse_no"] == top_kelly_horse]["horse_name"].iloc[0] if not df[df["horse_no"] == top_kelly_horse].empty else f"#{top_kelly_horse}"

        print(f"[FINAL VERDICT] R{r_no}: #{top_kelly_horse} {horse_name} CONFIRMED (edge={edge:+.1%}, odds={odds:.1f}). Firing pre-race audit...")

        verdict, reasoning = await consensus_agent.get_consensus(df, top_kelly_horse)

        state[final_verdict_key] = True
        save_scheduler_state(state)

        icon = "🏆" if ("Grade [S]" in reasoning or "Grade [A]" in reasoning) else "⚠️"
        await telegram_service.send_message(
            f"{icon} *WAR ROOM VERDICT: {venue} R{r_no}*\n"
            f"🎯 *Pick:* #{top_kelly_horse} {horse_name}\n"
            f"📊 *Market Confirmed:* Odds {odds:.1f} | EV Edge {edge:+.1%}\n"
            f"⏱ *Jump:* {j_time} HKT\n\n"
            f"🧠 *DeepSeek Verdict:* {verdict}\n{reasoning}"
        )
    except Exception as e:
        print(f"[ERROR] Final Verdict failed for R{r_no}: {e}")

async def run_async_command(cmd, log_prefix="SYSTEM"):
    """Runs a command asynchronously without blocking the event loop."""
    print(f"[{datetime.now(HKT)}] [{log_prefix}] Executing: {' '.join(cmd)}")
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(BASE_DIR)
    )
    stdout, stderr = await process.communicate()
    return process.returncode, stdout.decode().strip(), stderr.decode().strip()

async def run_scrape():
    """Triggers the noon scraping of racecards."""
    print(f"[{datetime.now(HKT)}] --- STARTING NOON SCRAPE ---")
    script = BASE_DIR / "scripts" / "smart_racecard_fetcher.py"
    cmd = [PYTHON_EXEC, str(script)]
    
    returncode, stdout, stderr = await run_async_command(cmd, "SCRAPE")
    
    if returncode == 0:
        await telegram_service.send_message("✅ *Lunar Heartbeat*: Noon racecard & odds scraped successfully.")
    else:
        await telegram_service.send_message(f"⚠️ *Lunar Alert*: Scrape failed!\n{stderr[:100]}")


async def run_odds_refresh(venue: str):
    """
    Scrapes current morning odds for all races, then patches kelly_stakes
    in the existing prediction files without re-running the AI.
    Intended to run at ~09:30 HKT after HKJC publishes morning prices.
    """
    from services.odds_ingest import OddsIngest
    from config.settings import Config

    today_iso = datetime.now(HKT).strftime("%Y-%m-%d")
    today_compact = today_iso.replace("-", "")
    print(f"[{datetime.now(HKT)}] --- STARTING MORNING ODDS REFRESH ({venue}) ---")

    ingest = OddsIngest(headless=True)
    scraped, patched = 0, 0

    for r_no in range(1, 12):
        # 1. Scrape live odds snapshot
        try:
            ok = await ingest.capture_snapshot(today_iso, r_no, venue)
            if ok:
                scraped += 1
        except Exception as e:
            print(f"  [ERROR] Odds scrape R{r_no}: {e}")
            continue

        # 2. Load the freshest valid snapshot
        odds_dir = BASE_DIR / "data" / "odds"
        snaps = sorted(
            odds_dir.glob(f"snapshot_{today_compact}_R{r_no}_*.json"),
            key=lambda p: p.stat().st_mtime, reverse=True
        )
        win_odds = {}
        for snap in snaps:
            try:
                d = json.loads(snap.read_text(encoding="utf-8"))
                if d.get("win_odds"):
                    win_odds = {str(k): float(v) for k, v in d["win_odds"].items()}
                    break
            except:
                pass

        if not win_odds:
            print(f"  [SKIP] R{r_no}: snapshot empty — odds not yet published.")
            continue

        # 3. Patch kelly_stakes in the existing prediction file
        pred_file = BASE_DIR / "data" / "predictions" / f"prediction_{today_iso}_{venue}_R{r_no}.json"
        if not pred_file.exists():
            print(f"  [SKIP] R{r_no}: prediction file missing.")
            continue

        try:
            pred = json.loads(pred_file.read_text(encoding="utf-8"))
            probs = pred.get("probabilities", {})

            # Recalculate Kelly stakes with real odds
            edges = {}
            for h_id, p in probs.items():
                o = win_odds.get(h_id)
                if o and o > 1.0 and p > 0:
                    edge = (p * o - 1) / (o - 1)
                    if edge > Config.MIN_EDGE:
                        edges[h_id] = edge

            bankroll_file = BASE_DIR / "data" / "bankroll.json"
            bankroll = 9000.0
            if bankroll_file.exists():
                bk = json.loads(bankroll_file.read_text(encoding="utf-8"))
                bankroll = float(bk.get("current_bankroll", bk.get("bankroll", 9000.0)))

            kelly_stakes = {}
            for h_id, edge in sorted(edges.items(), key=lambda x: x[1], reverse=True):
                if len(kelly_stakes) >= 2:
                    break
                stake = max(10, int(bankroll * Config.KELLY_FRACTION * edge // 10) * 10)
                kelly_stakes[h_id] = float(stake)

            # Patch fields
            pred["market_odds"] = win_odds
            pred["kelly_stakes"] = kelly_stakes

            # Re-evaluate is_best_bet
            has_real_kelly = any(v >= 10 for v in kelly_stakes.values())
            pred["is_best_bet"] = (
                has_real_kelly
                and pred.get("confidence_score", 0) >= Config.MIN_CONFIDENCE
            )

            pred_file.write_text(
                json.dumps(pred, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            patched += 1
            best_flag = "BET" if pred["is_best_bet"] else "   "
            top = max(probs.items(), key=lambda x: x[1]) if probs else ("?", 0)
            top_odds = win_odds.get(top[0], "?")
            top_kelly = kelly_stakes.get(top[0], 0)
            print(f"  [{best_flag}] R{r_no}: top=#{top[0]} prob={top[1]:.1%} odds={top_odds} kelly=HK${top_kelly:.0f}")
        except Exception as e:
            print(f"  [ERROR] R{r_no} patch failed: {e}")

    await ingest.browser_mgr.stop()
    summary = f"📊 *Morning Odds Refresh*: {scraped} races scraped, {patched} predictions patched with real Kelly stakes."
    print(f"[ODDS REFRESH] {summary}")
    await telegram_service.send_message(summary)

async def run_predict(venue):
    """Triggers the pre-race predictions and DeepSeek audit."""
    print(f"[{datetime.now(HKT)}] --- STARTING PRE-RACE PREDICTIONS ---")
    today_iso = datetime.now(HKT).strftime("%Y-%m-%d")
    script = BASE_DIR / "predict_today.py"
    cmd = [PYTHON_EXEC, str(script), today_iso, venue]
    
    returncode, stdout, stderr = await run_async_command(cmd, "PREDICT")
    
    if returncode == 0:
        await telegram_service.send_message(f"🧠 *Lunar Intelligence*: Predictions generated for {venue}.\nCheck logs for full strategic brief.")
    else:
        await telegram_service.send_message(f"⚠️ *Vultr VM*: Prediction failed!\n{stderr[:100]}")

async def run_learn(venue):
    """Triggers the post-race ingestion and learning scripts."""
    print(f"[{datetime.now(HKT)}] --- STARTING POST-RACE LEARNING ---")
    today_iso = datetime.now(HKT).strftime("%Y-%m-%d")
    
    # 1. Fetch official results
    script_results = BASE_DIR / "scripts" / "batch_results.py"
    cmd1 = [PYTHON_EXEC, str(script_results), today_iso, venue]
    rc1, out1, err1 = await run_async_command(cmd1, "LEARN-RESULTS")
    
    if rc1 != 0:
        await telegram_service.send_message(f"⚠️ *Lunar Alert*: Results ingestion failed!\n{err1[:100]}")
        return False

    # 2. Enrich Pedigree Data
    script_pedigree = BASE_DIR / "scripts" / "scrape_pedigree.py"
    cmd_ped = [PYTHON_EXEC, str(script_pedigree), "--all"]
    rc_p, out_p, err_p = await run_async_command(cmd_ped, "LEARN-PEDIGREE")
    if rc_p == 0:
        print("[LEARN] Pedigree cache updated.")
    else:
        print(f"[ERROR] Pedigree Enrichment failed: {err_p}")

    # 3. Generate Narratives & Retrospectives (MemPalace Context)
    print(f"[LEARN] Step 3: Generating MemPalace Narratives & Retrospectives...")
    script_narrator = BASE_DIR / "scripts" / "mempalace_narrator.py"
    script_retro = BASE_DIR / "scripts" / "generate_retrospectives.py"
    
    await run_async_command([PYTHON_EXEC, str(script_narrator)], "NARRATOR")
    await run_async_command([PYTHON_EXEC, str(script_retro), today_iso, venue], "RETROSPECTIVES")

    # 4. Memory Sync (MemPalace Mining)
    from services.memory_service import memory_service
    print(f"[LEARN] Step 4: Mining new intelligence into Palace...")
    try:
        memory_service.mine(str(BASE_DIR / "data"))
        await telegram_service.send_message("🧠 *Lunar Memory*: Today's results, predictions, and features successfully mined into Palace.")
    except Exception as e:
        print(f"[MEMORY WARN] Mining failed: {e}")

    # 5. Matrix Update (Training Data Append)
    print(f"[LEARN] Step 5: Updating Master Matrix...")
    script_learn = BASE_DIR / "scripts" / "learn_today.py"
    cmd2 = [PYTHON_EXEC, str(script_learn), today_iso, venue]
    rc2, out2, err2 = await run_async_command(cmd2, "LEARN-MATRIX")

    if rc2 == 0:
        print(f"[LEARN] SUCCESS: Matrix updated.")
        await telegram_service.send_message(f"📚 *Lunar Learning*: Today's results ingested and matrix updated for {venue}. Self-learning cycle complete.")
        return True
    else:
        await telegram_service.send_message(f"⚠️ *Lunar Alert*: Learning logic failed!\n{err2[:100]}")
        return False

async def run_live_war_room(venue):
    """
    Main polling loop for Race Day.
    Checks the 'T-15 minute' window for each race and runs DeepSeek-R1 audits.
    """
    from services.live_audit_service import live_audit_service
    from services.odds_ingest import OddsIngest
    
    ingest = OddsIngest(headless=True)
    
    print(f"[{datetime.now(HKT)}] --- STARTING LIVE WAR ROOM (Venue: {venue}) ---")
    
    # Check health of dependencies before starting
    ds_ok = await consensus_agent.check_health()
    mem_ok = await check_mempalace()
    
    if not ds_ok or not mem_ok:
        status_msg = f"⚠️ *Lunar Alert*: War Room started with issues!\n- DeepSeek: {'✅' if ds_ok else '❌'}\n- MemPalace: {'✅' if mem_ok else '❌'}"
        await telegram_service.send_message(status_msg)
    else:
        await telegram_service.send_message(f"📡 *Lunar War Room*: Active for {venue}.\nWaiting for Smart Money signatures...")

    # Load dynamic schedule
    schedule = get_dynamic_schedule()
    today_iso = datetime.now(HKT).strftime("%Y-%m-%d")

    # Pre-emptively capture baseline for all races to avoid 'market blindness'
    print(f"[{datetime.now(HKT)}] [WAR ROOM] Capturing initial baseline snapshots for all races...")
    for r_no in schedule.keys():
        try:
            await ingest.capture_snapshot(today_iso, int(r_no), venue)
        except: pass

    while True:
        now = datetime.now(HKT)
        today_iso = now.strftime("%Y-%m-%d")
        today_compact = today_iso.replace("-", "")
        hkt_now = now.strftime("%H:%M")
        
        # REFRESH STATE: Re-read state in every loop iteration to ensure shared sync
        state = load_scheduler_state()
        
        for r_no, j_time in schedule.items():
            if str(r_no) in state["audited_races"]:
                continue
            
            # Simple HKT countdown (e.g. j_time = "13:00")
            try:
                j_dt = datetime.strptime(j_time.strip().replace(" ",""), "%H:%M")
                now_dt = datetime.strptime(hkt_now, "%H:%M")
                diff_min = (j_dt - now_dt).total_seconds() / 60
                
                # 0. LIVE ODDS INGESTION (Every 3 mins if within T-25)
                # We use a state check to prevent hammering the browser
                if 0 <= diff_min <= 25:
                    last_scrape = state.get(f"last_scrape_R{r_no}", 0)
                    if (now.timestamp() - last_scrape) > 180: # 3 minutes
                        print(f"[INGEST] Refreshing live odds for R{r_no}...")
                        await ingest.capture_snapshot(today_iso, int(r_no), venue)
                        state[f"last_scrape_R{r_no}"] = now.timestamp()
                        save_scheduler_state(state)
 

                # FINAL WAR ROOM VERDICT: T-20 to T-10 window
                if 10 <= diff_min <= 20:
                    asyncio.create_task(run_final_war_room_verdict(r_no, today_iso, venue, j_time))
            except Exception as e:
                print(f"[WARN] Schedule parse error for R{r_no} ({j_time}): {e}")
        
        # 2. Check for Post-Race Learning (23:15 HKT)
        if now.hour == 23 and now.minute >= 15 and not state.get("learned_today"):
            success = await run_learn(venue)
            if success:
                state["learned_today"] = True
                save_scheduler_state(state)
        
        # Every 60 seconds
        print(f"[{now.strftime('%H:%M:%S')}] Polling market for anomalies...")
        await asyncio.sleep(60)

async def check_mempalace():
    """Verify connectivity to the MemPalace vector store."""
    print(f"[{datetime.now(HKT)}] [CHECK] Verifying MemPalace connection...")
    try:
        status = memory_service.get_status()
        if status and "WING" in status:
            print("  [OK] MemPalace is online.")
            return True
        else:
            print("  [WARN] MemPalace unreachable or invalid.")
            return False
    except Exception as e:
        print(f"  [ERROR] MemPalace check failed: {e}")
        return False

async def check_deepseek():
    """Verify connectivity to the DeepSeek API."""
    print(f"[{datetime.now(HKT)}] [CHECK] Verifying DeepSeek API...")
    ok = await consensus_agent.check_health()
    if ok:
        print("  [OK] DeepSeek API is online.")
    else:
        print("  [WARN] DeepSeek API unreachable.")
    return ok

async def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else None
    
    if mode == "--status":
        fxt = get_today_fixture()
        today_str = datetime.now(HKT).strftime("%a %d %b")
        if fxt:
            venue_name = "Sha Tin" if fxt["venue"] == "ST" else "Happy Valley"
            msg = (
                f"🌅 *Good Morning — {today_str}*\n\n"
                f"🏇 *RACE DAY: {venue_name}* ({fxt['venue']})\n\n"
                f"📅 Schedule:\n"
                f"  09:30 Odds scrape\n"
                f"  12:00 Racecard scrape\n"
                f"  13:00 Predictions\n"
                f"  T-25 Live war room\n\n"
                f"_VM is online and ready._"
            )
        else:
            # Find next race day
            now = datetime.now(HKT)
            with open(FIXTURES_FILE, "r") as f:
                fixtures = json.load(f)
            next_fxt = None
            for fx in fixtures:
                try:
                    fx_date = datetime.strptime(fx["date"], "%d/%m/%Y").replace(tzinfo=HKT)
                    if fx_date.date() > now.date():
                        next_fxt = fx
                        break
                except Exception:
                    continue
            next_info = f"Next race: {next_fxt['date']} {next_fxt['venue']}" if next_fxt else "No upcoming fixture found"
            msg = (
                f"🌅 *Good Morning — {today_str}*\n\n"
                f"😴 *No racing today.*\n"
                f"📆 {next_info}\n\n"
                f"_VM is online. Rest day operations running._"
            )
        await telegram_service.send_message(msg)

    elif mode == "--check":
        fxt = get_today_fixture()
        if fxt:
            print(f"RACE DAY: {fxt['venue']} ({fxt['type']})")
        else:
            print("NO RACE TODAY")
        
        # Comprehensive Health Check
        await check_mempalace()
        await check_deepseek()
            
    elif mode == "--noon":
        fxt = get_today_fixture()
        if fxt:
            await run_scrape()
        else:
            print("Skipping noon scrape: Not a local race day.")
            
    elif mode == "--predict":
        fxt = get_today_fixture()
        if fxt:
            await run_predict(fxt['venue'])
        else:
            print("Skipping predictions: Not a local race day.")
            
    elif mode == "--live":
        fxt = get_today_fixture()
        if fxt:
            await run_live_war_room(fxt['venue'])
        else:
            print("Skipping Live War Room: Not a local race day.")
            
    elif mode == "--learn":
        fxt = get_today_fixture()
        if fxt:
            await run_learn(fxt['venue'])
        else:
            # Fallback for non-race days if forced
            await run_learn("ST")
            
    elif mode == "--odds":
        fxt = get_today_fixture()
        if fxt:
            await run_odds_refresh(fxt["venue"])
        else:
            print("Skipping odds refresh: Not a local race day.")

    elif mode == "--restday":
        fxt = get_today_fixture()
        if not fxt:
            print("NON-RACE DAY DETECTED. Triggering intensive Rest Day Orchestrator...")
            script_restday = BASE_DIR / "scripts" / "lunar_rest_day.py"
            await run_async_command([PYTHON_EXEC, str(script_restday)], "RESTDAY")
        else:
            print("Today is a Race Day! Skipping deep rest-day optimizations to preserve CPU.")

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else None
    if mode == "--live":
        _lock = acquire_lock() # Hold lock for entire process lifetime
    asyncio.run(main())
