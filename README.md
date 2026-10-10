# Lead Verifier

Filters raw leads for **MRA Real Estate** before they reach the CRM. One CSV in, one graded CSV out.
Cheapest checks first: a row that already failed never costs an API credit.

It grades **contactability** (can we reach this person?), not buyer intent. It sits next to
HOT/WARM/COLD, it doesn't replace it. It never contacts a lead.

## Setup (under 5 minutes)

```bash
python3 -m venv .venv && source .venv/bin/activate     # Python 3.11+
pip install -e .
cp .env.example .env                                   # keys are optional, see below
```

## Try it now (no API keys needed)

```bash
lead-verifier run tests/fixtures/sample_leads.csv --offline-only
```

```
Rows in: 12
A: 2   B: 4   C: 1   REJECT: 5
Credits used this run: none  (offline-only)
Rows deferred: 0
  wrote data/output/sample_leads_graded.csv
  wrote data/output/sample_leads_A_B.csv  (+ _C.csv, _REJECT.csv)
```

`--offline-only` = phone + email syntax + disposable list + MX lookup. Zero credits.

## Point-and-click version

```bash
lead-verifier ui          # opens http://127.0.0.1:8765 in your browser
```
Two tabs: **Check one lead** (type a phone, email and/or website, get a plain-English verdict) and
**Check a spreadsheet** (drop a CSV, filter by grade, download the good leads). It listens on your
computer only. There is also a one-lead command-line version:

```bash
lead-verifier check -p 01676728214 -e name@example.com -w www.example.com
```

## Real run

Drop your CSV in `data/input/`, add keys to `.env`, then:

```bash
lead-verifier run data/input/leads.csv --limit 5      # smoke-test your keys first
lead-verifier run data/input/leads.csv                # full run
```

| Command | What it does |
|---|---|
| `run <csv> [--offline-only] [--limit N] [--out-dir D] [--config F]` | Grade a file |
| `resume <graded.csv>` | Re-check rows deferred by quota (`quota_exhausted` / `provider_error`) |
| `quota` | Today's usage per provider |
| `cache clear [--kind email\|reputation\|age\|mx\|whatsapp]` | Wipe cached lookups |

Every run ends with rows in, A/B/C/REJECT counts, credits used per provider, and rows deferred.
**Re-running a file costs zero new credits**: every answer is cached (email 30d, reputation 7d,
age 180d). If a provider runs out of quota mid-run, the run continues with everything else;
run `resume` after the quota resets (or next day).

## Keys (`.env`)

