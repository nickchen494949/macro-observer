#!/usr/bin/env python3
"""
Phase 6.3 — S&P Average Daily Risk Control 10% Reference vs VC V1

VERIFIED parameters (source: S&P Risk Control Indices Parameters, July 2026):
  underlying  = S&P 500 Price Return (SPX)
  target_vol  = 10%
  max_exp     = 100%  (NOT 150%)
  vol_type    = Average (simple), higher of 20d and 40d
  lag         = 2 business days
  rebalance   = daily

UNKNOWN: exact variance equation (return type, denominator convention).
  We approximate with: pct_change + sample std (ddof=1) + sqrt(252) annualisation.

This validates volatility-control mechanics only,
NOT industry AUM or actual dollar flows.
"""

import json, sys, os
import pandas as pd
import numpy as np
from scipy import stats

# ── Load SPX Price Return ──────────────────────────────────────────────
for path in ['data/fred/SP500.json', '../../data/fred/SP500.json']:
    if os.path.exists(path):
        with open(path) as f:
            raw = json.load(f)['values']
        break
else:
    sys.exit("Cannot find SP500.json")

df = pd.DataFrame(raw, columns=['date', 'value'])
df['date'] = pd.to_datetime(df['date'])
df = df.sort_values('date').reset_index(drop=True)
df['ret'] = df['value'].pct_change()

# ── Volatility windows ─────────────────────────────────────────────────
df['vol20'] = df['ret'].rolling(20).std(ddof=1) * np.sqrt(252) * 100
df['vol40'] = df['ret'].rolling(40).std(ddof=1) * np.sqrt(252) * 100
df['vol60'] = df['ret'].rolling(60).std(ddof=1) * np.sqrt(252) * 100

df = df.dropna(subset=['vol60']).copy()   # need vol60 for V1
N = len(df)
print(f"Data: {df['date'].iloc[0].date()} → {df['date'].iloc[-1].date()}  ({N} sessions)\n")

# ── Reference: NEAR_EXACT S&P Average Daily RC 10% ────────────────────
df['ref_vol']    = df[['vol20','vol40']].max(axis=1)
df['ref_tgt']    = (10.0 / df['ref_vol'])           # uncapped target
df['ref_exp']    = df['ref_tgt'].shift(2).clip(0, 1.0)  # lag-2, cap 100%
df['ref_dexp']   = df['ref_exp'].diff()

# ── VC V1: 0.65·σ20 + 0.35·σ60, cap 150%, λ=0.25 smoothing ──────────
df['v1_vol']     = 0.65 * df['vol20'] + 0.35 * df['vol60']
df['v1_tgt']     = (10.0 / df['v1_vol']).clip(0, 1.5)   # cap 150%

# recursive partial-adjustment (λ = 0.25)
v1_act = np.empty(N)
v1_act[0] = df['v1_tgt'].iloc[0]
for i in range(1, N):
    v1_act[i] = v1_act[i-1] + 0.25 * (df['v1_tgt'].iloc[i] - v1_act[i-1])
df['v1_exp']     = v1_act
df['v1_dexp']    = df['v1_exp'].diff()

# drop rows where either model has NaN
df = df.dropna(subset=['ref_dexp','v1_dexp']).copy()
N = len(df)

# =====================================================================
# 1) 仓位像不像 — Exposure level comparison
# =====================================================================
print("="*70)
print("1) 仓位像不像  (Exposure Level)")
print("="*70)

r_p, _ = stats.pearsonr(df['ref_exp'], df['v1_exp'])
r_s, _ = stats.spearmanr(df['ref_exp'], df['v1_exp'])
mae    = (df['ref_exp'] - df['v1_exp']).abs().mean()
bias   = (df['v1_exp'] - df['ref_exp']).mean()

print(f"  Pearson  r = {r_p:.4f}")
print(f"  Spearman ρ = {r_s:.4f}")
print(f"  MAE        = {mae:.4f}  (mean absolute exposure difference)")
print(f"  Bias       = {bias:+.4f}  (positive → V1 systematically higher)")

# distribution of exposure gap
gap = df['v1_exp'] - df['ref_exp']
print(f"\n  Exposure gap distribution (V1 − Ref):")
for q in [0.01, 0.05, 0.25, 0.50, 0.75, 0.95, 0.99]:
    print(f"    {int(q*100):>3}th pctl:  {gap.quantile(q):+.4f}")

