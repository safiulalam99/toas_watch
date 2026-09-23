#!/usr/bin/env python3
"""Watch TOAS 'Quickly Available' page and report added/removed apartments.

Setup:  pip install requests beautifulsoup4
Run:    python3 toas_watch.py
Optional phone push: set env NTFY_TOPIC to a private topic name and
install the free ntfy app, subscribing to that topic.
"""
import json, os, sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

URL = "https://toas.fi/en/quickly-available/"
DIR = Path(__file__).parent
STATE = DIR / "toas_state.json"
LOG = DIR / "toas_changes.log"


def fetch_listings():
    html = requests.get(URL, timeout=30, headers={"User-Agent": "toas-watch/1.0"}).text
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for table in soup.find_all("table"):
        h = table.find_previous(["h2", "h3"])
        section = h.get_text(" ", strip=True) if h else "?"
        for tr in table.find_all("tr")[1:]:  # skip header row
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) >= 5:
                items.append(f"{section} | " + " | ".join(cells))
    return items


def notify(msg):
    print(msg)
    topic = os.getenv("NTFY_TOPIC")
    if topic:
        requests.post(f"https://ntfy.sh/{topic}", data=msg.encode("utf-8"),
                      headers={"Title": "TOAS apartments changed"}, timeout=15)


def main():
    current = Counter(fetch_listings())
    if not current:
        sys.exit("No listings parsed (page empty or layout changed) - state not updated.")
    old = Counter(json.loads(STATE.read_text())) if STATE.exists() else None
    STATE.write_text(json.dumps(current))
    if old is None:
        print(f"First run: saved {sum(current.values())} listings.")
        return
    added, removed = current - old, old - current
    if not added and not removed:
        return
    lines = [f"NEW: {k}" for k in added] + [f"GONE: {k}" for k in removed]
    msg = "\n".join(lines)
    with LOG.open("a") as f:
        f.write(f"\n[{datetime.now():%Y-%m-%d %H:%M}]\n{msg}\n")
    notify(msg)


if __name__ == "__main__":
    main()