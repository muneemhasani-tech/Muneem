---
name: publish-prep
description: Prepare the final publishing package (caption, hashtags, SEO title, cover text, keyword CTA setup, disclaimer, pre-publish checklist) for an approved video. Never publishes. Use when the user is ready to post.
disable-model-invocation: true
---

# publish-prep

## Purpose
Produce everything needed to post manually in one pass, and verify nothing blocks publication.

## Inputs
Approved script, reviewed status, CTA, platform list, config (voice, compliance, site, banned phrases).

## Workflow
1. **Gate**: confirm idea `approvals.script` is set by a human and `claims_needing_verification` is empty/verified. If not, stop and list blockers.
2. Per platform write: caption (first line = hook keyword for search), hashtags (≤5 targeted: area + topic + audience), title (YouTube/blog) with the primary keyword first, cover text, alt text.
3. Add the disclaimer line if config requires; add CTA keyword and confirm fulfilment is ready.
4. Pre-publish checklist: captions burned/checked, cover frame, no real client data visible, links/UTM work, WhatsApp keyword automation tested (human), comment-reply plan for the first hour.
5. Save to `content-engine/data/scripts/<script-id>.publish.md`.

## Decision rules
- No approval on record → no package.
- Do not schedule or post through any API/MCP; this skill only prepares text.

## Quality checks
Caption matches video claims exactly; hashtags relevant not spammy; no banned phrases.

## Output
Per-platform publishing package + checklist + blockers.

## Failure handling
Blockers present → output only the blocker list.

## Human approval points
**Human publishes.** Any future auto-publish integration must ask for per-post approval first.

## Tool assumptions
Text only; manual-invocation skill (`disable-model-invocation`) so it never runs automatically.