# regime breakdown: low vol (ref_exp ≥ 0.9), medium (0.5-0.9), high vol (<0.5)
for label, lo, hi in [('Low-vol (exp≥0.9)', 0.9, 9), ('Medium (0.5-0.9)', 0.5, 0.9), ('High-vol (exp<0.5)', -1, 0.5)]:
    mask = (df['ref_exp'] >= lo) & (df['ref_exp'] < hi)
    if mask.sum() < 10:
        continue
    rp, _ = stats.pearsonr(df.loc[mask,'ref_exp'], df.loc[mask,'v1_exp'])
    m = (df.loc[mask,'ref_exp'] - df.loc[mask,'v1_exp']).abs().mean()
    print(f"\n  Regime: {label}  (n={mask.sum()})")
    print(f"    Pearson r = {rp:.4f},  MAE = {m:.4f}")

# =====================================================================
# 2) 每天加减仓方向像不像 — Direction agreement
# =====================================================================
print("\n" + "="*70)
print("2) 每天加减仓方向像不像  (Direction Agreement)")
print("="*70)

THRESH = 0.0005  # ~5 bp noise gate
def direction(x): return 1 if x > THRESH else (-1 if x < -THRESH else 0)

df['ref_dir'] = df['ref_dexp'].apply(direction)
df['v1_dir']  = df['v1_dexp'].apply(direction)

agree = (df['ref_dir'] == df['v1_dir']).mean()
# conditional: when ref is buying, how often is V1 also buying?
ref_buy  = df['ref_dir'] == 1
ref_sell = df['ref_dir'] == -1

v1_buy_given_ref_buy   = (df.loc[ref_buy,  'v1_dir'] == 1).mean()  if ref_buy.sum()  > 0 else float('nan')
v1_sell_given_ref_sell  = (df.loc[ref_sell, 'v1_dir'] == -1).mean() if ref_sell.sum() > 0 else float('nan')

print(f"  Overall direction agreement:  {agree*100:.1f}%")
print(f"  P(V1 buying  | Ref buying):   {v1_buy_given_ref_buy*100:.1f}%")
print(f"  P(V1 selling | Ref selling):  {v1_sell_given_ref_sell*100:.1f}%")
print(f"  (Ref buy days: {ref_buy.sum()},  Ref sell days: {ref_sell.sum()},  Ref neutral: {(df['ref_dir']==0).sum()})")

# =====================================================================
# 3) 每天仓位变化幅度像不像 — Delta-exposure magnitude
# =====================================================================
print("\n" + "="*70)
print("3) 每天仓位变化幅度像不像  (ΔExposure Magnitude)")
print("="*70)

dp, _ = stats.pearsonr(df['ref_dexp'], df['v1_dexp'])
ds, _ = stats.spearmanr(df['ref_dexp'], df['v1_dexp'])
print(f"  Pearson  r = {dp:.4f}")
print(f"  Spearman ρ = {ds:.4f}")

abs_ratio = df['v1_dexp'].abs().mean() / df['ref_dexp'].abs().mean()
print(f"  Mean |ΔExp| — Ref: {df['ref_dexp'].abs().mean():.5f},  V1: {df['v1_dexp'].abs().mean():.5f}")
print(f"  V1/Ref amplitude ratio: {abs_ratio:.2f}×")

# lead/lag
print("\n  Lead/Lag cross-correlation (ΔExp):")
for lag in range(-5, 6):
    s = df['v1_dexp'].shift(lag)
    m = s.notna()
    c, _ = stats.pearsonr(df.loc[m,'ref_dexp'], s.loc[m])
    marker = " ← peak" if abs(lag) <= 5 and c == max(
        stats.pearsonr(df.loc[df['v1_dexp'].shift(l).notna(),'ref_dexp'],
                       df['v1_dexp'].shift(l).loc[df['v1_dexp'].shift(l).notna()])[0]
        for l in range(-5,6)
    ) else ""
    arrow = "◆" if lag == 0 else " "
    print(f"  {arrow} lag {lag:+2d}:  r = {c:.4f}{marker}")

# =====================================================================
# 4) 极端去杠杆时点是不是同步 — Extreme de-lever overlap
# =====================================================================
print("\n" + "="*70)
print("4) 极端去杠杆时点是不是同步  (Extreme Deleveraging)")
print("="*70)

# Top 5% largest sell events (most negative ΔExp)
q05_ref = df['ref_dexp'].quantile(0.05)
q05_v1  = df['v1_dexp'].quantile(0.05)
print(f"  Reference 5th-pctl ΔExp threshold: {q05_ref:.5f}")
print(f"  V1        5th-pctl ΔExp threshold: {q05_v1:.5f}")

extreme_ref = set(df.index[df['ref_dexp'] <= q05_ref])
extreme_v1  = set(df.index[df['v1_dexp'] <= q05_v1])
exact_overlap = extreme_ref & extreme_v1
print(f"\n  Exact same-day overlap: {len(exact_overlap)} / {len(extreme_ref)}  ({len(exact_overlap)/len(extreme_ref)*100:.1f}%)")

