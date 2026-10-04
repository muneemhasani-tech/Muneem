---
name: optimize-profile
description: Audit and rewrite a social profile (name field, bio, pinned posts, highlights, link, grid) so a viewer who arrives from a Reel immediately understands who it is for and what to do next. Use when starting an account, when views are high but follows/enquiries are low, or when asked about bio/profile optimization.
---

# optimize-profile

## Purpose
Convert profile visitors into followers and enquiries. The source strategy ends with the profile page (step 10) because every Reel sends viewers there.

## Inputs
Current bio text, name field, link, pinned posts and highlights (pasted or described; Claude cannot see a profile unless a browser tool is connected), active config (audiences, offer, voice, compliance), top-performing posts from `performance.csv` if present.

## Workflow
1. Run the 5-second test: who is this for, what outcome, why trust, what next? Score each as clear/vague/missing.
2. Rewrite: name field with a searchable keyword (e.g. "Dhaka Property Advisor"), 3-line bio (audience + outcome, proof/credibility that is TRUE and documentable, one CTA), link target (WhatsApp or site), 3 pinned posts (best proof, best explainer, best CTA), highlight titles.
3. Grid check: do the last 9 covers tell a consistent story and pillar mix?
4. Provide 2 variants (local buyer vs NRB emphasis) when the config has several audiences.

## Decision rules
- No unverifiable credentials, awards, numbers, or "guaranteed" language. Follower/deal counts only if the user supplies them.
- One CTA in the bio.

## Quality checks
Bio under platform limits; contains audience and outcome; compliance rules from config applied.

## Output
Audit table + rewritten name/bio/link/pins/highlights + grid notes.

## Failure handling
Profile not visible → ask for pasted bio and a description of pins/grid.

## Human approval points
Human edits the live profile. Claude does not change accounts.

## Tool assumptions
Text only; optional browser tool for viewing a public profile if connected.
