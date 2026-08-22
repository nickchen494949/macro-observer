#!/usr/bin/env python3
"""
🌲 Model Comparison — Simple vs Ridge vs RF
=============================================
Uses unified engine.py (all fixes applied).
Walk-forward expanding-window comparison.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
from engine import (
    load_adjusted_prices, load_pe, build_features,
    walk_forward_purged, calc_metrics, fmt_metrics,
    SECTORS, NAMES, HDR, SEP,
)

START = '2019-01'
END = '2026-06'

print('=' * 88)
print('🌲 MODEL COMPARISON — Walk-Forward OOS (engine.py v3)')
print('=' * 88)

# ── Load data ──
print('\n[1] Loading adjusted prices...')
daily = load_adjusted_prices()
pe = load_pe()

print('\n[2] Building features...')
df_all, feat_xs, _ = build_features(daily, pe)
df_noXLE, _, _ = build_features(daily, pe, exclude_tickers=['XLE'])
print(f'  All: {len(df_all):,d} rows | No XLE: {len(df_noXLE):,d} rows')

# ── Benchmarks ──
spy_df = df_all[df_all['ticker'] == 'SPY'] if 'SPY' in df_all['ticker'].values else None

# ── Run models ──
configs = [
    ('RF Top3',            'rf',    df_all,   3),
    ('RF Top1',            'rf',    df_all,   1),
    ('RF Top3 (no XLE)',   'rf',    df_noXLE, 3),
    ('RF Top1 (no XLE)',   'rf',    df_noXLE, 1),
    ('Ridge Top3',         'ridge', df_all,   3),
    ('Ridge Top1',         'ridge', df_all,   1),
    ('Ridge Top3 (no XLE)','ridge', df_noXLE, 3),
    ('Ridge Top1 (no XLE)','ridge', df_noXLE, 1),
]

print(f'\n[3] Running models ({START}→{END})...')
print()
print(HDR)
print(SEP)

# SPY benchmark
spy_prices = daily.get('SPY')
if spy_prices is not None:
    spy_m = spy_prices['adj_close'].resample('ME').last().dropna()
    spy_ret = spy_m.pct_change().dropna()
    spy_ret = spy_ret[(spy_ret.index >= START) & (spy_ret.index <= END)]
    spy_met = calc_metrics(spy_ret, 'SPY (benchmark)')
    if spy_met:
        print(fmt_metrics(spy_met))

qqq_prices = daily.get('QQQ')
if qqq_prices is not None:
    qqq_m = qqq_prices['adj_close'].resample('ME').last().dropna()
    qqq_ret = qqq_m.pct_change().dropna()
    qqq_ret = qqq_ret[(qqq_ret.index >= START) & (qqq_ret.index <= END)]
    qqq_met = calc_metrics(qqq_ret, 'QQQ (benchmark)')
    if qqq_met:
        print(fmt_metrics(qqq_met))

print(SEP)

all_results = []
for name, model_type, data, top_n in configs:
    rdf = walk_forward_purged(
        data, feat_xs, top_n=top_n, start=START, end=END,
        model_type=model_type,
    )
    if len(rdf) == 0:
        continue

    m = calc_metrics(rdf['top_ret'], name)
    m_sp = calc_metrics(rdf['spread'], f'{name} spread')
    if m:
        xle_n = (rdf['top1'] == 'XLE').sum() if top_n == 1 else rdf['picks'].str.contains('XLE').sum()
        extra = f'  XLE:{xle_n}/{m["n"]}'
        print(fmt_metrics(m) + extra)
        all_results.append(m)

# ── Annual breakdown for best model ──
print(f'\n{"=" * 88}')
print('📅 ANNUAL BREAKDOWN (RF Top1 no XLE)')
print('=' * 88)

rdf_best = walk_forward_purged(df_noXLE, feat_xs, top_n=1, start=START, end=END)
if len(rdf_best) > 0:
    rdf_best['year'] = rdf_best['date'].dt.year
    print(f"\n  {'Year':<6s} {'TopRet':>9s} {'EW':>9s} {'Spread':>9s} {'WR':>5s} {'IC':>7s}")
    print('  ' + '─' * 50)
    for year, g in rdf_best.groupby('year'):
        tr = g['top_ret'].mean() * 12
        ew = g['ew'].mean() * 12
        sp = g['spread'].mean() * 12
        wr = (g['spread'] > 0).mean()
        ic = g['ic'].dropna().mean()
        print(f"  {year:<6d} {tr*100:+8.1f}% {ew*100:+8.1f}% {sp*100:+8.1f}% "
              f"{wr*100:4.0f}% {ic:+6.3f}")

    # Feature importance (from last RF)
    print(f'\n  Recent 12 picks:')
    for _, row in rdf_best.tail(12).iterrows():
        ret_str = f'{row["top_ret"]*100:+.1f}%' if pd.notna(row['top_ret']) else 'n/a'
        print(f'    {row["date"].strftime("%Y-%m")}: {NAMES.get(row["top1"], row["top1"]):<6s} ret={ret_str}')

print('\n✅ Done')
