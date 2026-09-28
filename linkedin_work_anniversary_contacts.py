#!/usr/bin/env python3
"""
Save phone numbers of LinkedIn work-anniversary people to a local CSV file.

Steps:
  1. Open Google Chrome with the "Badarinath Devarasetty" profile
     (cam.badari@gmail.com) and open Gmail
  2. Open LinkedIn in a new tab
  3. Go to "My Network" > "Catch up" > "Work anniversaries"
  4. Open each person's profile in a new tab, open "Contact info", and if a
     phone number is listed save it to linkedin_work_anniversary_contacts_<date>.csv:
         Name, LinkedIn Profile, Phone Number

Everyone checked (with or without a phone) is remembered in
work_anniversary_contacts_checked.json, so later runs only open new profiles.
The files stay on this laptop only; nothing is uploaded anywhere.

Usage:
  python3 linkedin_work_anniversary_contacts.py              # check everyone new on the list
  python3 linkedin_work_anniversary_contacts.py --limit 20   # check at most 20 profiles

Needs the same one-time Chrome setting as linkedin_birthdays.py:
  View > Developer > Allow JavaScript from Apple Events
"""

import argparse
import csv
import datetime as dt
import json
import sys
import time
from pathlib import Path

from linkedin_birthday_contacts import HEADER, read_phone
from linkedin_birthdays import GMAIL_URL, JS_LOAD_MORE, LINKEDIN_URL, Chrome, human_pause, log
from linkedin_job_changes import open_category
from linkedin_work_anniversaries import WORK_ANNIVERSARIES

BASE_DIR = Path(__file__).resolve().parent
CONTACTS_CSV = BASE_DIR / f"linkedin_work_anniversary_contacts_{dt.date.today().isoformat()}.csv"
CHECKED_LOG = BASE_DIR / "work_anniversary_contacts_checked.json"

# People on the Work anniversaries page ("Completed N years at ...") with their profile links.
JS_PROFILES = r"""
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
    if (!/Completed .* at |anniversary/i.test(card.innerText || '')) continue;
    const name = [...card.querySelectorAll('a[href*="/in/"]')]
                   .map(x => (x.innerText || '').trim().split('\n')[0]).find(t => t) ||
                 (card.innerText || '').trim().split('\n')[0];
    seen.add(href);
    out.push({name, profile: href});
  }
  return JSON.stringify(out);
})()
"""


def load_checked():
    try:
        return json.loads(CHECKED_LOG.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def mark_checked(checked, profile, has_phone):
    checked[profile] = {"date": dt.date.today().isoformat(), "phone_found": has_phone}
    CHECKED_LOG.write_text(json.dumps(checked, indent=2))


def save_row(name, profile, phone):
    new_file = not CONTACTS_CSV.exists()
    with CONTACTS_CSV.open("a", newline="") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(HEADER)
        w.writerow([name, profile, phone])


def all_profiles(chrome, wanted):
    """Scroll the list until it stops growing (or has enough new people)."""
    people, last = [], -1
    for _ in range(20):
        people = json.loads(chrome.js(JS_PROFILES))
        if len(people) == last or len(people) >= wanted:
            break
        last = len(people)
        chrome.js(JS_LOAD_MORE)
        time.sleep(2)
    return people


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=None, help="max profiles to open this run")
    args = ap.parse_args()

    chrome = Chrome()
    log("Step 1: Opening Chrome (Badarinath Devarasetty profile) with Gmail...")
    chrome.open_profile_window(GMAIL_URL)

    log("Step 2: Opening LinkedIn in a new tab...")
    chrome.new_tab(LINKEDIN_URL)
    chrome.wait_loaded()
    if any(k in chrome.url() for k in ("login", "authwall", "signup")):
        sys.exit("LinkedIn isn't signed in on this Chrome profile. Sign in and run again.")
    if not chrome.js_allowed:
        sys.exit("Enable in Chrome: View > Developer > Allow JavaScript from Apple Events")

    open_category(chrome, WORK_ANNIVERSARIES)  # step 3

    checked = load_checked()
    wanted = len(checked) + (args.limit or 10_000)
    people = [p for p in all_profiles(chrome, wanted) if p["profile"] not in checked]
    if args.limit:
        people = people[:args.limit]
    log(f"Step 4: {len(people)} new people to check...")

    saved = 0
    for p in people:
        name, profile = p["name"], p["profile"]
        phone = read_phone(chrome, profile)
        mark_checked(checked, profile, bool(phone))
        if phone:
            save_row(name, profile, phone)
            saved += 1
            log(f" -> {name}: phone saved")
        else:
            log(f" -  {name}: no phone number")
        human_pause(2, 4)  # be gentle; avoid LinkedIn rate-limits

    if saved:
        log(f"Done. {saved} phone numbers saved to {CONTACTS_CSV}")
    else:
        log("Done. No new phone numbers found.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\nStopped.")
