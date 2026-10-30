#!/bin/sh
# Yahoo small/mid-cap download, only inside 07:15–15:45 Beijing (after the dashboard's daily batch, before the US
# pre-market live-quote window). Exit codes: 0 done, 2 HTTP 429 (stop for the day), 3 window closed → wait, resume.
cd "$(dirname "$0")"
while true; do
  while [ "$(date +%H%M)" -lt 0715 ] || [ "$(date +%H%M)" -gt 1545 ]; do sleep 120; done
  python3 fetch_smallcap.py >> logs/fetch_smallcap.log 2>&1
  rc=$?
  [ $rc -eq 0 ] && break
  if [ $rc -eq 2 ]; then sleep 43200; fi          # rate-limited: wait 12 h
  sleep 300
done
echo SMALLCAP_DONE >> logs/fetch_smallcap.log
