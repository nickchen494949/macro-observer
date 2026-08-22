#!/usr/bin/env python3
"""
🌲 Random Forest vs Linear vs Simple Ranking — Sector Rotation
================================================================
Walk-forward expanding-window comparison.

Models:
  A. Simple ranking (val + eps_rev + momentum weighted average)
  B. Ridge regression
  C. Random Forest (regressor)
  D. Random Forest (exclude XLE)

Target: 3M sector excess return vs median sector
Features: PE-capped at 50x, EPS revision winsorized ±50%

All walk-forward: train on expanding window, predict next period.
"""

import os, sys, json, warnings
import pandas as pd, numpy as np
from scipy import stats
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge

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

# ══════════════════════════════════════════════════════════
# DATA
# ══════════════════════════════════════════════════════════
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
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date').sort_index()
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

# ══════════════════════════════════════════════════════════
# FEATURES
# ══════════════════════════════════════════════════════════
FEAT_COLS = ['f_valuation', 'f_eps_rev', 'f_eps_rev_1m', 'f_mom6', 'f_mom3',
             'f_mom1', 'f_pe_level', 'f_pe_chg3', 'f_dist_high6']

def build_features(panel, pe, exclude_tickers=None):
    """Build feature matrix with cross-sectional z-scores."""
    tickers = [t for t in SECTORS if t not in (exclude_tickers or [])]
    sector_panel = panel[panel['ticker'].isin(tickers)].copy()
    m = sector_panel.merge(pe[['date','ticker','fpe']], on=['date','ticker'], how='left')
    m.loc[(m['fpe'] > 50) | (m['fpe'] <= 0), 'fpe'] = np.nan

    all_feat = []
    for t in tickers:
        s = m[m['ticker'] == t].sort_values('date').copy()
        if len(s) < 25: continue

        # Valuation
        s['f_valuation'] = -s['fpe'].rolling(24, min_periods=12).apply(
            lambda x: (x.iloc[-1] - x.mean()) / (x.std() + 1e-9))

        # EPS revision (3M and 1M)
        s['fwd_eps'] = s['close'] / s['fpe']
        s['f_eps_rev'] = s['fwd_eps'].pct_change(3).clip(-0.5, 0.5)
        s['f_eps_rev_1m'] = s['fwd_eps'].pct_change(1).clip(-0.3, 0.3)

        # Momentum
        s['f_mom6'] = s['close'].pct_change(6)
        s['f_mom3'] = s['close'].pct_change(3)
        s['f_mom1'] = s['close'].pct_change(1)

        # PE level and change
        s['f_pe_level'] = s['fpe']
        s['f_pe_chg3'] = s['fpe'].pct_change(3)

        # Distance from 6M high
        s['f_dist_high6'] = s['close'] / s['close'].rolling(6).max() - 1

        # Target: 3M forward excess return vs cross-sectional median
        s['fwd_ret_3m'] = s['close'].pct_change(3).shift(-3)

        all_feat.append(s)

    df = pd.concat(all_feat, ignore_index=True)

    # Cross-sectional median for target
    df['fwd_ret_3m_median'] = df.groupby('date')['fwd_ret_3m'].transform('median')
    df['target'] = df['fwd_ret_3m'] - df['fwd_ret_3m_median']

    # Also keep 1M forward for evaluation
    for t_name in tickers:
        mask = df['ticker'] == t_name
        sub = df.loc[mask].sort_values('date')
        df.loc[mask, 'fwd_ret_1m'] = sub['close'].pct_change(1).shift(-1).values

    # Cross-sectional z-score features
    feat_xs = []
    for c in FEAT_COLS:
        zc = c + '_xs'
        df[zc] = df.groupby('date')[c].transform(
            lambda x: (x - x.mean()) / (x.std() + 1e-9) if x.std() > 0 else 0)
        feat_xs.append(zc)

    return df, feat_xs

