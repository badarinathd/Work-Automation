#!/usr/bin/env python3
"""
Send WhatsApp messages listed in a Google Sheet, using the WhatsApp desktop app.

Steps:
  1. Open the Google Sheet (in Chrome, and read it as CSV)
  2. Go through the rows one by one. Column G's link opens a WhatsApp chat
     with "Hi <Name>!," + the Message; this script builds the same chat from
     the same row's Name (B), Number (D) and Message (F), so it isn't affected
     by G's formula pointing one row up (G2 uses B1/D1).
  3. Open the chat in the WhatsApp app with the message typed in, and press Enter

Rows without a proper phone number or without a message are skipped.
Every message sent is recorded in whatsapp_sent.json, so the same message is
never sent to the same number twice (safe to run again).

Usage:
  python3 whatsapp_from_sheet.py              # send
  python3 whatsapp_from_sheet.py --dry-run    # just list what would be sent

One-time setup:
  - WhatsApp desktop app installed and logged in
  - Let Terminal press keys: System Settings > Privacy & Security > Accessibility
    > turn on "Terminal" (macOS asks the first time)
  - Don't use the keyboard/mouse while it runs: it presses Enter in WhatsApp
"""

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from linkedin_birthdays import Chrome, human_pause, log, osascript

SHEET_ID = "1Egb7_iQ7xFGfpwTLReOcoEe306CZP3F08zcCO7Xpnoo"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit"
SHEET_CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"
COL_NAME, COL_NUMBER, COL_MESSAGE = 1, 3, 5   # B, D, F  (G = "Send Message" link built from D + F)
DEFAULT_COUNTRY_CODE = "91"                   # used when a number has no country code

SENT_LOG = Path(__file__).resolve().parent / "whatsapp_sent.json"

def read_sheet():
    with urllib.request.urlopen(SHEET_CSV_URL, timeout=30) as r:
        text = r.read().decode("utf-8")
    return list(csv.reader(io.StringIO(text)))


def clean_number(raw):
    """'+91 98xxx xxxxx' -> '9198xxxxxxxx'. Returns '' if it isn't a usable number."""
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 10:
        digits = DEFAULT_COUNTRY_CODE + digits
    return digits if 11 <= len(digits) <= 15 else ""


def load_sent():
    try:
        return json.loads(SENT_LOG.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def sent_key(number, message):
    return f"{number}:{hashlib.sha1(message.encode()).hexdigest()[:12]}"


def rows_to_send(rows):
    out = []
    for i, r in enumerate(rows[1:], start=2):        # row 2 = G2
        r = r + [""] * (COL_MESSAGE + 1 - len(r))
        number, message = clean_number(r[COL_NUMBER]), r[COL_MESSAGE].strip()
        name = r[COL_NAME].strip()
        if number and message:
            # Same text the column G link builds: "Hi <Name>!," + newline + Message
            text = f"Hi {name}!,\n{message}" if name else message
            out.append({"row": i, "name": name or number, "number": number, "message": text})
    return out


def frontmost_app():
    return osascript('tell application "System Events" to return name of first process whose frontmost is true')


def send_one(p):
    """Open the chat in the WhatsApp app with the text filled in, then press Enter."""
    url = "whatsapp://send?" + urllib.parse.urlencode({"phone": p["number"], "text": p["message"]},
                                                     quote_via=urllib.parse.quote)
    subprocess.run(["open", url], check=True)
    time.sleep(5)                                   # let the chat open and the text appear
    osascript('tell application "WhatsApp" to activate')
    time.sleep(1)
    # Only press Enter if WhatsApp is really the app in front (never type into another app)
    if frontmost_app() != "WhatsApp":
        return "WhatsApp wasn't in front; didn't press Enter"
    osascript('tell application "System Events" to key code 36')    # Enter = Send
    time.sleep(2)
    return "sent"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="only list what would be sent")
    args = ap.parse_args()

    log("Step 1: Reading the Google Sheet...")
    people = rows_to_send(read_sheet())
    sent_log = load_sent()
    todo = [p for p in people if sent_key(p["number"], p["message"]) not in sent_log]
    log(f"{len(people)} rows have a number and a message; {len(people) - len(todo)} already sent; "
        f"{len(todo)} to send.")

    if args.dry_run:
        for p in todo:
            first = p["message"].replace("\n", " ")[:70]
            log(f" -> G{p['row']}: {p['name']} (..{p['number'][-4:]}): \"{first}...\"")
        return
    if not todo:
        return

    chrome = Chrome()
    chrome.open_profile_window(SHEET_URL)            # step 1: show the sheet
    log("Step 2: Sending with the WhatsApp app, row by row...")

    sent = 0
    for p in todo:
        log(f" -> G{p['row']}: {p['name']} (..{p['number'][-4:]})")
        try:
            result = send_one(p)
        except RuntimeError as e:
            if any(k in str(e) for k in ("not allowed", "assistive", "1002", "25211")):
                sys.exit("\nNOT SENT: macOS blocked the Enter key press.\n"
                         "Fix: System Settings > Privacy & Security > Accessibility > turn on Terminal,\n"
                         "then quit Terminal (Cmd+Q), reopen it, and run this script again.")
            raise
        if result == "sent":
            sent += 1
            sent_log[sent_key(p["number"], p["message"])] = {
                "name": p["name"], "row": p["row"], "date": dt.datetime.now().isoformat(timespec="seconds")}
            SENT_LOG.write_text(json.dumps(sent_log, indent=2))
            log("    Sent (Enter pressed)")
        else:
            log(f"    Skipped: {result}")
        human_pause(5, 10)  # be gentle; WhatsApp bans accounts that blast messages

    log(f"Done. WhatsApp messages sent: {sent}.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\nStopped.")
