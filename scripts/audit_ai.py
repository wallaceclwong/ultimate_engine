import os
import sys
import json
from google import genai
from google.genai import types

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import Config

def audit_ai():
    print("="*60)
    print("AUDIT: VERTEX AI CONNECTIVITY")
    print("="*60)
    
    try:
        print(f"[INFO] Connecting to project: {Config.MODEL_PROJECT_ID}")
        print(f"[INFO] Location: us-central1")
        print(f"[INFO] Model: {Config.GEMINI_MODEL}")
        
        client = genai.Client(
            vertexai=True,
            project=Config.MODEL_PROJECT_ID,
            location="us-central1"
        )
        
        print("\n[INFO] Sending 2-cent test prompt...")
        response = client.models.generate_content(
            model=Config.GEMINI_MODEL,
            contents="Confirm system readiness for HKJC horse racing analysis. Reply with 'READY' and a 1-sentence analytical tip."
        )
        
        print(f"\nAI RESPONSE: {response.text.strip()}")
        
        if "READY" in response.text.upper():
            print("\n" + "="*60)
            print("✅ AI FLOW: PASSED")
            print("="*60)
        else:
            print("\n" + "="*60)
            print("⚠️ AI FLOW: UNEXPECTED RESPONSE")
            print("="*60)
            
    except Exception as e:
        print("\n" + "="*60)
        print(f"❌ AI FLOW: FAILED")
        print(f"Error: {e}")
        print("="*60)

if __name__ == "__main__":
    audit_ai()
