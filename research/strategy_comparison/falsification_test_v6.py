#!/usr/bin/env python3
"""
Historical Falsification Test v6 — Conditional Fallback
========================================================
Purpose: NOT validation. Testing the "house is already on fire" hypothesis.

Logic:
- Hawkish pulse -> EXIT
- If EPS at exit > -3%: (Early Warning)
    -> Re-enter on New EPS distress OR Hawk normalize
- If EPS at exit <= -3%: (Late Arrival / House on Fire)
    -> Suppress Hawk normalize
    -> Wait for EPS to recover > -3% to re-enter
"""

import sys, os, csv, json, urllib.request
import pandas as pd, numpy as np
from datetime import timedelta
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

PROJ_DIR = '/Users/happygolucky/projects/宏观观察器'
KW_URL = "https://www.federalreserve.gov/data/yield-curve-tables/feds200533.csv"

# STEP 1: Load data
# --- Kim-Wright ---
req = urllib.request.Request(KW_URL, headers={'User-Agent': 'Mozilla/5.0'})
resp = urllib.request.urlopen(req, timeout=30)
raw = resp.read().decode('utf-8')
lines = raw.strip().split('\n')
header_idx = next(i for i, l in enumerate(lines) if l.startswith('Date,'))
reader = csv.DictReader(lines[header_idx:])
kw_rows = []
for row in reader:
    try:
        kw_rows.append({'date': row['Date'], 'fwd_1y': float(row['THREEFF0100.B']),
                        'tp_1y': float(row['THREEFFTP0100.B'])})
    except: continue
kw = pd.DataFrame(kw_rows); kw['date'] = pd.to_datetime(kw['date'])
kw['exp_short_1y'] = kw['fwd_1y'] - kw['tp_1y']
kw = kw.sort_values('date').reset_index(drop=True)

# --- DFF ---
dff_json = os.path.join(PROJ_DIR, 'data', 'fred', 'DFF.json')
with open(dff_json) as f: dff_data = json.load(f)
dff_raw = dff_data.get('values', dff_data) if isinstance(dff_data, dict) else dff_data
dff = pd.DataFrame(dff_raw, columns=['date', 'value'])
dff['date'] = pd.to_datetime(dff['date']); dff['dff'] = pd.to_numeric(dff['value'], errors='coerce')
dff = dff[['date', 'dff']].dropna()

merged = pd.merge(kw[['date','exp_short_1y']], dff[['date','dff']], on='date', how='inner')
merged = merged.sort_values('date').reset_index(drop=True)
merged['hawkish_path'] = merged['exp_short_1y'] - merged['dff']
merged['delta_exp_4w'] = merged['exp_short_1y'] - merged['exp_short_1y'].shift(20)
merged['is_strong_hawk'] = (merged['hawkish_path'] > 0.5) & (merged['delta_exp_4w'] > 0.25)

# --- QQQ ---
ypath = os.path.join(PROJ_DIR, 'data', 'yahoo', 'QQQ.json')
if os.path.exists(ypath):
    with open(ypath) as f: yd = json.load(f)
    vals = yd.get('values', yd) if isinstance(yd, dict) else yd
    qqq = pd.DataFrame(vals, columns=['date', 'close'])
    qqq['date'] = pd.to_datetime(qqq['date']); qqq['close'] = pd.to_numeric(qqq['close'], errors='coerce')

qqq = qqq.dropna().sort_values('date').reset_index(drop=True)
qqq['daily_ret'] = qqq['close'].pct_change()
qqq_dates = pd.DatetimeIndex(qqq['date'].values)

# --- S&P 500 Trailing EPS ---
eps_path = os.path.join(PROJ_DIR, 'data', 'valuation', 'SP500_EPS.json')
with open(eps_path) as f: eps_data = json.load(f)
eps_vals = eps_data if isinstance(eps_data, list) else eps_data.get('values', [])
eps_df = pd.DataFrame(eps_vals, columns=['date', 'eps'])
eps_df['date'] = pd.to_datetime(eps_df['date'])
eps_df['eps'] = pd.to_numeric(eps_df['eps'], errors='coerce')
eps_df = eps_df.dropna().sort_values('date').reset_index(drop=True)
eps_df['eps_12m'] = eps_df['eps'].rolling(4, min_periods=4).sum()
eps_df['eps_mom_6m'] = eps_df['eps'].pct_change(6) * 100

# STEP 2: Build daily signals
def next_td(date, trading_dates):
    mask = trading_dates >= date
    return trading_dates[mask][0] if mask.any() else None

def kw_pub_tuesday(obs_date):
    wd = obs_date.weekday()
    friday = obs_date + timedelta(days=(4 - wd) % 7)
    return friday + timedelta(days=4)

