# Amplivo Clips — Subsidiary MVP

Autonomous **marketplace clipper** under Amplivo.  
Primary mode: earn on Whop / Clipt / GetClipped campaigns.  
No streamer cold-outreach in v1.

## North star

Agent pipeline turns campaign sources into posted short-form clips and payout proofs — with minimal human QA.

## v1 scope (build)

1. Ingest campaigns (manual API + stub scanner + GUI seed)
2. Produce clips via OpusClip API (dry-run if no key)
3. Quality gate (LLM score hook / length / brand-safety)
4. Record post + proof URL for marketplace submit
5. n8n hourly drain (`/clips/drain`) for produce + auto-submit
6. GUI at `/dashboard/clips` for ops (seed, drain, submit, mark paid)

## Agent-automatable now

| Action | Endpoint / UI |
|--------|----------------|
| Seed demo campaigns | `POST /clips/campaigns/seed` or GUI button |
| Ingest campaign | `POST /clips/campaigns` or GUI form |
| Produce + QA | `POST /clips/jobs/run` (skips campaigns with active jobs) |
| Poll Opus producing | `POST /clips/jobs/poll` |
| Full cycle | `POST /clips/drain` or GUI **Run Drain** |
| Auto-submit ready | dry-run only (`force=true` to override) |
| Mark paid | `POST /clips/jobs/{id}/paid` or GUI |
| Overview | `GET /clips/overview` |

Guards: max 1 blocking job per campaign; `clips_max_jobs_per_run` from settings; fake proof auto-submit only when `clips_dry_run=true`.

## Still human / later

- Marketplace browser login + campaign scrape
- Real TikTok/IG posting (not proof stub)
- Payout reconciliation from marketplace wallets

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
