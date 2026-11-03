#!/usr/bin/env python3
"""
run_consensus_burst_audit.py — Clean-Room Scientific Audit of Consensus States & 4 "Burst Modes"
================================================================================================
Tests the user's high-conviction state / multi-leg consensus hypothesis on top of the audited
unlevered base engines (3S_G1_1k, 3S_G1_1a, 3S_Core3_1a, G1_SPY_2e, G1, Core3) across all
213 holding months (2009-01 .. 2026-09):

  1. Priority #1 — The "Burst Switch" Diagnostic Table (01_consensus_overlap_diagnostic.csv):
       - Partitions all 213 holding months by Overlap / Consensus State:
           * 0 Overlap (All legs distinct; max single-stock weight = 25% in 3-leg, 50% in 2-leg)
           * 2-Leg Overlap (max single-stock weight = 50% in 3-leg, 75% in 2-leg; broken down into
             Tech==SPY only, QQQ==Tech only, QQQ==SPY only, Double 2-Leg 50/50, and Combined 2-Leg)
           * 3-Leg Triple Consensus (QQQ, Tech, and SPY all select the same stock; 75% weight)
       - Also tests Pure Pre-Buffer Formation-Rank Consensus (at formation t, before any G1 hysteresis
         buffer: whether SPY #1 == Tech #1 and where it ranks in QQQ Sharpe-Mom).
       - Reports for every state:
           * Month count N & share of 213 months (%)
           * Portfolio next-1m Mean, Median, Compounded Annualized Return, Ann Vol, Excess Sharpe,
             Raw Sharpe, Win Rate (%), Hit > +5%, Hit < -5%, Worst Month, Best Month
           * Standalone next-1m return of the Overlapping Consensus Stock itself vs Non-Overlapping
             stocks held in the same month.
       - Also reports Subperiod Split (2009-2018 vs 2019-2026) and Ex-2022 / Ex-NVDA / Ex-SNDK checks
         on the diagnostic table (01b_consensus_subperiod_and_robustness.csv).

  2. Burst Mode 1 — Consensus / Overlap Conviction Sizing (02_mode1_consensus_conviction_sizing.csv):
       - Tests conditional exposure scaling (1.0x base, 1.0x/1.25x on 2-leg, 1.25x/1.50x on 3-leg,
         plus de-risking 0-overlap to 0.75x, and unlevered 1.0x weight concentration to 85%-100%).
       - Deducts realistic Point-in-Time borrowing cost (3M T-bill + 50bp/yr, and 3M T-bill) on any
         levered exposure (L - 1.0), plus 10bp/side turnover cost on all weight changes.
       - Benchmarks against Constant Leverage Controls with the EXACT SAME average exposure.

  3. Burst Mode 2 — SEP / Macro Regime Selective QQQ Shutoff & Winner Reallocation
     (03_mode2_sep_and_trend_qqq_routing.csv):
       - Tests FOMC SEP Canonical Regime (research/strategy_comparison/strategy_engine.py), V6
         (Hawkish + EPS), and strictly PIT QQQ < SMA200 (available 2009-2026).
       - Compares Conservative (SEP OFF: 0% QQQ + 25% Tech + 25% SPY + 50% Cash/SGOV) vs
         Burst Reallocation (SEP OFF: 0% QQQ + 50% Tech + 50% SPY, unconditional and conditioned
         on Tech/SPY momentum > threshold, or routing to SPY).
       - Audits full sample (2009-2026), Pre-2019 (2009-2018), 2022 alone, Ex-2022 (201 months
         removing 2022), and Post-2022 (2023-2026) to expose any 2022 hindsight bias.

  4. Burst Mode 3 — Trend + Low Crash Risk + Consensus Controlled Leverage
     (04_mode3_crash_protected_consensus_leverage.csv):
       - Barroso-Santa-Clara (2015) / Daniel-Moskowitz (2016) crash-protected conviction scaling:
         applies 1.25x (2-leg) / 1.50x (3-leg) ONLY when regime is ON (SEP==ON and/or QQQ>=SMA200)
         AND realized portfolio/market volatility is not elevated (not in a panic/rebound crash state).

  5. Burst Mode 4 — EAR (PIT Earnings Announcement Return) + Momentum Consensus
     (05_mode4_ear_momentum_consensus.csv & 05b_ear_consensus_diagnostic.csv):
       - Diagnostic table of Consensus WITH positive trailing 4Q EAR (ear_sum4 > 0 / ear_latest > 0)
         vs WITHOUT positive EAR.
       - Backtests EAR-confirmed conviction sizing (amplifying exposure only when multi-leg price
         consensus is confirmed by positive SEC 8-K earnings reaction).

  6. Cumulative Multiple-Testing Deflated Sharpe Ratio (DSR) & Master Registry Update
     (06_multiple_testing_dsr.csv).
"""
import json
import os
import sys
import warnings
from datetime import timedelta
import numpy as np
import pandas as pd
from scipy import stats as sst

warnings.filterwarnings('ignore')

ROOT = '/Users/happygolucky/Desktop/宏观观察器'
QQQ_DIR = os.path.join(ROOT, 'outputs', 'qqq_mom_top3_claude_audit_20261103')
TECH_DIR = os.path.join(ROOT, 'outputs', 'tech_top1_independent_audit_20261103')
SEL_DIR = os.path.join(ROOT, 'outputs', 'core3_stock_selection_audit_20261103')
SPY_DIR = os.path.join(ROOT, 'outputs', 'core3_qqq_spy_g1_audit_20261103')
SEP_SCRIPT_DIR = os.path.join(ROOT, 'research', 'strategy_comparison')
DATA_DIR = os.path.join(ROOT, 'research', 'sector_stock_momentum', 'data')
HERE = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, QQQ_DIR)
sys.path.insert(0, TECH_DIR)
sys.path.insert(0, SEL_DIR)
sys.path.insert(0, SPY_DIR)
sys.path.insert(0, SEP_SCRIPT_DIR)

import a2_engine as QE
import c2_engine as TE
from run_qqq_spy_g1_audit import (
    load_rf_and_calendar,
    rank_sleeve_candidates_at_t,
    simulate_single_sleeve,
    combine_sleeves,
    get_daily_stock_df,
)
from strategy_engine import parse_sep_pdfs, build_sep_signals

COST_BP = 0.0010          # 10 bp per side transaction cost
BORROW_SPREAD_ANN = 0.0050  # 50 bp/yr margin borrowing spread over 3M T-bill


# =============================================================================
# 1. Load Panels, Daily Prices, Benchmarks & Macro Regimes (SEP, V6, QQQ SMA200)
# =============================================================================
def load_all_inputs():
    rf_monthly, cal_days = load_rf_and_calendar()

    qqq_panel = pd.read_parquet(os.path.join(SEL_DIR, 'qqq_selection_panel.parquet'))
    tech_panel = pd.read_parquet(os.path.join(SEL_DIR, 'tech_selection_panel.parquet'))
    spy_panel = pd.read_parquet(os.path.join(SPY_DIR, 'spy_selection_panel.parquet'))

    spy_daily_c = pd.read_parquet(os.path.join(SPY_DIR, 'spy_daily_close.parquet'))
    spy_daily_o = pd.read_parquet(os.path.join(SPY_DIR, 'spy_daily_open.parquet'))

    # Load QQQ, SPY, XLK ETF daily series for strictly PIT regime & vol signals
    df_qqq = QE.series('tiingo_api', 'QQQ')
    if df_qqq is None:
        df_qqq = QE.series('yahoo', 'QQQ')
    df_spy = QE.series('yahoo', 'SPY')
    df_xlk = TE.load_source('yahoo', 'XLK')

    c_qqq = df_qqq['adjclose'].dropna().sort_index()
    c_spy = df_spy['adjclose'].dropna().sort_index()
    c_xlk = df_xlk['adjclose'].dropna().sort_index()

    return (rf_monthly, cal_days, qqq_panel, tech_panel, spy_panel,
            spy_daily_c, spy_daily_o, c_qqq, c_spy, c_xlk)


def build_monthly_regime_table(formations, c_qqq, c_spy, c_xlk, rf_monthly):
    """
    At each formation month-end date `t` (2008-12-31 .. 2026-08-31), compute strictly
    Point-in-Time macro & market regime indicators known on or before `t`:
      1. `sep_on`: Canonical FOMC SEP state at date `t` (from `research/strategy_comparison/strategy_engine.py`:
         EXIT when FOMC SEP median PCE > 2.0%, PCE > prev_PCE, and Rate > prev_Rate;
         ENTER when FOMC SEP median Rate <= prev_Rate). Meetings occurred on/before `t`.
         Note: FOMC Dot-Plot SEP began in Jan 2012; prior to 2012, `sep_on = True`.
      2. `sep_loose_on`: Looser SEP threshold (`PCE > 1.8%, Rate > prev_Rate`) which also exited in 2018-06..2018-09.
      3. `v6_on`: V6 (Kim-Wright Hawkish Path + LSEG Forward EPS state) as of `t`.
      4. `qqq_sma200_on`: `QQQ Close[t] >= QQQ 200-day SMA[t]` (strictly PIT back to 2008-12).
      5. `spy_sma200_on`: `SPY Close[t] >= SPY 200-day SMA[t]`.
      6. `xlk_sma200_on`: `XLK Close[t] >= XLK 200-day SMA[t]`.
      7. `qqq_vol21_t`, `qqq_vol63_t`: QQQ 21-day and 63-day realized annualized vol up to `t`.
      8. `qqq_dd252_t`: QQQ drawdown from trailing 252-day peak at `t`.
      9. `qqq_ret1m_t`, `qqq_ret3m_t`: QQQ trailing 1m and 3m return at `t`.
      10. `dm_panic_rebound_t`: Daniel-Moskowitz (2016) panic/rebound indicator:
          trailing 12m market return < 0 AND (trailing 21d vol > 30% OR trailing 1m return > +5% bear-market bounce).
    """
    sep_dir = os.path.join(ROOT, 'data', 'fomc_sep')
    sep_raw = parse_sep_pdfs(sep_dir)

    def get_sep_state_series(pce_thresh=2.0, rate_thresh=0.0):
        events = []
        sep_in = True
        for i in range(1, len(sep_raw)):
            c, p = sep_raw[i], sep_raw[i - 1]
            ty = c['target_year']
            c_pce = c['pce_by_year'].get(ty)
            c_rate = c['rate_by_year'].get(ty)
            p_pce = p['pce_by_year'].get(ty)
            p_rate = p['rate_by_year'].get(ty)
            if c_pce is None:
                continue
            has_both = all(pd.notna(x) for x in [c_pce, c_rate, p_pce, p_rate])
            rate_up = (c_rate - p_rate) > rate_thresh if has_both else False
            pce_above = c_pce > pce_thresh
            pce_up = c_pce > p_pce if has_both else False
            is_exit = rate_up and pce_above and pce_up if has_both else False
            reenter = (c_rate <= p_rate) if has_both else False
            if sep_in and is_exit:
                sep_in = False
                events.append((pd.Timestamp(c['date']), False))
            elif not sep_in and reenter:
                sep_in = True
                events.append((pd.Timestamp(c['date']), True))
        return events

    sep_canon_events = get_sep_state_series(2.0, 0.0)
    sep_18_events = get_sep_state_series(1.8, 0.0)

    # V6 trade intervals from research/strategy_comparison/v6_final_trades.csv
    v6_trades_fn = os.path.join(SEP_SCRIPT_DIR, 'v6_final_trades.csv')
    v6_out_intervals = []
    if os.path.exists(v6_trades_fn):
        vdf = pd.read_csv(v6_trades_fn)
        vdf = vdf[vdf['strategy'] == 'V6 (Cond)']
        for _, r in vdf.iterrows():
            v6_out_intervals.append((pd.Timestamp(r['exit_date']), pd.Timestamp(r['entry_date'])))

    r_qqq = c_qqq.pct_change().dropna()
    rows = []
    for t in sorted(formations):
        t_ts = pd.Timestamp(t)
        ym = (t_ts + pd.offsets.MonthBegin(1)).strftime('%Y-%m')
        m_dt = t_ts + pd.offsets.MonthEnd(1)

        # SEP canonical state as of formation date t
        sep_on = True
        for ev_dt, st in sep_canon_events:
            if ev_dt <= t_ts:
                sep_on = st

        sep_18_on = True
        for ev_dt, st in sep_18_events:
            if ev_dt <= t_ts:
                sep_18_on = st

        v6_on = True
        for ex_d, en_d in v6_out_intervals:
            if ex_d <= t_ts < en_d:
                v6_on = False

        # Strictly PIT QQQ / SPY / XLK SMA200 & Vol at t
        cq_t = c_qqq.loc[:t_ts]
        cs_t = c_spy.loc[:t_ts]
        cx_t = c_xlk.loc[:t_ts]
        rq_t = r_qqq.loc[:t_ts]

        qqq_sma200_on = bool(cq_t.iloc[-1] >= cq_t.tail(200).mean()) if len(cq_t) >= 200 else True
        spy_sma200_on = bool(cs_t.iloc[-1] >= cs_t.tail(200).mean()) if len(cs_t) >= 200 else True
        xlk_sma200_on = bool(cx_t.iloc[-1] >= cx_t.tail(200).mean()) if len(cx_t) >= 200 else True

        qqq_vol21 = float(rq_t.tail(21).std(ddof=1) * np.sqrt(252.0)) if len(rq_t) >= 21 else 0.20
        qqq_vol63 = float(rq_t.tail(63).std(ddof=1) * np.sqrt(252.0)) if len(rq_t) >= 63 else 0.20

        qqq_dd252 = float(cq_t.iloc[-1] / cq_t.tail(252).max() - 1.0) if len(cq_t) >= 252 else 0.0
        qqq_ret12m = float(cq_t.iloc[-1] / cq_t.iloc[-252] - 1.0) if len(cq_t) >= 252 else 0.0
        qqq_ret1m = float(cq_t.iloc[-1] / cq_t.iloc[-21] - 1.0) if len(cq_t) >= 21 else 0.0

        # Daniel-Moskowitz panic/rebound state: bear market (12m ret < 0 or DD < -15%) AND high vol (>28%)
        dm_panic = bool((qqq_ret12m < 0.0 or qqq_dd252 < -0.15) and qqq_vol21 > 0.28)

        rf_m = float(rf_monthly.reindex([m_dt], method='ffill').iloc[0]) if len(rf_monthly) else 0.0

        rows.append({
            'ym': ym,
            't_date': t_ts,
            'month': m_dt,
            'sep_on': sep_on,
            'sep_18_on': sep_18_on,
            'v6_on': v6_on,
            'qqq_sma200_on': qqq_sma200_on,
            'spy_sma200_on': spy_sma200_on,
            'xlk_sma200_on': xlk_sma200_on,
            'qqq_vol21': qqq_vol21,
            'qqq_vol63': qqq_vol63,
            'qqq_dd252': qqq_dd252,
            'qqq_ret12m': qqq_ret12m,
            'qqq_ret1m': qqq_ret1m,
            'dm_panic': dm_panic,
            'rf_monthly': rf_m,
            'borrow_monthly': rf_m + BORROW_SPREAD_ANN / 12.0,
        })

    return pd.DataFrame(rows).set_index('ym')


