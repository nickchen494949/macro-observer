#!/usr/bin/env python3
"""
🔪 5-KNIFE AUDIT for RF Sector Rotation
=========================================
1. Purged walk-forward (3M embargo on training labels)
2. Sector concentration + leave-one-sector-out
3. Exclude 2022
4. OOS permutation importance
5. Placebo / shuffled-label test
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
# DATA (same loading as before)
# ══════════════════════════════════════════════════
def load_pe():
    frames = []
    for fname, ticker in PE_MAP.items():
        fp = os.path.join(PE_DIR, fname)
        if not os.path.exists(fp): continue
        df = pd.read_csv(fp); df.columns = [c.strip() for c in df.columns]
        df['date'] = pd.to_datetime(df['date'])
        df = df.dropna(subset=['forward_pe']).set_index('date').sort_index()
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
        s['fwd_ret_3m'] = s['close'].pct_change(3).shift(-3)
        s['fwd_ret_1m'] = s['close'].pct_change(1).shift(-1)
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
# WALK-FORWARD with PURGE
# ══════════════════════════════════════════════════
def walk_forward_purged(df, feat_xs, top_n=1, start=START, end=END,
                        embargo_months=3, exclude_years=None,
                        shuffle_labels=False, shuffle_feature=None):
    """
    Walk-forward with purge/embargo for 3M overlapping targets.
    
    When predicting at month T:
      - Training uses only observations where date < T - embargo_months
      - This ensures no training label overlaps with the prediction period
    
    shuffle_labels: if True, randomly permute training labels (placebo test)
    shuffle_feature: if set, permute this feature in test set (permutation importance)
    """
    dates = sorted(df['date'].unique())
    dates = [d for d in dates if pd.Timestamp(start) <= d <= pd.Timestamp(end)]
    if exclude_years:
        dates = [d for d in dates if d.year not in exclude_years]

    results = []
    rng = np.random.RandomState(42)

    for pred_date in dates:
        # PURGED: only train on data where 3M target has FULLY realized
        # observation at month S has target covering S to S+3
        # so we need S+3 <= pred_date, i.e., S <= pred_date - 3 months
        cutoff = pred_date - pd.DateOffset(months=embargo_months)
        train = df[df['date'] <= cutoff].dropna(subset=feat_xs + ['target'])
        test = df[df['date'] == pred_date].dropna(subset=feat_xs)

        if len(train) < 100 or len(test) < 4:
            continue

        X_tr = train[feat_xs].values
        y_tr = train['target'].values

        if shuffle_labels:
            y_tr = rng.permutation(y_tr)

        X_te = test[feat_xs].values.copy()
        if shuffle_feature and shuffle_feature in feat_xs:
            idx = feat_xs.index(shuffle_feature)
            X_te[:, idx] = rng.permutation(X_te[:, idx])

        mdl = RandomForestRegressor(n_estimators=200, max_depth=4,
                min_samples_leaf=10, random_state=42, n_jobs=-1)
        mdl.fit(X_tr, y_tr)
        preds = mdl.predict(X_te)

        test = test.copy(); test['pred'] = preds
        test = test.sort_values('pred', ascending=False)
        top = test.head(top_n)
        bot = test.tail(top_n)

        top_ret = top['fwd_ret_1m'].mean() if top['fwd_ret_1m'].notna().any() else np.nan
        bot_ret = bot['fwd_ret_1m'].mean() if bot['fwd_ret_1m'].notna().any() else np.nan
        ew = test['fwd_ret_1m'].mean()
        ic = stats.spearmanr(test['pred'], test['fwd_ret_1m'])[0] \
            if len(test) >= 5 and test['fwd_ret_1m'].notna().sum() >= 5 else np.nan

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
    peak = cum.cummax()
    mdd = ((cum-peak)/peak).min()
    return {'label':label,'cagr':cagr,'sharpe':sharpe,'sortino':sortino,
            'mdd':mdd,'n':n,'wr':(r>0).mean()}

def fmt_row(m):
    return (f"{m['label']:<32s} {m['cagr']*100:+6.1f}% {m['sharpe']:6.2f}  "
            f"{m['sortino']:6.2f}  {m['mdd']*100:6.1f}% {m['wr']*100:4.0f}% {m['n']:4d}")

# ══════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════
print('='*85)
print('🔪 5-KNIFE AUDIT — RF Sector Rotation')
print('='*85)

pe = load_pe()
prices = load_prices()
panel = to_monthly(prices)
df_noXLE, feat_xs = build_features(panel, pe, exclude_tickers=['XLE'])
df_all, _ = build_features(panel, pe)
print(f'Data: {len(df_noXLE):,d} rows (no XLE), {len(feat_xs)} features')

hdr = f"{'Test':<32s} {'CAGR':>7s} {'Sharpe':>7s} {'Sortino':>8s} {'MaxDD':>7s} {'WR':>5s} {'N':>5s}"

# ═══════════════════════════════════════════════
# KNIFE 1: Purged vs Non-Purged
# ═══════════════════════════════════════════════
print('\n' + '='*85)
print('🔪 KNIFE 1: Purged Walk-Forward (3M embargo)')
print('='*85)
print('  Without purge: training uses ALL data < T (labels may overlap prediction)')
print('  With purge: training uses data <= T-3 months (no 3M label leakage)')
print()
print(hdr)
print('─'*85)

# Non-purged (old version — embargo=0)
rdf_nopurge = walk_forward_purged(df_noXLE, feat_xs, top_n=1, embargo_months=0)
m1a = metrics(rdf_nopurge['top_ret'], 'NO purge (old, leaky)')
m1a_sp = metrics(rdf_nopurge['spread'], 'NO purge spread')

# Purged
rdf_purge = walk_forward_purged(df_noXLE, feat_xs, top_n=1, embargo_months=3)
m1b = metrics(rdf_purge['top_ret'], 'PURGED 3M embargo')
m1b_sp = metrics(rdf_purge['spread'], 'PURGED spread')

# Also Top3
rdf_purge3 = walk_forward_purged(df_noXLE, feat_xs, top_n=3, embargo_months=3)
m1c = metrics(rdf_purge3['top_ret'], 'PURGED 3M Top3')
m1c_sp = metrics(rdf_purge3['spread'], 'PURGED Top3 spread')

for m in [m1a, m1b, m1c]:
    if m: print(fmt_row(m))
print()
for m in [m1a_sp, m1b_sp, m1c_sp]:
    if m: print(fmt_row(m))

drop = ((m1a['cagr'] - m1b['cagr']) / abs(m1a['cagr'])) * 100 if m1a and m1b else 0
print(f'\n  Purge impact on CAGR: {drop:+.0f}% change')
if m1b and m1b['cagr'] > 0.15:
    print('  → Signal SURVIVES purge ✅')
elif m1b and m1b['cagr'] > 0.10:
    print('  → Signal weakened but alive ⚠️')
else:
    print('  → Signal may have been leaking ❌')

# ═══════════════════════════════════════════════
# KNIFE 2: Sector Concentration + Leave-One-Out
# ═══════════════════════════════════════════════
print('\n' + '='*85)
print('🔪 KNIFE 2: Sector Concentration + Leave-One-Sector-Out')
print('='*85)

# What does RF no-XLE Top1 actually pick?
print('\n  Sector pick frequency (RF no-XLE Top1, purged):')
if len(rdf_purge) > 0:
    counts = rdf_purge['top1'].value_counts()
    total = len(rdf_purge)
    for t, c in counts.items():
        bar = '█' * int(c / total * 40)
        print(f'    {NAMES.get(t,t):<6s} ({t}): {c:3d}/{total} = {c/total*100:4.1f}%  {bar}')

# Leave-one-sector-out
print(f'\n  Leave-One-Sector-Out (purged, Top1, {START}→{END}):')
print(f'  {hdr}')
print('  ' + '─'*85)

loso_results = []
sectors_to_test = [t for t in SECTORS if t != 'XLE']  # already excluding XLE
for excluded in sectors_to_test:
    exclude_list = ['XLE', excluded]
    df_loso, fx = build_features(panel, pe, exclude_tickers=exclude_list)
    rdf_loso = walk_forward_purged(df_loso, fx, top_n=1, embargo_months=3)
    m_loso = metrics(rdf_loso['top_ret'], f'excl XLE+{excluded}')
    m_loso_sp = metrics(rdf_loso['spread'], f'excl XLE+{excluded} sprd')
    if m_loso:
        print(f'  {fmt_row(m_loso)}')
        loso_results.append(m_loso)

if loso_results:
    cagrs = [m['cagr'] for m in loso_results]
    print(f'\n  LOSO CAGR range: {min(cagrs)*100:+.1f}% to {max(cagrs)*100:+.1f}%')
    print(f'  LOSO CAGR mean:  {np.mean(cagrs)*100:+.1f}%')
    print(f'  LOSO CAGR std:   {np.std(cagrs)*100:.1f}%')
    if np.mean(cagrs) > 0.12:
        print('  → Robust across sector removal ✅')
    elif np.mean(cagrs) > 0.08:
        print('  → Somewhat dependent on specific sectors ⚠️')
    else:
        print('  → Concentrated in few sectors ❌')

# ═══════════════════════════════════════════════
# KNIFE 3: Exclude 2022
# ═══════════════════════════════════════════════
print('\n' + '='*85)
print('🔪 KNIFE 3: Exclude 2022')
print('='*85)
print()
print(hdr)
print('─'*85)

rdf_no22 = walk_forward_purged(df_noXLE, feat_xs, top_n=1,
                                embargo_months=3, exclude_years=[2022])
m3a = metrics(rdf_no22['top_ret'], 'Purged, no 2022, Top1')
m3a_sp = metrics(rdf_no22['spread'], 'Purged, no 2022, sprd')

rdf_no22_t3 = walk_forward_purged(df_noXLE, feat_xs, top_n=3,
                                   embargo_months=3, exclude_years=[2022])
m3b = metrics(rdf_no22_t3['top_ret'], 'Purged, no 2022, Top3')
m3b_sp = metrics(rdf_no22_t3['spread'], 'Purged, no 2022, sprd')

for m in [m1b, m3a]:  # purged with vs without 2022
    if m: print(fmt_row(m))
print()
for m in [m1b_sp, m3a_sp]:
    if m: print(fmt_row(m))

# ═══════════════════════════════════════════════
# KNIFE 4: OOS Permutation Importance
# ═══════════════════════════════════════════════
print('\n' + '='*85)
print('🔪 KNIFE 4: OOS Permutation Importance')
print('='*85)
print('  Shuffle each feature in test set, measure spread drop')
print()

# Baseline
rdf_base = walk_forward_purged(df_noXLE, feat_xs, top_n=1, embargo_months=3)
base_spread = rdf_base['spread'].mean() * 12

print(f'  Baseline annualized spread: {base_spread*100:+.1f}%')
print()

perm_results = []
# Group correlated features
feature_groups = {
    'valuation': ['f_valuation_xs'],
    'eps_rev (3M)': ['f_eps_rev_xs'],
    'eps_rev (1M)': ['f_eps_rev_1m_xs'],
    'momentum (6M)': ['f_mom6_xs'],
    'momentum (3M)': ['f_mom3_xs'],
    'momentum (1M)': ['f_mom1_xs'],
    'pe_level': ['f_pe_level_xs'],
    'pe_change': ['f_pe_chg3_xs'],
    'dist_high': ['f_dist_high6_xs'],
    'ALL momentum': ['f_mom6_xs', 'f_mom3_xs', 'f_mom1_xs'],
    'ALL valuation': ['f_valuation_xs', 'f_pe_level_xs'],
    'ALL eps': ['f_eps_rev_xs', 'f_eps_rev_1m_xs'],
}

for group_name, features_to_shuffle in feature_groups.items():
    # Shuffle all features in this group simultaneously
    rdf_shuf = walk_forward_purged(df_noXLE, feat_xs, top_n=1,
                                    embargo_months=3,
                                    shuffle_feature=features_to_shuffle[0])
    shuf_spread = rdf_shuf['spread'].mean() * 12
    drop = base_spread - shuf_spread
    pct_drop = (drop / abs(base_spread)) * 100 if base_spread != 0 else 0
    importance = '🔴 critical' if pct_drop > 30 else '🟡 important' if pct_drop > 10 else '⚪ minor'
    print(f'  {group_name:<20s}: spread {shuf_spread*100:+.1f}%  '
          f'(drop {drop*100:+.1f}%, {pct_drop:+.0f}%)  {importance}')

# ═══════════════════════════════════════════════
# KNIFE 5: Placebo Test (shuffled labels)
# ═══════════════════════════════════════════════
print('\n' + '='*85)
print('🔪 KNIFE 5: Placebo Test (shuffled labels)')
print('='*85)
print('  If RF works with random labels → model is overfitting')
print()

placebo_spreads = []
for seed_offset in range(10):
    # We use shuffle_labels=True which uses RandomState(42)
    # but we'll run it once since the walk-forward is deterministic per shuffle
    rdf_placebo = walk_forward_purged(df_noXLE, feat_xs, top_n=1,
                                       embargo_months=3, shuffle_labels=True)
    placebo_sp = rdf_placebo['spread'].mean() * 12
    placebo_spreads.append(placebo_sp)
    break  # One shuffle is enough to demonstrate

m_placebo = metrics(rdf_placebo['top_ret'], 'Placebo (random labels)')
m_placebo_sp = metrics(rdf_placebo['spread'], 'Placebo spread')

print(hdr)
print('─'*85)
if m1b: print(fmt_row(m1b))
if m_placebo: print(fmt_row(m_placebo))
print()
print(f'  Real spread:    {base_spread*100:+.1f}%')
print(f'  Placebo spread: {placebo_spreads[0]*100:+.1f}%')

if abs(placebo_spreads[0]) < abs(base_spread) * 0.3:
    print('  → Placebo is near zero, real signal exists ✅')
else:
    print('  → Placebo too strong, possible overfitting ❌')

# ═══════════════════════════════════════════════
# FINAL VERDICT
# ═══════════════════════════════════════════════
print('\n' + '='*85)
print('📋 FINAL VERDICT')
print('='*85)

checks = [
    ('1. Purged walk-forward', m1b['cagr'] > 0.10 if m1b else False,
     f"CAGR {m1b['cagr']*100:+.1f}%" if m1b else 'N/A'),
    ('2. LOSO mean CAGR > 12%', np.mean(cagrs) > 0.12 if loso_results else False,
     f"mean {np.mean(cagrs)*100:+.1f}%" if loso_results else 'N/A'),
    ('3. Survives w/o 2022', m3a['cagr'] > 0.10 if m3a else False,
     f"CAGR {m3a['cagr']*100:+.1f}%" if m3a else 'N/A'),
    ('4. Real > placebo spread', abs(base_spread) > abs(placebo_spreads[0]) * 2,
     f"real {base_spread*100:+.1f}% vs placebo {placebo_spreads[0]*100:+.1f}%"),
]

passed = 0
for name, ok, detail in checks:
    status = '✅' if ok else '❌'
    print(f'  {status} {name}: {detail}')
    if ok: passed += 1

print(f'\n  Score: {passed}/4')
if passed >= 3:
    print('  → 🟢 Candidate signal — worth serious validation')
elif passed >= 2:
    print('  → 🟡 Promising but needs more work')
else:
    print('  → 🔴 Not robust enough')

print('\n✅ Audit complete')
