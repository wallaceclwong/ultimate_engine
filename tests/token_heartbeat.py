import os
import asyncio
import httpx
from openai import AsyncOpenAI
from dotenv import load_dotenv
from pathlib import Path

# Load credentials
BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / ".env")

async def test_tokens():
    print("--- 🩺 TOKEN HEARTBEAT CHECK ---")
    
    # 1. Test DeepSeek API
    ds_key = os.getenv("DEEPSEEK_API_KEY")
    print(f"1. DeepSeek Key (ends in {ds_key[-4:]})...", end=" ")
    try:
        client = AsyncOpenAI(api_key=ds_key, base_url="https://api.deepseek.com")
        # Use a simple models.list to verify connectivity
        await client.models.list()
        print("[OK] (Authenticated)")
    except Exception as e:
        print(f"[FAIL] ({str(e)})")

    # 2. Test Telegram Bot Token
    tg_token = os.getenv("TELEGRAM_BOT_TOKEN")
    tg_chat = os.getenv("TELEGRAM_CHAT_ID")
    print(f"2. Telegram Bot (ends in {tg_token[-4:]})...", end=" ")
    try:
        url = f"https://api.telegram.org/bot{tg_token}/getMe"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                print(f"[OK] (Logged in as @{data['result']['username']})")
                
                # Optional: Send a tiny heartbeat message
                msg_url = f"https://api.telegram.org/bot{tg_token}/sendMessage"
                await client.post(msg_url, json={
                    "chat_id": tg_chat,
                    "text": "🛡️ *Security Restore*: Token heartbeat successful. System is LIVE.",
                    "parse_mode": "Markdown"
                })
                print("   - Heartbeat message sent to Telegram.")
            else:
                print(f"[FAIL] (Status {resp.status_code})")
    except Exception as e:
        print(f"[FAIL] ({str(e)})")

    print("--- 🏁 CHECK COMPLETE ---")

if __name__ == "__main__":
    asyncio.run(test_tokens())
