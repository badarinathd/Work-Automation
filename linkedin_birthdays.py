#!/usr/bin/env python3
"""
Send LinkedIn birthday wishes using your normal Chrome (already signed in).

Steps:
  1. Open Google Chrome with the "Badarinath Devarasetty" profile
     (cam.badari@gmail.com) and open Gmail
  2. Open LinkedIn in a new tab
  3. Go to "My Network" and wait for it to load
  4. Switch to the "Catch up" tab and wait for it to load
  5. Open "Birthdays" and send wishes one by one

Usage:
  python3 linkedin_birthdays.py              # send wishes
  python3 linkedin_birthdays.py --dry-run    # just list who would be wished (sends nothing)
  python3 linkedin_birthdays.py --limit 5    # send at most 5 wishes
  python3 linkedin_birthdays.py --include-recent   # also belated birthdays (can be 200+)

One-time Chrome setting (lets this script click things in Chrome):
  In Chrome's menu bar: View > Developer > Allow JavaScript from Apple Events
On the first run macOS may ask to let Terminal control "Google Chrome": click OK.
"""

import argparse
import datetime as dt
import json
import random
import subprocess
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SENT_LOG = BASE_DIR / "birthday_wishes_sent.json"

CHROME_PROFILE = "Default"  # the "Badarinath Devarasetty" / cam.badari@gmail.com profile
GMAIL_URL = "https://mail.google.com/mail/u/0/"
LINKEDIN_URL = "https://www.linkedin.com/feed/"
MY_NETWORK_URL = "https://www.linkedin.com/mynetwork/"
CATCH_UP_URL = "https://www.linkedin.com/mynetwork/catch-up/all/"
BIRTHDAYS_URL = "https://www.linkedin.com/mynetwork/catch-up/birthday/"
# {name} = full name, {suggestion} = LinkedIn's suggested text for that person
# ("Wishing you a very happy birthday!" or "Happy belated birthday!")
WISH_TEMPLATE = "Hi {name}, {suggestion_lc}"


def log(msg):
    print(f"[{dt.datetime.now():%H:%M:%S}] {msg}", flush=True)


def human_pause(lo=1.5, hi=3.5):
    time.sleep(random.uniform(lo, hi))


# ---------------------------------------------------------------- Chrome control

class JSBlocked(Exception):
    """Chrome's 'Allow JavaScript from Apple Events' setting is off."""


def osascript(script, *args):
    r = subprocess.run(["osascript", "-e", script, *args], capture_output=True, text=True)
    if r.returncode != 0:
        err = r.stderr.strip()
        if "JavaScript through AppleScript is turned off" in err or "Apple Events" in err:
            raise JSBlocked(err)
        if "Can’t get window id" in err or "Can't get window id" in err:
            sys.exit("\nThe Chrome window used by the script was closed. Stopping.")
        if "Not authorized" in err or "-1743" in err:
            sys.exit("\nmacOS blocked control of Chrome. Allow it in System Settings > "
                     "Privacy & Security > Automation (Terminal > Google Chrome).")
        raise RuntimeError(err)
    return r.stdout.strip()


