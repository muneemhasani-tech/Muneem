---
name: analyze-hooks
description: Break down the verbal, written, and visual hooks of viral/outlier videos into reusable mechanisms and patterns. Use when the user shares a viral video transcript/description, after /find-outliers, or asks "why did this hook work".
---

# analyze-hooks

## Purpose
Extract transferable hook mechanics (not wording) from successful examples so `/generate-hooks` can apply them to new topics.

## Inputs
`viral_example` records or pasted transcript + description of the first 3s visuals and on-screen text. If only a link is given and no content is retrievable, ask for the transcript/description — do not guess what the video contains.

## Workflow
For each example, document three layers:
1. **Verbal**: exact first line; mechanism (`open_loop | contrarian | specific_number | warning | identity_call_out | story_cold_open | demonstration`); word count; what question it plants.
2. **Written**: on-screen text; does it add a second angle or repeat the audio?
3. **Visual**: first frame, motion in 0–2s, pattern interrupts, what the eye is asked to do.
Then: the *gap* (what the viewer wants resolved), the *stake* (why care), and the *payoff timing*.
Across examples: tally mechanisms and note combinations that recur.
Write a "pattern card": mechanism + template with blanks + when it fits + risk.

## Decision rules
- Describe what is observable; label inference as inference.
- Reject patterns that depend on misleading claims (clickbait the video can't pay off) — flag, don't copy.
- Patterns must be adapted to the active config's compliance rules (e.g. fear hooks must not accuse named parties).

## Quality checks
Pattern cards have templates a stranger could fill; no verbatim reuse of someone's script beyond a short quoted hook for analysis.

## Output
Per-example breakdown + pattern cards saved to `content-engine/data/outliers/patterns.md` (append). Update `why_it_worked` in the viral_example record.

## Failure handling
Thin input → list what's missing and analyse only what's present, marking LOW confidence.

## Human approval points
None.

## Tool assumptions
Text only. Cannot watch video; relies on supplied transcript/description (or a connected video tool if one exists).
