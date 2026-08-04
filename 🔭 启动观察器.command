#!/bin/bash
# 宏观观察器 — One-click launcher
cd "$(dirname "$0")"

# Check if already running
if lsof -i :8765 -t >/dev/null 2>&1; then
  echo "✅ Server already running on :8765"
else
  echo "🚀 Starting server..."
  nohup node server.js > /tmp/macro-server.log 2>&1 &
  # Wait for server to be ready
  for i in {1..15}; do
    sleep 1
    if curl -s http://localhost:8765/health >/dev/null 2>&1; then
      echo "✅ Server ready!"
      break
    fi
    echo "   waiting... ($i)"
  done
fi

# Open in browser
echo "🌐 Opening dashboard..."
open http://localhost:8765

echo ""
echo "📋 Log: tail -f /tmp/macro-server.log"
echo "🛑 Stop: lsof -i :8765 -t | xargs kill"
echo ""
echo "This window can be closed."
