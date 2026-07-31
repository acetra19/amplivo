# Amplivo Clips — Subsidiary MVP

Autonomous **marketplace clipper** under Amplivo.  
Primary mode: earn on Whop / Clipt / GetClipped campaigns.  
No streamer cold-outreach in v1.

## North star

Agent pipeline turns campaign sources into posted short-form clips and payout proofs — with minimal human QA.

## v1 scope (build)

1. Ingest campaigns (manual API + stub scanner)
2. Produce clips via OpusClip API (dry-run if no key)
3. Quality gate (LLM score hook / length / brand-safety)
4. Record post + proof URL for marketplace submit
5. n8n hourly tick for due jobs

## Out of scope (v1)

- Streamer sales / retainers
- TikTok account farming at scale
- Full browser login automation for every marketplace
- Replacing Amplivo affiliate ops

## Agent map

| Agent | Job |
|-------|-----|
| Campaign Scanner | Pull / normalize open campaigns |
| Clip Producer | Source URL → OpusClip → clip assets |
| Quality Gate | Accept / reject before post |
| Poster | Publish or attach external post URL |
| Ops | Stats + payout tracking |

## Money model (v1)

Worker CPM / per-clip approve on marketplaces. Amplivo Clips is the operating company; Amplivo remains the parent sales stack.

## Env keys

```
OPUSCLIP_API_KEY=
CLIPS_DRY_RUN=true
CLIPS_DEFAULT_MARKETPLACE=whop
CLIPS_MAX_JOBS_PER_RUN=5
```
