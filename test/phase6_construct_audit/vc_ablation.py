#!/usr/bin/env python3
"""
Phase 6.4 — Vol Control Mechanism Ablation

Starting from VC V1, change ONE mechanism at a time to identify
which structural design choice causes poor daily flow agreement.

Variants:
  A. V1 baseline         (0.65·σ20+0.35·σ60, cap 150%, λ=0.25, no lag)
  B. Cap only            → cap 100%
  C. Vol rule only       → max(σ20, σ40)
  D. Smoothing only      → instant snap (λ=1.0)
  E. Lag only            → T-2 observation lag
  F. Full S&P reference  → max(σ20,σ40) + cap 100% + instant + T-2 lag

Reference: NEAR_EXACT S&P Average Daily RC 10%
           max(σ20,σ40), cap 100%, instant snap, T-2 lag

Lag sign convention:
  corr(Ref[t], Variant[t - lag])
  lag > 0 → Variant is DELAYED (reacts after Reference)
  lag < 0 → Variant is EARLY  (reacts before Reference)

This validates volatility-control mechanics only,
NOT industry AUM or actual dollar flows.
"""

import json, os, sys, textwrap
import pandas as pd
import numpy as np
from scipy import stats
from collections import OrderedDict

# ── Load ───────────────────────────────────────────────────────────────
for p in ['data/fred/SP500.json', '../../data/fred/SP500.json']:
    if os.path.exists(p):
        with open(p) as f:
            raw = json.load(f)['values']
        break
else:
    sys.exit("SP500.json not found")

df = pd.DataFrame(raw, columns=['date','value'])
df['date'] = pd.to_datetime(df['date'])
df = df.sort_values('date').reset_index(drop=True)
df['ret'] = df['value'].pct_change()
df['vol20'] = df['ret'].rolling(20).std(ddof=1) * np.sqrt(252) * 100
df['vol40'] = df['ret'].rolling(40).std(ddof=1) * np.sqrt(252) * 100
df['vol60'] = df['ret'].rolling(60).std(ddof=1) * np.sqrt(252) * 100
df = df.dropna(subset=['vol60']).copy()
N = len(df)

# ── Reference: S&P Average Daily RC 10% ──────────────────────────────
df['ref_vol'] = df[['vol20','vol40']].max(axis=1)
df['ref_tgt'] = 10.0 / df['ref_vol']
df['ref_exp'] = df['ref_tgt'].shift(2).clip(0, 1.0)
df['ref_dexp'] = df['ref_exp'].diff()

# ── Build variants ────────────────────────────────────────────────────
def build_variant(vol_rule, cap, smoothing_lambda, lag_days, label):
    """
    vol_rule: 'v1_blend' or 'sp_max'
    cap: float (1.0 or 1.5)
    smoothing_lambda: float (0.25 = V1 partial, 1.0 = instant)
    lag_days: int (0 or 2)
    """
    if vol_rule == 'v1_blend':
        vol = 0.65 * df['vol20'] + 0.35 * df['vol60']
    else:  # sp_max
        vol = df[['vol20','vol40']].max(axis=1)

    tgt = (10.0 / vol).clip(0, cap)

    if lag_days > 0:
        tgt_lagged = tgt.shift(lag_days)
    else:
        tgt_lagged = tgt

    # apply smoothing
    arr = tgt_lagged.values.copy()
    exp = np.empty(N)
    # seed: first non-NaN target
    first_valid = np.where(~np.isnan(arr))[0]
    if len(first_valid) == 0:
        return None
    seed_idx = first_valid[0]
    exp[:seed_idx+1] = np.nan
    exp[seed_idx] = arr[seed_idx]
    for i in range(seed_idx+1, N):
        if np.isnan(arr[i]):
            exp[i] = exp[i-1]
        else:
            exp[i] = exp[i-1] + smoothing_lambda * (arr[i] - exp[i-1])

    # clip after smoothing too (for cap variants)
    exp = np.clip(exp, 0, cap)

    col_exp  = f'{label}_exp'
    col_dexp = f'{label}_dexp'
    df[col_exp]  = exp
    df[col_dexp] = pd.Series(exp).diff().values
    return col_exp, col_dexp

variants = OrderedDict()
variants['A'] = ('V1 baseline',           'v1_blend', 1.5, 0.25, 0)
variants['B'] = ('Cap→100%',              'v1_blend', 1.0, 0.25, 0)
variants['C'] = ('Vol→max(20,40)',        'sp_max',   1.5, 0.25, 0)
variants['D'] = ('Smoothing→instant',     'v1_blend', 1.5, 1.0,  0)
variants['E'] = ('Lag→T-2',              'v1_blend', 1.5, 0.25, 2)
variants['F'] = ('Full S&P rules',        'sp_max',   1.0, 1.0,  2)

