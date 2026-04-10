import os
import requests

WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]
PING_ROLE_ID = os.environ["PING_ROLE_ID"]

payload = {
    "content": f"<@&{PING_ROLE_ID}> GitHub Actions test message",
    "allowed_mentions": {
        "roles": [PING_ROLE_ID]
    }
}

r = requests.post(WEBHOOK_URL, json=payload, timeout=20)
print("STATUS CODE:", r.status_code)
print("RESPONSE TEXT:", r.text)
r.raise_for_status()
print("Message sent successfully.")
