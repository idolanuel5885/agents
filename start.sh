#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Agent Runner — starting up"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Pull latest code + update agents
echo "→ Pulling latest updates..."
git pull origin main --quiet
git submodule update --init --recursive --quiet
echo "✓ Code up to date"

# Install/update dependencies
echo "→ Installing dependencies..."
pip install -q -r requirements.txt
for agent_dir in agents/*/; do
  if [ -f "$agent_dir/requirements.txt" ]; then
    pip install -q -r "$agent_dir/requirements.txt"
  fi
done
echo "✓ Dependencies ready"

# Open browser (works on Mac, Linux desktop, WSL)
URL="http://localhost:8000"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Open this in your browser: $URL"
echo "  Press Ctrl+C to stop"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
(sleep 2 && (open "$URL" 2>/dev/null || xdg-open "$URL" 2>/dev/null || true)) &

# Start the server
uvicorn server:app --host 0.0.0.0 --port 8000
