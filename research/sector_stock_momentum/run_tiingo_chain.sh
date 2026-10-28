#!/bin/sh
# after the first Tiingo pass ends cleanly ('done'), run once more for the rename successors (HWM, GAP, FBIN)
cd "$(dirname "$0")"
while pgrep -f "fetch_tiingo.py" >/dev/null; do sleep 30; done
if [ "$(tail -1 fetch_tiingo.log)" = "done" ]; then
  sleep 80
  python3 fetch_tiingo.py > fetch_tiingo_pass2.log 2>&1
fi