# ══════════════════════════════════════════════════════════
# WALK-FORWARD ENGINE
# ══════════════════════════════════════════════════════════
def walk_forward(df, feat_xs, model_type='rf', min_train=36,
                 start='2019-01', end='2026-06', top_n=3):
    dates = sorted(df['date'].unique())
    dates = [d for d in dates if pd.Timestamp(start) <= d <= pd.Timestamp(end)]

    results = []
    yearly_fi = {}

    for pred_date in dates:
        train = df[df['date'] < pred_date].dropna(subset=feat_xs + ['target'])
        test = df[df['date'] == pred_date].dropna(subset=feat_xs)

        if len(train) < min_train * 3 or len(test) < 4:
            continue

        X_tr, y_tr = train[feat_xs].values, train['target'].values
        X_te = test[feat_xs].values

        if model_type == 'rf':
            mdl = RandomForestRegressor(n_estimators=200, max_depth=4,
                    min_samples_leaf=10, random_state=42, n_jobs=-1)
        elif model_type == 'ridge':
            mdl = Ridge(alpha=1.0)
        elif model_type == 'simple':
            # Simple weighted average of first 3 features
            weights = np.array([1.0, 1.0, 0.0, 0.5, 0.0, 0.0, 0.0, 0.0, 0.0])
            weights = weights[:len(feat_xs)]
            preds = X_te @ weights
            test = test.copy(); test['pred'] = preds
            test = test.sort_values('pred', ascending=False)
            top = test.head(top_n)
            top_ret = top['fwd_ret_1m'].mean() if 'fwd_ret_1m' in top else np.nan
            bot = test.tail(top_n)
            bot_ret = bot['fwd_ret_1m'].mean() if 'fwd_ret_1m' in bot else np.nan
            ew = test['fwd_ret_1m'].mean() if 'fwd_ret_1m' in test else np.nan
            ic = stats.spearmanr(test['pred'], test['fwd_ret_1m'])[0] if len(test)>=5 and test['fwd_ret_1m'].notna().sum()>=5 else np.nan
            results.append({'date':pred_date,'top_ret':top_ret,'bot_ret':bot_ret,
                           'spread':top_ret-bot_ret if pd.notna(bot_ret) else np.nan,
                           'ew':ew,'ic':ic,'top1':top['ticker'].iloc[0],
                           'picks':','.join(top['ticker'].tolist())})
            continue

        mdl.fit(X_tr, y_tr)
        preds = mdl.predict(X_te)

        test = test.copy(); test['pred'] = preds
        test = test.sort_values('pred', ascending=False)
        top = test.head(top_n)
        bot = test.tail(top_n)

        top_ret = top['fwd_ret_1m'].mean() if top['fwd_ret_1m'].notna().any() else np.nan
        bot_ret = bot['fwd_ret_1m'].mean() if bot['fwd_ret_1m'].notna().any() else np.nan
        ew = test['fwd_ret_1m'].mean()
        ic = stats.spearmanr(test['pred'], test['fwd_ret_1m'])[0] if len(test)>=5 and test['fwd_ret_1m'].notna().sum()>=5 else np.nan

        results.append({'date':pred_date,'top_ret':top_ret,'bot_ret':bot_ret,
                       'spread':top_ret-bot_ret if pd.notna(bot_ret) else np.nan,
                       'ew':ew,'ic':ic,'top1':top['ticker'].iloc[0],
                       'picks':','.join(top['ticker'].tolist())})

        # Feature importance (RF only)
        if model_type == 'rf':
            year = pred_date.year
            if year not in yearly_fi:
                yearly_fi[year] = []
            yearly_fi[year].append(dict(zip(feat_xs, mdl.feature_importances_)))

    rdf = pd.DataFrame(results)
    return rdf, yearly_fi

def calc_metrics(rets):
    r = pd.Series(rets).dropna()
    n = len(r)
    if n < 6: return None
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
    wr = (r > 0).mean()
    return {'cagr':cagr,'sharpe':sharpe,'sortino':sortino,'mdd':mdd,'n':n,'wr':wr}

