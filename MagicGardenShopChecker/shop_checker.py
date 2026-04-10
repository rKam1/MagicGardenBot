import json
import os
import re
from pathlib import Path

import requests

API_URL = "https://mg-api.ariedam.fr/live/shops"
WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]
PING_ROLE_ID = os.environ["PING_ROLE_ID"]

TRACKED_ITEMS = {
    "cactus": "Cactus",
    "bamboo": "Bamboo",
    "violetcort": "Violet Cort",
    "passionfruit": "Passion Fruit",
    "sunflower": "Sunflower",
    "starweaver": "Starweaver",
    "dawnbinder": "Dawnbinder",
    "moonbinder": "Moonbinder",
}

STATE_FILE = Path(__file__).parent / "shop_state.json"


def normalize_name(text):
    return re.sub(r"[^a-z0-9]", "", text.lower())


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


def get_in_stock_rare_items(in_stock_items):
    found = []

    for item in in_stock_items:
        normalized_item_name = normalize_name(item["name"])

        for tracked_key, display_name in TRACKED_ITEMS.items():
            if tracked_key in normalized_item_name:
                found.append({
                    "name": item["name"],
                    "display_name": display_name,
                    "stock": item["stock"],
                    "category": item["category"],
                })
                break

    return found


def load_previous_state():
    if not STATE_FILE.exists():
        return None
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def save_state(data):
    STATE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def send_discord_alert(found_rare_items, in_stock_items):
    rare_text = ", ".join(item["display_name"] for item in found_rare_items)
    stock_lines = "\n".join(
        f"• {item['name']} x{item['stock']} ({item['category']})"
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
    print("Discord status:", r.status_code)
    print("Discord response:", r.text)
    r.raise_for_status()


def main():
    current_shop = fetch_shop_data()
    current_in_stock = get_in_stock_items(current_shop)
    current_rare = get_in_stock_rare_items(current_in_stock)

    print("Current in-stock items:", [item["name"] for item in current_in_stock])
    print("Current rare items:", [item["display_name"] for item in current_rare])

    previous_shop = load_previous_state()

    if previous_shop is None or previous_shop == {}:
        print("No previous state found. Saving baseline.")
        save_state(current_shop)
        return

    if current_shop != previous_shop:
        print("Shop changed.")

        if current_rare:
            print("Tracked rare items found:", [item["display_name"] for item in current_rare])
            send_discord_alert(current_rare, current_in_stock)
            print("Alert sent.")
        else:
            print("Shop changed, but no tracked rare items are currently in stock.")
    else:
        print("No shop change detected.")

    save_state(current_shop)


if __name__ == "__main__":
    main()
