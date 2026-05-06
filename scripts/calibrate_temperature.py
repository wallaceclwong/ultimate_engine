import pandas as pd
import numpy as np
import lightgbm as lgb
import xgboost as xgb
from catboost import CatBoost
import pickle, json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_DIR = BASE_DIR / "models"

with open(MODEL_DIR / "model_meta.json") as f:
    meta = json.load(f)
ALL_FEATURES = meta["features"]

print("Loading data & models...")
df = pd.read_parquet(BASE_DIR / "final_feature_matrix.parquet")
df_val = df[df["date"].dt.year == 2025].copy()

lgb_m = lgb.Booster(model_file=str(MODEL_DIR / "model_lgb.txt"))
xgb_m = xgb.Booster(); xgb_m.load_model(str(MODEL_DIR / "model_xgb.json"))
cat_m = CatBoost(); cat_m.load_model(str(MODEL_DIR / "model_cat.cbm"))

def norm(s): mn, mx = s.min(), s.max(); return (s - mn) / (mx - mn + 1e-9)

# Pre-compute raw ensemble scores once
print("Scoring 2025 races...")
raw_scores = {}
for race_id, grp in df_val.groupby("race_id"):
    avail = [f for f in ALL_FEATURES if f in grp.columns]
    X = grp[avail].reindex(columns=ALL_FEATURES, fill_value=0)
    for col in ["venue", "track_type", "course", "race_class", "track_condition"]:
        if col in X.columns:
            X[col] = X[col].astype("category")
    lgb_s = lgb_m.predict(X)
    xgb_s = xgb_m.predict(xgb.DMatrix(X, enable_categorical=True))
    cat_s = cat_m.predict(X)
    ensemble = (norm(lgb_s) + norm(np.array(xgb_s)) + norm(np.array(cat_s))) / 3.0
    raw_scores[race_id] = (grp.index.tolist(), ensemble, grp["is_win"].values)

print(f"\n{'='*60}")
print(f"  TEMPERATURE CALIBRATION — 2025 ({len(raw_scores)} races)")
print(f"{'='*60}")
print(f"  {'Temp':>6} | {'LogLoss':>8} | {'Brier':>8} | {'Top1%':>7} | {'Avg fair/mkt':>13}")
print(f"  {'-'*6}-+-{'-'*8}-+-{'-'*8}-+-{'-'*7}-+-{'-'*13}")

best_temp, best_logloss = None, 999

for temp in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 1.0, 1.2, 1.5]:
    logloss_vals, brier_vals, top1_hits, fair_mkt_ratios = [], [], [], []

    for race_id, (idx, scores, is_win) in raw_scores.items():
        exp_s = np.exp((scores - scores.max()) / temp)
        probs = exp_s / exp_s.sum()

        # Log-loss (only on winner)
        winner_idx = np.argmax(is_win)
        logloss_vals.append(-np.log(probs[winner_idx] + 1e-9))

        # Brier score
        brier_vals.append(np.mean((probs - is_win) ** 2))

        # Top-1 accuracy
        top1_hits.append(int(np.argmax(probs) == winner_idx))

        # Fair odds vs market (only for winner)
        grp_rows = df_val.loc[idx]
        mkt_odds = grp_rows["win_odds"].values[winner_idx]
        fair_odds = 1.0 / (probs[winner_idx] + 1e-9)
        if mkt_odds > 0:
            fair_mkt_ratios.append(fair_odds / mkt_odds)

    ll = np.mean(logloss_vals)
    br = np.mean(brier_vals)
    t1 = np.mean(top1_hits)
    fm = np.mean(fair_mkt_ratios)

    marker = " ◄ BEST" if ll < best_logloss else ""
    if ll < best_logloss:
        best_logloss = ll
        best_temp = temp

    print(f"  {temp:>6.1f} | {ll:>8.4f} | {br:>8.4f} | {t1:>6.1%} | {fm:>12.3f}x{marker}")

print(f"\n  Optimal temperature: {best_temp}")
print(f"  (fair/mkt ratio: 1.0 = perfectly calibrated; >1.0 = model underconfident)")
print(f"\n  Current in predict_today.py: TEMPERATURE = 0.6")
if best_temp != 0.6:
    print(f"  Recommendation: change to TEMPERATURE = {best_temp}")
else:
    print(f"  Current value is already optimal.")
