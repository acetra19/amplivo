#!/usr/bin/env bash
# Deploy Agentic Sales Agency to your VPS (Linux)
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "ERROR: .env missing. Run: cp .env.example .env && nano .env"
  exit 1
fi

get_env() {
  grep -E "^${1}=" .env | head -1 | cut -d= -f2- | tr -d '\r' \
    | sed 's/^[[:space:]]*//;s/[[:space:]]*$//;s/^"\(.*\)"$/\1/'
}

required=(BREVO_API_KEY OUTBOUND_FROM_EMAIL N8N_HOST API_DOMAIN N8N_WEBHOOK_URL POSTGRES_PASSWORD N8N_ENCRYPTION_KEY AFFILIATE_POSTBACK_SECRET)
for var in "${required[@]}"; do
  val="$(get_env "$var")"
  if [ -z "$val" ]; then
    echo "ERROR: Set $var in .env before deploying."
    exit 1
  fi
  export "$var=$val"
done

provider="$(get_env LLM_PROVIDER)"
provider="${provider:-groq}"
groq_key="$(get_env GROQ_API_KEY)"
anthropic_key="$(get_env ANTHROPIC_API_KEY)"
if [ "$provider" = "groq" ] && [ -z "$groq_key" ]; then
  echo "ERROR: Set GROQ_API_KEY in .env (or switch LLM_PROVIDER=anthropic)"
  exit 1
fi
if [ "$provider" = "anthropic" ] && [ -z "$anthropic_key" ]; then
  echo "ERROR: Set ANTHROPIC_API_KEY in .env"
  exit 1
fi

LANDING_DOMAIN="$(get_env LANDING_DOMAIN)"
DASHBOARD_DOMAIN="$(get_env DASHBOARD_DOMAIN)"

echo "==> Pulling latest images..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml pull

echo "==> Building and starting stack..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

echo "==> Waiting for API..."
for i in $(seq 1 30); do
  if docker compose exec -T api python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')" 2>/dev/null; then
    echo "API is ready."
    break
  fi
  sleep 2
done

echo ""
echo "Deployment complete."
echo "  API:     https://${API_DOMAIN}"
echo "  Landing: https://${LANDING_DOMAIN:-$API_DOMAIN}"
echo "  Dashboard: https://${DASHBOARD_DOMAIN:-$API_DOMAIN/dashboard}"
echo "  n8n:       https://${N8N_HOST}"
echo ""
echo "Next steps:"
echo "  1. Point DNS A-records for ${API_DOMAIN}, ${LANDING_DOMAIN:-}, ${DASHBOARD_DOMAIN:-dash}, ${N8N_HOST} to VPS IP"
echo "  2. Open https://${N8N_HOST} and import workflows from n8n/workflows/"
echo "  3. Test: curl https://${API_DOMAIN}/health"
echo "  4. Import leads: python scripts/import-leads.py data/leads-example.csv --webhook https://${N8N_HOST}/webhook/new-lead"
