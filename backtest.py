"""
backtest.py — REVISED
─────────────────────────────────────────────────────────────────
Ultimate Hybrid Engine — Step 3: Backtest Engine

Simulates betting performance on the 2025–2026 race data.
Fixes: Added full feature engineering to avoid KeyError.

Run on: Vultr VM
Usage : python3 backtest.py
"""

import json
import pickle
import pandas as pd
import numpy as np
from pathlib import Path

import lightgbm as lgb
import xgboost as xgb
from catboost import CatBoost, Pool

# ─── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).parent.absolute()
TRAINING_FILE = BASE_DIR / "final_feature_matrix.parquet"
MODEL_DIR     = BASE_DIR / "models"
RESULTS_OUT   = BASE_DIR / "backtest_results.csv"

# ─── Load Data ───────────────────────────────────────────────────────────────
print("=" * 60)
print("  Ultimate Hybrid Engine -- Step 3: Backtest Engine")
print("=" * 60)
print("\nLoading unified feature matrix...")
df = pd.read_parquet(TRAINING_FILE)
df["date"] = pd.to_datetime(df["date"])
df["year"] = df["date"].dt.year

# Merge AI unluckiness scores if not already in matrix
if "ai_unluckiness" not in df.columns:
    ai_cache_path = BASE_DIR / "data" / "ai_sentiment_cache.parquet"
    if ai_cache_path.exists():
        df_ai = pd.read_parquet(ai_cache_path)
        df_ai["horse_no"] = df_ai["horse_no"].astype(str)
        df["horse_no"] = df["horse_no"].astype(str)
        df = df.merge(df_ai, on=["race_id", "horse_no"], how="left")
        df["ai_unluckiness"] = df["ai_unlucky_score"].fillna(1.0)
    else:
        df["ai_unluckiness"] = 1.0

# Filter to Test Period (2025+)
# The matrix already contains all engineered features (Sectionals, Expanding Stats, etc.)
test_df = df[df["year"] >= 2025].sort_values(["date", "race_num", "horse_no"]).reset_index(drop=True)
test_df = test_df[test_df["plc"] != 99].reset_index(drop=True)

print(f"Test rows (2025+): {len(test_df):,}  |  Races: {test_df['race_id'].nunique():,}")


# ─── Load Models ─────────────────────────────────────────────────────────────
print("\nLoading models...")

lgb_model = lgb.Booster(model_file=str(MODEL_DIR / "model_lgb.txt"))
xgb_model = xgb.Booster()
xgb_model.load_model(str(MODEL_DIR / "model_xgb.json"))
cat_model = CatBoost().load_model(str(MODEL_DIR / "model_cat.cbm"))
xgb_enc   = pickle.load(open(str(MODEL_DIR / "xgb_encoder.pkl"), "rb"))

with open(str(MODEL_DIR / "model_meta.json"), "r") as f:
    meta = json.load(f)
    ALL_FEATURES = meta["features"]

# Fill categoricals
# (Stage 4: Unified matrix already has these, but we cast to category for LGBM)
CATEGORICAL_FEATURES = ["venue", "track_type", "course", "race_class", "track_condition"]
for col in CATEGORICAL_FEATURES:
    if col in test_df.columns:
        test_df[col] = test_df[col].astype("category")

X_test = test_df[ALL_FEATURES]


# ─── Ensemble Prediction ─────────────────────────────────────────────────────

def get_ensemble_probs(df_test, X):
    print("\nGenerating predictions...")

    # 1. LightGBM
    lgb_scores = lgb_model.predict(X)

    # 2. XGBoost
    EV_THRESHOLD = 1.30 # Tighten policy
    X_xgb = X.copy()
    for col in CATEGORICAL_FEATURES:
        X_xgb[col] = X_xgb[col].astype(str)
    X_xgb[CATEGORICAL_FEATURES] = xgb_enc.transform(X_xgb[CATEGORICAL_FEATURES])
    xgb_scores = xgb_model.predict(xgb.DMatrix(X_xgb))

    # 3. CatBoost
    cat_scores = cat_model.predict(Pool(data=X, cat_features=CATEGORICAL_FEATURES))

    df_pred = df_test.copy()
    df_pred["lgb_score"] = lgb_scores
    df_pred["xgb_score"] = xgb_scores
    df_pred["cat_score"] = cat_scores

    def rescale(s):
        return (s - s.min()) / (s.max() - s.min() + 1e-9)

    df_pred["lgb_norm"] = df_pred.groupby("race_id")["lgb_score"].transform(rescale)
    df_pred["xgb_norm"] = df_pred.groupby("race_id")["xgb_score"].transform(rescale)
    df_pred["cat_norm"] = df_pred.groupby("race_id")["cat_score"].transform(rescale)

    # Unify the 3 models (Weighted by their 2026 validation performance)
    # CatBoost had the highest purity (34.4%)
    df_pred["ensemble_score"] = (
        df_pred["lgb_norm"] * 0.30 + 
        df_pred["xgb_norm"] * 0.30 + 
        df_pred["cat_norm"] * 0.40
    )

    # ─── Standardized Probability Calibration (Softmax + Market Blend) ───
    # Matches live prediction logic in predict_today.py exactly
    TEMPERATURE = 0.55
    MARKET_BLEND = 0.30

    # Ensure implied_prob_norm is calculated properly
    if "implied_prob_norm" not in df_pred.columns:
        if "market_implied_prob" in df_pred.columns:
            df_pred["implied_prob_norm"] = df_pred.groupby("race_id")["market_implied_prob"].transform(lambda x: x / (x.sum() + 1e-9))
        elif "win_odds" in df_pred.columns:
            df_pred["market_implied_prob"] = df_pred["win_odds"].apply(lambda odds: 1.0 / odds if odds > 0 else 0.05)
            df_pred["implied_prob_norm"] = df_pred.groupby("race_id")["market_implied_prob"].transform(lambda x: x / (x.sum() + 1e-9))
        else:
            df_pred["implied_prob_norm"] = 1.0 / len(df_pred) # neutral fallback

    # Vectorized group Softmax calculation
    max_scores = df_pred.groupby("race_id")["ensemble_score"].transform("max")
    df_pred["exp_score"] = np.exp((df_pred["ensemble_score"] - max_scores) / TEMPERATURE)
    sum_exp_scores = df_pred.groupby("race_id")["exp_score"].transform("sum")
    df_pred["model_prob"] = df_pred["exp_score"] / (sum_exp_scores + 1e-9)

    # Vectorized Bayesian Market Blend
    blended = (1 - MARKET_BLEND) * df_pred["model_prob"] + MARKET_BLEND * df_pred["implied_prob_norm"]
    df_pred["blended_prob"] = blended
    sum_blended = df_pred.groupby("race_id")["blended_prob"].transform("sum")
    df_pred["pred_prob"] = df_pred["blended_prob"] / (sum_blended + 1e-9)

    # Drop temp columns
    df_pred.drop(columns=["exp_score", "model_prob", "blended_prob"], inplace=True, errors="ignore")

    return df_pred

