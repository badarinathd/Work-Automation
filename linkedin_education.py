#!/usr/bin/env python3
"""
Send LinkedIn education congratulations (finished / started a school) using your
normal Chrome (already signed in).

Steps:
  1. Open Google Chrome with the "Badarinath Devarasetty" profile and open Gmail
  2. Open LinkedIn in a new tab
  3. Go to "My Network" > "Catch up" > "Education"
  4. Send congratulations one by one (people already messaged are skipped)

Usage:
  python3 linkedin_education.py              # send congratulations
  python3 linkedin_education.py --dry-run    # just list who would be messaged (sends nothing)
  python3 linkedin_education.py --limit 20   # send at most 20 messages

Needs the same one-time Chrome setting as linkedin_birthdays.py:
  View > Developer > Allow JavaScript from Apple Events
"""

import sys

from linkedin_job_changes import Category, main

EDUCATION = Category(
    tab="Education",
    url="https://www.linkedin.com/mynetwork/catch-up/education/",
    sent_log="education_wishes_sent.json",
    suggestion_regex=r"Congrat.*",
    # e.g. "Hi Sanjib Sapui, congrats on finishing up at Indian Institute of Technology, Madras!"
    template="Hi {name}, {suggestion_lc}",
)

if __name__ == "__main__":
    try:
        main(EDUCATION, __doc__)
    except KeyboardInterrupt:
        sys.exit("\nStopped.")
