#!/usr/bin/env bash
# Apply a SQL seed file via the Postgres container (no API image rebuild needed).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

FILE="${1:-database/06-systeme-knowledge-seed.sql}"
COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.prod.yml)

if [[ ! -f "$FILE" ]]; then
  echo "Missing file: $FILE" >&2
  exit 1
fi

echo "Applying $FILE ..."
cat "$FILE" | "${COMPOSE[@]}" exec -T postgres psql -U agentur -d agentur -v ON_ERROR_STOP=1
echo "Done."
