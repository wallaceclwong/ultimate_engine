import os
import sys
from dotenv import load_dotenv
from openai import OpenAI

def test_connectivity():
    # Force UTF-8 for output
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass
    
    print("--- DEEPSEEK CONNECTIVITY TEST (VM) ---")
    load_dotenv()
    api_key = os.getenv("DEEPSEEK_API_KEY")
    
    if not api_key:
        print("[ERROR] DEEPSEEK_API_KEY not found in .env")
        sys.exit(1)
        
    print(f"Using API Key ending in: ...{api_key[-4:]}")
    
    try:
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        print("Sending test request to 'deepseek-chat'...")
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": "Test connectivity. Reply with OK."}],
            max_tokens=20,
            timeout=30
        )
        content = response.choices[0].message.content.strip()
        
        # Safe ASCII printing to avoid VM terminal encoding issues
        safe_content = content.encode('ascii', errors='replace').decode('ascii')
        print(f"DeepSeek Response (Safe-ASCII): {safe_content}")
        
        if content:
            print("\n[SUCCESS] VM -> DeepSeek connectivity confirmed.")
        else:
            print("\n[WARNING] Empty response.")
            
    except Exception as e:
        print(f"\n[ERROR] Connectivity FAILED: {str(e).encode('ascii', 'replace').decode('ascii')}")
        sys.exit(1)

if __name__ == "__main__":
    test_connectivity()
