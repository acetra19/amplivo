#!/usr/bin/env bash
# Start full stack on VPS (production)
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
echo "API:  https://${API_DOMAIN:-see .env}"
echo "n8n:  https://${N8N_HOST:-see .env}"
