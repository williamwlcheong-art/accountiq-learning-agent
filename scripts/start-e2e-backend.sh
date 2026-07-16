#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DB="$ROOT/data/accountiq_e2e.db"

rm -f "$DB" "$DB-wal" "$DB-shm"
mkdir -p "$ROOT/data" "$ROOT/data/pdfs"

export ACCOUNTIQ_DB_PATH="$DB"
export ACCOUNTIQ_E2E_MODE=true
export SECRET_KEY="e2e-secret-key-not-for-production"
export ANTHROPIC_API_KEY="sk-ant-e2e-placeholder"
export CLAUDE_MODEL="claude-sonnet-4-6"

UVICORN="$ROOT/venv/bin/uvicorn"
if [[ ! -x "$UVICORN" ]]; then
  if [[ -x "$ROOT/.venv/bin/uvicorn" ]]; then
    UVICORN="$ROOT/.venv/bin/uvicorn"
  else
    PARENT_ROOT="$(cd "$ROOT/../.." 2>/dev/null && pwd)"
    if [[ -x "$PARENT_ROOT/venv/bin/uvicorn" ]]; then
      UVICORN="$PARENT_ROOT/venv/bin/uvicorn"
    elif [[ -x "$PARENT_ROOT/.venv/bin/uvicorn" ]]; then
      UVICORN="$PARENT_ROOT/.venv/bin/uvicorn"
    else
      UVICORN="$(command -v uvicorn)"
    fi
  fi
fi

PYTHON="$(dirname "$UVICORN")/python"
PYTHONPATH="$ROOT/backend" "$PYTHON" - <<'PY'
import sqlite3
from auth import hash_password
from db import DB_PATH, init_db

init_db()
with sqlite3.connect(DB_PATH) as db:
    db.execute(
        "INSERT INTO users (email, hashed_pw) VALUES (?, ?)",
        ("owner-e2e@example.com", hash_password("correcthorse")),
    )
    db.commit()
PY
"$PYTHON" "$ROOT/scripts/provision_admin.py" \
  --database "$DB" \
  --email "owner-e2e@example.com" \
  --confirm-admin-provisioning

cd "$ROOT/backend"
exec "$UVICORN" main:app --port 8765
