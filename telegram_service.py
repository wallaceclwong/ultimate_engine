import os
import httpx
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Load .env from same directory
BASE_DIR = Path(__file__).parent.absolute()
load_dotenv(BASE_DIR / ".env")

class TelegramService:
    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"

    async def send_message(self, text: str):
        """Sends a simple text message."""
        if not self.bot_token or not self.chat_id:
            print("[WARN] Telegram credentials missing. Skipping notification.")
            return

        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload, timeout=10)
                if response.status_code == 200:
                    return True
                else:
                    print(f"[ERROR] Telegram send failed: {response.status_code} {response.text}")
                    return False
            except Exception as e:
                print(f"[ERROR] Telegram exception: {e}")
                return False

    async def send_elite_brief(self, race_id: str, horse: str, ev: float, reasoning: str):
        """Sends a specialized Strategic Brief for high-EV tips."""
        header = f"🚀 *ULTIMATE ELITE BRIEF: {race_id}*"
        body = (
            f"\n🎯 *Pick:* {horse}"
            f"\n📊 *EV:* {ev:.2f}"
            f"\n\n🧠 *DeepSeek-R1 Strategic Consensus:*\n{reasoning}"
        )
        return await self.send_message(f"{header}\n{body}")

telegram_service = TelegramService()

if __name__ == "__main__":
    # Test block
    async def test():
        print("Testing Telegram service...")
        success = await telegram_service.send_message("🛡️ *Ultimate Engine VM* is now online & automated.")
        if success:
            print("Test message sent!")
        else:
            print("Failed to send test message.")

    asyncio.run(test())
