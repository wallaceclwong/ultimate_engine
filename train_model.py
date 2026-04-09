"""
train_model.py
─────────────────────────────────────────────────────────────────
Ultimate Hybrid Engine — Step 2: Triple Ensemble Training

Trains three ranking models on 82,386 horse-race records:
  - LightGBM  (lambdarank)
  - XGBoost   (rank:pairwise)
  - CatBoost  (YetiRank)

Temporal split:
  Train : 2018-2024  (~70k rows)
  Val   : 2025       (~10k rows)
  Test  : 2026       (held out, used in backtest.py)

Output:
  ~/ultimate_engine/models/model_lgb.txt
  ~/ultimate_engine/models/model_xgb.json
  ~/ultimate_engine/models/model_cat.cbm
  ~/ultimate_engine/models/xgb_encoder.pkl
  ~/ultimate_engine/models/model_meta.json

Run on: Vultr VM
Usage : python3 train_model.py
"""

import json
import pickle
import pandas as pd
import numpy as np
from pathlib import Path

import lightgbm as lgb
import xgboost as xgb
from catboost import CatBoost, Pool
from sklearn.preprocessing import OrdinalEncoder

# ─── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).parent.absolute()
TRAINING_FILE = BASE_DIR / "training_data_hybrid.parquet"
MODEL_DIR     = BASE_DIR / "models"
MODEL_DIR.mkdir(exist_ok=True)


# ─── Load Data ───────────────────────────────────────────────────────────────
print("=" * 60)
print("  Ultimate Hybrid Engine -- Step 2: Train Ensemble")
print("=" * 60)
print("\nLoading training data...")
df = pd.read_parquet(TRAINING_FILE)
df["date"] = pd.to_datetime(df["date"])
df["race_id"] = df["race_id"].astype(str)  # Fix: ensure mixed int/str race_id is uniform

# Filter out rows with unknown positions (plc=99)
df = df[df["plc"] != 99].reset_index(drop=True)

print(f"Loaded {len(df):,} horse-race rows (after filtering unknown positions)")
print(f"Date range: {df['date'].min().date()} -> {df['date'].max().date()}")
print(f"Unique races: {df['race_id'].nunique():,}")

# --- Data Cleanup: Force Numeric Types ---
# (Handles cases where some columns might be 'object' due to NaNs or processing issues)
FORCED_NUMERIC = [
    "last_6_avg", "last_6_best", "last_2_avg", "last_6_trend",
    "gear_change", "stable_change", "distance", "ai_unluckiness",
    "win_odds", "market_implied_prob", "actual_wt",
    "finish_time_secs", "race_sec_sum", "sec_pos_1", "sec_pos_2", "sec_pos_pre"
]
for col in FORCED_NUMERIC:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')

# Populate race_sec_sum from real finish_time_secs data
# finish_time_secs has real per-race timing; race_sec_sum was always a placeholder (70.0)
if "finish_time_secs" in df.columns:
    real_mask = df["finish_time_secs"] > 0
    df.loc[real_mask, "race_sec_sum"] = df.loc[real_mask, "finish_time_secs"]
    print(f"Populated race_sec_sum from finish_time_secs for {real_mask.sum():,} rows.")

print("Data types cleaned.")


# ─── Feature Engineering ─────────────────────────────────────────────────────
print("\nEngineering features...")

# 1. Jockey / Trainer win & place rates (historical overall - LEAKAGE FIXED)
# Important: We must mask the data to ONLY the training period (<= 2024) 
# when calculating these aggregate statistics to prevent leakage.
df["year"] = df["date"].dt.year
train_mask = df["year"] <= 2024

# 1. Jockey / Trainer win & place rates (Expanding Mean - NO LEAKAGE)
# This calculates the average performance of each jockey/trainer up to (but not including) the current race.
# It is the most realistic way to train a betting model.
df = df.sort_values("date")

def calculate_expanding_stats(group_col, target_col, prefix):
    # Calculate expanding mean (average of all previous races)
    stats = df.groupby(group_col)[target_col].expanding().mean().reset_index(level=0, drop=True)
    # Shift by 1 to exclude the current race's result
    stats = df.groupby(group_col)[target_col].shift(1).fillna(0) # Simple shift (caution: needs careful handling of first race)
    # Actually, a better way for expanding mean without leakage:
    expanded = df.groupby(group_col)[target_col].apply(lambda x: x.shift(1).expanding().mean())
    df[f"{prefix}_{target_col}_rate"] = expanded.reset_index(level=0, drop=True)

