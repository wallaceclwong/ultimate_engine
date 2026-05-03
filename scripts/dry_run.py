"""
Ultimate Engine v3 — Full Dry-Run
Validates all components, today's data, code fixes, and race-day timeline.
Run: python scripts/dry_run.py
"""
import json
import sys
import subprocess
from pathlib import Path
from datetime import datetime
import pytz
import pandas as pd

BASE  = Path(__file__).resolve().parent.parent
HKT   = pytz.timezone("Asia/Hong_Kong")
now   = datetime.now(HKT)
DATE  = "2026-04-29"
VENUE = "HV"
PROC  = BASE / "data" / "processed"
PRED  = BASE / "data" / "predictions"
DATA  = BASE / "data"
SEP   = "=" * 72

OK   = "[ OK ]"
FAIL = "[FAIL]"
WARN = "[WARN]"

results = {"pass": 0, "fail": 0, "warn": 0}

def chk(status, msg):
    if status is True:
        tag = OK;   results["pass"] += 1
    elif status is False:
        tag = FAIL; results["fail"] += 1
    else:
        tag = WARN; results["warn"] += 1
    print(f"  {tag}  {msg}")

# ─── HEADER ─────────────────────────────────────────────────────────
print()
print(SEP)
print("  ULTIMATE ENGINE v3  —  FULL DRY-RUN")
print(f"  Date  : {DATE}  |  Venue : {VENUE}  |  Now : {now.strftime('%H:%M HKT')}")
print(SEP)

# ─── 1. FIXTURE CHECK ───────────────────────────────────────────────
print("\n[ 1 ] FIXTURE CHECK")
fx_path = DATA / "fixtures_2026.json"
if fx_path.exists():
    fixtures = json.load(open(fx_path, encoding="utf-8"))
    d, m, y = now.day, now.month, now.year
    possible = [f"{d}/{m:02d}/{y}", f"{d:02d}/{m:02d}/{y}", f"{d}/{m}/{y}", f"{d:02d}/{m}/{y}"]
    fxt = next((f for f in fixtures if f["date"] in possible), None)
    chk(bool(fxt),
        f"Today in fixtures : {fxt['date']} {fxt['venue']} ({fxt.get('type','?')})" if fxt
        else "NOT found as a race day in fixtures_2026.json")
else:
    chk(False, "fixtures_2026.json not found")

# ─── 2. LOCAL FILES ─────────────────────────────────────────────────
print("\n[ 2 ] LOCAL FILES")
rc_files   = sorted(DATA.glob("racecard_20260429_R*.json"))
feat_files = sorted(PROC.glob("features_2026-04-29_HV_R*.parquet"))
pred_files = sorted(PRED.glob("prediction_2026-04-29_HV_R*.json"))
chk(len(rc_files) == 9,   f"Racecards (local) : {len(rc_files)}/9")
chk(len(feat_files) == 9, f"Features  (local) : {len(feat_files)}/9")
chk(len(pred_files) == 9, f"AI Preds  (local) : {len(pred_files)}/9")

# ─── 3. SCHEDULER STATE ─────────────────────────────────────────────
print("\n[ 3 ] SCHEDULER STATE")
state_path = DATA / "scheduler_state.json"
if state_path.exists():
    state = json.load(open(state_path))
    chk(state.get("last_reset_date") == DATE,
        f"Reset date        : {state.get('last_reset_date')} (expected {DATE})")
    chk(not state.get("learned_today", False),
        f"learned_today     : {state.get('learned_today')} (should be False)")
    chk(state.get("audited_races", []) == [],
        f"audited_races     : {state.get('audited_races')} (should be empty)")
    chk(isinstance(state.get("audited_horses"), dict),
        f"audited_horses    : dict with {len(state.get('audited_horses',{}))} entries")
else:
    chk(False, "scheduler_state.json not found")

