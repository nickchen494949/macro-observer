#!/usr/bin/env python3
"""
run_clean_room_reconciliation_and_dsr.py
========================================
100% Standalone Clean-Room Verification, Discrepancy Reconciliation & Cumulative DSR Audit.
Does NOT import `run_qqq_spy_g1_audit.py`, `run_consensus_burst_audit.py`,
`run_shadow_industry_and_sector_audit.py`, or `run_four_experiments_abcd.py`.

Executes the user's 3 mandatory verification gates:
  1. Gate ① — Exact Accounting & Daily NAV Discrepancy Reconciliation:
       - Reconciles `Ctrl_1k` 2022 return (`+8.13%` in all CSVs vs `+3.4%` chat typo).
       - Reconciles `M3_4a` Round 1 (`-34.63%` Daily MaxDD, `60.86%` CAGR, `-22.41%` Monthly MaxDD)
         vs Round 3 `Ref_M3_4a` (`-35.19%` Daily MaxDD, `63.51%` CAGR, `-25.57%` Monthly MaxDD)
         and `ExpBC_2e` (`-38.02%` Daily MaxDD):
         * Identifies the exact code difference (`port_vol_est <= 0.55` stock-level volatility cap
           present in Round 1's `make_mode3_rule`, omitted in Round 3's `make_exp_abc_rule`).
         * Lists all 11 3-leg consensus months where `qqq_vol21 <= 0.30` but `port_vol_est > 0.55`.
         * Audits exact peak-to-trough dates for every Daily MaxDD number (`-34.63%`, `-35.19%`,
           `-36.17%`, `-38.02%`, `-38.66%`, `-40.19%`).
  2. Gate ② — Independent Clean-Room From-Scratch Rewrite of `ExpABC_3b`, `ExpABC_3f`, `ExpABC_3a`,
              `ExpAB_2a`, `M3_4a`, and `Ctrl_1k`:
       - Evaluates all strategies under BOTH:
           * `LowVol_Gate_V1` (Strict Round 1 Dual Gate: `qqq_vol21 <= 0.30 AND port_vol_est <= 0.55 AND not dm_panic`)
           * `LowVol_Gate_V2` (Round 3 Market-Only Gate: `qqq_vol21 <= 0.30 AND not dm_panic`)
       - Also fetches actual historical EOD prices (`adjOpen`, `adjClose`) from Tiingo for `NVDL`
         and `PLTU` (the actual 2x single-stock ETFs live during our post-2022 3-leg months) to
         compare real-world ETF NAV/price returns against our daily-reset formula simulation.
  3. Gate ③ — Cumulative Trial Registry & Deflated Sharpe Ratio (DSR) Update:
       - Incorporates EVERY trial across all rounds (prior 878 + Round 8.1 + Round 8.2 + Round 8.3
         = >1,030 canonical trials) and computes exact Bailey-Lopez de Prado (2014) DSR p-values
         using both each variant's exact sample skewness/kurtosis and the control benchmark Moments.
"""
import json
import os
import sys
import urllib.request
import urllib.error
import warnings
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
SSM_DIR = os.path.join(ROOT, 'research', 'sector_stock_momentum')
HERE = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, QQQ_DIR)
sys.path.insert(0, TECH_DIR)
sys.path.insert(0, SEP_SCRIPT_DIR)

import a2_engine as QE
import c2_engine as TE
from strategy_engine import parse_sep_pdfs

COST_BP = 0.0010          # 10 bp per side
BORROW_SPREAD_ANN = 0.0050  # 50 bp/yr over 3M T-bill

SOXX_STRICT_TICKERS = {
    'ADI', 'ALAB', 'ALTR', 'AMAT', 'AMD', 'ARM', 'ASML', 'ATML', 'AVGO', 'BRCM',
    'ENPH', 'FSLR', 'GFS', 'INTC', 'IPGP', 'KLAC', 'LLTC', 'LRCX', 'LSI', 'MCHP',
    'MPWR', 'MRVL', 'MU', 'MXIM', 'NSM', 'NVDA', 'NVLS', 'NXPI', 'ON', 'PMCS',
    'Q', 'QCOM', 'QRVO', 'SEDG', 'SUNEQ', 'SWKS', 'TER', 'TXN', 'WFR', 'XLNX',
}

HARDWARE_STORAGE_TICKERS = {
    'A', 'AAPL', 'ANET', 'APH', 'CIEN', 'COHR', 'CSCO', 'DELL', 'EMC', 'FFIV',
    'FLEX', 'FLIR', 'GLW', 'HPE', 'HPQ', 'HRS', 'IPGP', 'JAVA', 'JBL', 'JNPR',
    'KEYS', 'LITE', 'LOGI', 'LXK', 'MOLX', 'MSI', 'NTAP', 'QLGC', 'ROP', 'SMCI',
    'SNDK', 'STX', 'TDY', 'TEL', 'TLAB', 'TRMB', 'VIAV', 'WDC', 'XRX', 'ZBRA',
}


def classify_it_subind(tk):
    if tk in SOXX_STRICT_TICKERS:
        return 'Semiconductors_SOXX'
    elif tk in {'SNDK', 'WDC', 'STX', 'NTAP', 'EMC', 'QLGC'}:
        return 'Memory_Storage'
    elif tk in HARDWARE_STORAGE_TICKERS:
        return 'Hardware_Networking'
    else:
        return 'Software_Services'


# =============================================================================
# 1. Clean-Room Data Loader & Independent Sleeve Rebuilder
# =============================================================================
def clean_room_load_raw():
    # 1. 3M T-Bill monthly risk-free rate
    fn_rf = os.path.join(ROOT, 'data', 'fred', 'DGS3MO.json')
    d_rf = json.load(open(fn_rf))['values']
    s_rf = pd.Series({
        pd.Timestamp(dt): float(v) / 100.0
        for dt, v in d_rf if v is not None and v != '.'
    }).sort_index()
    rf_monthly = s_rf.resample('ME').last() / 12.0

    # 2. NYSE Trading Calendar
    cal = QE.calendar()
    cal_days = cal[(cal >= '2009-01-02') & (cal <= '2026-10-01')]

    # 3. Selection Panels & Daily Price Matrices
    qqq_panel = pd.read_parquet(os.path.join(SEL_DIR, 'qqq_selection_panel.parquet'))
    tech_panel = pd.read_parquet(os.path.join(SEL_DIR, 'tech_selection_panel.parquet'))
    spy_panel = pd.read_parquet(os.path.join(SPY_DIR, 'spy_selection_panel.parquet'))
    spy_daily_c = pd.read_parquet(os.path.join(SPY_DIR, 'spy_daily_close.parquet'))
    spy_daily_o = pd.read_parquet(os.path.join(SPY_DIR, 'spy_daily_open.parquet'))

    # 4. QQQ ETF daily close for strictly PIT volatility & panic indicator
    df_qqq = QE.series('tiingo_api', 'QQQ')
    if df_qqq is None:
        df_qqq = QE.series('yahoo', 'QQQ')
    c_qqq = df_qqq['adjclose'].dropna().sort_index()

    return rf_monthly, cal_days, qqq_panel, tech_panel, spy_panel, spy_daily_c, spy_daily_o, c_qqq


