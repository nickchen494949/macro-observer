#!/usr/bin/env python3
"""
🔪 5-KNIFE AUDIT v4 — Uses engine.py v4
=========================================
v4 fixes:
  1. Split-only price for EPS, total-return for P&L
  2. Placebo: fixed fake history per seed (not reshuffled per month)
  3. Strict ex-2022: checks execution date overlap
  4. Benchmark: same execution dates as strategy
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
from engine import (
    load_prices, load_pe, build_features,
    walk_forward_purged, make_placebo_df, compute_benchmark_returns,
    calc_metrics, fmt_metrics,
    SECTORS, NAMES, HDR, SEP,
)

START = '2019-01'
END = '2026-06'
N_PLACEBO = 500

print('=' * 90)
print('🔪 5-KNIFE AUDIT v4')
print('=' * 90)
print()
print('  v4 fixes:')
print('    1. split-only price for EPS / total-return for P&L')
print('    2. placebo: fixed fake history per seed')
print('    3. strict ex-2022 by execution date overlap')
print('    4. benchmark uses same execution dates')

# ── Load ──
print('\n[DATA] Loading prices (split-only + total-return)...')
daily = load_prices()
pe, pe_coverage = load_pe()
print('\n  PE coverage:')
for t, (s, e) in sorted(pe_coverage.items()):
    print(f'    {t}: {s} → {e}')

print('\n[DATA] Building features (no XLE)...')
df_noXLE, feat_xs, _ = build_features(daily, (pe, pe_coverage), exclude_tickers=['XLE'])
print(f'  {len(df_noXLE):,d} rows, {len(feat_xs)} features')
print(f'  exec_ret coverage: {df_noXLE["exec_ret"].notna().sum()}/{len(df_noXLE)}')

# ═══════════════════════════════════════════════
# KNIFE 1: Next-Trading-Day + Benchmark Alignment
# ═══════════════════════════════════════════════
print('\n' + '=' * 90)
print('🔪 KNIFE 1: Next-Trading-Day Execution + Aligned Benchmarks')
print('=' * 90)
print()
print(HDR)
print(SEP)

rdf_t1 = walk_forward_purged(df_noXLE, feat_xs, top_n=1, start=START, end=END)
m_t1 = calc_metrics(rdf_t1['top_ret'], 'RF noXLE Top1')
m_t1_sp = calc_metrics(rdf_t1['spread'], 'spread Top1')

rdf_t3 = walk_forward_purged(df_noXLE, feat_xs, top_n=3, start=START, end=END)
m_t3 = calc_metrics(rdf_t3['top_ret'], 'RF noXLE Top3')
m_t3_sp = calc_metrics(rdf_t3['spread'], 'spread Top3')

# Aligned benchmarks
signal_dates = sorted(rdf_t1['date'].unique()) if len(rdf_t1) > 0 else []
spy_ret = compute_benchmark_returns(daily, signal_dates, 'SPY')
qqq_ret = compute_benchmark_returns(daily, signal_dates, 'QQQ')
m_spy = calc_metrics(spy_ret, 'SPY (same dates)')
m_qqq = calc_metrics(qqq_ret, 'QQQ (same dates)')

for m in [m_spy, m_qqq]:
    if m: print(fmt_metrics(m))
print(SEP)
for m in [m_t1, m_t3]:
    if m: print(fmt_metrics(m))
print()
for m in [m_t1_sp, m_t3_sp]:
    if m: print(fmt_metrics(m))

# ═══════════════════════════════════════════════
# KNIFE 2: Sector Picks + LOSO
# ═══════════════════════════════════════════════
print('\n' + '=' * 90)
print('🔪 KNIFE 2: Sector Picks + Leave-One-Sector-Out')
print('=' * 90)

if len(rdf_t1) > 0:
    print('\n  Sector pick frequency (Top1):')
    counts = rdf_t1['top1'].value_counts()
    total = len(rdf_t1)
    for t, c in counts.items():
        bar = '█' * int(c / total * 40)
        print(f'    {NAMES.get(t, t):<6s} ({t}): {c:3d}/{total} = {c/total*100:4.1f}%  {bar}')

print(f'\n  LOSO:')
print(f'  {HDR}')
print(f'  {SEP}')

loso_results = []
for excluded in [t for t in SECTORS if t != 'XLE']:
    df_loso, fx, _ = build_features(daily, (pe, pe_coverage),
                                     exclude_tickers=['XLE', excluded])
    if df_loso is None:
        continue
    rdf_loso = walk_forward_purged(df_loso, fx, top_n=1, start=START, end=END)
    m_loso = calc_metrics(rdf_loso['top_ret'], f'excl XLE+{excluded}')
    if m_loso:
        print(f'  {fmt_metrics(m_loso)}')
        loso_results.append(m_loso)

if loso_results:
    cagrs = [m['cagr'] for m in loso_results]
    print(f'\n  LOSO CAGR: {min(cagrs)*100:+.1f}% → {max(cagrs)*100:+.1f}%, '
          f'mean {np.mean(cagrs)*100:+.1f}% ± {np.std(cagrs)*100:.1f}%')

# ═══════════════════════════════════════════════
# KNIFE 3: Strict Exclude 2022 (exec dates + training labels)
# ═══════════════════════════════════════════════
print('\n' + '=' * 90)
print('🔪 KNIFE 3: Strict Exclude 2022')
print('=' * 90)
print('  Removes: test signals with execution in 2022 + training labels touching 2022')
print()
print(HDR)
print(SEP)

rdf_no22 = walk_forward_purged(
    df_noXLE, feat_xs, top_n=1, start=START, end=END,
    exclude_years_test=[2022],
    exclude_labels_overlapping=[2022],
)
m_no22 = calc_metrics(rdf_no22['top_ret'], 'strict excl 2022 Top1')

for m in [m_t1, m_no22]:
    if m: print(fmt_metrics(m))

# ═══════════════════════════════════════════════
# KNIFE 4: Permutation Importance
# ═══════════════════════════════════════════════
print('\n' + '=' * 90)
print('🔪 KNIFE 4: Permutation Importance (proper groups)')
print('=' * 90)

base_spread = rdf_t1['spread'].mean() * 12
print(f'  Baseline annualized spread: {base_spread*100:+.1f}%\n')

feature_groups = {
    'valuation':     ['f_valuation_xs'],
    'eps_rev 3M':    ['f_eps_rev_xs'],
    'eps_rev 1M':    ['f_eps_rev_1m_xs'],
    'mom 6M':        ['f_mom6_xs'],
    'mom 3M':        ['f_mom3_xs'],
    'mom 1M':        ['f_mom1_xs'],
    'pe_level':      ['f_pe_level_xs'],
    'pe_change':     ['f_pe_chg3_xs'],
    'dist_high':     ['f_dist_high6_xs'],
    'ALL momentum':  ['f_mom6_xs', 'f_mom3_xs', 'f_mom1_xs'],
    'ALL valuation': ['f_valuation_xs', 'f_pe_level_xs'],
    'ALL eps':       ['f_eps_rev_xs', 'f_eps_rev_1m_xs'],
}

for gname, feats in feature_groups.items():
    rdf_shuf = walk_forward_purged(
        df_noXLE, feat_xs, top_n=1, start=START, end=END,
        shuffle_features=feats,
    )
    shuf_sp = rdf_shuf['spread'].mean() * 12
    drop = base_spread - shuf_sp
    pct = (drop / abs(base_spread)) * 100 if abs(base_spread) > 1e-6 else 0
    tag = '🔴 critical' if pct > 30 else '🟡 important' if pct > 10 else '⚪ minor'
    fstr = '+'.join(f.replace('_xs', '').replace('f_', '') for f in feats)
    print(f'  {gname:<18s} [{fstr:<30s}]: '
          f'sprd {shuf_sp*100:+5.1f}% (Δ{drop*100:+5.1f}%, {pct:+.0f}%)  {tag}')

# ═══════════════════════════════════════════════
# KNIFE 5: Placebo — 500 iter, fixed fake history
# ═══════════════════════════════════════════════
print('\n' + '=' * 90)
print('🔪 KNIFE 5: Placebo (500 iter, fixed fake history per seed)')
print('=' * 90)
print(f'  Each seed creates ONE fixed cross-sectional shuffle of all targets')
print(f'  Used consistently across entire walk-forward')
print(f'  Running {N_PLACEBO} iterations...', flush=True)

placebo_spreads = []
for i in range(N_PLACEBO):
    df_fake = make_placebo_df(df_noXLE, seed=i)
    rdf_p = walk_forward_purged(df_fake, feat_xs, top_n=1, start=START, end=END)
    sp = rdf_p['spread'].mean() * 12
    placebo_spreads.append(sp)
    if (i + 1) % 100 == 0:
        print(f'    {i+1}/{N_PLACEBO} done (spread: {sp*100:+.1f}%)...', flush=True)

placebo_arr = np.array(placebo_spreads)
n_ge = (placebo_arr >= base_spread).sum()
p_value = (1 + n_ge) / (N_PLACEBO + 1)

print(f'\n  Real spread:             {base_spread*100:+.1f}%')
print(f'  Placebo mean:            {placebo_arr.mean()*100:+.1f}%')
print(f'  Placebo std:             {placebo_arr.std()*100:.1f}%')
print(f'  Placebo 5th pctl:        {np.percentile(placebo_arr, 5)*100:+.1f}%')
print(f'  Placebo 95th pctl:       {np.percentile(placebo_arr, 95)*100:+.1f}%')
print(f'  Placebo 99th pctl:       {np.percentile(placebo_arr, 99)*100:+.1f}%')
print(f'\n  Real percentile:         {(placebo_arr < base_spread).mean()*100:.1f}%')
print(f'  p-value:                 {p_value:.4f}  ((1+#{"{"}placebo≥real{"}"})/(N+1))')

if p_value < 0.01:
    print('  → p < 1%  ✅')
elif p_value < 0.05:
    print('  → p < 5%  ✅')
elif p_value < 0.10:
    print('  → p < 10% ⚠️')
else:
    print('  → p ≥ 10% ❌')

# ═══════════════════════════════════════════════
# VERDICT
# ═══════════════════════════════════════════════
print('\n' + '=' * 90)
print('📋 VERDICT (v4)')
print('=' * 90)

checks = [
    ('Next-day exec CAGR > 10%',
     m_t1 and m_t1['cagr'] > 0.10,
     f"CAGR {m_t1['cagr']*100:+.1f}%, Sharpe {m_t1['sharpe']:.2f}" if m_t1 else 'N/A'),
    ('LOSO mean CAGR > 8%',
     loso_results and np.mean(cagrs) > 0.08,
     f"mean {np.mean(cagrs)*100:+.1f}%" if loso_results else 'N/A'),
    ('Strict excl-2022 CAGR > 8%',
     m_no22 and m_no22['cagr'] > 0.08,
     f"CAGR {m_no22['cagr']*100:+.1f}%" if m_no22 else 'N/A'),
    ('Placebo p < 0.05',
     p_value < 0.05,
     f'p = {p_value:.4f}'),
]

passed = sum(1 for _, ok, _ in checks if ok)
for name, ok, detail in checks:
    print(f'  {"✅" if ok else "❌"} {name}: {detail}')

print(f'\n  Score: {passed}/4')
if passed == 4:
    print('  → 🟢 Candidate signal (v4 clean)')
elif passed >= 3:
    print('  → 🟡 Promising')
elif passed >= 2:
    print('  → 🟡 Weakened')
else:
    print('  → 🔴 Did not survive')

print('\n✅ v4 audit complete')