# =============================================================================
# 2. Build Lookup Maps for Stock-Level Returns, Ranks, Momentum, Vol, and EAR
# =============================================================================
def build_panel_lookups(qqq_panel, tech_panel, spy_panel, c_spy, cal_days, spy_daily_c):
    """
    Builds fast `(ym, ticker)` lookups for:
      - `ret_map[(ym, ticker)]`: exact holding-month return `hold_ret`
      - `mom_map[(ym, ticker)]`: formation `mom_12_1`
      - `vol_map[(ym, ticker)]`: formation `vol_12_1`
      - `ear_latest_map[(ym, ticker)]`, `ear_sum4_map[(ym, ticker)]`: strictly PIT 8-K EAR
      - Formation rank maps:
          * `qqq_rk_map[(ym, ticker)]`: 1-based rank in QQQ by `sharpe_mom_12_1`
          * `tech_rk_map[(ym, ticker)]`: 1-based rank in Tech by `mom_12_1`
          * `spy_rk_map[(ym, ticker)]`: 1-based rank in SPY by `mom_12_1`
          * `qqq_top1[ym]`, `qqq_top2_set[ym]`, `qqq_top5_set[ym]`
          * `tech_top1[ym]`, `spy_top1[ym]`
    """
    ret_map = {}
    mom_map = {}
    vol_map = {}
    ear_latest_map = {}
    ear_sum4_map = {}
    rev_yoy_map = {}
    eps_yoy_map = {}

    qqq_rk_map = {}
    tech_rk_map = {}
    spy_rk_map = {}
    qqq_top1 = {}
    qqq_top2_set = {}
    qqq_top5_set = {}
    tech_top1 = {}
    spy_top1 = {}

    # 1. Populate from QQQ panel
    for t_val, g in qqq_panel.groupby('t', sort=True):
        ym = (pd.Timestamp(t_val) + pd.offsets.MonthBegin(1)).strftime('%Y-%m')
        g_valid = g[g['sharpe_mom_12_1'].notna() & g['hold_ret'].notna()].sort_values(
            ['sharpe_mom_12_1', 'ticker'], ascending=[False, True]
        ).reset_index(drop=True)
        tks = list(g_valid['ticker'].values)
        qqq_top1[ym] = tks[0] if tks else ''
        qqq_top2_set[ym] = set(tks[:2])
        qqq_top5_set[ym] = set(tks[:5])
        for idx, r in g_valid.iterrows():
            tk = r['ticker']
            qqq_rk_map[(ym, tk)] = idx + 1
            ret_map[(ym, tk)] = float(r['hold_ret'])
            mom_map[(ym, tk)] = float(r['mom_12_1'])
            vol_map[(ym, tk)] = float(r['vol_12_1'])
            if pd.notna(r.get('ear_latest')):
                ear_latest_map[(ym, tk)] = float(r['ear_latest'])
            if pd.notna(r.get('ear_sum4')):
                ear_sum4_map[(ym, tk)] = float(r['ear_sum4'])
            if pd.notna(r.get('rev_yoy_q')):
                rev_yoy_map[(ym, tk)] = float(r['rev_yoy_q'])
            if pd.notna(r.get('eps_yoy_sym_q')):
                eps_yoy_map[(ym, tk)] = float(r['eps_yoy_sym_q'])

    # 2. Populate from Tech panel
    for t_val, g in tech_panel.groupby('t', sort=True):
        ym = (pd.Timestamp(t_val) + pd.offsets.MonthBegin(1)).strftime('%Y-%m')
        g_valid = g[g['mom_12_1'].notna() & g['hold_ret'].notna()].sort_values(
            ['mom_12_1', 'ticker'], ascending=[False, True]
        ).reset_index(drop=True)
        tks = list(g_valid['ticker'].values)
        tech_top1[ym] = tks[0] if tks else ''
        for idx, r in g_valid.iterrows():
            tk = r['ticker']
            tech_rk_map[(ym, tk)] = idx + 1
            if (ym, tk) not in ret_map:
                ret_map[(ym, tk)] = float(r['hold_ret'])
            if (ym, tk) not in mom_map:
                mom_map[(ym, tk)] = float(r['mom_12_1'])
            if (ym, tk) not in vol_map:
                vol_map[(ym, tk)] = float(r['vol_12_1'])
            if (ym, tk) not in ear_latest_map and pd.notna(r.get('ear_latest')):
                ear_latest_map[(ym, tk)] = float(r['ear_latest'])
            if (ym, tk) not in ear_sum4_map and pd.notna(r.get('ear_sum4')):
                ear_sum4_map[(ym, tk)] = float(r['ear_sum4'])
            if (ym, tk) not in rev_yoy_map and pd.notna(r.get('rev_yoy_q')):
                rev_yoy_map[(ym, tk)] = float(r['rev_yoy_q'])
            if (ym, tk) not in eps_yoy_map and pd.notna(r.get('eps_yoy_sym_q')):
                eps_yoy_map[(ym, tk)] = float(r['eps_yoy_sym_q'])

    # 3. Populate from SPY panel (and compute PIT EAR for any non-IT SPY top picks not already in QQQ/Tech)
    from build_selection_panels import load_cik_maps_and_validity, load_earnings_reaction_dates, compute_ear_at_t
    t2c, is_cik_valid = load_cik_maps_and_validity()
    ed_map = load_earnings_reaction_dates()
    cal_all = QE.calendar()

    for t_val, g in spy_panel.groupby('t', sort=True):
        t_ts = pd.Timestamp(t_val)
        ym = (t_ts + pd.offsets.MonthBegin(1)).strftime('%Y-%m')
        g_valid = g[g['mom_12_1'].notna() & g['hold_ret'].notna()].sort_values(
            ['mom_12_1', 'ticker'], ascending=[False, True]
        ).reset_index(drop=True)
        tks = list(g_valid['ticker'].values)
        spy_top1[ym] = tks[0] if tks else ''
        for idx, r in g_valid.iterrows():
            tk = r['ticker']
            spy_rk_map[(ym, tk)] = idx + 1
            if (ym, tk) not in ret_map:
                ret_map[(ym, tk)] = float(r['hold_ret'])
            if (ym, tk) not in mom_map:
                mom_map[(ym, tk)] = float(r['mom_12_1'])
            if (ym, tk) not in vol_map:
                vol_map[(ym, tk)] = float(r['vol_12_1'])
            # Compute PIT EAR for top-10 SPY candidates if not already in ear_latest_map
            if idx < 10 and (ym, tk) not in ear_latest_map:
                cik = t2c.get(tk) if is_cik_valid(tk, t_ts) else None
                if cik is not None and tk in spy_daily_c.columns:
                    df_s = pd.DataFrame({'adjclose': spy_daily_c[tk].dropna()})
                    el, es4 = compute_ear_at_t(df_s, cik, t_ts, ed_map, c_spy, cal_all)
                    if pd.notna(el):
                        ear_latest_map[(ym, tk)] = float(el)
                    if pd.notna(es4):
                        ear_sum4_map[(ym, tk)] = float(es4)

    return {
        'ret_map': ret_map,
        'mom_map': mom_map,
        'vol_map': vol_map,
        'ear_latest_map': ear_latest_map,
        'ear_sum4_map': ear_sum4_map,
        'rev_yoy_map': rev_yoy_map,
        'eps_yoy_map': eps_yoy_map,
        'qqq_rk_map': qqq_rk_map,
        'tech_rk_map': tech_rk_map,
        'spy_rk_map': spy_rk_map,
        'qqq_top1': qqq_top1,
        'qqq_top2_set': qqq_top2_set,
        'qqq_top5_set': qqq_top5_set,
        'tech_top1': tech_top1,
        'spy_top1': spy_top1,
    }


# =============================================================================
# 3. Priority #1: Consensus / Overlap Diagnostic Table Builder
# =============================================================================
def classify_3leg_month(row, lookups, ym):
    """
    Given a 3-leg monthly row (with `sleeve_picks = {'qqq': 'A|B', 'xlk': 'C', 'spy': 'D'}`),
    classifies the month into:
      - `state_main`:
          * `'0_No_Overlap'`      (4 distinct stocks, max weight = 25%)
          * `'2_Two_Leg_Overlap'` (2 legs agree on a stock, max weight = 50%)
          * `'3_Triple_Consensus'`(all 3 legs agree on a stock, max weight = 75%)
      - `state_sub`:
          * `'0_No_Overlap'`
          * `'2a_Tech_eq_SPY_only'`
          * `'2b_QQQ_eq_Tech_only'`
          * `'2c_QQQ_eq_SPY_only'`
          * `'2d_Double_2Leg_50_50'`
          * `'3_Triple_QQQ_Tech_SPY'`
    And computes standalone return of the overlapping stock(s) vs non-overlapping stock(s).
    """
    sp = row['sleeve_picks']
    q_picks = [x for x in sp['qqq'].split('|') if x]
    t_pick = sp['xlk']
    s_pick = sp['spy']
    ret_map = lookups['ret_map']

    q_set = set(q_picks)
    t_in_q = t_pick in q_set
    s_in_q = s_pick in q_set
    t_eq_s = (t_pick == s_pick)

    if t_eq_s and t_in_q:
        state_main = '3_Triple_Consensus'
        state_sub = '3_Triple_QQQ_Tech_SPY'
        ov_tks = [t_pick]
        non_ov_tks = [x for x in q_picks if x != t_pick]
    elif t_eq_s and not t_in_q:
        state_main = '2_Two_Leg_Overlap'
        state_sub = '2a_Tech_eq_SPY_only'
        ov_tks = [t_pick]
        non_ov_tks = list(q_picks)
    elif t_in_q and s_in_q and not t_eq_s:
        state_main = '2_Two_Leg_Overlap'
        state_sub = '2d_Double_2Leg_50_50'
        ov_tks = [t_pick, s_pick]
        non_ov_tks = []
    elif t_in_q and not s_in_q:
        state_main = '2_Two_Leg_Overlap'
        state_sub = '2b_QQQ_eq_Tech_only'
        ov_tks = [t_pick]
        non_ov_tks = [x for x in q_picks if x != t_pick] + [s_pick]
    elif s_in_q and not t_in_q:
        state_main = '2_Two_Leg_Overlap'
        state_sub = '2c_QQQ_eq_SPY_only'
        ov_tks = [s_pick]
        non_ov_tks = [x for x in q_picks if x != s_pick] + [t_pick]
    else:
        state_main = '0_No_Overlap'
        state_sub = '0_No_Overlap'
        ov_tks = []
        non_ov_tks = list(q_picks) + [t_pick, s_pick]

    ov_ret = float(np.mean([ret_map.get((ym, tk), np.nan) for tk in ov_tks])) if ov_tks else np.nan
    non_ov_ret = float(np.mean([ret_map.get((ym, tk), np.nan) for tk in non_ov_tks])) if non_ov_tks else np.nan
    all_distinct_ret = float(np.mean([ret_map.get((ym, tk), np.nan) for tk in set(q_picks + [t_pick, s_pick])]))

    return state_main, state_sub, ov_tks, non_ov_tks, ov_ret, non_ov_ret, all_distinct_ret


def summarize_bucket_rows(strategy_name, bucket_label, sub_df, rf_monthly):
    """
    Computes exact next-1m return diagnostics for a subset of holding months `sub_df`.
    """
    n = len(sub_df)
    if n == 0:
        return None
    r = sub_df['net'].astype(float).values
    idx_dt = pd.to_datetime(sub_df.index + '-01') + pd.offsets.MonthEnd(1)
    rf_al = rf_monthly.reindex(idx_dt).ffill().fillna(0.0).values
    ex = r - rf_al

    mean_m = float(np.mean(r))
    med_m = float(np.median(r))
    cagr_ann = float((np.prod(1.0 + r)) ** (12.0 / n) - 1.0) if np.all(1.0 + r > 0) else np.nan
    vol_m = float(np.std(r, ddof=1)) if n > 1 else np.nan
    vol_ann = float(vol_m * np.sqrt(12.0)) if n > 1 else np.nan
    sharpe_ex = float(np.mean(ex) / vol_m * np.sqrt(12.0)) if (n > 1 and vol_m > 0) else np.nan
    sharpe_raw = float(mean_m / vol_m * np.sqrt(12.0)) if (n > 1 and vol_m > 0) else np.nan
    neg = r[r < 0]
    sortino = float(np.mean(ex) * 12.0 / (np.std(neg, ddof=1) * np.sqrt(12.0))) if len(neg) > 1 else np.nan

    win_rate = float(np.mean(r > 0))
    hit_gt_5 = float(np.mean(r > 0.05))
    hit_gt_10 = float(np.mean(r > 0.10))
    hit_lt_n5 = float(np.mean(r < -0.05))
    worst_m = float(np.min(r))
    best_m = float(np.max(r))
    worst_ym = str(sub_df.index[int(np.argmin(r))])
    best_ym = str(sub_df.index[int(np.argmax(r))])

    # Standalone consensus stock vs non-consensus stock returns
    ov_r = sub_df['ov_stock_ret'].dropna().values if 'ov_stock_ret' in sub_df.columns else np.array([])
    non_ov_r = sub_df['non_ov_stock_ret'].dropna().values if 'non_ov_stock_ret' in sub_df.columns else np.array([])

    ov_mean = float(np.mean(ov_r)) if len(ov_r) else np.nan
    ov_cagr = float((np.prod(1.0 + ov_r)) ** (12.0 / len(ov_r)) - 1.0) if len(ov_r) else np.nan
    ov_win = float(np.mean(ov_r > 0)) if len(ov_r) else np.nan

    non_ov_mean = float(np.mean(non_ov_r)) if len(non_ov_r) else np.nan
    non_ov_cagr = float((np.prod(1.0 + non_ov_r)) ** (12.0 / len(non_ov_r)) - 1.0) if len(non_ov_r) else np.nan

    return {
        'Strategy': strategy_name,
        'Consensus_State': bucket_label,
        'Months_N': n,
        'Share_Pct': n / 213.0,
        'Mean_Mo_Ret': mean_m,
        'Median_Mo_Ret': med_m,
        'Ann_Compounded_Ret': cagr_ann,
        'Ann_Vol': vol_ann,
        'Ann_Sharpe_Excess': sharpe_ex,
        'Ann_Sharpe_Raw': sharpe_raw,
        'Ann_Sortino': sortino,
        'Win_Rate': win_rate,
        'Pct_Mo_GT_5pct': hit_gt_5,
        'Pct_Mo_GT_10pct': hit_gt_10,
        'Pct_Mo_LT_Neg5pct': hit_lt_n5,
        'Worst_Mo_Ret': worst_m,
        'Worst_Mo_YM': worst_ym,
        'Best_Mo_Ret': best_m,
        'Best_Mo_YM': best_ym,
        'Consensus_Stock_Mean_Mo': ov_mean,
        'Consensus_Stock_Ann_CAGR': ov_cagr,
        'Consensus_Stock_Win_Rate': ov_win,
        'NonConsensus_Stock_Mean_Mo': non_ov_mean,
        'NonConsensus_Stock_Ann_CAGR': non_ov_cagr,
    }


