# Content Engine (MRA Real Estate first, reusable for any business)

A modular set of Claude Code skills for short-form content: research → ideas → hooks → script → score → review → production → publish prep → performance feedback.

> **Source:** built from the "100K Organic Short Form Content Strategy" screenshot (10 sections: viral hooks/topics; verbal, written and visual outlier hooks; 7 formats; storytelling and educational scripts; Hemingway edit; two unreadable rows; profile). Sections 8–9 were unreadable in the image and are not modelled — see their entries in the final report.

## Layout
```
.claude/skills/            18 skills (generic — no MRA specifics)
content-engine/
  config/active.yaml       which business config is loaded
  config/mra-real-estate.yaml   MRA audiences, pillars, voice, compliance, what data is actually connected
  config/learned-rules.md  rules proposed by /analyze-performance, human-approved
  schemas/schemas.md       shared YAML/CSV record shapes
  data/                    ideas/, scripts/, outliers/, performance.csv, experiments.yaml
  examples/                illustrative records
  scripts/validate_skills.py   checks frontmatter, sections, references
```
Reuse for another business: copy `mra-real-estate.yaml`, edit, point `active.yaml` at it.

## Skills
| Layer | Skill | Claude alone? | Needs |
|---|---|---|---|
| Orchestrator | `/content-engine` | yes | chains the rest; stops at approval gates |
| Intelligence | `/find-outliers` | only with supplied data | pasted metrics or a connected tool |
| | `/analyze-hooks` | yes (given transcript) | transcript/description |
| | `/generate-topics` | yes | config |
| | `/analyze-performance` | yes | logged data (≥10 posts for rules) |
| | `/log-performance` | yes | pasted metrics or Supermetrics (own account only) |
| Creative | `/generate-hooks` `/select-format` `/write-script` `/create-visual-hook` `/create-cta` | yes | human verifies claims |
| | `/score-content` | yes | heuristic until calibrated |
| Production | `/content-review` `/production-brief` `/repurpose-content` `/content-calendar` | yes | human decisions |
| | `/publish-prep` | yes (prepares text only) | human publishes |

## What is NOT connected
No scraper for competitor/viral data, no TikTok/YouTube analytics, no publishing API. Claude cannot see private analytics. Skills ask for pasted data rather than inventing it. Filming, on-camera delivery, legal verification, and publishing are human.

## Typical sequences
- Weekly ideas: `/content-engine create 10 content opportunities this week` → pick → `/generate-hooks`
- One video: `/generate-hooks` → `/select-format` → `/write-script` → `/create-visual-hook` → `/create-cta` → `/score-content` → `/content-review` → *(you verify + approve)* → `/production-brief` → *(film)* → `/publish-prep` → *(you post)*
- Feedback: `/log-performance` (24h/7d) → `/analyze-performance` weekly

## Existing account skills these complement
`mrre-topic-keyword-research`, `mrre-video-hook-writer`, `mrre-humps-script-writer`, `mrre-retention-edit-checklist`, `mrre-blog-flywheel`, `mrre-daily-ops-tracker`.

## Validate
`python3 content-engine/scripts/validate_skills.py`

## Roadmap
1. (now) File-based skills above.
2. Connect own-account analytics (Supermetrics Instagram) and verify with `accounts_discovery`.
3. Add a viral-data source (scraper/MCP) — needs your approval, credentials, and likely cost.
4. Social listening / trend and keyword tools; A/B experiment registry in use.
5. Optional: publishing integration with per-post approval.
