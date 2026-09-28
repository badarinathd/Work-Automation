/**
 * Google Apps Script that lets linkedin_birthdays.py add rows to this Google Sheet.
 *
 * Setup (one time):
 *  1. Create a Google Sheet (e.g. "LinkedIn Birthday Contacts").
 *  2. Extensions > Apps Script. Delete what's there, paste this whole file.
 *  3. Change SECRET below to any random word (and put the same word in sheet_config.json).
 *  4. Deploy > New deployment > type "Web app":
 *       Execute as: Me       Who has access: Anyone
 *     Click Deploy, allow access, and copy the "Web app URL".
 *  5. Put the URL and secret in ~/Work-Automation/sheet_config.json:
 *       {"url": "https://script.google.com/macros/s/.../exec", "secret": "your-word"}
 */
const SECRET = 'change-me';
const HEADERS = ['Date', 'Name', 'Profile link', 'Phone #'];

function doPost(e) {
  const body = JSON.parse(e.postData.contents);
  if (body.secret !== SECRET) {
    return ContentService.createTextOutput('forbidden');
  }
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheets()[0];
  if (sheet.getLastRow() === 0) {
    sheet.appendRow(HEADERS);
    sheet.setFrozenRows(1);
  }
  // Skip if this profile link is already in the sheet
  const links = sheet.getLastRow() > 1
      ? sheet.getRange(2, 3, sheet.getLastRow() - 1, 1).getValues().flat()
      : [];
  if (links.includes(body.profile)) {
    return ContentService.createTextOutput('exists');
  }
  // Leading ' keeps phone numbers as text (so +91... isn't turned into a formula/number)
  sheet.appendRow([body.date, body.name, body.profile, "'" + body.phone]);
  return ContentService.createTextOutput('added');
}