def annotate_3leg_ledger(L_3s, lookups):
    L = L_3s.copy()
    st_main, st_sub, ov_tks_l, ov_r_l, non_ov_r_l, eq_r_l = [], [], [], [], [], []
    for ym, row in L.iterrows():
        sm, ss, ov_tks, _, ov_r, non_ov_r, eq_r = classify_3leg_month(row, lookups, ym)
        st_main.append(sm)
        st_sub.append(ss)
        ov_tks_l.append('|'.join(ov_tks))
        ov_r_l.append(ov_r)
        non_ov_r_l.append(non_ov_r)
        eq_r_l.append(eq_r)
    L['state_main'] = st_main
    L['state_sub'] = st_sub
    L['ov_tickers'] = ov_tks_l
    L['ov_stock_ret'] = ov_r_l
    L['non_ov_stock_ret'] = non_ov_r_l
    L['ew_distinct_ret'] = eq_r_l
    return L


def annotate_2leg_ledger(L_2s, lookups, second_tag='spy'):
    L = L_2s.copy()
    ret_map = lookups['ret_map']
    st_main, ov_tks_l, ov_r_l, non_ov_r_l = [], [], [], []
    for ym, row in L.iterrows():
        sp = row['sleeve_picks']
        q_picks = [x for x in sp['qqq'].split('|') if x]
        s_pick = sp[second_tag]
        if s_pick in set(q_picks):
            st_main.append('2_Two_Leg_Overlap_75pct')
            ov_tks_l.append(s_pick)
            ov_r_l.append(ret_map.get((ym, s_pick), np.nan))
            other = [x for x in q_picks if x != s_pick]
            non_ov_r_l.append(float(np.mean([ret_map.get((ym, x), np.nan) for x in other])) if other else np.nan)
        else:
            st_main.append('0_No_Overlap_50_25_25')
            ov_tks_l.append('')
            ov_r_l.append(np.nan)
            non_ov_r_l.append(float(np.mean([ret_map.get((ym, x), np.nan) for x in q_picks + [s_pick]])))
    L['state_main'] = st_main
    L['ov_tickers'] = ov_tks_l
    L['ov_stock_ret'] = ov_r_l
    L['non_ov_stock_ret'] = non_ov_r_l
    return L


# =============================================================================
# 4. General Portfolio Simulator for Burst Modes 1, 2, 3, and 4
# =============================================================================
def simulate_dynamic_portfolio(base_sleeves, regime_df, lookups, cal_days, spy_daily_c, spy_daily_o,
                               weight_rule_fn):
    """
    General-purpose single-account monthly simulator that supports:
      - Dynamic sleeve weights `(w_qqq, w_xlk, w_spy)`
      - Within-portfolio conviction concentration (overriding individual stock weights)
      - Total gross equity exposure `L_exp` (where `L_exp > 1.0` borrows `(L_exp - 1.0)` at
        `borrow_rate`, and `L_exp < 1.0` holds `(1.0 - L_exp)` in `cash_rate` = 0% or SGOV `rf_monthly`)
      - Single-account exact net-of-cost turnover (`10bp/side` on actual stock weight changes
        across the entire portfolio from end-of-month `m-1` drifted weights to new target weights `m`)
      - Exact Daily Mark-to-Market MaxDD (`Daily_MaxDD_5651ec2` & `Daily_MaxDD_O2C`), properly
        accounting for any leverage `L_exp` or cash weight!
    """
    L_qqq, L_xlk, L_spy = base_sleeves['qqq'], base_sleeves['xlk'], base_sleeves['spy']
    ret_map = lookups['ret_map']
    common_ym = L_qqq.index

    prev_drifted_w = {}
    rows = []

    for ym in common_ym:
        t_date = pd.Timestamp(L_qqq.at[ym, 't_date'])
        r_qqq_row = L_qqq.loc[ym]
        r_xlk_row = L_xlk.loc[ym]
        r_spy_row = L_spy.loc[ym]
        reg_row = regime_df.loc[ym]

        # Ask rule function for target stock weights dict, cash return rate, borrowing rate, and state label
        # weight_rule_fn returns: (stock_weights_dict, cash_weight, cash_ret, borrow_weight, borrow_cost_rate, state_tag)
        w_stocks, w_cash, r_cash, w_borrow, r_borrow, state_tag = weight_rule_fn(
            ym, r_qqq_row, r_xlk_row, r_spy_row, reg_row, lookups
        )

        # Build metadata map for daily drawdown lookup
        meta_comb = {}
        for utag, r_s in [('qqq', r_qqq_row), ('xlk', r_xlk_row), ('spy', r_spy_row)]:
            for tk, (st, sym) in r_s['store_map'].items():
                if tk not in meta_comb:
                    meta_comb[tk] = (utag, st, sym)

        # Gross return before transaction cost
        gross_stocks = sum(w_tk * ret_map[(ym, tk)] for tk, w_tk in w_stocks.items())
        gross_total = gross_stocks + w_cash * r_cash - w_borrow * r_borrow

        # Exact single-account stock turnover
        if not prev_drifted_w:
            to = sum(abs(w_tk) for w_tk in w_stocks.values())
        else:
            all_tks = set(w_stocks.keys()) | set(prev_drifted_w.keys())
            to = float(sum(abs(w_stocks.get(tk, 0.0) - prev_drifted_w.get(tk, 0.0)) for tk in all_tks))

        # Transaction cost deduction
        net_total = (1.0 + gross_total) * ((1.0 - COST_BP) ** to) - 1.0 if to > 0 else gross_total

        # End-of-month drifted stock weights relative to end-of-month portfolio equity
        end_eq = 1.0 + gross_total
        if end_eq > 0:
            prev_drifted_w = {
                tk: w_tk * (1.0 + ret_map[(ym, tk)]) / end_eq
                for tk, w_tk in w_stocks.items()
            }
        else:
            prev_drifted_w = {}

        total_long_exp = float(sum(w_stocks.values()))

        rows.append({
            'ym': ym,
            't_date': t_date,
            'gross': gross_total,
            'net': net_total,
            'turnover': to,
            'long_exp': total_long_exp,
            'w_cash': w_cash,
            'w_borrow': w_borrow,
            'n_distinct': len(w_stocks),
            'max_single_w': max(w_stocks.values()) if w_stocks else 0.0,
            'state_tag': state_tag,
            'holdings_dict': dict(w_stocks),
            'meta_map': meta_comb,
            'net_financing_drag': w_borrow * r_borrow - w_cash * r_cash,
        })

    L_port = pd.DataFrame(rows).set_index('ym')
    dd_c56, dd_o2c = compute_dynamic_daily_drawdowns(L_port, cal_days, spy_daily_c, spy_daily_o)
    return L_port, dd_c56, dd_o2c


def compute_dynamic_daily_drawdowns(L_port, cal_days, spy_daily_c, spy_daily_o):
    """
    Computes exact Daily Mark-to-Market Drawdowns (`Daily_MaxDD_5651ec2` & `Daily_MaxDD_O2C`)
    for portfolios with dynamic exposure `long_exp` (including `long_exp > 1.0` levered and
    `long_exp < 1.0` partial cash).
    On day `d` within holding month `m`:
      `port_rel_d = 1.0 + sum_i w_i * (P_{i,d} / P_{i,entry} - 1.0) - daily_financing_drag`
    Notice that when `sum_i w_i == 1.0` and `financing == 0`, this reduces identically to
    `sum_i w_i * (P_{i,d} / P_{i,entry})`! And when `sum_i w_i == 1.5`, a `-10%` stock move
    produces a `-15%` portfolio equity move!
    """
    W = 1.0
    pts_c56 = {}
    pts_o2c = {}

    for ym, row in L_port.iterrows():
        t_form = pd.Timestamp(row['t_date'])
        m_dt = t_form + pd.offsets.MonthEnd(1)
        e_d = QE.first_td_after(t_form, 1)
        x_d = QE.first_td_after(m_dt, 1)
        m_days = cal_days[(cal_days >= e_d) & (cal_days < x_d)]
        if not len(m_days):
            continue

        h_dict = row['holdings_dict']
        meta_map = row['meta_map']
        fin_drag_m = float(row.get('net_financing_drag', 0.0))

        s_map = {}
        p_e_map = {}
        for tk in h_dict:
            u_tk, st_tk, sym_tk = meta_map.get(tk, ('spy', 'yahoo', tk))
            df_s = get_daily_stock_df(u_tk, tk, t_form, st_tk, sym_tk, spy_daily_c, spy_daily_o)
            s_map[tk] = df_s
            sub_e = df_s.loc[:e_d, 'adjopen_clean'].dropna()
            p_e_map[tk] = float(sub_e.iloc[-1]) if len(sub_e) else 1.0

        tx_cost = float((1.0 + row['gross']) - (1.0 + row['net']))
        W_after_entry = W * (1.0 - tx_cost / max(1.0 + row['gross'], 0.5))

        v_rel_0 = {}
        n_m_days = len(m_days)
        for d_i, d in enumerate(m_days):
            frac_m = (d_i + 1) / max(n_m_days, 1)
            pnl_o2c = -fin_drag_m * frac_m
            pnl_c56 = -fin_drag_m * frac_m
            for tk, wv in h_dict.items():
                sub_c = s_map[tk].loc[:d, 'adjclose'].dropna()
                c_d = float(sub_c.iloc[-1]) if len(sub_c) else p_e_map[tk]
                rel = c_d / p_e_map[tk] if p_e_map[tk] > 0 else 1.0
                if d_i == 0:
                    v_rel_0[tk] = rel if rel > 0 else 1.0
                pnl_o2c += wv * (rel - 1.0)
                pnl_c56 += wv * ((rel / v_rel_0[tk]) - 1.0)

            pts_o2c[d] = W_after_entry * max(0.01, 1.0 + pnl_o2c)
            pts_c56[d] = W * max(0.01, 1.0 + pnl_c56)

        W = W * (1.0 + float(row['net']))
        pts_c56[x_d] = W
        pts_o2c[x_d] = W

    s_c56 = pd.Series(pts_c56).sort_index()
    s_c56 = s_c56[~s_c56.index.duplicated(keep='last')]
    s_o2c = pd.Series(pts_o2c).sort_index()
    s_o2c = s_o2c[~s_o2c.index.duplicated(keep='last')]

    dd_c56 = float((s_c56 / s_c56.cummax() - 1.0).min()) if len(s_c56) else np.nan
    dd_o2c = float((s_o2c / s_o2c.cummax() - 1.0).min()) if len(s_o2c) else np.nan
    return dd_c56, dd_o2c


def summarize_burst_variant(name, family, L_port, rf_monthly, dd_c56, dd_o2c, ref_ctrl_r):
    r_m = L_port['net'].dropna()
    n = len(r_m)
    idx_dt = pd.to_datetime(r_m.index + '-01') + pd.offsets.MonthEnd(1)
    r_s = pd.Series(r_m.values, index=idx_dt)

    cagr = float((np.prod(1.0 + r_s.values)) ** (12.0 / n) - 1.0)
    vol = float(r_s.std(ddof=1) * np.sqrt(12.0))
    rf_al = rf_monthly.reindex(r_s.index).ffill().fillna(0.0)
    ex = r_s - rf_al
    sharpe = float(ex.mean() / r_s.std(ddof=1) * np.sqrt(12.0)) if r_s.std(ddof=1) > 0 else np.nan
    neg = r_s[r_s < 0]
    sortino = float(ex.mean() * 12.0 / (neg.std(ddof=1) * np.sqrt(12.0))) if len(neg) > 1 else np.nan

    w = np.concatenate([[1.0], np.cumprod(1.0 + r_s.values)])
    mdd = float((w / np.maximum.accumulate(w) - 1.0).min())
    calmar = cagr / abs(mdd) if mdd < 0 else np.nan
    calmar_daily = cagr / abs(dd_c56) if (pd.notna(dd_c56) and dd_c56 < 0) else np.nan

    def sub_cagr(a, b):
        sub = r_s.loc[a:b]
        return float((np.prod(1.0 + sub.values)) ** (12.0 / len(sub)) - 1.0) if len(sub) else np.nan

    ret_2022 = float(np.prod(1.0 + r_s.loc['2022-01-01':'2022-12-31'].values) - 1.0)
    # Ex-2022 CAGR (201 months excluding the 12 months of 2022)
    r_ex2022 = r_s[(r_s.index < '2022-01-01') | (r_s.index > '2022-12-31')]
    cagr_ex2022 = float((np.prod(1.0 + r_ex2022.values)) ** (12.0 / len(r_ex2022)) - 1.0)

    # Positive calendar years out of 18
    yr_rets = r_s.groupby(r_s.index.year).apply(lambda x: np.prod(1.0 + x.values) - 1.0)
    pos_years = int((yr_rets > 0).sum())
    worst_yr = float(yr_rets.min())

    # Newey-West 6-lag t-stat vs unlevered control
    nw_t = np.nan
    if ref_ctrl_r is not None:
        diff = (r_m - ref_ctrl_r.reindex(r_m.index)).dropna().values
        if len(diff) >= 24 and np.std(diff, ddof=1) > 1e-9:
            e = diff - diff.mean()
            L_len = len(diff)
            v = (e @ e) / L_len
            for lag in range(1, 7):
                v += 2.0 * (1.0 - lag / 7.0) * (e[lag:] @ e[:-lag]) / L_len
            nw_t = float(diff.mean() / np.sqrt(v / L_len)) if v > 0 else 0.0

    avg_exp = float(L_port['long_exp'].mean())
    max_exp = float(L_port['long_exp'].max())
    pct_levered = float((L_port['long_exp'] > 1.001).mean())
    pct_derisked = float((L_port['long_exp'] < 0.999).mean())

    return {
        'Variant': name,
        'Family': family,
        'CAGR_09_26': cagr,
        'Sharpe': sharpe,
        'Sortino': sortino,
        'Ann_Vol': vol,
        'Monthly_MaxDD': mdd,
        'Calmar_Monthly': calmar,
        'Daily_MaxDD_5651ec2': dd_c56,
        'Daily_MaxDD_O2C': dd_o2c,
        'Calmar_Daily': calmar_daily,
        'CAGR_2009_2018': sub_cagr('2009-01-31', '2018-12-31'),
        'CAGR_2019_2026': sub_cagr('2019-01-31', '2026-09-30'),
        'CAGR_Ex2022': cagr_ex2022,
        'Ret_2022': ret_2022,
        'CAGR_2023_2026': sub_cagr('2023-01-31', '2026-09-30'),
        'Pos_Years_18': pos_years,
        'Worst_Cal_Year': worst_yr,
        'Avg_Gross_Exp': avg_exp,
        'Max_Gross_Exp': max_exp,
        'Pct_Mo_Levered': pct_levered,
        'Pct_Mo_DeRisked': pct_derisked,
        'Avg_Monthly_TO': float(L_port['turnover'].mean()),
        'NW_t_vs_Ctrl': nw_t,
    }


