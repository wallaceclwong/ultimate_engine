import json
import pandas as pd
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
RES  = DATA / "results"

rc  = json.load(open(DATA / "racecard_20260426_R9.json", encoding="utf-8"))
res = json.load(open(RES  / "results_2026-04-26_ST_R9.json", encoding="utf-8"))

res_map = {str(h["horse_no"]): h for h in res.get("results", [])}

rows = []
for h in rc.get("horses", []):
    no   = str(h.get("saddle_number", "?"))
    r    = res_map.get(no, {})
    plc  = r.get("plc", "-")
    flag = "<< WIN" if plc == "1" else ("place" if plc in ["2", "3"] else "")
    rows.append({
        "#"      : no,
        "Horse"  : str(h.get("horse_name", ""))[:20],
        "Dr"     : h.get("draw", "-"),
        "Jockey" : str(h.get("jockey", ""))[:13],
        "Trainer": str(h.get("trainer", ""))[:11],
        "Wt"     : h.get("weight", "-"),
        "Last 6 Runs"   : str(h.get("last_6_runs", "")),
        "Gear"   : str(h.get("gear") or "-"),
        "Fin"    : plc,
        "Odds"   : r.get("win_odds", "-"),
        "LBW"    : r.get("lbw", "-"),
        "Time"   : r.get("finish_time", "-"),
        "Result" : flag,
    })

pd.set_option("display.width", 280)
pd.set_option("display.max_colwidth", 35)
pd.set_option("display.colheader_justify", "left")
df = pd.DataFrame(rows)

dist = rc.get("distance", "?")
cls  = rc.get("race_class", "?")
cond = rc.get("track_condition", "?")
pace = rc.get("predicted_pace", "?")
jump = str(rc.get("jump_time", "")).strip()

divs    = res.get("dividends", {})
win_d   = divs.get("WIN",  [{}])[0].get("dividend", "?")
place_d = divs.get("PLACE", [])
quin_d  = divs.get("QUINELLA", [])

SEP = "=" * 130

print()
print(SEP)
print("  APR 26 2026  |  SHA TIN (ST)  |  RACE 9  |  QUEEN ELIZABETH II CUP  (Group 1)")
print(f"  {dist}m  |  {cls}  |  Going: {cond}  |  Predicted Pace: {pace}  |  Jump: {jump}")
print(SEP)
print(df.to_string(index=False))
print()
print("  ── DIVIDENDS ──────────────────────────────────────────")
print(f"  WIN                : ${win_d}")
for p in place_d:
    print(f"  PLACE  #{p.get('combination','?'):>3}         : ${p.get('dividend','?')}")
for q in quin_d:
    print(f"  QUINELLA  {q.get('combination','?'):<7}   : ${q.get('dividend','?')}")

inc = res.get("incidents", "")
if inc:
    print(f"\n  ── INCIDENTS ──────────────────────────────────────────")
    print(f"  {inc}")

sr = res.get("stewards_report", "")
if sr:
    print(f"\n  ── STEWARDS REPORT ────────────────────────────────────")
    for line in sr.split(". "):
        if line.strip():
            print(f"  {line.strip()}")

print(SEP)
