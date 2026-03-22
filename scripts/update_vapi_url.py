"""
CareCloud — Update Vapi Assistant Server URL
Run this every time your ngrok URL changes:
    python scripts/update_vapi_url.py

It reads VAPI_API_KEY, VAPI_ASSISTANT_ID, and BASE_URL from .env
"""
import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

VAPI_API_KEY      = os.getenv("VAPI_API_KEY")
VAPI_ASSISTANT_ID = os.getenv("VAPI_ASSISTANT_ID", "4eea5695-5661-4b0d-82ce-a9ff04793706")
BASE_URL          = os.getenv("BASE_URL")

if not VAPI_API_KEY:
    print("❌  VAPI_API_KEY not set in .env")
    sys.exit(1)

if not BASE_URL:
    print("❌  BASE_URL not set in .env")
    sys.exit(1)

webhook_url = f"{BASE_URL}/webhook"
print(f"🔄  Updating Vapi assistant {VAPI_ASSISTANT_ID}")
print(f"    serverUrl → {webhook_url}")

resp = requests.patch(
    f"https://api.vapi.ai/assistant/{VAPI_ASSISTANT_ID}",
    json={"serverUrl": webhook_url},
    headers={
        "Authorization": f"Bearer {VAPI_API_KEY}",
        "Content-Type": "application/json",
    },
    timeout=60,
)

if resp.status_code == 200:
    print("✅  Vapi assistant updated successfully!")
    print(f"    Name: {resp.json().get('name')}")
else:
    print(f"❌  Failed: {resp.status_code} — {resp.text}")
    sys.exit(1)
