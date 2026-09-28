#!/usr/bin/env python3
"""
Save phone numbers of today's LinkedIn birthday people to a local CSV file.

Steps:
  1. Open Google Chrome with the "Badarinath Devarasetty" profile
     (cam.badari@gmail.com) and open Gmail
  2. Open LinkedIn in a new tab
  3. Go to "My Network" and wait for it to load
  4. Switch to the "Catch up" tab and wait for it to load
  5. Open "Birthdays"
  6. Open each of today's birthday profiles in a new tab, open "Contact info",
     and if a phone number is listed save it to linkedin_birthday_contacts_<date>.csv
     (e.g. linkedin_birthday_contacts_2026-09-27.csv):
         Name, LinkedIn Profile, Phone Number

The file stays on this laptop only; nothing is uploaded anywhere.

Usage:
  python3 linkedin_birthday_contacts.py

Needs the same one-time Chrome setting as linkedin_birthdays.py:
  View > Developer > Allow JavaScript from Apple Events
"""

import csv
import datetime as dt
import json
import re
import sys
import time
from pathlib import Path

from linkedin_birthdays import (BIRTHDAYS_URL, GMAIL_URL, JS_LOAD_MORE, LINKEDIN_URL, Chrome,
                                human_pause, log, open_birthdays)

CONTACTS_CSV = Path(__file__).resolve().parent / f"linkedin_birthday_contacts_{dt.date.today().isoformat()}.csv"
HEADER = ["Name", "LinkedIn Profile", "Phone Number"]

# Today's birthday people with their profile links. A card is the largest block
# around a profile link that still contains only that one person's /in/ link.
JS_TODAY_PROFILES = r"""
(function(){
  const out = [], seen = new Set();
  const key = a => a.href.split('?')[0];
  for (const a of document.querySelectorAll('main a[href*="/in/"]')) {
    const href = key(a);
    if (seen.has(href)) continue;
    let card = a;
    while (card.parentElement &&
           new Set([...card.parentElement.querySelectorAll('a[href*="/in/"]')].map(key)).size === 1) {
      card = card.parentElement;
    }
    if (!/birthday today/i.test(card.innerText || '')) continue;
    const name = [...card.querySelectorAll('a[href*="/in/"]')]
                   .map(x => (x.innerText || '').trim().split('\n')[0]).find(t => t) ||
                 (card.innerText || '').trim().split('\n')[0];
    seen.add(href);
    out.push({name, profile: href});
  }
  return JSON.stringify(out);
})()
"""

# Reads phone number(s) from the "Contact info" panel: the lines after "Phone".
# The panel opens empty and fills in a moment later; "Connected since" is always
# its last section, so it only counts as loaded once that is there.
JS_READ_PHONE = r"""
(function(){
  for (const box of document.querySelectorAll('dialog, [role=dialog]')) {
    if (!/Contact info/.test(box.innerText || '')) continue;
    const lines = box.innerText.split('\n').map(l => l.trim()).filter(Boolean);
    if (!lines.includes('Connected since')) return JSON.stringify({open: false, phones: []});
    const phones = [];
    const i = lines.indexOf('Phone');
    if (i >= 0) {
      for (const l of lines.slice(i + 1)) {
        if (!/\d[\d\s()+-]{6,}/.test(l)) break;       // next section (Address, Email, ...)
        phones.push(l);
      }
    }
    return JSON.stringify({open: true, phones});
  }
  return JSON.stringify({open: false, phones: []});
})()
"""


def clean_phone(phone):
    """Drop LinkedIn's type label, e.g. "98xxxxxxxx (Mobile)" -> "98xxxxxxxx"."""
    return re.sub(r"\s*\([A-Za-z ]+\)", "", phone).strip()


def saved_profiles():
    try:
        with CONTACTS_CSV.open() as f:
            return {row["LinkedIn Profile"] for row in csv.DictReader(f)}
    except FileNotFoundError:
        return set()


def save_row(name, profile, phone):
    new_file = not CONTACTS_CSV.exists()
    with CONTACTS_CSV.open("a", newline="") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(HEADER)
        w.writerow([name, profile, phone])


def read_phone(chrome, profile):
    """Open the profile in a new tab, open Contact info, return phone(s) or ''."""
    chrome.new_tab(profile)
    chrome.wait_loaded()
    try:
        if not chrome.click_text(["Contact info"], timeout=10):
            chrome.goto(profile.rstrip("/") + "/overlay/contact-info/")
            chrome.wait_loaded()
        for _ in range(15):
            time.sleep(1)
            info = json.loads(chrome.js(JS_READ_PHONE))
            if info["open"]:
                return ", ".join(clean_phone(ph) for ph in info["phones"])
            time.sleep(1)
        return ""
    finally:
        human_pause(1, 2)
        chrome.close_tab()


def today_profiles(chrome):
    """Scroll the Birthdays list until the "today" section has fully loaded."""
    people, last = [], -1
    for _ in range(10):
        people = json.loads(chrome.js(JS_TODAY_PROFILES))
        if len(people) == last and "recent birthday" in chrome.js("document.body.innerText").lower():
            break
        last = len(people)
        chrome.js(JS_LOAD_MORE)
        time.sleep(2)
    return people


def main():
    chrome = Chrome()
    log("Step 1: Opening Chrome (Badarinath Devarasetty profile) with Gmail...")
    chrome.open_profile_window(GMAIL_URL)

    log("Step 2: Opening LinkedIn in a new tab...")
    chrome.new_tab(LINKEDIN_URL)
    chrome.wait_loaded()
    if any(k in chrome.url() for k in ("login", "authwall", "signup")):
        sys.exit("LinkedIn isn't signed in on this Chrome profile. Sign in and run again.")

    open_birthdays(chrome)  # steps 3-5
    if not chrome.js_allowed:
        sys.exit("Enable in Chrome: View > Developer > Allow JavaScript from Apple Events")
    if "/catch-up/birthday" not in chrome.url():
        chrome.goto(BIRTHDAYS_URL)
        chrome.wait_loaded()

    people = today_profiles(chrome)
    log(f"Step 6: {len(people)} birthdays today. Checking Contact info for each...")
    done = saved_profiles()
    saved = 0
    for p in people:
        name, profile = p["name"], p["profile"]
        if profile in done:
            log(f" -  {name}: already in the file")
            continue
        phone = read_phone(chrome, profile)
        if not phone:
            log(f" -  {name}: no phone number")
            continue
        save_row(name, profile, phone)
        saved += 1
        log(f" -> {name}: phone saved")
        human_pause(2, 4)  # be gentle; avoid LinkedIn rate-limits

    log(f"Done. {saved} new phone numbers saved to {CONTACTS_CSV}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\nStopped.")
