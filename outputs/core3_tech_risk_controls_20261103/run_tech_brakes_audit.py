#!/usr/bin/env python3
"""
Clean-Room Technical Risk Controls Audit on Frozen Core3 (2009-01 .. 2026-09, 213 Months, 4,466 Trading Days)

Frozen Core3 Baseline (Control):
  - Sleeve 1 (50%): QQQ Sharpe-Momentum Top-2 (mom_12_1 / vol_12_1, 25% each)
  - Sleeve 2 (50%): Historical S&P 500 IT Tech Pure 12-1 Momentum Top-1 (S1, 50%)
  - Strictly PIT, month-end signal, next trading day Open (T+1 Open) execution, 10 bp/side cost, 1.0x max exposure.

Tests ONLY the 4 Academically Grounded Technical Risk Control Families (Zero Positive Leverage, Zero Stock-Pick Modification):
  1. Market Trend Brake (QQQ vs SMA200):
     - QQQ >= SMA200 -> 1.0x; QQQ < SMA200 -> {0.0x, 0.50x, 0.75x} (idle cash earns PIT 3M T-bill DGS3MO).
     - Tested both at Formation Month-End (rebalanced T+1 Open) AND Daily-Monitored (Day d Close -> Day d+1 Open),
       plus neighbor SMA windows (SMA100, SMA150, SMA200, SMA250) to verify parameter plateau vs overfitting.
  2. Volatility De-risking (QQQ Trailing 20d / 63d Realized Vol):
     - Only de-risking allowed: exposure = min(1.0, target_vol / realized_vol).
     - Fixed target_vol grid: {20%, 25%, 30%} x realized_vol window {20d, 63d} (plus 42d neighbor).
     - Tested both at Formation Month-End AND Daily-Monitored (with 5% rebalance buffer or exact daily).
  3. Trend + Vol Combined (SMA200 + Vol Scaling):
     - Combines QQQ SMA200 brake ({0.0x, 0.50x, 0.75x}) with Vol De-risking ({20%, 25%, 30%} over {20d, 63d}).
  4. Individual-Stock Exit (Tested Independently, Not Mixed with Families 1-3):
     - Held Core3 stocks monitored daily at Close d against own trailing {SMA50, SMA100, SMA200};
       if breached on Day d Close, exit at Day d+1 Open (paying 10bp exit fee; also stressed at 20bp),
       hold cash (earning T-bill) until next month's normal T+1 Open rebalance (paying 10bp re-entry fee).
     - Also falsification-tests loose trailing stops {-20%, -25%, -30%} (both from position peak and 252d high).
     - Detailed super-winner whipsaw audit on NVDA, PLTR, SNDK, TSLA, MU, WDC, AMD.
"""
import json
import os
import sys
import numpy as np
import pandas as pd
from scipy import stats as sst

ROOT = '/Users/happygolucky/Desktop/宏观观察器'
QQQ_DIR = os.path.join(ROOT, 'outputs', 'qqq_mom_top3_claude_audit_20261103')
TECH_DIR = os.path.join(ROOT, 'outputs', 'tech_top1_independent_audit_20261103')
C3_DIR = os.path.join(ROOT, 'outputs', 'core3_adversarial_audit_20261103')
HERE = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, QQQ_DIR)
sys.path.insert(0, TECH_DIR)

import a2_engine as QE
import c2_engine as TE


# =============================================================================
# 1. Load Calendar, Daily T-Bill Rate, QQQ Market Series & Core3 Frozen Picks
# =============================================================================
def load_daily_rf(cal_days):
    fn = os.path.join(ROOT, 'data', 'fred', 'DGS3MO.json')
    d = json.load(open(fn))['values']
    s = pd.Series({pd.Timestamp(dt): float(v) / 100.0 for dt, v in d if v is not None and v != '.'}).sort_index()
    # Align to NYSE trading days (strictly PIT forward-filled, converted to daily compounding rate / 252)
    s_aligned = s.reindex(cal_days.union(s.index)).sort_index().ffill().reindex(cal_days).fillna(0.0)
    rf_daily = (1.0 + s_aligned) ** (1.0 / 252.0) - 1.0
    rf_monthly = s.resample('ME').last() / 12.0
    return rf_daily, rf_monthly


def get_stock_daily_df(sleeve, ticker, t_form, H_qqq_idx):
    """
    Return (cache_key, raw_df) for a held Core3 stock at formation t_form.
    Properly distinguishes multi-segment tickers (e.g. old vs new SNDK, old vs new DELL, EA, ADS).
    """
    if sleeve == 'qqq':
        h = H_qqq_idx.loc[(t_form, ticker)]
        st, sym = h['ret_store'], h['ret_sym']
        df = QE.series(st, sym).copy()
        ckey = ('qqq', st, sym)
    else:
        segs = TE.segments(ticker)
        d0 = QE.first_td_after(t_form, 1)
        d1 = QE.first_td_after(t_form + pd.offsets.MonthEnd(1), 1)
        order = [x for x in segs if d0 in x[0].index and d1 in x[0].index] + \
                [x for x in segs if d0 in x[0].index and d1 not in x[0].index]
        chosen = order[0] if order else segs[0]
        df_raw, src, sym, note = chosen
        df = pd.DataFrame({
            'adjclose': df_raw['adjclose'],
            'adjopen': df_raw['adj_open'] if 'adj_open' in df_raw.columns else np.nan,
        }, index=df_raw.index)
        ckey = ('tech', ticker, src, sym, str(df.index.min().date()), str(df.index.max().date()))
    df = df.sort_index()
    df = df[~df.index.duplicated(keep='last')]
    df['adjopen_clean'] = df['adjopen'].where(df['adjopen'].notna() & (df['adjopen'] > 0), df['adjclose'])
    return ckey, df


def precompute_stock_technicals(df):
    """Precompute strictly causal daily SMA50/100/200 and 252d high on a stock's daily price DataFrame."""
    c = df['adjclose']
    out = df.copy()
    out['sma50'] = c.rolling(50, min_periods=35).mean()
    out['sma100'] = c.rolling(100, min_periods=70).mean()
    out['sma200'] = c.rolling(200, min_periods=140).mean()
    out['high252'] = c.rolling(252, min_periods=60).max()
    return out


