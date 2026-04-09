"""
predict_live.py
─────────────────────────────────────────────────────────────────
Ultimate Hybrid Engine — Live Prediction Module

Usage:
    python3 predict_live.py 2026-04-01 ST
"""

import json
import pickle
import pandas as pd
import numpy as np
import sys
import io
import asyncio
from pathlib import Path
import lightgbm as lgb
import xgboost as xgb
from catboost import CatBoost
# ─── Config ──────────────────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).parent.absolute()

# Ensure local imports within ultimate_engine work
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from consensus_agent import consensus_agent
MODEL_DIR     = BASE_DIR / "models"
DATA_DIR      = BASE_DIR / "data"
MATRIX_FILE   = BASE_DIR / "final_feature_matrix.parquet"

# ─── Typical Race Times by Distance (seconds) ──────────────────────────────
# Derived from 8 years of HKJC results (training data median per distance)
# Used as statistical prior for race_sec_sum when actual time is unknown pre-race
RACE_TIME_BY_DIST = {
    1000: 56.69,
    1200: 69.08,
    1400: 82.20,
    1600: 94.72,
    1650: 97.00,  # Estimated (sparse data)
    2000: 121.70,
}
RACE_TIME_DEFAULT = 70.0  # Fallback if distance not in table

def load_latest_odds(date_comp, race_num):
    odds_dir = DATA_DIR / "odds"
    if not odds_dir.exists():
        return {}
    odds_files = list(odds_dir.glob(f"snapshot_{date_comp}_R{race_num}_*.json"))
    if not odds_files:
        return {}
    latest_file = max(odds_files, key=lambda p: p.stat().st_mtime)
    try:
        with open(latest_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get("win_odds", {})
    except Exception:
        return {}

# ─── Load Ensemble Models ───────────────────────────────────────────────────
print("\nLoading models...")
lgb_model = lgb.Booster(model_file=str(MODEL_DIR / "model_lgb.txt"))
xgb_model = xgb.Booster()
xgb_model.load_model(str(MODEL_DIR / "model_xgb.json"))
cat_model = CatBoost().load_model(str(MODEL_DIR / "model_cat.cbm"))
xgb_enc   = pickle.load(open(str(MODEL_DIR / "xgb_encoder.pkl"), "rb"))

with open(str(MODEL_DIR / "model_meta.json"), "r") as f:
    meta = json.load(f)
    ALL_FEATURES = meta["features"]

print("Loading historical stats from matrix...")
df_full = pd.read_parquet(MATRIX_FILE)
AI_CACHE = DATA_DIR / "ai_sentiment_cache.parquet"

# Load AI Unluckiness Scores (Latest per horse)
if AI_CACHE.exists():
    df_ai = pd.read_parquet(AI_CACHE)
    df_ai["horse_no"] = df_ai["horse_no"].astype(str)
    # Join with horse_id from historical data to map saddle # to unique ID
    ai_horse_map = df_full[["race_id", "horse_no", "horse_id"]].drop_duplicates()
    df_ai = df_ai.merge(ai_horse_map, on=["race_id", "horse_no"], how="inner")
    # Get LATEST score for each horse_id
    latest_ai_scores = df_ai.sort_values("race_id").groupby("horse_id").tail(1).set_index("horse_id")["ai_unlucky_score"].to_dict()
else:
    latest_ai_scores = {}
# Get the most recent stat for each jockey/trainer to use for today's races
j_stats = df_full.sort_values("date").groupby("jockey").tail(1)[["jockey", "jockey_win_rate", "jockey_place_rate", "jockey_rides"]]
t_stats = df_full.sort_values("date").groupby("trainer").tail(1)[["trainer", "trainer_win_rate", "trainer_place_rate"]]
# Horse habits for analytical features (median sectional positions)
# Check if columns exist before slicing to prevent KeyError
H_COLS = ["horse_id", "sec_pos_1", "sec_pos_2", "sec_pos_pre"]
H_COLS_EXIST = [c for c in H_COLS if c in df_full.columns]
h_stats = df_full.sort_values("date").groupby("horse_id").tail(1)[H_COLS_EXIST]

def predict_race(date_str, venue, race_num):
    date_comp = date_str.replace("-", "")
    rc_file = DATA_DIR / f"racecard_{date_comp}_R{race_num}.json"
    
    if not rc_file.exists():
        print(f"Skipping R{race_num}: {rc_file.name} not found.")
        return None

    with open(rc_file, 'r', encoding='utf-8') as f:
        rc = json.load(f)

    field_size = len(rc.get("horses", []))
    rows = []
    
    morning_odds = load_latest_odds(date_comp, race_num)
    
    for h in rc.get("horses", []):
        horse_id = h.get("horse_id") or ""
        jockey   = h.get("jockey", "").strip()
        trainer  = h.get("trainer", "").strip()
        horse_no = str(h.get("saddle_number", ""))

        # ── Feature Mapping ───────────────────────────────────
        js = j_stats[j_stats["jockey"] == jockey].iloc[0].to_dict() if jockey in j_stats["jockey"].values else {}
        ts = t_stats[t_stats["trainer"] == trainer].iloc[0].to_dict() if trainer in t_stats["trainer"].values else {}
        hs = h_stats[h_stats["horse_id"] == horse_id].iloc[0].to_dict() if horse_id in h_stats["horse_id"].values else {}

        last_6_raw = h.get("last_6_runs", [])
        last_6 = [int(r) for r in last_6_raw if str(r).isdigit()]

        win_odds_val = morning_odds.get(str(horse_no), h.get("win_odds", 10.0))
        win_odds = float(win_odds_val) if win_odds_val else 10.0

        row = {
            "horse_no":           horse_no,
            "horse_name":         h.get("horse_name"),
            "win_odds":           win_odds,
            "market_implied_prob": 1.0 / win_odds if win_odds > 0 else 0.05,
            "actual_wt":          float(h.get("weight", 120)),
            "draw":               int(h.get("draw", 0) or 0),
            "field_size":         field_size,
            "distance":           float(rc.get("distance", 1200)),
            "venue":              venue,
            "track_type":         rc.get("track_type", "Turf"),
            "course":             rc.get("course", "A"),
            "race_class":         rc.get("race_class", "Class 4"),
            "track_condition":    rc.get("track_condition", "Good"),  # Real going from scraper
            "last_6_avg":         np.mean(last_6) if last_6 else 7.0,
            "last_6_best":        min(last_6) if last_6 else 5.0,
            "last_2_avg":         np.mean(last_6[:2]) if len(last_6)>=2 else 7.0,
            "last_6_trend":       (np.mean(last_6[:3]) - np.mean(last_6[3:])) if len(last_6)>=6 else 0.0,
            "gear_change":        0.0,
            "stable_change":      0,
            "ai_unluckiness":     latest_ai_scores.get(horse_id, 1.0),
            # Honest Stats (from matrix)
            "jockey_win_rate":    js.get("jockey_win_rate", 0.08),
            "jockey_place_rate":  js.get("jockey_place_rate", 0.23),
            "jockey_rides":       js.get("jockey_rides", 100),
            "trainer_win_rate":   ts.get("trainer_win_rate", 0.08),
            "trainer_place_rate": ts.get("trainer_place_rate", 0.23),
            # Analytical Habits (from matrix)
            "sec_pos_1":          hs.get("sec_pos_1", 6.0),
            "sec_pos_2":          hs.get("sec_pos_2", 6.0),
            "sec_pos_pre":        hs.get("sec_pos_pre", 6.0),
            "race_sec_sum":       RACE_TIME_BY_DIST.get(int(rc.get("distance", 1200)), RACE_TIME_DEFAULT),
        }
        
        # Computed
        row["draw_relative"] = row["draw"] / field_size if field_size > 0 else 0.5
        rows.append(row)

    df_race = pd.DataFrame(rows)
    df_race["implied_prob_norm"] = df_race["market_implied_prob"] / df_race["market_implied_prob"].sum()
    df_race["odds_rank"] = df_race["win_odds"].rank(method="min")

    # Final Feature Processing
    for col in ["venue", "track_type", "course", "race_class", "track_condition"]:
        df_race[col] = df_race[col].astype("category")

    X = df_race[ALL_FEATURES]

    # Predict
    def norm(s):
        mn, mx = s.min(), s.max()
        return (s - mn) / (mx - mn + 1e-9)

    lgb_scores = lgb_model.predict(X)
    xgb_scores = xgb_model.predict(xgb.DMatrix(X, enable_categorical=True))
    cat_scores = cat_model.predict(X)
    
    df_race["ensemble_score"] = (norm(lgb_scores) + norm(xgb_scores) + norm(cat_scores)) / 3.0
    df_race["rank"] = df_race["ensemble_score"].rank(ascending=False, method="first").astype(int)
    
    # ── Final Probability Calibration (Softmax) ──
    TEMPERATURE = 0.35
    scores = df_race["ensemble_score"].values
    exp_scores = np.exp((scores - np.max(scores)) / TEMPERATURE)
    df_race["pred_prob"] = exp_scores / exp_scores.sum()
    
    df_race["fair_odds"] = 1.0 / df_race["pred_prob"]
    df_race["ev"] = df_race["pred_prob"] * df_race["win_odds"]
    df_race["value_mult"] = df_race["win_odds"] / df_race["fair_odds"]
    
    # Stage 7: Feature Capture for Post-Race Learning
    processed_dir = DATA_DIR / "processed"
    if not processed_dir.exists():
        processed_dir.mkdir(parents=True, exist_ok=True)
    df_race.to_parquet(processed_dir / f"features_{date_str}_{venue}_R{race_num}.parquet")
    
    return df_race.sort_values("rank")

async def main():
    date_target = sys.argv[1] if len(sys.argv) > 1 else "2026-04-01"
    venue_target = sys.argv[2] if len(sys.argv) > 2 else "ST"
    
    print(f"\nULTIMATE ENGINE (Triple Consensus): {date_target} at {venue_target}")
    print("="*60)
    
    full_results = []
    for r in range(1, 12):
        res = predict_race(date_target, venue_target, r)
        if res is not None:
            print(f"  Processed R{r}")
            res["race"] = r
            full_results.append(res)
    
    if not full_results:
        print("No races found for this date/venue.")
        return

    summary = pd.concat(full_results)
    # Filter High EV Plays
    tips = summary[summary["ev"] > 1.25].sort_values("ev", ascending=False)
    
    if tips.empty:
        print("\n  No high-value trades found yet (Waiting for odds movement).")
        return

    print("\n" + "="*60)
    print(f"  STEP 6: AI-NATIVE TRIPLE CONSENSUS AUDITS")
    print("="*60)

    for _, tip in tips.iterrows():
        print(f"\n[Audit] R{tip['race']} | {tip['horse_name']} (#{tip['horse_no']})")
        print(f"      Statistical Rank: {tip['rank']} | Odds: {tip['win_odds']:.1f} | EV: {tip['ev']:.2f}")
        
        # Trigger DeepSeek-R1 Reasoning Audit
        # We find the race data for this specific race to give context to R1
        race_data = next(r for r in full_results if (r["race"] == tip["race"]).all())
        
        verdict, reasoning = await consensus_agent.get_consensus(race_data, tip["horse_no"])
        
        icon = "[CONFIRMED]" if verdict == "CONFIRMED" else "[CAUTION]" if verdict == "CAUTION" else "[VETO]"
        print(f"      {icon} CONV: {verdict}")
        print(f"      REASON: {reasoning}")
        print("-" * 40)
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())
