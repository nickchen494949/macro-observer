#!/usr/bin/env python3
"""
🔪 5-KNIFE AUDIT v2 — RF Sector Rotation (all bugs fixed)
===========================================================
Fixes from code review:
  1. 🔴 Next-day execution: return = close[T+1]→close[T+2], not close[T]→close[T+1]
  2. 🔴 Placebo: 500 iterations with different seeds, empirical p-value
  3. 🟠 Group permutation: shuffle ALL features in group simultaneously
  4. 🟠 Exclude-2022: purge from BOTH test AND training
  5. 🟠 README coverage: XLC from 2018-06, XLRE from 2016-01
"""

import os, json, warnings
import pandas as pd, numpy as np
from scipy import stats
from sklearn.ensemble import RandomForestRegressor

warnings.filterwarnings('ignore')

PROJ = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
PE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pe_data')
SECTORS = ['XLK','XLC','XLY','XLF','XLI','XLU','XLE','XLRE','XLB','XLP','XLV']
PE_MAP = {
    '20517_information_technology.csv':'XLK','20518_communication_services.csv':'XLC',
    '20519_consumer_discretionary.csv':'XLY','20520_financials.csv':'XLF',
    '20521_industrials.csv':'XLI','20522_utilities.csv':'XLU',
    '20523_energy.csv':'XLE','20524_real_estate.csv':'XLRE',
    '20525_materials.csv':'XLB','20526_consumer_staples.csv':'XLP',
    '20527_health_care.csv':'XLV',
}
NAMES = {'XLK':'Tech','XLC':'Comm','XLY':'Disc','XLF':'Fin','XLI':'Ind',
         'XLU':'Util','XLE':'Enrg','XLRE':'RE','XLB':'Mat','XLP':'Stpl','XLV':'Hlth'}

FEAT_COLS = ['f_valuation','f_eps_rev','f_eps_rev_1m','f_mom6','f_mom3',
             'f_mom1','f_pe_level','f_pe_chg3','f_dist_high6']
START = '2019-01'
END = '2026-06'

# ══════════════════════════════════════════════════
# DATA
# ══════════════════════════════════════════════════
def load_pe():
    frames = []
    for fname, ticker in PE_MAP.items():
        fp = os.path.join(PE_DIR, fname)
        if not os.path.exists(fp): continue
        df = pd.read_csv(fp); df.columns = [c.strip() for c in df.columns]
        df['date'] = pd.to_datetime(df['date'])
        df = df.dropna(subset=['forward_pe']).set_index('date').sort_index()
        # XLC first-day anomaly: 10.13x → 21.66x next day. Drop first row.
        if ticker == 'XLC' and len(df) > 1 and df['forward_pe'].iloc[0] < 12:
            df = df.iloc[1:]
        m = df['forward_pe'].resample('ME').last().dropna().to_frame('fpe')
        m['ticker'] = ticker; frames.append(m.reset_index())
    return pd.concat(frames, ignore_index=True)

def load_prices():
    prices = {}; need = []
    for t in SECTORS + ['TLT','SPY','QQQ']:
        fp = os.path.join(PROJ, 'data', 'yahoo', t.replace('^','_') + '.json')
        if os.path.exists(fp):
            with open(fp) as f: d = json.load(f)
            df = pd.DataFrame(d['values'], columns=['date','close'])
            df['date'] = pd.to_datetime(df['date']); df = df.set_index('date').sort_index()
            df['close'] = pd.to_numeric(df['close'], errors='coerce')
            if len(df) > 100: prices[t] = df; continue
        need.append(t)
    if need:
        import yfinance as yf, time
        for t in need:
            try:
                h = yf.Ticker(t).history(start='2002-01-01',end='2026-09-01',interval='1d')
                if not h.empty:
                    df = pd.DataFrame({'close':h['Close']})
                    df.index = df.index.tz_localize(None); prices[t] = df
                time.sleep(1.5)
            except: pass
    return prices

def to_monthly(prices):
    frames = []
    for t, df in prices.items():
        if df.index.tz is not None: df = df.copy(); df.index = df.index.tz_localize(None)
        m = df['close'].resample('ME').last().dropna().to_frame('close')
        m['ticker'] = t; frames.append(m.reset_index())
    p = pd.concat(frames, ignore_index=True)
    p['date'] = pd.to_datetime(p['date']).dt.tz_localize(None)
    return p.sort_values(['date','ticker']).reset_index(drop=True)