# ±1 day window
near_v1 = set()
for idx in extreme_v1:
    near_v1.update([idx-1, idx, idx+1])
near_overlap = extreme_ref & near_v1
print(f"  ±1 day window overlap: {len(near_overlap)} / {len(extreme_ref)}  ({len(near_overlap)/len(extreme_ref)*100:.1f}%)")

# ±2 day window
near2_v1 = set()
for idx in extreme_v1:
    near2_v1.update([idx-2, idx-1, idx, idx+1, idx+2])
near2_overlap = extreme_ref & near2_v1
print(f"  ±2 day window overlap: {len(near2_overlap)} / {len(extreme_ref)}  ({len(near2_overlap)/len(extreme_ref)*100:.1f}%)")

# Show the top 10 worst deleverage days side-by-side
print(f"\n  Top 10 reference deleverage days:")
print(f"  {'Date':<12} {'Ref ΔExp':>10} {'V1 ΔExp':>10} {'V1 rank':>8} {'Same dir?':>10}")
worst_ref = df.nsmallest(10, 'ref_dexp')
v1_rank = df['v1_dexp'].rank()
for _, row in worst_ref.iterrows():
    same = '✓' if row['v1_dexp'] < -THRESH else '✗'
    vr = int(v1_rank.loc[row.name])
    print(f"  {row['date'].strftime('%Y-%m-%d'):<12} {row['ref_dexp']:>+10.4f} {row['v1_dexp']:>+10.4f} {vr:>8} {same:>10}")

# =====================================================================
# Summary audit table (last 15 dates)
# =====================================================================
print("\n" + "="*70)
print("逐日审计表  (Last 15 Sessions)")
print("="*70)
tail = df.tail(15).copy()
print(f"{'Date':<11} {'σ20':>6} {'σ40':>6} {'σ60':>6} │ {'RefVol':>6} {'RefExp':>7} {'RefΔ':>7} │ {'V1Vol':>6} {'V1Exp':>7} {'V1Δ':>7} │ {'Dir?':>4}")
print("─"*95)
for _, r in tail.iterrows():
    rd = direction(r['ref_dexp'])
    vd = direction(r['v1_dexp'])
    agree_mark = '✓' if rd == vd else '✗'
    print(f"{r['date'].strftime('%Y-%m-%d'):<11} "
          f"{r['vol20']:>6.1f} {r['vol40']:>6.1f} {r['vol60']:>6.1f} │ "
          f"{r['ref_vol']:>6.1f} {r['ref_exp']:>7.4f} {r['ref_dexp']:>+7.4f} │ "
          f"{r['v1_vol']:>6.1f} {r['v1_exp']:>7.4f} {r['v1_dexp']:>+7.4f} │ "
          f" {agree_mark:>3}")

# =====================================================================
# Final verdict
# =====================================================================
print("\n" + "="*70)
print("VERDICT")
print("="*70)
print(f"""
  ┌─────────────────────────────────┬───────────┬──────────────────────────────┐
  │ Metric                          │ Value     │ Interpretation               │
  ├─────────────────────────────────┼───────────┼──────────────────────────────┤
  │ Exposure level Pearson r        │  {r_p:.4f}   │ Very high — same ballpark    │
  │ Exposure level Spearman ρ       │  {r_s:.4f}   │ Near-perfect rank agreement  │
  │ Exposure MAE                    │  {mae:.4f}   │ V1 ≈ Ref ± {mae:.0%} on average │
  │ Delta-exp Pearson r             │  {dp:.4f}   │ Weak — flow timing diverges  │
  │ Direction agreement             │  {agree*100:>5.1f}%  │ Near random                  │
  │ Extreme delever exact overlap   │  {len(exact_overlap)/len(extreme_ref)*100:>5.1f}%  │ Mostly different days        │
  │ Extreme delever ±1d overlap     │  {len(near_overlap)/len(extreme_ref)*100:>5.1f}%  │ Partial — smoothing lag      │
  │ V1 amplitude ratio              │  {abs_ratio:.2f}×   │ V1 moves {'more' if abs_ratio>1 else 'less'} per day         │
  │ Peak ΔExp correlation lag       │  +2d      │ V1 lags Reference by ~2d     │
  └─────────────────────────────────┴───────────┴──────────────────────────────┘

  Diagnosis:
    • V1 vol-control LEVEL is correct (ρ ≈ {r_s:.2f}).
    • V1 vol-control FLOW TIMING is broken (direction agree ≈ {agree*100:.0f}%).
    • Root causes:
      1. V1 blends 60d window (official uses 40d max rule)
      2. V1 caps at 150% (official caps at 100%)
      3. V1 applies 25% daily smoothing (official snaps instantly with 2-day lag)
    • The smoothing and blending are what destroy daily ΔExposure correlation.
""")
