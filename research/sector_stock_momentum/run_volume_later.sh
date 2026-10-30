#!/bin/sh
# start the Yahoo volume download only after 07:15 Beijing time (after the dashboard's 06:15 daily Yahoo batch,
# outside US-session live-quote windows); avoids two Yahoo request streams at the same time
cd "$(dirname "$0")"
while [ "$(date +%H%M)" -lt 0715 ] || [ "$(date +%H%M)" -gt 1500 ]; do sleep 120; done
python3 fetch_volume.py > logs/fetch_volume.log 2>&1
