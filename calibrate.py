import pandas as pd
import numpy as np

# Load backtest results
df = pd.read_csv("/root/ultimate_engine/backtest_results.csv")
df["win"] = (df["result"] == "WIN").astype(int)

# Bin the probabilities to see if they are "Overconfident"
# (e.g. if we say 60% prob, does it win 60% of the time?)
bins = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 1.0]
df["prob_bin"] = pd.cut(df["prob"], bins=bins)

calibration = df.groupby("prob_bin", observed=True).agg(
    count=("win", "count"),
    mean_prob=("prob", "mean"),
    actual_win_rate=("win", "mean")
).reset_index()

print("=== PROBABILITY CALIBRATION REPORT ===")
print(calibration)

# Check for "Overconfidence"
overconfidence = (calibration["mean_prob"] - calibration["actual_win_rate"]).dropna()
print(f"\nAverage Overconfidence: {overconfidence.mean():.1%}")
if overconfidence.mean() > 0.05:
    print("WARNING: Model is heavily OVERCONFIDENT. Probabilities are too high.")
elif overconfidence.mean() < -0.05:
    print("WARNING: Model is UNDERCONFIDENT. Probabilities are too low.")
else:
    print("Model is reasonably calibrated.")

# Top 5 biggest losses/wins
print("\n=== TOP 5 BIGGEST BETS ===")
print(df.sort_values("stake_amt", ascending=False)[["horse", "prob", "odds", "stake_amt", "profit", "result"]].head(10))