print("Calculating expanding stats for jockeys...")
df['jockey_win_rate'] = df.groupby('jockey')['is_win'].apply(lambda x: x.shift(1).expanding().mean()).reset_index(level=0, drop=True)
df['jockey_place_rate'] = df.groupby('jockey')['is_place'].apply(lambda x: x.shift(1).expanding().mean()).reset_index(level=0, drop=True)
df['jockey_rides'] = df.groupby('jockey').cumcount()

print("Calculating expanding stats for trainers...")
df['trainer_win_rate'] = df.groupby('trainer')['is_win'].apply(lambda x: x.shift(1).expanding().mean()).reset_index(level=0, drop=True)
df['trainer_place_rate'] = df.groupby('trainer')['is_place'].apply(lambda x: x.shift(1).expanding().mean()).reset_index(level=0, drop=True)
df['trainer_starts'] = df.groupby('trainer').cumcount()

# Fill NaNs from first-time runners
df = df.fillna(0)

# 2. Odds rank within race (1 = favourite)
df["odds_rank"] = df.groupby("race_id")["win_odds"].rank(method="min", ascending=True)

# 3. Implied probability normalised to sum to 1 within each race
df["implied_prob_norm"] = df.groupby("race_id")["market_implied_prob"].transform(
    lambda x: x / x.sum()
)

# 4. Relevance label for ranking: winner gets highest score
#    winner (plc=1) -> field_size-1, last -> 0
df["relevance"] = np.maximum(0, df["field_size"] - df["plc"]).astype(int)

for col in ["venue", "track_type", "course", "race_class", "track_condition"]:
    if col in df.columns:
        df[col] = df[col].fillna("Unknown").astype(str)
    else:
        df[col] = "Unknown"

print("Features engineered.")


FINAL_MATRIX = BASE_DIR / "final_feature_matrix.parquet"
# Sanitize all object columns to string to prevent PyArrow mixed-type errors
# (learn_today.py appends can introduce int race_id/horse_id alongside str ones)
# Exclude 'date' which is datetime, not string
obj_cols = [c for c in df.select_dtypes(include=["object"]).columns if c != "date"]
for col in obj_cols:
    df[col] = df[col].astype(str)
df.to_parquet(FINAL_MATRIX, index=False)
print(f"Unified feature matrix saved to: {FINAL_MATRIX}")


# ─── Feature Definitions ─────────────────────────────────────────────────────
NUMERIC_FEATURES = [
    # Market signals
    "win_odds", "market_implied_prob", "implied_prob_norm", "odds_rank",
    # Physical
    "actual_wt", "draw", "draw_relative", "field_size",
    # Connections
    "jockey_win_rate", "jockey_place_rate", "jockey_rides",
    "trainer_win_rate", "trainer_place_rate",
    "last_6_avg", "last_6_best", "last_2_avg", "last_6_trend",
    "gear_change", "stable_change",
    # AI Sentiment (Hybrid Layer)
    "ai_unluckiness",
    # Race context
    "distance",
    # Sectionals (NEW Stage 4)
    "race_sec_sum", "sec_pos_1", "sec_pos_2", "sec_pos_pre"
]

# Ensure all expected features exist, filling missing ones with neutral defaults
for col in NUMERIC_FEATURES:
    if col not in df.columns:
        # Default for sectional positions (sec_pos_1, etc.) is usually around 6.0
        default_val = 6.0 if "sec_pos" in col else 0.0
        df[col] = default_val

CATEGORICAL_FEATURES = ["venue", "track_type", "course", "race_class", "track_condition"]
ALL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES

# Convert categoricals to pandas category dtype (required by LightGBM)
for col in CATEGORICAL_FEATURES:
    df[col] = df[col].astype("category")


# ─── Temporal Split ──────────────────────────────────────────────────────────
df["date"] = pd.to_datetime(df["date"], errors="coerce")  # Re-ensure datetime after sanitization
df["year"] = df["date"].dt.year

train_df = df[df["year"] <= 2024].sort_values("race_id").reset_index(drop=True)
val_df   = df[df["year"] == 2025].sort_values("race_id").reset_index(drop=True)
test_df  = df[df["year"] == 2026].sort_values("race_id").reset_index(drop=True)

