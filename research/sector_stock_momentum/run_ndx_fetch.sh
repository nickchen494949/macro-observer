#!/bin/sh
# nohup chain: NDX price fetch (WIKI + Tiingo, ~70 min). Log: logs/fetch_ndx_prices.log
cd "$(dirname "$0")"
python3 fetch_ndx_prices.py >> logs/fetch_ndx_prices.log 2>&1
