---
name: create-cta
description: Create a single, low-friction call to action (spoken, on-screen, caption) matched to funnel stage and an actually-ready lead magnet or next step. Use when finishing a script or when CTAs are weak/missing.
---

# create-cta

## Purpose
Convert attention into one measurable action without breaking trust.

## Inputs
Script/idea, funnel stage (top/middle/bottom), config `cta_options`, what the user can actually fulfil (checklist ready? WhatsApp monitored? consult slots?).

## Workflow
1. Ask or infer the stage: top = save/follow/share; middle = keyword for checklist; bottom = consult.
2. Check fulfilment: if the user hasn't confirmed the lead magnet/WhatsApp flow exists, set `fulfilment_ready: false` and recommend a save/share CTA or flag that a keyword CTA can't launch yet.
3. Write 3 variants (spoken ≤10 words, on-screen ≤4 words, caption line). Pick one.
4. Ensure it follows the payoff, not before it, and relates to the video's promise.
5. Save a `cta` record.

## Decision rules
- One ask only. Never stack "follow, like, comment, DM".
- Do not promise outcomes ("we'll make you rich"). Do not request personal documents in comments.
- Keyword CTAs: keyword is one word, unique per video, so enquiries are attributable.

## Quality checks
Single action; matches stage; fulfilment status explicit; attribution keyword defined.

## Output
Chosen CTA + 2 alternatives + fulfilment note.

## Failure handling
No config CTA options → propose from generic types and label as unconfigured.

## Human approval points
User confirms lead magnet / WhatsApp automation exists before a keyword CTA is published. Setting up automations (e.g. ManyChat) is external and needs the user's go-ahead.

## Tool assumptions
Text only.