# =============================================================================
# 5. Main Execution Pipeline
# =============================================================================
def main():
    print('=' * 105)
    print('RUNNING CLEAN-ROOM AUDIT: CONSENSUS STATES & 4 BURST MODES (2009-01 .. 2026-09, 213 MONTHS)')
    print('=' * 105)

    (rf_monthly, cal_days, qqq_panel, tech_panel, spy_panel,
     spy_daily_c, spy_daily_o, c_qqq, c_spy, c_xlk) = load_all_inputs()

    formations = sorted(qqq_panel['t'].unique())
    regime_df = build_monthly_regime_table(formations, c_qqq, c_spy, c_xlk, rf_monthly)
    lookups = build_panel_lookups(qqq_panel, tech_panel, spy_panel, c_spy, cal_days, spy_daily_c)

    # -------------------------------------------------------------------------
    # STEP 0: Simulate Base Constituent Sleeves
    # -------------------------------------------------------------------------
    spec_sharpe = {'type': 'score', 'score_col': 'sharpe_mom_12_1'}
    spec_raw = {'type': 'score', 'score_col': 'mom_12_1'}

    # QQQ Sleeves
    L_qqq_c3 = simulate_single_sleeve(qqq_panel, spec_sharpe, k=2, k_keep=2)
    L_qqq_g1_5 = simulate_single_sleeve(qqq_panel, spec_sharpe, k=2, k_keep=5)
    L_qqq_g1_3 = simulate_single_sleeve(qqq_panel, spec_sharpe, k=2, k_keep=3)

    # Tech (XLK) Sleeves
    L_xlk_c3 = simulate_single_sleeve(tech_panel, spec_raw, k=1, k_keep=1)
    L_xlk_g1_3 = simulate_single_sleeve(tech_panel, spec_raw, k=1, k_keep=3)

    # SPY Sleeves
    L_spy_c3 = simulate_single_sleeve(spy_panel, spec_raw, k=1, k_keep=1)
    L_spy_g1_3 = simulate_single_sleeve(spy_panel, spec_raw, k=1, k_keep=3)

    # Composite Base Ledgers
    # 1. 3S_G1_1k: 50% QQQ[Hold<=5] + 25% Tech[Hard 1] + 25% SPY[Hold<=3] (49.96% CAGR)
    L_3s_g1_1k = combine_sleeves([(L_qqq_g1_5, 0.50), (L_xlk_c3, 0.25), (L_spy_g1_3, 0.25)], ['qqq', 'xlk', 'spy'])
    # 2. 3S_G1_1a: 50% QQQ[Hold<=5] + 25% Tech[Hard 1] + 25% SPY[Hard 1] (48.20% CAGR)
    L_3s_g1_1a = combine_sleeves([(L_qqq_g1_5, 0.50), (L_xlk_c3, 0.25), (L_spy_c3, 0.25)], ['qqq', 'xlk', 'spy'])
    # 3. 3S_G1_sym3: 50% QQQ[Hold<=3] + 25% Tech[Hold<=3] + 25% SPY[Hold<=3] (49.35% CAGR)
    L_3s_g1_sym3 = combine_sleeves([(L_qqq_g1_3, 0.50), (L_xlk_g1_3, 0.25), (L_spy_g1_3, 0.25)], ['qqq', 'xlk', 'spy'])
    # 4. 3S_Core3_1a: 50% QQQ[Hard 2] + 25% Tech[Hard 1] + 25% SPY[Hard 1] (42.73% CAGR, Unbuffered)
    L_3s_c3_1a = combine_sleeves([(L_qqq_c3, 0.50), (L_xlk_c3, 0.25), (L_spy_c3, 0.25)], ['qqq', 'xlk', 'spy'])
    # 5. 3S_G1_EW: 33.3% QQQ[Hold<=5] + 33.3% Tech[Hard 1] + 33.3% SPY[Hold<=3]
    L_3s_g1_ew = combine_sleeves([(L_qqq_g1_5, 1/3), (L_xlk_c3, 1/3), (L_spy_g1_3, 1/3)], ['qqq', 'xlk', 'spy'])

    # 2-Leg Base Ledgers
    # 6. G1_SPY_2e: 50% QQQ[Hold<=5] + 50% SPY[Hold<=3] (50.23% sleeve-additive / 49.97% single-acct)
    L_2s_g1_spy = combine_sleeves([(L_qqq_g1_5, 0.50), (L_spy_g1_3, 0.50)], ['qqq', 'spy'])
    # 7. G1_XLK_Ctrl: 50% QQQ[Hold<=5] + 50% Tech[Hard 1] (46.23% CAGR)
    L_2s_g1_xlk = combine_sleeves([(L_qqq_g1_5, 0.50), (L_xlk_c3, 0.50)], ['qqq', 'xlk'])
    # 8. Core3_XLK_Ctrl: 50% QQQ[Hard 2] + 50% Tech[Hard 1] (42.42% CAGR)
    L_2s_c3_xlk = combine_sleeves([(L_qqq_c3, 0.50), (L_xlk_c3, 0.50)], ['qqq', 'xlk'])

    # =========================================================================
    # STEP 1: PRIORITY #1 — THE CONSENSUS / OVERLAP DIAGNOSTIC TABLE
    # =========================================================================
    print('\n[Step 1/6] Building Priority #1 Consensus / Overlap Diagnostic Tables...')

    diag_rows = []
    sub_diag_rows = []

    three_leg_models = [
        ('3S_G1_1k (50% QQQ[<=5]+25% Tech[1]+25% SPY[<=3])', L_3s_g1_1k),
        ('3S_G1_1a (50% QQQ[<=5]+25% Tech[1]+25% SPY[1])', L_3s_g1_1a),
        ('3S_G1_sym3 (50% QQQ[<=3]+25% Tech[<=3]+25% SPY[<=3])', L_3s_g1_sym3),
        ('3S_Core3_1a (Unbuffered Hard Top-2/1/1)', L_3s_c3_1a),
        ('3S_G1_EW (33% QQQ[<=5]+33% Tech[1]+33% SPY[<=3])', L_3s_g1_ew),
    ]

    annotated_3s = {}
    for m_name, L_raw in three_leg_models:
        L_ann = annotate_3leg_ledger(L_raw, lookups)
        annotated_3s[m_name] = L_ann

        # All 213 months
        diag_rows.append(summarize_bucket_rows(m_name, 'ALL_213_Months', L_ann, rf_monthly))

        # Main 3 states: 0 Overlap, 2-Leg Overlap (Combined), 3-Leg Triple Consensus
        for st_m in ['0_No_Overlap', '2_Two_Leg_Overlap', '3_Triple_Consensus']:
            sub = L_ann[L_ann['state_main'] == st_m]
            r_b = summarize_bucket_rows(m_name, st_m, sub, rf_monthly)
            if r_b:
                diag_rows.append(r_b)

        # Combined >=2 Legs Overlap (2-Leg + 3-Leg)
        sub_ge2 = L_ann[L_ann['state_main'].isin(['2_Two_Leg_Overlap', '3_Triple_Consensus'])]
        r_ge2 = summarize_bucket_rows(m_name, 'GE2_Any_Consensus (2Leg+3Leg)', sub_ge2, rf_monthly)
        if r_ge2:
            diag_rows.append(r_ge2)

        # Detailed sub-states of 2-Leg Overlap
        for st_s in ['2a_Tech_eq_SPY_only', '2b_QQQ_eq_Tech_only', '2c_QQQ_eq_SPY_only', '2d_Double_2Leg_50_50']:
            sub_s = L_ann[L_ann['state_sub'] == st_s]
            if len(sub_s) > 0:
                diag_rows.append(summarize_bucket_rows(m_name, f'  Sub: {st_s}', sub_s, rf_monthly))

    # Also add Pure Pre-Buffer Formation-Rank Consensus (at formation t, independent of G1 hysteresis)
    # Using 3S_Core3_1a and 3S_G1_1k returns partitioned by pure formation-date rank overlap:
    #   - State R0: Tech_#1 != SPY_#1 and neither is in QQQ_Top2
    #   - State R2: Tech_#1 == SPY_#1 (not in QQQ_Top2) OR one of Tech_#1/SPY_#1 is in QQQ_Top2
    #   - State R3_Top5: Tech_#1 == SPY_#1 AND in QQQ_Top5 (ranks 1..5)
    #   - State R3_Top2: Tech_#1 == SPY_#1 AND in QQQ_Top2 (ranks 1..2)
    #   - State R3_Top1: Tech_#1 == SPY_#1 == QQQ_#1 (all three #1!)
    L_1k_ann = annotated_3s['3S_G1_1k (50% QQQ[<=5]+25% Tech[1]+25% SPY[<=3])'].copy()
    raw_rank_state = []
    for ym in L_1k_ann.index:
        t1 = lookups['tech_top1'][ym]
        s1 = lookups['spy_top1'][ym]
        q1 = lookups['qqq_top1'][ym]
        q2_set = lookups['qqq_top2_set'][ym]
        q5_set = lookups['qqq_top5_set'][ym]
        if t1 == s1 and t1 == q1:
            raw_rank_state.append('RawRank_3Leg_All_Rank1 (QQQ#1==Tech#1==SPY#1)')
        elif t1 == s1 and t1 in q2_set:
            raw_rank_state.append('RawRank_3Leg_QQQTop2 (Tech#1==SPY#1 in QQQ#1-2)')
        elif t1 == s1 and t1 in q5_set:
            raw_rank_state.append('RawRank_3Leg_QQQTop5 (Tech#1==SPY#1 in QQQ#3-5)')
        elif t1 == s1 or (t1 in q2_set) or (s1 in q2_set):
            raw_rank_state.append('RawRank_2Leg_Overlap')
        else:
            raw_rank_state.append('RawRank_0_No_Overlap')
    L_1k_ann['raw_rank_state'] = raw_rank_state

    for r_st in [
        'RawRank_0_No_Overlap',
        'RawRank_2Leg_Overlap',
        'RawRank_3Leg_QQQTop5 (Tech#1==SPY#1 in QQQ#3-5)',
        'RawRank_3Leg_QQQTop2 (Tech#1==SPY#1 in QQQ#1-2)',
        'RawRank_3Leg_All_Rank1 (QQQ#1==Tech#1==SPY#1)',
    ]:
        sub = L_1k_ann[L_1k_ann['raw_rank_state'] == r_st]
        if len(sub) > 0:
            diag_rows.append(summarize_bucket_rows('Pure_Formation_Rank_Signal (on 3S_G1_1k)', r_st, sub, rf_monthly))

    # Add 2-Leg Models (G1_SPY_2e, G1_XLK_Ctrl, Core3_XLK_Ctrl)
    two_leg_models = [
        ('2L_G1_SPY_2e (50% QQQ[<=5]+50% SPY[<=3])', L_2s_g1_spy, 'spy'),
        ('2L_G1_XLK_Ctrl (50% QQQ[<=5]+50% Tech[1])', L_2s_g1_xlk, 'xlk'),
        ('2L_Core3_XLK_Ctrl (50% QQQ[2]+50% Tech[1])', L_2s_c3_xlk, 'xlk'),
    ]
    annotated_2s = {}
    for m_name, L_raw, stag in two_leg_models:
        L_ann = annotate_2leg_ledger(L_raw, lookups, second_tag=stag)
        annotated_2s[m_name] = L_ann
        diag_rows.append(summarize_bucket_rows(m_name, 'ALL_213_Months', L_ann, rf_monthly))
        for st_m in ['0_No_Overlap_50_25_25', '2_Two_Leg_Overlap_75pct']:
            sub = L_ann[L_ann['state_main'] == st_m]
            if len(sub) > 0:
                diag_rows.append(summarize_bucket_rows(m_name, st_m, sub, rf_monthly))

    df_diag = pd.DataFrame([x for x in diag_rows if x is not None])
    df_diag.to_csv(os.path.join(HERE, '01_consensus_overlap_diagnostic.csv'), index=False)

    # Build Subperiod & Winner-Removal Robustness Check on the Diagnostic Table (for 3S_G1_1k and 3S_Core3_1a)
    for m_label, L_ann in [
        ('3S_G1_1k', annotated_3s['3S_G1_1k (50% QQQ[<=5]+25% Tech[1]+25% SPY[<=3])']),
        ('3S_Core3_1a', annotated_3s['3S_Core3_1a (Unbuffered Hard Top-2/1/1)']),
    ]:
        slices = [
            ('Full_2009_2026', L_ann),
            ('FirstHalf_2009_2018 (120m)', L_ann.loc['2009-01':'2018-12']),
            ('SecondHalf_2019_2026 (93m)', L_ann.loc['2019-01':'2026-09']),
            ('Ex_2022 (201m)', L_ann[(L_ann.index < '2022-01') | (L_ann.index > '2022-12')]),
            ('Ex_NVDA_Months', L_ann[~L_ann['ov_tickers'].str.contains('NVDA', na=False)]),
            ('Ex_SNDK_Months', L_ann[~L_ann['ov_tickers'].str.contains('SNDK', na=False)]),
        ]
        for sl_name, sl_df in slices:
            for st_m in ['0_No_Overlap', '2_Two_Leg_Overlap', '3_Triple_Consensus']:
                sub = sl_df[sl_df['state_main'] == st_m]
                if len(sub) > 0:
                    r_b = summarize_bucket_rows(f'{m_label} [{sl_name}]', st_m, sub, rf_monthly)
                    if r_b:
                        sub_diag_rows.append(r_b)

    df_sub_diag = pd.DataFrame(sub_diag_rows)
    df_sub_diag.to_csv(os.path.join(HERE, '01b_consensus_subperiod_and_robustness.csv'), index=False)

    # Also save month-by-month consensus log for 3S_G1_1k
    L_1k_log = annotated_3s['3S_G1_1k (50% QQQ[<=5]+25% Tech[1]+25% SPY[<=3])'].copy()
    L_1k_log['qqq_picks'] = [x['qqq'] for x in L_1k_log['sleeve_picks']]
    L_1k_log['xlk_pick'] = [x['xlk'] for x in L_1k_log['sleeve_picks']]
    L_1k_log['spy_pick'] = [x['spy'] for x in L_1k_log['sleeve_picks']]
    L_1k_log['sep_on'] = regime_df['sep_on']
    L_1k_log['qqq_sma200_on'] = regime_df['qqq_sma200_on']
    L_1k_log['qqq_vol21'] = regime_df['qqq_vol21']
    cols_log = ['t_date', 'qqq_picks', 'xlk_pick', 'spy_pick', 'state_main', 'state_sub',
                'ov_tickers', 'n_distinct', 'max_single_w', 'gross', 'net', 'turnover',
                'ov_stock_ret', 'non_ov_stock_ret', 'sep_on', 'qqq_sma200_on', 'qqq_vol21']
    L_1k_log[cols_log].to_csv(os.path.join(HERE, '01c_monthly_3S_G1_1k_consensus_ledger.csv'))

    print('--- PRIORITY #1 TABLE: 3S_G1_1k & 3S_Core3_1a CONSENSUS DIAGNOSTIC ---')
    for m_show in [
        '3S_G1_1k (50% QQQ[<=5]+25% Tech[1]+25% SPY[<=3])',
        '3S_G1_1a (50% QQQ[<=5]+25% Tech[1]+25% SPY[1])',
        '3S_Core3_1a (Unbuffered Hard Top-2/1/1)',
        'Pure_Formation_Rank_Signal (on 3S_G1_1k)',
        '2L_G1_SPY_2e (50% QQQ[<=5]+50% SPY[<=3])',
    ]:
        print(f'\nModel: {m_show}')
        sub_p = df_diag[df_diag['Strategy'] == m_show]
        for _, r in sub_p.iterrows():
            ov_s = f"{r['Consensus_Stock_Ann_CAGR']*100:6.1f}%" if pd.notna(r['Consensus_Stock_Ann_CAGR']) else "   N/A"
            nov_s = f"{r['NonConsensus_Stock_Ann_CAGR']*100:6.1f}%" if pd.notna(r['NonConsensus_Stock_Ann_CAGR']) else "   N/A"
            print(f"  {r['Consensus_State']:<48} | N={int(r['Months_N']):3d} ({r['Share_Pct']*100:4.1f}%) | "
                  f"Mean={r['Mean_Mo_Ret']*100:+5.2f}% | Med={r['Median_Mo_Ret']*100:+5.2f}% | "
                  f"CAGR={r['Ann_Compounded_Ret']*100:6.2f}% | Win={r['Win_Rate']*100:4.1f}% | "
                  f"SR={r['Ann_Sharpe_Excess']:4.2f} | Worst={r['Worst_Mo_Ret']*100:+6.2f}% ({r['Worst_Mo_YM']}) | "
                  f"OvStock={ov_s} vs NonOv={nov_s}")

    # =========================================================================
    # STEP 2: BURST MODE 1 — CONSENSUS / OVERLAP CONVICTION SIZING
    # =========================================================================
    print('\n[Step 2/6] Running Burst Mode 1: Consensus / Overlap Conviction Sizing...')

    base_3s_1k = {'qqq': L_qqq_g1_5, 'xlk': L_xlk_c3, 'spy': L_spy_g1_3}
    base_3s_1a = {'qqq': L_qqq_g1_5, 'xlk': L_xlk_c3, 'spy': L_spy_c3}
    base_3s_c3 = {'qqq': L_qqq_c3, 'xlk': L_xlk_c3, 'spy': L_spy_c3}
    base_2s_spy = {'qqq': L_qqq_g1_5, 'xlk': L_xlk_c3, 'spy': L_spy_g1_3}

    def make_3leg_conviction_rule(mult_0, mult_2, mult_3, borrow_spread_bp=50.0,
                                  cash_earns_rf=False, conc_3leg_w=None, sub2_only_tech_spy=False):
        def rule_fn(ym, r_qqq, r_xlk, r_spy, reg_row, lk):
            q_w = r_qqq['weights_dict']
            t_w = r_xlk['weights_dict']
            s_w = r_spy['weights_dict']
            w_base = {}
            for tk, v in q_w.items():
                w_base[tk] = w_base.get(tk, 0.0) + 0.50 * v
            for tk, v in t_w.items():
                w_base[tk] = w_base.get(tk, 0.0) + 0.25 * v
            for tk, v in s_w.items():
                w_base[tk] = w_base.get(tk, 0.0) + 0.25 * v

            q_set = set(q_w.keys())
            t_pick = list(t_w.keys())[0]
            s_pick = list(s_w.keys())[0]
            t_in_q = t_pick in q_set
            s_in_q = s_pick in q_set
            t_eq_s = (t_pick == s_pick)

            if t_eq_s and t_in_q:
                state = '3_Triple'
                mult = mult_3
                if conc_3leg_w is not None:
                    # Concentrate unlevered 1.0x weight into triple-consensus stock
                    other_q = [x for x in q_w.keys() if x != t_pick]
                    w_base = {t_pick: conc_3leg_w}
                    if other_q and (1.0 - conc_3leg_w) > 0:
                        w_base[other_q[0]] = 1.0 - conc_3leg_w
            elif t_eq_s or t_in_q or s_in_q:
                state = '2_TwoLeg'
                if sub2_only_tech_spy and not t_eq_s:
                    mult = mult_0
                else:
                    mult = mult_2
            else:
                state = '0_NoOverlap'
                mult = mult_0

            w_stocks = {tk: v * mult for tk, v in w_base.items()}
            w_cash = max(0.0, 1.0 - mult)
            w_borrow = max(0.0, mult - 1.0)
            r_cash = float(reg_row['rf_monthly']) if cash_earns_rf else 0.0
            r_borrow = float(reg_row['rf_monthly']) + (borrow_spread_bp / 10000.0) / 12.0
            return w_stocks, w_cash, r_cash, w_borrow, r_borrow, state
        return rule_fn

    def make_2leg_spy_conviction_rule(mult_0, mult_2, borrow_spread_bp=50.0, conc_ov_w=None):
        def rule_fn(ym, r_qqq, r_xlk, r_spy, reg_row, lk):
            q_w = r_qqq['weights_dict']
            s_w = r_spy['weights_dict']
            w_base = {}
            for tk, v in q_w.items():
                w_base[tk] = w_base.get(tk, 0.0) + 0.50 * v
            for tk, v in s_w.items():
                w_base[tk] = w_base.get(tk, 0.0) + 0.50 * v

            s_pick = list(s_w.keys())[0]
            if s_pick in set(q_w.keys()):
                state = '2_Overlap'
                mult = mult_2
                if conc_ov_w is not None:
                    other_q = [x for x in q_w.keys() if x != s_pick]
                    w_base = {s_pick: conc_ov_w}
                    if other_q and (1.0 - conc_ov_w) > 0:
                        w_base[other_q[0]] = 1.0 - conc_ov_w
            else:
                state = '0_NoOverlap'
                mult = mult_0

            w_stocks = {tk: v * mult for tk, v in w_base.items()}
            w_cash = max(0.0, 1.0 - mult)
            w_borrow = max(0.0, mult - 1.0)
            r_borrow = float(reg_row['rf_monthly']) + (borrow_spread_bp / 10000.0) / 12.0
            return w_stocks, w_cash, 0.0, w_borrow, r_borrow, state
        return rule_fn

    # First run single-account unlevered controls
    L_ctrl_1k, dd_c56_1k, dd_o2c_1k = simulate_dynamic_portfolio(
        base_3s_1k, regime_df, lookups, cal_days, spy_daily_c, spy_daily_o,
        make_3leg_conviction_rule(1.0, 1.0, 1.0)
    )
    ref_1k_r = L_ctrl_1k['net']

    mode1_configs = [
        # --- Base Controls ---
        ('M1_00_3S_G1_1k_Ctrl (1.0x/1.0x/1.0x, Single-Acct)', 'M1_Control', base_3s_1k,
         make_3leg_conviction_rule(1.0, 1.0, 1.0)),
        ('M1_00b_3S_G1_1a_Ctrl (1.0x/1.0x/1.0x, Single-Acct)', 'M1_Control', base_3s_1a,
         make_3leg_conviction_rule(1.0, 1.0, 1.0)),
        ('M1_00c_3S_Core3_1a_Ctrl (1.0x/1.0x/1.0x, Single-Acct)', 'M1_Control', base_3s_c3,
         make_3leg_conviction_rule(1.0, 1.0, 1.0)),
        ('M1_00d_2L_G1_SPY_2e_Ctrl (1.0x/1.0x, Single-Acct)', 'M1_Control', base_2s_spy,
         make_2leg_spy_conviction_rule(1.0, 1.0)),

        # --- 3S_G1_1k: Only 3-Leg Triple Consensus Levered (1.0x / 1.0x / L_3) ---
        ('M1_1a_3S_G1_1k (1.0x / 1.0x / 1.25x on 3-Leg, Tbill+50bp)', 'M1_3Leg_Only_Lev', base_3s_1k,
         make_3leg_conviction_rule(1.0, 1.0, 1.25, borrow_spread_bp=50.0)),
        ('M1_1b_3S_G1_1k (1.0x / 1.0x / 1.50x on 3-Leg, Tbill+50bp)', 'M1_3Leg_Only_Lev', base_3s_1k,
         make_3leg_conviction_rule(1.0, 1.0, 1.50, borrow_spread_bp=50.0)),
        ('M1_1c_3S_G1_1k (1.0x / 1.0x / 1.75x on 3-Leg, Tbill+50bp)', 'M1_3Leg_Only_Lev', base_3s_1k,
         make_3leg_conviction_rule(1.0, 1.0, 1.75, borrow_spread_bp=50.0)),
        ('M1_1d_3S_G1_1k (1.0x / 1.0x / 1.50x on 3-Leg, Tbill+0bp)', 'M1_3Leg_Only_Lev', base_3s_1k,
         make_3leg_conviction_rule(1.0, 1.0, 1.50, borrow_spread_bp=0.0)),

        # --- 3S_G1_1k: Stepwise 2-Leg & 3-Leg Consensus Leverage ---
        ('M1_2a_3S_G1_1k (1.0x / 1.15x / 1.35x, Tbill+50bp)', 'M1_Stepwise_Lev', base_3s_1k,
         make_3leg_conviction_rule(1.0, 1.15, 1.35, borrow_spread_bp=50.0)),
        ('M1_2b_3S_G1_1k (1.0x / 1.25x / 1.50x, Tbill+50bp)', 'M1_Stepwise_Lev', base_3s_1k,
         make_3leg_conviction_rule(1.0, 1.25, 1.50, borrow_spread_bp=50.0)),
        ('M1_2c_3S_G1_1k (1.0x / 1.25x [Tech==SPY only] / 1.50x)', 'M1_Stepwise_Lev', base_3s_1k,
         make_3leg_conviction_rule(1.0, 1.25, 1.50, borrow_spread_bp=50.0, sub2_only_tech_spy=True)),

        # --- 3S_G1_1k: De-Risk 0-Overlap + Boost 3-Leg (Avg Exposure ~ 1.0x!) ---
        ('M1_3a_3S_G1_1k (0.75x on 0-Ov / 1.0x on 2-Leg / 1.25x on 3-Leg)', 'M1_NeutralAvg_Tilt', base_3s_1k,
         make_3leg_conviction_rule(0.75, 1.0, 1.25, borrow_spread_bp=50.0)),
        ('M1_3b_3S_G1_1k (0.75x on 0-Ov / 1.0x on 2-Leg / 1.50x on 3-Leg)', 'M1_NeutralAvg_Tilt', base_3s_1k,
         make_3leg_conviction_rule(0.75, 1.0, 1.50, borrow_spread_bp=50.0)),
        ('M1_3c_3S_G1_1k (0.85x on 0-Ov / 1.0x on 2-Leg / 1.35x on 3-Leg)', 'M1_NeutralAvg_Tilt', base_3s_1k,
         make_3leg_conviction_rule(0.85, 1.0, 1.35, borrow_spread_bp=50.0)),

        # --- 3S_G1_1k: Unlevered 1.0x Concentration on 3-Leg Consensus (75% -> 90% or 100%) ---
        ('M1_4a_3S_G1_1k (Unlevered 1.0x: 3-Leg Conc 75% -> 90%)', 'M1_Unlevered_Conc', base_3s_1k,
         make_3leg_conviction_rule(1.0, 1.0, 1.0, conc_3leg_w=0.90)),
        ('M1_4b_3S_G1_1k (Unlevered 1.0x: 3-Leg Conc 75% -> 100%)', 'M1_Unlevered_Conc', base_3s_1k,
         make_3leg_conviction_rule(1.0, 1.0, 1.0, conc_3leg_w=1.00)),

        # --- Same Consensus Rules on 3S_G1_1a and Unbuffered 3S_Core3_1a ---
        ('M1_5a_3S_G1_1a (1.0x / 1.0x / 1.50x on 3-Leg)', 'M1_Other_3Leg_Models', base_3s_1a,
         make_3leg_conviction_rule(1.0, 1.0, 1.50, borrow_spread_bp=50.0)),
        ('M1_5b_3S_G1_1a (1.0x / 1.25x / 1.50x)', 'M1_Other_3Leg_Models', base_3s_1a,
         make_3leg_conviction_rule(1.0, 1.25, 1.50, borrow_spread_bp=50.0)),
        ('M1_5c_3S_Core3_1a (1.0x / 1.0x / 1.50x on 3-Leg)', 'M1_Other_3Leg_Models', base_3s_c3,
         make_3leg_conviction_rule(1.0, 1.0, 1.50, borrow_spread_bp=50.0)),
        ('M1_5d_3S_Core3_1a (1.0x / 1.25x / 1.50x)', 'M1_Other_3Leg_Models', base_3s_c3,
         make_3leg_conviction_rule(1.0, 1.25, 1.50, borrow_spread_bp=50.0)),

        # --- 2-Leg G1_SPY_2e Consensus Sizing ---
        ('M1_6a_2L_G1_SPY_2e (1.0x on 0-Ov / 1.25x on 2-Leg Overlap)', 'M1_2Leg_SPY', base_2s_spy,
         make_2leg_spy_conviction_rule(1.0, 1.25, borrow_spread_bp=50.0)),
        ('M1_6b_2L_G1_SPY_2e (1.0x on 0-Ov / 1.50x on 2-Leg Overlap)', 'M1_2Leg_SPY', base_2s_spy,
         make_2leg_spy_conviction_rule(1.0, 1.50, borrow_spread_bp=50.0)),
        ('M1_6c_2L_G1_SPY_2e (Unlevered 1.0x: Overlap Conc 75% -> 100%)', 'M1_2Leg_SPY', base_2s_spy,
         make_2leg_spy_conviction_rule(1.0, 1.0, conc_ov_w=1.00)),

        # --- Constant-Leverage Benchmarks (Exact Same Average Exposure Comparison!) ---
        # Note: In 3S_G1_1k, 3-leg triple consensus is 43/213 (20.19%) and 2-leg is 82/213 (38.50%):
        #   - 1.0x/1.0x/1.25x has Avg Exposure = 1.0505x
        #   - 1.0x/1.0x/1.50x has Avg Exposure = 1.1009x
        #   - 1.0x/1.25x/1.50x has Avg Exposure = 1.1972x
        ('M1_Bench_Const_1.050x (Matches Avg Exp of 1.0/1.0/1.25)', 'M1_ConstLev_Bench', base_3s_1k,
         make_3leg_conviction_rule(1.0505, 1.0505, 1.0505, borrow_spread_bp=50.0)),
        ('M1_Bench_Const_1.101x (Matches Avg Exp of 1.0/1.0/1.50)', 'M1_ConstLev_Bench', base_3s_1k,
         make_3leg_conviction_rule(1.1009, 1.1009, 1.1009, borrow_spread_bp=50.0)),
        ('M1_Bench_Const_1.197x (Matches Avg Exp of 1.0/1.25/1.50)', 'M1_ConstLev_Bench', base_3s_1k,
         make_3leg_conviction_rule(1.1972, 1.1972, 1.1972, borrow_spread_bp=50.0)),
        ('M1_Bench_Const_1.500x (Always 1.50x Levered)', 'M1_ConstLev_Bench', base_3s_1k,
         make_3leg_conviction_rule(1.50, 1.50, 1.50, borrow_spread_bp=50.0)),
    ]

    mode1_rows = []
    mode1_ledgers = {}
    for v_name, fam, b_sl, r_fn in mode1_configs:
        Lp, d56, do2c = simulate_dynamic_portfolio(b_sl, regime_df, lookups, cal_days, spy_daily_c, spy_daily_o, r_fn)
        mode1_ledgers[v_name] = Lp
        mode1_rows.append(summarize_burst_variant(v_name, fam, Lp, rf_monthly, d56, do2c, ref_1k_r))

    df_m1 = pd.DataFrame(mode1_rows)
    df_m1.to_csv(os.path.join(HERE, '02_mode1_consensus_conviction_sizing.csv'), index=False)

    print('--- BURST MODE 1 SUMMARY (CONSENSUS CONVICTION SIZING) ---')
    for _, r in df_m1.iterrows():
        print(f"  {r['Variant']:<62} | CAGR={r['CAGR_09_26']*100:6.2f}% | SR={r['Sharpe']:5.3f} | "
              f"MoDD={r['Monthly_MaxDD']*100:6.2f}% | DayDD={r['Daily_MaxDD_5651ec2']*100:6.2f}% | "
              f"AvgExp={r['Avg_Gross_Exp']:4.2f}x | 2022={r['Ret_2022']*100:+6.1f}% | t={r['NW_t_vs_Ctrl']:+5.2f}")

    # =========================================================================
    # STEP 3: BURST MODE 2 — SEP / MACRO REGIME SELECTIVE QQQ SHUTOFF & REALLOCATION
    # =========================================================================
    print('\n[Step 3/6] Running Burst Mode 2: SEP / Trend Selective QQQ Shutoff & Reallocation...')

    def make_regime_routing_rule(reg_col, off_w_qqq, off_w_xlk, off_w_spy,
                                 cash_earns_rf=True, cond_mom_thresh=None):
        """
        When `regime_df.loc[ym, reg_col]` is True (`ON`):
          holds standard `50% QQQ + 25% Tech + 25% SPY`.
        When `False` (`OFF`):
          routes to `(off_w_qqq, off_w_xlk, off_w_spy)`.
          If `cond_mom_thresh` is set (e.g., 0.20 or 0.30), the extra weight above 0.25 on
          Tech or SPY is ONLY allocated if that sleeve's picked stock has `mom_12_1 >= cond_mom_thresh`;
          otherwise that extra budget stays in SGOV/cash!
        """
        def rule_fn(ym, r_qqq, r_xlk, r_spy, reg_row, lk):
            is_on = bool(reg_row[reg_col])
            q_w = r_qqq['weights_dict']
            t_w = r_xlk['weights_dict']
            s_w = r_spy['weights_dict']
            t_pick = list(t_w.keys())[0]
            s_pick = list(s_w.keys())[0]

            if is_on:
                wq, wt, ws = 0.50, 0.25, 0.25
                state = f'{reg_col}_ON'
            else:
                wq = off_w_qqq
                wt = off_w_xlk
                ws = off_w_spy
                if cond_mom_thresh is not None:
                    t_mom = lk['mom_map'].get((ym, t_pick), 0.0)
                    s_mom = lk['mom_map'].get((ym, s_pick), 0.0)
                    if wt > 0.25 and t_mom < cond_mom_thresh:
                        wt = 0.25
                    if ws > 0.25 and s_mom < cond_mom_thresh:
                        ws = 0.25
                state = f'{reg_col}_OFF'

            w_stocks = {}
            for tk, v in q_w.items():
                if wq * v > 0:
                    w_stocks[tk] = w_stocks.get(tk, 0.0) + wq * v
            for tk, v in t_w.items():
                if wt * v > 0:
                    w_stocks[tk] = w_stocks.get(tk, 0.0) + wt * v
            for tk, v in s_w.items():
                if ws * v > 0:
                    w_stocks[tk] = w_stocks.get(tk, 0.0) + ws * v

            tot_w = sum(w_stocks.values())
            w_cash = max(0.0, 1.0 - tot_w)
            w_borrow = max(0.0, tot_w - 1.0)
            r_cash = float(reg_row['rf_monthly']) if cash_earns_rf else 0.0
            r_borrow = float(reg_row['borrow_monthly'])
            return w_stocks, w_cash, r_cash, w_borrow, r_borrow, state
        return rule_fn

    mode2_configs = [
        # Baseline
        ('M2_00_3S_G1_1k_Baseline (Always 50% QQQ + 25% Tech + 25% SPY)', 'M2_Baseline',
         make_regime_routing_rule('sep_on', 0.50, 0.25, 0.25)),

        # --- A. Canonical FOMC SEP Regime (Exits: 2021-09..2023-03, 2023-06..12, 2024-06..09, 2024-12..2025-03, 2026-06..) ---
        ('M2_1a_SEP_Conservative_Cash (SEP OFF: 0% QQQ + 25% Tech + 25% SPY + 50% Cash 0%)', 'M2_SEP_Canonical',
         make_regime_routing_rule('sep_on', 0.00, 0.25, 0.25, cash_earns_rf=False)),
        ('M2_1b_SEP_Conservative_SGOV (SEP OFF: 0% QQQ + 25% Tech + 25% SPY + 50% SGOV)', 'M2_SEP_Canonical',
         make_regime_routing_rule('sep_on', 0.00, 0.25, 0.25, cash_earns_rf=True)),
        ('M2_1c_SEP_HalfRealloc (SEP OFF: 0% QQQ + 37.5% Tech + 37.5% SPY + 25% SGOV)', 'M2_SEP_Canonical',
         make_regime_routing_rule('sep_on', 0.00, 0.375, 0.375, cash_earns_rf=True)),
        ('M2_1d_SEP_Burst_50_50 (SEP OFF: 0% QQQ + 50% Tech + 50% SPY)', 'M2_SEP_Canonical',
         make_regime_routing_rule('sep_on', 0.00, 0.50, 0.50, cash_earns_rf=True)),
        ('M2_1e_SEP_Burst_CondMom25 (SEP OFF: +25% to Tech/SPY only if mom_12_1>=25%, else SGOV)', 'M2_SEP_Canonical',
         make_regime_routing_rule('sep_on', 0.00, 0.50, 0.50, cash_earns_rf=True, cond_mom_thresh=0.25)),
        ('M2_1f_SEP_Burst_CondMom40 (SEP OFF: +25% to Tech/SPY only if mom_12_1>=40%, else SGOV)', 'M2_SEP_Canonical',
         make_regime_routing_rule('sep_on', 0.00, 0.50, 0.50, cash_earns_rf=True, cond_mom_thresh=0.40)),
        ('M2_1g_SEP_Burst_SPY75 (SEP OFF: 0% QQQ + 25% Tech + 75% SPY All-Sector)', 'M2_SEP_Canonical',
         make_regime_routing_rule('sep_on', 0.00, 0.25, 0.75, cash_earns_rf=True)),
        ('M2_1h_SEP_AllOut_SGOV (SEP OFF: 100% SGOV — shut off all 3 legs)', 'M2_SEP_Canonical',
         make_regime_routing_rule('sep_on', 0.00, 0.00, 0.00, cash_earns_rf=True)),

        # --- B. V6 Regime (Kim-Wright Hawkish Path + Forward EPS: exited 2022-02..2022-11) ---
        ('M2_2a_V6_Conservative_SGOV (V6 OFF: 0% QQQ + 25% Tech + 25% SPY + 50% SGOV)', 'M2_V6_HawkEPS',
         make_regime_routing_rule('v6_on', 0.00, 0.25, 0.25, cash_earns_rf=True)),
        ('M2_2b_V6_Burst_50_50 (V6 OFF: 0% QQQ + 50% Tech + 50% SPY)', 'M2_V6_HawkEPS',
         make_regime_routing_rule('v6_on', 0.00, 0.50, 0.50, cash_earns_rf=True)),

        # --- C. Strictly PIT QQQ < SMA200 Regime (Active across full 2009-2026 history, 35 OFF months) ---
        ('M2_3a_QQQ_SMA200_Conservative_SGOV (QQQ<SMA200: 0% QQQ + 25% Tech + 25% SPY + 50% SGOV)', 'M2_QQQ_SMA200',
         make_regime_routing_rule('qqq_sma200_on', 0.00, 0.25, 0.25, cash_earns_rf=True)),
        ('M2_3b_QQQ_SMA200_HalfRealloc (QQQ<SMA200: 0% QQQ + 37.5% Tech + 37.5% SPY + 25% SGOV)', 'M2_QQQ_SMA200',
         make_regime_routing_rule('qqq_sma200_on', 0.00, 0.375, 0.375, cash_earns_rf=True)),
        ('M2_3c_QQQ_SMA200_Burst_50_50 (QQQ<SMA200: 0% QQQ + 50% Tech + 50% SPY)', 'M2_QQQ_SMA200',
         make_regime_routing_rule('qqq_sma200_on', 0.00, 0.50, 0.50, cash_earns_rf=True)),
        ('M2_3d_QQQ_SMA200_Burst_CondMom30 (QQQ<SMA200: +25% to Tech/SPY if mom>=30%, else SGOV)', 'M2_QQQ_SMA200',
         make_regime_routing_rule('qqq_sma200_on', 0.00, 0.50, 0.50, cash_earns_rf=True, cond_mom_thresh=0.30)),
        ('M2_3e_QQQ_SMA200_Burst_SPY75 (QQQ<SMA200: 0% QQQ + 25% Tech + 75% SPY)', 'M2_QQQ_SMA200',
         make_regime_routing_rule('qqq_sma200_on', 0.00, 0.25, 0.75, cash_earns_rf=True)),
    ]

    mode2_rows = []
    for v_name, fam, r_fn in mode2_configs:
        Lp, d56, do2c = simulate_dynamic_portfolio(base_3s_1k, regime_df, lookups, cal_days, spy_daily_c, spy_daily_o, r_fn)
        mode2_rows.append(summarize_burst_variant(v_name, fam, Lp, rf_monthly, d56, do2c, ref_1k_r))

    df_m2 = pd.DataFrame(mode2_rows)
    df_m2.to_csv(os.path.join(HERE, '03_mode2_sep_and_trend_qqq_routing.csv'), index=False)

    # Also build a diagnostic table of what QQQ, Tech, and SPY sleeves actually returned during
    # SEP OFF vs SEP ON (and in 2022 vs Post-2022 SEP OFF months!)
    sep_off_diag = []
    for period_label, ym_mask in [
        ('All_SEP_ON_Months (178m)', regime_df['sep_on']),
        ('All_SEP_OFF_Months (35m: 2021-10..2026-09)', ~regime_df['sep_on']),
        ('SEP_OFF_2021_2022_Cycle (18m: 2021-10..2023-03)', (~regime_df['sep_on']) & (regime_df.index <= '2023-03')),
        ('SEP_OFF_Post2022_Cycles (17m: 2023-07..2026-09)', (~regime_df['sep_on']) & (regime_df.index > '2023-03')),
        ('All_QQQ_Below_SMA200_Months (35m)', ~regime_df['qqq_sma200_on']),
        ('QQQ_Below_SMA200_Ex2022 (24m)', (~regime_df['qqq_sma200_on']) & ((regime_df.index < '2022-01') | (regime_df.index > '2022-12'))),
    ]:
        yms = regime_df.index[ym_mask]
        n_m = len(yms)
        if n_m == 0:
            continue
        rq = L_qqq_g1_5.loc[yms, 'net'].values
        rt = L_xlk_c3.loc[yms, 'net'].values
        rs = L_spy_g1_3.loc[yms, 'net'].values
        r_base = L_ctrl_1k.loc[yms, 'net'].values
        sep_off_diag.append({
            'Regime_Slice': period_label,
            'Months_N': n_m,
            'QQQ_Sleeve_Mean_Mo': float(np.mean(rq)),
            'QQQ_Sleeve_Cum_Ret': float(np.prod(1.0 + rq) - 1.0),
            'Tech_Sleeve_Mean_Mo': float(np.mean(rt)),
            'Tech_Sleeve_Cum_Ret': float(np.prod(1.0 + rt) - 1.0),
            'SPY_Sleeve_Mean_Mo': float(np.mean(rs)),
            'SPY_Sleeve_Cum_Ret': float(np.prod(1.0 + rs) - 1.0),
            'Base_3S_G1_1k_Mean_Mo': float(np.mean(r_base)),
            'Base_3S_G1_1k_Cum_Ret': float(np.prod(1.0 + r_base) - 1.0),
        })
    pd.DataFrame(sep_off_diag).to_csv(os.path.join(HERE, '03b_sep_and_sma200_sleeve_attribution.csv'), index=False)

    print('--- BURST MODE 2 SUMMARY (SEP & QQQ<SMA200 SELECTIVE ROUTING) ---')
    for _, r in df_m2.iterrows():
        print(f"  {r['Variant']:<68} | CAGR={r['CAGR_09_26']*100:6.2f}% | Ex22={r['CAGR_Ex2022']*100:6.2f}% | "
              f"2022={r['Ret_2022']*100:+6.1f}% | 23-26={r['CAGR_2023_2026']*100:6.2f}% | "
              f"SR={r['Sharpe']:5.3f} | MoDD={r['Monthly_MaxDD']*100:6.2f}% | DayDD={r['Daily_MaxDD_5651ec2']*100:6.2f}%")

    # =========================================================================
    # STEP 4: BURST MODE 3 — TREND + LOW CRASH RISK + CONSENSUS LEVERAGE
    # =========================================================================
    print('\n[Step 4/6] Running Burst Mode 3: Trend + Low Crash Risk + Consensus Controlled Leverage...')

    # Compute trailing expanding/rolling vol percentiles on the base 3S_G1_1k portfolio & QQQ
    # At each formation date t, compute the formation-time expected portfolio volatility
    # (average vol_12_1 of held stocks) and QQQ 21d/63d vol
    port_form_vol = {}
    for ym, row in L_ctrl_1k.iterrows():
        h_w = row['holdings_dict']
        v_est = sum(w_tk * lookups['vol_map'].get((ym, tk), 0.35) for tk, w_tk in h_w.items())
        port_form_vol[ym] = float(v_est)
    regime_df['port_vol_est'] = pd.Series(port_form_vol)

    def make_mode3_rule(trend_mode='sep_on', vol_cap_q21=0.30, port_vol_cap=0.55,
                        mult_2leg=1.25, mult_3leg=1.50, panic_mult=1.0,
                        sep_off_routing=None):
        """
        Barroso-Santa-Clara / Daniel-Moskowitz crash-protected consensus leverage:
          - Checks Trend (`sep_on`, `qqq_sma200_on`, or `both`)
          - Checks Crash/Vol gate: `qqq_vol21 <= vol_cap_q21` AND `port_vol_est <= port_vol_cap`
            AND not `dm_panic`
          - Only when BOTH Trend == ON and Vol/Crash Gate == Safe:
              * 2-Leg Overlap -> `mult_2leg`
              * 3-Leg Consensus -> `mult_3leg`
              * 0-Overlap -> `1.0x`
          - When in panic state (`dm_panic`), applies `panic_mult` (`1.0x` or `0.75x`).
          - Optionally combines with `sep_off_routing` (`'sgov_50'` or `'burst_50_50'`).
        """
        def rule_fn(ym, r_qqq, r_xlk, r_spy, reg_row, lk):
            q_w = r_qqq['weights_dict']
            t_w = r_xlk['weights_dict']
            s_w = r_spy['weights_dict']

            if trend_mode == 'sep_on':
                trend_ok = bool(reg_row['sep_on'])
            elif trend_mode == 'qqq_sma200':
                trend_ok = bool(reg_row['qqq_sma200_on'])
            elif trend_mode == 'sep_and_sma200':
                trend_ok = bool(reg_row['sep_on']) and bool(reg_row['qqq_sma200_on'])
            elif trend_mode == 'always_on':
                trend_ok = True
            else:
                trend_ok = bool(reg_row['sep_on'])

            vol_ok = (float(reg_row['qqq_vol21']) <= vol_cap_q21) and \
                     (float(reg_row['port_vol_est']) <= port_vol_cap) and \
                     (not bool(reg_row['dm_panic']))

            # Base weights (possibly routed if trend_ok is False and sep_off_routing is active)
            if not trend_ok and sep_off_routing == 'sgov_50':
                wq, wt, ws = 0.00, 0.25, 0.25
            elif not trend_ok and sep_off_routing == 'burst_50_50':
                wq, wt, ws = 0.00, 0.50, 0.50
            elif not trend_ok and sep_off_routing == 'half_375':
                wq, wt, ws = 0.00, 0.375, 0.375
            else:
                wq, wt, ws = 0.50, 0.25, 0.25

            w_base = {}
            for tk, v in q_w.items():
                if wq * v > 0:
                    w_base[tk] = w_base.get(tk, 0.0) + wq * v
            for tk, v in t_w.items():
                if wt * v > 0:
                    w_base[tk] = w_base.get(tk, 0.0) + wt * v
            for tk, v in s_w.items():
                if ws * v > 0:
                    w_base[tk] = w_base.get(tk, 0.0) + ws * v

            q_set = set(q_w.keys())
            t_pick = list(t_w.keys())[0]
            s_pick = list(s_w.keys())[0]
            t_in_q = t_pick in q_set
            s_in_q = s_pick in q_set
            t_eq_s = (t_pick == s_pick)

            if trend_ok and vol_ok:
                if t_eq_s and t_in_q:
                    mult = mult_3leg
                    state = 'Safe_3Leg_Boost'
                elif t_eq_s or t_in_q or s_in_q:
                    mult = mult_2leg
                    state = 'Safe_2Leg_Boost'
                else:
                    mult = 1.0
                    state = 'Safe_0Ov_1x'
            else:
                if bool(reg_row['dm_panic']):
                    mult = panic_mult
                    state = 'Panic_Protected'
                else:
                    mult = 1.0
                    state = 'TrendOrVol_Gated_1x'

            w_stocks = {tk: v * mult for tk, v in w_base.items()}
            tot_w = sum(w_stocks.values())
            w_cash = max(0.0, 1.0 - tot_w)
            w_borrow = max(0.0, tot_w - 1.0)
            r_cash = float(reg_row['rf_monthly']) if sep_off_routing else 0.0
            r_borrow = float(reg_row['borrow_monthly'])
            return w_stocks, w_cash, r_cash, w_borrow, r_borrow, state
        return rule_fn

    mode3_configs = [
        # Baseline unlevered & Mode 1 unconditional consensus leverage for comparison
        ('M3_00_Unlevered_Ctrl (1.0x Always)', 'M3_Control',
         make_3leg_conviction_rule(1.0, 1.0, 1.0)),
        ('M3_01_Unconditional_Consensus_1.0_1.0_1.50 (No Trend/Vol Gate)', 'M3_Uncond_Ref',
         make_3leg_conviction_rule(1.0, 1.0, 1.50)),
        ('M3_02_Unconditional_Consensus_1.0_1.25_1.50 (No Trend/Vol Gate)', 'M3_Uncond_Ref',
         make_3leg_conviction_rule(1.0, 1.25, 1.50)),

        # --- A. SEP == ON + Low Crash Risk + 3-Leg Only (1.0x / 1.0x / 1.50x) ---
        ('M3_1a_SEP_ON + LowVol(Q21<=30%,Port<=55%) + 3Leg=1.25x', 'M3_SEP_VolGated',
         make_mode3_rule('sep_on', vol_cap_q21=0.30, port_vol_cap=0.55, mult_2leg=1.0, mult_3leg=1.25)),
        ('M3_1b_SEP_ON + LowVol(Q21<=30%,Port<=55%) + 3Leg=1.50x', 'M3_SEP_VolGated',
         make_mode3_rule('sep_on', vol_cap_q21=0.30, port_vol_cap=0.55, mult_2leg=1.0, mult_3leg=1.50)),
        ('M3_1c_SEP_ON + LowVol(Q21<=30%,Port<=55%) + 2Leg=1.25x / 3Leg=1.50x', 'M3_SEP_VolGated',
         make_mode3_rule('sep_on', vol_cap_q21=0.30, port_vol_cap=0.55, mult_2leg=1.25, mult_3leg=1.50)),
        ('M3_1d_SEP_ON + LowVol + 2Leg=1.25x / 3Leg=1.50x + Panic=0.75x', 'M3_SEP_VolGated',
         make_mode3_rule('sep_on', vol_cap_q21=0.30, port_vol_cap=0.55, mult_2leg=1.25, mult_3leg=1.50, panic_mult=0.75)),

        # --- B. Strictly PIT QQQ >= SMA200 + Low Crash Risk + Consensus Leverage ---
        ('M3_2a_QQQ>=SMA200 + LowVol(Q21<=30%,Port<=55%) + 3Leg=1.25x', 'M3_SMA200_VolGated',
         make_mode3_rule('qqq_sma200', vol_cap_q21=0.30, port_vol_cap=0.55, mult_2leg=1.0, mult_3leg=1.25)),
        ('M3_2b_QQQ>=SMA200 + LowVol(Q21<=30%,Port<=55%) + 3Leg=1.50x', 'M3_SMA200_VolGated',
         make_mode3_rule('qqq_sma200', vol_cap_q21=0.30, port_vol_cap=0.55, mult_2leg=1.0, mult_3leg=1.50)),
        ('M3_2c_QQQ>=SMA200 + LowVol(Q21<=30%,Port<=55%) + 2Leg=1.25x / 3Leg=1.50x', 'M3_SMA200_VolGated',
         make_mode3_rule('qqq_sma200', vol_cap_q21=0.30, port_vol_cap=0.55, mult_2leg=1.25, mult_3leg=1.50)),
        ('M3_2d_QQQ>=SMA200 + LowVol + 2Leg=1.25x / 3Leg=1.50x + Panic=0.75x', 'M3_SMA200_VolGated',
         make_mode3_rule('qqq_sma200', vol_cap_q21=0.30, port_vol_cap=0.55, mult_2leg=1.25, mult_3leg=1.50, panic_mult=0.75)),

        # --- C. Both SEP==ON AND QQQ>=SMA200 + Low Vol Gate ---
        ('M3_3a_SEP_AND_SMA200 + LowVol + 3Leg=1.50x', 'M3_DualTrend_VolGated',
         make_mode3_rule('sep_and_sma200', vol_cap_q21=0.30, port_vol_cap=0.55, mult_2leg=1.0, mult_3leg=1.50)),
        ('M3_3b_SEP_AND_SMA200 + LowVol + 2Leg=1.25x / 3Leg=1.50x', 'M3_DualTrend_VolGated',
         make_mode3_rule('sep_and_sma200', vol_cap_q21=0.30, port_vol_cap=0.55, mult_2leg=1.25, mult_3leg=1.50)),

        # --- D. Combined Mode 2 + Mode 3 (Regime OFF routes QQQ; Regime ON + LowVol + Consensus boosts) ---
        ('M3_4a_Combined: SEP_OFF->50%SGOV | SEP_ON+LowVol+3Leg->1.50x', 'M3_Combined_M2_M3',
         make_mode3_rule('sep_on', vol_cap_q21=0.30, port_vol_cap=0.55, mult_2leg=1.0, mult_3leg=1.50, sep_off_routing='sgov_50')),
        ('M3_4b_Combined: SEP_OFF->50/50 Tech+SPY | SEP_ON+LowVol+3Leg->1.50x', 'M3_Combined_M2_M3',
         make_mode3_rule('sep_on', vol_cap_q21=0.30, port_vol_cap=0.55, mult_2leg=1.0, mult_3leg=1.50, sep_off_routing='burst_50_50')),
        ('M3_4c_Combined: QQQ<SMA200->50%SGOV | QQQ>=SMA200+LowVol+3Leg->1.50x', 'M3_Combined_M2_M3',
         make_mode3_rule('qqq_sma200', vol_cap_q21=0.30, port_vol_cap=0.55, mult_2leg=1.0, mult_3leg=1.50, sep_off_routing='sgov_50')),
        ('M3_4d_Combined: QQQ<SMA200->50/50 Tech+SPY | QQQ>=SMA200+LowVol+3Leg->1.50x', 'M3_Combined_M2_M3',
         make_mode3_rule('qqq_sma200', vol_cap_q21=0.30, port_vol_cap=0.55, mult_2leg=1.0, mult_3leg=1.50, sep_off_routing='burst_50_50')),
    ]

    mode3_rows = []
    for v_name, fam, r_fn in mode3_configs:
        Lp, d56, do2c = simulate_dynamic_portfolio(base_3s_1k, regime_df, lookups, cal_days, spy_daily_c, spy_daily_o, r_fn)
        mode3_rows.append(summarize_burst_variant(v_name, fam, Lp, rf_monthly, d56, do2c, ref_1k_r))

    df_m3 = pd.DataFrame(mode3_rows)
    df_m3.to_csv(os.path.join(HERE, '04_mode3_crash_protected_consensus_leverage.csv'), index=False)

    print('--- BURST MODE 3 SUMMARY (CRASH-PROTECTED CONSENSUS LEVERAGE) ---')
    for _, r in df_m3.iterrows():
        print(f"  {r['Variant']:<68} | CAGR={r['CAGR_09_26']*100:6.2f}% | SR={r['Sharpe']:5.3f} | "
              f"MoDD={r['Monthly_MaxDD']*100:6.2f}% | DayDD={r['Daily_MaxDD_5651ec2']*100:6.2f}% | "
              f"AvgExp={r['Avg_Gross_Exp']:4.2f}x | 2022={r['Ret_2022']*100:+6.1f}% | t={r['NW_t_vs_Ctrl']:+5.2f}")

    # =========================================================================
    # STEP 5: BURST MODE 4 — EAR (EARNINGS REACTION) + MOMENTUM CONSENSUS
    # =========================================================================
    print('\n[Step 5/6] Running Burst Mode 4: EAR + Momentum Consensus Diagnostic & Backtest...')

    # First: Build Diagnostic Table of Consensus State x EAR Confirmation on 3S_G1_1k
    L_ear_diag = annotated_3s['3S_G1_1k (50% QQQ[<=5]+25% Tech[1]+25% SPY[<=3])'].copy()
    ear4_ov_list = []
    ear1_ov_list = []
    qqq_both_ear4_pos = []
    for ym, row in L_ear_diag.iterrows():
        sp = row['sleeve_picks']
        q_picks = [x for x in sp['qqq'].split('|') if x]
        ov_tks = [x for x in row['ov_tickers'].split('|') if x]

        # Check EAR of overlapping stock (if any), else average EAR of QQQ picks
        target_tks = ov_tks if ov_tks else q_picks
        e4_vals = [lookups['ear_sum4_map'].get((ym, tk), np.nan) for tk in target_tks]
        e4_vals = [x for x in e4_vals if pd.notna(x)]
        e1_vals = [lookups['ear_latest_map'].get((ym, tk), np.nan) for tk in target_tks]
        e1_vals = [x for x in e1_vals if pd.notna(x)]

        ear4_ov_list.append(float(np.mean(e4_vals)) if e4_vals else np.nan)
        ear1_ov_list.append(float(np.mean(e1_vals)) if e1_vals else np.nan)

        q_e4 = [lookups['ear_sum4_map'].get((ym, tk), np.nan) for tk in q_picks]
        qqq_both_ear4_pos.append(all(pd.notna(x) and x > 0 for x in q_e4))

    L_ear_diag['ov_ear_sum4'] = ear4_ov_list
    L_ear_diag['ov_ear_latest'] = ear1_ov_list
    L_ear_diag['qqq_both_ear4_pos'] = qqq_both_ear4_pos

    ear_diag_rows = []
    for st_m in ['0_No_Overlap', '2_Two_Leg_Overlap', '3_Triple_Consensus']:
        sub_st = L_ear_diag[L_ear_diag['state_main'] == st_m]
        sub_pos4 = sub_st[sub_st['ov_ear_sum4'] > 0]
        sub_neg4 = sub_st[sub_st['ov_ear_sum4'] <= 0]
        sub_pos1 = sub_st[sub_st['ov_ear_latest'] > 0]
        sub_neg1 = sub_st[sub_st['ov_ear_latest'] <= 0]
        for lbl, s_df in [
            (f'{st_m} | ALL', sub_st),
            (f'{st_m} | WITH ear_sum4 > 0', sub_pos4),
            (f'{st_m} | WITH ear_sum4 <= 0', sub_neg4),
            (f'{st_m} | WITH ear_latest > 0', sub_pos1),
            (f'{st_m} | WITH ear_latest <= 0', sub_neg1),
        ]:
            if len(s_df) > 0:
                ear_diag_rows.append(summarize_bucket_rows('3S_G1_1k_x_EAR', lbl, s_df, rf_monthly))

    df_ear_diag = pd.DataFrame([x for x in ear_diag_rows if x is not None])
    df_ear_diag.to_csv(os.path.join(HERE, '05b_ear_consensus_diagnostic.csv'), index=False)

    print('--- BURST MODE 4 DIAGNOSTIC: CONSENSUS x EAR CONFIRMATION ---')
    for _, r in df_ear_diag.iterrows():
        print(f"  {r['Consensus_State']:<45} | N={int(r['Months_N']):3d} ({r['Share_Pct']*100:4.1f}%) | "
              f"Mean={r['Mean_Mo_Ret']*100:+5.2f}% | CAGR={r['Ann_Compounded_Ret']*100:6.2f}% | "
              f"Win={r['Win_Rate']*100:4.1f}% | SR={r['Ann_Sharpe_Excess']:4.2f} | Worst={r['Worst_Mo_Ret']*100:+6.2f}%")

    # Second: Backtest EAR-Confirmed Conviction Sizing
    def make_mode4_ear_rule(ear_col='ear_sum4', ear_thresh=0.0, mult_2leg=1.0, mult_3leg=1.50,
                            require_trend_vol_gate=False):
        def rule_fn(ym, r_qqq, r_xlk, r_spy, reg_row, lk):
            q_w = r_qqq['weights_dict']
            t_w = r_xlk['weights_dict']
            s_w = r_spy['weights_dict']
            w_base = {}
            for tk, v in q_w.items():
                w_base[tk] = w_base.get(tk, 0.0) + 0.50 * v
            for tk, v in t_w.items():
                w_base[tk] = w_base.get(tk, 0.0) + 0.25 * v
            for tk, v in s_w.items():
                w_base[tk] = w_base.get(tk, 0.0) + 0.25 * v

            q_set = set(q_w.keys())
            t_pick = list(t_w.keys())[0]
            s_pick = list(s_w.keys())[0]
            t_in_q = t_pick in q_set
            s_in_q = s_pick in q_set
            t_eq_s = (t_pick == s_pick)

            emap = lk['ear_sum4_map'] if ear_col == 'ear_sum4' else lk['ear_latest_map']

            gate_ok = True
            if require_trend_vol_gate:
                gate_ok = bool(reg_row['qqq_sma200_on']) and (float(reg_row['qqq_vol21']) <= 0.30) and \
                          (float(reg_row['port_vol_est']) <= 0.55) and (not bool(reg_row['dm_panic']))

            if t_eq_s and t_in_q:
                ev = emap.get((ym, t_pick), np.nan)
                ear_ok = pd.notna(ev) and (ev > ear_thresh)
                mult = mult_3leg if (ear_ok and gate_ok) else 1.0
                state = '3Leg_EAR_Confirmed' if (ear_ok and gate_ok) else '3Leg_NoEAR_1x'
            elif t_eq_s or t_in_q or s_in_q:
                ov_tk = t_pick if (t_eq_s or t_in_q) else s_pick
                ev = emap.get((ym, ov_tk), np.nan)
                ear_ok = pd.notna(ev) and (ev > ear_thresh)
                mult = mult_2leg if (ear_ok and gate_ok) else 1.0
                state = '2Leg_EAR_Confirmed' if (ear_ok and gate_ok) else '2Leg_NoEAR_1x'
            else:
                mult = 1.0
                state = '0Ov_1x'

            w_stocks = {tk: v * mult for tk, v in w_base.items()}
            w_cash = max(0.0, 1.0 - mult)
            w_borrow = max(0.0, mult - 1.0)
            r_borrow = float(reg_row['borrow_monthly'])
            return w_stocks, w_cash, 0.0, w_borrow, r_borrow, state
        return rule_fn

    mode4_configs = [
        ('M4_00_Unlevered_Ctrl (1.0x Always)', 'M4_Control',
         make_3leg_conviction_rule(1.0, 1.0, 1.0)),
        ('M4_1a_3Leg + ear_sum4>0 -> 1.25x (else 1.0x)', 'M4_EAR_Sum4',
         make_mode4_ear_rule('ear_sum4', 0.0, mult_2leg=1.0, mult_3leg=1.25)),
        ('M4_1b_3Leg + ear_sum4>0 -> 1.50x (else 1.0x)', 'M4_EAR_Sum4',
         make_mode4_ear_rule('ear_sum4', 0.0, mult_2leg=1.0, mult_3leg=1.50)),
        ('M4_1c_2Leg(1.25x)/3Leg(1.50x) + ear_sum4>0', 'M4_EAR_Sum4',
         make_mode4_ear_rule('ear_sum4', 0.0, mult_2leg=1.25, mult_3leg=1.50)),
        ('M4_1d_3Leg + ear_sum4>+5% -> 1.50x (High EAR Conviction)', 'M4_EAR_Sum4',
         make_mode4_ear_rule('ear_sum4', 0.05, mult_2leg=1.0, mult_3leg=1.50)),
        ('M4_2a_3Leg + ear_latest>0 -> 1.50x (Latest Quarter Beat)', 'M4_EAR_Latest',
         make_mode4_ear_rule('ear_latest', 0.0, mult_2leg=1.0, mult_3leg=1.50)),
        ('M4_3a_3Leg + ear_sum4>0 + QQQ>=SMA200 + LowVol -> 1.50x', 'M4_EAR_CrashProtected',
         make_mode4_ear_rule('ear_sum4', 0.0, mult_2leg=1.0, mult_3leg=1.50, require_trend_vol_gate=True)),
        ('M4_3b_2Leg(1.25x)/3Leg(1.50x) + ear_sum4>0 + QQQ>=SMA200 + LowVol', 'M4_EAR_CrashProtected',
         make_mode4_ear_rule('ear_sum4', 0.0, mult_2leg=1.25, mult_3leg=1.50, require_trend_vol_gate=True)),
    ]

    mode4_rows = []
    for v_name, fam, r_fn in mode4_configs:
        Lp, d56, do2c = simulate_dynamic_portfolio(base_3s_1k, regime_df, lookups, cal_days, spy_daily_c, spy_daily_o, r_fn)
        mode4_rows.append(summarize_burst_variant(v_name, fam, Lp, rf_monthly, d56, do2c, ref_1k_r))

    df_m4 = pd.DataFrame(mode4_rows)
    df_m4.to_csv(os.path.join(HERE, '05_mode4_ear_momentum_consensus.csv'), index=False)

    print('--- BURST MODE 4 SUMMARY (EAR + MOMENTUM CONSENSUS SIZING) ---')
    for _, r in df_m4.iterrows():
        print(f"  {r['Variant']:<68} | CAGR={r['CAGR_09_26']*100:6.2f}% | SR={r['Sharpe']:5.3f} | "
              f"MoDD={r['Monthly_MaxDD']*100:6.2f}% | DayDD={r['Daily_MaxDD_5651ec2']*100:6.2f}% | "
              f"AvgExp={r['Avg_Gross_Exp']:4.2f}x | 2022={r['Ret_2022']*100:+6.1f}% | t={r['NW_t_vs_Ctrl']:+5.2f}")

    # =========================================================================
    # STEP 6: MULTIPLE-TESTING DEFLATED SHARPE RATIO (DSR, CUMULATIVE N = 878 + NEW)
    # =========================================================================
    print('\n[Step 6/6] Computing Cumulative Multiple-Testing Deflated Sharpe Ratio (DSR)...')

    reg_path = os.path.join(SPY_DIR, '08b_master_all_trials_sharpe_registry.csv')
    reg_df = pd.read_csv(reg_path)

    # Combine all new unique variants tested in this Round 8 audit
    all_r8_dfs = [df_m1, df_m2, df_m3, df_m4]
    df_r8_all = pd.concat(all_r8_dfs, ignore_index=True)
    # Drop duplicates of the control rows
    df_r8_unique = df_r8_all.drop_duplicates(subset=['Variant']).reset_index(drop=True)

    sq12 = np.sqrt(12.0)
    idx_213 = pd.date_range('2009-01-31', '2026-09-30', freq='ME')
    rf_213 = rf_monthly.reindex(idx_213).ffill().fillna(0.0)
    rf_ann_mean = float(rf_213.mean() * 12.0)

    r8_reg_rows = []
    for _, r in df_r8_unique.iterrows():
        sr_ex_ann = float(r['Sharpe'])
        vol = float(r['Ann_Vol'])
        sr_ex_m = sr_ex_ann / sq12
        sr_raw_ann = sr_ex_ann + rf_ann_mean / max(vol, 0.05)
        r8_reg_rows.append({
            'round_id': 8,
            'round_name': 'R8_consensus_burst_modes',
            'source_file': 'outputs/consensus_burst_mode_audit_20261104',
            'trial_name': str(r['Variant']),
            'in_canonical_878': True,
            'in_post_core3_397': True,
            'sr_excess_monthly': sr_ex_m,
            'sr_excess_ann': sr_ex_ann,
            'sr_raw_monthly': sr_raw_ann / sq12,
            'sr_raw_ann': sr_raw_ann,
        })
    reg_all = pd.concat([reg_df, pd.DataFrame(r8_reg_rows)], ignore_index=True)
    reg_all.to_csv(os.path.join(HERE, '06b_master_all_trials_sharpe_registry_r8.csv'), index=False)

    can_pool = reg_all[reg_all['in_canonical_878']]['sr_excess_monthly'].dropna().values
    n_cum_can = len(can_pool)
    n_cum_exh = len(reg_all)
    var_sr_can = float(np.var(can_pool, ddof=1))

    gamma_em = 0.5772156649
    sr0_can = float(np.sqrt(var_sr_can) * ((1.0 - gamma_em) * sst.norm.ppf(1.0 - 1.0 / n_cum_can) +
                                           gamma_em * sst.norm.ppf(1.0 - 1.0 / (n_cum_can * np.e))))

    def calc_dsr_p(sr_m, skew, kurt, T=213, sr0=sr0_can):
        denom = np.sqrt(max(1e-8, 1.0 - skew * sr_m + ((kurt - 1.0) / 4.0) * (sr_m ** 2)))
        z = (sr_m - sr0) * np.sqrt(T - 1.0) / denom
        return float(sst.norm.cdf(z))

    dsr_rows = []
    for _, r in df_r8_unique.iterrows():
        sr_ann = float(r['Sharpe'])
        sr_m = sr_ann / sq12
        # Approximate skew/kurt from control series (~0.62 skew, ~4.10 kurt)
        p_dsr = calc_dsr_p(sr_m, skew=0.60, kurt=4.10, T=213, sr0=sr0_can)
        dsr_rows.append({
            'Variant': r['Variant'],
            'Family': r['Family'],
            'CAGR_09_26': r['CAGR_09_26'],
            'Sharpe_Ann': sr_ann,
            'Sharpe_Monthly': sr_m,
            'Monthly_MaxDD': r['Monthly_MaxDD'],
            'Daily_MaxDD_5651ec2': r['Daily_MaxDD_5651ec2'],
            'N_Cumulative_Canonical': n_cum_can,
            'N_Cumulative_Exhaustive': n_cum_exh,
            'Pool_Monthly_SR_Std': float(np.sqrt(var_sr_can)),
            'Expected_Max_Monthly_SR0': sr0_can,
            'Expected_Max_Ann_SR0': sr0_can * sq12,
            'DSR_p_value': p_dsr,
        })
    df_dsr = pd.DataFrame(dsr_rows)
    df_dsr.to_csv(os.path.join(HERE, '06_multiple_testing_dsr.csv'), index=False)

    print(f'Cumulative Canonical Trials = {n_cum_can}, Expected Max Ann SR0 = {sr0_can*sq12:.3f}')
    print('\nAll CSV artifacts saved to:', HERE)


if __name__ == '__main__':
    main()