def clean_room_simulate_sleeve(df_panel, score_col, k_buy, k_keep, filter_non_it=False, top_non_it_sector_only=False):
    """
    Independent clean-room implementation of G1 buffered / hard-cutoff sleeve selection.
    At each formation date `t`:
      - Filters to valid candidates (`mom_12_1` notna and `hold_ret` notna)
      - Optionally restricts to non-IT sectors or the #1 non-IT sector by equal-weighted `mom_12_1`
      - Ranks descending by `score_col` (tie-break by `ticker` ascending)
      - Applies G1 hysteresis buffer: retains previously held tickers if their current rank <= `k_keep`,
        and fills remaining slots up to `k_buy` from the top of the current ranking.
    """
    prev_held = []
    out = {}

    for t_val, g in df_panel.groupby('t', sort=True):
        t_ts = pd.Timestamp(t_val)
        ym = (t_ts + pd.offsets.MonthBegin(1)).strftime('%Y-%m')

        d = g[g['mom_12_1'].notna() & g['hold_ret'].notna() & g[score_col].notna()].copy()
        if filter_non_it:
            d = d[d['sector'] != 'Information Technology'].copy()

        if top_non_it_sector_only:
            # Rank non-IT sectors by sector_ew_mom_12_1
            sec_moms = d.groupby('sector')['sector_ew_mom_12_1'].first().sort_values(ascending=False)
            top_sec = sec_moms.index[0]
            d_top = d[d['sector'] == top_sec].sort_values([score_col, 'ticker'], ascending=[False, True])
            sec_rk_map = {sec: idx + 1 for idx, sec in enumerate(sec_moms.index)}
            d['ex_it_sec_rk'] = d['sector'].map(sec_rk_map)
            d_rest = d[d['sector'] != top_sec].sort_values(['ex_it_sec_rk', score_col, 'ticker'], ascending=[True, False, True])
            d_sorted = pd.concat([d_top, d_rest], ignore_index=True)
        else:
            d_sorted = d.sort_values([score_col, 'ticker'], ascending=[False, True]).reset_index(drop=True)

        ranked_tks = list(d_sorted['ticker'].values)
        if k_keep > k_buy and prev_held:
            keep_set = set(ranked_tks[:k_keep])
            kept = [tk for tk in prev_held if tk in keep_set][:k_buy]
            for tk in ranked_tks:
                if len(kept) >= k_buy:
                    break
                if tk not in kept:
                    kept.append(tk)
            picks = kept
        else:
            picks = ranked_tks[:k_buy]

        prev_held = list(picks)
        w_dict = {tk: 1.0 / len(picks) for tk in picks}
        store_map = {
            r['ticker']: (r['store'], r['sym'])
            for _, r in d_sorted[d_sorted['ticker'].isin(set(picks))].iterrows()
        }
        out[ym] = {
            't_date': t_ts,
            'picks': list(picks),
            'weights_dict': w_dict,
            'store_map': store_map,
        }
    return out


def clean_room_build_signals_and_returns(formations, qqq_panel, tech_panel, spy_panel, c_qqq, rf_monthly, qqq_sl, xlk_sl, spy_sl):
    """
    Independent clean-room builder for:
      - Canonical FOMC SEP state (`sep_on`)
      - Market vol & panic gates (`qqq_vol21`, `dm_panic`)
      - Base 3S_G1_1k portfolio formation volatility (`port_vol_est`)
      - Stock-level holding returns (`ret_map`) and `vol_12_1` (`vol_map`)
      - Shadow Industry & Sector Confirmers (`soxx_top1`, `subind_grp1`, `conf2`)
    """
    # 1. Canonical FOMC SEP events
    sep_raw = parse_sep_pdfs(os.path.join(ROOT, 'data', 'fomc_sep'))
    sep_events = []
    sep_in = True
    for i in range(1, len(sep_raw)):
        c, p = sep_raw[i], sep_raw[i - 1]
        ty = c['target_year']
        c_pce, c_rate = c['pce_by_year'].get(ty), c['rate_by_year'].get(ty)
        p_pce, p_rate = p['pce_by_year'].get(ty), p['rate_by_year'].get(ty)
        if c_pce is None:
            continue
        has_both = all(pd.notna(x) for x in [c_pce, c_rate, p_pce, p_rate])
        if not has_both:
            continue
        is_exit = (c_rate > p_rate) and (c_pce > 2.0) and (c_pce > p_pce)
        reenter = (c_rate <= p_rate)
        if sep_in and is_exit:
            sep_in = False
            sep_events.append((pd.Timestamp(c['date']), False))
        elif (not sep_in) and reenter:
            sep_in = True
            sep_events.append((pd.Timestamp(c['date']), True))

    # 2. Stock return & vol maps across panels
    ret_map = {}
    vol_map = {}
    meta_all = {}
    for utag, pnl in [('qqq', qqq_panel), ('xlk', tech_panel), ('spy', spy_panel)]:
        for t_val, g in pnl.groupby('t', sort=True):
            ym = (pd.Timestamp(t_val) + pd.offsets.MonthBegin(1)).strftime('%Y-%m')
            for _, r in g[g['hold_ret'].notna()].iterrows():
                tk = r['ticker']
                if (ym, tk) not in ret_map:
                    ret_map[(ym, tk)] = float(r['hold_ret'])
                if (ym, tk) not in vol_map and pd.notna(r.get('vol_12_1')):
                    vol_map[(ym, tk)] = float(r['vol_12_1'])
                if (ym, tk) not in meta_all:
                    meta_all[(ym, tk)] = (utag, r['store'], r['sym'])

    # 3. Shadow Sub-Industry & Sector Confirmers at each formation t
    cols_c = ['t', 'ticker', 'mom_12_1', 'sharpe_mom_12_1', 'hold_ret']
    comb_it = pd.concat([tech_panel[cols_c], qqq_panel[cols_c]], ignore_index=True).drop_duplicates(subset=['t', 'ticker'], keep='first')
    comb_it['subind'] = comb_it['ticker'].apply(classify_it_subind)

    soxx_top1 = {}
    subind_grp_rk = {}
    stock_subind = {}
    for t_val, g in comb_it.groupby('t', sort=True):
        ym = (pd.Timestamp(t_val) + pd.offsets.MonthBegin(1)).strftime('%Y-%m')
        gv = g[g['mom_12_1'].notna() & g['hold_ret'].notna()]
        g_soxx = gv[gv['ticker'].isin(SOXX_STRICT_TICKERS)].sort_values(['mom_12_1', 'ticker'], ascending=[False, True])
        if not g_soxx.empty:
            soxx_top1[ym] = g_soxx['ticker'].iloc[0]
        grp_m = {}
        for sname, gsub in gv.groupby('subind'):
            grp_m[sname] = float(gsub['mom_12_1'].mean())
            for tk in gsub['ticker']:
                stock_subind[(ym, tk)] = sname
        for rk_i, (sname, _) in enumerate(sorted(grp_m.items(), key=lambda x: -x[1])):
            subind_grp_rk[(ym, sname)] = rk_i + 1

    sec_rk_raw = {}
    sec_rk_sh = {}
    for t_val, g in spy_panel.groupby('t', sort=True):
        ym = (pd.Timestamp(t_val) + pd.offsets.MonthBegin(1)).strftime('%Y-%m')
        gv = g[g['mom_12_1'].notna() & g['hold_ret'].notna()]
        for _, gsec in gv.groupby('sector'):
            sr_r = gsec.sort_values(['mom_12_1', 'ticker'], ascending=[False, True]).reset_index(drop=True)
            sr_s = gsec.sort_values(['sharpe_mom_12_1', 'ticker'], ascending=[False, True]).reset_index(drop=True)
            for idx, tk in enumerate(sr_r['ticker']):
                sec_rk_raw[(ym, tk)] = idx + 1
            for idx, tk in enumerate(sr_s['ticker']):
                sec_rk_sh[(ym, tk)] = idx + 1

    # 4. Monthly regime & consensus table
    r_qqq_d = c_qqq.pct_change().dropna()
    month_info = {}
    for t in sorted(formations):
        t_ts = pd.Timestamp(t)
        ym = (t_ts + pd.offsets.MonthBegin(1)).strftime('%Y-%m')
        m_dt = t_ts + pd.offsets.MonthEnd(1)

        sep_on = True
        for ev_dt, st in sep_events:
            if ev_dt <= t_ts:
                sep_on = st

        cq_t = c_qqq.loc[:t_ts]
        rq_t = r_qqq_d.loc[:t_ts]
        qqq_vol21 = float(rq_t.tail(21).std(ddof=1) * np.sqrt(252.0)) if len(rq_t) >= 21 else 0.20
        qqq_dd252 = float(cq_t.iloc[-1] / cq_t.tail(252).max() - 1.0) if len(cq_t) >= 252 else 0.0
        qqq_ret12m = float(cq_t.iloc[-1] / cq_t.iloc[-252] - 1.0) if len(cq_t) >= 252 else 0.0
        dm_panic = bool((qqq_ret12m < 0.0 or qqq_dd252 < -0.15) and qqq_vol21 > 0.28)
        qqq_sma200_on = bool(cq_t.iloc[-1] >= cq_t.tail(200).mean()) if len(cq_t) >= 200 else True

        rf_m = float(rf_monthly.reindex([m_dt], method='ffill').iloc[0])
        borrow_m = rf_m + BORROW_SPREAD_ANN / 12.0

        # Base 3S_G1_1k weights and portfolio formation volatility `port_vol_est`
        w_base = {}
        for tk, v in qqq_sl[ym]['weights_dict'].items():
            w_base[tk] = w_base.get(tk, 0.0) + 0.50 * v
        for tk, v in xlk_sl[ym]['weights_dict'].items():
            w_base[tk] = w_base.get(tk, 0.0) + 0.25 * v
        for tk, v in spy_sl[ym]['weights_dict'].items():
            w_base[tk] = w_base.get(tk, 0.0) + 0.25 * v

        port_vol_est = float(sum(w_tk * vol_map.get((ym, tk), 0.35) for tk, w_tk in w_base.items()))

        q_set = set(qqq_sl[ym]['picks'])
        t_pick = xlk_sl[ym]['picks'][0]
        s_pick = spy_sl[ym]['picks'][0]
        t_in_q = t_pick in q_set
        s_in_q = s_pick in q_set
        t_eq_s = (t_pick == s_pick)

        is_3leg = t_eq_s and t_in_q
        is_2leg = (not is_3leg) and (t_eq_s or t_in_q or s_in_q)
        ov_tk = t_pick if (t_eq_s or t_in_q) else (s_pick if s_in_q else '')
        other_q = [x for x in q_set if x != ov_tk]
        other_q_tk = other_q[0] if len(other_q) == 1 else None

        is_soxx1 = (ov_tk != '') and (soxx_top1.get(ym, '') == ov_tk)
        sname = stock_subind.get((ym, ov_tk), 'Non_IT')
        is_subind_grp1 = (subind_grp_rk.get((ym, sname), 99) == 1)

        sr_r = sec_rk_raw.get((ym, ov_tk), 99)
        sr_s = sec_rk_sh.get((ym, ov_tk), 99)
        is_conf2 = False
        if is_2leg and ov_tk != '':
            if (sr_r == 1 and sr_s == 1) or (s_in_q and not t_in_q and sr_r == 1) or (t_in_q and not s_in_q and is_soxx1):
                is_conf2 = True

        # Low-vol gates:
        # Gate V1 (Round 1 M3_4a exact gate): qqq_vol21 <= 0.30 AND port_vol_est <= 0.55 AND not dm_panic
        # Gate V2 (Round 3 gate): qqq_vol21 <= 0.30 AND not dm_panic
        lowvol_v1 = bool(sep_on and (qqq_vol21 <= 0.30) and (port_vol_est <= 0.55) and (not dm_panic))
        lowvol_v2 = bool(sep_on and (qqq_vol21 <= 0.30) and (not dm_panic))

        month_info[ym] = {
            't_date': t_ts,
            'sep_on': sep_on,
            'qqq_sma200_on': qqq_sma200_on,
            'qqq_vol21': qqq_vol21,
            'port_vol_est': port_vol_est,
            'dm_panic': dm_panic,
            'rf_monthly': rf_m,
            'borrow_monthly': borrow_m,
            'w_base': w_base,
            'is_3leg': is_3leg,
            'is_2leg': is_2leg,
            'ov_tk': ov_tk,
            'other_q_tk': other_q_tk,
            'is_soxx1': is_soxx1,
            'is_subind_grp1': is_subind_grp1,
            'is_conf2': is_conf2,
            'lowvol_v1': lowvol_v1,
            'lowvol_v2': lowvol_v2,
        }

    return ret_map, vol_map, meta_all, month_info


