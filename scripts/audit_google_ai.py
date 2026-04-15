"""
Architecture Audit: Verify zero Google AI usage in live pipeline.
Run: .venv\Scripts\python.exe scripts\audit_google_ai.py
"""
import sys
import os
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

PASS = "[PASS]"
FAIL = "[FAIL]"
failures = 0

def check(cond, msg):
    global failures
    if cond:
        print(f"{PASS} {msg}")
    else:
        print(f"{FAIL} {msg}")
        failures += 1

# 1. Config
from config.settings import Config
check(Config.USE_VERTEX_AI == False, "USE_VERTEX_AI is False")
check(Config.SHADOW_MODEL == "", "SHADOW_MODEL is empty")
check(Config.DEEPSEEK_API_KEY != "", "DEEPSEEK_API_KEY is set")
check(Config.PROJECT_ID == "ultimate-engine-2026", f"GCP PROJECT_ID = {Config.PROJECT_ID}")
check(Config.GCS_BUCKET_NAME != "", f"GCS_BUCKET_NAME = {Config.GCS_BUCKET_NAME}")
check(Config.FIRESTORE_DATABASE != "", f"FIRESTORE_DATABASE = {Config.FIRESTORE_DATABASE}")
check(os.path.exists(Config.GOOGLE_APPLICATION_CREDENTIALS), f"SA key exists at {Config.GOOGLE_APPLICATION_CREDENTIALS}")

# 2. ContextCachingService tombstoned
from services.context_caching_service import ContextCachingService
try:
    ContextCachingService()
    check(False, "ContextCachingService should raise NotImplementedError")
except NotImplementedError:
    check(True, "ContextCachingService is tombstoned (raises NotImplementedError)")
except Exception as e:
    check(False, f"ContextCachingService raised unexpected: {e}")

# 3. prediction_engine.py imports
src = pathlib.Path("services/prediction_engine.py").read_text(encoding="utf-8", errors="replace")
check("from google import genai" not in src, "prediction_engine.py: no google.genai import")
check("from openai import OpenAI" in src, "prediction_engine.py: uses OpenAI-compat (DeepSeek) client")

# 4. Scan all services/*.py for google.genai
forbidden = []
for f in pathlib.Path("services").glob("*.py"):
    content = f.read_text(encoding="utf-8", errors="replace")
    if "from google import genai" in content or "google.genai" in content:
        forbidden.append(f.name)
check(len(forbidden) == 0, f"services/: zero google.genai imports" + (f" (FOUND IN: {forbidden})" if forbidden else ""))

# 5. live_audit_service loads cleanly
try:
    from services.live_audit_service import live_audit_service
    check(True, "live_audit_service loaded (Firebase FCM + DeepSeek)")
except Exception as e:
    check(False, f"live_audit_service load failed: {e}")

print()
print("=" * 45)
print("  ARCHITECTURE AUDIT RESULT")
print("=" * 45)
print(f"  AI Engine : DeepSeek-R1 ({Config.DEEPSEEK_BASE_URL})")
print(f"  GCP Cloud : {Config.PROJECT_ID} / GCS={Config.GCS_BUCKET_NAME} / FS={Config.FIRESTORE_DATABASE}")
print(f"  Google AI : DISABLED (USE_VERTEX_AI={Config.USE_VERTEX_AI}, SHADOW_MODEL='{Config.SHADOW_MODEL}')")
print("=" * 45)
if failures == 0:
    print("  STATUS: ALL CHECKS PASSED")
else:
    print(f"  STATUS: {failures} CHECK(S) FAILED")
sys.exit(failures)
