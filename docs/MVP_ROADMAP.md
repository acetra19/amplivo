# MVP Roadmap – Agentic Sales Agency

## Overview

12-week plan from zero to first affiliate conversions, then scale toward full autonomy.

---

## Phase 0: Foundation (Week 1) ✅

| Task | Status | Owner |
|------|--------|-------|
| Repo structure + Docker stack | Done | Dev |
| PostgreSQL schema + seed data | Done | Dev |
| Agent skeletons (4 agents) | Done | Dev |
| n8n workflow templates | Done | Dev |
| Sign up GoHighLevel affiliate | **TODO** | You |
| Register sending domain (SPF/DKIM/DMARC) | **TODO** | You |
| Buy domain for landing page | **TODO** | You |
| Deploy VPS production stack | **TODO** | Dev |

**Exit criteria:** `./scripts/deploy-vps.sh` on VPS, `curl https://api.amplivo.net/health` OK.

---

## Phase 1: Lead Pipeline (Week 2–3)

### Week 2 – Data & Outreach Setup

- [ ] Deploy to VPS: `./scripts/deploy-vps.sh`
- [ ] DNS: `api.` + `n8n.` subdomains → VPS IP
- [ ] Import n8n workflows from `n8n/workflows/`
- [ ] Set up Instantly account + 2 campaigns (Sequence A / B)
- [ ] Warm up 2 sending domains (min 14 days – start early!)
- [ ] Connect Apollo or Clay for lead enrichment
- [ ] Define ICP list: 500 agencies (2–50 employees, DACH + US)

**API test:**
```bash
curl -X POST http://localhost:8000/leads \
  -H "Content-Type: application/json" \
  -d '{"email":"test@agency.com","first_name":"Max","company":"Test Agency","industry":"marketing_agency","employee_count":8,"source":"apollo"}'
```

### Week 3 – First Outbound

- [ ] Push 100 leads/day via n8n `new-lead` webhook
- [ ] Monitor reply rate in Instantly dashboard
- [ ] Tune scoring prompts in `agents/outbound_email/agent.py`
- [ ] A/B test subject lines (2 variants)

**KPI targets:**
- Email deliverability > 95%
- Reply rate > 2%
- Bounce rate < 3%

---

## Phase 2: Qualification & Landing (Week 4–5)

### Week 4 – Landing Page + Chat

- [ ] Deploy landing page (Next.js or Carrd)
- [ ] Embed chat widget calling `POST /chat`
- [ ] Add UTM tracking → n8n new-lead webhook
- [ ] Load product knowledge into `knowledge_chunks` (RAG prep)
- [ ] Affiliate disclosure on all pages

### Week 5 – Reply Automation

- [ ] Connect Instantly reply webhook → n8n `email-reply`
- [ ] Auto-classify replies (interested / objection / unsubscribe)
- [ ] Auto-send objection responses (confidence > 0.85)
- [ ] Human review queue for edge cases (Slack)

**KPI targets:**
- Chat → qualified rate > 20%
- Positive reply rate > 0.8% of sent

---

## Phase 3: Conversion Loop (Week 6–8)

### Week 6 – Affiliate Tracking

- [ ] Replace placeholder affiliate URLs in DB seed
- [ ] Set up postback URL → n8n `affiliate-postback`
- [ ] Test trial_start and signup events end-to-end
- [ ] Onboarding email sequence (Resend, 5 emails over 14 days)

### Week 7 – First Conversions

- [ ] Goal: 1 trial start from outbound
- [ ] Daily ops report to Slack (n8n cron workflow)
- [ ] Calculate actual CAC vs commission LTV
- [ ] Pause campaigns with CAC > 30% LTV

### Week 8 – Optimization

- [ ] Review all agent runs in `agent_runs` table
- [ ] Prompt iteration based on lost deals
- [ ] Expand to 200 leads/day if metrics green
- [ ] Add second product (Systeme.io) as nurture downsell

**KPI targets:**
- 3+ trial starts
- 1+ paid conversion
- CAC < $430

---

## Phase 4: Voice Agent (Week 9–10)

### Week 9 – LiveKit Setup

- [ ] Create LiveKit Cloud project
- [ ] Configure Deepgram + ElevenLabs keys
- [ ] Test voice agent locally: `python -m agents.voice_livekit.agent`
- [ ] Build voice queue endpoint (Redis list)

### Week 10 – Voice in Production

- [ ] Auto-call interested email replies within 2 hours
- [ ] Trial day-3 check-in calls (n8n `trial-started` workflow)
- [ ] Log all calls to `interactions` table
- [ ] Measure: call → trial upgrade rate

**KPI targets:**
- 30%+ call connect rate (warm leads)
- Voice-assisted conversion lift > 15%

---

## Phase 5: Scale & Autonomy (Week 11–12+)

### Week 11 – Content Agent

- [ ] SEO comparison pages (GHL vs competitors)
- [ ] Auto-publish 2 articles/week
- [ ] Inbound leads → same n8n pipeline

### Week 12 – Self-Optimization

- [ ] Automated A/B on email subjects (agent picks winner)
- [ ] ICP refinement agent (analyze conversions vs losses)
- [ ] Budget guardrails: auto-pause if daily ROI negative
- [ ] Weekly strategy report (Ops Agent)

**KPI targets (Month 3):**
- 5+ conversions/month
- $2,000+ monthly recurring commission
- 80%+ of pipeline runs without human intervention

---

## Infrastructure Checklist

| Service | Purpose | Est. Cost/mo |
|---------|---------|--------------|
| VPS (existing) | Docker host 24/7 | €0 extra |
| Brevo Free | Outbound email | €0 |
| Anthropic API (Haiku) | LLM agents | $5–15 |
| Domain | Outreach sending | ~€1 |
| Instantly / Apollo / LiveKit | Scale later | defer |
| **Total lean MVP** | | **~$15–35/mo** |

---

## n8n Workflow Import

1. Open `https://n8n.amplivo.net`
2. Settings → Import from File
3. Import each JSON from `n8n/workflows/`
4. Set environment variables in n8n
5. Activate workflows

## Key Endpoints

| Endpoint | Purpose |
|----------|---------|
| `POST /leads` | Create + score lead |
| `POST /chat` | Chat qualifier |
| `POST /webhooks/email-reply` | Classify reply |
| `POST /webhooks/affiliate` | Record conversion |
| `POST /ops/daily-report` | Metrics + AI report |

## Risk Register

| Risk | Mitigation |
|------|------------|
| Email domain burned | 2 domains, slow warmup, < 50 emails/domain/day initially |
| GDPR cold email | B2B only, opt-out honored instantly, document legal basis |
| LLM hallucination in sales | RAG over product docs, confidence thresholds |
| Low conversion | Pivot ICP after 2 weeks of data, not guesses |
| Affiliate program rejection | Apply early, have landing page ready |

---

## Next Actions (Start Today)

1. `cp .env.example .env` and fill keys
2. `docker compose up -d`
3. Sign up GoHighLevel affiliate program
4. Start domain warmup (takes 2 weeks – don't skip)
5. Import first 100 test leads from Apollo
