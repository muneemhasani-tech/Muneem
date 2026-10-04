---
name: content-calendar
description: Build a weekly/monthly short-form content calendar from scored ideas, balancing pillars, audiences, areas, formats, and filming batches. Use when planning the week/month or asked "what should I post when". For daily pace tracking the mrre-daily-ops-tracker skill also exists.
---

# content-calendar

## Purpose
Schedule approved/high-scoring ideas into a realistic posting plan with batch-filming days.

## Inputs
Scored ideas (`status: scored|reviewed|approved`), config (platforms, pillars), user's posting cadence and available filming days, `performance.csv` (best times/formats if available).

## Workflow
1. Ask or assume cadence (default: 5 posts/week). State assumption.
2. Select ideas: score ≥70 first; reviewed ones before unreviewed.
3. Balance: max 2 posts per pillar per week, mix audiences (local/NRB/seller), vary formats, no two same-area posts back-to-back.
4. Assign publishing slots; use measured best times only if data exists, else label "test slot".
5. Group into 1–2 filming batches; add editing and verification deadlines BEFORE film day (claims need time).
6. Write `content-engine/data/calendar-YYYY-WW.md`; include 1 flex slot for reactive content.

## Decision rules
- Unverified claims push an idea out of the near term.
- Don't schedule more than the user can film; fewer strong posts beat many weak ones.

## Quality checks
Every slot has idea id, format, filming batch, verification owner/date.

## Output
Calendar table + batch-film plan + backlog.

## Failure handling
No scored ideas → run `/generate-topics` and `/score-content` first (suggest, don't auto-run unasked outside /content-engine).

## Human approval points
User confirms schedule. Calendar invites/reminders in external systems (Google Calendar etc.) are created only on explicit request.

## Tool assumptions
Files. Google Calendar MCP optional and only with approval.
