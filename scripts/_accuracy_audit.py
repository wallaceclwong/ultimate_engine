"""
_accuracy_audit.py
==================
Compares AI top-pick (by probability) against actual race results.
Breaks down accuracy by: venue, confidence band, and audit contamination.
"""
import json
from pathlib import Path
from collections import defaultdict

PRED_DIR = Path("data/predictions")
RES_DIR  = Path("data/results")

def conf_band(c):
    if c >= 0.30: return "High  (>=30%)"
    if c >= 0.15: return "Med   (15-30%)"
    if c >= 0.08: return "Low   (8-15%)"
    return               "VLow  (<8%)"

preds   = sorted(PRED_DIR.glob("prediction_*.json"))
results = sorted(RES_DIR.glob("results_*.json"))

print(f"Prediction files : {len(preds)}")
print(f"Result files     : {len(results)}")

# ── Find evaluatable races ──────────────────────────────────────────────────
evaluatable = []
for pf in preds:
    parts = pf.stem.split("_")
    if len(parts) < 4: continue
    date, venue, race = parts[1], parts[2], parts[3]
    rf = RES_DIR / f"results_{date}_{venue}_{race}.json"
    if rf.exists():
        evaluatable.append((pf, rf, date, venue, race))

print(f"Evaluatable races: {len(evaluatable)}\n")
if not evaluatable:
    print("No overlapping prediction+result pairs found yet.")
    exit(0)

# ── Per-race evaluation ─────────────────────────────────────────────────────
rows = []
audit_contaminated = 0

for pf, rf, date, venue, race in sorted(evaluatable):
    try:
        pred   = json.loads(pf.read_text(encoding="utf-8"))
        result = json.loads(rf.read_text(encoding="utf-8"))
        probs  = pred.get("probabilities", {})
        res    = result.get("results", [])
        conf   = pred.get("confidence_score", 0.0)

        if not probs or not res: continue

        top_pick   = max(probs, key=probs.get)
        sorted_picks = sorted(probs, key=probs.get, reverse=True)
        top2 = set(sorted_picks[:2])
        top3 = set(sorted_picks[:3])

        winner  = next((r["horse_no"] for r in res if r.get("plc") == "1"), None)
        placers = {r["horse_no"] for r in res
                   if r.get("plc","99").isdigit() and int(r["plc"]) <= 3}
        if winner is None: continue

        # Audit-mode contamination: result file mtime < prediction file mtime
        # means results existed when prediction was generated
        rf_mtime  = Path(rf).stat().st_mtime
        pf_mtime  = Path(pf).stat().st_mtime
        is_audit  = rf_mtime < pf_mtime   # result older than prediction file

        rows.append({
            "race_id":  f"{date}_{venue}_{race}",
            "date":     date,
            "venue":    venue,
            "race":     race,
            "top_pick": top_pick,
            "winner":   winner,
            "win":      top_pick == winner,
            "place":    top_pick in placers,
            "top2_hit": winner in top2,
            "top3_hit": winner in top3,
            "conf":     conf,
            "band":     conf_band(conf),
            "audit":    is_audit,
        })
        if is_audit:
            audit_contaminated += 1
    except Exception as e:
        print(f"  ERROR: {e}")

# ── Helper ──────────────────────────────────────────────────────────────────
def stats(subset, label, indent=2):
    n = len(subset)
    if n == 0:
        print(" " * indent + f"{label:<22}: no data")
        return
    wins   = sum(1 for r in subset if r["win"])
    places = sum(1 for r in subset if r["place"])
    t2     = sum(1 for r in subset if r["top2_hit"])
    t3     = sum(1 for r in subset if r["top3_hit"])
    print(" " * indent + f"{label:<22}: "
          f"WIN {wins}/{n}={wins/n:5.1%}  "
          f"PLACE {wins+places}/{n}={(wins+places)/n:5.1%}  "
          f"Top2 {t2}/{n}={t2/n:5.1%}  "
          f"Top3 {t3}/{n}={t3/n:5.1%}")

# ── 1. Overall ───────────────────────────────────────────────────────────────
print("=" * 80)
print("  OVERALL")
print("=" * 80)
stats(rows, "All races")
genuine = [r for r in rows if not r["audit"]]
audit   = [r for r in rows if r["audit"]]
stats(genuine, "Genuine (pre-race)")
stats(audit,   "Audit-contaminated")
print(f"  (Baseline random 14-runner: WIN ~7%, PLACE ~21%)")

