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

STATE_FILE = Path(__file__).parent / "shop_state.json"

# Turn this to True for one run if you want to force a Discord alert
FORCE_ALERT = True


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
        lower_name = item["name"].lower()
        for rare in RARE_ITEMS:
            if rare in lower_name:
                found.append(item)
                break

    return found


def load_previous_state():
    if not STATE_FILE.exists():
        return None
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def save_state(data):
    STATE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def send_discord_alert(found_rare_items, in_stock_items):
    rare_text = ", ".join(item["name"] for item in found_rare_items)
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
    current_shop = fetch_shop_data()
    current_in_stock = get_in_stock_items(current_shop)
    current_rare = get_in_stock_rare_items(current_in_stock)

    print("Current in-stock items:", [item["name"] for item in current_in_stock])
    print("Current rare items:", [item["name"] for item in current_rare])

    if FORCE_ALERT:
        print("FORCE_ALERT is enabled.")
        if current_rare:
            send_discord_alert(current_rare, current_in_stock)
            print("Forced alert sent.")
        else:
            print("FORCE_ALERT enabled, but no tracked rare items are currently in stock.")
        save_state(current_shop)
        return

    previous_shop = load_previous_state()

    if previous_shop is None or not previous_shop:
        print("No previous state found. Saving baseline.")
        save_state(current_shop)
        return

    previous_in_stock = get_in_stock_items(previous_shop)
    previous_rare = get_in_stock_rare_items(previous_in_stock)

    previous_rare_names = {item["name"] for item in previous_rare}
    current_rare_names = {item["name"] for item in current_rare}

    new_rare_names = current_rare_names - previous_rare_names
    new_rare_items = [item for item in current_rare if item["name"] in new_rare_names]

    print("Previous rare items:", list(previous_rare_names))
    print("New rare items:", list(new_rare_names))

    if new_rare_items:
        send_discord_alert(new_rare_items, current_in_stock)
        print("Alert sent.")
    else:
        print("No new tracked rare items found.")

    save_state(current_shop)


if __name__ == "__main__":
    main()
