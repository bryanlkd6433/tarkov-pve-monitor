import os
import json
import hashlib
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo


# ============================================================
# CONFIGURATION
# ============================================================

WEBHOOK = os.environ.get("DISCORD_WEBHOOK")

TELEGRAM_URL = "https://t.me/s/escapefromtarkovEN"

STATE_FILE = "status.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/140 Safari/537.36"
    )
}


# ============================================================
# LOAD / SAVE MONITOR STATE
# ============================================================

def load_state():

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    except (FileNotFoundError, json.JSONDecodeError):

        return {
            "last_message_hash": "",
            "initialized": False
        }


def save_state(state):

    with open(STATE_FILE, "w", encoding="utf-8") as f:

        json.dump(
            state,
            f,
            indent=2
        )


# ============================================================
# READ OFFICIAL TARKOV TELEGRAM
# ============================================================

def get_official_posts():

    response = requests.get(
        TELEGRAM_URL,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    posts = []

    for message in soup.select(
        ".tgme_widget_message_wrap"
    ):

        text_element = message.select_one(
            ".tgme_widget_message_text"
        )

        if not text_element:
            continue

        text = text_element.get_text(
            " ",
            strip=True
        )

        link_element = message.select_one(
            ".tgme_widget_message_date"
        )

        link = ""

        if link_element:

            link = link_element.get(
                "href",
                ""
            )

        posts.append({
            "text": text,
            "link": link
        })

    return posts


# ============================================================
# CLASSIFY TARKOV ANNOUNCEMENTS
# ============================================================

def classify_post(text):

    lower = text.lower()

    # Only Escape from Tarkov.
    # Ignore Arena-only announcements.

    if "#escapefromtarkov" not in lower:
        return None

    # Ignore website / account-center maintenance.

    if (
        "website" in lower
        or "account center" in lower
    ):
        return None

    maintenance_words = [
        "maintenance",
        "technical update",
        "update installation",
        "installation"
    ]

    if not any(
        word in lower
        for word in maintenance_words
    ):
        return None

    # --------------------------------------------------------
    # COMPLETE
    # --------------------------------------------------------

    if any(
        word in lower
        for word in [
            "is complete",
            "has been completed",
            "installation is complete",
            "installation in #escapefromtarkov is complete"
        ]
    ):
        return "COMPLETE"

    # --------------------------------------------------------
    # EXTENDED
    # --------------------------------------------------------

    if any(
        word in lower
        for word in [
            "has been extended",
            "maintenance extended",
            "installation has been extended"
        ]
    ):
        return "EXTENDED"

    # --------------------------------------------------------
    # STARTED
    # --------------------------------------------------------

    if any(
        word in lower
        for word in [
            "has begun",
            "have started",
            "we have started",
            "installation has begun"
        ]
    ):
        return "STARTED"

    # --------------------------------------------------------
    # PLANNED
    # --------------------------------------------------------

    if any(
        word in lower
        for word in [
            "we are planning",
            "we plan to",
            "tomorrow",
            "will take"
        ]
    ):
        return "PLANNED"

    return None


# ============================================================
# SEND REAL TARKOV ALERT TO DISCORD
# ============================================================

def discord_message(event, text, link):

    now = datetime.now(
        ZoneInfo("Asia/Singapore")
    ).strftime(
        "%d %b %Y, %I:%M %p"
    )

    configs = {

        "PLANNED": {
            "title":
                "🔵 Tarkov Maintenance Scheduled",

            "color":
                0x3498DB
        },

        "STARTED": {
            "title":
                "🟠 Tarkov Maintenance Started",

            "color":
                0xF39C12
        },

        "EXTENDED": {
            "title":
                "🔴 Tarkov Maintenance Extended",

            "color":
                0xE74C3C
        },

        "COMPLETE": {
            "title":
                "🟢 Tarkov Maintenance Complete",

            "color":
                0x2ECC71
        }
    }

    config = configs[event]

    # Prevent Discord message being too large.

    if len(text) > 1500:

        text = (
            text[:1500]
            + "..."
        )

    payload = {

        "username":
            "Tarkov PvE Monitor",

        "embeds": [{

            "title":
                config["title"],

            "description":
                text,

            "color":
                config["color"],

            "fields": [

                {
                    "name":
                        "Game",

                    "value":
                        "Escape from Tarkov",

                    "inline":
                        True
                },

                {
                    "name":
                        "Mode",

                    "value":
                        "PvE / EFT Services",

                    "inline":
                        True
                }

            ],

            "footer": {

                "text":
                    f"Checked {now} SGT • Official BSG announcement"

            }

        }]

    }

    if link:

        payload["embeds"][0]["url"] = link

    response = requests.post(
        WEBHOOK,
        json=payload,
        timeout=30
    )

    response.raise_for_status()


# ============================================================
# NORMAL MONITOR
# ============================================================

def main():

    if not WEBHOOK:

        raise RuntimeError(
            "DISCORD_WEBHOOK secret is missing"
        )

    state = load_state()

    try:

        posts = get_official_posts()

    except requests.RequestException as error:

        print(
            "Unable to read official "
            f"Telegram feed: {error}"
        )

        return

    relevant = []

    for post in posts:

        event = classify_post(
            post["text"]
        )

        if event:

            message_hash = hashlib.sha256(
                post["text"].encode(
                    "utf-8"
                )
            ).hexdigest()

            relevant.append({

                "event":
                    event,

                "text":
                    post["text"],

                "link":
                    post["link"],

                "hash":
                    message_hash

            })

    if not relevant:

        print(
            "No relevant EFT maintenance "
            "announcements found."
        )

        return

    latest = relevant[-1]

    print(
        "Latest maintenance event: "
        f"{latest['event']}"
    )

    print(
        "Announcement: "
        f"{latest['text'][:300]}"
    )

    # --------------------------------------------------------
    # FIRST RUN
    # --------------------------------------------------------

    if not state.get(
        "initialized"
    ):

        print(
            "First run. "
            "Establishing baseline."
        )

        state[
            "last_message_hash"
        ] = latest["hash"]

        state[
            "initialized"
        ] = True

        save_state(
            state
        )

        return

    # --------------------------------------------------------
    # NO CHANGE
    # --------------------------------------------------------

    if (
        latest["hash"]
        == state.get(
            "last_message_hash"
        )
    ):

        print(
            "No new maintenance "
            "announcement."
        )

        return

    # --------------------------------------------------------
    # NEW ANNOUNCEMENT
    # --------------------------------------------------------

    print(
        "New maintenance "
        "announcement detected!"
    )

    discord_message(
        latest["event"],
        latest["text"],
        latest["link"]
    )

    state[
        "last_message_hash"
    ] = latest["hash"]

    save_state(
        state
    )

    print(
        "Discord notification sent."
    )


# ============================================================
# DISCORD TEST
# ============================================================

def send_test():

    if not WEBHOOK:
        raise RuntimeError(
            "DISCORD_WEBHOOK secret is missing"
        )

    now = datetime.now(
        ZoneInfo("Asia/Singapore")
    ).strftime("%d %b %Y, %I:%M %p")

    payload = {
        "content": (
            "🧪 **Tarkov PvE Monitor — Test Successful**\n\n"
            "🟢 GitHub Actions: Online\n"
            "🟢 Discord Webhook: Connected\n"
            "🟢 Tarkov Announcement Monitor: Active\n"
            "⏱️ Check interval: ~5 minutes\n\n"
            f"Test time: {now} SGT"
        )
    }

    response = requests.post(
        WEBHOOK,
        json=payload,
        timeout=30
    )

    # Show Discord's response if it rejects the message.
    print(f"Discord HTTP status: {response.status_code}")

    if response.status_code >= 400:
        print(f"Discord response: {response.text}")

    response.raise_for_status()

    print("TEST DISCORD NOTIFICATION SENT")


# ============================================================
# CURRENT MODE: TEST
# ============================================================

if __name__ == "__main__":

    send_test()
