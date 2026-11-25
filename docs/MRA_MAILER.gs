// MRA mailer: paste into a new project at https://script.google.com, fill ALLOWED, then
// Deploy > New deployment > Web app > Execute as: Me > Who has access: Anyone > Deploy, and copy the Web app URL
// into the cloud environment variable MRA_MAILER_URL. Only the addresses in ALLOWED can ever receive mail from it.
const ALLOWED = ['owner@example.com'];  // the owner and associates, lower case

function doPost(e) {
  const d = JSON.parse(e.postData.contents);
  const to = String(d.to || '').trim().toLowerCase();
  const subject = String(d.subject || '');
  if (ALLOWED.indexOf(to) < 0) return out({ok: false, error: 'recipient not allowed'});
  if (subject.indexOf('MRA ') !== 0) return out({ok: false, error: 'subject must start with MRA'});
  const q = 'in:sent to:' + to + ' subject:("' + subject.replace(/["()]/g, ' ') + '") newer_than:2d';
  if (GmailApp.search(q, 0, 1).length) return out({ok: true, skipped: 'already sent'});
  const opts = {htmlBody: String(d.html || ''), name: 'MRA Property Hunt'};
  if (d.inline_png) opts.inlineImages = {att0: Utilities.newBlob(Utilities.base64Decode(d.inline_png), 'image/png', 'mra-weekly.png')};
  GmailApp.sendEmail(to, subject, String(d.text || ''), opts);
  return out({ok: true, sent: true});
}

function out(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}
