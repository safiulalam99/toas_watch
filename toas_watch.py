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
    """Returns a dict of {row_key: {section, location, type, size, rent}}"""
    html = requests.get(URL, timeout=30, headers={"User-Agent": "toas-watch/1.0"}).text
    soup = BeautifulSoup(html, "html.parser")
    listings = {}
    for table in soup.find_all("table"):
        h = table.find_previous(["h2", "h3"])
        section = h.get_text(" ", strip=True) if h else "?"
        for tr in table.find_all("tr")[1:]:  # skip header row
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) >= 5:
                location, apt_type, size, floor, rent = cells[0], cells[1], cells[2], cells[3], cells[4]
                key = f"{section} | {location} | {apt_type} | {size} | {floor} | {rent}"
                listings[key] = {
                    "section": section, "location": location, "type": apt_type,
                    "size": size, "floor": floor, "rent": rent,
                }
    return listings


def format_apartment(info, emoji):
    return (
        f"{emoji} {info['location']} \u2014 {info['size']} m\u00b2\n"
        f"   {info['type']}\n"
        f"   Rent: {info['rent']} \u20ac \u00b7 Floor {info['floor']}\n"
        f"   {info['section']}"
    )


def notify(added_infos, removed_infos):
    blocks = [format_apartment(i, "\U0001F7E2 NEW") for i in added_infos]
    blocks += [format_apartment(i, "\U0001F534 GONE") for i in removed_infos]
    msg = "\n\n".join(blocks)
    print(msg)

    topic = os.getenv("NTFY_TOPIC")
    if not topic:
        return
    title = f"TOAS: {len(added_infos)} new, {len(removed_infos)} gone"
    requests.post(
        f"https://ntfy.sh/{topic}",
        data=msg.encode("utf-8"),
        headers={
            "Title": title.encode("utf-8"),
            "Priority": "high" if added_infos else "default",
            "Tags": "house,bell" if added_infos else "wave",
        },
        timeout=15,
    )


def main():
    current = fetch_listings()
    if not current:
        sys.exit("No listings parsed (page empty or layout changed) - state not updated.")

    old = json.loads(STATE.read_text()) if STATE.exists() else None
    STATE.write_text(json.dumps(current))

    if old is None:
        print(f"First run: saved {len(current)} listings.")
        return

    added_keys = set(current) - set(old)
    removed_keys = set(old) - set(current)
    if not added_keys and not removed_keys:
        return

    added_infos = [current[k] for k in added_keys]
    removed_infos = [old[k] for k in removed_keys]

    log_lines = [f"NEW: {k}" for k in added_keys] + [f"GONE: {k}" for k in removed_keys]
    with LOG.open("a") as f:
        f.write(f"\n[{datetime.now():%Y-%m-%d %H:%M}]\n" + "\n".join(log_lines) + "\n")

    notify(added_infos, removed_infos)


if __name__ == "__main__":
    main()