# ══════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════
print('='*85)
print('🌲 MODEL COMPARISON: Simple vs Ridge vs RF — Walk-Forward OOS')
print('='*85)

pe = load_pe()
prices = load_prices()
panel = to_monthly(prices)
print(f'Data loaded: PE {len(pe):,d} rows | Panel {len(panel):,d} rows')

# Build features (with and without XLE)
df_all, feat_xs = build_features(panel, pe)
df_noXLE, _ = build_features(panel, pe, exclude_tickers=['XLE'])
print(f'Features: {len(df_all):,d} rows, {len(feat_xs)} features')

# SPY benchmark
spy = panel[panel['ticker']=='SPY'].sort_values('date').copy()
spy['ret'] = spy['close'].pct_change()

START = '2019-01'
END = '2026-06'

print(f'\nWalk-forward period: {START} → {END}')
print(f'Training starts from earliest PE data (~2005)')
print(f'Target: 3M excess return vs median sector')
print(f'PE capped at 50x | EPS rev winsorized ±50% / ±30%')

# ── Run all models ──
configs = [
    ('Simple Ranking', 'simple', df_all, 3),
    ('Ridge Regression', 'ridge', df_all, 3),
    ('Random Forest', 'rf', df_all, 3),
    ('RF (no XLE)', 'rf', df_noXLE, 3),
    ('Simple Top1', 'simple', df_all, 1),
    ('Ridge Top1', 'ridge', df_all, 1),
    ('RF Top1', 'rf', df_all, 1),
    ('RF Top1 (no XLE)', 'rf', df_noXLE, 1),
]

all_rows = []
all_fi = {}

for name, model, data, top_n in configs:
    rdf, yearly_fi = walk_forward(data, feat_xs, model_type=model,
                                   start=START, end=END, top_n=top_n)
    if len(rdf) == 0: continue

    m = calc_metrics(rdf['top_ret'])
    sm = calc_metrics(rdf['spread'])
    if m is None: continue

    # SPY for same period
    spy_sub = spy[(spy['date']>=START)&(spy['date']<=END)]['ret'].dropna()
    spy_m = calc_metrics(spy_sub)

    xle_n = (rdf['top1'] == 'XLE').sum() if top_n == 1 else rdf['picks'].str.contains('XLE').sum()
    ic_avg = rdf['ic'].dropna().mean()

    all_rows.append({
        'Model': name, 'CAGR': m['cagr'], 'Sharpe': m['sharpe'],
        'Sortino': m['sortino'], 'MaxDD': m['mdd'],
        'SprdCAGR': sm['cagr'] if sm else 0, 'WR': m['wr'],
        'RankIC': ic_avg, 'XLE': f"{xle_n}/{m['n']}", 'N': m['n'],
    })

    if yearly_fi:
        all_fi[name] = yearly_fi

# ── Benchmarks ──
spy_sub = spy[(spy['date']>=START)&(spy['date']<=END)]['ret'].dropna()
spy_met = calc_metrics(spy_sub)
if spy_met:
    all_rows.insert(0, {'Model':'SPY','CAGR':spy_met['cagr'],'Sharpe':spy_met['sharpe'],
                        'Sortino':spy_met['sortino'],'MaxDD':spy_met['mdd'],
                        'SprdCAGR':0,'WR':spy_met['wr'],'RankIC':0,'XLE':'—','N':spy_met['n']})

qqq = panel[panel['ticker']=='QQQ'].sort_values('date').copy()
qqq['ret'] = qqq['close'].pct_change()
qqq_sub = qqq[(qqq['date']>=START)&(qqq['date']<=END)]['ret'].dropna()
qqq_met = calc_metrics(qqq_sub)
if qqq_met:
    all_rows.insert(1, {'Model':'QQQ','CAGR':qqq_met['cagr'],'Sharpe':qqq_met['sharpe'],
                        'Sortino':qqq_met['sortino'],'MaxDD':qqq_met['mdd'],
                        'SprdCAGR':0,'WR':qqq_met['wr'],'RankIC':0,'XLE':'—','N':qqq_met['n']})

