#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${ACCOUNTIQ_PORT:-8765}"

export ACCOUNTIQ_DEMO_MODE=true
export ACCOUNTIQ_AUTH_DISABLED="${ACCOUNTIQ_AUTH_DISABLED:-true}"

cd "$ROOT/backend"

if [[ -x "$ROOT/venv/bin/python" ]]; then
  exec "$ROOT/venv/bin/python" -m uvicorn main:app --reload --port "$PORT"
fi

exec python -m uvicorn main:app --reload --port "$PORT"
