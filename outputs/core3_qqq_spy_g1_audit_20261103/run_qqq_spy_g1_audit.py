#!/usr/bin/env python3
"""
run_qqq_spy_g1_audit.py — Clean-Room Adversarial Audit of QQQ + SPY (vs QQQ + XLK & QQQ + XLK + SPY)
Under Both Core3 (Hard Cutoff) and G1 (Buy-Hold Hysteresis Buffer)
=====================================================================================================
Tests the user's hypothesis:
  "我们现在是qqq,xlk ，有没有可能，qqq spy also good? u get it? use core 3 , and g1."

Evaluates across 2009-01 .. 2026-09 (213 months, T+1 Open execution, 10 bp/side cost, 1.0x unlevered, Cash = 0%):
  1. Standalone SPY (Full S&P 500 across all 11 GICS sectors) Constituent Momentum Sleeves:
       - SPY Raw 12-1 Momentum (Top-1, Top-2, Top-3, Rank #1/#2/#3, and G1 Buffers)
       - SPY Sharpe-Momentum (mom_12_1 / vol_12_1: Top-1, Top-2, Top-3, Rank #1/#2/#3, and G1 Buffers)
       - SPY Sector-Rotation Momentum (Top-1 Sector by EW Mom/Sharpe -> Top-1 Stock, Hard & Buffered)
       - SPY Ex-IT (Non-Tech 10 GICS Sectors) Top-1 (Raw & Sharpe-Mom)
       - SPY + A5 Anti-Jump Veto (max_ret_5d < 35%) & FIP Smoothness
  2. 2-Sleeve Pairings (50% QQQ + 50% SPY vs 50% QQQ + 50% XLK) under BOTH Core3 and G1:
       - Core3 (Hard Cutoff): QQQ Hard Top-2 + SPY Hard Top-1 / Top-2
       - G1 (QQQ Buffered Hold <= Top-3/4/5/6 + SPY Hard Top-1 / Top-2)
       - G1-Both (QQQ Buffered Hold <= Top-5 + SPY Buffered Hold <= Top-2/3/4)
       - Weight Grid (75/25, 50/50, 25/75) & De-Overlap variants
  3. 3-Sleeve Combinations (QQQ + XLK + SPY) under BOTH Core3 and G1:
       - 50% QQQ + 25% XLK + 25% SPY (Raw, Sharpe, Sector-Stock, Ex-IT)
       - 33.3% QQQ + 33.3% XLK + 33.3% SPY
       - 40% QQQ + 40% XLK + 20% SPY
  4. Forensic Attribution:
       - Month-by-month comparison of SPY Top-1 vs XLK Top-1 (agreement rate, GICS sector breakdown,
         2022 bear market attribution, overlap with QQQ Top-2, sleeve correlations)
  5. Full Adversarial Audit:
       - True Daily Mark-to-Market MaxDD (5651ec2 & Open-to-Close)
       - Leave-One-Winner-Out (No NVDA, No SNDK, No PLTR, No DVN, Ban Top-3, Remove Top-5 Months)
       - Second-Vendor (Tiingo-First) Replication
       - Cumulative Multiple-Testing Deflated Sharpe Ratio (DSR)
"""
import json
import os
import sys
import warnings
import numpy as np
import pandas as pd
from scipy import stats as sst

warnings.filterwarnings('ignore')

ROOT = '/Users/happygolucky/Desktop/宏观观察器'
QQQ_DIR = os.path.join(ROOT, 'outputs', 'qqq_mom_top3_claude_audit_20261103')
TECH_DIR = os.path.join(ROOT, 'outputs', 'tech_top1_independent_audit_20261103')
SEL_DIR = os.path.join(ROOT, 'outputs', 'core3_stock_selection_audit_20261103')
STR_DIR = os.path.join(ROOT, 'outputs', 'core3_structural_blindspots_audit_20261103')
HERE = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, QQQ_DIR)
sys.path.insert(0, TECH_DIR)

import a2_engine as QE
import c2_engine as TE

COST_BP = 0.0010  # 10 bp per side


# =============================================================================
# 1. Load Risk-Free Rate & Trading Calendar
# =============================================================================
def load_rf_and_calendar():
    fn = os.path.join(ROOT, 'data', 'fred', 'DGS3MO.json')
    d = json.load(open(fn))['values']
    s = pd.Series({pd.Timestamp(dt): float(v) / 100.0 for dt, v in d if v is not None and v != '.'}).sort_index()
    rf_monthly = s.resample('ME').last() / 12.0
    cal = QE.calendar()
    cal_days = cal[(cal >= '2009-01-02') & (cal <= '2026-10-01')]
    return rf_monthly, cal_days


# =============================================================================
# 2. Candidate Ranking & Single-Sleeve Simulation Engine (Supporting Hard & G1 Buffer)
# =============================================================================
def rank_sleeve_candidates_at_t(g, spec, exclude_tickers=None):
    """
    Ranks eligible candidates at formation month-end `t` for any universe (`QQQ`, `XLK`, `SPY`).
    Supports:
      - `type == 'score'`: sort descending by `score_col`
      - `type == 'sector_top'`: filter to top `n_sec` sectors by `sec_rank_col`, then sort by `score_col`
      - `type == 'ex_it_score'`: exclude `Information Technology` sector, then sort by `score_col`
      - `type == 'veto'`: sort by `base_col`, veto candidates in `pool_n` failing `veto_fn(row)`
      - `type == 'pool_rerank'`: take top `pool_n` by `base_col`, re-rank by `rerank_col`
    """
    d = g.copy()
    if exclude_tickers:
        d = d[~d['ticker'].isin(set(exclude_tickers))]

    base_col = spec.get('base_col', 'mom_12_1')
    d = d[d[base_col].notna() & d['hold_ret'].notna()].copy()
    if d.empty:
        return d

    stype = spec['type']
    if stype == 'score':
        sc = spec['score_col']
        return d[d[sc].notna()].sort_values([sc, 'ticker'], ascending=[False, True]).reset_index(drop=True)

    elif stype == 'ex_it_score':
        sc = spec['score_col']
        d_sub = d[d['sector'] != 'Information Technology'].copy()
        if d_sub.empty:
            d_sub = d
        return d_sub[d_sub[sc].notna()].sort_values([sc, 'ticker'], ascending=[False, True]).reset_index(drop=True)

    elif stype == 'sector_top':
        n_sec = int(spec.get('n_sec', 1))
        sec_rk_col = spec.get('sec_rank_col', 'sector_rank_mom')
        sc = spec.get('score_col', 'mom_12_1')
        per_sec_k = int(spec.get('per_sec_k', 1))
        if n_sec == 1:
            d_top = d[d[sec_rk_col] <= 1].sort_values([sc, 'ticker'], ascending=[False, True])
            d_rest = d[d[sec_rk_col] > 1].sort_values([sec_rk_col, sc, 'ticker'], ascending=[True, False, True])
            return pd.concat([d_top, d_rest], ignore_index=True)
        else:
            # Top `per_sec_k` from each of top `n_sec` sectors first, then rest
            top_picks = []
            for rk_s in range(1, n_sec + 1):
                sub_s = d[d[sec_rk_col] == rk_s].sort_values([sc, 'ticker'], ascending=[False, True]).head(per_sec_k)
                top_picks.append(sub_s)
            top_df = pd.concat(top_picks, ignore_index=True) if top_picks else pd.DataFrame()
            rest_df = d[~d['ticker'].isin(set(top_df['ticker']))].sort_values([sec_rk_col, sc, 'ticker'], ascending=[True, False, True])
            return pd.concat([top_df, rest_df], ignore_index=True)

    elif stype == 'veto':
        pool_n = int(spec.get('pool_n', 8))
        veto_fn = spec['veto_fn']
        d_sorted = d.sort_values([base_col, 'ticker'], ascending=[False, True])
        pool = d_sorted.head(pool_n).copy()
        pass_mask = ~pool.apply(veto_fn, axis=1)
        passed = pool[pass_mask]
        failed = pool[~pass_mask]
        rest = d_sorted.iloc[pool_n:]
        return pd.concat([passed, failed, rest], ignore_index=True)

    elif stype == 'pool_rerank':
        pool_n = int(spec.get('pool_n', 5))
        rerank_col = spec['rerank_col']
        d_sorted = d.sort_values([base_col, 'ticker'], ascending=[False, True])
        pool = d_sorted.head(pool_n).copy()
        pool_valid = pool[pool[rerank_col].notna()].sort_values([rerank_col, base_col, 'ticker'], ascending=[False, False, True])
        pool_na = pool[pool[rerank_col].isna()]
        rest = d_sorted.iloc[pool_n:]
        return pd.concat([pool_valid, pool_na, rest], ignore_index=True)

    raise ValueError(f'Unknown spec type: {stype}')


def simulate_single_sleeve(df_panel, spec, k=1, k_keep=None, target_rank=None,
                           linear_cost=False, exclude_tickers=None):
    """
    Simulates a single constituent sleeve (`QQQ`, `XLK`, or `SPY`) across all 213 months.
    - If `k_keep` is None or `<= k`: Hard Cutoff `Top-k` (`Core3` style).
    - If `k_keep > k`: `G1` Buy-Hold Hysteresis Buffer (`Buy Top-k, Hold while Rank <= k_keep`).
    - If `target_rank` is set (e.g. 1, 2, 3): holds the single stock at `target_rank`.
    """
    if k_keep is None:
        k_keep = k

    prev_w = {}
    prev_held = []
    rows = []

    for t_val, g in df_panel.groupby('t', sort=True):
        t_ts = pd.Timestamp(t_val)
        m_dt = t_ts + pd.offsets.MonthEnd(1)
        ym = (t_ts + pd.offsets.MonthBegin(1)).strftime('%Y-%m')

        d_rk = rank_sleeve_candidates_at_t(g, spec, exclude_tickers=exclude_tickers)
        ranked_tks = list(d_rk['ticker'].values)
        ret_map = dict(zip(d_rk['ticker'], d_rk['hold_ret'].astype(float)))
        sec_map = dict(zip(d_rk['ticker'], d_rk['sector'])) if 'sector' in d_rk.columns else {}
        store_map = dict(zip(d_rk['ticker'], zip(d_rk['store'], d_rk['sym'])))

        if target_rank is not None:
            idx = min(int(target_rank) - 1, len(ranked_tks) - 1)
            picks = [ranked_tks[idx]] if ranked_tks else []
        elif k_keep > k and prev_held:
            keep_pool = set(ranked_tks[:k_keep])
            kept = [tk for tk in prev_held if tk in keep_pool][:k]
            for tk in ranked_tks:
                if len(kept) >= k:
                    break
                if tk not in kept:
                    kept.append(tk)
            picks = kept
        else:
            picks = ranked_tks[:k]

        prev_held = list(picks)
        w = {tk: 1.0 / len(picks) for tk in picks} if picks else {}
        gross = float(sum(w[tk] * ret_map[tk] for tk in picks))

        if not prev_w:
            to = 2.0 if linear_cost else 1.0
        else:
            all_k = set(w) | set(prev_w)
            to = float(sum(abs(w.get(tk, 0.0) - prev_w.get(tk, 0.0)) for tk in all_k))

        if linear_cost:
            net = gross - COST_BP * to
        else:
            net = (1.0 + gross) * ((1.0 - COST_BP) ** to) - 1.0 if to > 0 else gross

        denom = sum(w[tk] * (1.0 + ret_map[tk]) for tk in picks)
        prev_w = {tk: w[tk] * (1.0 + ret_map[tk]) / denom for tk in picks} if denom > 0 else {}

        rows.append({
            'ym': ym,
            'month': m_dt,
            't_date': t_ts,
            'picks': '|'.join(picks),
            'sectors': '|'.join(sec_map.get(tk, 'IT') for tk in picks),
            'gross': gross,
            'turnover': to,
            'net': net,
            'weights_dict': dict(w),
            'store_map': {tk: store_map[tk] for tk in picks if tk in store_map},
        })

    return pd.DataFrame(rows).set_index('ym')