# =============================================================================
# 2. Clean-Room Daily Stock Price Lookup & Portfolio Simulator
# =============================================================================
_CLEAN_DAILY_CACHE = {}


def clean_room_get_daily_df(utag, tk, t_form, store, sym, spy_daily_c, spy_daily_o):
    t_form = pd.Timestamp(t_form)
    if utag == 'spy' and tk in spy_daily_c.columns:
        ckey = ('spy', tk)
        if ckey not in _CLEAN_DAILY_CACHE:
            c_s = spy_daily_c[tk].dropna()
            o_raw = spy_daily_o[tk].reindex(c_s.index)
            o_s = o_raw.where(o_raw.notna() & (o_raw > 0), c_s)
            _CLEAN_DAILY_CACHE[ckey] = pd.DataFrame({'adjclose': c_s, 'adjopen_clean': o_s}).sort_index()
        return _CLEAN_DAILY_CACHE[ckey]

    if utag == 'qqq' or ':' in str(store):
        st_base = str(store).split(':')[0] if ':' in str(store) else store
        ckey = ('qqq', st_base, sym)
        if ckey not in _CLEAN_DAILY_CACHE:
            df = QE.series(st_base, sym)
            if df is None:
                df = QE.series('yahoo', tk)
            df = df.sort_index()
            df = df[~df.index.duplicated(keep='last')].copy()
            df['adjopen_clean'] = df['adjopen'].where(df['adjopen'].notna() & (df['adjopen'] > 0), df['adjclose'])
            _CLEAN_DAILY_CACHE[ckey] = df
        return _CLEAN_DAILY_CACHE[ckey]

    segs = TE.segments(tk)
    d0 = QE.first_td_after(t_form, 1)
    d1 = QE.first_td_after(t_form + pd.offsets.MonthEnd(1), 1)
    order = [x for x in segs if d0 in x[0].index and d1 in x[0].index] + \
            [x for x in segs if d0 in x[0].index and d1 not in x[0].index]
    if order:
        df_raw, src, sym_seg, _ = order[0]
        ckey = ('xlk', tk, src, sym_seg, str(df_raw.index.min().date()))
        if ckey not in _CLEAN_DAILY_CACHE:
            df = pd.DataFrame({
                'adjclose': df_raw['adjclose'],
                'adjopen': df_raw['adj_open'] if 'adj_open' in df_raw.columns else np.nan,
            }, index=df_raw.index).sort_index()
            df = df[~df.index.duplicated(keep='last')]
            df['adjopen_clean'] = df['adjopen'].where(df['adjopen'].notna() & (df['adjopen'] > 0), df['adjclose'])
            _CLEAN_DAILY_CACHE[ckey] = df
        return _CLEAN_DAILY_CACHE[ckey]

    c_s = spy_daily_c[tk].dropna()
    o_s = spy_daily_o[tk].reindex(c_s.index).fillna(c_s)
    return pd.DataFrame({'adjclose': c_s, 'adjopen_clean': o_s}).sort_index()