def build_features(panel, pe, exclude_tickers=None):
    tickers = [t for t in SECTORS if t not in (exclude_tickers or [])]
    sector_panel = panel[panel['ticker'].isin(tickers)].copy()
    m = sector_panel.merge(pe[['date','ticker','fpe']], on=['date','ticker'], how='left')
    m.loc[(m['fpe'] > 50) | (m['fpe'] <= 0), 'fpe'] = np.nan
    all_feat = []
    for t in tickers:
        s = m[m['ticker'] == t].sort_values('date').copy()
        if len(s) < 25: continue
        s['f_valuation'] = -s['fpe'].rolling(24, min_periods=12).apply(
            lambda x: (x.iloc[-1] - x.mean()) / (x.std() + 1e-9))
        s['fwd_eps'] = s['close'] / s['fpe']
        s['f_eps_rev'] = s['fwd_eps'].pct_change(3).clip(-0.5, 0.5)
        s['f_eps_rev_1m'] = s['fwd_eps'].pct_change(1).clip(-0.3, 0.3)
        s['f_mom6'] = s['close'].pct_change(6)
        s['f_mom3'] = s['close'].pct_change(3)
        s['f_mom1'] = s['close'].pct_change(1)
        s['f_pe_level'] = s['fpe']
        s['f_pe_chg3'] = s['fpe'].pct_change(3)
        s['f_dist_high6'] = s['close'] / s['close'].rolling(6).max() - 1
        # 3M target for training (used with embargo)
        s['fwd_ret_3m'] = s['close'].pct_change(3).shift(-3)

        # ══════════════════════════════════════════════════
        # FIX #1: NEXT-DAY EXECUTION
        # ══════════════════════════════════════════════════
        # Old (same-close bug):
        #   fwd_ret_1m = close.pct_change(1).shift(-1)
        #   At T: return = close[T+1]/close[T] - 1
        #   Problem: close[T] used in signal AND as entry price
        #
        # Fixed:
        #   fwd_ret_exec = close.pct_change(1).shift(-2)
        #   At T: return = close[T+2]/close[T+1] - 1
        #   Signal at T → execute at close[T+1] → exit at close[T+2]
        #   No same-close bias.
        s['fwd_ret_exec'] = s['close'].pct_change(1).shift(-2)

        all_feat.append(s)
    df = pd.concat(all_feat, ignore_index=True)
    df['fwd_ret_3m_median'] = df.groupby('date')['fwd_ret_3m'].transform('median')
    df['target'] = df['fwd_ret_3m'] - df['fwd_ret_3m_median']
    feat_xs = []
    for c in FEAT_COLS:
        zc = c + '_xs'
        df[zc] = df.groupby('date')[c].transform(
            lambda x: (x - x.mean()) / (x.std() + 1e-9) if x.std() > 0 else 0)
        feat_xs.append(zc)
    return df, feat_xs