# ── 2. By Venue ─────────────────────────────────────────────────────────────
print()
print("=" * 80)
print("  BY VENUE  (genuine pre-race predictions only)")
print("=" * 80)
for v in ["ST", "HV"]:
    subset = [r for r in genuine if r["venue"] == v]
    stats(subset, f"{v} ({len(subset)} races)")

# ── 3. By Confidence Band ────────────────────────────────────────────────────
print()
print("=" * 80)
print("  BY CONFIDENCE BAND  (genuine only)")
print("=" * 80)
for band in ["High  (>=30%)", "Med   (15-30%)", "Low   (8-15%)", "VLow  (<8%)"]:
    subset = [r for r in genuine if r["band"] == band]
    stats(subset, band)

# ── 4. By Meeting (date) ────────────────────────────────────────────────────
print()
print("=" * 80)
print("  BY MEETING  (genuine only, newest first)")
print("=" * 80)
meetings = defaultdict(list)
for r in genuine:
    meetings[f"{r['date']}_{r['venue']}"].append(r)
for key in sorted(meetings, reverse=True):
    stats(meetings[key], key)

# ── 5. Confidence calibration scatter ───────────────────────────────────────
print()
print("=" * 80)
print("  CONFIDENCE CALIBRATION  (does higher conf = more wins?)")
print("=" * 80)
buckets = defaultdict(list)
for r in genuine:
    b = int(r["conf"] * 20) / 20   # round to nearest 5%
    buckets[b].append(r)
print(f"  {'Conf':>8}  {'n':>4}  {'Win%':>6}  {'Place%':>8}")
for b in sorted(buckets):
    grp = buckets[b]
    n = len(grp)
    w = sum(1 for r in grp if r["win"])
    p = sum(1 for r in grp if r["place"])
    print(f"  {b:>7.0%}  {n:>4}  {w/n:>6.1%}  {(w+p)/n:>8.1%}")

# ── 6. By Track Condition (Going) ───────────────────────────────────────────
print()
print("=" * 80)
print("  BY GOING / TRACK CONDITION  (genuine only)")
print("=" * 80)

DATA_DIR = Path("data")

for r in genuine:
    date_compact = r["date"].replace("-", "")
    race_no      = r["race"].replace("R", "")
    rc_path      = DATA_DIR / f"racecard_{date_compact}_R{race_no}.json"
    going = "Unknown"
    if rc_path.exists():
        try:
            rc = json.loads(rc_path.read_text(encoding="utf-8"))
            going = rc.get("track_condition", "Unknown")
        except:
            pass
    r["going"] = going

going_groups = defaultdict(list)
for r in genuine:
    going_groups[r["going"]].append(r)

for going in sorted(going_groups):
    stats(going_groups[going], f"{going}")

# ── 7. Key Insights Summary ──────────────────────────────────────────────────
print()
print("=" * 80)
print("  KEY INSIGHTS")
print("=" * 80)

n_gen = len(genuine)
w_gen = sum(1 for r in genuine if r["win"])
p_gen = sum(1 for r in genuine if r["place"])

print(f"  Genuine pre-race sample : {n_gen} races  ({len(audit)} audit-contaminated excluded)")
print(f"  Top-1 WIN rate          : {w_gen}/{n_gen} = {w_gen/n_gen:.1%}  (baseline ~7%)")
print(f"  Top-1 PLACE rate        : {w_gen+p_gen}/{n_gen} = {(w_gen+p_gen)/n_gen:.1%}  (baseline ~21%)")
print()

# Confidence calibration check
conf_vals  = [r["conf"] for r in genuine]
conf_range = max(conf_vals) - min(conf_vals) if conf_vals else 0
if conf_range < 0.15:
    print(f"  ⚠️  CONFIDENCE UNCALIBRATED: range only {conf_range:.0%}  "
          f"({min(conf_vals):.0%}–{max(conf_vals):.0%})")
    print(f"     Model is outputting near-uniform confidence — scores are noise.")
    print(f"     Status: confidence rubric fix applied to prompt. Re-run predictions to verify.")
else:
    print(f"  ✅ Confidence range: {min(conf_vals):.0%}–{max(conf_vals):.0%}  (well spread)")

# Per-going flag
for going, grp in sorted(going_groups.items()):
    if going in ("Soft", "Wet", "Yielding") and grp:
        w = sum(1 for r in grp if r["win"])
        print(f"  ⚠️  Going '{going}': {w}/{len(grp)} wins = {w/len(grp):.0%} "
              f"— model may be mispricing non-Good surfaces")
