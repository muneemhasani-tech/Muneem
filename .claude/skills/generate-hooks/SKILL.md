---
name: generate-hooks
description: Generate multiple verbal and written hook options (with mechanism labels) for a content idea, using pattern cards and the business voice. Use when an idea needs an opening line, "give me hooks for X", or after /generate-topics. For a full hook + publishing-text package for the website flywheel, the mrre-video-hook-writer skill also exists.
---

# generate-hooks

## Purpose
Create 8–12 distinct hook candidates (verbal + matching written hook) for one idea, so the best can be chosen and scored.

## Inputs
`content_idea` (topic, angle, audience, area); pattern cards from `content-engine/data/outliers/patterns.md` if present; active config voice, languages, banned phrases, compliance.

## Workflow
1. Identify the single tension in the topic (the thing the viewer fears, wants, or misbelieves).
2. Write ≥2 hooks for each of: open_loop, contrarian, specific_number, warning, identity_call_out, story_cold_open.
3. Each hook: verbal line (≤12 words preferred, spoken-natural, in the configured language), written hook (≤7 words, adds a second angle), mechanism, curiosity gap, payoff second.
4. Delete hooks that: can't be paid off in the video; use banned phrases; accuse named parties; state unsourced legal figures.
5. Recommend top 3 with reasoning; mark which pair best with a strong visual (hand off to `/create-visual-hook`).
6. Save as `hook` records attached to the idea (`hook_ids`).

## Decision rules
- Name the area/audience in at least half the hooks.
- Gap must be honest: the answer must exist in the script.
- Read each aloud mentally: if it sounds written rather than spoken, rewrite.

## Quality checks
Variety across mechanisms; zero hooks start with filler ("So,", "Hey guys"); every hook has a payoff plan.

## Output
Table (id, verbal, written, mechanism, gap) + top-3 recommendation.

## Failure handling
Weak idea (no tension found) → say so and return it to `/generate-topics` with a suggested sharper angle instead of padding with generic hooks.

## Human approval points
User chooses the hook; Claude does not lock one in without a choice unless running inside `/content-engine` with "auto-pick" explicitly requested (still flagged as a proposal).

## Tool assumptions
Text only.
