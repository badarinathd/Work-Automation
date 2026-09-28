#!/usr/bin/env python3
"""
Send today's Facebook birthday wishes using your normal Chrome (already signed in).

Opens https://www.facebook.com/events/birthdays in a new tab, then for each of
"Today's birthdays":
  - if Facebook shows a ready-made wish box: posts it on their timeline
  - if it only offers "Message": sends a private Messenger message

Usage:
  python3 facebook_birthdays.py              # send wishes
  python3 facebook_birthdays.py --dry-run    # just list who would be wished (sends nothing)

Needs the same one-time Chrome setting as linkedin_birthdays.py:
  View > Developer > Allow JavaScript from Apple Events
"""

import argparse
import json
import sys
import time

from linkedin_birthdays import Chrome, JSBlocked, human_pause, load_sent_today, log, record_sent

BIRTHDAYS_URL = "https://www.facebook.com/events/birthdays"
# Messenger text, {first} = first name
MESSENGER_TEMPLATE = "Happy Birthday, {first}! Wishing you a wonderful year ahead."

JS_HELPERS = r"""
function visible(el){ const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; }
// Each person has a link labelled "<Name>'s birthday is <Month Day[, Year]>".
// Their card is the nearest ancestor that contains only that one person.
function cards(){
  const todayHdr = [...document.querySelectorAll('span, h2, h3')].find(e => e.innerText.trim() === "Today's birthdays");
  const recentHdr = [...document.querySelectorAll('span, h2, h3')].find(e => e.innerText.trim() === "Recent birthdays");
  const out = [];
  for (const a of document.querySelectorAll('a[aria-label*="\'s birthday is "]')) {
    if (!visible(a)) continue;
    // only "Today's birthdays": after its header and before "Recent birthdays"
    if (todayHdr && !(todayHdr.compareDocumentPosition(a) & Node.DOCUMENT_POSITION_FOLLOWING)) continue;
    if (recentHdr && (recentHdr.compareDocumentPosition(a) & Node.DOCUMENT_POSITION_FOLLOWING)) continue;
    const name = a.getAttribute('aria-label').split("'s birthday is ")[0].trim();
    let card = a;
    while (card.parentElement &&
           card.parentElement.querySelectorAll('a[aria-label*="\'s birthday is "]').length === 1) {
      card = card.parentElement;
    }
    const box = card.querySelector('[role=textbox][contenteditable=true]');
    const post = card.querySelector('[role=button][aria-label="Post birthday message"]');
    const msg = [...card.querySelectorAll('[role=button]')].find(b => b.getAttribute('aria-label') === 'Message');
    const done = /You wished .* happy birthday|You (posted|wrote) on/i.test(card.innerText);
    out.push({name, card, box, post, msg, done});
  }
  return out;
}
"""

JS_LIST = JS_HELPERS + r"""
JSON.stringify(cards().map(c => ({name: c.name, done: c.done,
  kind: c.box && c.post ? 'timeline' : (c.msg ? 'messenger' : 'none'),
  text: c.box ? c.box.innerText.trim() : ''})))
"""

JS_POST = JS_HELPERS + r"""
(function(name){
  const c = cards().find(c => c.name === name);
  if (!c || !c.post || !c.box || !c.box.innerText.trim()) return 'missing';
  c.post.click();
  return 'clicked';
})(NAME)
"""

JS_IS_DONE = JS_HELPERS + r"""
(function(name){
  const c = cards().find(c => c.name === name);
  return String(!!c && (c.done || !c.box));
})(NAME)
"""

JS_OPEN_MESSENGER = JS_HELPERS + r"""
(function(name){
  const c = cards().find(c => c.name === name);
  if (!c || !c.msg) return 'missing';
  c.msg.click();
  return 'clicked';
})(NAME)
"""

