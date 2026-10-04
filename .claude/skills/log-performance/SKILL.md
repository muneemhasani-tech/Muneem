---
name: log-performance
description: Record published-post performance (views, retention, shares, saves, follows, enquiries) into content-engine/data/performance.csv from pasted numbers or a connected analytics source. Use when the user reports results, 24h/72h/7d after publishing, or exports insights.
---

# log-performance

## Purpose
Create the clean dataset the feedback loop depends on.

## Inputs
Pasted metrics/screenshots-as-text, CSV export, or Supermetrics `instagram_insights` results (only if the account is verified linked). Idea id + post URL. Columns defined in `content-engine/schemas/schemas.md`.

## Workflow
1. Identify the idea/post. If unmatched, create a row with `idea_id` blank and ask.
2. Write values exactly as given. Empty = not available; never fill 0 or estimate.
3. Record `data_source` (`manual` or `mcp:<name>`) and snapshot age (add to `notes`: "24h", "7d").
4. Append a new row for each new snapshot; don't overwrite older snapshots.
5. Update idea `status: published` → `analyzed` only after `/analyze-performance`.
6. Ask the user for enquiries/qualified leads (human-entered) — the metric that matters most.

## Decision rules
- Data from a tool must come from an actual call in this session; otherwise mark `manual`.
- Retention fields only from platform analytics, never inferred.

## Quality checks
Numbers match source; units consistent (percentages as 0–100); dates ISO.

## Output
Appended CSV rows + one-line confirmation of what was logged and what's missing.

## Failure handling
Ambiguous metric names → ask. Private/unavailable data → leave blank and note.

## Human approval points
Writing to external systems: none (local file only). Pulling analytics via MCP requires the user's linked account and consent.

## Tool assumptions
Files; optional Supermetrics MCP. No scraping of private analytics.
