import os
import json
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

WEBHOOK = os.environ.get("DISCORD_WEBHOOK")
STATUS_FILE = "status.json"


def load_status():
    try:
        with open(STATUS_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"last_status": ""}


def save_status(status):
    with open(STATUS_FILE, "w") as f:
        json.dump({"last_status": status}, f, indent=2)


def check_tarkov():
    url = "https://status.escapefromtarkov.com"

    try:
        response = requests.get(
            url,
            timeout=20,
            headers={"User-Agent": "Tarkov-PvE-Monitor/1.0"}
        )
        response.raise_for_status()

        text = response.text.lower()

        if "maintenance" in text:
            return "MAINTENANCE"

        if "operational" in text:
            return "ONLINE"

        return "UNKNOWN"

    except requests.RequestException as error:
        print(f"Status check failed: {error}")
        return "CHECK_FAILED"


def send_discord(status):
    if not WEBHOOK:
        raise RuntimeError("DISCORD_WEBHOOK secret is missing")

    time_sgt = datetime.now(
        ZoneInfo("Asia/Singapore")
    ).strftime("%d %b %Y, %I:%M %p")

    messages = {
        "ONLINE": (
            "🟢 Escape from Tarkov — Online",
            "Tarkov services appear to be operational.",
            0x2ECC71
        ),
        "MAINTENANCE": (
            "🟠 Escape from Tarkov — Maintenance",
            "Battlestate Games status indicates maintenance.",
            0xF39C12
        ),
        "UNKNOWN": (
            "⚪ Escape from Tarkov — Unknown Status",
            "The monitor could not determine the current service status.",
            0x95A5A6
        )
    }

    title, description, color = messages[status]

    payload = {
        "username": "Tarkov PvE Monitor",
        "embeds": [{
            "title": title,
            "description": description,
            "color": color,
            "fields": [
                {
                    "name": "Target",
                    "value": "Escape from Tarkov / PvE",
                    "inline": True
                },
                {
                    "name": "Status",
                    "value": status,
                    "inline": True
                }
            ],
            "footer": {
                "text": f"Checked {time_sgt} SGT"
            }
        }]
    }

    response = requests.post(WEBHOOK, json=payload, timeout=20)
    response.raise_for_status()

    print("Discord notification sent.")


def main():
    previous = load_status()
    current = check_tarkov()

    print(f"Previous status: {previous['last_status']}")
    print(f"Current status: {current}")

    # Don't alert Discord just because the status website
    # temporarily failed.
    if current == "CHECK_FAILED":
        return

    if current != previous["last_status"]:
        send_discord(current)
        save_status(current)
    else:
        print("No status change. No Discord notification.")


if __name__ == "__main__":
    main()