def clean_room_simulate_strategy(
    common_yms, qqq_sl, xlk_sl, spy_sl, extra_sl, month_info, ret_map,
    cal_days, spy_daily_c, spy_daily_o, rule_fn
):
    prev_drifted_w = {}
    rows = []

    for ym in common_yms:
        mi = month_info[ym]
        t_date = mi['t_date']
        w_stocks, w_cash, r_cash, w_borrow, r_borrow = rule_fn(
            ym, qqq_sl[ym], xlk_sl[ym], spy_sl[ym], extra_sl, mi
        )

        # Build metadata map in exact canonical order ('qqq', 'xlk', 'spy', extras)
        meta_comb = {}
        for utag, sl_d in [('qqq', qqq_sl[ym]), ('xlk', xlk_sl[ym]), ('spy', spy_sl[ym])]:
            for tk, (st, sym) in sl_d['store_map'].items():
                if tk not in meta_comb:
                    meta_comb[tk] = (utag, st, sym)
        for ex_name, ex_d in extra_sl.items():
            for tk, (st, sym) in ex_d[ym]['store_map'].items():
                if tk not in meta_comb:
                    meta_comb[tk] = ('spy', st, sym)

        gross_stocks = sum(w_tk * ret_map[(ym, tk)] for tk, w_tk in w_stocks.items() if w_tk > 0)
        gross_total = gross_stocks + w_cash * r_cash - w_borrow * r_borrow

        if not prev_drifted_w:
            to = float(sum(abs(v) for v in w_stocks.values()))
        else:
            all_k = set(w_stocks.keys()) | set(prev_drifted_w.keys())
            to = float(sum(abs(w_stocks.get(k, 0.0) - prev_drifted_w.get(k, 0.0)) for k in all_k))

        net_total = (1.0 + gross_total) * ((1.0 - COST_BP) ** to) - 1.0 if to > 0 else gross_total

        end_eq = 1.0 + gross_total
        if end_eq > 0:
            prev_drifted_w = {
                tk: w_tk * (1.0 + ret_map[(ym, tk)]) / end_eq
                for tk, w_tk in w_stocks.items() if w_tk > 0
            }
        else:
            prev_drifted_w = {}

        rows.append({
            'ym': ym,
            't_date': t_date,
            'gross': gross_total,
            'net': net_total,
            'turnover': to,
            'long_exp': float(sum(w_stocks.values())),
            'w_cash': w_cash,
            'w_borrow': w_borrow,
            'holdings_dict': dict(w_stocks),
            'meta_map': meta_comb,
            'net_financing_drag': w_borrow * r_borrow - w_cash * r_cash,
        })

    L_port = pd.DataFrame(rows).set_index('ym')

    # Compute exact daily NAV paths & peak/trough drawdown dates
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
        fin_drag_m = float(row['net_financing_drag'])

        s_map = {}
        p_e_map = {}
        for tk in h_dict:
            u_tk, st_tk, sym_tk = meta_map.get(tk, ('spy', 'yahoo', tk))
            df_s = clean_room_get_daily_df(u_tk, tk, t_form, st_tk, sym_tk, spy_daily_c, spy_daily_o)
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

    dd_series_c56 = s_c56 / s_c56.cummax() - 1.0
    trough_dt = dd_series_c56.idxmin()
    peak_dt = s_c56.loc[:trough_dt].idxmax()
    dd_c56 = float(dd_series_c56.min())
    dd_o2c = float((s_o2c / s_o2c.cummax() - 1.0).min())

    return L_port, dd_c56, dd_o2c, peak_dt.strftime('%Y-%m-%d'), trough_dt.strftime('%Y-%m-%d')


def clean_room_summarize(name, family, L_port, rf_monthly, dd_c56, dd_o2c, peak_dt, trough_dt, ref_ctrl_r):
    r_m = L_port['net'].dropna()
    n = len(r_m)
    idx_dt = pd.to_datetime(r_m.index + '-01') + pd.offsets.MonthEnd(1)
    r_s = pd.Series(r_m.values, index=idx_dt)

    cagr = float((np.prod(1.0 + r_s.values)) ** (12.0 / n) - 1.0)
    vol = float(r_s.std(ddof=1) * np.sqrt(12.0))
    rf_al = rf_monthly.reindex(r_s.index).ffill().fillna(0.0)
    ex = r_s - rf_al
    sharpe = float(ex.mean() / r_s.std(ddof=1) * np.sqrt(12.0))
    neg = r_s[r_s < 0]
    sortino = float(ex.mean() * 12.0 / (neg.std(ddof=1) * np.sqrt(12.0))) if len(neg) > 1 else np.nan

    w = np.concatenate([[1.0], np.cumprod(1.0 + r_s.values)])
    mdd = float((w / np.maximum.accumulate(w) - 1.0).min())
    calmar_daily = cagr / abs(dd_c56) if dd_c56 < 0 else np.nan

    def sub_cagr(a, b):
        sub = r_s.loc[a:b]
        return float((np.prod(1.0 + sub.values)) ** (12.0 / len(sub)) - 1.0)

    ret_2022 = float(np.prod(1.0 + r_s.loc['2022-01-01':'2022-12-31'].values) - 1.0)
    r_ex22 = r_s[(r_s.index < '2022-01-01') | (r_s.index > '2022-12-31')]
    cagr_ex22 = float((np.prod(1.0 + r_ex22.values)) ** (12.0 / len(r_ex22)) - 1.0)

    yr_rets = r_s.groupby(r_s.index.year).apply(lambda x: np.prod(1.0 + x.values) - 1.0)
    pos_years = int((yr_rets > 0).sum())
    worst_yr = float(yr_rets.min())

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

    # Sample skewness and Pearson kurtosis (3.0 = normal) of monthly excess returns for DSR
    skew_ex = float(sst.skew(ex.values, bias=False))
    kurt_ex = float(sst.kurtosis(ex.values, fisher=False, bias=False))

    return {
        'Variant': name,
        'Family': family,
        'CAGR_09_26': cagr,
        'Sharpe': sharpe,
        'Sortino': sortino,
        'Ann_Vol': vol,
        'Monthly_MaxDD': mdd,
        'Daily_MaxDD_5651ec2': dd_c56,
        'Daily_MaxDD_O2C': dd_o2c,
        'Daily_DD_Peak_Date': peak_dt,
        'Daily_DD_Trough_Date': trough_dt,
        'Calmar_Daily': calmar_daily,
        'CAGR_2009_2018': sub_cagr('2009-01-31', '2018-12-31'),
        'CAGR_2019_2026': sub_cagr('2019-01-31', '2026-09-30'),
        'CAGR_Ex2022': cagr_ex22,
        'Ret_2022': ret_2022,
        'CAGR_2023_2026': sub_cagr('2023-01-31', '2026-09-30'),
        'Pos_Years_18': pos_years,
        'Worst_Cal_Year': worst_yr,
        'Avg_Gross_Exp': float(L_port['long_exp'].mean()),
        'Max_Gross_Exp': float(L_port['long_exp'].max()),
        'Pct_Mo_Levered': float((L_port['long_exp'] > 1.001).mean()),
        'Pct_Mo_DeRisked': float((L_port['long_exp'] < 0.999).mean()),
        'Avg_Monthly_TO': float(L_port['turnover'].mean()),
        'NW_t_vs_Ctrl': nw_t,
        'Sample_Skew': skew_ex,
        'Sample_Kurt_Pearson': kurt_ex,
    }


