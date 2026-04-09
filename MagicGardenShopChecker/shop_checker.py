import json
import os
from pathlib import Path

import requests

API_URL = "https://mg-api.ariedam.fr/live/shops"
WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]
PING_ROLE_ID = os.environ["PING_ROLE_ID"]

RARE_ITEMS = [
    "cactus",
    "bamboo",
    "violet cort spore",
    "passion fruit",
    "sunflower",
    "starweaver pod",
    "dawnbinder pod",
    "moonbinder pod",
]

STATE_FILE = Path("shop_state.json")


def fetch_shop_data():
    r = requests.get(API_URL, timeout=20)
    r.raise_for_status()
    return r.json()


def get_in_stock_items(shop_data):
    items = []

    for category_name, category in shop_data.items():
        if isinstance(category, dict) and "items" in category:
            for item in category["items"]:
                name = item.get("name", "")
                stock = item.get("stock", 0)
                if stock and stock > 0:
                    items.append({
                        "category": category_name,
                        "name": name,
                        "stock": stock,
                    })

    return items


def find_rare_items(in_stock_items):
    found = []
    for item in in_stock_items:
        lower_name = item["name"].lower()
        for rare in RARE_ITEMS:
            if rare in lower_name:
                found.append(item["name"])
                break
    return found


def load_previous_state():
    if not STATE_FILE.exists():
        return None
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def save_state(data):
    STATE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def send_discord_alert(found_items, in_stock_items):
    rare_text = ", ".join(found_items)
    stock_lines = "\n".join(
        f"- {item['name']} x{item['stock']} ({item['category']})"
        for item in in_stock_items
    )

    payload = {
        "content": (
            f"<@&{PING_ROLE_ID}> rare item spotted in the shop: **{rare_text}**\n\n"
            f"**Items currently in stock:**\n{stock_lines}"
        ),
        "allowed_mentions": {
            "roles": [PING_ROLE_ID]
        }
    }

    r = requests.post(WEBHOOK_URL, json=payload, timeout=20)
    r.raise_for_status()

def main():
    send_discord_alert(
        ["test rare item"],
        [
            {"name": "Cactus", "stock": 3, "category": "seed"},
            {"name": "Bamboo", "stock": 2, "category": "seed"},
        ]
    )
    print("Test alert sent.")


if __name__ == "__main__":
    main()