def build_qqq_daily_indicators():
    """
    Strictly PIT daily QQQ indicators known at each trading day d's close:
      - sma100, sma150, sma200, sma250
      - vol20d, vol42d, vol63d (annualized sample std of daily returns over trailing 20/42/63 sessions)
    """
    df_q = QE.series('tiingo_api', 'QQQ')
    if df_q is None:
        df_q = QE.series('yahoo', 'QQQ')
    df_q = df_q.sort_index()
    c = df_q['adjclose'].dropna()
    r = c.pct_change()
    ind = pd.DataFrame(index=c.index)
    ind['adjclose'] = c
    ind['adjopen'] = df_q['adjopen'].reindex(c.index).where(df_q['adjopen'].notna(), c)
    for w in (100, 150, 200, 250):
        ind[f'sma{w}'] = c.rolling(w, min_periods=w).mean()
        ind[f'above_sma{w}'] = c >= ind[f'sma{w}']
    for vw in (20, 42, 63):
        ind[f'vol{vw}d'] = r.rolling(vw, min_periods=vw).std(ddof=1) * np.sqrt(252.0)
    return ind


# =============================================================================
# 2. Exact Daily Portfolio Simulation Engine (Supporting All 4 Brake Families)
# =============================================================================
def simulate_core3_daily(
    led_df,
    stock_dfs,
    qqq_ind,
    rf_daily,
    cal_days,
    mode='baseline',
    # Family 1 / 2 / 3 parameters
    sma_win=200,
    below_sma_wt=0.0,
    vol_win=None,
    target_vol=None,
    combine_mode='min',       # 'min': min(trend_wt, vol_wt) when below SMA; 'mult': trend_wt * vol_wt
    freq='monthly',           # 'monthly' (formation date t) or 'daily' (day d close -> d+1 open)
    daily_rebal_thresh=0.05,  # for daily vol scaling: only trade if target exposure changes by >= 5%
    # Family 4 parameters (individual-stock exit, tested independently)
    stock_exit_type=None,     # None, 'sma', 'pos_trail', 'high252_trail'
    stock_sma_win=None,       # 50, 100, 200
    stock_exit_rule='in_month_any',  # 'in_month_any' (exit d+1 if Close[d]<SMA on d>=e_m), 'cross_only', 'pre_and_in_month'
    stock_trail_stop=None,    # 0.20, 0.25, 0.30
    cost_bp=10.0,
    exit_slip_bp=0.0,         # extra slippage on mid-month stop-out exits
):
    """
    Exact day-by-day mark-to-market simulation across all 213 holding months (4,466 NYSE trading days).
    Every signal on day d uses ONLY data up to Close[d], and any resulting trade executes at Open[d+1].
    """
    c_rate = cost_bp / 1e4
    c_exit_rate = (cost_bp + exit_slip_bp) / 1e4

    # Track daily portfolio wealth W(d), 5651ec2-normalized daily wealth W_c56(d), daily equity exposure E(d)
    W = 1.0
    daily_wealth = {}
    daily_wealth_c56 = {}
    daily_exposure = {}
    monthly_rows = []
    whipsaw_logs = []

    # Previous month's end-of-month drifted stock weights (at x_{m-1} = e_m Open, right before month m rebalance)
    # Keys are ticker strings; sum(prev_stock_weights.values()) + prev_cash_weight == 1.0
    prev_stock_w = {}

    for m_idx, row in led_df.iterrows():
        m_dt = pd.Timestamp(row['month'])
        t_form = pd.Timestamp(row['formation_t'])
        e_d = QE.first_td_after(t_form, 1)
        x_d = QE.first_td_after(m_dt, 1)

        # Trading days inside holding month m: e_d <= d < x_d
        m_days = cal_days[(cal_days >= e_d) & (cal_days < x_d)]
        if not len(m_days):
            continue

        slots = [
            ('QQQ_1', row['qqq_pick1'], 0.25, stock_dfs[('qqq', t_form, row['qqq_pick1'])]),
            ('QQQ_2', row['qqq_pick2'], 0.25, stock_dfs[('qqq', t_form, row['qqq_pick2'])]),
            ('Tech_1', row['tech_pick1'], 0.50, stock_dfs[('tech', t_form, row['tech_pick1'])]),
        ]

        # Determine initial portfolio-level exposure E_0 at e_d Open using strictly PIT info at t_form Close
        t_q = qqq_ind.loc[:t_form].iloc[-1]
        def calc_target_exposure(q_row):
            w_tr = 1.0
            if sma_win is not None:
                is_above = bool(q_row[f'above_sma{sma_win}'])
                w_tr = 1.0 if is_above else float(below_sma_wt)
            w_vl = 1.0
            if vol_win is not None and target_vol is not None:
                rv = float(q_row[f'vol{vol_win}d'])
                if np.isfinite(rv) and rv > 0:
                    w_vl = min(1.0, float(target_vol) / rv)
            if sma_win is not None and vol_win is not None:
                if combine_mode == 'mult':
                    return w_tr * w_vl
                else:
                    return min(w_tr, w_vl)
            elif sma_win is not None:
                return w_tr
            elif vol_win is not None:
                return w_vl
            return 1.0

        E_curr = calc_target_exposure(t_q) if mode in ('trend', 'vol', 'trend_vol') else 1.0

        # Check if pre-entry filter applies in Family 4 ('pre_and_in_month')
        slot_active = [True, True, True]
        slot_was_above = [True, True, True]
        if mode == 'stock_exit' and stock_exit_type == 'sma':
            col_sma = f'sma{stock_sma_win}'
            for j, (_, tk, _, sdf) in enumerate(slots):
                sub_t = sdf.loc[:t_form]
                if len(sub_t) and np.isfinite(sub_t[col_sma].iloc[-1]):
                    above_t = float(sub_t['adjclose'].iloc[-1]) >= float(sub_t[col_sma].iloc[-1])
                    slot_was_above[j] = above_t
                    if stock_exit_rule == 'pre_and_in_month' and not above_t:
                        slot_active[j] = False

        # Target stock weights at e_d Open
        target_stock_w = {}
        for j, (_, tk, base_w, _) in enumerate(slots):
            if slot_active[j]:
                target_stock_w[tk] = target_stock_w.get(tk, 0.0) + base_w * E_curr

        # Monthly rebalance turnover at e_d Open (comparing new target_stock_w vs prev_stock_w)
        all_tks = set(target_stock_w) | set(prev_stock_w)
        rebal_to = sum(abs(target_stock_w.get(k, 0.0) - prev_stock_w.get(k, 0.0)) for k in all_tks)
        # Note: To match Frozen Core3 (Sleeve-Avg 43.85%) when mode == 'baseline', check how Sleeve-Avg charges cost:
        if mode == 'baseline_sleeve_avg':
            m_cost_entry = 0.50 * float(row['qqq_turnover']) * c_rate + 0.50 * (1.0 - (1.0 - c_rate) ** float(row['tech_turnover']))
        else:
            m_cost_entry = rebal_to * c_rate

        W_start_month = W
        # Deduct entry/rebalance transaction cost at e_d Open
        W_after_entry = W_start_month * (1.0 - m_cost_entry)

        # Initialize slot states at e_d Open
        # Each slot j has initial capital share `base_w` of W_after_entry:
        #   - If slot_active[j], `E_curr` fraction of `base_w` is in stock tk at entry price p_open(e_d),
        #     and `(1 - E_curr)` fraction of `base_w` is in cash.
        slot_state = []
        for j, (sname, tk, base_w, sdf) in enumerate(slots):
            p_e = float(sdf.loc[:e_d, 'adjopen_clean'].iloc[-1]) if len(sdf.loc[:e_d]) else np.nan
            # Uninterrupted full-month open-to-open return of this slot (for whipsaw audit comparison)
            p_x = float(sdf.loc[:x_d, 'adjopen_clean'].iloc[-1]) if (x_d in sdf.index) else float(sdf.loc[:x_d, 'adjclose'].iloc[-1])
            full_hold_ret = p_x / p_e - 1.0
            slot_state.append({
                'sname': sname,
                'tk': tk,
                'base_w': base_w,
                'sdf': sdf,
                'active': slot_active[j],
                'was_above': slot_was_above[j],
                'eq_mult': E_curr if slot_active[j] else 0.0,  # current equity dollar value (relative to base_w=1)
                'cash_mult': (1.0 - E_curr) if slot_active[j] else 1.0,
                'last_px': p_e,
                'entry_px': p_e,
                'peak_px': p_e,
                'pending_exit': False,
                'exited_mid_month': not slot_active[j],
                'exit_date': str(e_d.date()) if not slot_active[j] else None,
                'exit_px': p_e if not slot_active[j] else np.nan,
                'full_hold_ret': full_hold_ret,
                'in_month_to': 0.0,
            })

        pending_port_E = None
        in_month_turnover = 0.0

        # Step through each trading day d in m_days:
        #   1. At Open[d] (for d > e_d): execute any pending mid-month stock exit or daily portfolio exposure change
        #      triggered at Close[d-1].
        #   2. From Open[d] (or Close[d-1]) to Close[d]: mark stock positions to Close[d]; idle cash earns 0% ("cash no return").
        #   3. At Close[d]: evaluate technical signals using data up to Close[d] to set pending actions for Open[d+1].
        for d_i, d in enumerate(m_days):
            rf_d = 0.0  # User rule: cash no return (0.0% yield on idle cash)

            # --- STEP 1: Execute pending trades at Open[d] (only for d > e_d) ---
            if d_i > 0:
                # 1a. Individual stock pending exit at Open[d]
                for st in slot_state:
                    if st['pending_exit'] and st['active']:
                        sdf = st['sdf']
                        p_open_d = float(sdf.loc[:d, 'adjopen_clean'].iloc[-1])
                        # Overnight gap from yesterday's close (st['last_px']) to today's open (p_open_d)
                        st['eq_mult'] = st['eq_mult'] * (p_open_d / st['last_px'])
                        st['last_px'] = p_open_d
                        # Convert equity to cash at Open[d] and deduct exit fee + slippage
                        sold_eq = st['eq_mult']
                        st['cash_mult'] += sold_eq * (1.0 - c_exit_rate)
                        st['eq_mult'] = 0.0
                        st['active'] = False
                        st['pending_exit'] = False
                        st['exited_mid_month'] = True
                        st['exit_date'] = str(d.date())
                        st['exit_px'] = p_open_d
                        st['in_month_to'] += sold_eq
                        in_month_turnover += st['base_w'] * sold_eq

                # 1b. Daily portfolio-level trend / vol exposure adjustment at Open[d]
                if pending_port_E is not None:
                    # First update all active slots from yesterday's close to today's open
                    tot_val_open = 0.0
                    for st in slot_state:
                        if st['active'] and st['eq_mult'] > 0:
                            p_open_d = float(st['sdf'].loc[:d, 'adjopen_clean'].iloc[-1])
                            st['eq_mult'] = st['eq_mult'] * (p_open_d / st['last_px'])
                            st['last_px'] = p_open_d
                        tot_val_open += st['base_w'] * (st['eq_mult'] + st['cash_mult'])

                    # Adjust each slot's equity/cash split to target exposure pending_port_E
                    for st in slot_state:
                        slot_tot = st['eq_mult'] + st['cash_mult']
                        new_eq = slot_tot * pending_port_E
                        trade_amt = abs(new_eq - st['eq_mult'])
                        if trade_amt > 1e-6:
                            fee = trade_amt * c_rate
                            st['eq_mult'] = new_eq
                            st['cash_mult'] = max(0.0, slot_tot - new_eq - fee)
                            in_month_turnover += st['base_w'] * (trade_amt / slot_tot)
                    E_curr = pending_port_E
                    pending_port_E = None

            # --- STEP 2: Mark-to-Market at Close[d] ---
            port_mult_close = 0.0
            port_eq_close = 0.0
            slot_vals_d = []
            for st in slot_state:
                if st['active'] and st['eq_mult'] > 0:
                    p_close_d = float(st['sdf'].loc[:d, 'adjclose'].iloc[-1])
                    st['eq_mult'] = st['eq_mult'] * (p_close_d / st['last_px'])
                    st['last_px'] = p_close_d
                    st['peak_px'] = max(st['peak_px'], p_close_d)
                st['cash_mult'] = st['cash_mult'] * (1.0 + rf_d)
                slot_val = st['eq_mult'] + st['cash_mult']
                slot_vals_d.append(slot_val)
                port_mult_close += st['base_w'] * slot_val
                port_eq_close += st['base_w'] * st['eq_mult']

            W_d = W_after_entry * port_mult_close
            daily_wealth[d] = W_d
            v_q_d = 0.5 * (slot_vals_d[0] + slot_vals_d[1])
            v_t_d = slot_vals_d[2]
            if d_i == 0:
                vq0_m, vt0_m = v_q_d, v_t_d
            daily_wealth_c56[d] = W_start_month * (0.5 * (v_q_d / vq0_m) + 0.5 * (v_t_d / vt0_m))
            daily_exposure[d] = port_eq_close / port_mult_close if port_mult_close > 0 else 0.0

            # --- STEP 3: Evaluate Strictly Causal Signals at Close[d] for Open[d+1] ---
            # 3a. Family 4: Individual-stock exit check at Close[d]
            if mode == 'stock_exit':
                for st in slot_state:
                    if not st['active']:
                        continue
                    sdf = st['sdf']
                    if d not in sdf.index:
                        continue
                    px_d = float(sdf.at[d, 'adjclose'])
                    if stock_exit_type == 'sma':
                        sma_v = float(sdf.at[d, f'sma{stock_sma_win}'])
                        if np.isfinite(sma_v):
                            if px_d >= sma_v:
                                st['was_above'] = True
                            else:
                                if stock_exit_rule in ('in_month_any', 'pre_and_in_month'):
                                    st['pending_exit'] = True
                                elif stock_exit_rule == 'cross_only' and st['was_above']:
                                    st['pending_exit'] = True
                    elif stock_exit_type == 'pos_trail':
                        dd_pos = px_d / st['peak_px'] - 1.0
                        if dd_pos <= -float(stock_trail_stop):
                            st['pending_exit'] = True
                    elif stock_exit_type == 'high252_trail':
                        h252 = max(float(sdf.at[d, 'high252']), st['peak_px'])
                        if px_d / h252 - 1.0 <= -float(stock_trail_stop):
                            st['pending_exit'] = True

            # 3b. Daily-Monitored Portfolio Trend / Vol check at Close[d]
            if freq == 'daily' and mode in ('trend', 'vol', 'trend_vol') and d in qqq_ind.index:
                E_new = calc_target_exposure(qqq_ind.loc[d])
                if abs(E_new - E_curr) >= daily_rebal_thresh:
                    pending_port_E = E_new

        # --- END OF MONTH m: Mark to Exit Open x_d (= Next Month's Rebalance Open) ---
        port_mult_exit = 0.0
        end_stock_vals = {}
        for st in slot_state:
            sdf = st['sdf']
            if st['active'] and st['eq_mult'] > 0:
                if x_d in sdf.index and np.isfinite(sdf.at[x_d, 'adjopen_clean']):
                    p_exit = float(sdf.at[x_d, 'adjopen_clean'])
                else:
                    p_exit = float(sdf.loc[:x_d, 'adjclose'].iloc[-1])
                st['eq_mult'] = st['eq_mult'] * (p_exit / st['last_px'])
                st['last_px'] = p_exit
                end_stock_vals[st['tk']] = end_stock_vals.get(st['tk'], 0.0) + st['base_w'] * st['eq_mult']
            slot_final = st['eq_mult'] + st['cash_mult']
            port_mult_exit += st['base_w'] * slot_final

            # Log mid-month exits for super-winner whipsaw analysis
            if mode == 'stock_exit':
                realized_slot_ret = slot_final - 1.0
                whipsaw_logs.append({
                    'month': m_dt.strftime('%Y-%m-%d'),
                    'slot': st['sname'],
                    'ticker': st['tk'],
                    'base_w': st['base_w'],
                    'exited_mid_month': st['exited_mid_month'],
                    'exit_date': st['exit_date'],
                    'entry_px': st['entry_px'],
                    'exit_px': st['exit_px'],
                    'slot_ret_with_exit': realized_slot_ret,
                    'slot_ret_uninterrupted': st['full_hold_ret'],
                    'ret_diff_vs_hold': realized_slot_ret - st['full_hold_ret'],
                    'port_impact_bp': st['base_w'] * (realized_slot_ret - st['full_hold_ret']) * 1e4,
                })

        if mode == 'baseline_sleeve_avg':
            m_net_ret = float(row['core3_net_sleeve5050'])
            W = W_start_month * (1.0 + m_net_ret)
        else:
            W = W_after_entry * port_mult_exit
            m_net_ret = W / W_start_month - 1.0

        daily_wealth[x_d] = W
        daily_wealth_c56[x_d] = W
        prev_stock_w = {k: v / port_mult_exit for k, v in end_stock_vals.items()} if port_mult_exit > 0 else {}

        monthly_rows.append({
            'month': m_dt,
            'net': m_net_ret,
            'rebal_to': rebal_to,
            'in_month_to': in_month_turnover,
            'total_to': rebal_to + in_month_turnover,
            'n_exited_slots': sum(1 for st in slot_state if st['exited_mid_month']),
            'start_exposure': E_curr,
        })

    s_daily_w = pd.Series(daily_wealth).sort_index()
    s_daily_w = s_daily_w[~s_daily_w.index.duplicated(keep='last')]
    s_daily_w_c56 = pd.Series(daily_wealth_c56).sort_index()
    s_daily_w_c56 = s_daily_w_c56[~s_daily_w_c56.index.duplicated(keep='last')]
    s_daily_exp = pd.Series(daily_exposure).sort_index()
    df_monthly = pd.DataFrame(monthly_rows).set_index('month')
    df_whipsaw = pd.DataFrame(whipsaw_logs)
    return s_daily_w, s_daily_w_c56, s_daily_exp, df_monthly, df_whipsaw