cols = {}
for key, (label, vr, cap, lam, lag) in variants.items():
    tag = key.lower()
    result = build_variant(vr, cap, lam, lag, tag)
    if result:
        cols[key] = result

# trim to rows where reference and all variants have data
keep = df['ref_dexp'].notna()
for key in cols:
    col_exp, col_dexp = cols[key]
    keep = keep & df[col_dexp].notna()
df = df[keep].copy()
N = len(df)
print(f"Data: {df['date'].iloc[0].date()} → {df['date'].iloc[-1].date()}  ({N} sessions)\n")

# ── Metrics ───────────────────────────────────────────────────────────
THRESH = 0.0005

def direction(x):
    if x > THRESH: return 1
    if x < -THRESH: return -1
    return 0

def compute_metrics(key):
    label = variants[key][0]
    col_exp, col_dexp = cols[key]

    vexp  = df[col_exp].values
    vdexp = df[col_dexp].values
    rexp  = df['ref_exp'].values
    rdexp = df['ref_dexp'].values

    m = {}
    m['label'] = label

    # 1. Exposure level
    m['exp_pearson'], _  = stats.pearsonr(rexp, vexp)
    m['exp_spearman'], _ = stats.spearmanr(rexp, vexp)
    m['exp_mae']         = np.abs(rexp - vexp).mean()
    m['exp_bias']        = (vexp - rexp).mean()

    # 2. Delta exposure
    m['dexp_pearson'], _  = stats.pearsonr(rdexp, vdexp)
    m['dexp_spearman'], _ = stats.spearmanr(rdexp, vdexp)
    m['mean_abs_dexp_ref'] = np.abs(rdexp).mean()
    m['mean_abs_dexp_var'] = np.abs(vdexp).mean()

    # 3. Direction
    rdir = np.array([direction(x) for x in rdexp])
    vdir = np.array([direction(x) for x in vdexp])

    m['dir_agree'] = (rdir == vdir).mean()

    # confusion matrix
    # rows = ref direction, cols = variant direction
    cm = np.zeros((3,3), dtype=int)  # sell(-1), neutral(0), buy(1) → index 0,1,2
    for r, v in zip(rdir, vdir):
        cm[r+1][v+1] += 1
    m['confusion'] = cm
    m['n_ref_buy']  = (rdir == 1).sum()
    m['n_ref_sell'] = (rdir == -1).sum()
    m['n_ref_neut'] = (rdir == 0).sum()

    # naive baseline: always predict most common class
    most_common = max(m['n_ref_buy'], m['n_ref_sell'], m['n_ref_neut'])
    m['naive_baseline'] = most_common / N

    # conditional
    buy_mask  = rdir == 1
    sell_mask = rdir == -1
    m['p_var_buy_given_ref_buy']   = (vdir[buy_mask] == 1).mean()  if buy_mask.sum() > 0 else float('nan')
    m['p_var_sell_given_ref_sell']  = (vdir[sell_mask] == -1).mean() if sell_mask.sum() > 0 else float('nan')

    # 4. Extreme events — top 5% absolute delta
    q95r = np.percentile(np.abs(rdexp), 95)
    q95v = np.percentile(np.abs(vdexp), 95)
    extreme_ref = set(np.where(np.abs(rdexp) >= q95r)[0])
    extreme_var = set(np.where(np.abs(vdexp) >= q95v)[0])

    exact = extreme_ref & extreme_var
    m['extreme_exact'] = len(exact)
    m['extreme_total'] = len(extreme_ref)

    near1 = set()
    for i in extreme_var:
        near1.update([i-1, i, i+1])
    m['extreme_pm1'] = len(extreme_ref & near1)

    near2 = set()
    for i in extreme_var:
        near2.update(range(i-2, i+3))
    m['extreme_pm2'] = len(extreme_ref & near2)

    # 5. Lead/lag
    lags = {}
    for lag in range(-5, 6):
        s = pd.Series(vdexp).shift(lag)
        valid = s.notna()
        c, _ = stats.pearsonr(rdexp[valid], s[valid])
        lags[lag] = c
    m['leadlag'] = lags
    m['peak_lag'] = max(lags, key=lags.get)

    # 6. Top 20 deleverage events
    idx_worst20 = np.argsort(rdexp)[:20]
    delever_rows = []
    for i in idx_worst20:
        delever_rows.append({
            'date': df.iloc[i]['date'],
            'ref_dexp': rdexp[i],
            'var_dexp': vdexp[i],
            'same_dir': vdexp[i] < -THRESH
        })
    m['delever_top20'] = delever_rows

    return m

# ── Run all variants ──────────────────────────────────────────────────
results = OrderedDict()
for key in variants:
    results[key] = compute_metrics(key)

