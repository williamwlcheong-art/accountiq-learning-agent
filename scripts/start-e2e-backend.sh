#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DB="$ROOT/data/accountiq_e2e.db"

rm -f "$DB" "$DB-wal" "$DB-shm"
mkdir -p "$ROOT/data" "$ROOT/data/pdfs"

export ACCOUNTIQ_DB_PATH="$DB"
export ACCOUNTIQ_E2E_MODE=true
export SECRET_KEY="e2e-secret-key-not-for-production"
export OWNER_EMAIL="owner-e2e@example.com"
export ANTHROPIC_API_KEY="sk-ant-e2e-placeholder"
export CLAUDE_MODEL="claude-sonnet-4-6"

UVICORN="$ROOT/venv/bin/uvicorn"
if [[ ! -x "$UVICORN" ]]; then
  PARENT_ROOT="$(cd "$ROOT/../.." 2>/dev/null && pwd)"
  if [[ -x "$PARENT_ROOT/venv/bin/uvicorn" ]]; then
    UVICORN="$PARENT_ROOT/venv/bin/uvicorn"
  else
    UVICORN="$(command -v uvicorn)"
  fi
fi

cd "$ROOT/backend"
exec "$UVICORN" main:app --port 8765
