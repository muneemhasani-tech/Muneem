---
name: content-engine
description: Master orchestrator for short-form content. Takes a request like "create 10 content opportunities for MRA Real Estate this week" and chains the right skills (research, topics, hooks, format, script, visual hook, CTA, score, review, production, repurpose, publish-prep) with approval checkpoints. Use for any multi-step content request.
---

# content-engine

## Purpose
Route a content request through the smallest set of skills that satisfies it, passing structured records between them, and stop at human gates.

## Inputs
A natural-language request; active config via `content-engine/config/active.yaml`. Optional: pasted viral examples, performance data.

## Workflow
1. **Read context**: active config, `content-engine/data/` state (ideas by status, performance rows).
2. **Plan** — state the chain you will run and why, as a short list, before running. Choose by request:
   - "ideas / opportunities" → `find-outliers` (only if data supplied) → `generate-topics` → `score-content` (rough) → present ranked list. **STOP for user selection.**
   - "make this into a video" → `generate-hooks` → (user picks) → `select-format` → `write-script` → `create-visual-hook` → `create-cta` → `score-content` → `content-review`. **STOP for human approval.**
   - "plan the week" → `content-calendar` (needs scored ideas).
   - "prep to post" → `publish-prep` (manual invoke; requires approvals).
   - "what's working" → `log-performance` → `analyze-performance`.
   - "profile / bio / grid" → `optimize-profile`.
   - "repurpose" → `repurpose-content`.
3. **Run skills in order**, each reading prior records; update idea `status` after each stage.
4. **Report**: what ran, what was skipped and why, files written, open human tasks.

## Approval checkpoints (hard stops)
Stop and ask before: publishing/scheduling anything; sending any message (email, WhatsApp, DM, comments); modifying external systems (calendar, drive, CMS, analytics config); spending money (ads, paid tools, API credits); deleting or overwriting data (idea files, performance rows); installing MCPs/tools; marking scripts `approved`; naming any real person/company as a fraud/scam.

## Decision rules
- Do the minimum chain. Don't run all stages when the user asked for ideas.
- Capability honesty: before using live-data skills, check what's connected. If not, say "not connected" and ask for pasted data. Never simulate data.
- Missing config → ask which business; don't default silently.
- Any claim on law/tax/market → goes to `claims_needing_verification`; blocks approval.

## Quality checks
Every produced idea has a record file; chain ended at a gate or completed; no unverified claim presented as fact; no skill was skipped silently.

## Output
Summary table (idea id, status, score, next human action) + file list + open approvals.

## Failure handling
If a skill stage fails or lacks input: stop the chain for that idea, report the exact missing input, continue other ideas.

## Human approval points
See hard stops above. Humans always: verify legal facts, film, approve the script, publish.

## Tool assumptions
Files + the skills in `.claude/skills/`. Optional existing skills for MRA: `mrre-topic-keyword-research`, `mrre-video-hook-writer`, `mrre-humps-script-writer`, `mrre-retention-edit-checklist`, `mrre-blog-flywheel`, `mrre-daily-ops-tracker` (use them when the user wants the MRA-specific website/HUMPS flywheel). No publishing integration exists.