# ══════════════════════════════════════════════════
# WALK-FORWARD (PURGED, FIXED)
# ══════════════════════════════════════════════════
def walk_forward_purged(df, feat_xs, top_n=1, start=START, end=END,
                        embargo_months=3, exclude_years_test=None,
                        exclude_years_train=None,
                        shuffle_labels=False, shuffle_seed=42,
                        shuffle_features=None):
    """
    Walk-forward with purge/embargo.

    FIX #3: shuffle_features now takes a LIST and shuffles ALL of them.
    FIX #4: exclude_years_train removes years from training too.
    """
    dates = sorted(df['date'].unique())
    dates = [d for d in dates if pd.Timestamp(start) <= d <= pd.Timestamp(end)]
    if exclude_years_test:
        dates = [d for d in dates if d.year not in exclude_years_test]

    results = []
    rng = np.random.RandomState(shuffle_seed)

    for pred_date in dates:
        cutoff = pred_date - pd.DateOffset(months=embargo_months)
        train = df[df['date'] <= cutoff].dropna(subset=feat_xs + ['target'])

        # FIX #4: also exclude years from training if requested
        if exclude_years_train:
            train = train[~train['date'].dt.year.isin(exclude_years_train)]

        test = df[df['date'] == pred_date].dropna(subset=feat_xs)

        if len(train) < 100 or len(test) < 4:
            continue

        X_tr = train[feat_xs].values
        y_tr = train['target'].values

        if shuffle_labels:
            y_tr = rng.permutation(y_tr)

        X_te = test[feat_xs].values.copy()

        # FIX #3: shuffle ALL features in the list, not just [0]
        if shuffle_features:
            for sf in shuffle_features:
                if sf in feat_xs:
                    idx = feat_xs.index(sf)
                    X_te[:, idx] = rng.permutation(X_te[:, idx])

        mdl = RandomForestRegressor(n_estimators=200, max_depth=4,
                min_samples_leaf=10, random_state=42, n_jobs=-1)
        mdl.fit(X_tr, y_tr)
        preds = mdl.predict(X_te)

        test = test.copy(); test['pred'] = preds
        test = test.sort_values('pred', ascending=False)
        top = test.head(top_n)
        bot = test.tail(top_n)

        # FIX #1: use fwd_ret_exec (next-day execution), not fwd_ret_1m
        top_ret = top['fwd_ret_exec'].mean() if top['fwd_ret_exec'].notna().any() else np.nan
        bot_ret = bot['fwd_ret_exec'].mean() if bot['fwd_ret_exec'].notna().any() else np.nan
        ew = test['fwd_ret_exec'].mean()
        ic = stats.spearmanr(test['pred'], test['fwd_ret_exec'])[0] \
            if len(test) >= 5 and test['fwd_ret_exec'].notna().sum() >= 5 else np.nan

        results.append({
            'date': pred_date, 'top_ret': top_ret, 'bot_ret': bot_ret,
            'spread': top_ret - bot_ret if pd.notna(bot_ret) else np.nan,
            'ew': ew, 'ic': ic, 'top1': top['ticker'].iloc[0],
            'picks': ','.join(top['ticker'].tolist()),
        })

    return pd.DataFrame(results)

def metrics(rets, label=''):
    r = pd.Series(rets).dropna()
    n = len(r)
    if n < 4: return None
    cum = (1+r).cumprod()
    years = n/12
    cagr = cum.iloc[-1]**(1/years)-1 if years > 0 else 0
    vol = r.std()*np.sqrt(12)
    sharpe = (r.mean()*12)/vol if vol > 0 else 0
    down = r[r<0]
    dv = down.std()*np.sqrt(12) if len(down)>1 else vol
    sortino = (r.mean()*12)/dv if dv > 0 else 0
    peak = cum.cummax(); mdd = ((cum-peak)/peak).min()
    return {'label':label,'cagr':cagr,'sharpe':sharpe,'sortino':sortino,
            'mdd':mdd,'n':n,'wr':(r>0).mean()}

def fmt(m):
    return (f"{m['label']:<35s} {m['cagr']*100:+6.1f}% {m['sharpe']:6.2f}  "
            f"{m['sortino']:6.2f}  {m['mdd']*100:6.1f}% {m['wr']*100:4.0f}% {m['n']:4d}")

HDR = f"{'Test':<35s} {'CAGR':>7s} {'Sharpe':>7s} {'Sortino':>8s} {'MaxDD':>7s} {'WR':>5s} {'N':>5s}"

# ══════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════
print('='*85)
print('🔪 5-KNIFE AUDIT v2 — ALL BUGS FIXED')
print('='*85)
print()
print('  Fixes applied:')
print('    1. 🔴 Next-day execution: return = close[T+1]→close[T+2]')
print('    2. 🔴 Placebo: 500 iterations, empirical p-value')
print('    3. 🟠 Group permutation: shuffle ALL features in group')
print('    4. 🟠 Exclude-2022: purged from BOTH test AND training')
print('    5. 🟠 XLC first-day anomaly (10.13x) dropped')

pe = load_pe()
prices = load_prices()
panel = to_monthly(prices)
df_noXLE, feat_xs = build_features(panel, pe, exclude_tickers=['XLE'])
df_all, _ = build_features(panel, pe)
print(f'\n  Data: {len(df_noXLE):,d} rows (no XLE), {len(feat_xs)} features')

# ═══════════════════════════════════════════════
# KNIFE 1: Same-close vs Next-day execution
# ═══════════════════════════════════════════════
print('\n' + '='*85)
print('🔪 KNIFE 1: Next-Day Execution (THE critical fix)')
print('='*85)
print('  Old: signal at T, return from close[T] → close[T+1] (same-close)')
print('  New: signal at T, return from close[T+1] → close[T+2] (next-day)')
print()
print(HDR)
print('─'*85)

