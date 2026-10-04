---
name: find-outliers
description: Identify outlier (over-performing) short-form posts from data the user supplies or a connected source, compute outlier ratios, and log them as viral_example records. Use when the user pastes viral links/metrics/transcripts, asks "what's working in real estate reels", or starts weekly research.
---

# find-outliers

## Purpose
Separate genuinely over-performing content from merely big accounts, and store it as structured input for hook analysis and topic generation.

## Reality check (read first)
Claude **cannot browse Instagram/TikTok feeds or see competitor analytics** unless a scraper/MCP/browser tool is actually connected. Check `data_access` in the active config and the tools present in this session. If none: ask the user to paste URL + creator + views + creator's typical views + first 15s transcript. Never fabricate metrics.

## Inputs
- User-pasted items, or results from a connected tool (state which: `data_provenance`).
- Active config (for relevance filtering).

## Workflow
1. Normalise each item into `viral_example` (schemas.md). 
2. Compute `outlier_ratio = views / creator_median_views`. If median unknown → leave null and mark "unrankable"; do not guess.
3. Classify: ≥5× strong outlier, 2–5× mild, <2× not an outlier. Accounts <1k followers with big numbers: flag as possible fluke.
4. Filter for relevance to the config's pillars/audiences; park the rest as "adjacent".
5. Save to `content-engine/data/outliers/<id>.yaml`. Present a ranked table.
6. Offer next step: `/analyze-hooks` on the top items, `/generate-topics`.

## Decision rules
- Ratio beats raw views. A 40k post on a 2k-median account outranks 400k on a 1M-median account.
- Prefer ≥3 outliers sharing a pattern over one standout.

## Quality checks
Every row has provenance; no null ratio presented as ranked; no copying of others' scripts — extract patterns only.

## Output
Ranked table (creator, platform, views, ratio, pattern guess, provenance) + saved records.

## Failure handling
No data → give the exact paste template and stop; do not substitute invented examples.

## Human approval points
None (read-only). Any scraping setup that spends money or needs credentials → ask first.

## Tool assumptions
Files; optional browser/MCP. Own-account metrics: Supermetrics `instagram_insights` only if the account is linked (verify via `accounts_discovery`).
