#!/usr/bin/env python3
"""
🌲 Model Comparison v4 — Uses engine.py v4
============================================
RF vs Ridge, with aligned benchmarks and all v4 fixes.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
from engine import (
    load_prices, load_pe, build_features,
    walk_forward_purged, compute_benchmark_returns,
    calc_metrics, fmt_metrics,
    SECTORS, NAMES, HDR, SEP,
)

START = '2019-01'
END = '2026-06'

print('=' * 90)
print('🌲 MODEL COMPARISON v4 — Walk-Forward OOS')
print('=' * 90)

print('\n[1] Loading prices...')
daily = load_prices()
pe, pe_cov = load_pe()

print('\n[2] Building features...')
df_all, feat_xs, _ = build_features(daily, (pe, pe_cov))
df_noXLE, _, _ = build_features(daily, (pe, pe_cov), exclude_tickers=['XLE'])
print(f'  All: {len(df_all):,d} | No XLE: {len(df_noXLE):,d}')

# ── Models ──
configs = [
    ('RF Top3',            'rf',    df_all,   3),
    ('RF Top1',            'rf',    df_all,   1),
    ('RF Top3 (no XLE)',   'rf',    df_noXLE, 3),
    ('RF Top1 (no XLE)',   'rf',    df_noXLE, 1),
    ('Ridge Top3',         'ridge', df_all,   3),
    ('Ridge Top1',         'ridge', df_all,   1),
    ('Ridge Top1 (no XLE)','ridge', df_noXLE, 1),
]

print(f'\n[3] Running ({START}→{END})...\n')
print(HDR)
print(SEP)

# Aligned benchmarks (run one RF first to get signal dates)
rdf_ref = walk_forward_purged(df_noXLE, feat_xs, top_n=1, start=START, end=END)
sig_dates = sorted(rdf_ref['date'].unique()) if len(rdf_ref) > 0 else []

spy_ret = compute_benchmark_returns(daily, sig_dates, 'SPY')
qqq_ret = compute_benchmark_returns(daily, sig_dates, 'QQQ')
for ticker, ret in [('SPY', spy_ret), ('QQQ', qqq_ret)]:
    m = calc_metrics(ret, f'{ticker} (aligned)')
    if m: print(fmt_metrics(m))
print(SEP)

for name, model_type, data, top_n in configs:
    rdf = walk_forward_purged(data, feat_xs, top_n=top_n, start=START, end=END,
                               model_type=model_type)
    if len(rdf) == 0:
        continue
    m = calc_metrics(rdf['top_ret'], name)
    if m:
        xle_n = (rdf['top1'] == 'XLE').sum() if top_n == 1 else rdf['picks'].str.contains('XLE').sum()
        print(fmt_metrics(m) + f'  XLE:{xle_n}/{m["n"]}')

# ── Annual breakdown ──
print(f'\n{"=" * 90}')
print('📅 ANNUAL (RF Top1 no XLE)')
print('=' * 90)

if len(rdf_ref) > 0:
    rdf_ref['year'] = rdf_ref['date'].dt.year
    print(f"\n  {'Year':<6s} {'TopRet':>8s} {'EW':>8s} {'Spread':>8s} {'WR':>5s} {'IC':>7s}")
    print('  ' + '─' * 45)
    for year, g in rdf_ref.groupby('year'):
        tr = g['top_ret'].mean() * 12
        ew = g['ew'].mean() * 12
        sp = g['spread'].mean() * 12
        wr = (g['spread'] > 0).mean()
        ic = g['ic'].dropna().mean()
        print(f"  {year:<6d} {tr*100:+7.1f}% {ew*100:+7.1f}% {sp*100:+7.1f}% "
              f"{wr*100:4.0f}% {ic:+6.3f}")

    print(f'\n  Recent picks:')
    for _, row in rdf_ref.tail(12).iterrows():
        r = f'{row["top_ret"]*100:+.1f}%' if pd.notna(row['top_ret']) else 'n/a'
        print(f'    {row["date"].strftime("%Y-%m")}: {NAMES.get(row["top1"], row["top1"]):<6s} {r}')

print('\n✅ Done')