# =============================================================================
# 3. Actual Tiingo 2x ETF Price Verification (NVDL & PLTU)
# =============================================================================
def verify_actual_tiingo_2x_etfs(common_yms, month_info):
    """
    Fetches actual market EOD `adjOpen` and `adjClose` for `NVDL` (launched 2022-12-13)
    and `PLTU` (launched 2024-12-11) from Tiingo API and compares actual T+1 Open -> T'+1 Open
    market returns against our simulated daily-reset 2x ETF returns in `13b_expD_single_stock_2x_etf_monthly_audit.csv`.
    """
    env_p = os.path.join(SSM_DIR, '.env')
    token = None
    if os.path.exists(env_p):
        for line in open(env_p):
            if line.startswith('TIINGO_API_KEY='):
                token = line.strip().split('=', 1)[1]
                break

    cache_dir = os.path.join(HERE, 'actual_2x_etf_tiingo')
    os.makedirs(cache_dir, exist_ok=True)

    etf_map = {'NVDA': 'NVDL', 'PLTR': 'PLTU'}
    etf_dfs = {}
    for stk, etf_sym in etf_map.items():
        fp = os.path.join(cache_dir, f'{etf_sym}.json')
        if not os.path.exists(fp) and token:
            url = (f'https://api.tiingo.com/tiingo/daily/{etf_sym.lower()}/prices'
                   f'?startDate=2022-01-01&format=json&token={token}')
            req = urllib.request.Request(url, headers={'Content-Type': 'application/json', 'User-Agent': 'macro-observer'})
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    data = json.loads(r.read())
                json.dump(data, open(fp, 'w'))
            except Exception as e:
                print(f'  [Warn] Tiingo fetch for {etf_sym} failed: {e}')
        if os.path.exists(fp):
            data = json.load(open(fp))
            df = pd.DataFrame(data)
            df['date'] = pd.to_datetime(df['date']).dt.tz_localize(None)
            df = df.set_index('date').sort_index()
            etf_dfs[etf_sym] = df

    df_13b = pd.read_csv(os.path.join(HERE, '13b_expD_single_stock_2x_etf_monthly_audit.csv')).set_index('ym')
    rows_cmp = []
    for i, ym in enumerate(common_yms):
        if ym not in df_13b.index:
            continue
        r13 = df_13b.loc[ym]
        if not bool(r13['pit_2x_etf_available']):
            continue
        stk = r13['ticker']
        etf_sym = etf_map.get(stk)
        if etf_sym not in etf_dfs:
            continue
        df_e = etf_dfs[etf_sym]
        t_date = pd.Timestamp(r13['t_date'])
        next_t_date = month_info[common_yms[i + 1]]['t_date'] if (i + 1 < len(common_yms)) else (t_date + pd.offsets.MonthEnd(1))
        e_d = QE.first_td_after(t_date, 1)
        x_d = QE.first_td_after(next_t_date, 1)

        sub = df_e.loc[(df_e.index >= e_d) & (df_e.index <= x_d)]
        if len(sub) >= 2:
            p_in = float(sub['adjOpen'].iloc[0]) if pd.notna(sub['adjOpen'].iloc[0]) and sub['adjOpen'].iloc[0] > 0 else float(sub['adjClose'].iloc[0])
            p_out = float(sub['adjOpen'].iloc[-1]) if pd.notna(sub['adjOpen'].iloc[-1]) and sub['adjOpen'].iloc[-1] > 0 else float(sub['adjClose'].iloc[-1])
            actual_etf_ret = p_out / p_in - 1.0
        else:
            actual_etf_ret = np.nan

        sim_ret = float(r13['true_daily_reset_2x_etf_ret'])
        rows_cmp.append({
            'ym': ym,
            'stock': stk,
            'etf_ticker': etf_sym,
            'entry_date': e_d.strftime('%Y-%m-%d'),
            'exit_date': x_d.strftime('%Y-%m-%d'),
            'subind_group_is_1': bool(r13['subind_group_is_1']),
            'stock_1x_ret': float(r13['stock_1x_ret']),
            'naive_2x_ret_wrong': float(r13['naive_2x_ret_wrong']),
            'simulated_daily_reset_2x_ret': sim_ret,
            'actual_market_etf_ret_tiingo': actual_etf_ret,
            'diff_actual_minus_sim': actual_etf_ret - sim_ret if pd.notna(actual_etf_ret) else np.nan,
        })
    return pd.DataFrame(rows_cmp)


