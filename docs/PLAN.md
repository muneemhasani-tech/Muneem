# Lead Verifier — Plan & Spec Verification

Written before any code. Section 1 is the §12 verification result, section 2 the design
decisions taken where the spec was silent or contradictory, section 3 the milestone plan.

## 1. §12 verification results

Checked 2026-09-30. Several provider doc sites (docs.quickemailverification.com,
verifalia.com, urlhaus-api.abuse.ch, data.iana.org) were blocked by the build sandbox's
egress proxy, so those rows rest on search-result summaries plus vendor SDK knowledge and are
marked **UNVERIFIED-AGAINST-LIVE-DOCS**. Every client is covered by a `respx` contract test,
so a wrong field name is a one-line fix, but **do one live call per provider before trusting
a 500-row run** (`lead-verifier run ... --limit 5`).

| # | Item | Spec assumption | Finding | Action |
|---|------|-----------------|---------|--------|
| 1 | QuickEmailVerification | ~100/day free | Confirmed: 100 credits/day free, full API access. `GET /v1/verify?email=&apikey=`; fields `result, reason, accept_all, role, disposable, free, mx_record, safe_to_send, did_you_mean`. Booleans arrive as strings `"true"/"false"`. Remaining credits in header `X-QEV-Remaining-Credits`. Insufficient credit = HTTP 402 (UNVERIFIED). | Client tolerant of string/bool. Treat 402/429 as quota exhaustion. |
| 2 | Verifalia | ~25/day, auth | Confirmed 25 free credits/day. **Resets at midnight GMT, not Asia/Dhaka.** Auth = HTTP Basic (username/password). Job-based API (`POST /v2.6/email-validations`, poll, read `entries`). | **Mismatch:** spec's quota day is Dhaka. Added per-provider `reset_tz` (Verifalia = UTC) so our counter matches the provider's. Response shape UNVERIFIED; parser is defensive; job deleted after read (lead privacy). |
| 3 | Safe Browsing vs Web Risk | default Web Risk | Web Risk `uris.search` free tier is **100,000 calls/month** (then $0.50/1k), no commercial restriction stated. | Web Risk used. Spec's `daily_limit: 3000` ≈ 90k/month, safely inside the free tier. Safe Browsing not built. |
| 4 | URLhaus | maybe key | **Auth-Key now mandatory** (abuse.ch "Community First", since 2025-06-30), sent as HTTP header `Auth-Key`; free from auth.abuse.ch. Host lookup: `POST https://urlhaus-api.abuse.ch/v1/host/` form `host=`. | Key required in `.env`; without it URLhaus is skipped (domain_flagged stays blank unless Web Risk answers). |
| 5 | RDAP for `.bd` | check coverage | **`.bd` has no RDAP server** in the IANA bootstrap (WHOIS only, `whois.btcl.net.bd`, unreliable). | `whoisit` for gTLDs; `python-whois` fallback; `.bd` age will often be blank — expected and never crashes a row. |

## 2. Design decisions (spec gaps / contradictions)

1. **"No valid phone AND no valid email → REJECT" vs "email risky + no phone → C".**
   Reconciled by defining a *usable* email = passed offline checks and not (invalid /
   disposable) — i.e. valid, risky-non-disposable, or unknown. The early reject at step 4 fires
   when there is no valid phone and no usable email. Email `invalid` after the API also
   rejects (when no phone).
2. **Valid mobile of any country counts.** Real-estate leads include NRIs. Parsing defaults to
   BD; `+44…`/`+1…` mobiles that validate are treated as valid mobiles.
3. **Valid mobile + invalid email → B** (`email_invalid`). Spec's A/B rules don't cover it; the
   phone is still a working channel.
4. **Domain age < 90d caps the grade at C**; flagged domain → REJECT.
5. **Phone-only rows (no email)** can reach A; the email is `skipped`/`no_email`.
6. **URLhaus flags only hosts with currently-online malware URLs** (`urls_online > 0`), so a
   cleaned-up compromised site isn't penalised forever. `domain.urlhaus_require_online: false`
   restores "listed at all".
7. **Skip-domains** = the spec's free-mail list plus social/link hosts (facebook.com, wa.me,
   …) — checking those is pointless credit spend.
8. **Duplicate pointer**: `phone_duplicate_of` is filled for phone *and* email duplicates
   (first-occurrence row number); the reason string says which (`duplicate_phone_of_row_3`).
   Row numbers are 1-based data rows (header excluded).
9. **Cache per provider**: reputation cached as `webrisk|domain` and `urlhaus|domain`
   separately, so a half-answered lookup still saves credits next run. An MX cache (`mx`, 7d)
   is added since DNS is otherwise re-done on every run. Age cache stores the creation *date*
   so age stays correct across the 180-day TTL.
10. **Never cached**: quota-exhausted, no-key, transport-failure results.
11. **Resume** = re-run the whole file; everything already answered is a cache hit (zero
    credits), only deferred lookups touch the network. `resume` also picks up `provider_error`.
12. **In-flight de-duplication**: 200 leads sharing a domain make one lookup, not 200.
13. **DNS failure ≠ bad email.** Only NXDOMAIN / null-MX / no-A-or-MX is `no_mx`; a timeout is
    `unknown/mx_check_failed`, so a flaky laptop connection can't mass-reject good leads.
14. **CSV**: read UTF-8(BOM) with cp1252 fallback; write UTF-8 with BOM (Google Sheets opens
    Bangla names correctly). Caveat: Sheets converts `+8801…` to a number on import — import
    with "Convert text to numbers" **off** (in README).
15. **Extras beyond the file tree**: `config.py`, `http.py` (retry helper), `util.py`.

## 3. Pipeline shape

```
Phase A (sync, all rows):  normalise → phone → dedupe → email syntax/disposable → derive domain
Phase B (async, per row):  MX → [early reject?] → email API → [reject?] → reputation ‖ age → WhatsApp
Phase C (sync):            score → write graded + A_B / C / REJECT
```
Dedupe needs the whole file, so phase A completes before any network call.
`--offline-only` stops phase B after MX (no reputation, no age, no API).

## 4. Milestones (each ends with green tests)

1. Skeleton: config, CLI stub, CSV read/write + aliasing, round-trip test
2. Phone + dedupe (20 messy BD formats)
3. Email offline (syntax, disposable, MX); `--offline-only` end to end
4. Cache + quota
5. Email API (QEV → Verifalia → deferred)
6. Domain reputation + age
7. Scoring + split outputs
8. resume + quota commands
9. WhatsApp interface + disabled stub
10. README

## 5. Risks

- Unverified provider payloads (above) → mitigated by contract tests + `--limit 5` smoke run.
- QEV's own reset timezone is undocumented; configurable via `reset_tz`.
- Sandbox has no working DNS/most provider hosts, so live behaviour is tested by mocks only.