| Variable | Provider | Free tier | Needed for |
|---|---|---|---|
| `QEV_API_KEY` | QuickEmailVerification | 100/day | mailbox check (primary) |
| `VERIFALIA_USERNAME` / `_PASSWORD` | Verifalia | 25/day (resets midnight **GMT**) | fallback when QEV is exhausted |
| `GOOGLE_WEBRISK_API_KEY` | Google Web Risk | 100k/month | phishing/malware listing |
| `URLHAUS_AUTH_KEY` | abuse.ch | free | malware host listing (**key now mandatory**, get it at https://auth.abuse.ch/) |

Missing key = that provider is skipped, nothing crashes. Domain age uses free RDAP/WHOIS (no key).
**Note:** `.bd` domains have no RDAP server, so their age is often blank. That is expected.

## Output

Your original columns are kept untouched, followed by:
`phone_e164, phone_valid, phone_type, phone_carrier, phone_duplicate_of, email_status,
email_reason, domain, domain_flagged, domain_flag_source, domain_age_days, grade, grade_reasons,
checked_at`. Plus `*_A_B.csv`, `*_C.csv`, `*_REJECT.csv`.
If your file already has a column with one of those names, ours is prefixed `lv_`.

Input columns are matched by alias (case-insensitive): name/full_name/client, phone/mobile/number/
contact/whatsapp, email/e-mail/mail, website/url/site/domain, source/platform/origin. Any of them
may be missing.

**Google Sheets:** File → Import → upload → *untick* "Convert text to numbers, dates and
formulas", otherwise `+8801711223344` is turned into a plain number. Files are UTF-8 with BOM so
Bangla names display correctly.

## Grades

| Grade | Meaning |
|---|---|
| **A** | Valid mobile, and email valid or not given |
| **B** | Valid mobile with risky/unknown/invalid email; or valid email with no phone / a landline |
| **C** | One weak signal only (landline only, or risky email and no phone); or domain younger than 90 days |
| **REJECT** | No usable phone or email; duplicate; domain flagged by Web Risk/URLhaus; disposable email with no valid phone |

`grade_reasons` lists every rule that fired. Thresholds and quotas live in `config.yaml`.
Row numbers in `phone_duplicate_of` are 1-based data rows (header excluded). It is filled for
phone *and* email duplicates; the reason says which.

Judgement calls worth knowing (details in `docs/PLAN.md`):
- Valid mobiles from any country count (NRI buyers), not only Bangladesh.
- A DNS timeout is `unknown/mx_check_failed`, never `no_mx`, so a bad connection can't mass-reject leads.
- URLhaus only flags hosts with malware URLs *currently online* (`domain.urlhaus_require_online`).
- Facebook/Instagram/WhatsApp links etc. are not treated as the lead's domain (`domain.skip_domains`).

## Privacy

`.env`, `cache.db` and `data/` are gitignored. Lead data only goes to the four named verification
APIs. Logs never contain full phones/emails (masked like `+88017****344`); HTTP-client request
logging is silenced because it would print emails and API keys.

## WhatsApp (disabled)

`lead_verifier/checks/whatsapp.py` defines the `WhatsAppChecker` interface and a no-op
`DisabledChecker`. No scraper is bundled: every available checker automates WhatsApp Web, which
breaks often and risks the account used. Setting `whatsapp.enabled: true` without writing your own
checker raises a clear error.

## Development

```bash
pip install -e '.[dev]' && pytest
```
HTTP is mocked with `respx`; no test touches the network.

---

# Property Finder (dashboard)

## Members-only access

The dashboard serves nothing until a person signs in with an approved account. Passwords are stored as salted PBKDF2 hashes, sessions are random tokens in an HttpOnly cookie, wrong-password attempts are rate limited, and every `/api` route (listings, phone numbers, URLs, CSV export) answers 401 without a session.

```
python -m property_finder admin                 # once: create the first admin (email, name, password)
python -m property_finder serve                 # this computer only: http://127.0.0.1:8770
python -m property_finder serve 8770 --host 0.0.0.0   # let others reach it (see HTTPS below)
python -m property_finder users                 # who asked for access
python -m property_finder approve rina@x.com    # or approve in the dashboard under Members
python -m property_finder revoke rina@x.com     # ends that person's sessions at once
```

People open the site and choose *Request access* (name, email, phone, how they know MRA, password). Nothing is visible to them until an admin approves, so call the phone number first. Members can browse listings, export CSV and update lead status and notes. Only admins can run searches, edit return assumptions, store the search API key, and approve or revoke people.

Forgot a password? `python -m property_finder reset-password EMAIL` sets a new one, signs that person out everywhere and clears any lockout.

### One-file version for cPanel

`python -m property_finder build-html index.html` writes a single `index.html` you upload to ordinary hosting (needs `pip install cryptography` on the computer that builds it). It has no server, so protection comes from encryption: the listings, phone numbers and URLs are AES-256-GCM encrypted inside the file, and each member's email and password unlock their own copy of the key (PBKDF2, 600,000 rounds). The admin adds members, resets their passwords and removes them inside the page, then presses *Download updated file* and uploads it to replace the old one. Use https, and give every member a long password: anyone can download the file and guess passwords offline, so the passwords are the whole lock. Run the command again to start over if the admin password is lost (members must be re-added).

To serve other people from the app instead, run it on a machine they can reach and put it behind HTTPS (Caddy or nginx), then start it with `PF_SECURE_COOKIES=1` (and `PF_TRUST_PROXY=1` behind a proxy so attempt limits use the real address). Without HTTPS, passwords cross the network in clear text.

One local dashboard that finds **properties for sale** across ~20 Bangladeshi sources for **Gulshan, Banani, Purbachal, Uttara, Dhanmondi and Bashundhara R/A**, ranks them by projected return, and keeps them as a lead list. Standard library only, no install.

```bash
python3 -m property_finder            # opens http://127.0.0.1:8770
python3 -m property_finder probe      # tests all 20 sources: robots.txt verdict, reachability, anti-bot walls, listings recognised
```

- **Sale only.** Rent ads are never listed or exported. Apartment rent pages are crawled in the background only to measure rent per sqft per area (needs 5+ ads per area), which feeds the ROI projection. Until then the editable placeholder rents under *Return assumptions* are used.
- **ROI on every listing:** rental yield (gross and net), and total return over 5 years = net rental income + price growth. Land shows growth only. Assumptions (rent per sqft by area, empty months, running costs %, growth %) are saved in the local database.
- **Sources (verified live, Oct 2026):** Bproperty (via its sitemap, ~5,400 listing pages in our areas), bdHousing, Aabason, Homefair BD (their own listing pages), Property Finder BD and Concord Property Solutions (via sitemaps). Bikroy (Cloudflare refuses cloud servers) and Bdstall (robots.txt bans AI crawlers) are included but only work when run from your own computer. **Web search** replaces the old one-click links: 12 query templates per area (Facebook groups in English and Bangla, plot posts, Marketplace, Facebook pages, Navana, Shanta, Rangs, Bashundhara, Assure, open web in English and Bangla, see `web_queries` in `sources.json`) run through an official search API (Serper.dev for Google results, or Brave Search). Facebook and Google pages are never fetched; the listing is built from the engine's title and snippet, and other result pages are opened only when their robots.txt allows. Each such listing records the query that found it, the snippet, and its evidence level. Set `SERPER_API_KEY` or `BRAVE_API_KEY`, or paste a key under *Web search* in the dashboard. A full run is 12 queries x 6 areas = 72 searches; repeats within 20 hours are skipped and a monthly budget caps spend. Queries use no `site:` operators (Serper's free plan rejects them); each template instead carries a host filter applied to the results. Developer queries skip about/blog/home pages, and sizes or prices that look absurd are kept and marked Clear with seller (sellers often hide real figures so buyers must call). Removed: BDHouse24, ToLet, Bhumi, Property.com.bd, BanglaProperty, DhakaProperty (domains do not exist), Lamudi and RealEstate.com.bd (unreachable), Flatbazar (an Indian site), Basha Lagbe (robots.txt forbids crawling).
- **Area rule:** a listing is kept only if its own text (English or Bangla) names one of the six areas.
- **Lead tools:** duplicate flag ("on N sites"), owner-only filter, price-drop flag, price per sqft by area, lead status and notes, WhatsApp links, **Export CSV** (columns match `lead-verifier run`, plus yield and return columns).
- **Crawling manners:** identifies itself as `MRA-PropertyFinder`, reads each site's `robots.txt` before every request and skips what it forbids (when an AI agent such as Claude runs it, rules aimed at AI crawlers are obeyed too) (or any site whose robots.txt it cannot read), honours `Crawl-delay`, waits ~1.5 s between requests per site, never tries to get around a block. Robots.txt is not a site's terms of service, so check those too.
- Add or fix a site by editing `property_finder/sources.json` (URL template only, no code). Text size: `--sec` at the top of `static/index.html` scales secondary text (1 = normal).
- Data lives in `data/property/listings.db` (git-ignored; contains phone numbers).

**Not yet verified against live sites** (the build sandbox blocks them): run `probe` first. Sites showing `BLOCKED`, `DEAD` or `NO LISTINGS RECOGNISED` need their URL or parser adjusted.