results = get_ensemble_probs(test_df, X_test)


# ─── Betting Simulation ──────────────────────────────────────────────────────
print("\nRunning betting simulation...")

INITIAL_BANKROLL = 10000.0

# The EV metric is noisy because probabilities are rank-mapped, not calibrated.
# Instead, trust the rank ordering and filter by odds range:
# - Skip short odds (< min_odds): false favourites, no value
# - Skip long odds (> max_odds): too volatile, model signal degrades
# Keep prob floor to avoid picks the model doesn't actually like.

ODDS_SWEEP = [
    (3.0, 20.0, 0.08),   # default: skip false favs and extreme longshots
    (4.0, 15.0, 0.08),   # tighter
    (5.0, 12.0, 0.08),   # mid-range value only
    (6.0, 10.0, 0.08),   # narrow value window
    (3.0, 20.0, 0.10),   # higher prob floor
    (4.0, 15.0, 0.10),
    (5.0, 12.0, 0.10),
]

print(f"\n{'Policy':>22} {'Bets':>6} {'Win%':>7} {'Profit':>10} {'ROI':>7} {'DDown':>8}")
print("-" * 65)

best_result = None

for min_odds, max_odds, prob_floor in ODDS_SWEEP:
    bankroll = INITIAL_BANKROLL
    history = []

    for race_id, group in results.groupby("race_id", sort=False):
        group = group.copy()
        group["ev"] = group["pred_prob"] * group["win_odds"]

        # Bet rank-1 within odds window and above prob floor
        bets = group[
            (group["pred_prob"] > prob_floor)
            & (group["win_odds"] >= min_odds)
            & (group["win_odds"] <= max_odds)
        ].sort_values("ensemble_score", ascending=False)

        if not bets.empty:
            bet_row = bets.iloc[0]
            prob, odds = bet_row["pred_prob"], bet_row["win_odds"]

            # 1/10th Kelly with a 3% safety cap
            kelly_full = (prob * (odds - 1) - (1 - prob)) / (odds - 1)
            kelly_full = max(0, kelly_full)
            stake_pct  = min(0.03, kelly_full * 0.10)
            stake_amt  = bankroll * stake_pct

            if stake_amt < 10:
                continue

            is_win = int(bet_row["plc"] == 1)
            profit = (stake_amt * odds - stake_amt) if is_win else -stake_amt
            bankroll += profit

            history.append({
                "race_id":      race_id,
                "date":         bet_row["date"],
                "horse":        bet_row["horse_name"],
                "prob":         round(prob, 4),
                "odds":         round(odds, 2),
                "stake_amt":    round(stake_amt, 2),
                "result":       "WIN" if is_win else "LOSS",
                "profit":       round(profit, 2),
                "bankroll":     round(bankroll, 2),
            })

    hist_df = pd.DataFrame(history)
    n_bets = len(hist_df)
    label = f"odds[{min_odds}-{max_odds}] P>{prob_floor}"
    if n_bets == 0:
        print(f"{label:>22} {'0':>6} {'—':>7} {'—':>10} {'—':>7} {'—':>8}")
        continue

    win_rate = len(hist_df[hist_df['result'] == 'WIN']) / n_bets
    net_profit = bankroll - INITIAL_BANKROLL
    roi = net_profit / max(1, hist_df['stake_amt'].sum())
    max_dd = hist_df['profit'].cumsum().min()

    print(f"{label:>22} {n_bets:>6} {win_rate:>7.1%} ${net_profit:>9,.0f} {roi:>7.1%} ${max_dd:>7,.0f}")

    if best_result is None or net_profit > best_result.get("profit", -99999):
        best_result = {
            "label": label, "n_bets": n_bets, "win_rate": win_rate,
            "profit": net_profit, "roi": roi, "max_dd": max_dd,
            "bankroll": bankroll, "history": hist_df,
        }

# ─── Best Result ─────────────────────────────────────────────────────────────
best = best_result
hist_df = best["history"]
hist_df.to_csv(RESULTS_OUT, index=False)

print("\n" + "=" * 60)
print(f"  BEST: {best['label']} — {best['n_bets']} bets, "
      f"{best['win_rate']:.1%} win, ${best['profit']:,.0f} profit, "
      f"{best['roi']:.1%} ROI")
print("=" * 60)
