#!/usr/bin/env python3
"""
🔪 5-KNIFE AUDIT v7 — final clean

Uses engine v7:
  - T+2 execution (Koyfin finalization lag)
  - Execution-aligned 3M target + exact purge
  - Symmetric Forward Earnings Momentum
  - Strict fixed universe
  - Proper placebo / permutation / Sortino

Also tests T+1 and T+3 execution for robustness.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
from engine import (
    load_prices, load_pe, build_features,
    common_feature_start, check_universe_completeness,
    walk_forward_purged, make_placebo_df, compute_benchmark_aligned,
    calc_metrics, fmt_metrics,
    SECTORS, NAMES, FEAT_COLS, HDR, SEP,
)

END = '2026-06'
N_PLACEBO = 500
N_PERM = 30

print('=' * 90)
print('🔪 5-KNIFE AUDIT v7 — FINAL CLEAN')
print('=' * 90)
print()
print('  T+2 execution | exec-aligned 3M target | symmetric Forward Earnings Momentum')
print('  strict fixed universe | NaN-safe placebo | proper Sortino')

# ── Load ──
print('\n[DATA] Loading prices...')
daily = load_prices()
pe, pe_cov = load_pe()

excl = ['XLE']
tickers = [t for t in SECTORS if t not in excl]
n_sectors = len(tickers)

print(f'\n[DATA] Building features ({n_sectors} sectors, execution_lag=2)...')
df_noXLE, feat_xs, _ = build_features(daily, (pe, pe_cov),
                                       exclude_tickers=excl, execution_lag=2)

START = common_feature_start(df_noXLE, feat_xs, n_sectors)
START_STR = START.strftime('%Y-%m') if START else '2019-06'
print(f'  Fixed universe start: {START_STR}')
print(f'  Rows: {len(df_noXLE):,d}')

bad = check_universe_completeness(df_noXLE, feat_xs, START, n_sectors)
if len(bad) > 0:
    print(f'  ⚠ {len(bad)} months incomplete after {START_STR}:')
    for dt, cnt in bad.items():
        print(f'    {dt.strftime("%Y-%m")}: {cnt}/{n_sectors}')
else:
    print(f'  ✅ All months have full {n_sectors}-sector universe')

WF = dict(start=START_STR, end=END, train_start=START_STR,
          min_test_sectors=n_sectors)

# ═══════════════════════════════════════════════
# KNIFE 0: Execution Lag Sensitivity (T+1, T+2, T+3)
# ═══════════════════════════════════════════════
print(f'\n{"=" * 90}')
print('🔪 KNIFE 0: Execution Lag Sensitivity')
print('=' * 90)
print()
print(HDR)
print(SEP)

for lag in [1, 2, 3]:
    df_lag, fx_lag, _ = build_features(daily, (pe, pe_cov),
                                        exclude_tickers=excl, execution_lag=lag)
    rdf_lag = walk_forward_purged(df_lag, fx_lag, top_n=1, **WF)
    m = calc_metrics(rdf_lag['top_ret'], f'T+{lag} execution')
    if m: print(fmt_metrics(m))

# ═══════════════════════════════════════════════
# KNIFE 1: Baseline (T+2) + Aligned Benchmarks
# ═══════════════════════════════════════════════
print(f'\n{"=" * 90}')
print(f'🔪 KNIFE 1: Baseline T+2 ({START_STR}→{END}) + Aligned Benchmarks')
print('=' * 90)
print()
print(HDR)
print(SEP)

rdf_t1 = walk_forward_purged(df_noXLE, feat_xs, top_n=1, **WF)
rdf_t3 = walk_forward_purged(df_noXLE, feat_xs, top_n=3, **WF)

m_t1 = calc_metrics(rdf_t1['top_ret'], 'RF noXLE Top1')
m_t3 = calc_metrics(rdf_t3['top_ret'], 'RF noXLE Top3')
m_ew = calc_metrics(rdf_t1['ew'], 'EW sectors')

spy_ret = compute_benchmark_aligned(daily, rdf_t1, 'SPY')
qqq_ret = compute_benchmark_aligned(daily, rdf_t1, 'QQQ')
m_spy = calc_metrics(spy_ret, 'SPY (aligned)')
m_qqq = calc_metrics(qqq_ret, 'QQQ (aligned)')

for m in [m_spy, m_qqq, m_ew]:
    if m: print(fmt_metrics(m))
print(SEP)
for m in [m_t1, m_t3]:
    if m: print(fmt_metrics(m))

if m_t1 and m_spy and m_ew:
    print(f'\n  Top1 vs SPY:  {(m_t1["cagr"]-m_spy["cagr"])*100:+.1f}%')
    print(f'  Top1 vs EW:   {(m_t1["cagr"]-m_ew["cagr"])*100:+.1f}%')
    print(f'  Rank IC:      {rdf_t1["ic"].dropna().mean():+.3f}')
    print(f'  N: {m_t1["n"]} (strat=SPY={m_spy["n"]})')

m_t1_sp = calc_metrics(rdf_t1['spread'], 'spread')
if m_t1_sp:
    print(f'  Spread: ann {m_t1_sp["cagr"]*100:+.1f}%, WR {m_t1_sp["wr"]*100:.0f}%')

# ═══════════════════════════════════════════════
# KNIFE 2: LOSO
# ═══════════════════════════════════════════════
print(f'\n{"=" * 90}')
print('🔪 KNIFE 2: LOSO')
print('=' * 90)

if len(rdf_t1) > 0:
    counts = rdf_t1['top1'].value_counts()
    total = len(rdf_t1)
    print('\n  Picks:')
    for t, c in counts.items():
        bar = '█' * int(c / total * 40)
        print(f'    {NAMES.get(t,t):<6s}: {c:3d}/{total} = {c/total*100:4.1f}% {bar}')

print(f'\n  {"Excluded":<14s} {"CAGR":>7s} {"SPY":>7s} {"Excess":>8s}')
print(f'  {"─"*40}')

loso_exc = []
for excluded in tickers:
    df_l, fx, _ = build_features(daily, (pe, pe_cov),
                                  exclude_tickers=['XLE', excluded], execution_lag=2)
    if df_l is None: continue
    n_l = len([t for t in tickers if t != excluded])
    rdf_l = walk_forward_purged(df_l, fx, top_n=1,
                                 start=START_STR, end=END, train_start=START_STR,
                                 min_test_sectors=n_l)
    m_l = calc_metrics(rdf_l['top_ret'], f'excl {excluded}')
    spy_l = compute_benchmark_aligned(daily, rdf_l, 'SPY')
    m_s = calc_metrics(spy_l, 'spy')
    if m_l and m_s:
        exc = m_l['cagr'] - m_s['cagr']
        print(f'  excl XLE+{excluded:<5s}  {m_l["cagr"]*100:+6.1f}% '
              f'{m_s["cagr"]*100:+6.1f}% {exc*100:+7.1f}%')
        loso_exc.append(exc)

if loso_exc:
    print(f'\n  Excess: {min(loso_exc)*100:+.1f}% → {max(loso_exc)*100:+.1f}%, '
          f'mean {np.mean(loso_exc)*100:+.1f}%')

# ═══════════════════════════════════════════════
# KNIFE 3: Strict Exclude 2022
# ═══════════════════════════════════════════════
print(f'\n{"=" * 90}')
print('🔪 KNIFE 3: Strict Exclude 2022')
print('=' * 90)
print()
print(HDR)
print(SEP)

rdf_no22 = walk_forward_purged(
    df_noXLE, feat_xs, top_n=1, **WF,
    exclude_years_test=[2022], exclude_labels_overlapping=[2022])
m_no22 = calc_metrics(rdf_no22['top_ret'], 'strict excl 2022')
spy_no22 = compute_benchmark_aligned(daily, rdf_no22, 'SPY')
m_spy22 = calc_metrics(spy_no22, 'SPY excl 2022')

for m in [m_t1, m_no22]:
    if m: print(fmt_metrics(m))
if m_no22 and m_spy22:
    print(f'\n  Excess (excl 2022): {(m_no22["cagr"]-m_spy22["cagr"])*100:+.1f}%')

# ═══════════════════════════════════════════════
# KNIFE 4: Permutation Importance (N_PERM repeats, deterministic)
# ═══════════════════════════════════════════════
print(f'\n{"=" * 90}')
print(f'🔪 KNIFE 4: Permutation Importance ({N_PERM} repeats)')
print('=' * 90)

base_spread = rdf_t1['spread'].mean() * 12
print(f'  Baseline spread: {base_spread*100:+.1f}%\n')

feature_groups = {
    'valuation':       ['f_valuation_xs'],
    'earn_mom 3M':     ['f_fwd_earn_mom_3m_xs'],
    'earn_mom 1M':     ['f_fwd_earn_mom_1m_xs'],
    'mom 6M':          ['f_mom6_xs'],
    'mom 3M':          ['f_mom3_xs'],
    'mom 1M':          ['f_mom1_xs'],
    'pe_level':        ['f_pe_level_xs'],
    'pe_change':       ['f_pe_chg3_xs'],
    'dist_high':       ['f_dist_high6_xs'],
    'ALL momentum':    ['f_mom6_xs', 'f_mom3_xs', 'f_mom1_xs'],
    'ALL earn_mom':    ['f_fwd_earn_mom_3m_xs', 'f_fwd_earn_mom_1m_xs'],
}

for gid, (gname, feats) in enumerate(feature_groups.items()):
    drops = []
    for rep in range(N_PERM):
        seed = gid * 10000 + rep
        rdf_shuf = walk_forward_purged(
            df_noXLE, feat_xs, top_n=1, **WF,
            shuffle_features=feats, permutation_seed=seed)
        shuf_sp = rdf_shuf['spread'].mean() * 12
        drops.append(base_spread - shuf_sp)

    mean_d = np.mean(drops)
    lo, hi = np.percentile(drops, [5, 95])
    pct = (mean_d / abs(base_spread)) * 100 if abs(base_spread) > 1e-6 else 0
    tag = '🔴' if pct > 30 else '🟡' if pct > 10 else '⚪'
    fstr = '+'.join(f.replace('_xs', '').replace('f_', '') for f in feats)
    print(f'  {gname:<18s}: Δ{mean_d*100:+5.1f}% ({pct:+.0f}%) '
          f'[5-95: {lo*100:+.1f}%..{hi*100:+.1f}%]  {tag}')

# ═══════════════════════════════════════════════
# KNIFE 5: Placebo
# ═══════════════════════════════════════════════
print(f'\n{"=" * 90}')
print(f'🔪 KNIFE 5: Placebo ({N_PLACEBO} seeds)')
print('=' * 90)

base_top_ew = (rdf_t1['top_ret'] - rdf_t1['ew']).mean() * 12
print(f'  Baseline spread:   {base_spread*100:+.1f}%')
print(f'  Baseline Top1-EW:  {base_top_ew*100:+.1f}%')
print(f'  Running...', flush=True)

pl_sp, pl_te = [], []
for i in range(N_PLACEBO):
    df_f = make_placebo_df(df_noXLE, seed=i)
    rdf_p = walk_forward_purged(df_f, feat_xs, top_n=1, **WF)
    pl_sp.append(rdf_p['spread'].mean() * 12)
    pl_te.append((rdf_p['top_ret'] - rdf_p['ew']).mean() * 12)
    if (i + 1) % 100 == 0:
        print(f'    {i+1}/{N_PLACEBO}...', flush=True)

psp = np.array(pl_sp)
pte = np.array(pl_te)
p_sp = (1 + (psp >= base_spread).sum()) / (N_PLACEBO + 1)
p_te = (1 + (pte >= base_top_ew).sum()) / (N_PLACEBO + 1)

print(f'\n  ── Spread ──')
print(f'  Real: {base_spread*100:+.1f}% | mean {psp.mean()*100:+.1f}%, '
      f'95th {np.percentile(psp,95)*100:+.1f}%')
print(f'  p = {p_sp:.4f}')
print(f'\n  ── Top1-EW ──')
print(f'  Real: {base_top_ew*100:+.1f}% | mean {pte.mean()*100:+.1f}%, '
      f'95th {np.percentile(pte,95)*100:+.1f}%')
print(f'  p = {p_te:.4f}')

# ═══════════════════════════════════════════════
# VERDICT
# ═══════════════════════════════════════════════
print(f'\n{"=" * 90}')
print('📋 VERDICT (v7 final-clean)')
print('=' * 90)

excess_spy = (m_t1['cagr'] - m_spy['cagr']) if m_t1 and m_spy else -1
excess_ew = (m_t1['cagr'] - m_ew['cagr']) if m_t1 and m_ew else -1
mean_ic = rdf_t1['ic'].dropna().mean() if len(rdf_t1) > 0 else -1
loso_mean = np.mean(loso_exc) if loso_exc else -1
no22_exc = (m_no22['cagr'] - m_spy22['cagr']) if m_no22 and m_spy22 else -1

checks = [
    ('Top1 > SPY',           excess_spy > 0,  f'{excess_spy*100:+.1f}%'),
    ('Top1 > EW',            excess_ew > 0,   f'{excess_ew*100:+.1f}%'),
    ('Rank IC > 0',          mean_ic > 0,     f'{mean_ic:+.3f}'),
    ('LOSO excess > 0',      loso_mean > 0,   f'{loso_mean*100:+.1f}%'),
    ('Excl-2022 excess > 0', no22_exc > 0,    f'{no22_exc*100:+.1f}%'),
    ('Placebo sprd p<0.05',  p_sp < 0.05,     f'p={p_sp:.4f}'),
    ('Placebo T1-EW p<0.05', p_te < 0.05,     f'p={p_te:.4f}'),
]

passed = sum(1 for _, ok, _ in checks if ok)
for name, ok, detail in checks:
    print(f'  {"✅" if ok else "❌"} {name}: {detail}')

print(f'\n  Score: {passed}/{len(checks)}')
if passed == len(checks):
    print('  → 🟢 Candidate (v7 clean)')
elif passed >= len(checks) - 1:
    print('  → 🟡 Promising')
else:
    print('  → 🔴 Weakened / dead')

print('\n  Remaining non-code risks:')
print('    ⚠ Koyfin historical PE ≠ perfect PIT (vendor-history backtest)')
print('    ⚠ Multiple-testing: many models tried before v7')
print('    ⚠ No transaction cost / turnover analysis')
print('\n✅ v7 complete')
