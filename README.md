# Amplivo – Agentic Sales Agency

Autonomous affiliate sales agency on **amplivo.net** — VPS + Docker.

**Repo:** [github.com/acetra19/amplivo](https://github.com/acetra19/amplivo)  
**Deploy:** [VPS Deploy Guide](docs/VPS_DEPLOY.md) · **Settings:** Dashboard → Settings

## What's included (ready to deploy)

| Component | Status |
|-----------|--------|
| Landing page + AI chat widget | ✅ `landing/` |
| Lead scoring + Brevo outbound | ✅ |
| Email sequences + daily follow-ups | ✅ n8n |
| Product knowledge base (GoHighLevel FAQ) | ✅ auto-seeded |
| Voice call queue (LiveKit-ready) | ✅ logs until LiveKit configured |
| Gamification dashboard (XP, quests, badges) | ✅ `/dashboard` |
| HTTPS via Caddy | ✅ prod compose |

## Quick Start (VPS)

```bash
git clone https://github.com/acetra19/amplivo.git /opt/amplivo && cd /opt/amplivo
cp .env.example .env && nano .env
python3 scripts/check-setup.py
chmod +x scripts/deploy-vps.sh && ./scripts/deploy-vps.sh
```

## DNS (A-records → VPS IP) für amplivo.net

| Subdomain | Zweck |
|-----------|--------|
| `www.amplivo.net` | Landing Page |
| `api.amplivo.net` | API |
| `dash.amplivo.net` | Dashboard + Settings |
| `n8n.amplivo.net` | n8n Workflows |

Open dashboard: `https://dash.amplivo.net`  
Settings/Keys: `https://dash.amplivo.net/dashboard/settings`

```bash
curl https://api.amplivo.net/health
curl https://api.amplivo.net/pipeline/stats
```

Open landing: `https://www.amplivo.net`

## Import leads (from your PC)

```powershell
python scripts/import-leads.py data/leads-example.csv --webhook https://n8n.amplivo.net/webhook/new-lead
```

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/deploy-vps.sh` | Production deploy |
| `scripts/check-setup.py` | Validate files + .env |
| `scripts/import-leads.py` | CSV → pipeline |
| `scripts/seed-knowledge.py` | Re-seed product FAQ |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/dashboard` | Gamification command center |
| GET | `/dashboard/settings` | API keys & deploy config GUI |
| GET/PUT | `/settings` | Read/save configuration |
| POST | `/settings/test` | Test Groq + Brevo connections |
| POST | `/register` | Landing signup + score |
| POST | `/chat` | AI qualifier chat |
| POST | `/leads` | Create + score lead |
| POST | `/outbound/send` | Send via Brevo |
| GET | `/pipeline/stats` | Dashboard metrics |
| POST | `/webhooks/voice-queue` | Queue voice call |
| POST | `/webhooks/affiliate` | Record conversion |

## Still needs your input

- [ ] API keys via **Dashboard → Settings** (or `.env` fallback)
- [ ] DNS subdomains
- [ ] GoHighLevel affiliate link → `AFFILIATE_TRACKING_BASE`
- [ ] Brevo domain authentication (SPF/DKIM)

## License

Private – all rights reserved.
