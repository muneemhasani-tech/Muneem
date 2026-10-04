---
name: analyze-performance
description: Analyse logged performance to find which hooks, formats, pillars, areas, and lengths win; propose rule updates and next experiments. Use weekly/monthly or when asked "what's working", "why did this flop".
---

# analyze-performance

## Purpose
Close the loop: turn results into evidence-based changes to the content rules and idea pipeline.

## Inputs
`content-engine/data/performance.csv`, linked ideas/hooks/scripts/scores, `content-engine/data/experiments.yaml`.

## Workflow
1. Check sample size. Under ~10 posts: report observations only, label "anecdotal"; no rule changes.
2. Compute per post: engagement rate, share rate, save rate, follow rate, enquiries per 1k views. Rank by **enquiries and saves/shares first**, views second.
3. Group by hook mechanism, format, pillar, area, length, CTA type, visual difficulty. Compare medians (not means).
4. Diagnose flops: low 3s retention → hook/visual; high 3s but low completion → pacing/payoff; high views, low enquiries → CTA/audience mismatch.
5. Compare to `content_score` totals: did high scores perform? Report correlation honestly (small N = weak).
6. Output: top 3 winning characteristics, top 3 losers, proposed rule changes (as a diff to `content-engine/config/learned-rules.md`), and 1–2 `content_experiment` proposals.

## Decision rules
- Never declare a winner from a single post or a viral fluke; require repetition (≥3 posts) before a rule.
- Don't change `compliance` rules from performance data.
- Rules are appended with date + evidence + confidence.

## Quality checks
Every claim cites rows; missing metrics acknowledged; no causal language without an experiment.

## Output
Analysis report + proposed rule diff + experiment proposals.

## Failure handling
Too little data → say what to log next and stop.

## Human approval points
Human approves any change written to `learned-rules.md` and any experiment launch.

## Tool assumptions
Files; arithmetic can be done with a small script if needed.
