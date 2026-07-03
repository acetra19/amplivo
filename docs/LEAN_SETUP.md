# Lean Bootstrap auf dem VPS (~€15/month)

Ihr habt bereits einen VPS — alles läuft dort 24/7 via Docker. Kein lokaler Betrieb nötig.

**Deploy-Anleitung:** [VPS Deploy Guide](VPS_DEPLOY.md)

## Kosten (Lean Phase)

| Item | Kosten | Anmerkung |
|------|--------|-----------|
| VPS | ✅ bereits vorhanden | Docker + Compose |
| Domain | ~€10/Jahr | Outreach-Domain |
| Anthropic API (Haiku) | ~$5–15/Monat | Pay-as-you-go |
| Brevo Free | €0 | 300 E-Mails/Tag |
| **Gesamt** | **~€15/Monat** | ohne Instantly/Apollo |

---

## Schnellstart auf dem VPS

```bash
# Auf dem VPS (SSH)
git clone <repo> /opt/agentur && cd /opt/agentur
cp .env.example .env
nano .env   # Keys + Domains eintragen

chmod +x scripts/deploy-vps.sh
./scripts/deploy-vps.sh
```

Von deinem PC aus Leads importieren:
```powershell
python scripts/import-leads.py leads.csv --webhook https://n8n.amplivo.net/webhook/new-lead
```

---

## .env – Pflichtfelder

```env
# Domains (DNS A-Record → VPS-IP)
API_DOMAIN=api.amplivo.net
N8N_HOST=n8n.amplivo.net
N8N_WEBHOOK_URL=https://n8n.amplivo.net

# API Keys
ANTHROPIC_API_KEY=sk-ant-...
BREVO_API_KEY=xkeysib-...
OUTBOUND_FROM_EMAIL=sales@amplivo.net
DAILY_EMAIL_LIMIT=10
```

---

## DNS Setup

Zwei A-Records auf eure VPS-IP zeigen lassen:

```
api.amplivo.net   →  VPS_IP
www.amplivo.net   →  VPS_IP
dash.amplivo.net  →  VPS_IP
n8n.amplivo.net   →  VPS_IP
```

Caddy holt automatisch HTTPS-Zertifikate (Let's Encrypt).

Outbound-E-Mail-Domain (separat empfohlen):
```
TXT  @              SPF (Brevo)
TXT  mail._domainkey DKIM (Brevo)
TXT  _dmarc          DMARC
```

---

## n8n Workflows importieren

1. Öffnen: `https://n8n.amplivo.net`
2. Workflows importieren aus `n8n/workflows/`:

| Datei | Zweck |
|-------|-------|
| `new-lead.json` | Score + erste Mail via Brevo |
| `email-reply.json` | Reply klassifizieren + antworten |
| `email-followup-daily.json` | Follow-ups Tag 3/7 (Cron 09:00) |
| `trial-started.json` | Onboarding nach Conversion |
| `daily-ops-report.json` | Tagesreport |

Alle Workflows aktivieren.

---

## Leads sammeln (ohne Apollo)

Manuell 100 Kontakte als CSV:
```csv
email,first_name,company,industry,employee_count
max@agency.de,Max,Agency GmbH,marketing_agency,8
```

Import vom PC oder VPS:
```bash
python scripts/import-leads.py leads.csv --webhook https://n8n.amplivo.net/webhook/new-lead
```

---

## E-Mail-Volumen (Domain schützen)

| Woche | DAILY_EMAIL_LIMIT |
|-------|-------------------|
| 1 | 10 |
| 2 | 20 |
| 3 | 30 |
| 4+ | 50–100 (nur bei guten Metriken) |

Quota prüfen:
```bash
curl https://api.amplivo.net/outbound/stats
```

Follow-ups laufen automatisch täglich um 09:00 (`email-followup-daily.json`).

---

## Replies verarbeiten

**Brevo Inbound Webhook** → n8n:
```
POST https://n8n.amplivo.net/webhook/email-reply
{"lead_id": "uuid", "reply_text": "Yes, interested"}
```

Oder direkt API:
```bash
curl -X POST https://api.amplivo.net/webhooks/brevo-inbound \
  -H "Content-Type: application/json" \
  -d '{"from_email":"lead@agency.de","text":"Sounds interesting"}'
```

---

## Erst upgraden nach erster Conversion

| Signal | Upgrade | Kosten |
|--------|---------|--------|
| >100 Mails/Tag | Instantly | $97/Mo |
| Lead-Suche zu langsam | Apollo | $49/Mo |
| Warm Leads wollen Anruf | LiveKit | $50/Mo |
| Bessere Einwandbehandlung | Sonnet statt Haiku | +~$30/Mo |

---

## Troubleshooting

**Caddy / HTTPS funktioniert nicht:**
- DNS A-Records propagiert? (`dig api.amplivo.net`)
- Ports 80 + 443 in Firewall offen?

**n8n Webhooks 404:**
- `N8N_WEBHOOK_URL` muss exakt `https://n8n.amplivo.net` sein
- Workflows aktiviert?

**E-Mails im Spam:**
- [mail-tester.com](https://www.mail-tester.com) testen
- Volumen reduzieren, Copy verbessern

**429 Daily limit:**
- Normal — `DAILY_EMAIL_LIMIT` langsam erhöhen
