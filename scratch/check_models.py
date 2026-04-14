import os
import sys
from pathlib import Path
import lightgbm as lgb
import xgboost as xgb
from catboost import CatBoost
import pickle
import json

BASE_DIR = Path("c:/Users/ASUS/ultimate_engine")
MODEL_DIR = BASE_DIR / "models"

print("Checking models...")
try:
    print("Loading LGB...")
    lgb_model = lgb.Booster(model_file=str(MODEL_DIR / "model_lgb.txt"))
    print("Loading XGB...")
    xgb_model = xgb.Booster()
    xgb_model.load_model(str(MODEL_DIR / "model_xgb.json"))
    print("Loading CAT...")
    cat_model = CatBoost().load_model(str(MODEL_DIR / "model_cat.cbm"))
    print("Loading XGB Encoder...")
    xgb_enc = pickle.load(open(str(MODEL_DIR / "xgb_encoder.pkl"), "rb"))
    print("Loading Metadata...")
    with open(str(MODEL_DIR / "model_meta.json"), "r") as f:
        meta = json.load(f)
    print("All models loaded successfully!")
except Exception as e:
    print(f"Error loading models: {e}")