class Chrome:
    """Drives one window of the user's real Chrome via AppleScript."""

    def __init__(self):
        self.window_id = None
        self.js_allowed = True

    def open_profile_window(self, url):
        subprocess.run(["open", "-na", "Google Chrome", "--args",
                        f"--profile-directory={CHROME_PROFILE}", "--new-window", url], check=True)
        time.sleep(3)
        self.window_id = osascript('tell application "Google Chrome" to return id of front window')

    def new_tab(self, url):
        osascript(f'''on run argv
            tell application "Google Chrome"
                set w to window id {self.window_id}
                tell w to make new tab with properties {{URL:(item 1 of argv)}}
                set active tab index of w to (count of tabs of w)
                set index of w to 1
                activate
            end tell
        end run''', url)

    def goto(self, url):
        osascript(f'''on run argv
            tell application "Google Chrome" to set URL of active tab of window id {self.window_id} to (item 1 of argv)
        end run''', url)

    def close_tab(self):
        osascript(f'tell application "Google Chrome" to close active tab of window id {self.window_id}')

    def url(self):
        return osascript(
            f'tell application "Google Chrome" to return URL of active tab of window id {self.window_id}')

    def js(self, code):
        return osascript(f'''on run argv
            tell application "Google Chrome" to return execute active tab of window id {self.window_id} javascript (item 1 of argv)
        end run''', code)

    def wait_loaded(self, timeout=30):
        deadline = time.time() + timeout
        time.sleep(1)
        while time.time() < deadline:
            if not self.js_allowed:
                # No page access: wait until Chrome's tab stops loading
                if osascript(f'tell application "Google Chrome" to return loading of '
                             f'active tab of window id {self.window_id}') == "false":
                    break
            else:
                try:
                    if self.js("document.readyState") == "complete":
                        break
                except JSBlocked:
                    self.js_allowed = False
                    continue
                except RuntimeError:
                    pass
            time.sleep(0.5)
        human_pause(2, 4)  # LinkedIn keeps rendering after "complete"

    def click_text(self, texts, timeout=15):
        """Click the first visible link/button/tab whose text or label matches one of texts."""
        if not self.js_allowed:
            return False
        code = JS_HELPERS + f"clickByText({json.dumps(texts)})"
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.js(code) == "ok":
                return True
            time.sleep(1)
        return False


JS_HELPERS = r"""
function visible(el){ const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; }
function label(el){ return ((el.innerText || '') + ' ' + (el.getAttribute('aria-label') || '')).trim().toLowerCase(); }
function clickByText(texts){
  const els = [...document.querySelectorAll('a, button, [role=tab], [role=button], [role=radio], label')];
  for (const t of texts.map(x => x.toLowerCase())) {
    const el = els.find(e => visible(e) && ((e.innerText || '').trim().toLowerCase() === t)) ||
               els.find(e => visible(e) && label(e).includes(t));
    if (el) { el.click(); return 'ok'; }
  }
  return 'notfound';
}
"""

# Birthday cards have a button labelled "Message <Name>: Wishing you a very happy birthday!".
# Returns the next person not in `skip`; clicks their button unless dryRun.
JS_NEXT_WISH = JS_HELPERS + r"""
(function(skip, dryRun, todayOnly){
  const btns = [...document.querySelectorAll('button, a')].filter(visible);
  for (const b of btns) {
    const m = (b.getAttribute('aria-label') || '').match(/^Message (.+?):\s*(.*birthday.*)$/i);
    if (!m || skip.includes(m[1].trim())) continue;
    // Card text says "Celebrate X's birthday today" or "... recent birthday on Sep 25"
    let card = b, when = '';
    for (let i = 0; i < 8 && card && !when; i++) {
      card = card.parentElement;
      const t = (card && card.innerText) || '';
      const w = t.match(/birthday today|recent birthday on [A-Za-z]+ \d+/i);
      if (w) when = w[0].toLowerCase().startsWith('birthday today') ? 'today' : w[0].replace(/^recent birthday /i, '');
    }
    if (todayOnly && when !== 'today') {
      if (when) return JSON.stringify({found: false, reachedOld: true});
      continue;
    }
    if (!dryRun) { b.scrollIntoView({block: 'center'}); b.click(); }
    return JSON.stringify({found: true, name: m[1].trim(), suggestion: m[2].trim(), when});
  }
  return JSON.stringify({found: false});
})(SKIP, DRY_RUN, TODAY_ONLY)
"""

# Loads more birthday cards: clicks "Show more"-style buttons and scrolls the
# last card (and any scrollable list around it) into view.
JS_LOAD_MORE = JS_HELPERS + r"""
(function(){
  const more = [...document.querySelectorAll('button')].find(b => visible(b) &&
      /^(show|see|load) more/i.test((b.innerText || b.getAttribute('aria-label') || '').trim()));
  if (more) more.click();
  const cards = [...document.querySelectorAll('[aria-label^="Message "]')];
  if (cards.length) cards[cards.length - 1].scrollIntoView({block: 'end'});
  window.scrollBy(0, 2000);
  // LinkedIn's list scrolls inside its own box (<main>), not the window
  for (const e of document.querySelectorAll('main, [class*="scaffold"], div')) {
    const st = getComputedStyle(e);
    if (/(auto|scroll)/.test(st.overflowY) && e.scrollHeight > e.clientHeight + 50) e.scrollTop += 1500;
  }
  return more ? 'clicked' : 'scrolled';
})()
"""

