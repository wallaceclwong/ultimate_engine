"""Show racecard table for a given meeting with actual results overlaid."""
import json
import sys
import pandas as pd
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
RES  = DATA / "results"

DATE  = sys.argv[1] if len(sys.argv) > 1 else "2026-04-26"
VENUE = sys.argv[2] if len(sys.argv) > 2 else "ST"
COMPACT = DATE.replace("-", "")
SEP = "=" * 112

pd.set_option("display.width", 220)
pd.set_option("display.max_colwidth", 20)
pd.set_option("display.colheader_justify", "left")

found = 0
for r in range(1, 12):
    rc_f  = DATA / f"racecard_{COMPACT}_R{r}.json"
    res_f = RES  / f"results_{DATE}_{VENUE}_R{r}.json"
    if not rc_f.exists():
        continue

    found += 1
    rc  = json.load(open(rc_f, encoding="utf-8"))
    res = json.load(open(res_f, encoding="utf-8")) if res_f.exists() else {}

    res_map = {}
    for h in res.get("results", []):
        res_map[str(h.get("horse_no", ""))] = {
            "plc"     : h.get("plc", "-"),
            "win_odds": h.get("win_odds", "-"),
        }

    rows = []
    for h in rc.get("horses", []):
        no   = str(h.get("saddle_number", "?"))
        name = str(h.get("horse_name", "?"))[:18]
        draw = str(h.get("draw", "-"))
        jock = str(h.get("jockey", "?"))[:14]
        trn  = str(h.get("trainer", "?"))[:12]
        wt   = str(h.get("weight", "-"))
        last6= str(h.get("last_6_runs", ""))[:12]
        gear = str(h.get("gear") or "-")[:8]
        syn  = round(float(h.get("synergy_score", 0) or 0), 2)
        plc  = res_map.get(no, {}).get("plc", "-")
        odds = res_map.get(no, {}).get("win_odds", "-")
        flag = "<< WIN" if plc == "1" else ("  place" if plc in ["2","3"] else "")
        rows.append({
            "#"      : no,
            "Horse"  : name,
            "Dr"     : draw,
            "Jockey" : jock,
            "Trainer": trn,
            "Wt"     : wt,
            "Last 6" : last6,
            "Gear"   : gear,
            "Syn"    : syn,
            "Fin"    : plc,
            "Odds"   : odds,
            "  "     : flag,
        })

    df = pd.DataFrame(rows)
    dist  = rc.get("distance", "?")
    cls   = rc.get("race_class", "?")
    cond  = rc.get("track_condition", "?")
    pace  = rc.get("predicted_pace", "?")
    jump  = str(rc.get("jump_time", "")).strip()
    win_div  = res.get("dividends", {}).get("WIN", [{}])[0].get("dividend", "?")
    quin_div = res.get("dividends", {}).get("QUINELLA", [{}])[0].get("combination", "?")

    print()
    print(SEP)
    print(f"  {DATE} | {VENUE} | Race {r} | {dist} | {cls} | {cond} | Pace: {pace} | Jump: {jump}")
    print(f"  WIN: ${win_div}   QUINELLA: {quin_div}   ({len(rows)} runners)")
    print(SEP)
    print(df.to_string(index=False))

if found == 0:
    print(f"No racecards found for {DATE} ({VENUE}).")
print()
