---
name: create-visual-hook
description: Design the first 3 seconds visually — first frame, motion, on-screen text placement, pattern interrupts, props — for a content idea, matched to production capacity. Use after hooks/script exist or when the user asks "what should the opening shot be".
---

# create-visual-hook

## Purpose
Make the first frame stop the scroll and visually reinforce (not duplicate) the verbal hook.

## Inputs
Chosen `hook`, `content_format`, script beat 1–2, production constraints, config (compliance on showing real property/people).

## Workflow
1. Identify the visual proof of the hook's tension (the document, the plot boundary, the price tag, the face reacting).
2. Propose 3 options at different cost levels (1 = desk + phone, 3 = on-location, 5 = crew/drone).
3. For each: first frame, motion within 1s, written-hook placement (top safe zone, large, high contrast), the pattern-interrupt schedule through the video (every 3–5s: cut, zoom, text change, B-roll, prop).
4. Recommend one. Record as `visual_hook` with `production_difficulty`.
5. Add a thumbnail/cover frame suggestion (the frame viewers see on the profile grid).

## Decision rules
- Prefer mock documents/redacted visuals; never show real client data, plot numbers, or faces without consent.
- Written hook should not sit under platform UI (bottom ~20%, right edge).
- If the verbal hook is weak, a strong visual can't save it — say so and loop back to `/generate-hooks`.

## Quality checks
First frame meaningful with sound off; difficulty rating given; interrupts scheduled for the whole runtime.

## Output
Three options table + recommended pick + cover-frame idea.

## Failure handling
Unknown location/props → default to desk + phone options and state assumption.

## Human approval points
User approves any shot involving real property, people, or documents.

## Tool assumptions
Text only. Cannot generate or inspect video/images in this skill.
