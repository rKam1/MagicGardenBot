import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

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
    "Pepper": ["pepper"],
    "Lemon": ["lemon"],
    "Dragon Fruit": ["dragonfruit"],
    "Crysanthemum": ["crysanthemum"],
    "Cacao": ["cacao"],
    "Lychee": ["lychee"],
}

STATE_FILE = Path(__file__).parent / "shop_state.json"
POLL_SECONDS = 20
ALERT_COOLDOWN_SECONDS = 300  # 5 minutes


def normalize_name(text):
    return re.sub(r"[^a-z0-9]", "", text.lower())


def utc_now():
    return datetime.now(timezone.utc)


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


def make_alert_key(tracked_items):
    names = sorted(set(item["display_name"] for item in tracked_items))
    return "|".join(names)


def load_state():
    if not STATE_FILE.exists():
        return {
            "last_shop": None,
            "last_alert_key": None,
            "last_alert_time": None,
        }

    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        data = {}

    return {
        "last_shop": data.get("last_shop"),
        "last_alert_key": data.get("last_alert_key"),
        "last_alert_time": data.get("last_alert_time"),
    }


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def should_send_alert(state, alert_key):
    last_alert_key = state.get("last_alert_key")
    last_alert_time = state.get("last_alert_time")

    if last_alert_key == alert_key and last_alert_time:
        try:
            last_time = datetime.fromisoformat(last_alert_time)
            if utc_now() - last_time < timedelta(seconds=ALERT_COOLDOWN_SECONDS):
                print("Skipping duplicate alert within cooldown window.")
                return False
        except Exception:
            pass

    return True


def send_discord_alert(tracked_items):
    tracked_text = ", ".join(sorted(set(item["display_name"] for item in tracked_items)))

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


def run_check():
    state = load_state()

    current_shop = fetch_shop_data()
    current_in_stock = get_in_stock_items(current_shop)
    current_tracked = get_in_stock_tracked_items(current_in_stock)

    print("Current in-stock items:", [item["name"] for item in current_in_stock])
    print("Current tracked items:", [item["display_name"] for item in current_tracked])

    previous_shop = state["last_shop"]

    if previous_shop is None:
        print("No previous state found. Saving baseline.")
        state["last_shop"] = current_shop
        save_state(state)
        return

    if current_shop != previous_shop:
        print("Shop changed.")

        if current_tracked:
            print("Tracked items found:", [item["display_name"] for item in current_tracked])

            alert_key = make_alert_key(current_tracked)

            if should_send_alert(state, alert_key):
                send_discord_alert(current_tracked)
                print("Alert sent.")
                state["last_alert_key"] = alert_key
                state["last_alert_time"] = utc_now().isoformat()
            else:
                print("Alert suppressed by dedupe/cooldown.")
        else:
            print("Shop changed, but no tracked items are currently in stock.")
    else:
        print("No shop change detected.")

    state["last_shop"] = current_shop
    save_state(state)


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