# ── Print ─────────────────────────────────────────────────────────────
print("="*90)
print("ABLATION SUMMARY TABLE")
print("="*90)

header = f"{'Var':>3} {'Description':<22} │ {'ExpρS':>6} {'ExpMAE':>6} {'Bias':>6} │ {'ΔρP':>6} {'ΔρS':>6} {'Dir%':>5} │ {'Ext%':>5} {'±1d%':>5} {'±2d%':>5} │ {'Peak':>4}"
print(header)
print("─"*90)
for key, m in results.items():
    ext_pct = m['extreme_exact']/m['extreme_total']*100 if m['extreme_total']>0 else 0
    pm1_pct = m['extreme_pm1']/m['extreme_total']*100 if m['extreme_total']>0 else 0
    pm2_pct = m['extreme_pm2']/m['extreme_total']*100 if m['extreme_total']>0 else 0
    print(f"  {key} {m['label']:<22} │ "
          f"{m['exp_spearman']:>6.3f} {m['exp_mae']:>6.3f} {m['exp_bias']:>+6.3f} │ "
          f"{m['dexp_pearson']:>6.3f} {m['dexp_spearman']:>6.3f} {m['dir_agree']*100:>5.1f} │ "
          f"{ext_pct:>5.1f} {pm1_pct:>5.1f} {pm2_pct:>5.1f} │ "
          f"{m['peak_lag']:>+4d}")
print()

# ── Detailed per-variant reports ──────────────────────────────────────
for key, m in results.items():
    print("="*90)
    print(f"Variant {key}: {m['label']}")
    desc = variants[key]
    print(f"  vol_rule={desc[1]}, cap={desc[2]}, λ={desc[3]}, lag={desc[4]}")
    print("="*90)

    print(f"\n  Exposure Level:")
    print(f"    Pearson r  = {m['exp_pearson']:.4f}")
    print(f"    Spearman ρ = {m['exp_spearman']:.4f}")
    print(f"    MAE        = {m['exp_mae']:.4f}")
    print(f"    Bias       = {m['exp_bias']:+.4f}")

    print(f"\n  ΔExposure:")
    print(f"    Pearson r  = {m['dexp_pearson']:.4f}")
    print(f"    Spearman ρ = {m['dexp_spearman']:.4f}")
    print(f"    Mean |Δ| ref = {m['mean_abs_dexp_ref']:.5f},  var = {m['mean_abs_dexp_var']:.5f}")

    print(f"\n  Direction Confusion Matrix  (rows=Ref, cols=Variant)")
    cm = m['confusion']
    labels = ['Sell','Neut','Buy']
    print(f"    {'':>8}  {'V:Sell':>6} {'V:Neut':>6} {'V:Buy':>6}  │ {'Total':>6}")
    print(f"    {'─'*42}")
    for i, rl in enumerate(labels):
        row_total = cm[i].sum()
        print(f"    R:{rl:<5}  {cm[i][0]:>6d} {cm[i][1]:>6d} {cm[i][2]:>6d}  │ {row_total:>6d}")
    print(f"\n    Overall agreement:        {m['dir_agree']*100:.1f}%")
    print(f"    Naive baseline (majority): {m['naive_baseline']*100:.1f}%")
    print(f"    P(V buy | R buy):          {m['p_var_buy_given_ref_buy']*100:.1f}%")
    print(f"    P(V sell | R sell):         {m['p_var_sell_given_ref_sell']*100:.1f}%")

    print(f"\n  Extreme Events (top 5% |ΔExp|):")
    print(f"    Exact same-day: {m['extreme_exact']}/{m['extreme_total']}  ({m['extreme_exact']/m['extreme_total']*100:.1f}%)")
    print(f"    ±1 day window:  {m['extreme_pm1']}/{m['extreme_total']}  ({m['extreme_pm1']/m['extreme_total']*100:.1f}%)")
    print(f"    ±2 day window:  {m['extreme_pm2']}/{m['extreme_total']}  ({m['extreme_pm2']/m['extreme_total']*100:.1f}%)")

    print(f"\n  Lead/Lag (ΔExp Pearson):")
    peak = m['peak_lag']
    for lag in range(-5, 6):
        c = m['leadlag'][lag]
        marker = " ← PEAK" if lag == peak else ""
        arrow = "◆" if lag == 0 else " "
        print(f"    {arrow} lag {lag:+2d}: r = {c:.4f}{marker}")

    print(f"\n  Top 20 Ref Deleverage Days:")
    print(f"    {'Date':<12} {'RefΔ':>8} {'VarΔ':>8} {'Dir?':>5}")
    for row in m['delever_top20']:
        mark = '✓' if row['same_dir'] else '✗'
        print(f"    {row['date'].strftime('%Y-%m-%d'):<12} {row['ref_dexp']:>+8.4f} {row['var_dexp']:>+8.4f} {mark:>5}")

    print()

