#!/usr/bin/env bash
# AccountIQ Learning Agent — one-time setup
set -e

echo "=== AccountIQ Learning Agent Setup ==="

# Create venv
if [ ! -d "venv" ]; then
  echo "Creating virtual environment…"
  python3 -m venv venv
fi

source venv/bin/activate

echo "Installing Python dependencies…"
pip install --upgrade pip -q
pip install -r backend/requirements.txt -q

echo ""
echo "=== Setup complete ==="
echo ""
echo "To start the server:"
echo "  source venv/bin/activate"
echo "  export ANTHROPIC_API_KEY=sk-ant-..."
echo "  cd backend && uvicorn main:app --reload --port 8765"
echo ""
echo "Then open: http://localhost:8765/app"