# LinkedIn renders the messaging page inside a same-origin "preload" iframe, so
# look for the message composer in the page and in every same-origin frame.
JS_COMPOSER = r"""
function composerDocs(){
  const docs = [document];
  for (const f of document.querySelectorAll('iframe')) {
    try { if (f.contentDocument) docs.push(f.contentDocument); } catch (e) {}
  }
  return docs;
}
function findComposer(name){
  for (const doc of composerDocs()) {
    const box = doc.querySelector('.msg-form__contenteditable');
    if (!box) continue;
    const heads = [...doc.querySelectorAll('h2, .msg-entity-lockup__entity-title')].map(h => h.innerText.trim());
    if (!heads.some(h => h.includes(name))) continue;   // wrong/old conversation still showing
    const form = box.closest('form') || doc;
    return {doc, box, send: form.querySelector('.msg-form__send-button')};
  }
  return null;
}
"""

# Birthday "Send message" pop-up: a textarea (aria-label "Message") prefilled
# with LinkedIn's suggestion, plus a Send button. Only used if it shows `name`.
JS_MODAL = r"""
function findModal(name){
  for (const ta of document.querySelectorAll('textarea[aria-label="Message"]')) {
    let m = ta;
    for (let i = 0; i < 15 && m; i++) {
      m = m.parentElement;
      if (!m) break;
      const send = [...m.querySelectorAll('button')].find(b => (b.innerText || '').trim() === 'Send');
      if (send) return (m.innerText || '').includes(name) ? {ta, send} : null;
    }
  }
  return null;
}
"""

# Puts the wish text in the pop-up (or messaging page) and clicks Send.
# Returns 'sent' or 'waiting'.
JS_SEND = JS_MODAL + JS_COMPOSER + r"""
(function(name, text){
  const modal = findModal(name);
  if (modal) {
    if (modal.ta.value !== text) {
      const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set;
      modal.ta.focus();
      setter.call(modal.ta, text);                      // works with React-controlled inputs
      modal.ta.dispatchEvent(new Event('input', {bubbles: true}));
      return 'waiting';
    }
    if (modal.send.disabled) return 'waiting';
    modal.send.click();
    return 'sent';
  }
  const c = findComposer(name);
  if (!c) return 'waiting';
  if (!c.box.innerText.trim()) {
    c.box.focus();
    c.doc.execCommand('insertText', false, text);
    c.box.dispatchEvent(new Event('input', {bubbles: true}));
    return 'waiting';
  }
  if (!c.send || c.send.disabled) return 'waiting';
  c.send.click();
  return 'sent';
})(NAME, TEXT)
"""

# True while a birthday "Send message" pop-up for `name` is still open.
JS_MODAL_OPEN = JS_MODAL + "(function(name){ return String(!!findModal(name)); })(NAME)"


# ---------------------------------------------------------------- sent log

