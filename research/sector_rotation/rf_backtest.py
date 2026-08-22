#!/usr/bin/env python3
"""
🌲 Model Comparison v7 (Final-Clean)
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
from engine import (
    load_prices, load_pe, build_features,
    walk_forward_purged, compute_benchmark_aligned,
    calc_metrics, fmt_metrics,
    SECTORS, NAMES, HDR, SEP,
)

END = '2026-06'

print('=' * 90)
print('🌲 MODEL COMPARISON v7 (Final-Clean)')
print('=' * 90)

print('\n[1] Loading prices...')
daily = load_prices()
pe, pe_cov = load_pe()

# Enforce strict universes
ALL_N = len(SECTORS)
NO_XLE_N = len(SECTORS) - 1

print(f'\n[2] Building STRICT features (lag=2)...')
df_all, feat_xs, _ = build_features(
    daily, (pe, pe_cov), execution_lag=2, strict_universe_n=ALL_N
)
df_noXLE, _, _ = build_features(
    daily, (pe, pe_cov), exclude_tickers=['XLE'], execution_lag=2, strict_universe_n=NO_XLE_N
)

# Use the strict start date of the noXLE universe (which will be >= ALL universe start)
START_STR = df_noXLE['date'].min().strftime('%Y-%m')
print(f'  Strict universe start: {START_STR}')

WF = dict(start=START_STR, end=END)

configs = [
    ('RF Top3',            'rf',    df_all,   3),
    ('RF Top1',            'rf',    df_all,   1),
    ('RF Top3 (no XLE)',   'rf',    df_noXLE, 3),
    ('RF Top1 (no XLE)',   'rf',    df_noXLE, 1),
    ('Ridge Top1',         'ridge', df_all,   1),
    ('Ridge Top1 (no XLE)','ridge', df_noXLE, 1),
]

print(f'\n[3] Running ({START_STR}→{END})...\n')

# Aligned benchmark (using noXLE top1 as reference dates)
rdf_ref = walk_forward_purged(df_noXLE, feat_xs, top_n=1, **WF)

print(HDR)
print(SEP)
spy_ret = compute_benchmark_aligned(daily, rdf_ref, 'SPY')
qqq_ret = compute_benchmark_aligned(daily, rdf_ref, 'QQQ')
for tk, ret in [('SPY', spy_ret), ('QQQ', qqq_ret)]:
    m = calc_metrics(ret, f'{tk} (aligned)')
    if m: print(fmt_metrics(m))
m_ew = calc_metrics(rdf_ref['ew'], 'EW sectors')
if m_ew: print(fmt_metrics(m_ew))
print(SEP)

for name, model_type, data, top_n in configs:
    rdf = walk_forward_purged(data, feat_xs, top_n=top_n, **WF, model_type=model_type)
    if len(rdf) == 0: continue
    m = calc_metrics(rdf['top_ret'], name)
    if m:
        xle_n = rdf['picks'].str.contains('XLE').sum()
        print(fmt_metrics(m) + f'  XLE:{xle_n}/{m["n"]}')

# Annual
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
