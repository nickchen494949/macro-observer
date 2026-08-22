#!/usr/bin/env python3
"""🌲 Model Comparison v7"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
from engine import (
    load_prices, load_pe, build_features, common_feature_start,
    walk_forward_purged, compute_benchmark_aligned,
    calc_metrics, fmt_metrics,
    SECTORS, NAMES, HDR, SEP,
)

END = '2026-06'

print('=' * 90)
print('🌲 MODEL COMPARISON v7')
print('=' * 90)

daily = load_prices()
pe, pe_cov = load_pe()

df_all, feat_xs, _ = build_features(daily, (pe, pe_cov), execution_lag=2)
df_noXLE, _, _ = build_features(daily, (pe, pe_cov), exclude_tickers=['XLE'], execution_lag=2)

tickers_noXLE = [t for t in SECTORS if t != 'XLE']
START = common_feature_start(df_noXLE, feat_xs, len(tickers_noXLE))
S = START.strftime('%Y-%m') if START else '2019-06'
print(f'  Start: {S}')

WF = dict(start=S, end=END, train_start=S, min_test_sectors=len(tickers_noXLE))

configs = [
    ('RF Top3',            'rf',    df_all,   3, None),
    ('RF Top1',            'rf',    df_all,   1, None),
    ('RF Top3 (no XLE)',   'rf',    df_noXLE, 3, len(tickers_noXLE)),
    ('RF Top1 (no XLE)',   'rf',    df_noXLE, 1, len(tickers_noXLE)),
    ('Ridge Top1',         'ridge', df_all,   1, None),
    ('Ridge Top1 (no XLE)','ridge', df_noXLE, 1, len(tickers_noXLE)),
]

rdf_ref = walk_forward_purged(df_noXLE, feat_xs, top_n=1, **WF)

print(f'\n{HDR}')
print(SEP)
spy_ret = compute_benchmark_aligned(daily, rdf_ref, 'SPY')
qqq_ret = compute_benchmark_aligned(daily, rdf_ref, 'QQQ')
for tk, r in [('SPY', spy_ret), ('QQQ', qqq_ret)]:
    m = calc_metrics(r, f'{tk} (aligned)')
    if m: print(fmt_metrics(m))
m_ew = calc_metrics(rdf_ref['ew'], 'EW sectors')
if m_ew: print(fmt_metrics(m_ew))
print(SEP)

for name, mt, data, tn, ms in configs:
    kw = dict(start=S, end=END, train_start=S, model_type=mt)
    if ms: kw['min_test_sectors'] = ms
    rdf = walk_forward_purged(data, feat_xs, top_n=tn, **kw)
    if len(rdf) == 0: continue
    m = calc_metrics(rdf['top_ret'], name)
    if m: print(fmt_metrics(m))

# Annual
print(f'\n{"=" * 90}')
print('📅 ANNUAL (RF Top1 no XLE)')
print('=' * 90)

if len(rdf_ref) > 0:
    rdf_ref['year'] = rdf_ref['date'].dt.year
    print(f"\n  {'Year':<6s} {'TopRet':>8s} {'EW':>8s} {'Spread':>8s} {'IC':>7s}")
    print('  ' + '─' * 40)
    for year, g in rdf_ref.groupby('year'):
        tr = g['top_ret'].mean() * 12
        ew = g['ew'].mean() * 12
        sp = g['spread'].mean() * 12
        ic = g['ic'].dropna().mean()
        print(f"  {year:<6d} {tr*100:+7.1f}% {ew*100:+7.1f}% {sp*100:+7.1f}% {ic:+6.3f}")

    print(f'\n  Recent:')
    for _, r in rdf_ref.tail(12).iterrows():
        ret = f'{r["top_ret"]*100:+.1f}%' if pd.notna(r['top_ret']) else 'n/a'
        print(f'    {r["date"].strftime("%Y-%m")}: {NAMES.get(r["top1"],r["top1"]):<6s} {ret}')

print('\n✅ Done')
