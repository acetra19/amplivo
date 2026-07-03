# VPS Deployment

Deploy the full stack on your existing VPS with Docker Compose + Caddy (HTTPS).

## Requirements

- Linux VPS (Ubuntu 22.04+ recommended)
- Docker + Docker Compose v2
- Domain with DNS access
- Ports **80** and **443** open

```bash
# Install Docker (if needed)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# re-login after usermod
```

---

## 1. Clone & Configure

```bash
cd /opt
git clone https://github.com/acetra19/amplivo.git /opt/amplivo
cd amplivo

cp .env.example .env
nano .env
```

Required values:

```env
POSTGRES_PASSWORD=strong-random-password
N8N_ENCRYPTION_KEY=random-32-char-string

API_DOMAIN=api.amplivo.net
LANDING_DOMAIN=www.amplivo.net
N8N_HOST=n8n.amplivo.net
N8N_WEBHOOK_URL=https://n8n.amplivo.net
CADDY_ADMIN_EMAIL=admin@amplivo.net

ANTHROPIC_API_KEY=sk-ant-...
BREVO_API_KEY=xkeysib-...
OUTBOUND_FROM_EMAIL=sales@amplivo.net
DAILY_EMAIL_LIMIT=10
```

---

## 2. DNS Records

Point both subdomains to your VPS IP:

| Type | Name | Value |
|------|------|-------|
| A | api | `YOUR_VPS_IP` |
| A | www (or landing subdomain) | `YOUR_VPS_IP` |
| A | n8n | `YOUR_VPS_IP` |

Wait for propagation (5–30 min), then verify:
```bash
dig +short api.amplivo.net
dig +short n8n.amplivo.net
```

---

## 3. Deploy

```bash
chmod +x scripts/deploy-vps.sh
./scripts/deploy-vps.sh
```

Or manually:
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Verify:
```bash
curl https://api.amplivo.net/health
curl https://api.amplivo.net/pipeline/stats
curl https://www.amplivo.net/
```

---

## 4. Firewall (recommended)

Only expose HTTP/S to the internet. Postgres and Redis stay internal.

```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

With `docker-compose.prod.yml`, Postgres (5432) and Redis (6379) are **not** published.

---

## 5. n8n Setup

1. Open `https://n8n.amplivo.net`
2. Create admin account on first visit
3. **Settings → Import from File** — import all JSON from `n8n/workflows/`:
   - `new-lead.json`, `email-reply.json`, `email-followup-daily.json`
   - `trial-started.json`, `daily-ops-report.json`, `landing-register.json`
4. Activate workflows

Test webhook:
```bash
curl -X POST https://n8n.amplivo.net/webhook/new-lead \
  -H "Content-Type: application/json" \
  -d '{"email":"test@agency.com","first_name":"Test","company":"Test Agency","industry":"marketing_agency","employee_count":5}'
```

---

## 6. Import Leads (from your PC)

You develop/import from your Windows machine — the stack runs on VPS:

```powershell
cd c:\1agentur
pip install httpx
python scripts/import-leads.py data/leads-example.csv `
  --webhook https://n8n.amplivo.net/webhook/new-lead
```

---

## Architecture on VPS

```
Internet
   │
   ▼
Caddy (:443) ──► api.amplivo.net  → FastAPI :8000
              └── n8n.amplivo.net  → n8n :5678

Internal Docker network:
   postgres, redis, api, n8n
```

---

## Updates & Maintenance

```bash
cd /opt/agentur
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Logs:
```bash
docker compose logs -f api
docker compose logs -f n8n
docker compose logs -f caddy
```

Backup Postgres:
```bash
docker compose exec postgres pg_dump -U agentur agentur > backup-$(date +%F).sql
```

---

## Dev vs Production

| | Development (optional, local) | Production (VPS) |
|--|----------------------------|------------------|
| Command | `docker compose up -d` | `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d` |
| HTTPS | No | Caddy + Let's Encrypt |
| DB exposed | localhost:5432 | Internal only |
| URLs | localhost:8000 | api.amplivo.net |

Local dev is optional for code changes — **production runs entirely on VPS**.

---

## Brevo Webhook (Inbound Replies)

In Brevo dashboard, set inbound webhook URL to:
```
https://n8n.amplivo.net/webhook/email-reply
```

Or use the API directly:
```
https://api.amplivo.net/webhooks/brevo-inbound
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Caddy certificate error | DNS not propagated; check A-records |
| n8n webhooks use localhost URL | Set `N8N_WEBHOOK_URL=https://n8n.amplivo.net`, restart n8n |
| API 502 | `docker compose logs api` — check ANTHROPIC_API_KEY |
| Outbound emails fail | Verify BREVO_API_KEY + domain authentication in Brevo |