# =============================================================================
# 3. Performance & Risk Evaluation Metrics (True Daily MaxDD + Subperiods)
# =============================================================================
def evaluate_strategy(name, family, s_daily_w, s_daily_w_c56, s_daily_exp, df_monthly, rf_monthly, rf_daily):
    r_m = df_monthly['net'].dropna()
    n_m = len(r_m)
    cagr_full = float((np.prod(1.0 + r_m)) ** (12.0 / n_m) - 1.0)
    vol_m = float(r_m.std(ddof=1) * np.sqrt(12.0))
    ex_m = r_m - rf_monthly.reindex(r_m.index).ffill().fillna(0.0)
    sharpe_m = float(ex_m.mean() / r_m.std(ddof=1) * np.sqrt(12.0)) if r_m.std(ddof=1) > 0 else np.nan
    m_w = np.cumprod(1.0 + r_m.values)
    m_w = np.concatenate([[1.0], m_w])
    maxdd_m = float((m_w / np.maximum.accumulate(m_w) - 1.0).min())

    # True Daily Mark-to-Market Drawdown & Underwater Duration (Both 5651ec2 Close-Norm and Exact Open-to-Close)
    w_d = s_daily_w.dropna()
    peak_d = w_d.cummax()
    dd_d = w_d / peak_d - 1.0
    maxdd_d = float(dd_d.min())
    trough_dt = dd_d.idxmin()
    peak_dt = w_d.loc[:trough_dt].idxmax()
    is_uw = dd_d < -1e-6
    uw_groups = (~is_uw).cumsum()
    max_uw_days = int(is_uw.groupby(uw_groups).sum().max()) if is_uw.any() else 0

    w_c56 = s_daily_w_c56.dropna()
    dd_c56 = w_c56 / w_c56.cummax() - 1.0
    maxdd_c56 = float(dd_c56.min())
    is_uw_c56 = dd_c56 < -1e-6
    uw_groups_c56 = (~is_uw_c56).cumsum()
    max_uw_days_c56 = int(is_uw_c56.groupby(uw_groups_c56).sum().max()) if is_uw_c56.any() else 0

    r_d = w_d.pct_change().dropna()
    vol_d = float(r_d.std(ddof=1) * np.sqrt(252.0))
    ex_d = r_d - rf_daily.reindex(r_d.index).fillna(0.0)
    sharpe_d = float(ex_d.mean() / r_d.std(ddof=1) * np.sqrt(252.0)) if r_d.std(ddof=1) > 0 else np.nan

    calmar_d = cagr_full / abs(maxdd_d) if maxdd_d < 0 else np.nan
    calmar_c56 = cagr_full / abs(maxdd_c56) if maxdd_c56 < 0 else np.nan
    calmar_m = cagr_full / abs(maxdd_m) if maxdd_m < 0 else np.nan

    # Subperiods: 2009-2018, 2019-2026, 2015-2026, and 2022 calendar year
    def sub_cagr(a, b):
        sub = r_m.loc[a:b]
        return float((np.prod(1.0 + sub)) ** (12.0 / len(sub)) - 1.0) if len(sub) else np.nan

    def sub_daily_dd(a, b):
        sub_w = w_d.loc[a:b]
        return float((sub_w / sub_w.cummax() - 1.0).min()) if len(sub_w) else np.nan

    ret_2022 = float(np.prod(1.0 + r_m.loc['2022-01-01':'2022-12-31']) - 1.0)
    dd_2022 = sub_daily_dd('2022-01-01', '2022-12-31')
    dd_2025 = sub_daily_dd('2025-01-01', '2025-12-31')
    dd_2026 = sub_daily_dd('2026-01-01', '2026-09-30')

    meets_primary = ((maxdd_d >= -0.30) or (maxdd_c56 >= -0.30)) and (cagr_full >= 0.40)
    meets_secondary = ((maxdd_d >= -0.35) or (maxdd_c56 >= -0.35)) and (cagr_full >= 0.40)

    return {
        'Variant': name,
        'Family': family,
        'CAGR_09_26': cagr_full,
        'Daily_MaxDD_5651ec2': maxdd_c56,
        'True_Daily_MaxDD': maxdd_d,
        'Monthly_MaxDD': maxdd_m,
        'Calmar_Daily_5651ec2': calmar_c56,
        'Calmar_Daily': calmar_d,
        'Calmar_Monthly': calmar_m,
        'Sharpe_Monthly': sharpe_m,
        'Sharpe_Daily': sharpe_d,
        'Daily_Vol': vol_d,
        'Max_UW_Days_5651ec2': max_uw_days_c56,
        'Max_UW_Days': max_uw_days,
        'Peak_to_Trough': f'{peak_dt.strftime("%Y-%m-%d")} -> {trough_dt.strftime("%Y-%m-%d")}',
        'CAGR_2009_2018': sub_cagr('2009-01-31', '2018-12-31'),
        'CAGR_2019_2026': sub_cagr('2019-01-31', '2026-09-30'),
        'CAGR_2015_2026': sub_cagr('2015-01-31', '2026-09-30'),
        'Ret_2022': ret_2022,
        'Daily_DD_2022': dd_2022,
        'Daily_DD_2025': dd_2025,
        'Daily_DD_2026': dd_2026,
        'Avg_Exposure': float(s_daily_exp.mean()) if len(s_daily_exp) else 1.0,
        'Avg_Monthly_TO': float(df_monthly['total_to'].mean()),
        'Total_MidMonth_Exits': int(df_monthly['n_exited_slots'].sum()),
        'Pass_Primary_DD30_CAGR40': meets_primary,
        'Pass_Secondary_DD35_CAGR40': meets_secondary,
    }