# Run with next-day execution (the fix)
rdf_fixed = walk_forward_purged(df_noXLE, feat_xs, top_n=1, embargo_months=3)
m_fixed = metrics(rdf_fixed['top_ret'], 'RF noXLE Top1 (next-day)')
m_fixed_sp = metrics(rdf_fixed['spread'], 'spread (next-day)')

rdf_fixed3 = walk_forward_purged(df_noXLE, feat_xs, top_n=3, embargo_months=3)
m_fixed3 = metrics(rdf_fixed3['top_ret'], 'RF noXLE Top3 (next-day)')
m_fixed3_sp = metrics(rdf_fixed3['spread'], 'spread Top3 (next-day)')

for m in [m_fixed, m_fixed3]:
    if m: print(fmt(m))
print()
for m in [m_fixed_sp, m_fixed3_sp]:
    if m: print(fmt(m))

# ═══════════════════════════════════════════════
# KNIFE 2: Sector Concentration + LOSO
# ═══════════════════════════════════════════════
print('\n' + '='*85)
print('🔪 KNIFE 2: Sector Picks + Leave-One-Sector-Out')
print('='*85)

if len(rdf_fixed) > 0:
    print('\n  Sector pick frequency (RF noXLE Top1, next-day execution):')
    counts = rdf_fixed['top1'].value_counts()
    total = len(rdf_fixed)
    for t, c in counts.items():
        bar = '█' * int(c / total * 40)
        print(f'    {NAMES.get(t,t):<6s} ({t}): {c:3d}/{total} = {c/total*100:4.1f}%  {bar}')

print(f'\n  LOSO (next-day, purged, Top1):')
print(f'  {HDR}')
print('  ' + '─'*85)

loso_results = []
for excluded in [t for t in SECTORS if t != 'XLE']:
    df_loso, fx = build_features(panel, pe, exclude_tickers=['XLE', excluded])
    rdf_loso = walk_forward_purged(df_loso, fx, top_n=1, embargo_months=3)
    m_loso = metrics(rdf_loso['top_ret'], f'excl XLE+{excluded}')
    if m_loso:
        print(f'  {fmt(m_loso)}')
        loso_results.append(m_loso)

if loso_results:
    cagrs = [m['cagr'] for m in loso_results]
    print(f'\n  LOSO CAGR: {min(cagrs)*100:+.1f}% → {max(cagrs)*100:+.1f}%, '
          f'mean {np.mean(cagrs)*100:+.1f}% ± {np.std(cagrs)*100:.1f}%')

# ═══════════════════════════════════════════════
# KNIFE 3: Exclude 2022 (from training AND test)
# ═══════════════════════════════════════════════
print('\n' + '='*85)
print('🔪 KNIFE 3: Exclude 2022 (test + training)')
print('='*85)
print()
print(HDR)
print('─'*85)

# Test only excluded (old way — can still learn from 2022)
rdf_no22_test = walk_forward_purged(df_noXLE, feat_xs, top_n=1,
    embargo_months=3, exclude_years_test=[2022])
m_no22t = metrics(rdf_no22_test['top_ret'], 'excl 2022 test only')

# Both test AND train excluded (strict)
rdf_no22_both = walk_forward_purged(df_noXLE, feat_xs, top_n=1,
    embargo_months=3, exclude_years_test=[2022], exclude_years_train=[2022])
m_no22b = metrics(rdf_no22_both['top_ret'], 'excl 2022 test+train (strict)')

for m in [m_fixed, m_no22t, m_no22b]:
    if m: print(fmt(m))

# ═══════════════════════════════════════════════
# KNIFE 4: OOS Permutation Importance (fixed groups)
# ═══════════════════════════════════════════════
print('\n' + '='*85)
print('🔪 KNIFE 4: Permutation Importance (groups fixed)')
print('='*85)

base_spread = rdf_fixed['spread'].mean() * 12
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
    # FIX #3: these now shuffle ALL listed features
    'ALL momentum':  ['f_mom6_xs', 'f_mom3_xs', 'f_mom1_xs'],
    'ALL valuation': ['f_valuation_xs', 'f_pe_level_xs'],
    'ALL eps':       ['f_eps_rev_xs', 'f_eps_rev_1m_xs'],
}

