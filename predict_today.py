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
from telegram_service import telegram_service
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
    # Sort by mtime descending, skip empty snapshots (betting closed after races)
    for f in sorted(odds_files, key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            with open(f, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
                win_odds = data.get("win_odds", {})
                if win_odds:  # skip empty snapshots
                    return win_odds
        except Exception:
            continue
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

async def send_bet_card(race_num, date_str, venue, top_pick, top_pick_edge, probabilities, market_odds):
    """
    Sends a structured Telegram bet recommendation card for a single race.
    Only called when is_best_bet=True.
    """
    horse_no   = str(int(top_pick['horse_no']))
    horse_name = top_pick['horse_name']
    odds       = float(top_pick['win_odds'])
    fair       = float(top_pick['fair_odds'])
    rank       = int(top_pick['rank'])
    field_size = int(top_pick['field_size'])

    # Top 3 ranked horses for context
    top3_lines = []
    sorted_probs = sorted(probabilities.items(), key=lambda x: x[1], reverse=True)[:3]
    for i, (h, p) in enumerate(sorted_probs, 1):
        mo = market_odds.get(h, 0)
        top3_lines.append(f"  {i}. #{h} | odds={mo:.1f} | prob={p:.1%}")
    top3_str = "\n".join(top3_lines)

    msg = (
        f"\U0001f3c7 *BET SIGNAL: {venue} R{race_num}*\n"
        f"\U0001f3af *Pick:* #{horse_no} {horse_name}\n"
        f"\U0001f4b0 *Odds:* {odds:.1f} | Fair: {fair:.1f} | Edge: {top_pick_edge:+.1%}\n"
        f"\U0001f4ca *Rank:* {rank}/{field_size} horses\n\n"
        f"*Top 3 Ranked:*\n{top3_str}\n\n"
        f"\u23f1 *Race:* {date_str} {venue} R{race_num}\n"
        f"\u26a0\ufe0f _Always verify odds before placing bet._"
    )
    await telegram_service.send_message(msg)


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
    TEMPERATURE = 0.6
    scores = df_race["ensemble_score"].values
    exp_scores = np.exp((scores - np.max(scores)) / TEMPERATURE)
    df_race["pred_prob"] = exp_scores / exp_scores.sum()
    
    df_race["fair_odds"] = 1.0 / df_race["pred_prob"]
    df_race["ev"] = df_race["pred_prob"] * df_race["win_odds"]
    df_race["value_mult"] = df_race["win_odds"] / df_race["fair_odds"]

    # ── Value Edge: how much the model disagrees with the market ──
    # edge > 0  → model thinks horse is undervalued (potential bet)
    # edge < 0  → model thinks horse is overvalued (skip)
    # Formula: (model_prob - market_prob) / market_prob
    df_race["value_edge"] = (
        df_race["pred_prob"] - df_race["market_implied_prob"]
    ) / df_race["market_implied_prob"].clip(lower=0.01)
    
    # Stage 7: Feature Capture for Post-Race Learning
    processed_dir = DATA_DIR / "processed"
    if not processed_dir.exists():
        processed_dir.mkdir(parents=True, exist_ok=True)
    df_race.to_parquet(processed_dir / f"features_{date_str}_{venue}_R{race_num}.parquet")
    
    # Save prediction JSON file
    predictions_dir = DATA_DIR / "predictions"
    if not predictions_dir.exists():
        predictions_dir.mkdir(parents=True, exist_ok=True)
    
    # Build prediction JSON in old format
    race_id = f"{date_str}_{venue}_R{race_num}"
    probabilities = {}
    market_odds = {}
    
    for _, row in df_race.iterrows():
        horse_no = str(int(row["horse_no"]))
        probabilities[horse_no] = float(row["pred_prob"])
        market_odds[horse_no] = float(row["win_odds"])
    
    # Get top pick — must be rank-1, not just first row (which is horse #1 by saddle)
    top_pick = df_race.sort_values("rank").iloc[0]
    recommended_bet = f"WIN {int(top_pick['horse_no'])}"
    
    # ── Confidence = Value Edge of the top pick ──────────────────────────────
    # Positive = model sees genuine value vs market; negative = market is right
    top_pick_edge = float(top_pick["value_edge"])

    # ── Skip Threshold (Priority 3) ──────────────────────────────────────────
    # Only flag as a best bet when ALL three conditions hold:
    #   1. Edge > 5%  (model genuinely disagrees with market)
    #   2. Market odds > 6.0  (avoid short-priced chalk where margin is thin)
    #   3. Top pick is rank-1  (we only back our strongest selection)
    is_best_bet = (
        top_pick_edge > 0.05
        and float(top_pick["win_odds"]) > 6.0
        and int(top_pick["rank"]) == 1
    )

    prediction_json = {
        "race_id": race_id,
        "gemini_model": "ensemble_lgb_xgb_cat",
        "confidence_score": round(top_pick_edge, 4),   # value edge, not raw prob
        "is_best_bet": is_best_bet,
        "recommended_bet": recommended_bet if is_best_bet else "NO BET",
        "probabilities": probabilities,
        "kelly_stakes": {},
        "market_odds": market_odds,
        "analysis_markdown": (
            f"## Race Analysis: {rc.get('race_class', 'Class 4')} "
            f"{rc.get('distance', 1200)}m {rc.get('track_type', 'Turf')} "
            f"({rc.get('track_condition', 'Good')})\n\n"
            f"### Top Pick\n"
            f"- **#{int(top_pick['horse_no'])} {top_pick['horse_name']}** "
            f"(Rank {top_pick['rank']}, Odds {top_pick['win_odds']:.1f}, "
            f"Fair {top_pick['fair_odds']:.1f}, Edge {top_pick_edge:+.1%})\n\n"
            f"### Bet Signal\n"
            f"- **{'✅ BET' if is_best_bet else '⛔ NO BET'}** "
            f"(edge={top_pick_edge:+.1%}, odds={top_pick['win_odds']:.1f})\n\n"
            f"### Key Stats\n"
            f"- Field Size: {field_size}\n"
            f"- Track: {venue} {rc.get('course', 'A')}\n"
            f"- Going: {rc.get('track_condition', 'Good')}"
        )
    }
    
    pred_file = predictions_dir / f"prediction_{date_str}_{venue}_R{race_num}.json"
    with open(pred_file, "w", encoding="utf-8") as f:
        json.dump(prediction_json, f, indent=2)
    
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
    
    # ── Bet Filter: mirrors is_best_bet in predict_race() ────────────────────
    # Tier 1: rank-1 picks with positive edge > 5% and market odds > 6.0
    tier1 = summary[
        (summary["rank"] == 1)
        & (summary["value_edge"] > 0.05)
        & (summary["win_odds"] > 6.0)
    ].copy()
    tier1["tier"] = "PRIMARY"

    # Tier 2: Outsiders with very strong model edge (edge > 30%, odds ≤ 50)
    # These are cases where the model strongly disagrees with the market on a non-rank-1 horse
    tier2 = summary[
        (summary["value_edge"] > 0.30)
        & (summary["win_odds"] <= 50)
    ].copy()
    tier2 = tier2[~tier2.index.isin(tier1.index)]
    tier2["tier"] = "SECONDARY"

    tips = pd.concat([tier1, tier2]).sort_values(["tier", "value_edge"], ascending=[True, False])

    if tips.empty:
        print("\n  ⛔ No value bets today — all races below edge threshold.")
        print("  (Showing top ranked horses per race for reference only)")
        for r_df in full_results:
            top = r_df.iloc[0]
            print(f"  R{int(top['race'])}: #{int(top['horse_no'])} {top['horse_name']} "
                  f"| odds={top['win_odds']:.1f} | fair={top['fair_odds']:.1f} "
                  f"| edge={top['value_edge']:+.1%} | ⛔ SKIP")
        return

    print("\n" + "="*60)
    print(f"  STEP 6: AI-NATIVE TRIPLE CONSENSUS AUDITS")
    print("="*60)

    # Track bets sent for the daily summary
    bets_sent = []

    for _, tip in tips.iterrows():
        tier_icon = "\U0001f525" if tip["tier"] == "PRIMARY" else "\U0001f4a5"
        print(f"\n[Audit] {tier_icon} {tip['tier']} | R{tip['race']} | {tip['horse_name']} (#{tip['horse_no']})")
        print(f"      Rank: {tip['rank']} | Odds: {tip['win_odds']:.1f} | Fair: {tip['fair_odds']:.1f} | Edge: {tip['value_edge']:+.1%}")

        race_data = next(r for r in full_results if (r["race"] == tip["race"]).all())

        # ── Store pick for daily summary (Muted individual Telegram alert) ──
        pred_file = DATA_DIR / "predictions" / f"prediction_{date_target}_{venue_target}_R{int(tip['race'])}.json"
        try:
            pred_data = json.loads(pred_file.read_text())
            bets_sent.append((int(tip['race']), tip['horse_name'], tip['win_odds'], tip['value_edge']))
        except Exception as e:
            print(f"[WARN] Could not parse prediction file for R{int(tip['race'])}: {e}")

        # ── DeepSeek-R1 Reasoning Audit (Internal only now) ──
        verdict, reasoning = await consensus_agent.get_consensus(race_data, tip["horse_no"])

        icon = "[CONFIRMED]" if verdict == "CONFIRMED" else "[CAUTION]" if verdict == "CAUTION" else "[VETO]"
        print(f"      {icon} CONV: {verdict}")
        print(f"      REASON: {reasoning}")
        print("-" * 40)

    # ── Daily Summary Card ──
    if bets_sent:
        lines = [f"  R{r}: #{name} @ {odds:.1f} (edge {edge:+.1%})" for r, name, odds, edge in bets_sent]
        await telegram_service.send_message(
            f"\U0001f4cb *Daily Bet Sheet: {date_target} {venue_target}*\n"
            + "\n".join(lines)
            + f"\n\n*Total picks: {len(bets_sent)}/{len(full_results)} races*"
        )
    else:
        await telegram_service.send_message(
            f"\u26d4 *{date_target} {venue_target}* — No value bets today.\n"
            f"All {len(full_results)} races below edge/odds threshold."
        )

    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())