# Messenger chat pop-up: textbox labelled "Write to <Name>". Its editor ignores
# execCommand, so the text is pasted. The send button ("Press enter to send")
# only exists once there's text; with an empty box it's "Send a like" (never clicked).
JS_MESSENGER_SEND = r"""
(function(name, text){
  const box = document.querySelector('[role=textbox][contenteditable=true][aria-label="Write to ' + name + '"]');
  if (!box) return 'waiting';
  let chat = box;
  for (let i = 0; i < 20 && chat && !chat.querySelector('[aria-label="Close chat"]'); i++) chat = chat.parentElement;
  if (!chat) return 'waiting';
  if (chat.innerText.includes(text)) {
    // Our text is in the conversation and the box is empty again: it was sent
    if (!box.innerText.trim()) return 'sent';
  }
  if (!box.innerText.trim()) {
    box.focus();
    const dt = new DataTransfer();
    dt.setData('text/plain', text);
    box.dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true}));
    return 'waiting';
  }
  if (!box.innerText.includes(text)) return 'wrong-text';
  const send = chat.querySelector('[aria-label="Press enter to send"], [aria-label="Press Enter to send"]');
  if (!send) return 'waiting';
  send.click();
  return 'waiting';   // confirmed as 'sent' on the next check
})(NAME, TEXT)
"""


def wait_for(chrome, code, want="true", tries=15):
    for _ in range(tries):
        time.sleep(1)
        if chrome.js(code) == want:
            return True
    return False


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="only list who would be wished")
    args = ap.parse_args()

    chrome = Chrome()
    chrome.window_id = chrome_window(chrome)
    log("Opening Facebook birthdays in a new tab...")
    chrome.new_tab(BIRTHDAYS_URL)
    chrome.wait_loaded()
    time.sleep(3)
    if "login" in chrome.url():
        sys.exit("Facebook isn't signed in on this Chrome profile. Sign in and run again.")

    data, done_today = load_sent_today()
    people = json.loads(chrome.js(JS_LIST))
    if not people:
        log("No birthdays today.")
    sent = 0
    for p in people:
        name, key = p["name"], f"facebook:{p['name']}"
        if p["done"] or key in done_today:
            log(f" -  Already wished: {name}")
            continue
        if p["kind"] == "none":
            log(f" -  No way to wish {name} from this page, skipping")
            continue

        if p["kind"] == "timeline":
            log(f" -> Timeline post for {name}: \"{p['text']}\"")
            if args.dry_run:
                continue
            chrome.js(JS_POST.replace("NAME", json.dumps(name)))
            ok = wait_for(chrome, JS_IS_DONE.replace("NAME", json.dumps(name)))
        else:
            text = MESSENGER_TEMPLATE.format(first=name.split()[0])
            log(f" -> Messenger message to {name}: \"{text}\"")
            if args.dry_run:
                continue
            chrome.js(JS_OPEN_MESSENGER.replace("NAME", json.dumps(name)))
            send_js = JS_MESSENGER_SEND.replace("NAME", json.dumps(name)).replace("TEXT", json.dumps(text))
            status = "waiting"
            for _ in range(20):
                time.sleep(1)
                status = chrome.js(send_js)
                if status in ("sent", "wrong-text"):
                    break
            ok = status == "sent"

        if ok:
            sent += 1
            record_sent(data, key)
            log("    Sent")
        else:
            log(f"    Could not send to {name}")
        human_pause(3, 6)

    log(f"Done. Facebook wishes sent this run: {sent}.")


def chrome_window(chrome):
    """Use the front Chrome window (opened by open_chrome_profile.py / linkedin script)."""
    from linkedin_birthdays import osascript
    return osascript('tell application "Google Chrome" to return id of front window')


if __name__ == "__main__":
    try:
        main()
    except JSBlocked:
        sys.exit("Enable in Chrome: View > Developer > Allow JavaScript from Apple Events")
    except KeyboardInterrupt:
        sys.exit("\nStopped.")
