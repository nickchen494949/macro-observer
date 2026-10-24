#!/usr/bin/env python3
"""
🌲 Model Comparison v8 (Final Run)
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
print('🌲 MODEL COMPARISON v8 (Final Run)')
print('=' * 90)

print('\n[1] Loading prices...')
daily = load_prices()
pe, pe_cov = load_pe()

ALL_N = len(SECTORS)
NO_XLE_N = len(SECTORS) - 1

print(f'\n[2] Building STRICT features (lag=2)...')
df_all, feat_xs, _ = build_features(
    daily, (pe, pe_cov), execution_lag=2, strict_universe_n=ALL_N
)
df_noXLE, _, _ = build_features(
    daily, (pe, pe_cov), exclude_tickers=['XLE'], execution_lag=2, strict_universe_n=NO_XLE_N
)

# Enforce exact same history for all variants based on noXLE's max history
valid_dates = df_noXLE[df_noXLE['universe_valid']]['date']
MASTER_START = valid_dates.min().strftime('%Y-%m')
print(f'  Common Master start: {MASTER_START}')

WF_KWARGS = dict(start=MASTER_START, end=END, train_start=MASTER_START)

configs = [
    ('RF Top3',            'rf',    df_all,   3),
    ('RF Top1',            'rf',    df_all,   1),
    ('RF Top3 (no XLE)',   'rf',    df_noXLE, 3),
    ('RF Top1 (no XLE)',   'rf',    df_noXLE, 1),
    ('Ridge Top1',         'ridge', df_all,   1),
    ('Ridge Top1 (no XLE)','ridge', df_noXLE, 1),
]

print(f'\n[3] Running ({MASTER_START}→{END})...\n')

# We use noXLE as the calendar reference (it will have missing=CASH for missing months)
rdf_ref = walk_forward_purged(df_noXLE, feat_xs, top_n=1, **WF_KWARGS)

print(HDR)
print(SEP)
spy_ret = compute_benchmark_aligned(daily, rdf_ref, 'SPY')
qqq_ret = compute_benchmark_aligned(daily, rdf_ref, 'QQQ')
for tk, ret in [('SPY', spy_ret), ('QQQ', qqq_ret)]:
    m = calc_metrics(ret, f'{tk} (aligned)')
    if m: print(fmt_metrics(m))

# EW is already computed across available sectors in the reference configuration
m_ew = calc_metrics(rdf_ref['ew'], 'EW sectors')
if m_ew: print(fmt_metrics(m_ew))
print(SEP)

for name, model_type, data, top_n in configs:
    rdf = walk_forward_purged(data, feat_xs, top_n=top_n, **WF_KWARGS, model_type=model_type)
    if len(rdf) == 0: continue
    
    # We drop CASH placeholders to count the true active predictions for Picks logging
    active_rdf = rdf.dropna(subset=['spread'])
    
    m = calc_metrics(rdf['top_ret'], name)
    if m:
        xle_n = active_rdf['picks'].str.contains('XLE').sum() if len(active_rdf) > 0 else 0
        print(fmt_metrics(m) + f'  XLE:{xle_n}/{len(active_rdf)}')

# Annual breakdown
print(f'\n{"=" * 90}')
print('📅 ANNUAL (RF Top1 no XLE)')
print('=' * 90)

if len(rdf_ref) > 0:
    rdf_ref['year'] = rdf_ref['date'].dt.year
    print(f"\n  {'Year':<6s} {'TopRet':>8s} {'EW':>8s} {'Spread':>8s} {'WR':>5s} {'IC':>7s}")
    print('  ' + '─' * 45)
    for year, g in rdf_ref.groupby('year'):
        # For annual breakdown, mean * 12 needs caution because N may be < 12
        # So we sum returns for the year to be exact, or keep using annualized average.
        tr = g['top_ret'].mean() * 12
        ew = g['ew'].mean() * 12
        
        # Spread is NaN for CASH months, drop them for spread/wr/ic stats
        g_active = g.dropna(subset=['spread'])
        sp = g_active['spread'].mean() * 12 if len(g_active) > 0 else np.nan
        wr = (g_active['spread'] > 0).mean() if len(g_active) > 0 else np.nan
        ic = g_active['ic'].dropna().mean() if len(g_active) > 0 else np.nan
        
        print(f"  {year:<6d} {tr*100:+7.1f}% {ew*100:+7.1f}% {sp*100:+7.1f}% "
              f"{wr*100:4.0f}% {ic:+6.3f}")

    print(f'\n  Recent picks:')
    for _, row in rdf_ref.tail(12).iterrows():
        r = f'{row["top_ret"]*100:+.1f}%' if pd.notna(row['top_ret']) else 'n/a'
        print(f'    {row["date"].strftime("%Y-%m")}: {NAMES.get(row["top1"], row["top1"]):<6s} {r}')

print('\n✅ Done')