def combine_sleeves(sleeves_with_weights, univ_tags):
    """
    Combines 2 or 3 simulated sleeves (e.g. `[(L_qqq, 0.50), (L_spy, 0.50)]` or
    `[(L_qqq, 0.50), (L_xlk, 0.25), (L_spy, 0.25)]`) into a composite portfolio ledger.
    Matches exact Core3 / G1 sleeve-additive return & turnover accounting.
    """
    common_ym = sleeves_with_weights[0][0].index
    for L_s, _ in sleeves_with_weights[1:]:
        common_ym = common_ym.intersection(L_s.index)

    rows = []
    for ym in common_ym:
        t_date = sleeves_with_weights[0][0].at[ym, 't_date']
        gross_p = 0.0
        net_p = 0.0
        to_p = 0.0
        w_comb = {}
        meta_comb = {}
        sleeve_picks = {}

        for (L_s, w_s), utag in zip(sleeves_with_weights, univ_tags):
            row_s = L_s.loc[ym]
            gross_p += w_s * float(row_s['gross'])
            net_p += w_s * float(row_s['net'])
            to_p += w_s * float(row_s['turnover'])
            sleeve_picks[utag] = row_s['picks']
            for tk, w_tk in row_s['weights_dict'].items():
                w_comb[tk] = w_comb.get(tk, 0.0) + w_s * w_tk
                if tk not in meta_comb:
                    st, sym = row_s['store_map'].get(tk, ('yahoo', tk))
                    meta_comb[tk] = (utag, st, sym)

        # Check if any stock is held in multiple sleeves (overlap)
        n_total_slots = sum(len(L_s.loc[ym, 'weights_dict']) for L_s, _ in sleeves_with_weights)
        is_overlap = len(w_comb) < n_total_slots

        rows.append({
            'ym': ym,
            't_date': t_date,
            'gross': gross_p,
            'net': net_p,
            'turnover': to_p,
            'n_distinct': len(w_comb),
            'max_single_w': max(w_comb.values()) if w_comb else 0.0,
            'is_overlap': is_overlap,
            'holdings_dict': w_comb,
            'meta_map': meta_comb,
            'sleeve_picks': sleeve_picks,
        })

    return pd.DataFrame(rows).set_index('ym')


# =============================================================================
# 3. True Daily Mark-to-Market Drawdown Builder (Supporting QQQ, XLK, and SPY)
# =============================================================================
_DAILY_STOCK_CACHE = {}


def get_daily_stock_df(utag, tk, t_form, store, sym, spy_daily_c, spy_daily_o):
    t_form = pd.Timestamp(t_form)
    if utag == 'spy' and tk in spy_daily_c.columns:
        ckey = ('spy', tk)
        if ckey not in _DAILY_STOCK_CACHE:
            c_s = spy_daily_c[tk].dropna()
            o_s = spy_daily_o[tk].reindex(c_s.index).where(spy_daily_o[tk].reindex(c_s.index).notna() & (spy_daily_o[tk].reindex(c_s.index) > 0), c_s)
            _DAILY_STOCK_CACHE[ckey] = pd.DataFrame({'adjclose': c_s, 'adjopen_clean': o_s}).sort_index()
        return _DAILY_STOCK_CACHE[ckey]

    if utag == 'qqq' or ':' in str(store):
        st_base = str(store).split(':')[0] if ':' in str(store) else store
        ckey = ('qqq', st_base, sym)
        if ckey not in _DAILY_STOCK_CACHE:
            df = QE.series(st_base, sym)
            if df is None:
                df = QE.series('yahoo', tk)
            df = df.sort_index()
            df = df[~df.index.duplicated(keep='last')].copy()
            df['adjopen_clean'] = df['adjopen'].where(df['adjopen'].notna() & (df['adjopen'] > 0), df['adjclose'])
            _DAILY_STOCK_CACHE[ckey] = df
        return _DAILY_STOCK_CACHE[ckey]

    # Tech / XLK fallback via TE.segments
    segs = TE.segments(tk)
    d0 = QE.first_td_after(t_form, 1)
    d1 = QE.first_td_after(t_form + pd.offsets.MonthEnd(1), 1)
    order = [x for x in segs if d0 in x[0].index and d1 in x[0].index] + \
            [x for x in segs if d0 in x[0].index and d1 not in x[0].index]
    if order:
        df_raw, src, sym_seg, _ = order[0]
        ckey = ('xlk', tk, src, sym_seg, str(df_raw.index.min().date()))
        if ckey not in _DAILY_STOCK_CACHE:
            df = pd.DataFrame({
                'adjclose': df_raw['adjclose'],
                'adjopen': df_raw['adj_open'] if 'adj_open' in df_raw.columns else np.nan,
            }, index=df_raw.index).sort_index()
            df = df[~df.index.duplicated(keep='last')]
            df['adjopen_clean'] = df['adjopen'].where(df['adjopen'].notna() & (df['adjopen'] > 0), df['adjclose'])
            _DAILY_STOCK_CACHE[ckey] = df
        return _DAILY_STOCK_CACHE[ckey]

    # Final fallback to spy_daily_c
    c_s = spy_daily_c[tk].dropna()
    o_s = spy_daily_o[tk].reindex(c_s.index).fillna(c_s)
    return pd.DataFrame({'adjclose': c_s, 'adjopen_clean': o_s}).sort_index()


