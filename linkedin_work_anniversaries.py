#!/usr/bin/env python3
"""
Send LinkedIn work-anniversary congratulations using your normal Chrome (already signed in).

Steps:
  1. Open Google Chrome with the "Badarinath Devarasetty" profile and open Gmail
  2. Open LinkedIn in a new tab
  3. Go to "My Network" > "Catch up" > "Work anniversaries"
  4. Send congratulations one by one (people already messaged are skipped)

Usage:
  python3 linkedin_work_anniversaries.py              # send congratulations
  python3 linkedin_work_anniversaries.py --dry-run    # just list who would be messaged (sends nothing)
  python3 linkedin_work_anniversaries.py --limit 20   # send at most 20 messages

Needs the same one-time Chrome setting as linkedin_birthdays.py:
  View > Developer > Allow JavaScript from Apple Events
"""

import sys

from linkedin_job_changes import Category, main

WORK_ANNIVERSARIES = Category(
    tab="Work anniversaries",
    url="https://www.linkedin.com/mynetwork/catch-up/work_anniversaries/",
    sent_log="work_anniversary_wishes_sent.json",
    suggestion_regex=r"Congrat.*anniversary.*",
    # e.g. "Hi Dipsha Ghatak, congrats on your 7 year anniversary at Amazon!"
    template="Hi {name}, {suggestion_lc}",
)

if __name__ == "__main__":
    try:
        main(WORK_ANNIVERSARIES, __doc__)
    except KeyboardInterrupt:
        sys.exit("\nStopped.")