print(f"\nTrain (2018-2024): {len(train_df):,} rows  |  {train_df['race_id'].nunique():,} races")
print(f"Val   (2025):      {len(val_df):,} rows  |  {val_df['race_id'].nunique():,} races")
print(f"Test  (2026):      {len(test_df):,} rows  |  {test_df['race_id'].nunique():,} races")

X_train = train_df[ALL_FEATURES]
y_train = train_df["relevance"]
X_val   = val_df[ALL_FEATURES]
y_val   = val_df["relevance"]

train_groups = train_df.groupby("race_id", sort=False).size().values
val_groups   = val_df.groupby("race_id",   sort=False).size().values


# ─── Evaluation Helper ───────────────────────────────────────────────────────
def evaluate_top1(name, scores, df_eval):
    """
    For each race: rank horses by predicted score, check if top-1 is the winner.
    Also compare against 'just pick the favourite' baseline.
    """
    ev = df_eval.copy()
    ev["score"]     = scores
    ev["pred_rank"] = ev.groupby("race_id")["score"].rank(ascending=False, method="first")

    top1 = ev[ev["pred_rank"] == 1]
    win_acc   = top1["is_win"].mean()
    place_acc = top1["is_place"].mean()

    # Favourite baseline
    fav_win = ev[ev["odds_rank"] == 1]["is_win"].mean()

    print(f"\n  {name}")
    print(f"    Win accuracy   : {win_acc:.1%}  (fav baseline: {fav_win:.1%})")
    print(f"    Place accuracy : {place_acc:.1%}")
    print(f"    Races assessed : {ev['race_id'].nunique():,}")

    return win_acc, place_acc


# ═════════════════════════════════════════════════════════════════════════════
# MODEL 1: LightGBM (lambdarank)
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("  Model 1 of 3: LightGBM (lambdarank)")
print("=" * 60)

lgb_train_ds = lgb.Dataset(
    X_train, label=y_train, group=train_groups,
    categorical_feature=CATEGORICAL_FEATURES, free_raw_data=False
)
lgb_val_ds = lgb.Dataset(
    X_val, label=y_val, group=val_groups,
    reference=lgb_train_ds
)

lgb_params = {
    "objective":        "lambdarank",
    "metric":           "ndcg",
    "ndcg_eval_at":     [1, 3],
    "learning_rate":    0.05,
    "num_leaves":       64,
    "min_data_in_leaf": 20,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq":     5,
    "verbose":          -1,
    "n_jobs":           -1,
}

lgb_model = lgb.train(
    lgb_params,
    lgb_train_ds,
    num_boost_round=500,
    valid_sets=[lgb_val_ds],
    callbacks=[lgb.early_stopping(30), lgb.log_evaluation(50)],
)

lgb_scores = lgb_model.predict(X_val)
lgb_win, lgb_place = evaluate_top1("LightGBM", lgb_scores, val_df)
lgb_model.save_model(str(MODEL_DIR / "model_lgb.txt"))
print(f"  Saved: models/model_lgb.txt")


# ═════════════════════════════════════════════════════════════════════════════
# MODEL 2: XGBoost (rank:pairwise)
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("  Model 2 of 3: XGBoost (rank:pairwise)")
print("=" * 60)

# XGBoost needs encoded categoricals
enc = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)
X_train_xgb = X_train.copy()
X_val_xgb   = X_val.copy()
# Convert category dtype to string for OrdinalEncoder compatibility
for col in CATEGORICAL_FEATURES:
    X_train_xgb[col] = X_train_xgb[col].astype(str)
    X_val_xgb[col]   = X_val_xgb[col].astype(str)
X_train_xgb[CATEGORICAL_FEATURES] = enc.fit_transform(X_train_xgb[CATEGORICAL_FEATURES])
X_val_xgb[CATEGORICAL_FEATURES]   = enc.transform(X_val_xgb[CATEGORICAL_FEATURES])

xgb_train_dm = xgb.DMatrix(X_train_xgb, label=y_train)
xgb_train_dm.set_group(train_groups)
xgb_val_dm   = xgb.DMatrix(X_val_xgb, label=y_val)
xgb_val_dm.set_group(val_groups)

xgb_params = {
    "objective":         "rank:pairwise",
    "eval_metric":       "ndcg@1",
    "eta":               0.05,
    "max_depth":         6,
    "subsample":         0.8,
    "colsample_bytree":  0.8,
    "min_child_weight":  10,
    "verbosity":         0,
    "nthread":           -1,
}

