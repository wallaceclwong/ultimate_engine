import sys
from pathlib import Path

root_dir = str(Path(__file__).resolve().parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from services.memory_service import MemoryService

def pull():
    m = MemoryService()
    print("\n=== Pulling retrained models on VM ===")

    out = m._execute_cmd("cd /root/ultimate_engine && git pull origin main 2>&1")
    print(out if out else "(no output)")

    print("\n--- Model file dates ---")
    out = m._execute_cmd("ls -lh /root/ultimate_engine/models/")
    print(out if out else "(no output)")

    print("\n--- Quick sanity: model loads OK ---")
    test = """import sys
sys.path.insert(0, '/root/ultimate_engine')
import lightgbm as lgb
import xgboost as xgb
from catboost import CatBoost
m1 = lgb.Booster(model_file='/root/ultimate_engine/models/model_lgb.txt')
m2 = xgb.Booster(); m2.load_model('/root/ultimate_engine/models/model_xgb.json')
m3 = CatBoost().load_model('/root/ultimate_engine/models/model_cat.cbm')
print('LightGBM trees:', m1.num_trees())
print('XGBoost trees:', m2.num_boosted_rounds())
print('CatBoost iters:', m3.tree_count_)
print('ALL MODELS OK')
"""
    m._execute_cmd("cat > /tmp/check_models.py << 'PYEOF'\n" + test + "\nPYEOF")
    out = m._execute_cmd("/root/ultimate_engine/.venv/bin/python /tmp/check_models.py 2>&1")
    print(out if out else "(no output)")

if __name__ == "__main__":
    pull()
