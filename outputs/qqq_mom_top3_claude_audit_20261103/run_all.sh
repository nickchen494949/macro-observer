#!/bin/zsh
# Reproduce the Claude clean-room audit of "QQQ Pure 12-1 Momentum Top-3" end to end.
# (a0 / a1b fetchers are network steps; their outputs are cached in tiingo/ and wiki_ndx/.)
set -e
setopt null_glob
cd "$(dirname "$0")"
rm -f r_hold_returns_*.parquet s_panel_lb*.parquet s_panel_vendor_*.parquet   # caches depend on the vendor files
python3 a1_universe.py
python3 a1c_compare_wiki.py
python3 a3_signals.py
python3 a4_backtest.py --rebuild
python3 a4b_recon_attribution.py
python3 a6_truncation_test.py
python3 -W ignore a7_crosscheck.py
python3 a7b_jump_scan.py
python3 a5_stats_stress.py --rebuild
python3 a8_gaps_mt_vendor.py
python3 a8b_membership_doubt.py
python3 a9_report_tables.py
