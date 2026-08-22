#!/usr/bin/env python3
"""
🔪 5-KNIFE AUDIT v6

v6 fixes:
  1. Permutation importance: N_PERM=30 with different permutation_seed each
  2. Fixed training universe (train_start = common universe start)
  3. Month-Period date comparison (END='2026-06' includes June)
  4. Universe completeness check after start
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
print('🔪 5-KNIFE AUDIT v6')
print('=' * 90)

# ── Load ──
print('\n[DATA] Loading prices...')
daily = load_prices()
pe, pe_cov = load_pe()

excl = ['XLE']
tickers = [t for t in SECTORS if t not in excl]
print(f'\n[DATA] Building features ({len(tickers)} sectors, excl {excl})...')
df_noXLE, feat_xs, _ = build_features(daily, (pe, pe_cov), exclude_tickers=excl)

# Fixed universe start
START = common_feature_start(df_noXLE, feat_xs, len(tickers))
START_STR = START.strftime('%Y-%m') if START else '2019-06'
print(f'  Fixed universe start: {START_STR}')
print(f'  Rows: {len(df_noXLE):,d}')

# Universe completeness check
bad = check_universe_completeness(df_noXLE, feat_xs, START, len(tickers))
if len(bad) > 0:
    print(f'\n  ⚠ {len(bad)} months with incomplete universe after {START_STR}:')
    for dt, cnt in bad.items():
        print(f'    {dt.strftime("%Y-%m")}: {cnt}/{len(tickers)} sectors')
else:
    print(f'  ✅ All months after {START_STR} have full {len(tickers)}-sector universe')

# Common kwargs
WF_KWARGS = dict(start=START_STR, end=END, train_start=START_STR)

# ═══════════════════════════════════════════════
# KNIFE 1: Baseline + Aligned Benchmarks
# ═══════════════════════════════════════════════
print(f'\n{"=" * 90}')
print(f'🔪 KNIFE 1: Baseline ({START_STR}→{END}) + Aligned Benchmarks')
print('=' * 90)
print()
print(HDR)
print(SEP)

rdf_t1 = walk_forward_purged(df_noXLE, feat_xs, top_n=1, **WF_KWARGS)
rdf_t3 = walk_forward_purged(df_noXLE, feat_xs, top_n=3, **WF_KWARGS)

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

# Excess
if m_t1 and m_spy and m_ew:
    print(f'\n  Top1 vs SPY:  {(m_t1["cagr"]-m_spy["cagr"])*100:+.1f}%')
    print(f'  Top1 vs EW:   {(m_t1["cagr"]-m_ew["cagr"])*100:+.1f}%')
    print(f'  Rank IC:      {rdf_t1["ic"].dropna().mean():+.3f}')
    print(f'  N: strat={m_t1["n"]}, SPY={m_spy["n"]}, QQQ={m_qqq["n"]}')

# ═══════════════════════════════════════════════
# KNIFE 2: LOSO
# ═══════════════════════════════════════════════
print(f'\n{"=" * 90}')
print('🔪 KNIFE 2: LOSO (excess vs aligned SPY)')
print('=' * 90)

if len(rdf_t1) > 0:
    print('\n  Picks:')
    counts = rdf_t1['top1'].value_counts()
    total = len(rdf_t1)
    for t, c in counts.items():
        bar = '█' * int(c / total * 40)
        print(f'    {NAMES.get(t,t):<6s}: {c:3d}/{total} = {c/total*100:4.1f}% {bar}')

print(f'\n  {"Excluded":<14s} {"CAGR":>7s} {"SPY":>7s} {"Excess":>8s} {"Sharpe":>7s}')
print(f'  {"─"*50}')

loso_excesses = []
for excluded in tickers:
    df_l, fx, _ = build_features(daily, (pe, pe_cov), exclude_tickers=['XLE', excluded])
    if df_l is None: continue
    rdf_l = walk_forward_purged(df_l, fx, top_n=1, **WF_KWARGS)
    m_l = calc_metrics(rdf_l['top_ret'], f'excl {excluded}')
    spy_l = compute_benchmark_aligned(daily, rdf_l, 'SPY')
    m_s = calc_metrics(spy_l, 'spy')
    if m_l and m_s:
        exc = m_l['cagr'] - m_s['cagr']
        print(f'  excl XLE+{excluded:<5s}  {m_l["cagr"]*100:+6.1f}% '
              f'{m_s["cagr"]*100:+6.1f}% {exc*100:+7.1f}% {m_l["sharpe"]:6.2f}')
        loso_excesses.append(exc)

if loso_excesses:
    print(f'\n  LOSO excess: {min(loso_excesses)*100:+.1f}% → '
          f'{max(loso_excesses)*100:+.1f}%, mean {np.mean(loso_excesses)*100:+.1f}%')

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
    df_noXLE, feat_xs, top_n=1, **WF_KWARGS,
    exclude_years_test=[2022], exclude_labels_overlapping=[2022])
m_no22 = calc_metrics(rdf_no22['top_ret'], 'strict excl 2022')
spy_no22 = compute_benchmark_aligned(daily, rdf_no22, 'SPY')
m_spy22 = calc_metrics(spy_no22, 'SPY excl 2022')

for m in [m_t1, m_no22]:
    if m: print(fmt_metrics(m))
if m_no22 and m_spy22:
    print(f'\n  Excess vs SPY (excl 2022): {(m_no22["cagr"]-m_spy22["cagr"])*100:+.1f}%')

# ═══════════════════════════════════════════════
# KNIFE 4: Permutation Importance (N_PERM repeats)
# ═══════════════════════════════════════════════
print(f'\n{"=" * 90}')
print(f'🔪 KNIFE 4: Permutation Importance ({N_PERM} repeats per group)')
print('=' * 90)

base_spread = rdf_t1['spread'].mean() * 12
print(f'  Baseline spread: {base_spread*100:+.1f}%\n')

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
    'ALL eps':       ['f_eps_rev_xs', 'f_eps_rev_1m_xs'],
}

for gname, feats in feature_groups.items():
    drops = []
    for rep in range(N_PERM):
        rdf_shuf = walk_forward_purged(
            df_noXLE, feat_xs, top_n=1, **WF_KWARGS,
            shuffle_features=feats,
            permutation_seed=rep * 1000 + hash(gname) % 1000,
        )
        shuf_sp = rdf_shuf['spread'].mean() * 12
        drops.append(base_spread - shuf_sp)

    mean_d = np.mean(drops)
    med_d = np.median(drops)
    lo, hi = np.percentile(drops, [5, 95])
    pct = (mean_d / abs(base_spread)) * 100 if abs(base_spread) > 1e-6 else 0
    tag = '🔴' if pct > 30 else '🟡' if pct > 10 else '⚪'
    fstr = '+'.join(f.replace('_xs', '').replace('f_', '') for f in feats)
    print(f'  {gname:<18s}: mean Δ{mean_d*100:+5.1f}% ({pct:+.0f}%) '
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

placebo_sp = []
placebo_te = []
for i in range(N_PLACEBO):
    df_fake = make_placebo_df(df_noXLE, seed=i)
    rdf_p = walk_forward_purged(df_fake, feat_xs, top_n=1, **WF_KWARGS)
    placebo_sp.append(rdf_p['spread'].mean() * 12)
    placebo_te.append((rdf_p['top_ret'] - rdf_p['ew']).mean() * 12)
    if (i + 1) % 100 == 0:
        print(f'    {i+1}/{N_PLACEBO}...', flush=True)

psp = np.array(placebo_sp)
pte = np.array(placebo_te)

p_sp = (1 + (psp >= base_spread).sum()) / (N_PLACEBO + 1)
p_te = (1 + (pte >= base_top_ew).sum()) / (N_PLACEBO + 1)

print(f'\n  ── Spread ──')
print(f'  Real: {base_spread*100:+.1f}% | Placebo: mean {psp.mean()*100:+.1f}%, '
      f'95th {np.percentile(psp,95)*100:+.1f}%, 99th {np.percentile(psp,99)*100:+.1f}%')
print(f'  p = {p_sp:.4f}')

print(f'\n  ── Top1-EW ──')
print(f'  Real: {base_top_ew*100:+.1f}% | Placebo: mean {pte.mean()*100:+.1f}%, '
      f'95th {np.percentile(pte,95)*100:+.1f}%, 99th {np.percentile(pte,99)*100:+.1f}%')
print(f'  p = {p_te:.4f}')

# ═══════════════════════════════════════════════
# VERDICT
# ═══════════════════════════════════════════════
print(f'\n{"=" * 90}')
print('📋 VERDICT (v6 — excess-based, fixed universe)')
print('=' * 90)

excess_spy = (m_t1['cagr'] - m_spy['cagr']) if m_t1 and m_spy else -1
excess_ew = (m_t1['cagr'] - m_ew['cagr']) if m_t1 and m_ew else -1
mean_ic = rdf_t1['ic'].dropna().mean() if len(rdf_t1) > 0 else -1
loso_mean = np.mean(loso_excesses) if loso_excesses else -1
no22_exc = (m_no22['cagr'] - m_spy22['cagr']) if m_no22 and m_spy22 else -1

checks = [
    ('Top1 > aligned SPY',       excess_spy > 0,   f'{excess_spy*100:+.1f}%'),
    ('Top1 > EW sectors',        excess_ew > 0,    f'{excess_ew*100:+.1f}%'),
    ('Rank IC > 0',              mean_ic > 0,      f'{mean_ic:+.3f}'),
    ('LOSO mean excess > 0',     loso_mean > 0,    f'{loso_mean*100:+.1f}%'),
    ('Excl-2022 excess > 0',     no22_exc > 0,     f'{no22_exc*100:+.1f}%'),
    ('Placebo spread p<0.05',    p_sp < 0.05,      f'p={p_sp:.4f}'),
    ('Placebo Top1-EW p<0.05',   p_te < 0.05,      f'p={p_te:.4f}'),
]

passed = sum(1 for _, ok, _ in checks if ok)
for name, ok, detail in checks:
    print(f'  {"✅" if ok else "❌"} {name}: {detail}')

print(f'\n  Score: {passed}/{len(checks)}')
if passed == len(checks):
    print('  → 🟢 Candidate signal (v6 clean)')
elif passed >= len(checks) - 1:
    print('  → 🟡 Promising')
else:
    print('  → 🔴 Weakened or dead')

print('\n  ⚠️ Not testable by code: Koyfin PIT integrity, ETF P/PE ≠ consensus EPS')
print('✅ v6 complete')
