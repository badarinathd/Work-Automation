# Work-Automation

Scripts that send greetings on LinkedIn, Facebook and WhatsApp, and save
contact numbers, using your **normal Chrome** ("Badarinath Devarasetty" profile,
cam.badari@gmail.com) and the **WhatsApp desktop app**. No extensions, no extra
Python packages. Only macOS's built-in `python3` and AppleScript are needed.

## One-time setup

| What | Where |
|---|---|
| Let scripts click in Chrome | Chrome menu bar: **View → Developer → Allow JavaScript from Apple Events** |
| Let Terminal control Chrome | Click **OK** when macOS asks the first time |
| Let Terminal press Enter in WhatsApp (WhatsApp script only) | **System Settings → Privacy & Security → Accessibility → Terminal: on**, then restart Terminal |
| Stay signed in | LinkedIn and Facebook in the Chrome profile; WhatsApp desktop app logged in |

While a script runs, **don't use Chrome or the keyboard** until Terminal says `Done`.
Press **Ctrl + C** to stop any script.

## Scripts

### Greetings

| Script | What it does | Run |
|---|---|---|
| `linkedin_birthdays.py` | LinkedIn → My Network → Catch up → **Birthdays**. Messages everyone with a birthday **today**: *"Hi <Name>, wishing you a very happy birthday!"* | `python3 linkedin_birthdays.py` |
| `linkedin_job_changes.py` | Catch up → **Job changes**. *"Hi <Name>, congrats on starting your new role at <Company>!"* | `python3 linkedin_job_changes.py` |
| `linkedin_work_anniversaries.py` | Catch up → **Work anniversaries**. *"Hi <Name>, congrats on your N year anniversary at <Company>!"* | `python3 linkedin_work_anniversaries.py` |
| `linkedin_education.py` | Catch up → **Education**. *"Hi <Name>, congrats on finishing up at <School>!"* | `python3 linkedin_education.py` |
| `facebook_birthdays.py` | facebook.com/events/birthdays. For **today's** birthdays, posts Facebook's suggested wish on their timeline, or sends a Messenger message if only "Message" is offered | `python3 facebook_birthdays.py` |
| `whatsapp_from_sheet.py` | Reads the **"Send-Whatsapp-Birthday"** Google Sheet (tab "Mass message"). For each row with a Number (D) and Message (F), opens the chat in the **WhatsApp app** with *"Hi <Name>!,"* + message and presses Enter | `python3 whatsapp_from_sheet.py` |

### Contact numbers (saved on this laptop only)

| Script | What it does | Run |
|---|---|---|
| `linkedin_birthday_contacts.py` | For **today's** LinkedIn birthdays: opens each profile in a new tab → **Contact info** → saves the phone number, if there is one, to `linkedin_birthday_contacts_<date>.csv` | `python3 linkedin_birthday_contacts.py` |
| `linkedin_work_anniversary_contacts.py` | Same for the **Work anniversaries** list, saving to `linkedin_work_anniversary_contacts_<date>.csv`. Remembers who was already checked | `python3 linkedin_work_anniversary_contacts.py` |

CSV format: `Name, LinkedIn Profile, Phone Number` (labels like "(Mobile)" removed).

### Helper

| Script | What it does |
|---|---|
| `open_chrome_profile.py` | Opens Chrome with the cam.badari@gmail.com profile, plus Gmail and LinkedIn tabs |

## Common options

| Option | Meaning | Works with |
|---|---|---|
| `--dry-run` | Only show who would be messaged; send nothing | all greeting scripts |
| `--limit N` | Send to / check at most N people. **Default is 10 per run** for every `linkedin_*` script; `--limit 0` = no limit | all `linkedin_*` scripts |
| `--include-recent` | Also wish belated (recent) birthdays, not just today's | `linkedin_birthdays.py` |

Tip: always try `--dry-run` first. LinkedIn scripts handle **10 people per run** by
default (change `DEFAULT_LIMIT` in `linkedin_birthdays.py`); run again for the next 10.

## Record files (created by the scripts)

These stop anyone from being messaged twice. Deleting one lets a script message those people again.

| File | Used by |
|---|---|
| `birthday_wishes_sent.json` | LinkedIn and Facebook birthdays (per day) |
| `job_change_wishes_sent.json` | Job changes |
| `work_anniversary_wishes_sent.json` | Work anniversaries |
| `education_wishes_sent.json` | Education |
| `whatsapp_sent.json` | WhatsApp (same message never sent to the same number twice) |
| `work_anniversary_contacts_checked.json` | Work-anniversary contacts (profiles already opened) |
| `birthday_contacts_checked.json` | Birthday contacts (profiles already opened today) |
| `linkedin_*_contacts_<date>.csv` | Saved phone numbers |

## Other files

| File | Note |
|---|---|
| `linkedin_birthday.csv` | A contacts CSV (Name, LinkedIn Profile, Phone Number) that isn't created by these scripts; probably an upload/copy for the Google Sheet |
| `google_sheet_apps_script.js` | **Not used.** Leftover from a Google Sheets upload idea that was not built; safe to delete |

## How it works (for changes)

- `linkedin_birthdays.py` holds the shared Chrome-control code (`Chrome` class,
  AppleScript + JavaScript helpers). The other scripts import from it.
- `linkedin_job_changes.py` holds the shared "Catch up" logic (`Category`).
  `linkedin_work_anniversaries.py` and `linkedin_education.py` only define their section.
- Message wording: `WISH_TEMPLATE` in `linkedin_birthdays.py`, `template=` in each
  Category, `MESSENGER_TEMPLATE` in `facebook_birthdays.py`.

## Known issue in the Google Sheet

Column G's formula in the "Mass message" tab points one row up (G2 uses B1/D1).
`whatsapp_from_sheet.py` doesn't use column G, so it isn't affected, but clicking
the links by hand opens the wrong person. Fix G2 to
`=HYPERLINK("https://wa.me/"&D2&"?text=Hi "&B2&"!,%0A"&ENCODEURL(F2),"Send Message")`
and copy it down.
