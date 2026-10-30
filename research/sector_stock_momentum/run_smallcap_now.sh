#!/bin/sh
# continuous small/mid-cap download (user instruction 2026-10-29: do not pause outside the safe window);
# wider spacing outside 07:15-15:45 Beijing; stops for the day on HTTP 429
cd "$(dirname "$0")"
SMALLCAP_NO_WINDOW=1 python3 fetch_smallcap.py >> logs/fetch_smallcap.log 2>&1
rc=$?
[ $rc -eq 0 ] && echo SMALLCAP_DONE >> logs/fetch_smallcap.log
echo "run_smallcap_now exit $rc" >> logs/fetch_smallcap.log
