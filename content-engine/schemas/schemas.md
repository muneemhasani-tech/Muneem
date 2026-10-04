# Shared data schemas

Skills hand work to each other as YAML files. Every record has `id` and `schema` so skills can
validate what they receive. Files live in `content-engine/data/`. IDs: `idea-YYYYMMDD-NN`.
Fields marked `# human` are never filled by Claude from imagination: leave `null` until supplied.

## content_idea  (data/ideas/<id>.yaml) — the spine; all other records attach to it
```yaml
schema: content_idea/1
id: idea-20261004-01
status: idea            # idea | scored | scripted | reviewed | approved | filmed | published | analyzed | killed
created: 2026-10-04
pillar: due_diligence
audience: local_buyer
area: Bashundhara       # or null
topic: "What to check in a plot's mutation record before paying a booking amount"
angle: "The one document sellers hope you skip"
source: { type: user_supplied, ref: null, research_id: null }
outlier_refs: []        # ids of viral_example records that inspired this
hook_ids: []
format: null            # see content_format
script_id: null
visual_hook_id: null
cta_id: null
score_id: null
claims_needing_verification: []   # list of strings; blocks approval until cleared
approvals: { script: null, publish: null }   # human: {by, date}
```

## viral_example  (data/outliers/<id>.yaml)
```yaml
schema: viral_example/1
id: viral-001
platform: instagram
url: "<user supplied>"
creator: "<handle>"
creator_median_views: null   # human/supplied — needed to call it an outlier
views: null
outlier_ratio: null          # views / creator_median_views; null if median unknown
posted: null
transcript: "<first 15s verbatim, user supplied>"
data_provenance: user_pasted # user_pasted | mcp:<name> | estimated
why_it_worked: []            # filled by analyze-hooks
```

## hook  (embedded in data/scripts/<id>.yaml or standalone)
```yaml
schema: hook/1
id: hook-01
verbal: "Most buyers in Bashundhara never check this one record."   # first spoken line, <=12 words ideal
written: "BEFORE you pay booking money"                              # on-screen text, <=7 words
visual_ref: visual-01
mechanism: open_loop          # open_loop | contrarian | specific_number | warning | identity_call_out | story_cold_open | demonstration
curiosity_gap: "Which record? what happens if skipped?"
payoff_at_second: 18
```

## visual_hook  (data/scripts/<id>.yaml)
```yaml
schema: visual_hook/1
id: visual-01
shot: "Hand slides a folder across a desk; close-up on the highlighted line"
first_frame: "Highlighted line on a document (no real client data)"
motion: "Zoom to highlight within 1s"
pattern_interrupt_at: [3, 8, 15]
props: [mock document]
location: office
production_difficulty: 2     # 1 easy – 5 hard
```

## content_format
```yaml
schema: content_format/1
type: tutorial   # tutorial | comparison | myth_bust | dos_vs_donts | tip_hack | transformation | challenge | story | talking_head_educational | list | walkthrough | case_study | q_and_a
length_seconds: 40
platform_targets: [instagram_reel, youtube_short]
reason: "Process explanation needs authority + clarity; no location access needed"
```

## script  (data/scripts/<id>.yaml)
```yaml
schema: script/1
id: script-20261004-01
idea_id: idea-20261004-01
language: Banglish
hook_id: hook-01
beats:
  - { t: "0-3",  type: hook,    spoken: "...", on_screen: "...", visual: "..." }
  - { t: "3-10", type: context, spoken: "...", on_screen: "...", visual: "..." }
  - { t: "10-35", type: payoff, spoken: "...", on_screen: "...", visual: "..." }
  - { t: "35-40", type: cta,    spoken: "...", on_screen: "...", visual: "..." }
word_count: 95
claims: [{ text: "...", verified: false, source: null }]   # human verifies
```

## audience  (content-engine/config/*.yaml → audiences[])  — see mra-real-estate.yaml
## cta
```yaml
schema: cta/1
id: cta-01
type: whatsapp_keyword
spoken: "Comment MUTATION and I'll send the checklist."
on_screen: "Comment MUTATION"
friction: low        # low | medium | high
funnel_stage: top    # top | middle | bottom
fulfilment_ready: false   # human: is the checklist/lead magnet actually ready?
```

## content_score  (data/ideas/<id>.score.yaml) — see score-content skill for rubric
```yaml
schema: content_score/1
idea_id: idea-20261004-01
total: 78
dimensions: { topic_strength: 7, outlier_potential: 5, verbal_hook: 8, ... }
caps_applied: []
verdict: revise      # ship | revise | rework | kill
top_fixes: ["Make the verbal hook name the area", "Add pattern interrupt at 12s"]
confidence: medium   # low if no real data behind outlier_potential
```

## performance_result  (data/performance.csv — one row per post)
Columns: `idea_id,platform,post_url,posted_date,hook_id,format,length_s,views,reach,avg_watch_s,avg_pct_viewed,
retention_3s_pct,completion_pct,likes,comments,shares,saves,follows,profile_visits,link_clicks_or_ctr,
enquiries,qualified_leads,data_source,notes`
Rules: empty cell = not available (never 0 unless truly zero). `data_source` = `manual` or `mcp:<name>`.
`enquiries`/`qualified_leads` are human-entered from WhatsApp/DMs.

## content_experiment  (data/experiments.yaml)
```yaml
schema: content_experiment/1
id: exp-001
hypothesis: "Naming the area in the verbal hook raises 3s retention"
variable: hook.verbal_has_area
control_ids: [idea-...]
test_ids: [idea-...]
min_posts_per_arm: 5
metric: retention_3s_pct
status: running     # planned | running | concluded
result: null
decision: null      # adopt | reject | inconclusive
```