xgb_model = xgb.train(
    xgb_params,
    xgb_train_dm,
    num_boost_round=500,
    evals=[(xgb_val_dm, "val")],
    early_stopping_rounds=30,
    verbose_eval=50,
)

xgb_scores = xgb_model.predict(xgb_val_dm)
xgb_win, xgb_place = evaluate_top1("XGBoost", xgb_scores, val_df)
xgb_model.save_model(str(MODEL_DIR / "model_xgb.json"))
pickle.dump(enc, open(str(MODEL_DIR / "xgb_encoder.pkl"), "wb"))
print(f"  Saved: models/model_xgb.json")


# ═════════════════════════════════════════════════════════════════════════════
# MODEL 3: CatBoost (YetiRank)
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("  Model 3 of 3: CatBoost (YetiRank)")
print("=" * 60)

cat_feat_idx = [ALL_FEATURES.index(c) for c in CATEGORICAL_FEATURES]

train_pool = Pool(
    data=X_train, label=y_train,
    group_id=train_df["race_id"],
    cat_features=cat_feat_idx,
    feature_names=ALL_FEATURES,
)
val_pool = Pool(
    data=X_val, label=y_val,
    group_id=val_df["race_id"],
    cat_features=cat_feat_idx,
    feature_names=ALL_FEATURES,
)

cat_model = CatBoost({
    "loss_function":         "YetiRank",
    "eval_metric":           "NDCG:top=1",
    "iterations":            500,
    "learning_rate":         0.05,
    "depth":                 6,
    "early_stopping_rounds": 30,
    "verbose":               50,
    "task_type":             "CPU",
    "thread_count":          -1,
})

cat_model.fit(train_pool, eval_set=val_pool, use_best_model=True)
cat_scores = cat_model.predict(val_pool)
cat_win, cat_place = evaluate_top1("CatBoost", cat_scores, val_df)
cat_model.save_model(str(MODEL_DIR / "model_cat.cbm"))
print(f"  Saved: models/model_cat.cbm")


# ═════════════════════════════════════════════════════════════════════════════
# ENSEMBLE: Average of all 3
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("  Final: Ensemble (avg of all 3 models)")
print("=" * 60)


def norm(s):
    mn, mx = s.min(), s.max()
    return (s - mn) / (mx - mn + 1e-9)


ensemble_scores = (norm(lgb_scores) + norm(xgb_scores) + norm(cat_scores)) / 3.0
ens_win, ens_place = evaluate_top1("ENSEMBLE", ensemble_scores, val_df)


# ─── Feature Importance (LightGBM) ───────────────────────────────────────────
print("\n-- Top 15 Most Important Features (LightGBM gain) --")
fi = pd.Series(
    lgb_model.feature_importance(importance_type="gain"),
    index=ALL_FEATURES
).sort_values(ascending=False)

for feat, score in fi.head(15).items():
    bar = "=" * int(score / fi.max() * 30)
    print(f"  {feat:<28} {bar}")


# ─── Save Metadata ───────────────────────────────────────────────────────────
meta = {
    "train_rows":      int(len(train_df)),
    "val_rows":        int(len(val_df)),
    "train_races":     int(train_df["race_id"].nunique()),
    "val_races":       int(val_df["race_id"].nunique()),
    "features":        ALL_FEATURES,
    "lgb_win_acc":     round(lgb_win, 4),
    "xgb_win_acc":     round(xgb_win, 4),
    "cat_win_acc":     round(cat_win, 4),
    "ensemble_win_acc":round(ens_win, 4),
    "lgb_place_acc":   round(lgb_place, 4),
    "ensemble_place_acc": round(ens_place, 4),
}

with open(str(MODEL_DIR / "model_meta.json"), "w") as f:
    json.dump(meta, f, indent=2)

print(f"\n{'='*60}")
print(f"  STEP 2 COMPLETE")
print(f"{'='*60}")
print(f"  LightGBM  win accuracy : {lgb_win:.1%}")
print(f"  XGBoost   win accuracy : {xgb_win:.1%}")
print(f"  CatBoost  win accuracy : {cat_win:.1%}")
print(f"  ENSEMBLE  win accuracy : {ens_win:.1%}")
print(f"\n  Models saved to: ~/ultimate_engine/models/")
print(f"  -> Next: python3 backtest.py")
