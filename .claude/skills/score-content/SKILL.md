---
name: score-content
description: Score a short-form content idea or script on a 100-point rubric (hooks, curiosity, relevance, retention, shareability, saves, CTA, production ease) with explained reasons, caps, and top fixes. Use after hooks/scripts exist, when asked "is this good", "rank these ideas", or before approving content for production.
---

# score-content

## Purpose
Turn a content idea/script into a repeatable 0–100 score with reasons, so ideas can be ranked and weak ones fixed or killed before filming.

## Inputs
- A `content_idea` (and ideally its hooks, script, visual hook, CTA) — see `content-engine/schemas/schemas.md`; or pasted text.
- Business config from `content-engine/config/active.yaml` → `active_config`.
- Optional: `viral_example` records and past `performance.csv` (strengthens outlier/novelty scoring).

## Rubric (100 points)
| Dimension | Max | What earns the points |
|---|---|---|
| Topic strength | 8 | Maps to a pillar; real problem/desire; has an angle, not just a subject |
| Outlier potential | 10 | Evidence similar angles beat creators' medians (needs data; else score ≤5 and mark low confidence) |
| Verbal hook | 10 | First spoken line ≤12 words, specific, creates a gap or tension within 3s |
| Written hook | 6 | On-screen text ≤7 words, complements (not repeats) the verbal hook |
| Visual hook | 10 | First frame is arresting/clear; motion or pattern interrupt in first 2s |
| Curiosity | 8 | Open loop that is paid off; payoff is not the first line |
| Audience relevance | 10 | Named audience + named pain/area; viewer thinks "that's me" |
| Novelty | 5 | Fresh angle vs. recent own posts and viral examples |
| Retention potential | 8 | Tight length, a change every 2–4s, no dead intro, payoff timed late |
| Shareability | 6 | Viewer would send it to a specific person ("send to your brother buying a plot") |
| Save potential | 5 | Contains a checklist/steps/reference worth returning to |
| CTA strength | 5 | One ask, low friction, matches funnel stage, fulfilment is ready |
| Production ease | 9 | 9 = phone + desk, 1 location; 1 = travel, crew, permits (higher = easier) |

Total = sum of dimension scores. Hook block (verbal + written + visual) = 26 pts.

## Workflow
1. Load the idea + linked records. Note what is MISSING (no script → can't score retention/CTA; score those at 50% and list as "unscored — assumed").
2. Score each dimension with an integer and a one-line reason quoting the actual text.
3. Apply caps (below). 
4. Verdict: **85+ ship**, **70–84 revise**, **55–69 rework**, **<55 kill/park**.
5. List the 3 highest-leverage fixes (points gained per effort).
6. Write `content_score` YAML next to the idea; set idea `status: scored`.

## Decision rules / caps
- Any hook dimension (verbal, written, visual) below 50% of its max → total capped at 69.
- Compliance violation per config `compliance` (unsourced legal figure, return promise, accusation) → verdict `rework` regardless of total; list the line.
- No evidence for outlier potential → max 5/10 and `confidence: low`. Never invent view counts or "proven" claims.
- Production ease 1–3 on an otherwise 85+ idea → flag "batch-film only".

## Quality checks
- Every score has a reason that quotes the draft; no dimension scored on vibes.
- Totals add up. Caps stated explicitly.
- Confidence is `low` if >2 dimensions were assumed.

## Output
Markdown table (dimension | score/max | reason) + total, verdict, caps, top 3 fixes, plus saved `content_score` YAML.

## Failure handling
Missing config → ask which config to use; do not assume MRA defaults silently. Missing fields → score what exists and say what's assumed.

## Human approval points
None to score. Scoring never approves content — approval is a human step in `/content-review`.

## Tool assumptions
Files only. No API. Do not claim to predict real views; the score is a pre-production quality heuristic until calibrated by `/analyze-performance`.
