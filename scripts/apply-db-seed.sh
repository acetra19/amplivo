#!/usr/bin/env bash
# Apply SQL seed/migration files via the Postgres container (no API image rebuild needed).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.prod.yml)

if [[ $# -gt 0 ]]; then
  FILES=("$@")
else
  FILES=(
    database/06-systeme-knowledge-seed.sql
    database/07-systeme-email-sequences.sql
  )
fi

for FILE in "${FILES[@]}"; do
  if [[ ! -f "$FILE" ]]; then
    echo "Missing file: $FILE" >&2
    exit 1
  fi
  echo "Applying $FILE ..."
  cat "$FILE" | "${COMPOSE[@]}" exec -T postgres psql -U agentur -d agentur -v ON_ERROR_STOP=1
done

echo "Done."
