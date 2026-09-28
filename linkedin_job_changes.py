#!/usr/bin/env python3
"""
Send LinkedIn "new job" congratulations using your normal Chrome (already signed in).

Steps:
  1. Open Google Chrome with the "Badarinath Devarasetty" profile and open Gmail
  2. Open LinkedIn in a new tab
  3. Go to "My Network" > "Catch up" > "Job changes"
  4. Send congratulations one by one (people already messaged are skipped)

Usage:
  python3 linkedin_job_changes.py              # send congratulations
  python3 linkedin_job_changes.py --dry-run    # just list who would be messaged (sends nothing)
  python3 linkedin_job_changes.py --limit 20   # send at most 20 messages

Needs the same one-time Chrome setting as linkedin_birthdays.py:
  View > Developer > Allow JavaScript from Apple Events
"""

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

from linkedin_birthdays import (CATCH_UP_URL, GMAIL_URL, JS_HELPERS, JS_LOAD_MORE, JS_MODAL_OPEN,
                                JS_SEND, LINKEDIN_URL, MY_NETWORK_URL, Chrome, human_pause, log)

BASE_DIR = Path(__file__).resolve().parent


class Category:
    """A LinkedIn "Catch up" section whose cards have a "Message <Name>: <suggestion>" button."""

    def __init__(self, tab, url, sent_log, suggestion_regex, template):
        self.tab = tab                          # tab text on the Catch up page
        self.url = url
        self.sent_log = BASE_DIR / sent_log
        self.suggestion_regex = suggestion_regex  # JS regex source the suggestion must match
        self.template = template                # {name}, {suggestion}, {suggestion_lc}


JOB_CHANGES = Category(
    tab="Job changes",
    url="https://www.linkedin.com/mynetwork/catch-up/job_changes/",
    sent_log="job_change_wishes_sent.json",
    suggestion_regex=r"Congrat.*",
    # e.g. "Hi Nishaanth S, congrats on starting your new role at Google!"
    template="Hi {name}, {suggestion_lc}",
)

# Cards have a button labelled "Message <Name>: <LinkedIn's suggested text>".
# Returns the next person not in `skip`; clicks their button unless dryRun.
JS_NEXT = JS_HELPERS + r"""
(function(skip, dryRun, suggestion){
  const re = new RegExp('^Message (.+?):\\s*(' + suggestion + ')$', 'i');
  for (const b of [...document.querySelectorAll('button, a')].filter(visible)) {
    const m = (b.getAttribute('aria-label') || '').match(re);
    if (!m || skip.includes(m[1].trim())) continue;
    if (!dryRun) { b.scrollIntoView({block: 'center'}); b.click(); }
    return JSON.stringify({found: true, name: m[1].trim(), suggestion: m[2].trim()});
  }
  return JSON.stringify({found: false});
})(SKIP, DRY_RUN, SUGGESTION)
"""


def load_sent(cat):
    try:
        return json.loads(cat.sent_log.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def record_sent(cat, sent, name, text):
    sent[name] = {"date": dt.date.today().isoformat(), "message": text}
    cat.sent_log.write_text(json.dumps(sent, indent=2))


def open_category(chrome, cat):
    log(f"Step 3: My Network > Catch up > {cat.tab}...")
    if not chrome.click_text(["My Network"]):
        chrome.goto(MY_NETWORK_URL)
    chrome.wait_loaded()
    if not chrome.click_text(["Catch up"]):
        chrome.goto(CATCH_UP_URL)
    chrome.wait_loaded()
    if not chrome.click_text([cat.tab]):
        chrome.goto(cat.url)
    chrome.wait_loaded()


def next_person(chrome, cat, skip, dry_run):
    code = (JS_NEXT.replace("SKIP", json.dumps(sorted(skip))).replace("DRY_RUN", json.dumps(dry_run))
            .replace("SUGGESTION", json.dumps(cat.suggestion_regex)))
    for _ in range(15):  # the list loads as you scroll
        result = json.loads(chrome.js(code))
        if result["found"]:
            return result
        chrome.js(JS_LOAD_MORE)
        time.sleep(2)
    return None


def send_congrats(chrome, cat, dry_run, limit):
    sent_log = load_sent(cat)
    skip = set(sent_log)
    sent = 0
    count = 0

    while limit is None or (sent if not dry_run else count) < limit:
        if not dry_run and cat.url.rstrip("/").split("/")[-1] not in chrome.url():
            chrome.goto(cat.url)
            chrome.wait_loaded()

        person = next_person(chrome, cat, skip, dry_run)
        if not person:
            break
        name = person["name"]
        skip.add(name)
        s = person["suggestion"]
        text = cat.template.format(name=name.split(",")[0].strip(), suggestion=s, suggestion_lc=s[0].lower() + s[1:])
        count += 1

        if dry_run:
            log(f" -> Would message {name}: \"{text}\"")
            continue

        log(f" -> Messaging {name}: \"{text}\"")
        send_js = JS_SEND.replace("NAME", json.dumps(name)).replace("TEXT", json.dumps(text))
        status = "waiting"
        for _ in range(25):
            time.sleep(1)
            status = chrome.js(send_js)
            if status == "sent":
                break
        if status == "sent":
            # The pop-up closes after a successful send
            for _ in range(10):
                time.sleep(1)
                if chrome.js(JS_MODAL_OPEN.replace("NAME", json.dumps(name))) == "false":
                    break
            else:
                status = "stuck"
        if status == "sent":
            sent += 1
            record_sent(cat, sent_log, name, text)
            log(f"    Sent ({sent})")
        else:
            log(f"    Could not send to {name}")

        human_pause(4, 8)  # be gentle; avoid LinkedIn rate-limits
        chrome.goto(cat.url)
        chrome.wait_loaded()

    if dry_run:
        log(f"Done. {count} people would be messaged.")
    else:
        log(f"Done. Congratulations sent this run: {sent}.")


def main(cat=JOB_CHANGES, doc=__doc__):
    ap = argparse.ArgumentParser(description=doc, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="only list who would be messaged")
    ap.add_argument("--limit", type=int, default=None, help="max messages to send")
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

    open_category(chrome, cat)
    send_congrats(chrome, cat, args.dry_run, args.limit)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\nStopped.")