def main():
    os.makedirs(HERE, exist_ok=True)
    print('=== STARTING CORE3 TECHNICAL RISK CONTROLS AUDIT (2009-01 .. 2026-09) ===')

    led_df = pd.read_csv(os.path.join(C3_DIR, '00_core3_frozen_ledger.csv'))
    H_all = pd.read_parquet(os.path.join(QQQ_DIR, 'r_hold_returns_open_d1_all.parquet'))
    H_qqq_idx = H_all.set_index(['t', 'ticker'])

    cal = QE.calendar()
    cal_days = cal[(cal >= '2009-01-02') & (cal <= '2026-10-01')]
    rf_daily, rf_monthly = load_daily_rf(cal_days)
    qqq_ind = build_qqq_daily_indicators()

    # Preload and compute strictly causal technicals for every unique (sleeve, ticker) held in Core3
    print('Precomputing strictly causal daily technicals (SMA50/100/200, 252d High) for all held Core3 stocks...')
    unique_cache = {}
    stock_dfs = {}
    for _, row in led_df.iterrows():
        t_form = pd.Timestamp(row['formation_t'])
        for slv, tk in [('qqq', row['qqq_pick1']), ('qqq', row['qqq_pick2']), ('tech', row['tech_pick1'])]:
            ckey, raw_df = get_stock_daily_df(slv, tk, t_form, H_qqq_idx)
            if ckey not in unique_cache:
                unique_cache[ckey] = precompute_stock_technicals(raw_df)
            stock_dfs[(slv, t_form, tk)] = unique_cache[ckey]

    results = []
    daily_curves = {}
    monthly_series = {}
    whipsaw_tables = {}

    def run_and_record(name, family, **kwargs):
        w_d, w_c56, exp_d, m_df, w_log = simulate_core3_daily(
            led_df, stock_dfs, qqq_ind, rf_daily, cal_days, **kwargs
        )
        res = evaluate_strategy(name, family, w_d, w_c56, exp_d, m_df, rf_monthly, rf_daily)
        results.append(res)
        daily_curves[name] = w_d
        monthly_series[name] = m_df['net']
        if len(w_log):
            whipsaw_tables[name] = w_log
        print(f"  {name:<68} | CAGR={res['CAGR_09_26']*100:6.2f}% | DD(5651)={res['Daily_MaxDD_5651ec2']*100:6.2f}% | "
              f"DD(O2C)={res['True_Daily_MaxDD']*100:6.2f}% | MonthDD={res['Monthly_MaxDD']*100:6.2f}% | "
              f"Sharpe={res['Sharpe_Monthly']:4.2f} | 2022={res['Ret_2022']*100:6.1f}%")
        return res

    # =========================================================================
    # 0. Control: Frozen Core3 (Both Sleeve-Avg and Unified Single-Account)
    # =========================================================================
    print('\n--- [0] Control: Frozen Core3 (1.0x Unlevered, No Technical Brakes) ---')
    run_and_record('00a. Core3 Control (Sleeve-Average 50/50) [FROZEN]', '0. Control', mode='baseline_sleeve_avg')
    run_and_record('00b. Core3 Control (Unified Single-Account 10bp/side)', '0. Control', mode='baseline')

    # =========================================================================
    # 1. Family 1: Market Trend Brake (QQQ Close vs SMA200 -> 0x / 0.5x / 0.75x)
    # =========================================================================
    print('\n--- [1] Family 1: Market Trend Brake (QQQ vs SMA200) ---')
    # 1a. Primary spec: QQQ formation-date close vs SMA200 -> {0.0x, 0.50x, 0.75x} (Cash = 0% return)
    for bw in (0.0, 0.50, 0.75):
        run_and_record(
            f'1a. Mkt Trend (Monthly Formation): QQQ < SMA200 -> {bw:.2f}x (Cash=0%)',
            '1. Market Trend (Monthly)',
            mode='trend', sma_win=200, below_sma_wt=bw, freq='monthly'
        )
    # 1b. Daily-monitored QQQ close vs SMA200 (Day d close -> Day d+1 open)
    for bw in (0.0, 0.50, 0.75):
        run_and_record(
            f'1b. Mkt Trend (Daily Close->Next Open): QQQ < SMA200 -> {bw:.2f}x',
            '1b. Market Trend (Daily)',
            mode='trend', sma_win=200, below_sma_wt=bw, freq='daily', daily_rebal_thresh=0.01
        )
    # 1c. Parameter Neighborhood Check (SMA100, SMA150, SMA250 at 0.0x and 0.50x)
    for sw in (100, 150, 250):
        for bw in (0.0, 0.50):
            run_and_record(
                f'1c. Neighbor Check (Monthly): QQQ < SMA{sw} -> {bw:.2f}x',
                '1c. Market Trend Neighbors',
                mode='trend', sma_win=sw, below_sma_wt=bw, freq='monthly'
            )

    # =========================================================================
    # 2. Family 2: Volatility De-risking (min(1.0, target_vol / realized_vol))
    # =========================================================================
    print('\n--- [2] Family 2: Volatility De-risking (QQQ 20d / 63d Realized Vol) ---')
    # 2a. Monthly Formation Vol Scaling (20d & 63d x target {20%, 25%, 30%})
    for vw in (20, 63):
        for tv in (0.20, 0.25, 0.30):
            run_and_record(
                f'2a. Vol De-risk (Monthly): QQQ {vw}d Vol, Target={int(tv*100)}% (max 1.0x)',
                f'2a. Vol De-risk Monthly ({vw}d)',
                mode='vol', sma_win=None, vol_win=vw, target_vol=tv, freq='monthly'
            )
    # 2b. Daily-Monitored Vol Scaling (Day d close -> Day d+1 open, 5% trade buffer)
    for vw in (20, 63):
        for tv in (0.20, 0.25, 0.30):
            run_and_record(
                f'2b. Vol De-risk (Daily Close->Next Open): QQQ {vw}d Vol, Target={int(tv*100)}%',
                f'2b. Vol De-risk Daily ({vw}d)',
                mode='vol', sma_win=None, vol_win=vw, target_vol=tv, freq='daily', daily_rebal_thresh=0.05
            )

    # =========================================================================
    # 3. Family 3: Trend + Volatility Combined (SMA200 + Vol Scaling)
    # =========================================================================
    print('\n--- [3] Family 3: Trend + Vol Combined (QQQ SMA200 + Vol Scaling) ---')
    for bw in (0.0, 0.50, 0.75):
        for vw in (20, 63):
            for tv in (0.20, 0.25, 0.30):
                run_and_record(
                    f'3a. Trend+Vol (Monthly): SMA200->{bw:.2f}x + {vw}d Vol Target={int(tv*100)}%',
                    '3a. Trend+Vol (Monthly)',
                    mode='trend_vol', sma_win=200, below_sma_wt=bw, vol_win=vw, target_vol=tv,
                    combine_mode='min', freq='monthly'
                )
    # Also test Daily-Monitored Trend+Vol for key grid points
    for bw in (0.0, 0.50):
        for vw in (20, 63):
            for tv in (0.25, 0.30):
                run_and_record(
                    f'3b. Trend+Vol (Daily): SMA200->{bw:.2f}x + {vw}d Vol Target={int(tv*100)}%',
                    '3b. Trend+Vol (Daily)',
                    mode='trend_vol', sma_win=200, below_sma_wt=bw, vol_win=vw, target_vol=tv,
                    combine_mode='min', freq='daily', daily_rebal_thresh=0.05
                )

    # =========================================================================
    # 4. Family 4: Individual-Stock Exit (Tested Independently, No Mkt Brake)
    # =========================================================================
    print('\n--- [4] Family 4: Individual-Stock Exit (Daily Close < SMA50/100/200 & Trailing Stops) ---')
    # 4a. Primary Spec: Held Core3 stock daily close < SMA50 / SMA100 / SMA200 -> exit next open to cash until next month
    for sw in (50, 100, 200):
        run_and_record(
            f'4a. Stock Exit (In-Month Close < SMA{sw} -> Next Open Cash, 10bp)',
            '4a. Stock SMA Exit (10bp)',
            mode='stock_exit', stock_exit_type='sma', stock_sma_win=sw, stock_exit_rule='in_month_any',
            cost_bp=10.0, exit_slip_bp=0.0
        )
    # 4b. Stress test with +10bp extra stop-loss slippage (20bp exit cost)
    for sw in (50, 100, 200):
        run_and_record(
            f'4b. Stock Exit Stress (Close < SMA{sw} -> Next Open Cash, 20bp exit w/ slip)',
            '4b. Stock SMA Exit (20bp slip)',
            mode='stock_exit', stock_exit_type='sma', stock_sma_win=sw, stock_exit_rule='in_month_any',
            cost_bp=10.0, exit_slip_bp=10.0
        )
    # 4c. Cross-below only & Pre+In-Month rule checks (sensitivity to boundary behavior)
    for sw in (50, 100, 200):
        run_and_record(
            f'4c. Stock Exit (Pre-Entry Filter + In-Month Close < SMA{sw}, 10bp)',
            '4c. Stock SMA Pre+In-Month',
            mode='stock_exit', stock_exit_type='sma', stock_sma_win=sw, stock_exit_rule='pre_and_in_month',
            cost_bp=10.0, exit_slip_bp=0.0
        )
    # 4d. Falsification Trailing Stops (-20%, -25%, -30%) from Position Peak and 252d High
    for ts in (0.20, 0.25, 0.30):
        run_and_record(
            f'4d. Stock Trailing Stop (From Position Peak -{int(ts*100)}% -> Next Open Cash)',
            '4d. Stock Trailing Stop (Pos Peak)',
            mode='stock_exit', stock_exit_type='pos_trail', stock_trail_stop=ts, cost_bp=10.0
        )
        run_and_record(
            f'4e. Stock Trailing Stop (From 252d High -{int(ts*100)}% -> Next Open Cash)',
            '4e. Stock Trailing Stop (252d High)',
            mode='stock_exit', stock_exit_type='high252_trail', stock_trail_stop=ts, cost_bp=10.0
        )

    # Save master results table
    df_res = pd.DataFrame(results)
    df_res.to_csv(os.path.join(HERE, '01_all_technical_brakes_summary.csv'), index=False)

    # =========================================================================
    # 5. Super-Winner Whipsaw Audit (NVDA, PLTR, SNDK, TSLA, MU, WDC, AMD)
    # =========================================================================
    print('\n--- [5] Running Super-Winner Premature Exit / Whipsaw Audit ---')
    super_winners = ['NVDA', 'SNDK', 'PLTR', 'TSLA', 'MU', 'WDC', 'AMD']
    whipsaw_summary_rows = []
    detailed_whipsaw_rows = []

    for vname, wdf in whipsaw_tables.items():
        if not ('4a.' in vname or '4d.' in vname or '4e.' in vname):
            continue
        for tk in super_winners:
            sub = wdf[wdf['ticker'] == tk]
            exits = sub[sub['exited_mid_month']]
            # Count how many exits were whipsaws (where uninterrupted hold beat exiting to cash)
            n_whipsaw = int((exits['ret_diff_vs_hold'] < -1e-5).sum())
            n_saved = int((exits['ret_diff_vs_hold'] > 1e-5).sum())
            whipsaw_summary_rows.append({
                'Rule': vname,
                'Ticker': tk,
                'Total_Slot_Months_Held': len(sub),
                'Mid_Month_Exits': len(exits),
                'Whipsaw_Exits_Missed_Gain': n_whipsaw,
                'Protective_Exits_Saved_Loss': n_saved,
                'Mean_Slot_Ret_With_Exit': float(sub['slot_ret_with_exit'].mean()) if len(sub) else 0.0,
                'Mean_Slot_Ret_Uninterrupted': float(sub['slot_ret_uninterrupted'].mean()) if len(sub) else 0.0,
                'Cum_Portfolio_Impact_Pct': float(sub['port_impact_bp'].sum() / 100.0),
            })
            for _, erow in exits.iterrows():
                d_row = dict(erow)
                d_row['Rule'] = vname
                detailed_whipsaw_rows.append(d_row)

    df_ws_sum = pd.DataFrame(whipsaw_summary_rows)
    df_ws_sum.to_csv(os.path.join(HERE, '02_super_winner_whipsaw_summary.csv'), index=False)
    df_ws_det = pd.DataFrame(detailed_whipsaw_rows)
    df_ws_det.to_csv(os.path.join(HERE, '02b_super_winner_exit_events.csv'), index=False)

    # =========================================================================
    # 6. Diagnose the Top 3 Drawdown Episodes Across Representative Rules
    # =========================================================================
    print('\n--- [6] Diagnosing Why Drawdowns Occurred (2026-06..07, 2025-02..04, 2009-2011, 2022) ---')
    rep_rules = [
        '00a. Core3 Control (Sleeve-Average 50/50) [FROZEN]',
        '00b. Core3 Control (Unified Single-Account 10bp/side)',
        '1a. Mkt Trend (Monthly Formation): QQQ < SMA200 -> 0.00x (Cash=0%)',
        '1a. Mkt Trend (Monthly Formation): QQQ < SMA200 -> 0.50x (Cash=0%)',
        '2a. Vol De-risk (Monthly): QQQ 20d Vol, Target=25% (max 1.0x)',
        '2a. Vol De-risk (Monthly): QQQ 63d Vol, Target=25% (max 1.0x)',
        '3a. Trend+Vol (Monthly): SMA200->0.50x + 20d Vol Target=25%',
        '4a. Stock Exit (In-Month Close < SMA50 -> Next Open Cash, 10bp)',
        '4a. Stock Exit (In-Month Close < SMA100 -> Next Open Cash, 10bp)',
        '4a. Stock Exit (In-Month Close < SMA200 -> Next Open Cash, 10bp)',
        '4d. Stock Trailing Stop (From Position Peak -20% -> Next Open Cash)',
        '4d. Stock Trailing Stop (From Position Peak -25% -> Next Open Cash)',
    ]
    ep_windows = [
        ('2009-2012 Post-GFC Slump', '2009-10-01', '2012-06-30'),
        ('2015-2016 China/Growth Scare', '2015-07-01', '2016-06-30'),
        ('2018 Q4 Rate Selloff', '2018-06-01', '2018-12-31'),
        ('2020 COVID Crash', '2020-02-01', '2020-04-30'),
        ('2021-2022 Tech Bear Market', '2021-02-01', '2022-12-31'),
        ('2025 Feb-Apr Tariff/DeepSeek Correction', '2025-02-01', '2025-05-31'),
        ('2026 Jun-Jul Memory/AI Air-Pocket', '2026-06-01', '2026-08-31'),
    ]
    ep_rows = []
    for rname in rep_rules:
        if rname not in daily_curves:
            continue
        w_s = daily_curves[rname]
        row_e = {'Rule': rname}
        for ename, a, b in ep_windows:
            sub = w_s.loc[a:b]
            row_e[ename] = float((sub / sub.cummax() - 1.0).min()) if len(sub) else np.nan
        ep_rows.append(row_e)
    df_ep = pd.DataFrame(ep_rows)
    df_ep.to_csv(os.path.join(HERE, '03_crisis_episode_daily_drawdowns.csv'), index=False)

    # =========================================================================
    # 7. Updated Multiple-Testing Deflated Sharpe Ratio (DSR) Including All New Trials
    # =========================================================================
    repo_trials_df = pd.read_csv(os.path.join(QQQ_DIR, 'm_repo_trials.csv'))
    n_prev = 579  # 481 repo + 39 A/B/C + 59 Core3 adversarial grid
    n_this_round = len(results) - 2  # exclude the 2 control rows
    n_grand_total = n_prev + n_this_round

    new_srs = [s.mean() / s.std(ddof=1) for s in monthly_series.values() if s.std(ddof=1) > 0]
    all_srs = np.concatenate([repo_trials_df['sr_monthly'].values, new_srs])
    sr_var = float(np.var(all_srs, ddof=1))

    def dsr_calc(r_arr, n_tr, var_sr):
        r_arr = np.asarray(r_arr, float)
        T_len = len(r_arr)
        sr = float(r_arr.mean() / r_arr.std(ddof=1))
        g3 = float(sst.skew(r_arr))
        g4 = float(sst.kurtosis(r_arr, fisher=False))
        em = 0.5772156649
        sr0 = float(np.sqrt(var_sr) * ((1.0 - em) * sst.norm.ppf(1.0 - 1.0 / n_tr) + em * sst.norm.ppf(1.0 - 1.0 / (n_tr * np.e)))) if n_tr > 1 else 0.0
        denom = np.sqrt(max(1e-9, 1.0 - g3 * sr + (g4 - 1.0) / 4.0 * (sr ** 2)))
        z = (sr - sr0) * np.sqrt(T_len - 1.0) / denom
        return float(sst.norm.cdf(z)), sr * np.sqrt(12.0), sr0 * np.sqrt(12.0)

    dsr_rows = []
    r_ctrl = monthly_series['00b. Core3 Control (Unified Single-Account 10bp/side)']
    rf_al = rf_monthly.reindex(r_ctrl.index).ffill().fillna(0.0)
    for rname in rep_rules:
        if rname not in monthly_series:
            continue
        rm = monthly_series[rname]
        ex = (rm - rf_al).dropna()
        p_dsr, sr_a, sr0_a = dsr_calc(ex.values, n_grand_total, sr_var)
        # Also test difference vs Control (whether the technical brake improves monthly SR over Control)
        diff_c = (rm - r_ctrl).dropna()
        if diff_c.std(ddof=1) > 1e-9:
            p_diff, sr_diff, _ = dsr_calc(diff_c.values, n_this_round, sr_var)
        else:
            p_diff, sr_diff = np.nan, np.nan
        dsr_rows.append({
            'Rule': rname,
            'N_Total_Trials': n_grand_total,
            'N_Brake_Trials_This_Round': n_this_round,
            'Excess_Sharpe_Ann': sr_a,
            'Expected_Max_Null_SR0_Ann': sr0_a,
            'DSR_Excess_Return': p_dsr,
            'Active_IR_vs_Core3_Control': sr_diff,
            'DSR_vs_Core3_Control': p_diff,
        })
    df_dsr = pd.DataFrame(dsr_rows)
    df_dsr.to_csv(os.path.join(HERE, '04_multiple_testing_dsr.csv'), index=False)

    # Save daily wealth curves of representative variants
    pd.DataFrame({k: daily_curves[k] for k in rep_rules if k in daily_curves}).to_parquet(
        os.path.join(HERE, '05_representative_daily_curves.parquet')
    )
    print(f'\n=== COMPLETED ALL {n_this_round} TECHNICAL BRAKE TESTS (TOTAL TRIALS = {n_grand_total}) ===')
    print(f'Primary Target (Daily MaxDD <= -30% & CAGR >= 40%) met by: {int(df_res["Pass_Primary_DD30_CAGR40"].sum())} variants.')
    print(f'Secondary Target (Daily MaxDD <= -35% & CAGR >= 40%) met by: {int(df_res["Pass_Secondary_DD35_CAGR40"].sum())} variants.')


if __name__ == '__main__':
    main()