def load_sent_today():
    today = dt.date.today().isoformat()
    try:
        data = json.loads(SENT_LOG.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
    return data, set(data.get(today, []))


def record_sent(data, name):
    today = dt.date.today().isoformat()
    data.setdefault(today, [])
    if name not in data[today]:
        data[today].append(name)
    SENT_LOG.write_text(json.dumps(data, indent=2))


# ---------------------------------------------------------------- steps

def open_birthdays(chrome):
    log("Step 3: Opening 'My Network'...")
    if not chrome.click_text(["My Network"]):
        chrome.goto(MY_NETWORK_URL)
    chrome.wait_loaded()

    log("Step 4: Opening 'Catch up' tab...")
    if not chrome.click_text(["Catch up"]):
        chrome.goto(CATCH_UP_URL)
    chrome.wait_loaded()

    log("Step 5: Opening 'Birthdays'...")
    if not chrome.click_text(["Birthdays"]):
        chrome.goto(BIRTHDAYS_URL)
    chrome.wait_loaded()

    if not chrome.js_allowed:
        return
    # The list loads as you scroll; scroll down a few times, then back to top
    for _ in range(6):
        chrome.js(JS_LOAD_MORE)
        time.sleep(1.5)
    time.sleep(1)


def wish_text(person):
    s = person["suggestion"] or "Wishing you a very happy birthday!"
    return WISH_TEMPLATE.format(name=person["name"], suggestion=s,
                                suggestion_lc=s[0].lower() + s[1:])


def next_person(chrome, skip, dry_run, today_only):
    """Find (and click, unless dry run) the next birthday person not in skip."""
    code = (JS_NEXT_WISH.replace("SKIP", json.dumps(sorted(skip)))
            .replace("DRY_RUN", json.dumps(dry_run)).replace("TODAY_ONLY", json.dumps(today_only)))
    for _ in range(15):  # the list loads as you scroll
        result = json.loads(chrome.js(code))
        if result["found"]:
            return result
        if result.get("reachedOld"):
            return None
        chrome.js(JS_LOAD_MORE)
        time.sleep(2)
    return None


def send_wishes(chrome, dry_run, limit, today_only):
    data, done_today = load_sent_today()
    skip = set(done_today)
    sent = 0

    if done_today:
        log(f"Already wished today: {', '.join(sorted(done_today))}")

    while limit is None or sent < limit:
        if not dry_run and "/catch-up/birthday" not in chrome.url():
            chrome.goto(BIRTHDAYS_URL)
            chrome.wait_loaded()

        person = next_person(chrome, skip, dry_run, today_only)
        if not person:
            break
        name = person["name"]
        skip.add(name)
        text = wish_text(person)

        if dry_run:
            log(f" -> Would wish {name} ({person['when']}): \"{text}\"")
            continue

        log(f" -> Wishing {name} ({person['when']}): \"{text}\"")
        send_js = JS_SEND.replace("NAME", json.dumps(name)).replace("TEXT", json.dumps(text))
        status = "waiting"
        for _ in range(25):
            time.sleep(1)
            status = chrome.js(send_js)
            if status == "sent":
                break
        if status == "sent":
            # Confirm LinkedIn accepted it: the pop-up closes after a successful send
            for _ in range(10):
                time.sleep(1)
                if chrome.js(JS_MODAL_OPEN.replace("NAME", json.dumps(name))) == "false":
                    break
            else:
                status = "stuck"
        if status == "sent":
            sent += 1
            done_today.add(name)
            record_sent(data, name)
            log(f"    Sent ({sent})")
        else:
            log(f"    Could not send to {name} ({'pop-up did not close after Send' if status == 'stuck' else 'message box did not open'})")

        human_pause(3, 6)  # be gentle; avoid LinkedIn rate-limits
        chrome.goto(BIRTHDAYS_URL)
        chrome.wait_loaded()

    log(f"Done. Wishes sent this run: {sent}. Total wished today: {len(done_today)}.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="only list who would be wished")
    ap.add_argument("--limit", type=int, default=None, help="max wishes to send")
    ap.add_argument("--include-recent", action="store_true",
                    help="also wish recent (belated) birthdays, not just today's")
    args = ap.parse_args()

    chrome = Chrome()
    log("Step 1: Opening Chrome (Badarinath Devarasetty profile) with Gmail...")
    chrome.open_profile_window(GMAIL_URL)

    log("Step 2: Opening LinkedIn in a new tab...")
    chrome.new_tab(LINKEDIN_URL)
    chrome.wait_loaded()
    if any(k in chrome.url() for k in ("login", "authwall", "signup")):
        sys.exit("LinkedIn isn't signed in on this Chrome profile. Sign in and run again.")

    open_birthdays(chrome)
    if not chrome.js_allowed:
        sys.exit("\nThe Birthdays page is open, but Chrome won't let the script click "
                 "'Message' / 'Send'.\nTo send wishes automatically, enable in Chrome's "
                 "menu bar:\n  View > Developer > Allow JavaScript from Apple Events\n"
                 "then run this script again.")
    send_wishes(chrome, args.dry_run, args.limit, today_only=not args.include_recent)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\nStopped.")
