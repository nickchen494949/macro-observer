#!/bin/sh
# keep ONE Yahoo request stream: wait for the small/mid-cap download to finish, then download S&P opens
cd "$(dirname "$0")"
while pgrep -f fetch_smallcap.py > /dev/null; do sleep 60; done
python3 fetch_opens.py yahoo >> logs/fetch_opens.log 2>&1
echo "OPENS_EXIT $?" >> logs/fetch_opens.log
