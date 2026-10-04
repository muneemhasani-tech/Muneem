---
name: content-review
description: Quality-control gate for a script/caption before filming or publishing — Hemingway-style tightening, compliance check against the business config, claims verification status, and a go/no-go checklist. Use before approval, or when the user asks to edit/tighten/check a script.
---

# content-review

## Purpose
Catch weak writing and compliance/accuracy risks before they cost views or trust. This is the last Claude gate before human approval.

## Inputs
`script` record (or pasted text), caption/hashtags if available, `content_score` if present, active config compliance + banned phrases.

## Workflow
1. **Tighten (Hemingway pass)** — the source strategy runs scripts through Hemingway Editor; aim for reading grade ≤6, no hard/very-hard sentences, minimal adverbs/passive (if the script is Bangla/Banglish, judge by sentence length and plain words instead; the app is English-only and can be run by the user on the English parts): cut adverbs/filler; one idea per sentence; prefer short Anglo-Saxon words (or plain Bangla); spoken-rhythm check; remove throat-clearing opening; keep voice from config. Show before→after for changed lines.
2. **Compliance**: check every config `compliance` rule and `banned_phrases`. List each violation with the exact line.
3. **Claims**: list each claim; status `verified` only if a source and date are in the record. Otherwise "UNVERIFIED — human must verify".
4. **Flow**: hook promise paid off? CTA single? Length within range? Claim of urgency/scarcity honest?
5. **Checklist result**: PASS / PASS WITH HUMAN CHECKS / FAIL.
6. Update the script with the tightened version only as a proposal (keep original). Set idea `status: reviewed`.

## Decision rules
- Any unverified legal/financial claim → cannot be PASS; at best PASS WITH HUMAN CHECKS.
- Any accusation of a named party or promised returns → FAIL.
- Do not alter facts while "tightening". If a edit might change meaning, flag it.

## Quality checks
Edited script is shorter or equal; meaning unchanged; every violation cites a line.

## Output
Verdict, violations, claims table, tightened script (proposal), final human checklist.

## Failure handling
No script → ask for it. No config → use conservative defaults (no legal figures, no returns) and say so.

## Human approval points
**Human approves** the final script and verifies all flagged claims. This skill never marks content approved.

## Tool assumptions
Text only. Cannot verify law or market data itself.
