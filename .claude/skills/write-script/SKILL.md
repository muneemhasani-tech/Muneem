---
name: write-script
description: Write a beat-by-beat short-form script (story or educational) with spoken lines, on-screen text, and visual notes from an idea, hook, and format. Use when the user asks for a script/reel/short, or after /select-format. For MRA scripts using the HUMPS formula, the mrre-humps-script-writer skill is the specialised alternative; use it if the user wants HUMPS.
---

# write-script

## Purpose
Produce a filmable script that keeps the hook's promise, holds attention, and ends in one CTA.

## Inputs
`content_idea`, selected `hook`, `content_format`, optional `cta`, active config (voice, language, compliance), any facts/sources the user provided.

## Workflow
1. **Structure by format**
   - Educational: hook → why it matters (1 line) → 3 steps/checks max → common mistake → CTA.
   - Story: hook (cold open) → setup → turn → lesson → CTA. Use anonymised/composite stories and label composites in the notes; never invent a real client.
   - Myth vs fact / list: hook → items, strongest last or first-and-last → CTA.
2. Write beats with timecodes. Spoken lines at ~2.5 words/sec; total fits format length.
3. Mark every factual/legal/market statement in `claims` with `verified: false` and `source: null`. Phrase unverified process points generally ("usually", "check the current requirement").
4. Add `on_screen` text and `visual` note per beat (details by `/create-visual-hook` for beat 1).
5. Run a self-edit pass (see `/content-review`): cut filler, one idea per sentence, no jargon without a plain-words gloss.
6. Save `script` record; set idea `status: scripted`; list claims needing human verification.

## Decision rules
- Max one idea per video. If you need two, split into two ideas.
- Never introduce a legal fee, rate, or deadline unless the user supplied a source; otherwise say "verify current rate".
- Payoff must arrive by ~75% of the runtime so retention holds.

## Quality checks
Word count fits length; first line equals chosen hook; every claim listed; CTA is single and matches config options; no banned phrases.

## Output
Beat table + clean read-aloud version + claims-to-verify list.

## Failure handling
Missing facts → write the script with explicit `[VERIFY: ...]` placeholders rather than guessing.

## Human approval points
User must verify claims and approve the script before it's marked ready to film.

## Tool assumptions
Text only.
