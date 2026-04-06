import pandas as pd
import numpy as np
from pathlib import Path

# Paths
BASE_DIR      = Path(__file__).parent.absolute()
TRAINING_FILE = BASE_DIR / "training_data_hybrid.parquet"
FINAL_MATRIX  = BASE_DIR / "final_feature_matrix.parquet"

print("Loading data...")
df = pd.read_parquet(TRAINING_FILE)
df["date"] = pd.to_datetime(df["date"])
df = df.sort_values("date").reset_index(drop=True)

# Jockey Stats
print("Computing Jockey Stats...")
# Win rate: rolling mean (expanding) shift 1
df['jockey_win_rate'] = df.groupby('jockey')['is_win'].transform(lambda x: x.shift(1).expanding().mean()).fillna(0.08)
df['jockey_place_rate'] = df.groupby('jockey')['is_place'].transform(lambda x: x.shift(1).expanding().mean()).fillna(0.23)
df['jockey_rides'] = df.groupby('jockey').cumcount().fillna(0)

# Trainer Stats
print("Computing Trainer Stats...")
df['trainer_win_rate'] = df.groupby('trainer')['is_win'].transform(lambda x: x.shift(1).expanding().mean()).fillna(0.08)
df['trainer_place_rate'] = df.groupby('trainer')['is_place'].transform(lambda x: x.shift(1).expanding().mean()).fillna(0.23)
df['trainer_starts'] = df.groupby('trainer').cumcount().fillna(0)

# Other expected columns
df["odds_rank"] = df.groupby("race_id")["win_odds"].rank(method="min", ascending=True)
df["implied_prob_norm"] = df.groupby("race_id")["market_implied_prob"].transform(lambda x: x / x.sum() if x.sum() > 0 else 0)

# Ensure string types for Parquet
for col in df.select_dtypes(include=['object']).columns:
    df[col] = df[col].astype(str)

print(f"Saving to {FINAL_MATRIX}...")
df.to_parquet(FINAL_MATRIX, index=False)
print("Final Columns:", df.columns.tolist())