for gname, feats in feature_groups.items():
    rdf_shuf = walk_forward_purged(df_noXLE, feat_xs, top_n=1,
        embargo_months=3, shuffle_features=feats)
    shuf_sp = rdf_shuf['spread'].mean() * 12
    drop = base_spread - shuf_sp
    pct = (drop / abs(base_spread)) * 100 if base_spread != 0 else 0
    tag = '🔴 critical' if pct > 30 else '🟡 important' if pct > 10 else '⚪ minor'
    feats_str = '+'.join(f.replace('_xs','').replace('f_','') for f in feats)
    print(f'  {gname:<18s} [{feats_str:<30s}]: '
          f'spread {shuf_sp*100:+5.1f}% (Δ{drop*100:+5.1f}%, {pct:+.0f}%)  {tag}')

# ═══════════════════════════════════════════════
# KNIFE 5: Placebo — 500 iterations (FIXED)
# ═══════════════════════════════════════════════
print('\n' + '='*85)
print('🔪 KNIFE 5: Placebo (500 shuffled-label iterations)')
print('='*85)

N_PLACEBO = 500
placebo_spreads = []
print(f'  Running {N_PLACEBO} placebo iterations...', flush=True)

for i in range(N_PLACEBO):
    rdf_p = walk_forward_purged(df_noXLE, feat_xs, top_n=1,
        embargo_months=3, shuffle_labels=True, shuffle_seed=i)
    sp = rdf_p['spread'].mean() * 12
    placebo_spreads.append(sp)
    if (i+1) % 100 == 0:
        print(f'    {i+1}/{N_PLACEBO} done...', flush=True)

placebo_arr = np.array(placebo_spreads)
pctile = (placebo_arr < base_spread).mean() * 100
p_value = 1 - pctile / 100

print(f'\n  Real spread:             {base_spread*100:+.1f}%')
print(f'  Placebo mean:            {placebo_arr.mean()*100:+.1f}%')
print(f'  Placebo std:             {placebo_arr.std()*100:.1f}%')
print(f'  Placebo 5th percentile:  {np.percentile(placebo_arr, 5)*100:+.1f}%')
print(f'  Placebo 95th percentile: {np.percentile(placebo_arr, 95)*100:+.1f}%')
print(f'  Placebo 99th percentile: {np.percentile(placebo_arr, 99)*100:+.1f}%')
print(f'\n  Real spread percentile:  {pctile:.1f}%')
print(f'  Empirical p-value:       {p_value:.4f}')

if p_value < 0.01:
    print('  → p < 1% — strong evidence against random ✅')
elif p_value < 0.05:
    print('  → p < 5% — moderate evidence ✅')
elif p_value < 0.10:
    print('  → p < 10% — weak evidence ⚠️')
else:
    print('  → p >= 10% — not significant ❌')

# ═══════════════════════════════════════════════
# FINAL VERDICT
# ═══════════════════════════════════════════════
print('\n' + '='*85)
print('📋 FINAL VERDICT (v2 — all bugs fixed)')
print('='*85)

checks = []

# 1. Next-day execution survives
surv1 = m_fixed and m_fixed['cagr'] > 0.10
checks.append(('Next-day execution CAGR>10%', surv1,
    f"CAGR {m_fixed['cagr']*100:+.1f}%, Sharpe {m_fixed['sharpe']:.2f}" if m_fixed else 'N/A'))

# 2. LOSO
loso_ok = loso_results and np.mean(cagrs) > 0.08
checks.append(('LOSO mean CAGR>8%', loso_ok,
    f"mean {np.mean(cagrs)*100:+.1f}%" if loso_results else 'N/A'))

# 3. Survives strict 2022 exclusion
surv3 = m_no22b and m_no22b['cagr'] > 0.08
checks.append(('Strict excl-2022 CAGR>8%', surv3,
    f"CAGR {m_no22b['cagr']*100:+.1f}%" if m_no22b else 'N/A'))

# 4. Placebo p < 0.05
surv4 = p_value < 0.05
checks.append((f'Placebo p<0.05', surv4, f'p={p_value:.4f}'))

passed = sum(1 for _, ok, _ in checks if ok)
for name, ok, detail in checks:
    print(f'  {"✅" if ok else "❌"} {name}: {detail}')

print(f'\n  Score: {passed}/4')
if passed == 4:
    print('  → 🟢 Candidate signal survives all fixes')
elif passed >= 3:
    print('  → 🟡 Promising but one check failed')
elif passed >= 2:
    print('  → 🟡 Weakened after fixes')
else:
    print('  → 🔴 Signal did not survive bug fixes')

print('\n✅ Audit v2 complete')