def main():
    print('=' * 110)
    print('CLEAN-ROOM RECONCILIATION, FROM-SCRATCH REWRITE OF ExpABC_3b & CUMULATIVE DSR AUDIT')
    print('=' * 110)

    rf_monthly, cal_days, qqq_panel, tech_panel, spy_panel, spy_daily_c, spy_daily_o, c_qqq = clean_room_load_raw()
    formations = sorted(qqq_panel['t'].unique())

    # 1. Independently simulate constituent sleeves
    qqq_sl = clean_room_simulate_sleeve(qqq_panel, 'sharpe_mom_12_1', k_buy=2, k_keep=5)
    xlk_sl = clean_room_simulate_sleeve(tech_panel, 'mom_12_1', k_buy=1, k_keep=1)
    spy_sl = clean_room_simulate_sleeve(spy_panel, 'mom_12_1', k_buy=1, k_keep=3)
    exit_raw_sl = clean_room_simulate_sleeve(spy_panel, 'mom_12_1', k_buy=1, k_keep=3, filter_non_it=True)
    exit_secrot_sl = clean_room_simulate_sleeve(spy_panel, 'mom_12_1', k_buy=1, k_keep=3, filter_non_it=True, top_non_it_sector_only=True)
    extra_sl = {'exit_raw': exit_raw_sl, 'exit_secrot': exit_secrot_sl}

    common_yms = sorted(list(qqq_sl.keys()))
    ret_map, vol_map, meta_all, month_info = clean_room_build_signals_and_returns(
        formations, qqq_panel, tech_panel, spy_panel, c_qqq, rf_monthly, qqq_sl, xlk_sl, spy_sl
    )

    # =========================================================================
    # GATE ①: RECONCILE THE 11 MONTHS WHERE `lowvol_v1` != `lowvol_v2`
    # =========================================================================
    print('\n[Gate ①] Auditing the exact difference between Round 1 (M3_4a) and Round 3 (Ref_M3_4a):')
    diff_gate_rows = []
    for ym in common_yms:
        mi = month_info[ym]
        if mi['is_3leg'] and (mi['lowvol_v1'] != mi['lowvol_v2']):
            tk_c = mi['ov_tk']
            tk_q2 = mi['other_q_tk']
            r_c = ret_map[(ym, tk_c)]
            r_q2 = ret_map[(ym, tk_q2)] if tk_q2 else 0.0
            r_75_25 = 0.75 * r_c + 0.25 * r_q2
            diff_gate_rows.append({
                'ym': ym,
                'consensus_ticker': tk_c,
                'qqq_2nd_ticker': tk_q2,
                'subind_group_is_1': mi['is_subind_grp1'],
                'sep_on': mi['sep_on'],
                'qqq_vol21': mi['qqq_vol21'],
                'port_vol_est': mi['port_vol_est'],
                'gate_v1_with_portvol55': mi['lowvol_v1'],
                'gate_v2_no_portvol55': mi['lowvol_v2'],
                'consensus_stock_1x_ret': r_c,
                'qqq_2nd_stock_1x_ret': r_q2,
                'blend_75_25_1x_ret': r_75_25,
            })
    df_gate_diff = pd.DataFrame(diff_gate_rows)
    df_gate_diff.to_csv(os.path.join(HERE, '14a_reconciliation_11_portvol_months.csv'), index=False)
    print(f'  Found {len(df_gate_diff)} 3-Leg Consensus months where SEP=ON & qqq_vol21<=30%, '
          f'but port_vol_est > 55% (Round 1 blocked leverage; Round 3 allowed leverage):')
    for _, r in df_gate_diff.iterrows():
        print(f"    {r['ym']} | Pick={r['consensus_ticker']:<5} (QQQ#2={r['qqq_2nd_ticker']:<5}) | Grp#1={str(r['subind_group_is_1']):<5} | "
              f"QQQ_Vol21={r['qqq_vol21']*100:5.1f}% | Port_Vol12m={r['port_vol_est']*100:5.1f}% (>55%) | "
              f"75/25_1x_Ret={r['blend_75_25_1x_ret']*100:+6.2f}% | Cons_1x_Ret={r['consensus_stock_1x_ret']*100:+6.2f}%")

    # =========================================================================
    # GATE ②: CLEAN-ROOM REWRITE OF ALL KEY STRATEGIES UNDER BOTH V1 & V2 GATES
    # =========================================================================
    print('\n[Gate ②] Running Standalone Clean-Room Backtests Across Both Gate V1 (port_vol<=55%) and Gate V2...')

    def make_clean_rule(
        sep_off_mode='none',       # 'none', 'sgov50', 'sgov25_exit_raw25', 'sgov25_exit_secrot25'
        conc_mode='none',          # 'none', 'grp1_100', 'all3_100', 'soxx_100'
        l_conf2=1.0,
        l_ord3=1.0,
        l_grp3=1.0,
        vol_gate_version='v1',     # 'v1' (qqq_vol21<=0.30 & port_vol_est<=0.55 & not dm_panic) or 'v2' (qqq_vol21<=0.30 & not dm_panic)
    ):
        def _rule(ym, q_d, x_d, s_d, ex_d, mi):
            if sep_off_mode != 'none' and (not mi['sep_on']):
                w = {}
                for tk, v in x_d['weights_dict'].items():
                    w[tk] = w.get(tk, 0.0) + 0.25 * v
                for tk, v in s_d['weights_dict'].items():
                    w[tk] = w.get(tk, 0.0) + 0.25 * v
                if sep_off_mode == 'sgov50':
                    return w, 0.50, mi['rf_monthly'], 0.0, 0.0
                elif sep_off_mode == 'sgov25_exit_raw25':
                    for tk, v in ex_d['exit_raw'][ym]['weights_dict'].items():
                        w[tk] = w.get(tk, 0.0) + 0.25 * v
                    return w, 0.25, mi['rf_monthly'], 0.0, 0.0
                elif sep_off_mode == 'sgov25_exit_secrot25':
                    for tk, v in ex_d['exit_secrot'][ym]['weights_dict'].items():
                        w[tk] = w.get(tk, 0.0) + 0.25 * v
                    return w, 0.25, mi['rf_monthly'], 0.0, 0.0

            w_base = dict(mi['w_base'])
            if mi['is_3leg']:
                if conc_mode == 'grp1_100' and mi['is_subind_grp1']:
                    w_base = {mi['ov_tk']: 1.00}
                elif conc_mode == 'all3_100':
                    w_base = {mi['ov_tk']: 1.00}
                elif conc_mode == 'soxx_100' and mi['is_soxx1']:
                    w_base = {mi['ov_tk']: 1.00}

            low_vol_ok = mi['lowvol_v1'] if vol_gate_version == 'v1' else mi['lowvol_v2']
            L = 1.0
            if low_vol_ok:
                if mi['is_3leg']:
                    L = l_grp3 if mi['is_subind_grp1'] else l_ord3
                elif mi['is_2leg'] and mi['is_conf2']:
                    L = l_conf2

            w_stocks = {tk: v * L for tk, v in w_base.items()}
            w_borrow = max(0.0, L - 1.0)
            r_borrow = mi['borrow_monthly'] if w_borrow > 0 else 0.0
            return w_stocks, 0.0, 0.0, w_borrow, r_borrow
        return _rule

    # Run Control first
    L_ctrl, d56_ctrl, do2c_ctrl, pk_ctrl, tr_ctrl = clean_room_simulate_strategy(
        common_yms, qqq_sl, xlk_sl, spy_sl, extra_sl, month_info, ret_map,
        cal_days, spy_daily_c, spy_daily_o, make_clean_rule()
    )
    ref_ctrl_r = L_ctrl['net']

    clean_configs = [
        # 1. Base Unlevered Controls & Unlevered A/B Variants (Identical under V1 & V2 since L=1.0x always)
        ('CR_00_Ctrl_3S_G1_1k (50/25/25 Always, 1.0x)', '1_Unlevered_Base',
         'none', 'none', 1.0, 1.0, 1.0, 'v1'),
        ('CR_ExpA_1a (1.0x: 3Leg+Grp#1 -> 100% Stock)', '1_Unlevered_ExpA',
         'none', 'grp1_100', 1.0, 1.0, 1.0, 'v1'),
        ('CR_ExpA_1c (1.0x: 3Leg+SOXX#1 -> 100% Stock)', '1_Unlevered_ExpA',
         'none', 'soxx_100', 1.0, 1.0, 1.0, 'v1'),
        ('CR_ExpB_1a_M2_1b (1.0x: SEP_OFF -> 50% SGOV)', '1_Unlevered_ExpB',
         'sgov50', 'none', 1.0, 1.0, 1.0, 'v1'),
        ('CR_ExpB_1b (1.0x: SEP_OFF -> 25% SGOV + 25% ExIT_Raw[<=3])', '1_Unlevered_ExpB',
         'sgov25_exit_raw25', 'none', 1.0, 1.0, 1.0, 'v1'),
        ('CR_ExpB_1c (1.0x: SEP_OFF -> 25% SGOV + 25% ExIT_BestSec[<=3])', '1_Unlevered_ExpB',
         'sgov25_exit_secrot25', 'none', 1.0, 1.0, 1.0, 'v1'),
        ('CR_ExpAB_2a (1.0x: SEP_OFF ExIT_Raw + 3Leg_Grp#1->100%)', '1_Unlevered_ExpAB',
         'sgov25_exit_raw25', 'grp1_100', 1.0, 1.0, 1.0, 'v1'),
        ('CR_ExpAB_BestSec (1.0x: SEP_OFF ExIT_BestSec + 3Leg_Grp#1->100%)', '1_Unlevered_ExpAB',
         'sgov25_exit_secrot25', 'grp1_100', 1.0, 1.0, 1.0, 'v1'),
        ('CR_ExpAB_SGOV50 (1.0x: SEP_OFF 50%SGOV + 3Leg_Grp#1->100%)', '1_Unlevered_ExpAB',
         'sgov50', 'grp1_100', 1.0, 1.0, 1.0, 'v1'),

        # 2. M3_4a Reconciliation Pair (V1 = Round 1 Exact vs V2 = Round 3 Ref_M3_4a)
        ('CR_M3_4a_V1 [Round 1 Exact: qqq_vol21<=30% & port_vol<=55%] (All 3Leg=1.50x, 50%SGOV)', '2_M3_4a_Reconcile',
         'sgov50', 'none', 1.0, 1.50, 1.50, 'v1'),
        ('CR_M3_4a_V2 [Round 3 Ref_M3_4a: qqq_vol21<=30% only] (All 3Leg=1.50x, 50%SGOV)', '2_M3_4a_Reconcile',
         'sgov50', 'none', 1.0, 1.50, 1.50, 'v2'),

        # 3. ExpABC Family Under Gate V1 (Strict Dual Low-Vol Gate: qqq_vol21<=30% & port_vol<=55%)
        ('CR_ExpBC_2e_V1 [Strict PortVol<=55%] (50%SGOV | Conf2=1.25x, Ord3=1.50x, Grp#1=1.75x, 75/25)', '3_ExpABC_GateV1_Strict',
         'sgov50', 'none', 1.25, 1.50, 1.75, 'v1'),
        ('CR_ExpABC_3a_V1 [Strict PortVol<=55%] (ExIT_Raw | Conf2=1.25x, Ord3=1.50x, Grp#1=1.50x [100%])', '3_ExpABC_GateV1_Strict',
         'sgov25_exit_raw25', 'grp1_100', 1.25, 1.50, 1.50, 'v1'),
        ('CR_ExpABC_3b_V1 [Strict PortVol<=55%] (ExIT_Raw | Conf2=1.25x, Ord3=1.50x, Grp#1=1.75x [100%])', '3_ExpABC_GateV1_Strict',
         'sgov25_exit_raw25', 'grp1_100', 1.25, 1.50, 1.75, 'v1'),
        ('CR_ExpABC_3b_BestSec_V1 [Strict PortVol<=55%] (ExIT_BestSec | Conf2=1.25x, Ord3=1.50x, Grp#1=1.75x [100%])', '3_ExpABC_GateV1_Strict',
         'sgov25_exit_secrot25', 'grp1_100', 1.25, 1.50, 1.75, 'v1'),
        ('CR_ExpABC_3f_SGOV50_V1 [Strict PortVol<=55%] (50%SGOV | Conf2=1.25x, Ord3=1.50x, Grp#1=1.75x [100%])', '3_ExpABC_GateV1_Strict',
         'sgov50', 'grp1_100', 1.25, 1.50, 1.75, 'v1'),
        ('CR_ExpABC_3c_V1 [Strict PortVol<=55%] (ExIT_Raw | Conf2=1.25x, Ord3=1.50x, Grp#1=2.00x [100%])', '3_ExpABC_GateV1_Strict',
         'sgov25_exit_raw25', 'grp1_100', 1.25, 1.50, 2.00, 'v1'),

        # 4. ExpABC Family Under Gate V2 (Round 3 Market-Only Low-Vol Gate: qqq_vol21<=30%)
        ('CR_ExpBC_2e_V2 [Round 3 Gate: qqq_vol21<=30%] (50%SGOV | Conf2=1.25x, Ord3=1.50x, Grp#1=1.75x, 75/25)', '4_ExpABC_GateV2_MktOnly',
         'sgov50', 'none', 1.25, 1.50, 1.75, 'v2'),
        ('CR_ExpABC_3a_V2 [Round 3 Gate: qqq_vol21<=30%] (ExIT_Raw | Conf2=1.25x, Ord3=1.50x, Grp#1=1.50x [100%])', '4_ExpABC_GateV2_MktOnly',
         'sgov25_exit_raw25', 'grp1_100', 1.25, 1.50, 1.50, 'v2'),
        ('CR_ExpABC_3b_V2 [Round 3 Gate: qqq_vol21<=30%] (ExIT_Raw | Conf2=1.25x, Ord3=1.50x, Grp#1=1.75x [100%])', '4_ExpABC_GateV2_MktOnly',
         'sgov25_exit_raw25', 'grp1_100', 1.25, 1.50, 1.75, 'v2'),
        ('CR_ExpABC_3b_BestSec_V2 [Round 3 Gate: qqq_vol21<=30%] (ExIT_BestSec | Conf2=1.25x, Ord3=1.50x, Grp#1=1.75x [100%])', '4_ExpABC_GateV2_MktOnly',
         'sgov25_exit_secrot25', 'grp1_100', 1.25, 1.50, 1.75, 'v2'),
        ('CR_ExpABC_3f_SGOV50_V2 [Round 3 Gate: qqq_vol21<=30%] (50%SGOV | Conf2=1.25x, Ord3=1.50x, Grp#1=1.75x [100%])', '4_ExpABC_GateV2_MktOnly',
         'sgov50', 'grp1_100', 1.25, 1.50, 1.75, 'v2'),
        ('CR_ExpABC_3c_V2 [Round 3 Gate: qqq_vol21<=30%] (ExIT_Raw | Conf2=1.25x, Ord3=1.50x, Grp#1=2.00x [100%])', '4_ExpABC_GateV2_MktOnly',
         'sgov25_exit_raw25', 'grp1_100', 1.25, 1.50, 2.00, 'v2'),
    ]

    cr_rows = []
    cr_ledgers = {}
    for v_name, fam, som, cm, lc2, lo3, lg3, vgv in clean_configs:
        Lp, d56, do2c, pk_dt, tr_dt = clean_room_simulate_strategy(
            common_yms, qqq_sl, xlk_sl, spy_sl, extra_sl, month_info, ret_map,
            cal_days, spy_daily_c, spy_daily_o,
            make_clean_rule(som, cm, lc2, lo3, lg3, vgv)
        )
        cr_ledgers[v_name] = Lp
        cr_rows.append(clean_room_summarize(v_name, fam, Lp, rf_monthly, d56, do2c, pk_dt, tr_dt, ref_ctrl_r))

    df_cr = pd.DataFrame(cr_rows)
    df_cr.to_csv(os.path.join(HERE, '14b_clean_room_reconciled_backtests.csv'), index=False)

    print('\n--- CLEAN-ROOM BACKTEST & DAILY DD PEAK-TO-TROUGH RECONCILIATION ---')
    for _, r in df_cr.iterrows():
        print(f"  {r['Variant']:<96} | CAGR={r['CAGR_09_26']*100:6.2f}% | SR={r['Sharpe']:5.3f} | "
              f"MoDD={r['Monthly_MaxDD']*100:6.2f}% | DayDD={r['Daily_MaxDD_5651ec2']*100:6.2f}% ({r['Daily_DD_Peak_Date']}->{r['Daily_DD_Trough_Date']}) | "
              f"AvgExp={r['Avg_Gross_Exp']:4.2f}x | 2022={r['Ret_2022']*100:+5.1f}% | t={r['NW_t_vs_Ctrl']:+5.2f}")

    # Verify bit-for-bit equality against previous CSVs
    df_m3_old = pd.read_csv(os.path.join(HERE, '04_mode3_crash_protected_consensus_leverage.csv')).set_index('Variant')
    df_12_old = pd.read_csv(os.path.join(HERE, '12_expC_and_ABC_tiered_burst.csv')).set_index('Variant')

    m3_4a_old_cagr = float(df_m3_old.loc['M3_4a_Combined: SEP_OFF->50%SGOV | SEP_ON+LowVol+3Leg->1.50x', 'CAGR_09_26'])
    m3_4a_cr_v1_cagr = float(df_cr.loc[df_cr['Variant'].str.startswith('CR_M3_4a_V1'), 'CAGR_09_26'].iloc[0])

    ref_m3_4a_r3_cagr = float(df_12_old.loc['Ref_M3_4a: SEP_OFF(50%SGOV) | SEP_ON+LowVol: All_3Leg=1.50x', 'CAGR_09_26'])
    m3_4a_cr_v2_cagr = float(df_cr.loc[df_cr['Variant'].str.startswith('CR_M3_4a_V2'), 'CAGR_09_26'].iloc[0])

    abc3b_r3_cagr = float(df_12_old.loc['ExpABC_3b: A(100%Grp#1)+B(ExIT)+C(Conf2=1.25x, Ord3=1.50x, Grp#1=1.75x)', 'CAGR_09_26'])
    abc3b_cr_v2_cagr = float(df_cr.loc[df_cr['Variant'].str.startswith('CR_ExpABC_3b_V2'), 'CAGR_09_26'].iloc[0])

    print('\n--- BIT-FOR-BIT REPLICATION VERIFICATION ---')
    print(f'  Round 1 M3_4a CAGR   = {m3_4a_old_cagr:.16f} vs Clean-Room V1 = {m3_4a_cr_v1_cagr:.16f} (Diff = {abs(m3_4a_old_cagr - m3_4a_cr_v1_cagr):.2e})')
    print(f'  Round 3 Ref_M3_4a    = {ref_m3_4a_r3_cagr:.16f} vs Clean-Room V2 = {m3_4a_cr_v2_cagr:.16f} (Diff = {abs(ref_m3_4a_r3_cagr - m3_4a_cr_v2_cagr):.2e})')
    print(f'  Round 3 ExpABC_3b    = {abc3b_r3_cagr:.16f} vs Clean-Room V2 = {abc3b_cr_v2_cagr:.16f} (Diff = {abs(abc3b_r3_cagr - abc3b_cr_v2_cagr):.2e})')

    # =========================================================================
    # ACTUAL TIINGO 2x ETF PRICE VERIFICATION (NVDL & PLTU)
    # =========================================================================
    print('\n[Gate ②-B] Comparing Simulated Daily-Reset 2x ETF vs Actual Tiingo Market Prices (NVDL & PLTU)...')
    df_etf_cmp = verify_actual_tiingo_2x_etfs(common_yms, month_info)
    df_etf_cmp.to_csv(os.path.join(HERE, '14c_actual_tiingo_2x_etf_vs_simulation.csv'), index=False)
    if len(df_etf_cmp):
        for _, r in df_etf_cmp.iterrows():
            print(f"  {r['ym']} | {r['stock']} -> {r['etf_ticker']} ({r['entry_date']}..{r['exit_date']}) | Grp#1={str(r['subind_group_is_1']):<5} | "
                  f"1x={r['stock_1x_ret']*100:+6.2f}% | Naive2x={r['naive_2x_ret_wrong']*100:+6.2f}% | "
                  f"Sim2x={r['simulated_daily_reset_2x_ret']*100:+6.2f}% | Actual_Market_ETF={r['actual_market_etf_ret_tiingo']*100:+6.2f}% | "
                  f"Diff(Actual-Sim)={r['diff_actual_minus_sim']*100:+5.2f}%")
        print(f"  Mean Diff (Actual ETF Market Return - Simulated Formula) across {len(df_etf_cmp)} months = "
              f"{df_etf_cmp['diff_actual_minus_sim'].mean()*100:+.2f}%/mo (Median = {df_etf_cmp['diff_actual_minus_sim'].median()*100:+.2f}%/mo)")

    # =========================================================================
    # GATE ③: UPDATE CUMULATIVE TRIAL REGISTRY & DEFLATED SHARPE RATIO (DSR)
    # =========================================================================
    print('\n[Gate ③] Updating Master Trial Registry & Computing Deflated Sharpe Ratio (All Rounds Combined)...')
    reg_base = pd.read_csv(os.path.join(SPY_DIR, '08b_master_all_trials_sharpe_registry.csv'))

    # Collect all unique variants tested across Round 8.1, Round 8.2, Round 8.3, and Clean-Room Gate V1
    df_m1 = pd.read_csv(os.path.join(HERE, '02_mode1_consensus_conviction_sizing.csv'))
    df_m2 = pd.read_csv(os.path.join(HERE, '03_mode2_sep_and_trend_qqq_routing.csv'))
    df_m3 = pd.read_csv(os.path.join(HERE, '04_mode3_crash_protected_consensus_leverage.csv'))
    df_m4 = pd.read_csv(os.path.join(HERE, '05_mode4_ear_momentum_consensus.csv'))
    df_08 = pd.read_csv(os.path.join(HERE, '08_standalone_sector_and_industry_sleeves.csv'))
    df_09 = pd.read_csv(os.path.join(HERE, '09_shadow_confirmer_conviction_backtests.csv'))
    df_10 = pd.read_csv(os.path.join(HERE, '10_nontech_champion_vs_5leg_strawman.csv'))
    df_11b = pd.read_csv(os.path.join(HERE, '11b_expAB_unlevered_concentration_and_sepoff.csv'))
    df_12 = pd.read_csv(os.path.join(HERE, '12_expC_and_ABC_tiered_burst.csv'))
    df_13 = pd.read_csv(os.path.join(HERE, '13_expD_single_stock_2x_etf_backtests.csv'))

    # Standardize columns for registry addition
    sq12 = np.sqrt(12.0)
    idx_213 = pd.date_range('2009-01-31', '2026-09-30', freq='ME')
    rf_213 = rf_monthly.reindex(idx_213).ffill().fillna(0.0)
    rf_ann_mean = float(rf_213.mean() * 12.0)

    new_reg_rows = []
    seen_names = set(reg_base['trial_name'].astype(str).values)

    def add_df_to_reg(df_in, r_id, r_name, name_col='Variant'):
        for _, r in df_in.iterrows():
            tname = str(r[name_col])
            if tname in seen_names:
                continue
            seen_names.add(tname)
            sr_ex_ann = float(r['Sharpe'])
            vol = float(r.get('Ann_Vol', 0.38))
            sr_ex_m = sr_ex_ann / sq12
            sr_raw_ann = sr_ex_ann + rf_ann_mean / max(vol, 0.05)
            new_reg_rows.append({
                'round_id': r_id,
                'round_name': r_name,
                'source_file': 'outputs/consensus_burst_mode_audit_20261104',
                'trial_name': tname,
                'in_canonical_878': True,
                'in_post_core3_397': True,
                'sr_excess_monthly': sr_ex_m,
                'sr_excess_ann': sr_ex_ann,
                'sr_raw_monthly': sr_raw_ann / sq12,
                'sr_raw_ann': sr_raw_ann,
            })

    add_df_to_reg(pd.concat([df_m1, df_m2, df_m3, df_m4], ignore_index=True), 8, 'R8_1_consensus_burst_modes')
    add_df_to_reg(df_08, 9, 'R8_2_sector_industry_sleeves', name_col='Sleeve_Name')
    add_df_to_reg(pd.concat([df_09, df_10], ignore_index=True), 9, 'R8_2_shadow_and_nontech_arch')
    add_df_to_reg(pd.concat([df_11b, df_12, df_13, df_cr], ignore_index=True), 10, 'R8_3_experiments_ABCD_and_reconciled')

    reg_master = pd.concat([reg_base, pd.DataFrame(new_reg_rows)], ignore_index=True)
    reg_master.to_csv(os.path.join(HERE, '06b_master_all_trials_sharpe_registry_r8.csv'), index=False)

    can_pool = reg_master[reg_master['in_canonical_878']]['sr_excess_monthly'].dropna().values
    n_cum_can = len(can_pool)
    n_cum_exh = len(reg_master)
    var_sr_can = float(np.var(can_pool, ddof=1))

    gamma_em = 0.5772156649
    sr0_can = float(np.sqrt(var_sr_can) * (
        (1.0 - gamma_em) * sst.norm.ppf(1.0 - 1.0 / n_cum_can) +
        gamma_em * sst.norm.ppf(1.0 - 1.0 / (n_cum_can * np.e))
    ))

    def calc_dsr_p(sr_m, skew, kurt, T=213, sr0=sr0_can):
        denom = np.sqrt(max(1e-8, 1.0 - skew * sr_m + ((kurt - 1.0) / 4.0) * (sr_m ** 2)))
        z = (sr_m - sr0) * np.sqrt(T - 1.0) / denom
        return float(sst.norm.cdf(z))

    ctrl_skew = float(df_cr.loc[0, 'Sample_Skew'])
    ctrl_kurt = float(df_cr.loc[0, 'Sample_Kurt_Pearson'])

    dsr_rows = []
    # Evaluate DSR on all Clean-Room Reconciled variants + key Round 1/2/3 variants
    combined_for_dsr = pd.concat([df_cr, df_11b, df_12, df_13, df_09, df_m3, df_m2, df_m1], ignore_index=True)
    combined_for_dsr = combined_for_dsr.drop_duplicates(subset=['Variant']).reset_index(drop=True)

    for _, r in combined_for_dsr.iterrows():
        sr_ann = float(r['Sharpe'])
        sr_m = sr_ann / sq12
        sk = float(r['Sample_Skew']) if pd.notna(r.get('Sample_Skew')) else ctrl_skew
        ku = float(r['Sample_Kurt_Pearson']) if pd.notna(r.get('Sample_Kurt_Pearson')) else ctrl_kurt
        p_dsr_own = calc_dsr_p(sr_m, skew=sk, kurt=ku, T=213, sr0=sr0_can)
        p_dsr_ctrl_mom = calc_dsr_p(sr_m, skew=ctrl_skew, kurt=ctrl_kurt, T=213, sr0=sr0_can)
        dsr_rows.append({
            'Variant': r['Variant'],
            'Family': r['Family'],
            'CAGR_09_26': r['CAGR_09_26'],
            'Sharpe_Ann': sr_ann,
            'Sharpe_Monthly': sr_m,
            'Monthly_MaxDD': r['Monthly_MaxDD'],
            'Daily_MaxDD_5651ec2': r.get('Daily_MaxDD_5651ec2', np.nan),
            'N_Cumulative_Canonical': n_cum_can,
            'N_Cumulative_Exhaustive': n_cum_exh,
            'Pool_Monthly_SR_Std': float(np.sqrt(var_sr_can)),
            'Expected_Max_Monthly_SR0': sr0_can,
            'Expected_Max_Ann_SR0': sr0_can * sq12,
            'Sample_Skew': sk,
            'Sample_Kurt_Pearson': ku,
            'DSR_p_value_OwnMoments': p_dsr_own,
            'DSR_p_value_CtrlMoments': p_dsr_ctrl_mom,
            'DSR_p_value': p_dsr_ctrl_mom,
        })

    df_dsr_out = pd.DataFrame(dsr_rows)
    df_dsr_out.to_csv(os.path.join(HERE, '06_multiple_testing_dsr.csv'), index=False)

    print(f'  Updated Cumulative Canonical Trials N_cum = {n_cum_can} (Exhaustive = {n_cum_exh})')
    print(f'  Pool Monthly SR Std = {np.sqrt(var_sr_can):.4f} (Ann = {np.sqrt(var_sr_can)*sq12:.4f})')
    print(f'  Expected Max SR0 under Null = {sr0_can:.4f} monthly ({sr0_can*sq12:.3f} annualized)')
    print(f'  Control 3S_G1_1k Exact Sample Moments: Skew = {ctrl_skew:+.3f}, Kurtosis (Pearson) = {ctrl_kurt:.3f}')
    print('\n--- TOP CANDIDATES DEFLATED SHARPE RATIO (N_cum = ' + str(n_cum_can) + ') ---')
    for _, r in df_dsr_out.head(23).iterrows():
        print(f"  {r['Variant']:<96} | CAGR={r['CAGR_09_26']*100:6.2f}% | SR={r['Sharpe_Ann']:5.3f} | "
              f"DayDD={r['Daily_MaxDD_5651ec2']*100:6.2f}% | Skew={r['Sample_Skew']:+5.2f} Kurt={r['Sample_Kurt_Pearson']:5.2f} | "
              f"DSR(CtrlMom)={r['DSR_p_value_CtrlMoments']:.3f} | DSR(OwnMom)={r['DSR_p_value_OwnMoments']:.3f}")


if __name__ == '__main__':
    main()
