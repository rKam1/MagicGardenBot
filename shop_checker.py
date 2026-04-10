import json
import os
import re
import time
from pathlib import Path
from datetime import datetime, timedelta

import requests

API_URL = "https://mg-api.ariedam.fr/live/shops"
WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]
PING_ROLE_ID = os.environ["PING_ROLE_ID"]

TRACKED_ITEMS = {
    "Cactus": ["cactus"],
    "Bamboo": ["bamboo"],
    "Violet Cort": ["violetcort", "violetcortspore"],
    "Passion Fruit": ["passionfruit", "passionfruitseed"],
    "Sunflower": ["sunflower", "sunflowerseed"],
    "Starweaver Pod": ["starweaver", "starweaverpod"],
    "Dawnbinder Pod": ["dawnbinder", "dawnbinderpod"],
    "Moonbinder Pod": ["moonbinder", "moonbinderpod"],
    "Burro's Tail": ["burrostail"],
}

STATE_FILE = Path(__file__).parent / "shop_state.json"
LAST_ALERT_TIME = None
COOLDOWN = timedelta(minutes=5)
POLL_SECONDS = 20


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


def get_in_stock_tracked_items(in_stock_items):
    found = []

    for item in in_stock_items:
        normalized_item_name = normalize_name(item["name"])

        for display_name, aliases in TRACKED_ITEMS.items():
            if any(alias in normalized_item_name for alias in aliases):
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


def send_discord_alert(tracked_items):
    global LAST_ALERT_TIME

    now = datetime.utcnow()

    if LAST_ALERT_TIME is not None:
        if now - LAST_ALERT_TIME < COOLDOWN:
            print("Skipping alert due to cooldown.")
            return

    tracked_text = ", ".join(item["display_name"] for item in tracked_items)

    payload = {
        "content": f"<@&{PING_ROLE_ID}> tracked item spotted in the shop: **{tracked_text}**",
        "allowed_mentions": {
            "roles": [PING_ROLE_ID]
        }
    }

    r = requests.post(WEBHOOK_URL, json=payload, timeout=20)
    print("Discord status:", r.status_code)
    print("Discord response:", r.text)
    r.raise_for_status()

    LAST_ALERT_TIME = now


def run_check():
    current_shop = fetch_shop_data()
    current_in_stock = get_in_stock_items(current_shop)
    current_tracked = get_in_stock_tracked_items(current_in_stock)

    print("Current in-stock items:", [item["name"] for item in current_in_stock])
    print("Current tracked items:", [item["display_name"] for item in current_tracked])

    previous_shop = load_previous_state()

    if previous_shop is None or previous_shop == {}:
        print("No previous state found. Saving baseline.")
        save_state(current_shop)
        return

    if current_shop != previous_shop:
        print("Shop changed.")

        if current_tracked:
            print("Tracked items found:", [item["display_name"] for item in current_tracked])
            send_discord_alert(current_tracked)
            print("Alert sent.")
        else:
            print("Shop changed, but no tracked items are currently in stock.")
    else:
        print("No shop change detected.")

    save_state(current_shop)


def main():
    print("Starting Railway shop checker...")
    while True:
        try:
            run_check()
        except Exception as e:
            print("Error during check:", repr(e))
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