# ── Print ──
print('\n' + '='*85)
print('📊 RESULTS (OOS Walk-Forward)')
print('='*85)
hdr = f"{'Model':<22s} {'CAGR':>7s} {'Sharpe':>7s} {'Sortino':>8s} {'MaxDD':>7s} {'SprdCAGR':>9s} {'WR':>5s} {'IC':>6s} {'XLE':>7s}"
print(hdr)
print('─'*85)
for r in all_rows:
    xle = r.get('XLE','—')
    print(f"{r['Model']:<22s} {r['CAGR']*100:+6.1f}% {r['Sharpe']:6.2f}  {r['Sortino']:7.2f}  "
          f"{r['MaxDD']*100:6.1f}% {r['SprdCAGR']*100:+8.1f}% {r['WR']*100:4.0f}% {r['RankIC']:+5.3f} {xle:>7s}")

# ── Feature Importance Stability ──
if all_fi:
    print('\n' + '='*85)
    print('🔍 FEATURE IMPORTANCE BY YEAR (Random Forest)')
    print('='*85)

    for model_name, yearly in all_fi.items():
        print(f'\n  {model_name}:')
        years_sorted = sorted(yearly.keys())
        # Header
        feat_names_short = [c.replace('_xs','').replace('f_','') for c in feat_xs]
        hdr = f"  {'Year':<6s} " + ' '.join(f'{fn:>8s}' for fn in feat_names_short)
        print(hdr)
        print('  ' + '─'*80)

        for year in years_sorted:
            fi_list = yearly[year]
            avg = {}
            for c in feat_xs:
                avg[c] = np.mean([fi.get(c, 0) for fi in fi_list])
            vals = ' '.join(f'{avg[c]*100:7.1f}%' for c in feat_xs)
            print(f'  {year:<6d} {vals}')

        # Overall
        all_fi_flat = []
        for fi_list in yearly.values():
            all_fi_flat.extend(fi_list)
        overall = {}
        for c in feat_xs:
            overall[c] = np.mean([fi.get(c, 0) for fi in all_fi_flat])
        vals = ' '.join(f'{overall[c]*100:7.1f}%' for c in feat_xs)
        print(f'  {"ALL":<6s} {vals}')

        # Flag instability
        print()
        for c in feat_xs:
            per_year = [np.mean([fi.get(c,0) for fi in yearly[y]]) for y in years_sorted]
            cv = np.std(per_year) / (np.mean(per_year) + 1e-9)
            stability = '✅ stable' if cv < 0.3 else '⚠️ unstable' if cv < 0.6 else '❌ very unstable'
            short = c.replace('_xs','').replace('f_','')
            print(f'    {short:<20s} CV={cv:.2f}  {stability}')

# ── Annual breakdown ──
print('\n' + '='*85)
print('📅 ANNUAL BREAKDOWN (RF Top3)')
print('='*85)

# Re-run RF to get annual results
rdf_rf, _ = walk_forward(df_all, feat_xs, model_type='rf', start=START, end=END, top_n=3)
if len(rdf_rf) > 0:
    rdf_rf['year'] = rdf_rf['date'].dt.year
    print(f"\n  {'Year':<6s} {'Top3 Ret':>9s} {'EW Ret':>9s} {'Spread':>9s} {'WR':>5s} {'AvgIC':>7s}")
    print('  ' + '─'*50)
    for year, g in rdf_rf.groupby('year'):
        top_ann = g['top_ret'].mean() * 12
        ew_ann = g['ew'].mean() * 12
        sp_ann = g['spread'].mean() * 12
        wr = (g['spread'] > 0).mean()
        ic = g['ic'].dropna().mean()
        print(f"  {year:<6d} {top_ann*100:+8.1f}% {ew_ann*100:+8.1f}% {sp_ann*100:+8.1f}% {wr*100:4.0f}% {ic:+6.3f}")

print('\n✅ Done')
