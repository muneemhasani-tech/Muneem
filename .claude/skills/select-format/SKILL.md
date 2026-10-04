---
name: select-format
description: Choose the best short-form video format (talking head educational, story, list, myth-vs-fact, walkthrough, case study, split comparison, Q&A) and length for an idea given constraints. Use after a hook is chosen and before scripting.
---

# select-format

## Purpose
Match the idea to a format that fits its content type, the creator's real production capacity, and the platform.

## Inputs
`content_idea`, chosen hook, active config (platforms, length ranges), production constraints from the user (location access, time, who appears on camera).

## Workflow
1. Classify the idea's content type: process, warning, story, comparison, explainer, proof/case, Q&A.
2. Map (the seven formats from the source strategy first): process→`tutorial` or `walkthrough`; warning→`myth_bust` or `dos_vs_donts`; comparison→`comparison`; quick insight→`tip_hack`; before/after→`transformation` (needs real consented case; use anonymised/mock for property); engagement→`challenge`; narrative→`story`; proof→`case_study`; community question→`q_and_a`. Also available: `talking_head_educational`, `list`.
3. Pick the primary format + one alternative. State length target within config range.
4. Check feasibility: if the best format needs a site visit/crew the user hasn't confirmed, downgrade to the nearest feasible format and note the trade-off.
5. Write a `content_format` record onto the idea.

## Decision rules
- Default to the cheapest format that keeps the hook's promise.
- Case studies/real sites require human consent and approval — flag, don't assume.
- One idea → one format per video; use `/repurpose-content` for variants.

## Quality checks
Reason given in one sentence; length inside config range; feasibility stated.

## Output
Chosen format, alternative, length, reason, constraints.

## Failure handling
Unknown constraints → state the assumption (phone, single location, creator on camera) and proceed.

## Human approval points
User confirms format if it requires filming off-site or showing real property/clients.

## Tool assumptions
None.