# ─── 4. CODE FIX VERIFICATION ───────────────────────────────────────
print("\n[ 4 ] CODE FIX VERIFICATION")

def grep(path, needle):
    try:
        return needle in open(path, encoding="utf-8").read()
    except Exception:
        return False

sched  = BASE / "ultimate_scheduler_vm.py"
pred_f = BASE / "predict_today.py"
audit  = BASE / "services" / "live_audit_service.py"
odds   = BASE / "services" / "live_odds_monitor.py"
mem    = BASE / "services" / "memory_service.py"
start  = BASE / "scripts"  / "pc_startup.py"

chk(grep(sched,  "h_no = candidates_nos[0]"),              "scheduler : h_no extracted from candidates_nos")
chk(grep(sched,  "today_compact = today_iso.replace"),     "scheduler : today_compact defined before use")
chk(grep(sched,  "run_proactive_audit"),                   "scheduler : proactive audit function present")
chk(grep(sched,  "25 < diff_min <= 35"),                   "scheduler : T-35 proactive window added")
chk(grep(pred_f, "TEMPERATURE = 0.6"),                     "predict   : temperature raised 0.35 -> 0.6")
chk(grep(pred_f, 'summary["rank"] == 1'),                  "predict   : rank-1 tip filter active")
chk(grep(pred_f, "win_odds\"] <= 20"),                     "predict   : odds <=20 cap active")
chk(grep(audit,  "Path(__file__).parent.parent"),          "audit_svc : absolute features path")
chk(grep(odds,   "Path(__file__).parent.parent"),          "odds_mon  : absolute odds_dir path")
chk(grep(mem,    "except ImportError"),                    "mem_svc   : paramiko optional import")
chk(grep(start,  'encoding="utf-8", errors="replace"'),   "pc_start  : UTF-8 encoding fix")

# ─── 5. VM CONNECTIVITY ─────────────────────────────────────────────
print("\n[ 5 ] VM CONNECTIVITY")
try:
    r = subprocess.run(
        ["ssh", "-o", "ConnectTimeout=6", "-o", "BatchMode=yes",
         "root@100.109.76.69", "echo PONG"],
        capture_output=True, text=True, timeout=12
    )
    chk(r.returncode == 0, f"SSH ping VM       : {r.stdout.strip() or r.stderr.strip()[:50]}")
except Exception as e:
    chk(False, f"SSH ping VM       : {e}")

try:
    r2 = subprocess.run(
        ["ssh", "-o", "ConnectTimeout=6", "-o", "BatchMode=yes",
         "root@100.109.76.69",
         "ls /opt/ultimate_engine/data/processed/features_2026-04-29_HV_R*.parquet 2>/dev/null | wc -l"],
        capture_output=True, text=True, timeout=12
    )
    vm_n = r2.stdout.strip()
    chk(vm_n == "9", f"VM features       : {vm_n}/9 parquet files")
except Exception as e:
    chk(False, f"VM features       : {e}")

try:
    r3 = subprocess.run(
        ["ssh", "-o", "ConnectTimeout=6", "-o", "BatchMode=yes",
         "root@100.109.76.69",
         "cd /opt/ultimate_engine && python3 -c \"from consensus_agent import consensus_agent; import asyncio; print('DS:OK')\" 2>&1 | tail -1"],
        capture_output=True, text=True, timeout=20
    )
    ds_ok = "DS:OK" in r3.stdout
    chk(ds_ok, f"DeepSeek import   : {'OK' if ds_ok else r3.stdout.strip()[:60]}")
except Exception as e:
    chk(False, f"DeepSeek import   : {e}")

