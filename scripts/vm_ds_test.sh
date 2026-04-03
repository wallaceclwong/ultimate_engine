#!/bin/bash
echo "--- DEEPSEEK CONNECTIVITY TEST (CURL) ---"
# Load key from .env
DS_KEY=$(grep DEEPSEEK_API_KEY /root/ultimate_engine/.env | cut -d'=' -f2 | tr -d '"' | tr -d "'")

if [ -z "$DS_KEY" ]; then
    echo "[ERROR] DEEPSEEK_API_KEY not found in .env"
    exit 1
fi

echo "Testing with key ending in: ...${DS_KEY: -4}"

response=$(curl -s -w "\n%{http_code}" https://api.deepseek.com/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $DS_KEY" \
  -d '{
    "model": "deepseek-chat",
    "messages": [{"role": "user", "content": "hi"}],
    "max_tokens": 5
  }')

http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | head -n -1)

echo "HTTP Code: $http_code"
if [ "$http_code" -eq 200 ]; then
    echo "[SUCCESS] DeepSeek API reachable from VM."
    echo "Response: $body"
else
    echo "[ERROR] API call failed."
    echo "Body: $body"
    exit 1
fi
