---
name: production-brief
description: Turn an approved script into a one-page filming and editing brief — shot list, locations, props, on-screen text, B-roll, captions, music/sound notes, and an edit checklist. Use when a script is approved and the user is about to film or hand off to an editor. For retention-graph editing passes the mrre-retention-edit-checklist skill also exists.
---

# production-brief

## Purpose
Remove ambiguity between script and finished video so filming/editing is a single efficient session.

## Inputs
Reviewed script, `visual_hook`, `content_format`, `cta`; user's setup (phone, mic, location, editor app).

## Workflow
1. Check idea status is `reviewed`/`approved`; if claims are unverified, stop and list them.
2. Build shot list from beats: shot #, beat time, framing, action, spoken line, on-screen text, B-roll needed.
3. Group shots by location/setup for batch filming. List props and mock documents to prepare (redacted/mock only).
4. Edit instructions: cut cadence, captions style, text timings, hook-frame/cover, sound, end card (+ "general information, not legal advice" line when required by config).
5. Delivery spec: aspect 9:16, safe zones, length, file naming `idea-id_platform_v1`.
6. Save to `content-engine/data/scripts/<script-id>.brief.md`.

## Decision rules
- Batch by setup, not by script order.
- Anything requiring permits, third-party property, or people's faces → flagged "needs consent/permission".

## Quality checks
Every spoken line maps to a shot; every on-screen text has a timestamp; difficulty matches `visual_hook`.

## Output
Markdown brief (shot table, prop list, edit checklist, delivery spec).

## Failure handling
Unknown editor/tools → write tool-agnostic instructions.

## Human approval points
Human films and approves final cut. Claude cannot film, edit footage, or export.

## Tool assumptions
Text only.