hawk_daily = merged[['date','hawkish_path','delta_exp_4w','is_strong_hawk']].copy()
hawk_daily['pub_date'] = hawk_daily['date'].apply(kw_pub_tuesday)
hawk_daily['trade_date'] = hawk_daily['pub_date'].apply(lambda d: next_td(d, qqq_dates))
hawk_daily = hawk_daily.dropna(subset=['trade_date'])

hawk_signal_series = {}
for _, row in hawk_daily.iterrows():
    td = row['trade_date']
    if td not in hawk_signal_series or row['date'] > hawk_signal_series[td]['obs_date']:
        hawk_signal_series[td] = {'obs_date': row['date'], 'hp': row['hawkish_path'],
                                   'is_strong': row['is_strong_hawk']}

hawk_ff = pd.DataFrame(index=qqq['date'])
hawk_ff['hawk_hp'] = np.nan; hawk_ff['hawk_strong_raw'] = False
last_hp = np.nan; last_strong = False
for date in qqq['date']:
    if date in hawk_signal_series:
        last_hp = hawk_signal_series[date]['hp']
        last_strong = hawk_signal_series[date]['is_strong']
    hawk_ff.loc[date, 'hawk_hp'] = last_hp
    hawk_ff.loc[date, 'hawk_strong_raw'] = last_strong
hawk_ff['hawk_strong_prev'] = hawk_ff['hawk_strong_raw'].shift(1).fillna(False)
hawk_ff['hawk_strong_pulse'] = hawk_ff['hawk_strong_raw'] & ~hawk_ff['hawk_strong_prev']

eps_ff = pd.DataFrame(index=qqq['date'])
eps_ff['eps_mom_6m'] = np.nan
for _, row in eps_df.iterrows():
    pub_date = row['date'] + timedelta(days=45)
    td = next_td(pub_date, qqq_dates)
    if td is not None and pd.notna(row['eps_mom_6m']):
        eps_ff.loc[td, 'eps_mom_6m'] = row['eps_mom_6m']
eps_ff['eps_mom_6m'] = eps_ff['eps_mom_6m'].ffill()

# STEP 3: Strategy Engine
SAMPLE_START = pd.Timestamp('2000-01-01')
SAMPLE_END = min(qqq['date'].max(), eps_df['date'].max() + timedelta(days=90))
mask = (qqq['date'] >= SAMPLE_START) & (qqq['date'] <= SAMPLE_END)
qqq_sample = qqq[mask].copy().reset_index(drop=True)

EPS_THRESHOLD = -3.0

def run_strategy(name, qqq_df, exit_fn, entry_fn):
    equity = 1.0; state = 'IN'; trade_log = []; equity_curve = []; current_trade = None
    ctx = {'exit_date': None, 'eps_at_exit': None, 'eps_was_above_since_exit': False}
    for i, row in qqq_df.iterrows():
        date = row['date']; daily_ret = row['daily_ret'] if pd.notna(row['daily_ret']) else 0.0
        hawk = hawk_ff.loc[date] if date in hawk_ff.index else pd.Series({'hawk_hp': np.nan, 'hawk_strong_pulse': False})
        eps_mom = eps_ff.loc[date, 'eps_mom_6m'] if date in eps_ff.index else np.nan
        
        if state == 'IN':
            equity *= (1 + daily_ret)
            if exit_fn(date, hawk, eps_mom, ctx):
                state = 'OUT'
                ctx['exit_date'] = date
                ctx['eps_at_exit'] = eps_mom
                if pd.notna(eps_mom) and eps_mom > EPS_THRESHOLD:
                    ctx['eps_was_above_since_exit'] = True
                else:
                    ctx['eps_was_above_since_exit'] = False
                current_trade = {'exit_date': date, 'exit_price': row['close'],
                                 'exit_equity': equity, 'eps_at_exit': eps_mom}
        elif state == 'OUT':
            if pd.notna(eps_mom) and eps_mom > EPS_THRESHOLD:
                ctx['eps_was_above_since_exit'] = True
            if entry_fn(date, hawk, eps_mom, ctx):
                state = 'IN'
                if current_trade:
                    current_trade['entry_date'] = date; current_trade['entry_price'] = row['close']
                    current_trade['entry_reason'] = ctx.get('entry_reason', '?')
                    trade_log.append(current_trade); current_trade = None
        equity_curve.append({'date': date, 'equity': equity, 'state': state})
    if current_trade:
        last = qqq_df.iloc[-1]
        current_trade['entry_date'] = last['date']; current_trade['entry_price'] = last['close']
        current_trade['still_out'] = True; current_trade['entry_reason'] = 'STILL_OUT'
        trade_log.append(current_trade)
    return pd.DataFrame(equity_curve), trade_log

