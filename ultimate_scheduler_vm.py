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
from services.live_odds_monitor import get_live_odds_monitor
from services.stewards_lookup import get_stewards_lookup
import pytz

# Configuration
HKT = pytz.timezone('Asia/Hong_Kong')
BASE_DIR = Path(__file__).parent.absolute()
FIXTURES_FILE = BASE_DIR / "data" / "fixtures_season.json"
PYTHON_EXEC = sys.executable
STATE_FILE = BASE_DIR / "data" / "scheduler_state.json"
LOCK_FILE = BASE_DIR / "ultimate_scheduler.lock"

# Cache for get_today_fixture() to avoid re-reading JSON every 60s
_today_fixture_cache = None
_today_fixture_cache_date = None

# Held open for the lifetime of --live mode; released on process exit
_lock_fd = None


def acquire_lock():
    """Single-instance guard for --live mode using atomic file locking.

    Uses O_CREAT|O_EXCL for an atomic creation test — if the lock file
    already exists, we check whether the owning PID is still alive.
    Stale locks (dead PIDs) are removed and retried.

    Also kills any non-venv Python duplicates as a safety net.
    """
    global _lock_fd
    import psutil
    current_pid = os.getpid()
    try:
        parent_pid = psutil.Process(current_pid).ppid()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        parent_pid = -1

    # ── Kill non-venv dupes (safety net) ──────────────────────────────
    venv_py = str(BASE_DIR / ".venv" / "Scripts" / "python.exe").lower()
    for proc in psutil.process_iter(['pid', 'cmdline', 'exe']):
        try:
            if proc.info['pid'] in (current_pid, parent_pid):
                continue
            exe = (proc.info.get('exe') or '').lower()
            if 'python' not in exe:
                continue
            cmd = " ".join(proc.info['cmdline'] or [])
            if 'ultimate_scheduler_vm' not in cmd or '--live' not in cmd:
                continue
            if not psutil.pid_exists(proc.info['pid']):
                continue
            if exe != venv_py:
                try:
                    proc.kill()
                    print(f"[FIX] Killed non-venv war room duplicate PID {proc.info['pid']} ({exe})")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # ── Atomic lock file acquisition ──────────────────────────────────
    while True:
        try:
            _lock_fd = os.open(str(LOCK_FILE), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(_lock_fd, str(current_pid).encode())
            os.fsync(_lock_fd)
            return  # lock acquired
        except FileExistsError:
            pass

        # Lock file exists — check if the owner is still alive
        try:
            stale_pid = int(LOCK_FILE.read_text().strip())
        except (ValueError, OSError):
            stale_pid = None

        if stale_pid and not psutil.pid_exists(stale_pid):
            # Stale lock — remove and retry
            try:
                LOCK_FILE.unlink()
            except OSError:
                pass
            continue

        # Another live instance holds the lock
        print(f"[EXIT] War room already running (PID {stale_pid}). Duplicate suppressed.")
        sys.exit(0)
    return True

def load_scheduler_state():
    today = datetime.now(HKT).strftime("%Y-%m-%d")
    default_state = {"audited_races": [], "audited_horses": {}, "learned_today": False, "last_reset_date": today}
    if STATE_FILE.exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            try:
                state = json.load(f)
                # Ensure new key exists
                if "audited_horses" not in state:
                    state["audited_horses"] = {}
                # Reset if it's a new day
                if state.get("last_reset_date") != today:
                    print(f"[SYSTEM] New day detected ({today}): Resetting scheduler state.")
                    save_scheduler_state(default_state)
                    return default_state
                return state
            except (json.JSONDecodeError, KeyError):
                pass
    return default_state

def save_scheduler_state(state):
    """Atomically write scheduler state — write to temp then os.replace."""
    os.makedirs(STATE_FILE.parent, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, STATE_FILE)

def get_dynamic_schedule():
    """Reads all racecard files for today to build a jump-time map."""
    today_compact = datetime.now(HKT).strftime("%Y%m%d")
    schedule = {}
    for r in range(1, 14):
        rc_file = BASE_DIR / "data" / f"racecard_{today_compact}_R{r}.json"
        if rc_file.exists():
            try:
                with open(rc_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    jt = data.get("jump_time")
                    if jt:
                        schedule[r] = jt
            except (json.JSONDecodeError, KeyError, OSError):
                pass
    return schedule

def get_today_fixture():
    """Checks if today is a race day based on the season fixtures.
    Results are cached per calendar day to avoid re-parsing JSON every 60s."""
    global _today_fixture_cache, _today_fixture_cache_date

    if not FIXTURES_FILE.exists():
        print(f"[ERROR] Fixtures file not found: {FIXTURES_FILE}")
        return None

    now = datetime.now(HKT)
    today_str = now.strftime("%Y-%m-%d")
    if _today_fixture_cache_date == today_str:
        return _today_fixture_cache

    # Format options to match fixtures like "8/04/2026" or "08/04/2026"
    d, m, y = now.day, now.month, now.year
    possible_dates = [
        f"{d}/{m:02d}/{y}",
        f"{d:02d}/{m:02d}/{y}",
        f"{d}/{m}/{y}",
        f"{d:02d}/{m}/{y}"
    ]

    with open(FIXTURES_FILE, "r", encoding="utf-8") as f:
        fixtures = json.load(f)
        for fxt in fixtures:
            if fxt["date"] in possible_dates:
                print(f"[DEBUG] Fixture found: {fxt['venue']} on {fxt['date']}")
                _today_fixture_cache = fxt
                _today_fixture_cache_date = today_str
                return fxt
    print(f"[DEBUG] No fixture match for possible dates: {possible_dates}")
    _today_fixture_cache = None
    _today_fixture_cache_date = today_str
    return None

async def run_final_war_room_verdict(r_no, today_iso, venue, j_time):
    """
    Final War Room Verdict: fires EXACTLY ONE alert per race at T-15 minutes.
    If the top Kelly pick clears the threshold, runs DeepSeek and sends a BET alert.
    Otherwise, sends a NO BET alert.
    """
    try:
        # ── Load prediction JSON (primary data source) ──────────────────────
        # (dedup is handled by the caller pre-marking the state before spawning)
        pred_file = BASE_DIR / "data" / "predictions" / f"prediction_{today_iso}_{venue}_R{r_no}.json"
        if not pred_file.exists():
            print(f"[FINAL VERDICT] R{r_no}: prediction file missing, skipping.")
            return

        with open(pred_file, "r", encoding="utf-8") as f:
            pred = json.load(f)

        market_odds = pred.get("market_odds", {})
        probabilities = pred.get("probabilities", {})
        is_best_bet = pred.get("is_best_bet", False)
        is_wet = pred.get("wet_track", False)

        # Use top probability horse as our pick (Kelly disabled until proven track record)
        if not probabilities:
            print(f"[FINAL VERDICT] R{r_no}: no probabilities found.")
            return
        top_horse = max(probabilities, key=probabilities.get)
        odds = float(market_odds.get(top_horse, 0))
        prob = float(probabilities.get(top_horse, 0))
        fair_odds = round(1 / prob, 2) if prob > 0 else 99.0
        edge = (odds / fair_odds - 1) if fair_odds > 0 and odds > 1 else -1.0

        if not is_best_bet:
            print(f"[FINAL VERDICT] R{r_no}: NO BET (below threshold).")
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
                "rank":       1 if h_no == top_horse else 0,
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
        horse_name = df[df["horse_no"] == top_horse]["horse_name"].iloc[0] if not df[df["horse_no"] == top_horse].empty else f"#{top_horse}"

        wet_note = " | ⚠️ WET TRACK (reduced confidence)" if is_wet else ""
        print(f"[FINAL VERDICT] R{r_no}: #{top_horse} {horse_name} CONFIRMED (edge={edge:+.1%}, odds={odds:.1f}){wet_note}. Firing pre-race audit...")

        # ── Live odds movement (late money detection) ──────────────────────
        market_context = None
        try:
            odds_monitor = get_live_odds_monitor()
            state = odds_monitor.update_race_state(today_iso, venue, r_no)
            if state and top_horse in state.movements:
                m = state.movements[top_horse]
                market_context = {"movement": m.movement_pct, "trend": m.trend}
                print(f"[LATE MONEY] #{top_horse}: {m.trend} ({m.movement_pct:+.1%}) "
                      f"from {m.initial_odds} -> {m.current_odds}")
        except Exception as e:
            print(f"[LATE MONEY] Skipped — {e}")

        # ── Stewards historical incident lookup ────────────────────────────
        stewards_context = None
        try:
            stewards_lookup = get_stewards_lookup()
            stewards_context = stewards_lookup.get_horse_risk_profile(horse_name)
            if stewards_context.get("has_history"):
                risk = stewards_context.get("risk", "?")
                n_inc = len(stewards_context.get("recent_incidents", []))
                print(f"[STEWARDS] {horse_name}: risk={risk}, {n_inc} recent incidents")
        except Exception as e:
            print(f"[STEWARDS] Skipped — {e}")

        verdict, reasoning = await consensus_agent.get_consensus(
            df, top_horse, market_context, stewards_context
        )

        icon = "🏆" if ("Grade [S]" in reasoning or "Grade [A]" in reasoning) else "⚠️"
        await telegram_service.send_message(
            f"{icon} *WAR ROOM VERDICT: {venue} R{r_no}*\n"
            f"🎯 *Pick:* #{top_horse} {horse_name}\n"
            f"📊 *Edge:* Odds {odds:.1f} | Fair {fair_odds:.1f} | EV {edge:+.1%}{wet_note}\n"
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

async def run_analytical(venue: str):
    """Triggers analytical data ingestion for all races."""
    print(f"[{datetime.now(HKT)}] --- STARTING ANALYTICAL DATA INGEST ({venue}) ---")
    script = BASE_DIR / "services" / "analytical_ingest.py"
    today_iso = datetime.now(HKT).strftime("%Y-%m-%d")
    
    # Fetch analytical data for all races (1-11)
    success_count = 0
    for race_no in range(1, 12):
        retcode, stdout, stderr = await run_async_command(
            [PYTHON_EXEC, str(script), "--date", today_iso, "--venue", venue, "--race", str(race_no)],
            "ANALYTICAL"
        )
        if retcode == 0:
            success_count += 1
    
    print(f"[ANALYTICAL] {success_count}/11 races processed")

async def run_weather(venue: str):
    """Triggers weather intelligence generation."""
    print(f"[{datetime.now(HKT)}] --- STARTING WEATHER INTEL ({venue}) ---")
    script = BASE_DIR / "services" / "generate_weather_intel.py"
    today_iso = datetime.now(HKT).strftime("%Y-%m-%d")
    
    retcode, stdout, stderr = await run_async_command(
        [PYTHON_EXEC, str(script), "--date", today_iso, "--venue", venue],
        "WEATHER"
    )
    
    if retcode == 0:
        print(f"[WEATHER] Intelligence generated successfully")
    else:
        print(f"[WEATHER] Failed to generate intelligence")

async def run_odds_refresh(venue: str):
    """
    Updates win/place odds in the existing prediction files without re-running the AI.
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
            except (json.JSONDecodeError, OSError):
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

            # Kelly stakes disabled until proven track record — always empty
            pred["market_odds"] = win_odds
            pred["kelly_stakes"] = {}

            # Re-evaluate is_best_bet using top horse edge vs threshold
            # confidence_score is value_edge (0.0-0.80), NOT win probability
            rc_file = BASE_DIR / "data" / f"racecard_{today_compact}_R{r_no}.json"
            is_wet = False
            if rc_file.exists():
                rc_data = json.loads(rc_file.read_text(encoding="utf-8"))
                tc = rc_data.get("track_condition", "Good").upper()
                is_wet = any(w in tc for w in {"WET", "SOFT", "YIELDING", "HEAVY", "SLOW"})

            bet_threshold = 0.25 if is_wet else 0.15
            pred["wet_track"] = is_wet
            pred["is_best_bet"] = pred.get("confidence_score", 0) >= bet_threshold

            pred_file.write_text(
                json.dumps(pred, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            patched += 1
            best_flag = "BET" if pred["is_best_bet"] else "   "
            top = max(probs.items(), key=lambda x: x[1]) if probs else ("?", 0)
            top_odds = win_odds.get(top[0], "?")
            print(f"  [{best_flag}] R{r_no}: top=#{top[0]} prob={top[1]:.1%} odds={top_odds} edge={pred.get('confidence_score',0):+.1%}")
        except Exception as e:
            print(f"  [ERROR] R{r_no} patch failed: {e}")

    await ingest.browser_mgr.stop()
    summary = f"[ODDS REFRESH] {scraped} races scraped, {patched} predictions updated with live odds."
    print(summary)
    await telegram_service.send_message(f"*Morning Odds Refresh*: {scraped} races scraped, {patched} predictions updated with live odds.")

async def run_predict(venue):
    """Triggers the pre-race predictions and DeepSeek audit."""
    print(f"[{datetime.now(HKT)}] --- STARTING PRE-RACE PREDICTIONS ---")
    today_iso = datetime.now(HKT).strftime("%Y-%m-%d")
    script = BASE_DIR / "predict_today.py"
    cmd = [PYTHON_EXEC, str(script), today_iso, venue]
    
    returncode, stdout, stderr = await run_async_command(cmd, "PREDICT")
    
    if returncode == 0:
        print(f"[PREDICT] Predictions generated for {venue}. War Room Verdicts will fire at T-15 per race.")
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

    # 3. Matrix Update (Training Data Append)
    print(f"[LEARN] Step 3: Updating Master Matrix...")
    script_learn = BASE_DIR / "scripts" / "learn_today.py"
    cmd2 = [PYTHON_EXEC, str(script_learn), today_iso, venue]
    rc2, out2, err2 = await run_async_command(cmd2, "LEARN-MATRIX")

    if rc2 == 0:
        print(f"[LEARN] SUCCESS: Matrix updated for {venue}.")
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

    try:
        print(f"[{datetime.now(HKT)}] --- STARTING LIVE WAR ROOM (Venue: {venue}) ---")

        # Check health of dependencies before starting
        ds_ok = await consensus_agent.check_health()

        if not ds_ok:
            status_msg = f"🚨 *Lunar Alert*: War Room started but DeepSeek is DOWN ❌"
            await telegram_service.send_message(status_msg)
        else:
            await telegram_service.send_message(f"📡 *Lunar War Room*: Active for {venue}.\n- DeepSeek: ✅\nWaiting for Smart Money signatures...")

        # Load dynamic schedule
        schedule = get_dynamic_schedule()
        today_iso = datetime.now(HKT).strftime("%Y-%m-%d")

        # Pre-emptively capture baseline for all races to avoid 'market blindness'
        print(f"[{datetime.now(HKT)}] [WAR ROOM] Capturing initial baseline snapshots for all races...")
        for r_no in schedule.keys():
            try:
                await ingest.capture_snapshot(today_iso, int(r_no), venue)
            except Exception:
                pass

        while True:
            now = datetime.now(HKT)
            today_iso = now.strftime("%Y-%m-%d")
            today_compact = today_iso.replace("-", "")
            hkt_now = now.strftime("%H:%M")

            # EXIT CLEANLY if we've crossed into a new non-race day
            if not get_today_fixture():
                print(f"[{now}] War Room shutting down: no longer a race day.")
                await telegram_service.send_message("🌙 *War Room*: Race day complete. Shutting down.")
                break

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
                        final_key = f"final_verdict_R{r_no}"
                        if not state.get(final_key):
                            # Pre-mark to prevent duplicate firing from subsequent loop iterations
                            state[final_key] = True
                            save_scheduler_state(state)
                            task = asyncio.create_task(run_final_war_room_verdict(r_no, today_iso, venue, j_time))
                            task.add_done_callback(
                                lambda t, r=r_no: print(f"[ERROR] War Room verdict R{r} raised: {t.exception()}")
                                if t.exception() else None
                            )
                except Exception as e:
                    print(f"[WARN] Schedule parse error for R{r_no} ({j_time}): {e}")

            # 2. Check for Post-Race Learning (23:15 HKT)
            # state is already disk-fresh from load_scheduler_state() above (line 457)
            if now.hour == 23 and now.minute >= 15 and not state.get("learned_today"):
                success = await run_learn(venue)
                if success:
                    state["learned_today"] = True
                    save_scheduler_state(state)

            # Every 60 seconds
            print(f"[{now.strftime('%H:%M:%S')}] Polling market for anomalies...")
            await asyncio.sleep(60)
    finally:
        print(f"[{datetime.now(HKT)}] Cleaning up browser...")
        try:
            await ingest.browser_mgr.stop()
        except Exception as e:
            print(f"[WARN] Browser cleanup failed: {e}")

async def run_scrape(venue: str = None):
    """
    Triggers the racecard scraper for all races on today's meeting.
    Called by --noon mode to fetch racecard data before predictions.
    """
    fxt = get_today_fixture()
    if not fxt:
        print("[SCRAPE] No fixture today, skipping scrape.")
        return
    v = venue or fxt["venue"]
    print(f"[{datetime.now(HKT)}] --- STARTING NOON RACECARD SCRAPE ({v}) ---")
    today_iso = datetime.now(HKT).strftime("%Y-%m-%d")
    script = BASE_DIR / "scripts" / "smart_racecard_fetcher.py"
    if not script.exists():
        print(f"[SCRAPE] ERROR: smart_racecard_fetcher.py not found at {script}")
        return
    retcode, stdout, stderr = await run_async_command(
        [PYTHON_EXEC, str(script), "--date", today_iso, "--venue", v],
        "SCRAPE"
    )
    if retcode == 0:
        print(f"[SCRAPE] Racecards fetched successfully for {v}.")
    else:
        print(f"[SCRAPE] ERROR: Racecard fetch failed.\n{stderr[:200]}")

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
            with open(FIXTURES_FILE, "r", encoding="utf-8") as f:
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
            # Data availability check before predictions
            today_iso = datetime.now(HKT).strftime("%Y-%m-%d")
            date_compact = today_iso.replace("-", "")
            
            # Check odds data
            odds_dir = BASE_DIR / "data" / "odds"
            odds_files = list(odds_dir.glob(f"snapshot_*_R*.json")) if odds_dir.exists() else []
            
            # Check analytical data
            analytical_dir = BASE_DIR / "data" / "analytical"
            analytical_files = list(analytical_dir.glob(f"analytical_{today_iso}_*.json")) if analytical_dir.exists() else []
            
            print(f"[PREDICT CHECK] Odds files: {len(odds_files)}, Analytical files: {len(analytical_files)}")
            
            if len(odds_files) < 3:
                print("[PREDICT] WARNING: Insufficient odds data. Predictions may be degraded.")
            if len(analytical_files) < 3:
                print("[PREDICT] WARNING: Insufficient analytical data. Predictions may be degraded.")
            
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
        state = load_scheduler_state()
        if state.get("learned_today"):
            print("[LEARN] Already completed today (learned_today=True). Skipping duplicate run.")
        else:
            fxt = get_today_fixture()
            venue_l = fxt['venue'] if fxt else "ST"
            success = await run_learn(venue_l)
            if success:
                state["learned_today"] = True
                save_scheduler_state(state)
            
    elif mode == "--odds":
        fxt = get_today_fixture()
        if fxt:
            await run_odds_refresh(fxt["venue"])
        else:
            print("Skipping odds refresh: Not a local race day.")

    elif mode == "--analytical":
        fxt = get_today_fixture()
        if fxt:
            await run_analytical(fxt["venue"])
        else:
            print("Skipping analytical ingest: Not a local race day.")

    elif mode == "--weather":
        fxt = get_today_fixture()
        if fxt:
            await run_weather(fxt["venue"])
        else:
            print("Skipping weather intel: Not a local race day.")

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else None
    if mode == "--live":
        _lock = acquire_lock() # Hold lock for entire process lifetime
    asyncio.run(main())