def compute_daily_drawdowns(L_port, cal_days, spy_daily_c, spy_daily_o):
    """
    Computes both:
      - `Daily_MaxDD_5651ec2` (entry-day close normalized daily path)
      - `Daily_MaxDD_O2C` (exact Open-to-Close mark-to-market daily path)
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

        s_map = {}
        p_e_map = {}
        for tk in h_dict:
            u_tk, st_tk, sym_tk = meta_map.get(tk, ('spy', 'yahoo', tk))
            df_s = get_daily_stock_df(u_tk, tk, t_form, st_tk, sym_tk, spy_daily_c, spy_daily_o)
            s_map[tk] = df_s
            sub_e = df_s.loc[:e_d, 'adjopen_clean'].dropna()
            p_e_map[tk] = float(sub_e.iloc[-1]) if len(sub_e) else 1.0

        m_cost = float(row['gross'] - row['net'])
        W_after_entry = W * (1.0 - m_cost)

        v_rel_0 = {}
        for d_i, d in enumerate(m_days):
            port_mult_o2c = 0.0
            port_mult_c56 = 0.0
            for tk, wv in h_dict.items():
                sub_c = s_map[tk].loc[:d, 'adjclose'].dropna()
                c_d = float(sub_c.iloc[-1]) if len(sub_c) else p_e_map[tk]
                rel = c_d / p_e_map[tk] if p_e_map[tk] > 0 else 1.0
                if d_i == 0:
                    v_rel_0[tk] = rel if rel > 0 else 1.0
                port_mult_o2c += wv * rel
                port_mult_c56 += wv * (rel / v_rel_0[tk])

            pts_o2c[d] = W_after_entry * port_mult_o2c
            pts_c56[d] = W * port_mult_c56

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


# =============================================================================
# 4. Statistical Summary Helper
# =============================================================================
def summarize_ledger(name, family, L_df, rf_monthly, dd_c56=np.nan, dd_o2c=np.nan, ref_r=None, ref_g1_r=None):
    r_m = L_df['net'].dropna()
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

    def sub_cagr(a, b):
        sub = r_s.loc[a:b]
        return float((np.prod(1.0 + sub.values)) ** (12.0 / len(sub)) - 1.0) if len(sub) else np.nan

    ret_2022 = float(np.prod(1.0 + r_s.loc['2022-01-01':'2022-12-31'].values) - 1.0)

    def calc_nw_t(r_target, r_bench):
        if r_bench is None:
            return np.nan
        diff = (r_target - r_bench.reindex(r_target.index)).dropna().values
        if len(diff) < 24 or np.std(diff, ddof=1) < 1e-9:
            return 0.0
        e = diff - diff.mean()
        L_len = len(diff)
        v = (e @ e) / L_len
        for lag in range(1, 7):
            v += 2.0 * (1.0 - lag / 7.0) * (e[lag:] @ e[:-lag]) / L_len
        return float(diff.mean() / np.sqrt(v / L_len)) if v > 0 else 0.0

    nw_vs_c3 = calc_nw_t(r_m, ref_r)
    nw_vs_g1 = calc_nw_t(r_m, ref_g1_r)

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
        'CAGR_2009_2018': sub_cagr('2009-01-31', '2018-12-31'),
        'CAGR_2019_2026': sub_cagr('2019-01-31', '2026-09-30'),
        'Ret_2022': ret_2022,
        'Avg_Monthly_TO': float(L_df['turnover'].mean()),
        'Overlap_Share': float(L_df['is_overlap'].mean()) if 'is_overlap' in L_df.columns else 0.0,
        'NW_t_vs_Core3_Ctrl': nw_vs_c3,
        'NW_t_vs_G1_Ctrl': nw_vs_g1,
    }


def compute_cumulative_dsr(all_series_dict, best_key, prior_trials=434):
    """
    Bailey & López de Prado (2014) Deflated Sharpe Ratio across cumulative trials.
    """
    srs = []
    for s in all_series_dict.values():
        v = s.dropna().values
        if len(v) > 24 and np.std(v, ddof=1) > 0:
            srs.append(float(np.mean(v) / np.std(v, ddof=1)))
    n_new = len(srs)
    n_total = prior_trials + n_new
    var_sr = float(np.var(srs, ddof=1))
    emc = 0.5772156649
    sr0 = np.sqrt(var_sr) * ((1.0 - emc) * sst.norm.ppf(1.0 - 1.0 / n_total) + emc * sst.norm.ppf(1.0 - 1.0 / (n_total * np.e)))

    rb = all_series_dict[best_key].dropna().values
    T = len(rb)
    srb = float(np.mean(rb) / np.std(rb, ddof=1))
    sk = float(sst.skew(rb))
    ku = float(sst.kurtosis(rb, fisher=False))
    denom = np.sqrt(max(1e-8, 1.0 - sk * srb + ((ku - 1.0) / 4.0) * (srb ** 2)))
    z = (srb - sr0) * np.sqrt(T - 1.0) / denom
    return float(sst.norm.cdf(z)), float(sr0 * np.sqrt(12.0)), n_new, n_total


def main():
    print('=== STARTING CLEAN-ROOM AUDIT: QQQ + SPY vs QQQ + XLK (CORE3 & G1) ===')
    rf_monthly, cal_days = load_rf_and_calendar()

    df_qqq = pd.read_parquet(os.path.join(SEL_DIR, 'qqq_selection_panel.parquet'))
    df_xlk = pd.read_parquet(os.path.join(SEL_DIR, 'tech_selection_panel.parquet'))
    df_spy = pd.read_parquet(os.path.join(HERE, 'spy_selection_panel.parquet'))

    df_qqq_t = pd.read_parquet(os.path.join(SEL_DIR, 'qqq_selection_panel_tiingo.parquet'))
    df_xlk_t = pd.read_parquet(os.path.join(SEL_DIR, 'tech_selection_panel_tiingo.parquet'))
    df_spy_t = pd.read_parquet(os.path.join(HERE, 'spy_selection_panel_tiingo.parquet'))

    spy_daily_c = pd.read_parquet(os.path.join(HERE, 'spy_daily_close.parquet'))
    spy_daily_o = pd.read_parquet(os.path.join(HERE, 'spy_daily_open.parquet'))

    # Canonical selection specs
    q_sharpe_spec = {'type': 'score', 'base_col': 'sharpe_mom_12_1', 'score_col': 'sharpe_mom_12_1'}
    q_raw_spec = {'type': 'score', 'base_col': 'mom_12_1', 'score_col': 'mom_12_1'}

    x_raw_spec = {'type': 'score', 'base_col': 'mom_12_1', 'score_col': 'mom_12_1'}
    x_sharpe_spec = {'type': 'score', 'base_col': 'sharpe_mom_12_1', 'score_col': 'sharpe_mom_12_1'}
    x_a5_spec = {'type': 'veto', 'base_col': 'mom_12_1', 'pool_n': 4, 'veto_fn': lambda r: r['max_ret_5d_12_1'] > 0.35}

    s_raw_spec = {'type': 'score', 'base_col': 'mom_12_1', 'score_col': 'mom_12_1'}
    s_sharpe_spec = {'type': 'score', 'base_col': 'sharpe_mom_12_1', 'score_col': 'sharpe_mom_12_1'}
    s_sec_raw_spec = {'type': 'sector_top', 'base_col': 'mom_12_1', 'score_col': 'mom_12_1', 'sec_rank_col': 'sector_rank_mom', 'n_sec': 1}
    s_sec_sh_spec = {'type': 'sector_top', 'base_col': 'sharpe_mom_12_1', 'score_col': 'sharpe_mom_12_1', 'sec_rank_col': 'sector_rank_sharpe', 'n_sec': 1}
    s_sec2_raw_spec = {'type': 'sector_top', 'base_col': 'mom_12_1', 'score_col': 'mom_12_1', 'sec_rank_col': 'sector_rank_mom', 'n_sec': 2, 'per_sec_k': 1}
    s_exit_raw_spec = {'type': 'ex_it_score', 'base_col': 'mom_12_1', 'score_col': 'mom_12_1'}
    s_exit_sh_spec = {'type': 'ex_it_score', 'base_col': 'sharpe_mom_12_1', 'score_col': 'sharpe_mom_12_1'}
    s_a5_raw_spec = {'type': 'veto', 'base_col': 'mom_12_1', 'pool_n': 8, 'veto_fn': lambda r: r['max_ret_5d_12_1'] > 0.35}
    s_a5_sh_spec = {'type': 'veto', 'base_col': 'sharpe_mom_12_1', 'pool_n': 8, 'veto_fn': lambda r: r['max_ret_5d_12_1'] > 0.35}
    s_fip_raw_spec = {'type': 'pool_rerank', 'base_col': 'mom_12_1', 'pool_n': 5, 'rerank_col': 'fip_smooth_12_1'}
    s_fip_sh_spec = {'type': 'pool_rerank', 'base_col': 'sharpe_mom_12_1', 'pool_n': 5, 'rerank_col': 'fip_smooth_12_1'}

    # Pre-simulate core QQQ and XLK sleeves
    L_qqq_c3 = simulate_single_sleeve(df_qqq, q_sharpe_spec, k=2, k_keep=2, linear_cost=True)
    L_qqq_g1_3 = simulate_single_sleeve(df_qqq, q_sharpe_spec, k=2, k_keep=3, linear_cost=True)
    L_qqq_g1_4 = simulate_single_sleeve(df_qqq, q_sharpe_spec, k=2, k_keep=4, linear_cost=True)
    L_qqq_g1_5 = simulate_single_sleeve(df_qqq, q_sharpe_spec, k=2, k_keep=5, linear_cost=True)
    L_qqq_g1_6 = simulate_single_sleeve(df_qqq, q_sharpe_spec, k=2, k_keep=6, linear_cost=True)

    L_xlk_c3 = simulate_single_sleeve(df_xlk, x_raw_spec, k=1, k_keep=1, linear_cost=False)
    L_xlk_g2 = simulate_single_sleeve(df_xlk, x_raw_spec, k=1, k_keep=2, linear_cost=False)
    L_xlk_sh = simulate_single_sleeve(df_xlk, x_sharpe_spec, k=1, k_keep=1, linear_cost=False)
    L_xlk_a5 = simulate_single_sleeve(df_xlk, x_a5_spec, k=1, k_keep=1, linear_cost=False)

    # Controls: Core3 (QQQ Hard Top-2 + XLK Hard Top-1) & G1 (QQQ Hold<=5 + XLK Hard Top-1)
    L_ctrl_c3 = combine_sleeves([(L_qqq_c3, 0.50), (L_xlk_c3, 0.50)], ['qqq', 'xlk'])
    L_ctrl_g1 = combine_sleeves([(L_qqq_g1_5, 0.50), (L_xlk_c3, 0.50)], ['qqq', 'xlk'])
    r_ctrl_c3 = L_ctrl_c3['net']
    r_ctrl_g1 = L_ctrl_g1['net']

    master_rows = []
    standalone_rows = []
    all_series = {}
    saved_ledgers = {}

    def eval_portfolio(name, family, sleeves_w, utags, calc_daily=True):
        Lp = combine_sleeves(sleeves_w, utags)
        dd56, ddo2c = (np.nan, np.nan)
        if calc_daily:
            dd56, ddo2c = compute_daily_drawdowns(Lp, cal_days, spy_daily_c, spy_daily_o)
        row = summarize_ledger(name, family, Lp, rf_monthly, dd56, ddo2c, ref_r=r_ctrl_c3, ref_g1_r=r_ctrl_g1)
        master_rows.append(row)
        all_series[name] = Lp['net']
        saved_ledgers[name] = Lp
        print(f"  {name:<72} | CAGR={row['CAGR_09_26']*100:6.2f}% | M_DD={row['Monthly_MaxDD']*100:6.2f}% | "
              f"D_DD={dd56*100:6.2f}% | Sh={row['Sharpe']:4.2f} | 09-18={row['CAGR_2009_2018']*100:5.2f}% | "
              f"2022={row['Ret_2022']*100:6.2f}% | t_C3={row['NW_t_vs_Core3_Ctrl']:+5.2f}")
        return Lp, row

    def eval_single_sleeve(name, family, df_p, spec, k=1, k_keep=None, target_rank=None, utag='spy', linear_cost=False):
        Ls = simulate_single_sleeve(df_p, spec, k=k, k_keep=k_keep, target_rank=target_rank, linear_cost=linear_cost)
        Lp = combine_sleeves([(Ls, 1.0)], [utag])
        dd56, ddo2c = compute_daily_drawdowns(Lp, cal_days, spy_daily_c, spy_daily_o)
        row = summarize_ledger(name, family, Lp, rf_monthly, dd56, ddo2c, ref_r=L_xlk_c3['net'], ref_g1_r=L_qqq_c3['net'])
        standalone_rows.append(row)
        all_series[name] = Lp['net']
        print(f"  [Sleeve] {name:<63} | CAGR={row['CAGR_09_26']*100:6.2f}% | M_DD={row['Monthly_MaxDD']*100:6.2f}% | "
              f"D_DD={dd56*100:6.2f}% | Sh={row['Sharpe']:4.2f} | 09-18={row['CAGR_2009_2018']*100:5.2f}% | "
              f"2022={row['Ret_2022']*100:6.2f}%")
        return Ls, row

    # =========================================================================
    # SECTION 1: Standalone Sleeves (QQQ vs XLK vs SPY Across Variants)
    # =========================================================================
    print('\n--- [1] Standalone Sleeves: QQQ vs XLK vs Full S&P 500 (SPY) ---')
    eval_single_sleeve('S0a. QQQ Sharpe-Mom Top-2 [Hard Control]', '1. Standalone Control', df_qqq, q_sharpe_spec, k=2, k_keep=2, utag='qqq', linear_cost=True)
    eval_single_sleeve('S0b. QQQ Sharpe-Mom (Buy Top-2, Hold<=Top-5) [G1 Sleeve]', '1. Standalone Control', df_qqq, q_sharpe_spec, k=2, k_keep=5, utag='qqq', linear_cost=True)
    eval_single_sleeve('S0c. XLK Raw 12-1 Mom Top-1 [Hard Control]', '1. Standalone Control', df_xlk, x_raw_spec, k=1, k_keep=1, utag='xlk', linear_cost=False)
    eval_single_sleeve('S0d. XLK Raw 12-1 Mom (Buy Top-1, Hold<=Top-2)', '1. Standalone Control', df_xlk, x_raw_spec, k=1, k_keep=2, utag='xlk', linear_cost=False)
    eval_single_sleeve('S0e. XLK Sharpe-Mom Top-1 [Hard]', '1. Standalone Control', df_xlk, x_sharpe_spec, k=1, k_keep=1, utag='xlk', linear_cost=False)

    # SPY Raw 12-1 Momentum Standalone
    L_spy_raw_1, _ = eval_single_sleeve('S1a. SPY Raw 12-1 Mom Top-1 [Hard]', '1A. SPY Raw Mom', df_spy, s_raw_spec, k=1, k_keep=1, utag='spy')
    L_spy_raw_2, _ = eval_single_sleeve('S1b. SPY Raw 12-1 Mom Top-2 [Hard]', '1A. SPY Raw Mom', df_spy, s_raw_spec, k=2, k_keep=2, utag='spy')
    L_spy_raw_3, _ = eval_single_sleeve('S1c. SPY Raw 12-1 Mom Top-3 [Hard]', '1A. SPY Raw Mom', df_spy, s_raw_spec, k=3, k_keep=3, utag='spy')
    eval_single_sleeve('S1d. SPY Raw 12-1 Mom Rank #2 Alone', '1A. SPY Raw Mom', df_spy, s_raw_spec, k=1, target_rank=2, utag='spy')
    eval_single_sleeve('S1e. SPY Raw 12-1 Mom Rank #3 Alone', '1A. SPY Raw Mom', df_spy, s_raw_spec, k=1, target_rank=3, utag='spy')
    L_spy_raw_b2, _ = eval_single_sleeve('S1f. SPY Raw 12-1 Mom (Buy Top-1, Hold<=Top-2) [G1 Buffer]', '1A. SPY Raw Mom', df_spy, s_raw_spec, k=1, k_keep=2, utag='spy')
    L_spy_raw_b3, _ = eval_single_sleeve('S1g. SPY Raw 12-1 Mom (Buy Top-1, Hold<=Top-3) [G1 Buffer]', '1A. SPY Raw Mom', df_spy, s_raw_spec, k=1, k_keep=3, utag='spy')
    L_spy_raw_b5, _ = eval_single_sleeve('S1h. SPY Raw 12-1 Mom (Buy Top-2, Hold<=Top-5) [G1 Buffer]', '1A. SPY Raw Mom', df_spy, s_raw_spec, k=2, k_keep=5, utag='spy')

    # SPY Sharpe-Momentum Standalone
    L_spy_sh_1, _ = eval_single_sleeve('S2a. SPY Sharpe-Mom Top-1 [Hard]', '1B. SPY Sharpe-Mom', df_spy, s_sharpe_spec, k=1, k_keep=1, utag='spy')
    L_spy_sh_2, _ = eval_single_sleeve('S2b. SPY Sharpe-Mom Top-2 [Hard]', '1B. SPY Sharpe-Mom', df_spy, s_sharpe_spec, k=2, k_keep=2, utag='spy')
    L_spy_sh_3, _ = eval_single_sleeve('S2c. SPY Sharpe-Mom Top-3 [Hard]', '1B. SPY Sharpe-Mom', df_spy, s_sharpe_spec, k=3, k_keep=3, utag='spy')
    eval_single_sleeve('S2d. SPY Sharpe-Mom Rank #2 Alone', '1B. SPY Sharpe-Mom', df_spy, s_sharpe_spec, k=1, target_rank=2, utag='spy')
    eval_single_sleeve('S2e. SPY Sharpe-Mom Rank #3 Alone', '1B. SPY Sharpe-Mom', df_spy, s_sharpe_spec, k=1, target_rank=3, utag='spy')
    L_spy_sh_b2, _ = eval_single_sleeve('S2f. SPY Sharpe-Mom (Buy Top-1, Hold<=Top-2) [G1 Buffer]', '1B. SPY Sharpe-Mom', df_spy, s_sharpe_spec, k=1, k_keep=2, utag='spy')
    L_spy_sh_b3, _ = eval_single_sleeve('S2g. SPY Sharpe-Mom (Buy Top-1, Hold<=Top-3) [G1 Buffer]', '1B. SPY Sharpe-Mom', df_spy, s_sharpe_spec, k=1, k_keep=3, utag='spy')
    L_spy_sh_b5, _ = eval_single_sleeve('S2h. SPY Sharpe-Mom (Buy Top-2, Hold<=Top-5) [G1 Buffer]', '1B. SPY Sharpe-Mom', df_spy, s_sharpe_spec, k=2, k_keep=5, utag='spy')

    # SPY Sector-Rotation & Ex-IT & Jump-Veto Standalone
    L_spy_sec_1, _ = eval_single_sleeve('S3a. SPY Best-Sector (EW Mom) -> Top-1 Stock [SPEC, Hard]', '1C. SPY Sector/Veto', df_spy, s_sec_raw_spec, k=1, k_keep=1, utag='spy')
    L_spy_sec_b2, _ = eval_single_sleeve('S3b. SPY Best-Sector -> Top-1 Stock (Hold<=Top-2)', '1C. SPY Sector/Veto', df_spy, s_sec_raw_spec, k=1, k_keep=2, utag='spy')
    L_spy_sec_sh, _ = eval_single_sleeve('S3c. SPY Best-Sector (EW Sharpe) -> Top-1 Sharpe Stock', '1C. SPY Sector/Veto', df_spy, s_sec_sh_spec, k=1, k_keep=1, utag='spy')
    L_spy_sec2, _ = eval_single_sleeve('S3d. SPY Top-2 Sectors -> Top-1 Stock Each', '1C. SPY Sector/Veto', df_spy, s_sec2_raw_spec, k=2, k_keep=2, utag='spy')
    L_spy_exit_raw, _ = eval_single_sleeve('S3e. SPY Ex-IT (10 Non-Tech Sectors) Raw Mom Top-1', '1C. SPY Sector/Veto', df_spy, s_exit_raw_spec, k=1, k_keep=1, utag='spy')
    L_spy_exit_sh, _ = eval_single_sleeve('S3f. SPY Ex-IT (10 Non-Tech Sectors) Sharpe-Mom Top-1', '1C. SPY Sector/Veto', df_spy, s_exit_sh_spec, k=1, k_keep=1, utag='spy')
    L_spy_a5_raw, _ = eval_single_sleeve('S3g. SPY Raw Mom Top-1 + A5 Anti-Jump Veto (5d<35%)', '1C. SPY Sector/Veto', df_spy, s_a5_raw_spec, k=1, k_keep=1, utag='spy')
    L_spy_a5_sh, _ = eval_single_sleeve('S3h. SPY Sharpe-Mom Top-1 + A5 Anti-Jump Veto (5d<35%)', '1C. SPY Sector/Veto', df_spy, s_a5_sh_spec, k=1, k_keep=1, utag='spy')
    L_spy_fip_raw, _ = eval_single_sleeve('S3i. SPY Raw Mom Top-5 -> FIP Smooth Top-1', '1C. SPY Sector/Veto', df_spy, s_fip_raw_spec, k=1, k_keep=1, utag='spy')
    L_spy_fip_sh, _ = eval_single_sleeve('S3j. SPY Sharpe-Mom Top-5 -> FIP Smooth Top-1', '1C. SPY Sector/Veto', df_spy, s_fip_sh_spec, k=1, k_keep=1, utag='spy')

    # =========================================================================
    # SECTION 2: QQQ + XLK Controls (Core3 & G1 Grid)
    # =========================================================================
    print('\n--- [2] Controls: QQQ + XLK Under Core3 (Hard) and G1 (Buffer Grid) ---')
    eval_portfolio('00a. Core3 Control: 50% QQQ Sharpe Top-2 [Hard] + 50% XLK Raw Top-1 [Hard]', '0. QQQ+XLK Control',
                   [(L_qqq_c3, 0.50), (L_xlk_c3, 0.50)], ['qqq', 'xlk'])
    eval_portfolio('00b. G1 Control: 50% QQQ (Buy 2, Hold<=5) + 50% XLK Raw Top-1 [Hard]', '0. QQQ+XLK Control',
                   [(L_qqq_g1_5, 0.50), (L_xlk_c3, 0.50)], ['qqq', 'xlk'])
    eval_portfolio('00c. G1 (QQQ Hold<=3) + XLK Hard Top-1', '0. QQQ+XLK Control',
                   [(L_qqq_g1_3, 0.50), (L_xlk_c3, 0.50)], ['qqq', 'xlk'])
    eval_portfolio('00d. G1 (QQQ Hold<=4) + XLK Hard Top-1', '0. QQQ+XLK Control',
                   [(L_qqq_g1_4, 0.50), (L_xlk_c3, 0.50)], ['qqq', 'xlk'])
    eval_portfolio('00e. G1 (QQQ Hold<=6) + XLK Hard Top-1', '0. QQQ+XLK Control',
                   [(L_qqq_g1_6, 0.50), (L_xlk_c3, 0.50)], ['qqq', 'xlk'])
    eval_portfolio('00f. G1-Both: 50% QQQ (Buy 2, Hold<=5) + 50% XLK (Buy 1, Hold<=2)', '0. QQQ+XLK Control',
                   [(L_qqq_g1_5, 0.50), (L_xlk_g2, 0.50)], ['qqq', 'xlk'])

    # =========================================================================
    # SECTION 3: QQQ + SPY Under Core3 (Hard Cutoff)
    # =========================================================================
    print('\n--- [3] QQQ + SPY Under Core3 (Hard Cutoff) ---')
    eval_portfolio('C3_SPY_1a. Core3 + SPY Raw Mom Top-1 (50% QQQ Hard Top-2 + 50% SPY Raw Top-1)', '2A. Core3 QQQ+SPY',
                   [(L_qqq_c3, 0.50), (L_spy_raw_1, 0.50)], ['qqq', 'spy'])
    eval_portfolio('C3_SPY_1b. Core3 + SPY Raw Mom Top-2 (50% QQQ Hard Top-2 + 50% SPY Raw Top-2)', '2A. Core3 QQQ+SPY',
                   [(L_qqq_c3, 0.50), (L_spy_raw_2, 0.50)], ['qqq', 'spy'])
    eval_portfolio('C3_SPY_1c. Core3 + SPY Sharpe-Mom Top-1 (50% QQQ Hard Top-2 + 50% SPY Sharpe Top-1)', '2A. Core3 QQQ+SPY',
                   [(L_qqq_c3, 0.50), (L_spy_sh_1, 0.50)], ['qqq', 'spy'])
    eval_portfolio('C3_SPY_1d. Core3 + SPY Sharpe-Mom Top-2 (50% QQQ Hard Top-2 + 50% SPY Sharpe Top-2)', '2A. Core3 QQQ+SPY',
                   [(L_qqq_c3, 0.50), (L_spy_sh_2, 0.50)], ['qqq', 'spy'])
    eval_portfolio('C3_SPY_1e. Core3 + SPY Best-Sector->Top-1 Stock [SPEC] (50/50)', '2A. Core3 QQQ+SPY',
                   [(L_qqq_c3, 0.50), (L_spy_sec_1, 0.50)], ['qqq', 'spy'])
    eval_portfolio('C3_SPY_1f. Core3 + SPY Best-Sector(Sharpe)->Top-1 Sharpe Stock (50/50)', '2A. Core3 QQQ+SPY',
                   [(L_qqq_c3, 0.50), (L_spy_sec_sh, 0.50)], ['qqq', 'spy'])
    eval_portfolio('C3_SPY_1g. Core3 + SPY Top-2 Sectors->Top-1 Stock Each (50/50)', '2A. Core3 QQQ+SPY',
                   [(L_qqq_c3, 0.50), (L_spy_sec2, 0.50)], ['qqq', 'spy'])
    eval_portfolio('C3_SPY_1h. Core3 + SPY Raw Mom Top-1 + A5 Jump Veto (50/50)', '2A. Core3 QQQ+SPY',
                   [(L_qqq_c3, 0.50), (L_spy_a5_raw, 0.50)], ['qqq', 'spy'])
    eval_portfolio('C3_SPY_1i. Core3 + SPY Sharpe-Mom Top-1 + A5 Jump Veto (50/50)', '2A. Core3 QQQ+SPY',
                   [(L_qqq_c3, 0.50), (L_spy_a5_sh, 0.50)], ['qqq', 'spy'])
    eval_portfolio('C3_SPY_1j. Core3 + SPY Raw Top-5->FIP Smooth Top-1 (50/50)', '2A. Core3 QQQ+SPY',
                   [(L_qqq_c3, 0.50), (L_spy_fip_raw, 0.50)], ['qqq', 'spy'])
    eval_portfolio('C3_SPY_1k. Core3 + SPY Sharpe Top-5->FIP Smooth Top-1 (50/50)', '2A. Core3 QQQ+SPY',
                   [(L_qqq_c3, 0.50), (L_spy_fip_sh, 0.50)], ['qqq', 'spy'])
    eval_portfolio('C3_SPY_1l. Core3 + SPY Ex-IT (Non-Tech) Raw Mom Top-1 (50/50)', '2A. Core3 QQQ+SPY',
                   [(L_qqq_c3, 0.50), (L_spy_exit_raw, 0.50)], ['qqq', 'spy'])
    eval_portfolio('C3_SPY_1m. Core3 + SPY Ex-IT (Non-Tech) Sharpe-Mom Top-1 (50/50)', '2A. Core3 QQQ+SPY',
                   [(L_qqq_c3, 0.50), (L_spy_exit_sh, 0.50)], ['qqq', 'spy'])

    # =========================================================================
    # SECTION 4: QQQ + SPY Under G1 (Buy-Hold Buffer)
    # =========================================================================
    print('\n--- [4] QQQ + SPY Under G1 (Buy-Hold Hysteresis Buffer) ---')
    # 4A. G1 on QQQ (Hold<=5) + SPY Hard Top-1/Top-2
    eval_portfolio('G1_SPY_1a. G1 QQQ(Hold<=5) + SPY Raw Mom Hard Top-1 (50/50)', '2B. G1 QQQ+SPY',
                   [(L_qqq_g1_5, 0.50), (L_spy_raw_1, 0.50)], ['qqq', 'spy'])
    eval_portfolio('G1_SPY_1b. G1 QQQ(Hold<=5) + SPY Raw Mom Hard Top-2 (50/50)', '2B. G1 QQQ+SPY',
                   [(L_qqq_g1_5, 0.50), (L_spy_raw_2, 0.50)], ['qqq', 'spy'])
    eval_portfolio('G1_SPY_1c. G1 QQQ(Hold<=5) + SPY Sharpe-Mom Hard Top-1 (50/50)', '2B. G1 QQQ+SPY',
                   [(L_qqq_g1_5, 0.50), (L_spy_sh_1, 0.50)], ['qqq', 'spy'])
    eval_portfolio('G1_SPY_1d. G1 QQQ(Hold<=5) + SPY Sharpe-Mom Hard Top-2 (50/50)', '2B. G1 QQQ+SPY',
                   [(L_qqq_g1_5, 0.50), (L_spy_sh_2, 0.50)], ['qqq', 'spy'])
    eval_portfolio('G1_SPY_1e. G1 QQQ(Hold<=5) + SPY Best-Sector->Top-1 Stock [SPEC] (50/50)', '2B. G1 QQQ+SPY',
                   [(L_qqq_g1_5, 0.50), (L_spy_sec_1, 0.50)], ['qqq', 'spy'])
    eval_portfolio('G1_SPY_1f. G1 QQQ(Hold<=5) + SPY Best-Sector(Sharpe)->Top-1 Sharpe Stock (50/50)', '2B. G1 QQQ+SPY',
                   [(L_qqq_g1_5, 0.50), (L_spy_sec_sh, 0.50)], ['qqq', 'spy'])
    eval_portfolio('G1_SPY_1g. G1 QQQ(Hold<=5) + SPY Raw Top-1 + A5 Jump Veto (50/50)', '2B. G1 QQQ+SPY',
                   [(L_qqq_g1_5, 0.50), (L_spy_a5_raw, 0.50)], ['qqq', 'spy'])
    eval_portfolio('G1_SPY_1h. G1 QQQ(Hold<=5) + SPY Sharpe Top-1 + A5 Jump Veto (50/50)', '2B. G1 QQQ+SPY',
                   [(L_qqq_g1_5, 0.50), (L_spy_a5_sh, 0.50)], ['qqq', 'spy'])
    eval_portfolio('G1_SPY_1i. G1 QQQ(Hold<=5) + SPY Raw Top-5->FIP Smooth Top-1 (50/50)', '2B. G1 QQQ+SPY',
                   [(L_qqq_g1_5, 0.50), (L_spy_fip_raw, 0.50)], ['qqq', 'spy'])
    eval_portfolio('G1_SPY_1j. G1 QQQ(Hold<=5) + SPY Sharpe Top-5->FIP Smooth Top-1 (50/50)', '2B. G1 QQQ+SPY',
                   [(L_qqq_g1_5, 0.50), (L_spy_fip_sh, 0.50)], ['qqq', 'spy'])

    # 4B. G1 Buffer Neighborhood Grid on QQQ + SPY (K_keep in {3, 4, 5, 6} x SPY M_keep in {1, 2, 3})
    eval_portfolio('G1_SPY_2a. G1 Grid: QQQ(Hold<=3) + SPY Raw Hard Top-1', '2C. G1 QQQ+SPY Grid',
                   [(L_qqq_g1_3, 0.50), (L_spy_raw_1, 0.50)], ['qqq', 'spy'])
    eval_portfolio('G1_SPY_2b. G1 Grid: QQQ(Hold<=4) + SPY Raw Hard Top-1', '2C. G1 QQQ+SPY Grid',
                   [(L_qqq_g1_4, 0.50), (L_spy_raw_1, 0.50)], ['qqq', 'spy'])
    eval_portfolio('G1_SPY_2c. G1 Grid: QQQ(Hold<=6) + SPY Raw Hard Top-1', '2C. G1 QQQ+SPY Grid',
                   [(L_qqq_g1_6, 0.50), (L_spy_raw_1, 0.50)], ['qqq', 'spy'])
    eval_portfolio('G1_SPY_2d. G1-Both: QQQ(Hold<=5) + SPY Raw (Buy 1, Hold<=2)', '2C. G1 QQQ+SPY Grid',
                   [(L_qqq_g1_5, 0.50), (L_spy_raw_b2, 0.50)], ['qqq', 'spy'])
    eval_portfolio('G1_SPY_2e. G1-Both: QQQ(Hold<=5) + SPY Raw (Buy 1, Hold<=3)', '2C. G1 QQQ+SPY Grid',
                   [(L_qqq_g1_5, 0.50), (L_spy_raw_b3, 0.50)], ['qqq', 'spy'])
    eval_portfolio('G1_SPY_2f. G1-Both: QQQ(Hold<=5) + SPY Raw (Buy 2, Hold<=5)', '2C. G1 QQQ+SPY Grid',
                   [(L_qqq_g1_5, 0.50), (L_spy_raw_b5, 0.50)], ['qqq', 'spy'])
    eval_portfolio('G1_SPY_2g. G1-Both: QQQ(Hold<=5) + SPY Sharpe (Buy 1, Hold<=2)', '2C. G1 QQQ+SPY Grid',
                   [(L_qqq_g1_5, 0.50), (L_spy_sh_b2, 0.50)], ['qqq', 'spy'])
    eval_portfolio('G1_SPY_2h. G1-Both: QQQ(Hold<=5) + SPY Sharpe (Buy 1, Hold<=3)', '2C. G1 QQQ+SPY Grid',
                   [(L_qqq_g1_5, 0.50), (L_spy_sh_b3, 0.50)], ['qqq', 'spy'])
    eval_portfolio('G1_SPY_2i. G1-Both: QQQ(Hold<=5) + SPY Sharpe (Buy 2, Hold<=5)', '2C. G1 QQQ+SPY Grid',
                   [(L_qqq_g1_5, 0.50), (L_spy_sh_b5, 0.50)], ['qqq', 'spy'])
    eval_portfolio('G1_SPY_2j. G1-Both: QQQ(Hold<=5) + SPY Best-Sector->Stock (Hold<=2)', '2C. G1 QQQ+SPY Grid',
                   [(L_qqq_g1_5, 0.50), (L_spy_sec_b2, 0.50)], ['qqq', 'spy'])

    # 4C. Weight Sensitivity for QQQ + SPY (75/25 vs 50/50 vs 25/75)
    eval_portfolio('G1_SPY_3a. Weight 75/25: 75% QQQ(Hold<=5) + 25% SPY Raw Top-1', '2D. QQQ+SPY Weights',
                   [(L_qqq_g1_5, 0.75), (L_spy_raw_1, 0.25)], ['qqq', 'spy'])
    eval_portfolio('G1_SPY_3b. Weight 25/75: 25% QQQ(Hold<=5) + 75% SPY Raw Top-1', '2D. QQQ+SPY Weights',
                   [(L_qqq_g1_5, 0.25), (L_spy_raw_1, 0.75)], ['qqq', 'spy'])
    eval_portfolio('G1_SPY_3c. Weight 75/25: 75% QQQ(Hold<=5) + 25% SPY Sharpe Top-1', '2D. QQQ+SPY Weights',
                   [(L_qqq_g1_5, 0.75), (L_spy_sh_1, 0.25)], ['qqq', 'spy'])

    # =========================================================================
    # SECTION 5: 3-Sleeve Combinations (QQQ + XLK + SPY) Under Core3 & G1
    # =========================================================================
    print('\n--- [5] 3-Sleeve Combinations: QQQ + XLK + SPY Under Core3 and G1 ---')
    # Under Core3 (Hard Cutoff)
    eval_portfolio('3S_C3_1a. Core3 3-Sleeve (50% QQQ + 25% XLK + 25% SPY Raw Top-1)', '3A. 3-Sleeve Core3',
                   [(L_qqq_c3, 0.50), (L_xlk_c3, 0.25), (L_spy_raw_1, 0.25)], ['qqq', 'xlk', 'spy'])
    eval_portfolio('3S_C3_1b. Core3 3-Sleeve (50% QQQ + 25% XLK + 25% SPY Sharpe Top-1)', '3A. 3-Sleeve Core3',
                   [(L_qqq_c3, 0.50), (L_xlk_c3, 0.25), (L_spy_sh_1, 0.25)], ['qqq', 'xlk', 'spy'])
    eval_portfolio('3S_C3_1c. Core3 3-Sleeve (50% QQQ + 25% XLK + 25% SPY Best-Sector->Stock)', '3A. 3-Sleeve Core3',
                   [(L_qqq_c3, 0.50), (L_xlk_c3, 0.25), (L_spy_sec_1, 0.25)], ['qqq', 'xlk', 'spy'])
    eval_portfolio('3S_C3_1d. Core3 3-Sleeve (50% QQQ + 25% XLK + 25% SPY Ex-IT Raw Top-1)', '3A. 3-Sleeve Core3',
                   [(L_qqq_c3, 0.50), (L_xlk_c3, 0.25), (L_spy_exit_raw, 0.25)], ['qqq', 'xlk', 'spy'])
    eval_portfolio('3S_C3_1e. Core3 3-Sleeve Equal (33.3% QQQ + 33.3% XLK + 33.3% SPY Raw Top-1)', '3A. 3-Sleeve Core3',
                   [(L_qqq_c3, 1.0/3), (L_xlk_c3, 1.0/3), (L_spy_raw_1, 1.0/3)], ['qqq', 'xlk', 'spy'])

    # Under G1 (QQQ Hold<=5)
    eval_portfolio('3S_G1_1a. G1 3-Sleeve (50% QQQ[Hold<=5] + 25% XLK + 25% SPY Raw Top-1)', '3B. 3-Sleeve G1',
                   [(L_qqq_g1_5, 0.50), (L_xlk_c3, 0.25), (L_spy_raw_1, 0.25)], ['qqq', 'xlk', 'spy'])
    eval_portfolio('3S_G1_1b. G1 3-Sleeve (50% QQQ[Hold<=5] + 25% XLK + 25% SPY Sharpe Top-1)', '3B. 3-Sleeve G1',
                   [(L_qqq_g1_5, 0.50), (L_xlk_c3, 0.25), (L_spy_sh_1, 0.25)], ['qqq', 'xlk', 'spy'])
    eval_portfolio('3S_G1_1c. G1 3-Sleeve (50% QQQ[Hold<=5] + 25% XLK + 25% SPY Best-Sector->Stock)', '3B. 3-Sleeve G1',
                   [(L_qqq_g1_5, 0.50), (L_xlk_c3, 0.25), (L_spy_sec_1, 0.25)], ['qqq', 'xlk', 'spy'])
    eval_portfolio('3S_G1_1d. G1 3-Sleeve (50% QQQ[Hold<=5] + 25% XLK + 25% SPY Ex-IT Raw Top-1)', '3B. 3-Sleeve G1',
                   [(L_qqq_g1_5, 0.50), (L_xlk_c3, 0.25), (L_spy_exit_raw, 0.25)], ['qqq', 'xlk', 'spy'])
    eval_portfolio('3S_G1_1e. G1 3-Sleeve (50% QQQ[Hold<=5] + 25% XLK + 25% SPY Raw+A5 Veto)', '3B. 3-Sleeve G1',
                   [(L_qqq_g1_5, 0.50), (L_xlk_c3, 0.25), (L_spy_a5_raw, 0.25)], ['qqq', 'xlk', 'spy'])
    eval_portfolio('3S_G1_1f. G1 3-Sleeve Equal (33.3% QQQ[Hold<=5] + 33.3% XLK + 33.3% SPY Raw Top-1)', '3B. 3-Sleeve G1',
                   [(L_qqq_g1_5, 1.0/3), (L_xlk_c3, 1.0/3), (L_spy_raw_1, 1.0/3)], ['qqq', 'xlk', 'spy'])
    eval_portfolio('3S_G1_1g. G1 3-Sleeve Equal (33.3% QQQ[Hold<=5] + 33.3% XLK + 33.3% SPY Sharpe Top-1)', '3B. 3-Sleeve G1',
                   [(L_qqq_g1_5, 1.0/3), (L_xlk_c3, 1.0/3), (L_spy_sh_1, 1.0/3)], ['qqq', 'xlk', 'spy'])
    eval_portfolio('3S_G1_1h. G1 3-Sleeve (40% QQQ[Hold<=5] + 40% XLK + 20% SPY Raw Top-1)', '3B. 3-Sleeve G1',
                   [(L_qqq_g1_5, 0.40), (L_xlk_c3, 0.40), (L_spy_raw_1, 0.20)], ['qqq', 'xlk', 'spy'])
    eval_portfolio('3S_G1_1i. G1 3-Sleeve (40% QQQ[Hold<=5] + 40% XLK + 20% SPY Best-Sector->Stock)', '3B. 3-Sleeve G1',
                   [(L_qqq_g1_5, 0.40), (L_xlk_c3, 0.40), (L_spy_sec_1, 0.20)], ['qqq', 'xlk', 'spy'])
    eval_portfolio('3S_G1_1j. G1 3-Sleeve (50% QQQ[Hold<=5] + 25% XLK + 25% SPY Raw[Hold<=2])', '3B. 3-Sleeve G1',
                   [(L_qqq_g1_5, 0.50), (L_xlk_c3, 0.25), (L_spy_raw_b2, 0.25)], ['qqq', 'xlk', 'spy'])
    eval_portfolio('3S_G1_1k. G1 3-Sleeve (50% QQQ[Hold<=5] + 25% XLK + 25% SPY Raw[Hold<=3])', '3B. 3-Sleeve G1',
                   [(L_qqq_g1_5, 0.50), (L_xlk_c3, 0.25), (L_spy_raw_b3, 0.25)], ['qqq', 'xlk', 'spy'])

    # Save tables 01 and 02
    df_standalone = pd.DataFrame(standalone_rows)
    df_standalone.to_csv(os.path.join(HERE, '01_standalone_sleeves_comparison.csv'), index=False)
    df_master = pd.DataFrame(master_rows)
    df_master.to_csv(os.path.join(HERE, '02_all_qqq_spy_xlk_combinations.csv'), index=False)

    # =========================================================================
    # SECTION 6: Forensic Attribution — SPY vs XLK Sector & Overlap Analysis
    # =========================================================================
    print('\n--- [6] Forensic Sector & Overlap Attribution: SPY Top-1 vs XLK Top-1 ---')
    comp_rows = []
    for ym in L_xlk_c3.index:
        q_c3_pks = L_qqq_c3.at[ym, 'picks'].split('|')
        q_g1_pks = L_qqq_g1_5.at[ym, 'picks'].split('|')
        x_pk = L_xlk_c3.at[ym, 'picks']
        s_raw_pk = L_spy_raw_1.at[ym, 'picks']
        s_raw_sec = L_spy_raw_1.at[ym, 'sectors']
        s_sh_pk = L_spy_sh_1.at[ym, 'picks']
        s_sh_sec = L_spy_sh_1.at[ym, 'sectors']
        s_sec_pk = L_spy_sec_1.at[ym, 'picks']
        s_sec_sec = L_spy_sec_1.at[ym, 'sectors']

        comp_rows.append({
            'ym': ym,
            'qqq_c3_picks': '|'.join(q_c3_pks),
            'qqq_g1_picks': '|'.join(q_g1_pks),
            'xlk_pick': x_pk,
            'xlk_net': float(L_xlk_c3.at[ym, 'net']),
            'spy_raw_pick': s_raw_pk,
            'spy_raw_sector': s_raw_sec,
            'spy_raw_net': float(L_spy_raw_1.at[ym, 'net']),
            'spy_same_as_xlk': (s_raw_pk == x_pk),
            'spy_sh_pick': s_sh_pk,
            'spy_sh_sector': s_sh_sec,
            'spy_sh_net': float(L_spy_sh_1.at[ym, 'net']),
            'spy_sec_pick': s_sec_pk,
            'spy_sec_sector': s_sec_sec,
            'spy_sec_net': float(L_spy_sec_1.at[ym, 'net']),
            'spy_raw_in_qqq_c3': (s_raw_pk in q_c3_pks),
            'xlk_in_qqq_c3': (x_pk in q_c3_pks),
        })
    df_comp = pd.DataFrame(comp_rows)
    df_comp.to_csv(os.path.join(HERE, '03_monthly_spy_vs_xlk_picks.csv'), index=False)

    # Sector breakdown of SPY Raw Top-1, SPY Sharpe Top-1, and SPY Sector-Rotation Top-1
    sec_bd_rows = []
    for s_label, pk_col, sec_col, ret_col in [
        ('SPY Raw 12-1 Mom Top-1', 'spy_raw_pick', 'spy_raw_sector', 'spy_raw_net'),
        ('SPY Sharpe-Mom Top-1', 'spy_sh_pick', 'spy_sh_sector', 'spy_sh_net'),
        ('SPY Best-Sector -> Top-1 Stock', 'spy_sec_pick', 'spy_sec_sector', 'spy_sec_net'),
    ]:
        for sec_name, g_sec in df_comp.groupby(sec_col):
            r_vals = g_sec[ret_col].values
            r_xlk_vals = g_sec['xlk_net'].values
            sec_bd_rows.append({
                'Sleeve_Variant': s_label,
                'GICS_Sector': sec_name,
                'Months_Picked': len(g_sec),
                'Share_of_213_Months': len(g_sec) / len(df_comp),
                'Mean_Monthly_Net_Ret': float(np.mean(r_vals)),
                'Median_Monthly_Net_Ret': float(np.median(r_vals)),
                'Win_Rate': float(np.mean(r_vals > 0)),
                'XLK_Mean_Monthly_Ret_Same_Months': float(np.mean(r_xlk_vals)),
                'Active_Mean_Diff_vs_XLK': float(np.mean(r_vals - r_xlk_vals)),
                'Top_Example_Tickers': ', '.join(g_sec[pk_col].value_counts().head(4).index.tolist()),
            })
    df_sec_bd = pd.DataFrame(sec_bd_rows).sort_values(['Sleeve_Variant', 'Months_Picked'], ascending=[True, False])
    df_sec_bd.to_csv(os.path.join(HERE, '04_spy_sector_attribution.csv'), index=False)

    # Sleeve correlation matrix
    corr_df = pd.DataFrame({
        'QQQ_Sharpe_Top2_Hard': L_qqq_c3['net'],
        'QQQ_Sharpe_G1_Hold5': L_qqq_g1_5['net'],
        'XLK_Raw_Top1': L_xlk_c3['net'],
        'SPY_Raw_Top1': L_spy_raw_1['net'],
        'SPY_Sharpe_Top1': L_spy_sh_1['net'],
        'SPY_Sector_Top1': L_spy_sec_1['net'],
        'SPY_ExIT_Raw_Top1': L_spy_exit_raw['net'],
    }).corr()
    corr_df.to_csv(os.path.join(HERE, '05_sleeve_correlation_matrix.csv'))

    same_cnt = int(df_comp['spy_same_as_xlk'].sum())
    diff_df = df_comp[~df_comp['spy_same_as_xlk']]
    print(f"  SPY Raw Top-1 picks the EXACT SAME stock as XLK Top-1 in {same_cnt}/213 months ({same_cnt/213*100:.1f}%)!")
    print(f"  In the {len(diff_df)} months where SPY Raw Top-1 != XLK Top-1 (non-IT leader): "
          f"SPY mean={diff_df['spy_raw_net'].mean()*100:+.2f}%/mo vs XLK mean={diff_df['xlk_net'].mean()*100:+.2f}%/mo")
    print(f"  Correlations with QQQ(G1): XLK={corr_df.loc['QQQ_Sharpe_G1_Hold5','XLK_Raw_Top1']:.3f}, "
          f"SPY_Raw={corr_df.loc['QQQ_Sharpe_G1_Hold5','SPY_Raw_Top1']:.3f}, "
          f"SPY_Sharpe={corr_df.loc['QQQ_Sharpe_G1_Hold5','SPY_Sharpe_Top1']:.3f}, "
          f"SPY_Sector={corr_df.loc['QQQ_Sharpe_G1_Hold5','SPY_Sector_Top1']:.3f}, "
          f"SPY_ExIT={corr_df.loc['QQQ_Sharpe_G1_Hold5','SPY_ExIT_Raw_Top1']:.3f}")

    # =========================================================================
    # SECTION 7: Leave-One-Winner-Out & Remove Top-5 Months Stress Tests
    # =========================================================================
    print('\n--- [7] Leave-One-Winner-Out & Remove Top-5 Months Stress Tests ---')
    key_configs = [
        ('00a. Core3 Control (QQQ Hard + XLK Hard)',
         lambda ex: combine_sleeves([
             (simulate_single_sleeve(df_qqq, q_sharpe_spec, k=2, k_keep=2, linear_cost=True, exclude_tickers=ex), 0.50),
             (simulate_single_sleeve(df_xlk, x_raw_spec, k=1, k_keep=1, linear_cost=False, exclude_tickers=ex), 0.50)
         ], ['qqq', 'xlk'])),
        ('00b. G1 Control (QQQ Hold<=5 + XLK Hard)',
         lambda ex: combine_sleeves([
             (simulate_single_sleeve(df_qqq, q_sharpe_spec, k=2, k_keep=5, linear_cost=True, exclude_tickers=ex), 0.50),
             (simulate_single_sleeve(df_xlk, x_raw_spec, k=1, k_keep=1, linear_cost=False, exclude_tickers=ex), 0.50)
         ], ['qqq', 'xlk'])),
        ('C3_SPY_1a. Core3 + SPY Raw Top-1',
         lambda ex: combine_sleeves([
             (simulate_single_sleeve(df_qqq, q_sharpe_spec, k=2, k_keep=2, linear_cost=True, exclude_tickers=ex), 0.50),
             (simulate_single_sleeve(df_spy, s_raw_spec, k=1, k_keep=1, linear_cost=False, exclude_tickers=ex), 0.50)
         ], ['qqq', 'spy'])),
        ('C3_SPY_1c. Core3 + SPY Sharpe Top-1',
         lambda ex: combine_sleeves([
             (simulate_single_sleeve(df_qqq, q_sharpe_spec, k=2, k_keep=2, linear_cost=True, exclude_tickers=ex), 0.50),
             (simulate_single_sleeve(df_spy, s_sharpe_spec, k=1, k_keep=1, linear_cost=False, exclude_tickers=ex), 0.50)
         ], ['qqq', 'spy'])),
        ('G1_SPY_1a. G1 QQQ(Hold<=5) + SPY Raw Top-1',
         lambda ex: combine_sleeves([
             (simulate_single_sleeve(df_qqq, q_sharpe_spec, k=2, k_keep=5, linear_cost=True, exclude_tickers=ex), 0.50),
             (simulate_single_sleeve(df_spy, s_raw_spec, k=1, k_keep=1, linear_cost=False, exclude_tickers=ex), 0.50)
         ], ['qqq', 'spy'])),
        ('G1_SPY_1c. G1 QQQ(Hold<=5) + SPY Sharpe Top-1',
         lambda ex: combine_sleeves([
             (simulate_single_sleeve(df_qqq, q_sharpe_spec, k=2, k_keep=5, linear_cost=True, exclude_tickers=ex), 0.50),
             (simulate_single_sleeve(df_spy, s_sharpe_spec, k=1, k_keep=1, linear_cost=False, exclude_tickers=ex), 0.50)
         ], ['qqq', 'spy'])),
        ('G1_SPY_2d. G1-Both QQQ(Hold<=5) + SPY Raw(Hold<=2)',
         lambda ex: combine_sleeves([
             (simulate_single_sleeve(df_qqq, q_sharpe_spec, k=2, k_keep=5, linear_cost=True, exclude_tickers=ex), 0.50),
             (simulate_single_sleeve(df_spy, s_raw_spec, k=1, k_keep=2, linear_cost=False, exclude_tickers=ex), 0.50)
         ], ['qqq', 'spy'])),
        ('G1_SPY_2e. G1-Both QQQ(Hold<=5) + SPY Raw(Hold<=3)',
         lambda ex: combine_sleeves([
             (simulate_single_sleeve(df_qqq, q_sharpe_spec, k=2, k_keep=5, linear_cost=True, exclude_tickers=ex), 0.50),
             (simulate_single_sleeve(df_spy, s_raw_spec, k=1, k_keep=3, linear_cost=False, exclude_tickers=ex), 0.50)
         ], ['qqq', 'spy'])),
        ('3S_G1_1a. G1 3-Sleeve (50% QQQ[Hold<=5] + 25% XLK + 25% SPY Raw)',
         lambda ex: combine_sleeves([
             (simulate_single_sleeve(df_qqq, q_sharpe_spec, k=2, k_keep=5, linear_cost=True, exclude_tickers=ex), 0.50),
             (simulate_single_sleeve(df_xlk, x_raw_spec, k=1, k_keep=1, linear_cost=False, exclude_tickers=ex), 0.25),
             (simulate_single_sleeve(df_spy, s_raw_spec, k=1, k_keep=1, linear_cost=False, exclude_tickers=ex), 0.25)
         ], ['qqq', 'xlk', 'spy'])),
        ('3S_G1_1k. G1 3-Sleeve (50% QQQ[Hold<=5] + 25% XLK + 25% SPY Raw[Hold<=3])',
         lambda ex: combine_sleeves([
             (simulate_single_sleeve(df_qqq, q_sharpe_spec, k=2, k_keep=5, linear_cost=True, exclude_tickers=ex), 0.50),
             (simulate_single_sleeve(df_xlk, x_raw_spec, k=1, k_keep=1, linear_cost=False, exclude_tickers=ex), 0.25),
             (simulate_single_sleeve(df_spy, s_raw_spec, k=1, k_keep=3, linear_cost=False, exclude_tickers=ex), 0.25)
         ], ['qqq', 'xlk', 'spy'])),
    ]

    lowo_rows = []
    for label, fn_sim in key_configs:
        L_full = fn_sim(None)
        r_f = L_full['net'].values
        cagr_full = float((np.prod(1.0 + r_f)) ** (12.0 / len(r_f)) - 1.0)
        # Drop top 5 months
        r_sorted = np.sort(r_f)
        cagr_ex5m = float((np.prod(1.0 + r_sorted[:-5])) ** (12.0 / len(r_f)) - 1.0)

        row_l = {'Variant': label, 'Full_CAGR': cagr_full, 'Ex_Top5_Months_CAGR': cagr_ex5m}
        for ban_name, ban_set in [
            ('No_NVDA', {'NVDA'}),
            ('No_SNDK', {'SNDK'}),
            ('No_PLTR', {'PLTR'}),
            ('No_DVN', {'DVN'}),
            ('No_VST', {'VST'}),
            ('No_Top3_NVDA_SNDK_PLTR', {'NVDA', 'SNDK', 'PLTR'}),
        ]:
            L_b = fn_sim(ban_set)
            rb = L_b['net'].values
            row_l[ban_name] = float((np.prod(1.0 + rb)) ** (12.0 / len(rb)) - 1.0)
        lowo_rows.append(row_l)
        print(f"  {label:<54} | Full={row_l['Full_CAGR']*100:5.2f}% | NoNVDA={row_l['No_NVDA']*100:5.2f}% | "
              f"NoSNDK={row_l['No_SNDK']*100:5.2f}% | NoTop3={row_l['No_Top3_NVDA_SNDK_PLTR']*100:5.2f}% | Ex5M={cagr_ex5m*100:5.2f}%")

    df_lowo = pd.DataFrame(lowo_rows)
    df_lowo.to_csv(os.path.join(HERE, '06_leave_one_winner_out.csv'), index=False)

    # =========================================================================
    # SECTION 8: Second-Vendor (Tiingo-First) End-to-End Replication
    # =========================================================================
    print('\n--- [8] Second-Vendor (Tiingo-First) End-to-End Replication ---')
    L_qqq_c3_t = simulate_single_sleeve(df_qqq_t, q_sharpe_spec, k=2, k_keep=2, linear_cost=True)
    L_qqq_g1_5_t = simulate_single_sleeve(df_qqq_t, q_sharpe_spec, k=2, k_keep=5, linear_cost=True)
    L_xlk_c3_t = simulate_single_sleeve(df_xlk_t, x_raw_spec, k=1, k_keep=1, linear_cost=False)
    L_spy_raw_1_t = simulate_single_sleeve(df_spy_t, s_raw_spec, k=1, k_keep=1, linear_cost=False)
    L_spy_sh_1_t = simulate_single_sleeve(df_spy_t, s_sharpe_spec, k=1, k_keep=1, linear_cost=False)
    L_spy_sec_1_t = simulate_single_sleeve(df_spy_t, s_sec_raw_spec, k=1, k_keep=1, linear_cost=False)
    L_spy_raw_b2_t = simulate_single_sleeve(df_spy_t, s_raw_spec, k=1, k_keep=2, linear_cost=False)
    L_spy_raw_b3_t = simulate_single_sleeve(df_spy_t, s_raw_spec, k=1, k_keep=3, linear_cost=False)

    vendor_pairs = [
        ('00a. Core3 Control (QQQ Hard + XLK Hard)',
         L_ctrl_c3,
         combine_sleeves([(L_qqq_c3_t, 0.50), (L_xlk_c3_t, 0.50)], ['qqq', 'xlk'])),
        ('00b. G1 Control (QQQ Hold<=5 + XLK Hard)',
         L_ctrl_g1,
         combine_sleeves([(L_qqq_g1_5_t, 0.50), (L_xlk_c3_t, 0.50)], ['qqq', 'xlk'])),
        ('C3_SPY_1a. Core3 + SPY Raw Top-1',
         saved_ledgers['C3_SPY_1a. Core3 + SPY Raw Mom Top-1 (50% QQQ Hard Top-2 + 50% SPY Raw Top-1)'],
         combine_sleeves([(L_qqq_c3_t, 0.50), (L_spy_raw_1_t, 0.50)], ['qqq', 'spy'])),
        ('C3_SPY_1c. Core3 + SPY Sharpe Top-1',
         saved_ledgers['C3_SPY_1c. Core3 + SPY Sharpe-Mom Top-1 (50% QQQ Hard Top-2 + 50% SPY Sharpe Top-1)'],
         combine_sleeves([(L_qqq_c3_t, 0.50), (L_spy_sh_1_t, 0.50)], ['qqq', 'spy'])),
        ('G1_SPY_1a. G1 QQQ(Hold<=5) + SPY Raw Top-1',
         saved_ledgers['G1_SPY_1a. G1 QQQ(Hold<=5) + SPY Raw Mom Hard Top-1 (50/50)'],
         combine_sleeves([(L_qqq_g1_5_t, 0.50), (L_spy_raw_1_t, 0.50)], ['qqq', 'spy'])),
        ('G1_SPY_1c. G1 QQQ(Hold<=5) + SPY Sharpe Top-1',
         saved_ledgers['G1_SPY_1c. G1 QQQ(Hold<=5) + SPY Sharpe-Mom Hard Top-1 (50/50)'],
         combine_sleeves([(L_qqq_g1_5_t, 0.50), (L_spy_sh_1_t, 0.50)], ['qqq', 'spy'])),
        ('G1_SPY_1e. G1 QQQ(Hold<=5) + SPY Best-Sector->Stock',
         saved_ledgers['G1_SPY_1e. G1 QQQ(Hold<=5) + SPY Best-Sector->Top-1 Stock [SPEC] (50/50)'],
         combine_sleeves([(L_qqq_g1_5_t, 0.50), (L_spy_sec_1_t, 0.50)], ['qqq', 'spy'])),
        ('G1_SPY_2d. G1-Both QQQ(Hold<=5) + SPY Raw(Hold<=2)',
         saved_ledgers['G1_SPY_2d. G1-Both: QQQ(Hold<=5) + SPY Raw (Buy 1, Hold<=2)'],
         combine_sleeves([(L_qqq_g1_5_t, 0.50), (L_spy_raw_b2_t, 0.50)], ['qqq', 'spy'])),
        ('G1_SPY_2e. G1-Both QQQ(Hold<=5) + SPY Raw(Hold<=3)',
         saved_ledgers['G1_SPY_2e. G1-Both: QQQ(Hold<=5) + SPY Raw (Buy 1, Hold<=3)'],
         combine_sleeves([(L_qqq_g1_5_t, 0.50), (L_spy_raw_b3_t, 0.50)], ['qqq', 'spy'])),
        ('3S_G1_1a. G1 3-Sleeve (50% QQQ[Hold<=5] + 25% XLK + 25% SPY Raw)',
         saved_ledgers['3S_G1_1a. G1 3-Sleeve (50% QQQ[Hold<=5] + 25% XLK + 25% SPY Raw Top-1)'],
         combine_sleeves([(L_qqq_g1_5_t, 0.50), (L_xlk_c3_t, 0.25), (L_spy_raw_1_t, 0.25)], ['qqq', 'xlk', 'spy'])),
        ('3S_G1_1k. G1 3-Sleeve (50% QQQ[Hold<=5] + 25% XLK + 25% SPY Raw[Hold<=3])',
         saved_ledgers['3S_G1_1k. G1 3-Sleeve (50% QQQ[Hold<=5] + 25% XLK + 25% SPY Raw[Hold<=3])'],
         combine_sleeves([(L_qqq_g1_5_t, 0.50), (L_xlk_c3_t, 0.25), (L_spy_raw_b3_t, 0.25)], ['qqq', 'xlk', 'spy'])),
    ]

    v_rows = []
    for v_label, Lp_prim, Lp_tiin in vendor_pairs:
        s_p = summarize_ledger(v_label, 'Vendor', Lp_prim, rf_monthly)
        s_t = summarize_ledger(v_label, 'Vendor', Lp_tiin, rf_monthly)
        corr_m = float(Lp_prim['net'].corr(Lp_tiin['net']))
        v_rows.append({
            'Variant': v_label,
            'Primary_CAGR': s_p['CAGR_09_26'],
            'Tiingo_First_CAGR': s_t['CAGR_09_26'],
            'CAGR_Diff_bp': (s_t['CAGR_09_26'] - s_p['CAGR_09_26']) * 1e4,
            'Primary_Sharpe': s_p['Sharpe'],
            'Tiingo_First_Sharpe': s_t['Sharpe'],
            'Primary_MaxDD': s_p['Monthly_MaxDD'],
            'Tiingo_First_MaxDD': s_t['Monthly_MaxDD'],
            'Monthly_Return_Corr': corr_m,
        })
        print(f"  {v_label:<54} | Prim={s_p['CAGR_09_26']*100:6.2f}% | Tiingo={s_t['CAGR_09_26']*100:6.2f}% | "
              f"Diff={v_rows[-1]['CAGR_Diff_bp']:+6.1f}bp | Corr={corr_m:.5f}")

    df_vendor = pd.DataFrame(v_rows)
    df_vendor.to_csv(os.path.join(HERE, '07_second_vendor_replication.csv'), index=False)

    # =========================================================================
    # SECTION 9: Cumulative Multiple-Testing Deflated Sharpe Ratio (DSR)
    # =========================================================================
    print('\n--- [9] Cumulative Multiple-Testing Deflated Sharpe Ratio (DSR) ---')
    dsr_rows = []
    for k_name in [
        '00a. Core3 Control: 50% QQQ Sharpe Top-2 [Hard] + 50% XLK Raw Top-1 [Hard]',
        '00b. G1 Control: 50% QQQ (Buy 2, Hold<=5) + 50% XLK Raw Top-1 [Hard]',
        'C3_SPY_1a. Core3 + SPY Raw Mom Top-1 (50% QQQ Hard Top-2 + 50% SPY Raw Top-1)',
        'C3_SPY_1c. Core3 + SPY Sharpe-Mom Top-1 (50% QQQ Hard Top-2 + 50% SPY Sharpe Top-1)',
        'G1_SPY_1a. G1 QQQ(Hold<=5) + SPY Raw Mom Hard Top-1 (50/50)',
        'G1_SPY_1c. G1 QQQ(Hold<=5) + SPY Sharpe-Mom Hard Top-1 (50/50)',
        'G1_SPY_2d. G1-Both: QQQ(Hold<=5) + SPY Raw (Buy 1, Hold<=2)',
        'G1_SPY_2e. G1-Both: QQQ(Hold<=5) + SPY Raw (Buy 1, Hold<=3)',
        '3S_G1_1a. G1 3-Sleeve (50% QQQ[Hold<=5] + 25% XLK + 25% SPY Raw Top-1)',
        '3S_G1_1j. G1 3-Sleeve (50% QQQ[Hold<=5] + 25% XLK + 25% SPY Raw[Hold<=2])',
        '3S_G1_1k. G1 3-Sleeve (50% QQQ[Hold<=5] + 25% XLK + 25% SPY Raw[Hold<=3])',
        '3S_G1_1d. G1 3-Sleeve (50% QQQ[Hold<=5] + 25% XLK + 25% SPY Ex-IT Raw Top-1)',
    ]:
        dsr_val, sr0_ann, n_this, n_cum = compute_cumulative_dsr(all_series, k_name, prior_trials=434)
        dsr_rows.append({
            'Variant': k_name,
            'Round_Trials': n_this,
            'Cumulative_Trials_N': n_cum,
            'Expected_Max_SR_Null_Ann': sr0_ann,
            'Cumulative_DSR_p': dsr_val,
        })
        print(f"  {k_name:<72} | N_cum={n_cum} | E[MaxSR]={sr0_ann:.3f} | DSR={dsr_val:.4f}")

    df_dsr = pd.DataFrame(dsr_rows)
    df_dsr.to_csv(os.path.join(HERE, '08_multiple_testing_dsr.csv'), index=False)
    print('\n=== CLEAN-ROOM QQQ + SPY (CORE3 & G1) AUDIT COMPLETE ===')


if __name__ == '__main__':
    main()
