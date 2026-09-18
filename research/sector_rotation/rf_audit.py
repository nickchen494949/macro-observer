#!/usr/bin/env python3
"""
🔪 5-KNIFE AUDIT v8 (Final Run)

v8 fixes:
  1. Strict Universe: CASH holding for missing months
  2. train_start passed cleanly everywhere
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
from engine import (
    load_prices, load_pe, build_features,
    walk_forward_purged, make_placebo_df, compute_benchmark_aligned,
    calc_metrics, fmt_metrics,
    SECTORS, NAMES, FEAT_COLS, HDR, SEP,
)

END = '2026-06'
N_PLACEBO = 500
N_PERM = 30

print('=' * 90)
print('🔪 5-KNIFE AUDIT v8 (Final Run)')
print('=' * 90)

# ── Load ──
print('\n[DATA] Loading prices...')
daily = load_prices()
pe, pe_cov = load_pe()

excl = ['XLE']
tickers = [t for t in SECTORS if t not in excl]
STRICT_N = len(tickers)

# We use T+2 for the main results per Koyfin PIT discovery
print(f'\n[DATA] Building STRICT features ({STRICT_N} sectors, excl {excl}), lag=2...')
df_noXLE, feat_xs, _ = build_features(
    daily, (pe, pe_cov), exclude_tickers=excl, execution_lag=2, strict_universe_n=STRICT_N
)

# Start is just the min date now because build_features flagged universe_valid
valid_dates = df_noXLE[df_noXLE['universe_valid']]['date']
MASTER_START = valid_dates.min().strftime('%Y-%m')
print(f'  Master start (common train_start): {MASTER_START}')
print(f'  Rows: {len(df_noXLE):,d}')

WF_KWARGS = dict(start=MASTER_START, end=END, train_start=MASTER_START)

# ═══════════════════════════════════════════════
# KNIFE 1: Baseline Lags + Aligned Benchmarks
# ═══════════════════════════════════════════════
print(f'\n{"=" * 90}')
print(f'🔪 KNIFE 1: Baseline Execution Lags ({MASTER_START}→{END})')
print('=' * 90)
print()
print(HDR)
print(SEP)

# Test T+1, T+2, T+3
for lag in [1, 2, 3]:
    df_lag, fx, _ = build_features(
        daily, (pe, pe_cov), exclude_tickers=excl, execution_lag=lag, strict_universe_n=STRICT_N
    )
    rdf_lag = walk_forward_purged(df_lag, fx, top_n=1, **WF_KWARGS)
    spy_lag = compute_benchmark_aligned(daily, rdf_lag, 'SPY')
    
    m_l = calc_metrics(rdf_lag['top_ret'], f'RF noXLE Top1 (T+{lag})')
    m_s = calc_metrics(spy_lag, f'SPY (aligned T+{lag})')
    
    if m_l and m_s:
        exc = m_l['cagr'] - m_s['cagr']
        print(fmt_metrics(m_l) + f'  [Excess: {exc*100:+.1f}%]')

print(SEP)
# Main outputs use T+2 (df_noXLE)
rdf_t1 = walk_forward_purged(df_noXLE, feat_xs, top_n=1, **WF_KWARGS)
m_t1 = calc_metrics(rdf_t1['top_ret'], 'RF noXLE Top1 (T+2 MAIN)')

m_ew = calc_metrics(rdf_t1['ew'], 'EW sectors')
spy_ret = compute_benchmark_aligned(daily, rdf_t1, 'SPY')
qqq_ret = compute_benchmark_aligned(daily, rdf_t1, 'QQQ')
m_spy = calc_metrics(spy_ret, 'SPY (aligned)')
m_qqq = calc_metrics(qqq_ret, 'QQQ (aligned)')

for m in [m_spy, m_qqq, m_ew]:
    if m: print(fmt_metrics(m))
print(SEP)

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

print(f'\n  {"Excluded":<14s} {"CAGR":>7s} {"SPY":>7s} {"Excess":>8s} {"Sharpe":>7s}')
print(f'  {"─"*50}')

loso_excesses = []
for excluded in tickers:
    # Strict universe for LOSO is N-1
    df_l, fx, _ = build_features(
        daily, (pe, pe_cov), exclude_tickers=['XLE', excluded],
        execution_lag=2, strict_universe_n=STRICT_N - 1
    )
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
# KNIFE 4: Permutation Importance
# ═══════════════════════════════════════════════
print(f'\n{"=" * 90}')
print(f'🔪 KNIFE 4: Permutation Importance ({N_PERM} repeats per group)')
print('=' * 90)

# valid picks only for spread base
v_base = rdf_t1.dropna(subset=['spread'])
base_spread = v_base['spread'].mean() * 12
print(f'  Baseline spread: {base_spread*100:+.1f}%\n')

feature_groups = {
    'valuation':     ['f_valuation_xs'],
    'fwd_earn 3M':   ['f_fwd_earn_mom_3m_xs'],
    'fwd_earn 1M':   ['f_fwd_earn_mom_1m_xs'],
    'mom 6M':        ['f_mom6_xs'],
    'mom 3M':        ['f_mom3_xs'],
    'mom 1M':        ['f_mom1_xs'],
    'pe_level':      ['f_pe_level_xs'],
    'pe_change':     ['f_pe_chg3_xs'],
    'dist_high':     ['f_dist_high6_xs'],
    'ALL momentum':  ['f_mom6_xs', 'f_mom3_xs', 'f_mom1_xs'],
    'ALL fwd earn':  ['f_fwd_earn_mom_3m_xs', 'f_fwd_earn_mom_1m_xs'],
}

for group_id, (gname, feats) in enumerate(feature_groups.items()):
    drops = []
    for rep in range(N_PERM):
        seed = group_id * 10000 + rep
        rdf_shuf = walk_forward_purged(
            df_noXLE, feat_xs, top_n=1, **WF_KWARGS,
            shuffle_features=feats,
            permutation_seed=seed,
        )
        shuf_sp = rdf_shuf['spread'].dropna().mean() * 12
        drops.append(base_spread - shuf_sp)

    mean_d = np.mean(drops)
    lo, hi = np.percentile(drops, [5, 95])
    pct = (mean_d / abs(base_spread)) * 100 if abs(base_spread) > 1e-6 else 0
    tag = '🔴' if pct > 30 else '🟡' if pct > 10 else '⚪'
    print(f'  {gname:<18s}: mean Δ{mean_d*100:+5.1f}% ({pct:+.0f}%) '
          f'[5-95: {lo*100:+.1f}%..{hi*100:+.1f}%]  {tag}')

# ═══════════════════════════════════════════════
# KNIFE 5: Placebo
# ═══════════════════════════════════════════════
print(f'\n{"=" * 90}')
print(f'🔪 KNIFE 5: Placebo ({N_PLACEBO} seeds)')
print('=' * 90)

base_top_ew = (v_base['top_ret'] - v_base['ew']).mean() * 12
print(f'  Baseline spread:   {base_spread*100:+.1f}%')
print(f'  Baseline Top1-EW:  {base_top_ew*100:+.1f}%')
print(f'  Running...', flush=True)

placebo_sp = []
placebo_te = []
for i in range(N_PLACEBO):
    df_fake = make_placebo_df(df_noXLE, seed=i)
    rdf_p = walk_forward_purged(df_fake, feat_xs, top_n=1, **WF_KWARGS)
    v_p = rdf_p.dropna(subset=['spread'])
    placebo_sp.append(v_p['spread'].mean() * 12)
    placebo_te.append((v_p['top_ret'] - v_p['ew']).mean() * 12)
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
print('📋 VERDICT (v8 — final clean)')
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
    print('  → 🟢 Candidate signal (v8 clean)')
elif passed >= len(checks) - 1:
    print('  → 🟡 Promising')
else:
    print('  → 🔴 Weakened or dead')

print('\n✅ v8 audit complete')
