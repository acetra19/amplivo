# Architecture – Agentic Sales Agency

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        LEAD SOURCES                               │
│  Apollo/Clay │ Inbound/SEO │ Instantly Replies │ Affiliate CB   │
└──────┬──────────────┬──────────────┬──────────────┬────────────┘
       │              │              │              │
       ▼              ▼              ▼              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     n8n ORCHESTRATION                             │
│  new-lead │ email-reply │ trial-started │ daily-ops-report      │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FastAPI GATEWAY (:8000)                       │
│  /leads │ /chat │ /webhooks/* │ /ops/daily-report                │
└──────────────────────────┬──────────────────────────────────────┘
                           │
       ┌───────────────────┼───────────────────┐
       ▼                   ▼                   ▼
┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│  Outbound   │   │  Qualifier  │   │    Ops      │
│  Email Agent│   │  Chat Agent │   │  Reporter   │
└──────┬──────┘   └──────┬──────┘   └──────┬──────┘
       │                 │                 │
       └────────────┬────┴─────────────────┘
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│              PostgreSQL + pgvector + Redis                        │
│  leads │ interactions │ conversions │ knowledge_chunks           │
└─────────────────────────────────────────────────────────────────┘
                    │
                    ▼ (warm leads, score >= 80)
┌─────────────────────────────────────────────────────────────────┐
│              LiveKit Voice Agent                                  │
│  Deepgram STT → Claude → ElevenLabs TTS                          │
└─────────────────────────────────────────────────────────────────┘
```

## Agent Responsibilities

| Agent | File | Trigger | Output |
|-------|------|---------|--------|
| Outbound Email | `agents/outbound_email/agent.py` | New lead, email reply | Score, personalized email, reply class |
| Qualifier Chat | `agents/qualifier_chat/agent.py` | Website chat message | BANT score, trial CTA |
| Voice (LiveKit) | `agents/voice_livekit/agent.py` | Voice queue (Redis) | Call transcript → interactions |
| Ops Reporter | `agents/ops_reporter/agent.py` | Daily cron | Metrics rollup, AI summary |

## Data Flow: New Lead

```
1. Apollo export → POST n8n/webhook/new-lead
2. n8n → POST /leads (score + persist)
3. IF score >= 70 → Instantly Sequence A
   ELSE → Instantly Sequence B (nurture)
4. Lead status: enriched → contacted
```

## Data Flow: Email Reply

```
1. Instantly webhook → n8n/email-reply
2. n8n → POST /webhooks/email-reply (classify)
3. Switch on classification:
   - interested → voice queue + Cal.com link
   - objection → auto-reply via Resend (if confidence high)
   - unsubscribe → mark DNC in DB
```

## Data Flow: Conversion

```
1. Affiliate network postback → n8n/affiliate-postback
2. n8n → POST /webhooks/affiliate (record + update status)
3. Onboarding email sequence (Resend)
4. Day 3 → voice check-in call
```

## Database Schema (Core Tables)

- **affiliate_products** – product catalog with commission rates
- **leads** – pipeline state, score, ICP match
- **interactions** – every touchpoint (email, chat, voice)
- **email_sequences** + **lead_sequence_state** – drip tracking
- **conversions** – affiliate events + commission
- **knowledge_chunks** – RAG embeddings for product docs
- **agent_runs** – observability / debugging
- **daily_metrics** – rollup for ops dashboard

## Tech Choices

| Layer | Choice | Why |
|-------|--------|-----|
| Orchestration | n8n | Visual workflows, easy webhook glue, self-hosted |
| Agents | Python + Claude | Best tool-calling, existing LiveKit SDK |
| API | FastAPI | Async, typed, fast to iterate |
| DB | PostgreSQL + pgvector | CRM + RAG in one store |
| Queue | Redis | Voice queue, rate limits |
| Voice | LiveKit Agents | Open source, production-grade realtime |
| Email outbound | Instantly | Warmup, rotation, reply detection |
| Email transactional | Resend | Developer-friendly, good deliverability |

## Security Notes

- Affiliate postback protected by `X-Postback-Secret` header
- All API keys in `.env`, never committed
- `do_not_contact` flag checked before any outreach
- Agent responses logged for audit trail

## Scaling Path

| Stage | Leads/day | Infra change |
|-------|-----------|--------------|
| MVP | 100 | Single VPS, docker compose |
| Growth | 500 | Separate n8n + API instances |
| Scale | 2000+ | Temporal for job reliability, read replicas |

## Folder Structure

```
1agentur/
├── agents/              # Individual agent implementations
│   ├── outbound_email/
│   ├── qualifier_chat/
│   ├── voice_livekit/
│   └── ops_reporter/
├── packages/
│   ├── api/             # FastAPI gateway
│   └── shared/          # Config, DB, LLM, models
├── n8n/workflows/       # Importable workflow JSON
├── database/            # Schema + migrations
├── docs/                # Strategy docs
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```
