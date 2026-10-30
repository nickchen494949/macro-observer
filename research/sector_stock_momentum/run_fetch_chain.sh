#!/bin/sh
# Waits for fetch_prices.py to finish, then runs fetch_sectors.py (keeps Yahoo requests strictly sequential).
cd "$(dirname "$0")"
while pgrep -f "fetch_prices.py" >/dev/null; do sleep 30; done
sleep 8
python3 fetch_sectors.py > logs/fetch_sectors.log 2>&1
