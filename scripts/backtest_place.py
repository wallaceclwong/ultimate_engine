import pandas as pd
import numpy as np
import lightgbm as lgb
import xgboost as xgb
from catboost import CatBoost
import pickle
from pathlib import Path
import json

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_DIR = BASE_DIR / "models"

with open(MODEL_DIR / "model_meta.json") as f:
    meta = json.load(f)
ALL_FEATURES = meta["features"]

print("Loading matrix...")
df = pd.read_parquet(BASE_DIR / "final_feature_matrix.parquet")
df_val = df[df["date"].dt.year == 2025].copy()
print(f"2025 validation: {len(df_val)} rows, {df_val['race_id'].nunique()} races")

print("Loading models...")
lgb_m = lgb.Booster(model_file=str(MODEL_DIR / "model_lgb.txt"))
xgb_m = xgb.Booster(); xgb_m.load_model(str(MODEL_DIR / "model_xgb.json"))
cat_m = CatBoost(); cat_m.load_model(str(MODEL_DIR / "model_cat.cbm"))
enc = pickle.load(open(str(MODEL_DIR / "xgb_encoder.pkl"), "rb"))

def norm(s): mn, mx = s.min(), s.max(); return (s - mn) / (mx - mn + 1e-9)

results = []
for race_id, grp in df_val.groupby("race_id"):
    avail = [f for f in ALL_FEATURES if f in grp.columns]
    X = grp[avail].reindex(columns=ALL_FEATURES, fill_value=0)
    for col in ["venue", "track_type", "course", "race_class", "track_condition"]:
        if col in X.columns:
            X[col] = X[col].astype("category")
    lgb_s = lgb_m.predict(X)
    xgb_s = xgb_m.predict(xgb.DMatrix(X, enable_categorical=True))
    cat_s = cat_m.predict(X)
    score = (norm(lgb_s) + norm(pd.Series(xgb_s)) + norm(pd.Series(cat_s))) / 3.0
    grp = grp.copy()
    grp["score"] = score.values
    grp["rank"] = grp["score"].rank(ascending=False, method="first").astype(int)
    results.append(grp)

df_r = pd.concat(results)

print("\n" + "="*60)
print("  PLACE BET BACKTEST — 2025 (840 races)")
print("="*60)

for pick_rank in [1, 2, 3]:
    picks = df_r[df_r["rank"] == pick_rank].copy()
    total = len(picks)
    placed = picks["is_place"].sum()
    hit_rate = placed / total

    # Simulate place bets: HKJC place odds ≈ win_odds / 4 (rough estimate)
    picks["place_odds_est"] = (picks["win_odds"] / 4).clip(lower=1.05)

    # Filter: only bet when estimated place odds > threshold
    for min_odds in [1.2, 1.5, 2.0, 2.5]:
        subset = picks[picks["place_odds_est"] >= min_odds]
        if len(subset) == 0:
            continue
        n = len(subset)
        hits = subset["is_place"].sum()
        hr = hits / n
        roi = (hr * subset["place_odds_est"].mean()) - 1.0
        print(f"\n  Rank-{pick_rank} | Place odds >= {min_odds:.1f} | n={n} | Hit={hr:.1%} | Est. ROI={roi:+.1%}")

print("\n" + "="*60)
print("  ACTUAL ODDS BREAKDOWN (rank-1 picks by win_odds bucket)")
print("="*60)
rank1 = df_r[df_r["rank"] == 1].copy()
rank1["odds_bucket"] = pd.cut(rank1["win_odds"], bins=[0, 3, 5, 8, 15, 100], labels=["<3", "3-5", "5-8", "8-15", "15+"])
rank1["place_odds_est"] = (rank1["win_odds"] / 4).clip(lower=1.05)
for bucket, grp in rank1.groupby("odds_bucket", observed=True):
    n = len(grp)
    hr = grp["is_place"].mean()
    avg_place_odds = grp["place_odds_est"].mean()
    roi = hr * avg_place_odds - 1.0
    print(f"  Win odds {bucket:>5} | n={n:>4} | Place hit={hr:.1%} | Avg place odds={avg_place_odds:.2f} | ROI={roi:+.1%}")