# ── Final Answers ─────────────────────────────────────────────────────
print("="*90)
print("ABLATION ANSWERS")
print("="*90)

# Compare key metrics across variants to attribute causes
a = results['A']  # baseline
b = results['B']  # cap only
c = results['C']  # vol rule only
d = results['D']  # smoothing only
e = results['E']  # lag only
f = results['F']  # full S&P

print(f"""
Q1: Which assumption primarily causes exposure-level BIAS?
    A (baseline)   bias = {a['exp_bias']:+.4f}
    B (cap→100%)   bias = {b['exp_bias']:+.4f}   Δ = {b['exp_bias']-a['exp_bias']:+.4f}
    C (vol rule)   bias = {c['exp_bias']:+.4f}   Δ = {c['exp_bias']-a['exp_bias']:+.4f}
    D (no smooth)  bias = {d['exp_bias']:+.4f}   Δ = {d['exp_bias']-a['exp_bias']:+.4f}
    E (lag T-2)    bias = {e['exp_bias']:+.4f}   Δ = {e['exp_bias']-a['exp_bias']:+.4f}
    F (full S&P)   bias = {f['exp_bias']:+.4f}   Δ = {f['exp_bias']-a['exp_bias']:+.4f}
    → Biggest bias reduction from A→?: {'B (cap)' if abs(b['exp_bias']) < abs(c['exp_bias']) and abs(b['exp_bias']) < abs(d['exp_bias']) else 'see above'}

Q2: Which assumption primarily causes TIMING error?
    A (baseline)   ΔρP = {a['dexp_pearson']:.4f},  dir = {a['dir_agree']*100:.1f}%
    B (cap→100%)   ΔρP = {b['dexp_pearson']:.4f},  dir = {b['dir_agree']*100:.1f}%
    C (vol rule)   ΔρP = {c['dexp_pearson']:.4f},  dir = {c['dir_agree']*100:.1f}%
    D (no smooth)  ΔρP = {d['dexp_pearson']:.4f},  dir = {d['dir_agree']*100:.1f}%
    E (lag T-2)    ΔρP = {e['dexp_pearson']:.4f},  dir = {e['dir_agree']*100:.1f}%
    F (full S&P)   ΔρP = {f['dexp_pearson']:.4f},  dir = {f['dir_agree']*100:.1f}%

Q3: Which assumption primarily suppresses EXTREME-EVENT magnitude?
    Top 20 delever: count where variant also sells (same dir):
    A (baseline)   {sum(1 for r in a['delever_top20'] if r['same_dir'])}/20
    B (cap→100%)   {sum(1 for r in b['delever_top20'] if r['same_dir'])}/20
    C (vol rule)   {sum(1 for r in c['delever_top20'] if r['same_dir'])}/20
    D (no smooth)  {sum(1 for r in d['delever_top20'] if r['same_dir'])}/20
    E (lag T-2)    {sum(1 for r in e['delever_top20'] if r['same_dir'])}/20
    F (full S&P)   {sum(1 for r in f['delever_top20'] if r['same_dir'])}/20

    Top-5% exact-day overlap:
    A: {a['extreme_exact']}/{a['extreme_total']}  B: {b['extreme_exact']}/{b['extreme_total']}  C: {c['extreme_exact']}/{c['extreme_total']}  D: {d['extreme_exact']}/{d['extreme_total']}  E: {e['extreme_exact']}/{e['extreme_total']}  F: {f['extreme_exact']}/{f['extreme_total']}

Q4: Does fixing ONE mechanism recover most of the reference agreement?
    Compare ΔExp Pearson jumps:
    A→B (cap):       {a['dexp_pearson']:.4f} → {b['dexp_pearson']:.4f}  (Δ = {b['dexp_pearson']-a['dexp_pearson']:+.4f})
    A→C (vol rule):  {a['dexp_pearson']:.4f} → {c['dexp_pearson']:.4f}  (Δ = {c['dexp_pearson']-a['dexp_pearson']:+.4f})
    A→D (smooth):    {a['dexp_pearson']:.4f} → {d['dexp_pearson']:.4f}  (Δ = {d['dexp_pearson']-a['dexp_pearson']:+.4f})
    A→E (lag):       {a['dexp_pearson']:.4f} → {e['dexp_pearson']:.4f}  (Δ = {e['dexp_pearson']-a['dexp_pearson']:+.4f})
    A→F (full S&P):  {a['dexp_pearson']:.4f} → {f['dexp_pearson']:.4f}  (Δ = {f['dexp_pearson']-a['dexp_pearson']:+.4f})
""")
