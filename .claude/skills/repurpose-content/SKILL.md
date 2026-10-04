---
name: repurpose-content
description: Adapt a finished (or approved) short-form script into other formats and platforms — alternate cuts, carousel, X/LinkedIn post, blog outline, WhatsApp snippet, Stories — and recycle proven winners later with a fresh hook. Use after a script is approved or a post performed well. For full SEO blog articles the mrre-blog-flywheel skill is the specialised option.
---

# repurpose-content

## Purpose
Get several assets from one researched idea without duplicating effort or spamming the same content.

## Inputs
Approved `script` + `idea`, target platforms from config, performance data if recycling a winner.

## Workflow
1. Pick targets (default: 1 alternate hook cut, 1 carousel outline, 1 LinkedIn/Facebook text post, 1 blog outline, 1 story sequence).
2. Adapt per platform: LinkedIn → investor/NRB framing, longer, no hype; carousel → one point per slide, save-worthy; blog → hand off to `mrre-blog-flywheel` with topic + keyword + transcript.
3. For recycling: keep the proven topic, change the hook mechanism and first frame; wait ≥60 days or note the audience overlap.
4. Carry over claims list and verification status; unverified stays unverified.
5. Save as children of the idea (`data/ideas/<id>.repurpose.md`).

## Decision rules
- Never duplicate the same video verbatim to the same platform.
- Do not add new factual claims during repurposing.

## Quality checks
Each asset stands alone; CTA adapted per platform; compliance rules re-applied.

## Output
List of derived assets with drafts and platform notes.

## Failure handling
Script not approved → proceed only as drafts labelled "pre-approval".

## Human approval points
Human approves before any post/publish; Claude does not post.

## Tool assumptions
Text only.