# ─── 6. TODAY'S ML PICKS TABLE ──────────────────────────────────────
print("\n[ 6 ] TODAY'S ML PICKS  (Temp=0.6 | Odds<=20 filter | sorted by Mult)")
rows = []
for r in range(1, 10):
    fp = PROC / f"features_2026-04-29_HV_R{r}.parquet"
    rc = DATA  / f"racecard_20260429_R{r}.json"
    if not fp.exists():
        continue
    df  = pd.read_parquet(fp)
    top = df[df["rank"] == 1].iloc[0]
    odds = float(top.get("win_odds", 0))
    fair = float(top.get("fair_odds", 0))
    mult = float(top.get("value_mult", 0))
    j_time = "?"
    if rc.exists():
        try:
            rcd = json.load(open(rc, encoding="utf-8"))
            j_time = rcd.get("jump_time", rcd.get("race_time", rcd.get("time", "?"))).strip()
        except Exception:
            pass
    in_cap   = odds <= 20
    market   = "CONFIRMED" if (mult <= 1.0 and in_cap) else ("IN-CAP" if in_cap else "EXCLUDED")
    rows.append({
        "Race" : f"R{r}",
        "Jump" : j_time,
        "Pick #": str(top["horse_no"]),
        "Horse" : str(top.get("horse_name", "?"))[:16],
        "Odds"  : round(odds, 1),
        "Fair"  : round(fair, 1),
        "Mult"  : round(mult, 2),
        "Audit?": market,
    })

df_picks = pd.DataFrame(rows)
pd.set_option("display.width", 200)
pd.set_option("display.max_colwidth", 18)
pd.set_option("display.colheader_justify", "left")
print()
print(df_picks.to_string(index=False))

confirmed_races = [r for r in rows if r["Audit?"] == "CONFIRMED"]
incap_races     = [r for r in rows if r["Audit?"] == "IN-CAP"]
excluded_races  = [r for r in rows if r["Audit?"] == "EXCLUDED"]
print(f"\n  Market CONFIRMED (proactive audit at T-35) : {len(confirmed_races)} race(s)")
print(f"  In odds cap, no mkt confirmation           : {len(incap_races)} race(s)")
print(f"  Excluded (odds >20, no audit)              : {len(excluded_races)} race(s)")

# ─── 7. RACE-DAY TIMELINE ───────────────────────────────────────────
print("\n[ 7 ] TONIGHT'S EVENT TIMELINE  (HKT)")
print()
print(f"  {'Time':<7}  {'Event'}")
print(f"  {'-'*6}  {'-'*58}")

def offset(j, delta_min):
    try:
        h, m = map(int, j.strip().split(":"))
        total = h * 60 + m - delta_min
        return f"{total//60}:{total%60:02d}"
    except Exception:
        return "?"

timeline = []
for row in rows:
    j = row["Jump"]
    if j == "?":
        continue
    race = row["Race"]
    timeline += [
        (offset(j, 35), f"{race} ({j}) ▶ T-35 : Proactive audit window OPENS{' [CONFIRMED pick]' if row['Audit?']=='CONFIRMED' else ''}"),
        (offset(j, 25), f"{race} ({j}) ▶ T-25 : Proactive window closes / Odds ingest begins"),
        (offset(j, 18), f"{race} ({j}) ▶ T-18 : Smart-money scan OPENS (3% threshold)"),
        (offset(j,  2), f"{race} ({j}) ▶ T-2  : Smart-money scan CLOSES"),
        (j,             f"{race} ({j}) ▶ JUMP"),
    ]

for t, evt in sorted(timeline):
    marker = " <<" if "JUMP" in evt else ""
    print(f"  {t:<7}  {evt}{marker}")

print(f"\n  Post-race ~23:15  ▶ Auto-learning trigger (results ingestion + model update)")

# ─── SUMMARY ────────────────────────────────────────────────────────
print()
print(SEP)
total = results["pass"] + results["fail"] + results["warn"]
status = "READY FOR TONIGHT" if results["fail"] == 0 else "ACTION REQUIRED"
print(f"  RESULT : {status}")
print(f"  Checks : {results['pass']}/{total} passed  |  {results['fail']} failed  |  {results['warn']} warnings")
print(SEP)
print()
