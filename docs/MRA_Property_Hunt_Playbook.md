# MRA Property Hunt — Daily Automated Listing Pipeline
Process documentation — copy into any new session for context

## WHAT THIS IS
A daily automation that hunts new for-sale listings in Gulshan, Banani, Purbachal, Uttara, Dhanmondi and
Bashundhara R/A with the Property Finder tool (`property_finder/` in this repo), ranks them by projected
return, and hands the owner one short list to act on. The owner's part is limited to **one task a day**
(plus one short extra on Fridays).

## HOW IT WORKS

### LAYER 1 — Cloud Agent: Daily Property Hunt (4:00 PM Dhaka = 10:00 UTC, every day)
Platform: Claude Code Routines (cloud-scheduled agent, fresh session each run)
Routine name: "MRA Property Hunt" (ID shown in the Routines list)
What it does:
1. Clones this repo and finds yesterday's CSV in Google Drive ("MRA Property Hunt — YYYY-MM-DD.csv").
2. Runs `python3 -m property_finder hunt --web-areas 2 --seen yesterday.csv --out out`:
   * Crawls every source that allows it: Bproperty (sitemap), bdHousing, Aabason, Homefair BD,
     Property Finder BD, Concord Property Solutions (robots.txt checked before every request)
   * Web search (Serper, Google results) for 2 of the 6 areas per day, rotating, so every area is
     covered every 3 days: Facebook groups (English + Bangla), plot posts, Marketplace, Facebook pages,
     Bikroy ads, Navana, Shanta, Rangs, Bashundhara, Assure, open web (English + Bangla)
   * Marks a listing NEW when it was not in yesterday's CSV
3. Writes two Message drafts (WhatsApp, English + Bangla) for each of "Today's 3 to call":
   * Message A — approach the owner as MRA, offering to market the property and bring buyers
   * Message B — approach as a buyer's agent, only for a listing that matches a real MRA client
4. Saves the digest to Google Drive as "MRA Property Hunt — YYYY-MM-DD" and the full list as
   "MRA Property Hunt — YYYY-MM-DD.csv" (this CSV is tomorrow's "seen" list)
5. Emails the owner: Today's 3 to call (with drafts), best projected returns, price drops,
   new Facebook/web leads, link to the Drive files
6. Fridays only: adds a weekly roll-up from the last 7 Drive digests (new listings per area,
   price per sqft movement, which sources found the most)

It never contacts anyone. Only the owner sends messages.

### LAYER 2 — Owner (7:00 PM Dhaka, about 20 minutes): the ONE daily task
1. Open the "MRA Property Hunt — YYYY-MM-DD" email.
2. Call or WhatsApp the 3 people under "Today's 3 to call", using the drafts.
3. Reply to the email with one line per lead: `called / no answer / interested / not interested`.
   (Tomorrow's run reads the replies and drops "not interested" leads from the call list.)

Fridays, extra 10 minutes: read the weekly roll-up and update the rent assumptions in the dashboard
if MRA has better figures.

## DATA FLOW
4 PM cloud  → crawl + 2-area web search → digest + CSV to Drive → email to owner
7 PM owner  → contact today's 3 → one-line reply per lead
next 4 PM   → reads yesterday's CSV (what is new) and the owner's replies (who to skip)

## COSTS AND LIMITS
* Web search: 13 queries × 2 areas = 26 Serper searches a day, about 800 a month. The free Serper
  credit (2,500) lasts about 3 months; then a paid Serper plan is needed, or set `--web-areas 1`
  (13 a day) or `--no-web` (crawl only, free).
* Crawling is free. Bikroy and Bdstall only work from the owner's own computer (Cloudflare blocks
  cloud servers; Bdstall's robots.txt bans AI crawlers), so the cloud run skips them.
* Projected returns use the rent assumptions; placeholders until MRA's figures are entered.

## GOOGLE DRIVE NAMING CONVENTION
"MRA Property Hunt — YYYY-MM-DD"       digest (Google Doc)
"MRA Property Hunt — YYYY-MM-DD.csv"   full listing export, tomorrow's "seen" list
Never overwrite an earlier day's file.

## RUN BY HAND
`python3 -m property_finder hunt --web-areas 2 --seen yesterday.csv --out reports`
Prints the number of new listings and the paths of the digest and CSV.
