"""
_patch_going.py
===============
Patches track_condition into existing racecard JSON files for a given date.
Run this when the going is known from HKJC but racecards were scraped before
the going field parser was fixed.

Usage:
    python scripts/_patch_going.py --date 20260503 --going Good
    python scripts/_patch_going.py --date 20260503 --going "Yielding"
    python scripts/_patch_going.py --date 20260503 --going Wet
"""
import json
import argparse
from pathlib import Path

GOING_NORMALISE = {
    "good":             "Good",
    "good to firm":     "Good",
    "firm":             "Good",
    "good to yielding": "Yielding",
    "yielding":         "Yielding",
    "soft":             "Soft",
    "wet":              "Wet",
    "wet fast":         "Wet",
    "wet slow":         "Wet",
}

def main():
    parser = argparse.ArgumentParser(description="Patch track_condition into racecard files")
    parser.add_argument("--date",  required=True,  help="Date compact format YYYYMMDD, e.g. 20260503")
    parser.add_argument("--going", required=True,  help="Going value: Good | Yielding | Soft | Wet")
    parser.add_argument("--venue", default="ST",   help="Venue (for display only)")
    args = parser.parse_args()

    normalised = GOING_NORMALISE.get(args.going.lower().strip())
    if not normalised:
        print(f"[ERROR] Unrecognised going: '{args.going}'")
        print(f"        Valid values: {list(GOING_NORMALISE.keys())}")
        return

    data_dir   = Path(__file__).resolve().parent.parent / "data"
    pattern    = f"racecard_{args.date}_R*.json"
    rc_files   = sorted(data_dir.glob(pattern))

    if not rc_files:
        print(f"[ERROR] No racecard files found matching: data/{pattern}")
        return

    print(f"Patching {len(rc_files)} racecard files for {args.date} {args.venue}")
    print(f"Setting track_condition = '{normalised}'\n")

    patched = 0
    for f in rc_files:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            old = d.get("track_condition", "MISSING")
            d["track_condition"] = normalised
            f.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"  {f.name}: {old!r} → '{normalised}'")
            patched += 1
        except Exception as e:
            print(f"  [ERROR] {f.name}: {e}")

    print(f"\nDone. {patched}/{len(rc_files)} files patched.")

if __name__ == "__main__":
    main()