def hawk_pulse_exit(date, hawk, eps_mom, ctx): return hawk['hawk_strong_pulse']
def hawk_normalize(date, hawk, eps_mom, ctx): hp = hawk['hawk_hp']; return pd.notna(hp) and hp < 0.5
def eps_new_event_entry(date, hawk, eps_mom, ctx):
    if not ctx.get('eps_was_above_since_exit', False): return False
    if pd.notna(eps_mom) and eps_mom <= EPS_THRESHOLD:
        ctx['entry_reason'] = 'EPS_NEW'
        return True
    return False

# Old logic
def entry_new_eps_or_hawk(date, hawk, eps_mom, ctx):
    if eps_new_event_entry(date, hawk, eps_mom, ctx): return True
    if hawk_normalize(date, hawk, eps_mom, ctx):
        ctx['entry_reason'] = 'HAWK_NORMALIZE'
        return True
    return False

# v6 logic
def entry_v6_conditional(date, hawk, eps_mom, ctx):
    eps_at_exit = ctx.get('eps_at_exit')
    is_late_arrival = pd.notna(eps_at_exit) and eps_at_exit <= EPS_THRESHOLD
    
    if is_late_arrival:
        # Suppress hawk normalize. Wait for EPS to recover > -3%
        if pd.notna(eps_mom) and eps_mom > EPS_THRESHOLD:
            ctx['entry_reason'] = 'EPS_RECOVERY'
            return True
    else:
        # Normal path
        if eps_new_event_entry(date, hawk, eps_mom, ctx): return True
        if hawk_normalize(date, hawk, eps_mom, ctx):
            ctx['entry_reason'] = 'HAWK_NORMALIZE'
            return True
    return False

def metrics(name, eq_curve, qqq_df, trade_log):
    eq = eq_curve['equity'].values; n = len(eq); years = n / 252
    cagr = (eq[-1]/eq[0])**(1/years) - 1
    dr = np.diff(eq)/eq[:-1]
    sharpe = np.mean(dr)/np.std(dr)*np.sqrt(252) if np.std(dr)>0 else 0
    peak = np.maximum.accumulate(eq); dd = (eq-peak)/peak; mdd = dd.min()
    calmar = cagr/abs(mdd) if mdd != 0 else np.inf
    in_mkt = (eq_curve['state']=='IN').mean()
    return {'name': name, 'cagr': cagr, 'sharpe': sharpe, 'mdd': mdd, 'calmar': calmar,
            'in_mkt': in_mkt, 'n_trades': len(trade_log), 'final': eq[-1]}

configs = [
    ('Buy&Hold',                  lambda d,h,e,c: False,     lambda d,h,e,c: True),
    ('Hp→(NewEPS|H)',             hawk_pulse_exit,           entry_new_eps_or_hawk),
    ('Hp→v6(Conditional)',        hawk_pulse_exit,           entry_v6_conditional),
]

print(f"{'Strategy':<22} {'CAGR':>7} {'Sharpe':>7} {'MDD':>8} {'Calmar':>7} {'InMkt':>6} {'#Tr':>4} {'$1->':>8}")
print("-" * 82)
all_results = {}
for name, exit_fn, entry_fn in configs:
    eq, trades = run_strategy(name, qqq_sample, exit_fn, entry_fn)
    m = metrics(name, eq, qqq_sample, trades)
    print(f"{m['name']:<22} {m['cagr']:>+6.1%} {m['sharpe']:>7.2f} {m['mdd']:>+7.1%} {m['calmar']:>7.2f} "
          f"{m['in_mkt']:>5.0%} {m['n_trades']:>4} ${m['final']:>7.2f}")
    all_results[name] = trades

print(f"\n{'='*120}")
print(f"TRADE DETAIL: Hp→v6(Conditional)")
print(f"{'='*120}")
trades = all_results['Hp→v6(Conditional)']
print(f"{'Exit Date':>12} {'Exit QQQ':>9} {'EPSatExit':>10} | {'Entry Date':>12} {'Entry QQQ':>9} "
      f"{'Days':>5} {'B&H':>7} {'Reason':>15}")
print(f"{'-'*12} {'-'*9} {'-'*10} | {'-'*12} {'-'*9} {'-'*5} {'-'*7} {'-'*15}")
for t in trades:
    days = (t['entry_date'] - t['exit_date']).days
    bh = t['entry_price']/t['exit_price']-1 if t['exit_price']>0 else 0
    eps_exit = f"{t.get('eps_at_exit', 0):+.1f}%" if pd.notna(t.get('eps_at_exit')) else "N/A"
    reason = t.get('entry_reason', '?')
    still = ' ⏳' if t.get('still_out') else ''
    print(f"{t['exit_date'].strftime('%Y-%m-%d'):>12} ${t['exit_price']:>7.0f} {eps_exit:>10} | "
          f"{t['entry_date'].strftime('%Y-%m-%d'):>12} ${t['entry_price']:>7.0f} "
          f"{days:>4}d {bh:>+6.1%} {reason:>15}{still}")

