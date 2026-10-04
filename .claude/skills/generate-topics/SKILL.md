---
name: generate-topics
description: Generate and prioritise short-form content topics/angles from the business config pillars, audience pains, outlier patterns, and past performance. Use for weekly planning, when the user asks for content ideas, or at the start of /content-engine. For keyword-first research for the website, prefer the mrre-topic-keyword-research skill.
---

# generate-topics

## Purpose
Produce a pool of specific, differentiated `content_idea` records (topic + angle + audience + area), not generic subjects.

## Inputs
- Active config (pillars, audiences, areas, compliance).
- Optional: outlier records/pattern cards, `performance.csv` winners, existing ideas (to avoid repeats), user's raw notes or FAQs from clients.
- Count requested (default 10).

## Workflow
1. Load config and existing ideas (`content-engine/data/ideas/`). Build a "recently covered" list.
2. For each pillar, combine audience pain × area × pattern card to produce candidate angles. Prefer concrete situations ("a plot in Purbachal with two mutation records") over categories ("land buying tips").
3. Dedupe against existing ideas by topic+area.
4. For every idea fill `claims_needing_verification` with any legal/financial/market claim it implies.
5. Rough-rank by relevance, novelty, and production ease (do **not** present as the final score — `/score-content` does that).
6. Save each as `content_idea` YAML, `status: idea`.

## Decision rules
- Spread across ≥4 pillars; no more than 30% from one pillar.
- Market-intelligence ideas need a named, citable source supplied by the user; otherwise mark "needs data" and don't present figures.
- Scam ideas: pattern + verification step only (see compliance).

## Quality checks
Each idea names audience, pain, angle. No idea is just a keyword. No fabricated statistics.

## Output
Table (id, pillar, audience, area, angle, claims to verify) + saved files.

## Failure handling
Missing config → ask. Not enough inputs → generate from pillars and say outlier/performance data was unavailable.

## Human approval points
User picks which ideas proceed. Nothing auto-advances to scripting beyond what the user selected.

## Tool assumptions
Files only; no live trend data unless supplied.
