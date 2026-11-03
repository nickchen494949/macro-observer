#!/usr/bin/env python3
"""
build_selection_panels.py — Clean-Room Point-in-Time Stock-Selection Feature Engine for Core3
=============================================================================================
Builds strictly causal, point-in-time (PIT) monthly candidate panels for:
  1. Sleeve 1 Universe: Historical PIT Nasdaq-100 (QQQ) constituents (2008-12 .. 2026-08, 213 formation months)
  2. Sleeve 2 Universe: Historical PIT S&P 500 Information Technology constituents (2008-12 .. 2026-08, 213 formation months)
  3. Both Primary Vendor (Yahoo/Audit-Verified) AND Second Vendor (Tiingo-First)

Strictly Isolated Factor Families Computed at Formation Date t:
  - Control:
      * mom_12_1, vol_12_1, sharpe_mom_12_1 (= mom_12_1 / vol_12_1)
  - Hypothesis A: Momentum Consistency / Frog in the Pan (Da, Gurun, Warachka 2014, RFS):
      * fip_id_12_1     = sign(mom_12_1) * (%neg - %pos) over [t-12m, t-1m]
      * fip_smooth_12_1 = -fip_id_12_1 = sign(mom_12_1) * (%pos - %neg) (higher = more continuous)
      * fip_smooth_6_1  = sign(mom_6_1) * (%pos - %neg) over [t-6m, t-1m] (neighbor window)
      * pct_pos_12_1    = fraction of positive daily returns in [t-12m, t-1m]
      * max_ret_1d_12_1 = single largest daily return in [t-12m, t-1m]
      * max_ret_5d_12_1 = sum of 5 largest daily returns in [t-12m, t-1m]
      * non_jump_mom    = cumulative return in [t-12m, t-1m] after removing the 5 largest positive jump days
      * win_months_11   = fraction of the 11 formation months [t-12m..t-1m] with positive monthly return
  - Hypothesis B: Residual Momentum (Blitz, Huij, Martens 2011, JEMP):
      * Time-series OLS regression over [t-12m, t-1m] (plus 6m and 18m neighbor windows):
        - 1-Factor Market Model (against QQQ for NDX, SPY for Tech, and XLK for Sector-hedged Tech):
            r_{i,d} = alpha_i + beta_i * r_{bench,d} + eps_{i,d}
            res_ret_12_1    = prod_{d in [t-12m, t-1m]} (1 + r_{i,d} - beta_i * r_{bench,d}) - 1
            res_vol_12_1    = std(eps_{i,d}) * sqrt(252)
            res_sharpe_12_1 = res_ret_12_1 / res_vol_12_1
            res_std_blitz   = mean(eps_d_plus_alpha) / std(eps_d) * sqrt(252)
        - 2-Factor Market + Sector Model (SPY + XLK):
            res_ret_2f_12_1, res_vol_2f_12_1, res_sharpe_2f_12_1
  - Hypothesis C: Price Momentum + Fundamental / Earnings Momentum (Novy-Marx 2015 / PEAD):
      * Strictly PIT SEC 8-K Item 2.02 Earnings Announcement Return (EAR):
            ear_latest = 3-day abnormal return (Close[R-1] -> Close[R+1] minus benchmark) for latest release
                         with public_date = session[R+1] <= t and age <= 100 calendar days.
            ear_sum4   = sum of last up to 4 quarterly EARs (min 2, public <= t).
      * Strictly PIT SEC 10-Q/10-K XBRL Quarterly Fundamentals (gated by max(filed_curr, filed_prior) + 1d <= t
        and (t - period_end) <= 200 days, verified by cik_valid(ticker, t)):
            rev_yoy_q      = Revenue_q / Revenue_{q-4} - 1
            rev_accel_q    = rev_yoy_q - rev_yoy_{q-1}
            eps_yoy_sym_q  = (EPS_q - EPS_{q-4}) / (0.5 * (|EPS_q| + |EPS_{q-4}|))
            eps_accel_q    = eps_yoy_sym_q - eps_yoy_sym_{q-1}
            fund_mom_comp  = equal-weight cross-sectional percentile rank of available
                             {ear_latest, rev_yoy_q, rev_accel_q, eps_yoy_sym_q, eps_accel_q}
  - Hypothesis D (2nd Tier): 52-Week-High Proximity (George & Hwang 2004, JF):
      * prox_52wh_t  = Close[t] / MaxClose[t-252d : t]
      * prox_52wh_t1 = Close[t-1m] / MaxClose[t-12m : t-1m]
"""
import os
import sys
import numpy as np
import pandas as pd

ROOT = '/Users/happygolucky/Desktop/宏观观察器'
QQQ_DIR = os.path.join(ROOT, 'outputs', 'qqq_mom_top3_claude_audit_20261103')
TECH_DIR = os.path.join(ROOT, 'outputs', 'tech_top1_independent_audit_20261103')
DATA_DIR = os.path.join(ROOT, 'research', 'sector_stock_momentum', 'data')
HERE = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, QQQ_DIR)
sys.path.insert(0, TECH_DIR)

import a2_engine as QE
import c2_engine as TE


# =============================================================================
# 1. Load Benchmark Daily Returns (QQQ, SPY, XLK)
# =============================================================================
def load_benchmarks():
    df_qqq = QE.series('tiingo_api', 'QQQ')
    if df_qqq is None:
        df_qqq = QE.series('yahoo', 'QQQ')
    df_spy = QE.series('yahoo', 'SPY')
    df_xlk = TE.load_source('yahoo', 'XLK')

    r_qqq = df_qqq['adjclose'].dropna().sort_index().pct_change().dropna()
    r_spy = df_spy['adjclose'].dropna().sort_index().pct_change().dropna()
    r_xlk = df_xlk['adjclose'].dropna().sort_index().pct_change().dropna()
    return r_qqq, r_spy, r_xlk


# =============================================================================
# 2. Compute Price-Based Selection Features on One Daily Price Series at Date t
# =============================================================================
def compute_price_features_at_t(df_s, t, r_qqq, r_spy, r_xlk):
    """
    Strictly causal feature extraction for a single stock DataFrame `df_s` at formation month-end `t`.
    All slices use `df_s['adjclose'].loc[:t]` (never touching any observation after `t`).
    """
    t = pd.Timestamp(t)
    t_s1 = t - pd.offsets.MonthEnd(1)
    t_l6 = t - pd.offsets.MonthEnd(6)
    t_l9 = t - pd.offsets.MonthEnd(9)
    t_l12 = t - pd.offsets.MonthEnd(12)
    t_l18 = t - pd.offsets.MonthEnd(18)

    c_all = df_s['adjclose'].loc[:t].dropna()
    if len(c_all) < 120:
        return {}

    r_all = c_all.pct_change().dropna()

    # --- Slice [t-12m, t-1m] intersected with QQQ trading calendar (matches frozen Core3 vol_12_1) ---
    rq_12_1 = r_qqq.loc[t_l12:t_s1]
    common_12_1 = r_all.index.intersection(rq_12_1.index)
    if len(common_12_1) < 120:
        return {}

    ri_12 = r_all.loc[common_12_1].values
    rq_12 = rq_12_1.loc[common_12_1].values
    rs_12 = r_spy.reindex(common_12_1).fillna(0.0).values
    rx_12 = r_xlk.reindex(common_12_1).fillna(0.0).values

    # Month-end prices for 12-1 and 6-1 momentum
    def px_me(dt):
        s = c_all.loc[:dt]
        if not len(s) or (dt - s.index[-1]).days > 7:
            return np.nan
        return float(s.iloc[-1])

    p_t = px_me(t)
    p_s1 = px_me(t_s1)
    p_l6 = px_me(t_l6)
    p_l9 = px_me(t_l9)
    p_l12 = px_me(t_l12)

    if not (np.isfinite(p_t) and np.isfinite(p_s1) and np.isfinite(p_l12) and p_l12 > 0):
        return {}

    mom_12_1 = p_s1 / p_l12 - 1.0
    mom_6_1 = (p_s1 / p_l6 - 1.0) if (np.isfinite(p_l6) and p_l6 > 0) else np.nan
    mom_9_1 = (p_s1 / p_l9 - 1.0) if (np.isfinite(p_l9) and p_l9 > 0) else np.nan

    vol_12_1 = float(np.std(ri_12, ddof=1) * np.sqrt(252.0))
    sharpe_mom_12_1 = mom_12_1 / vol_12_1 if vol_12_1 > 0 else np.nan

    # -------------------------------------------------------------------------
    # Hypothesis A: Frog in the Pan (FIP) / Momentum Consistency
    # -------------------------------------------------------------------------
    pct_pos_12_1 = float(np.mean(ri_12 > 0))
    pct_neg_12_1 = float(np.mean(ri_12 < 0))
    sgn_12 = 1.0 if mom_12_1 >= 0 else -1.0
    # Da, Gurun, Warachka (2014): ID = sign(PRET) * (%neg - %pos); FIP_smooth = -ID = sign(PRET) * (%pos - %neg)
    fip_id_12_1 = sgn_12 * (pct_neg_12_1 - pct_pos_12_1)
    fip_smooth_12_1 = -fip_id_12_1

    # 6-1 neighbor window FIP
    common_6_1 = r_all.index.intersection(r_qqq.loc[t_l6:t_s1].index)
    if len(common_6_1) >= 60 and np.isfinite(mom_6_1):
        ri_6 = r_all.loc[common_6_1].values
        sgn_6 = 1.0 if mom_6_1 >= 0 else -1.0
        fip_smooth_6_1 = float(sgn_6 * (np.mean(ri_6 > 0) - np.mean(ri_6 < 0)))
        vol_6_1 = float(np.std(ri_6, ddof=1) * np.sqrt(252.0))
    else:
        fip_smooth_6_1 = np.nan
        vol_6_1 = np.nan

    # Extreme jump / lottery metrics over [t-12m, t-1m]
    sorted_ri = np.sort(ri_12)
    max_ret_1d_12_1 = float(sorted_ri[-1])
    max_ret_5d_12_1 = float(np.sum(sorted_ri[-5:]))
    # Non-jump cumulative return (removing the 5 largest positive single-day jumps in [t-12m, t-1m])
    non_jump_mom_12_1 = float(np.prod(1.0 + sorted_ri[:-5]) - 1.0)
    # Fraction of the 11 formation months with positive monthly return
    m_ends_12 = pd.date_range(t_l12, t_s1, freq='ME')
    m_pxs = [px_me(me) for me in m_ends_12]
    if all(np.isfinite(x) and x > 0 for x in m_pxs) and len(m_pxs) >= 2:
        m_rets = np.diff(m_pxs) / np.array(m_pxs[:-1])
        win_months_11 = float(np.mean(m_rets > 0))
    else:
        win_months_11 = np.nan

    # -------------------------------------------------------------------------
    # Hypothesis B: Residual Momentum (Blitz, Huij, Martens 2011)
    # -------------------------------------------------------------------------
    def calc_ols_residual(y, x_mat):
        # x_mat has shape (N, k); prepend column of 1s for intercept alpha
        X = np.column_stack([np.ones(len(y)), x_mat])
        coef, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
        alpha = coef[0]
        betas = coef[1:]
        systematic = x_mat @ betas if x_mat.ndim > 1 else x_mat * betas[0]
        # Hedged daily return = r_{i,d} - beta * r_{bench,d} (= alpha + eps_d)
        r_hedged = y - systematic
        eps = y - (alpha + systematic)
        res_ret = float(np.prod(1.0 + np.clip(r_hedged, -0.95, None)) - 1.0)
        res_vol = float(np.std(eps, ddof=1) * np.sqrt(252.0))
        res_sharpe = res_ret / res_vol if res_vol > 0 else np.nan
        # Blitz et al. (2011) standardized residual sum: sum(alpha + eps) / std(eps)
        res_blitz = float(np.mean(r_hedged) / np.std(eps, ddof=1) * np.sqrt(252.0)) if np.std(eps, ddof=1) > 0 else np.nan
        # Pure epsilon cumulative return (stripping out alpha too, testing sensitivity)
        eps_only_ret = float(np.prod(1.0 + np.clip(eps, -0.95, None)) - 1.0)
        return float(betas[0]), res_ret, res_vol, res_sharpe, res_blitz, eps_only_ret

    # B1a: Residual against QQQ (12-1 window)
    beta_qqq, res_ret_qqq_12_1, res_vol_qqq_12_1, res_sharpe_qqq_12_1, res_blitz_qqq_12_1, _ = calc_ols_residual(ri_12, rq_12)
    # B1b: Residual against SPY (12-1 window)
    beta_spy, res_ret_spy_12_1, res_vol_spy_12_1, res_sharpe_spy_12_1, res_blitz_spy_12_1, _ = calc_ols_residual(ri_12, rs_12)
    # B1c: Residual against XLK (12-1 window)
    beta_xlk, res_ret_xlk_12_1, res_vol_xlk_12_1, res_sharpe_xlk_12_1, res_blitz_xlk_12_1, _ = calc_ols_residual(ri_12, rx_12)
    # B2: 2-Factor Residual against SPY + XLK (Market + IT Sector)
    _, res_ret_2f_12_1, res_vol_2f_12_1, res_sharpe_2f_12_1, res_blitz_2f_12_1, _ = calc_ols_residual(
        ri_12, np.column_stack([rs_12, rx_12])
    )

    # Neighbor windows for Residual Momentum: 6-1 window and 18-1 window (against QQQ and XLK)
    if len(common_6_1) >= 60:
        rq_6 = r_qqq.loc[common_6_1].values
        rx_6 = r_xlk.reindex(common_6_1).fillna(0.0).values
        _, res_ret_qqq_6_1, _, res_sharpe_qqq_6_1, _, _ = calc_ols_residual(r_all.loc[common_6_1].values, rq_6)
        _, res_ret_xlk_6_1, _, res_sharpe_xlk_6_1, _, _ = calc_ols_residual(r_all.loc[common_6_1].values, rx_6)
    else:
        res_ret_qqq_6_1, res_sharpe_qqq_6_1 = np.nan, np.nan
        res_ret_xlk_6_1, res_sharpe_xlk_6_1 = np.nan, np.nan

    # Estimate beta over longer [t-18m, t-1m] window, then apply to [t-12m, t-1m] return (out-of-window beta check)
    common_18_1 = r_all.index.intersection(r_qqq.loc[t_l18:t_s1].index)
    if len(common_18_1) >= 150:
        ri_18 = r_all.loc[common_18_1].values
        rq_18 = r_qqq.loc[common_18_1].values
        rx_18 = r_xlk.reindex(common_18_1).fillna(0.0).values
        b18_q = float(np.cov(ri_18, rq_18, ddof=1)[0, 1] / np.var(rq_18, ddof=1))
        b18_x = float(np.cov(ri_18, rx_18, ddof=1)[0, 1] / np.var(rx_18, ddof=1))
        hedged_18q = ri_12 - b18_q * rq_12
        hedged_18x = ri_12 - b18_x * rx_12
        res_ret_qqq_b18 = float(np.prod(1.0 + np.clip(hedged_18q, -0.95, None)) - 1.0)
        res_sharpe_qqq_b18 = res_ret_qqq_b18 / (float(np.std(hedged_18q, ddof=1) * np.sqrt(252.0)))
        res_ret_xlk_b18 = float(np.prod(1.0 + np.clip(hedged_18x, -0.95, None)) - 1.0)
        res_sharpe_xlk_b18 = res_ret_xlk_b18 / (float(np.std(hedged_18x, ddof=1) * np.sqrt(252.0)))
    else:
        res_ret_qqq_b18, res_sharpe_qqq_b18 = res_ret_qqq_12_1, res_sharpe_qqq_12_1
        res_ret_xlk_b18, res_sharpe_xlk_b18 = res_ret_xlk_12_1, res_sharpe_xlk_12_1

    # -------------------------------------------------------------------------
    # Hypothesis D (2nd Tier): 52-Week-High Proximity (George & Hwang 2004)
    # -------------------------------------------------------------------------
    c_252_t = c_all.iloc[-252:] if len(c_all) >= 60 else c_all
    prox_52wh_t = float(p_t / c_252_t.max()) if len(c_252_t) and c_252_t.max() > 0 else np.nan
    c_12_1 = c_all.loc[t_l12:t_s1]
    prox_52wh_t1 = float(p_s1 / c_12_1.max()) if len(c_12_1) and c_12_1.max() > 0 else np.nan

    return {
        'mom_12_1': mom_12_1,
        'mom_9_1': mom_9_1,
        'mom_6_1': mom_6_1,
        'vol_12_1': vol_12_1,
        'vol_6_1': vol_6_1,
        'sharpe_mom_12_1': sharpe_mom_12_1,
        # Hypothesis A (FIP / Momentum Consistency)
        'pct_pos_12_1': pct_pos_12_1,
        'pct_neg_12_1': pct_neg_12_1,
        'fip_id_12_1': fip_id_12_1,
        'fip_smooth_12_1': fip_smooth_12_1,
        'fip_smooth_6_1': fip_smooth_6_1,
        'max_ret_1d_12_1': max_ret_1d_12_1,
        'max_ret_5d_12_1': max_ret_5d_12_1,
        'non_jump_mom_12_1': non_jump_mom_12_1,
        'win_months_11': win_months_11,
        # Hypothesis B (Residual Momentum)
        'beta_qqq': beta_qqq,
        'beta_spy': beta_spy,
        'beta_xlk': beta_xlk,
        'res_ret_qqq_12_1': res_ret_qqq_12_1,
        'res_vol_qqq_12_1': res_vol_qqq_12_1,
        'res_sharpe_qqq_12_1': res_sharpe_qqq_12_1,
        'res_blitz_qqq_12_1': res_blitz_qqq_12_1,
        'res_ret_spy_12_1': res_ret_spy_12_1,
        'res_sharpe_spy_12_1': res_sharpe_spy_12_1,
        'res_ret_xlk_12_1': res_ret_xlk_12_1,
        'res_vol_xlk_12_1': res_vol_xlk_12_1,
        'res_sharpe_xlk_12_1': res_sharpe_xlk_12_1,
        'res_blitz_xlk_12_1': res_blitz_xlk_12_1,
        'res_ret_2f_12_1': res_ret_2f_12_1,
        'res_sharpe_2f_12_1': res_sharpe_2f_12_1,
        'res_ret_qqq_6_1': res_ret_qqq_6_1,
        'res_sharpe_qqq_6_1': res_sharpe_qqq_6_1,
        'res_ret_xlk_6_1': res_ret_xlk_6_1,
        'res_sharpe_xlk_6_1': res_sharpe_xlk_6_1,
        'res_ret_qqq_b18': res_ret_qqq_b18,
        'res_sharpe_qqq_b18': res_sharpe_qqq_b18,
        'res_ret_xlk_b18': res_ret_xlk_b18,
        'res_sharpe_xlk_b18': res_sharpe_xlk_b18,
        # Hypothesis D (52-Week High Proximity)
        'prox_52wh_t': prox_52wh_t,
        'prox_52wh_t1': prox_52wh_t1,
    }


# =============================================================================
# 3. Strictly PIT Fundamental & Earnings Momentum Panel (Hypothesis C)
# =============================================================================
def load_cik_maps_and_validity():
    cm_sp = pd.read_csv(os.path.join(DATA_DIR, 'fundamentals', 'cik_map.csv')).dropna(subset=['cik'])
    cm_ndx = pd.read_csv(os.path.join(DATA_DIR, 'ndx_cik_map.csv')).dropna(subset=['cik'])
    t2c = {}
    for _, r in cm_sp.iterrows():
        t2c[str(r['ticker']).replace('.', '-')] = int(r['cik'])
        t2c[str(r['ticker'])] = int(r['cik'])
    for _, r in cm_ndx.iterrows():
        tk = str(r['ticker'])
        if tk not in t2c:
            t2c[tk] = int(r['cik'])
            t2c[tk.replace('.', '-')] = int(r['cik'])

    # Also map renamed tickers (e.g. FB -> META CIK, PCLN -> BKNG CIK, etc.)
    for old_tk, (new_tk, _) in QE.RENAME.items():
        if old_tk not in t2c and new_tk in t2c:
            t2c[old_tk] = t2c[new_tk]

    val_fn = os.path.join(DATA_DIR, 'cik_validity.csv')
    val_map = {}
    if os.path.exists(val_fn):
        vdf = pd.read_csv(val_fn, parse_dates=['valid_from', 'valid_to'])
        for r in vdf.itertuples():
            val_map[r.ticker] = (r.valid_from, r.valid_to)

    def is_cik_valid(tk, t_dt):
        t_dt = pd.Timestamp(t_dt)
        w = val_map.get(tk)
        if w is None:
            return True
        a, b = w
        return (pd.isna(a) or t_dt >= a) and (pd.isna(b) or t_dt < b)

    return t2c, is_cik_valid


def build_pit_fundamental_lookup(formations, cutoff=None):
    """
    Build a strictly PIT lookup indexed by (cik, t) for quarterly SEC XBRL fundamental momentum:
      - rev_yoy_q, rev_accel_q
      - eps_yoy_sym_q, eps_accel_q
      - eps_ttm_yoy_sym
    Every single number is gated by `max(all constituent filing dates) + 1 day <= t` (and `<= cutoff` if set),
    and staleness `(t - period_end) <= 200 days`.
    """
    f_sp = pd.read_parquet(os.path.join(DATA_DIR, 'fundamentals', 'eps_quarterly_pit.parquet'))
    f_ndx = pd.read_parquet(os.path.join(DATA_DIR, 'fundamentals_ndx', 'eps_quarterly_pit.parquet'))
    p = pd.concat([f_sp, f_ndx], ignore_index=True)
    p = p[p['cik'].notna()].copy()
    p['cik'] = p['cik'].astype('int64')
    p['period_end'] = pd.to_datetime(p['period_end'])
    for c in ['filed', 'available_date', 'filed_eps_diluted', 'filed_revenue',
              'eps_diluted_approx_ttm_available_date', 'revenue_ttm_available_date']:
        if c in p.columns:
            p[c] = pd.to_datetime(p[c])

    one_d = pd.Timedelta(days=1)
    if cutoff is not None:
        cut_dt = pd.Timestamp(cutoff)
        # Physical truncation of every field and date whose availability date (filed + 1d) is after cutoff
        gate = {
            'eps_diluted_approx_adj': 'filed_eps_diluted',
            'revenue': 'filed_revenue',
        }
        for col, fcol in gate.items():
            if col in p.columns and fcol in p.columns:
                p.loc[~(p[fcol] + one_d <= cut_dt), col] = np.nan
        if 'eps_diluted_approx_ttm_adj' in p.columns and 'eps_diluted_approx_ttm_available_date' in p.columns:
            p.loc[~(p['eps_diluted_approx_ttm_available_date'] <= cut_dt), 'eps_diluted_approx_ttm_adj'] = np.nan
        for c in ['filed_eps_diluted', 'filed_revenue']:
            if c in p.columns:
                p.loc[~(p[c] + one_d <= cut_dt), c] = pd.NaT
        for c in ['eps_diluted_approx_ttm_available_date', 'revenue_ttm_available_date', 'available_date']:
            if c in p.columns:
                p.loc[~(p[c] <= cut_dt), c] = pd.NaT

    p = p.sort_values(['cik', 'period_end', 'available_date']).drop_duplicates(['cik', 'period_end'], keep='first')

    # Match year-ago fiscal quarter (period_end + 365 days within +/- 20 days tolerance)
    prior = p[['cik', 'period_end', 'eps_diluted_approx_adj', 'revenue',
               'eps_diluted_approx_ttm_adj', 'filed_eps_diluted', 'filed_revenue',
               'eps_diluted_approx_ttm_available_date']].copy()
    prior['period_end'] = prior['period_end'] + pd.Timedelta(days=365)
    prior = prior.rename(columns={
        'eps_diluted_approx_adj': 'eps_py',
        'revenue': 'rev_py',
        'eps_diluted_approx_ttm_adj': 'ttm_py',
        'filed_eps_diluted': 'f_eps_py',
        'filed_revenue': 'f_rev_py',
        'eps_diluted_approx_ttm_available_date': 'av_ttm_py',
    }).sort_values('period_end')

    p = pd.merge_asof(
        p.sort_values('period_end'),
        prior,
        on='period_end',
        by='cik',
        tolerance=pd.Timedelta(days=20),
        direction='nearest'
    ).sort_values(['cik', 'period_end'])

    # Compute YoY quarterly EPS symmetric growth, YoY quarterly Revenue growth, and TTM EPS symmetric growth
    den_q = 0.5 * (p['eps_diluted_approx_adj'].abs() + p['eps_py'].abs())
    p['eps_yoy_sym_q'] = np.where(den_q > 1e-6, (p['eps_diluted_approx_adj'] - p['eps_py']) / den_q, np.nan)
    p['rev_yoy_q'] = np.where(p['rev_py'] > 0, p['revenue'] / p['rev_py'] - 1.0, np.nan)

    den_ttm = 0.5 * (p['eps_diluted_approx_ttm_adj'].abs() + p['ttm_py'].abs())
    p['eps_ttm_yoy_sym'] = np.where(den_ttm > 1e-6, (p['eps_diluted_approx_ttm_adj'] - p['ttm_py']) / den_ttm, np.nan)

    # Accelerations (quarter q minus quarter q-1, requiring consecutive quarters ~90 days apart)
    g = p.groupby('cik')
    q_gap = (p['period_end'] - g['period_end'].shift(1)).dt.days
    valid_consec = q_gap.between(70, 115)
    p['eps_accel_q'] = np.where(valid_consec, p['eps_yoy_sym_q'] - g['eps_yoy_sym_q'].shift(1), np.nan)
    p['rev_accel_q'] = np.where(valid_consec, p['rev_yoy_q'] - g['rev_yoy_q'].shift(1), np.nan)

    # Strict PIT Availability Dates (filed + 1 day across ALL inputs used in each formula)
    one_d = pd.Timedelta(days=1)
    mx = lambda *cols: pd.concat(list(cols), axis=1).max(axis=1, skipna=False)
    p['f_eps_yoy'] = mx(p['filed_eps_diluted'], p['f_eps_py'])
    p['f_rev_yoy'] = mx(p['filed_revenue'], p['f_rev_py'])
    g = p.groupby('cik')
    p['av_eps_yoy'] = p['f_eps_yoy'] + one_d
    p['av_eps_acc'] = mx(p['f_eps_yoy'], g['f_eps_yoy'].shift(1)) + one_d
    p['av_rev_yoy'] = p['f_rev_yoy'] + one_d
    p['av_rev_acc'] = mx(p['f_rev_yoy'], g['f_rev_yoy'].shift(1)) + one_d
    p['av_ttm_yoy'] = mx(p['eps_diluted_approx_ttm_available_date'], p['av_ttm_py'])

    form_dts = pd.DatetimeIndex(sorted(formations))
    ciks = p['cik'].unique()
    grid = pd.DataFrame([(c, t_val) for c in ciks for t_val in form_dts], columns=['cik', 't']).sort_values('t')
    out = grid.copy()

    spec_map = {
        'av_eps_yoy': ['eps_yoy_sym_q'],
        'av_eps_acc': ['eps_accel_q'],
        'av_rev_yoy': ['rev_yoy_q'],
        'av_rev_acc': ['rev_accel_q'],
        'av_ttm_yoy': ['eps_ttm_yoy_sym'],
    }
    for av_col, val_cols in spec_map.items():
        sub = p.dropna(subset=[av_col])[['cik', av_col, 'period_end'] + val_cols].sort_values([av_col, 'period_end'], kind='mergesort')
        m = pd.merge_asof(grid, sub, left_on='t', right_on=av_col, by='cik', direction='backward')
        stale = (m['t'] - m['period_end']).dt.days > 200
        for vc in val_cols:
            m.loc[stale, vc] = np.nan
        out = out.merge(m[['cik', 't'] + val_cols], on=['cik', 't'], how='left')

    return out.set_index(['cik', 't'])


def load_earnings_reaction_dates(cutoff=None):
    """Load SEC Form 8-K Item 2.02 earnings release reaction dates (strictly cut at `cutoff` if set)."""
    ed = pd.read_csv(os.path.join(DATA_DIR, 'earnings_dates.csv'), parse_dates=['filing_date', 'reaction_date'])
    ed = ed.dropna(subset=['cik', 'reaction_date']).copy()
    ed['cik'] = ed['cik'].astype('int64')
    if cutoff is not None:
        cut_dt = pd.Timestamp(cutoff)
        ed = ed[(ed['filing_date'] <= cut_dt) & (ed['reaction_date'] <= cut_dt)].copy()
    return {cik: np.sort(g['reaction_date'].unique()) for cik, g in ed.groupby('cik')}


def compute_ear_at_t(df_s, cik, t, ed_map, c_bench, cal):
    """
    Compute 3-day abnormal return (EAR) around the most recent 8-K earnings release for `cik`
    where `public_date = cal[R + 1] <= t` and `(t - R).days <= 100`.
    """
    if cik is None or pd.isna(cik) or int(cik) not in ed_map:
        return np.nan, np.nan
    t = pd.Timestamp(t)
    rx_dates = ed_map[int(cik)]
    # Only consider reaction dates prior to t
    rx_dates = rx_dates[rx_dates <= t]
    if not len(rx_dates):
        return np.nan, np.nan

    c_stock = df_s['adjclose'].loc[:t].dropna()
    if len(c_stock) < 10:
        return np.nan, np.nan

    ears = []
    # Check last 6 events up to t
    for r_dt in rx_dates[-6:]:
        idx_r = cal.searchsorted(pd.Timestamp(r_dt), side='left')
        if idx_r < 1 or idx_r + 1 >= len(cal):
            continue
        d_pre = cal[idx_r - 1]
        d_r = cal[idx_r]
        d_pub = cal[idx_r + 1]  # Strictly public at Close[R+1]
        if d_pub > t:
            continue
        if (d_pre not in c_stock.index) or (d_pub not in c_stock.index):
            continue
        if (d_pre not in c_bench.index) or (d_pub not in c_bench.index):
            continue
        ret_s = float(c_stock.at[d_pub] / c_stock.at[d_pre] - 1.0)
        ret_b = float(c_bench.at[d_pub] / c_bench.at[d_pre] - 1.0)
        ears.append((d_r, d_pub, ret_s - ret_b))

    if not ears:
        return np.nan, np.nan

    last_r, last_pub, last_ear = ears[-1]
    ear_latest = last_ear if (t - last_r).days <= 100 else np.nan

    # Sum of last up to 4 quarterly EARs within 400 days of t
    recent_4 = [e[2] for e in ears[-4:] if (t - e[0]).days <= 400]
    ear_sum4 = float(np.sum(recent_4)) if (len(recent_4) >= 2 and np.isfinite(ear_latest)) else np.nan
    return ear_latest, ear_sum4


def attach_composite_fund_mom(df_panel):
    """
    Within each formation month `t`, compute cross-sectional percentile ranks (0..1) of:
      - ear_latest, ear_sum4, rev_yoy_q, rev_accel_q, eps_yoy_sym_q, eps_accel_q, eps_ttm_yoy_sym
    and form:
      - `fund_mom_comp`: equal-weight mean of available fundamental momentum ranks
      - `op_accel_comp`: equal-weight mean of available operating acceleration ranks {rev_accel_q, eps_accel_q, rev_yoy_q, eps_yoy_sym_q}
      - `pead_comp`: equal-weight mean of available {ear_latest, ear_sum4, eps_yoy_sym_q}
    """
    df = df_panel.copy()
    f_cols = ['ear_latest', 'ear_sum4', 'rev_yoy_q', 'rev_accel_q', 'eps_yoy_sym_q', 'eps_accel_q', 'eps_ttm_yoy_sym']
    for c in f_cols:
        df['rk_' + c] = df.groupby('t')[c].rank(pct=True)

    all_rk = ['rk_' + c for c in f_cols]
    op_rk = ['rk_rev_yoy_q', 'rk_rev_accel_q', 'rk_eps_yoy_sym_q', 'rk_eps_accel_q']
    pead_rk = ['rk_ear_latest', 'rk_ear_sum4', 'rk_eps_yoy_sym_q']

    df['fund_mom_comp'] = df[all_rk].mean(axis=1)
    df['op_accel_comp'] = df[op_rk].mean(axis=1)
    df['pead_comp'] = df[pead_rk].mean(axis=1)
    return df


# =============================================================================
# 4. Build QQQ & Tech Candidate Selection Panels (Primary & Second Vendor)
# =============================================================================
def build_qqq_selection_panel(vendor='primary', cutoff=None):
    r_qqq, r_spy, r_xlk = load_benchmarks()
    cal = QE.calendar()
    c_qqq = (QE.series('tiingo_api', 'QQQ') if QE.series('tiingo_api', 'QQQ') is not None else QE.series('yahoo', 'QQQ'))['adjclose'].dropna()

    if vendor == 'primary':
        P_base = pd.read_parquet(os.path.join(QQQ_DIR, 's_panel.parquet'))
        H_all = pd.read_parquet(os.path.join(QQQ_DIR, 'r_hold_returns_open_d1_all.parquet'))
    else:
        P_base = pd.read_parquet(os.path.join(QQQ_DIR, 's_panel_vendor_tiingo_first.parquet'))
        H_all = pd.read_parquet(os.path.join(QQQ_DIR, 'r_hold_returns_open_d1_all.parquet'))

    if cutoff is not None:
        cut_dt = pd.Timestamp(cutoff)
        P_base = P_base[P_base['t'] <= cut_dt].copy()
        QE.CUTOFF = cut_dt
        QE._series_cut.cache_clear()

    formations = sorted(P_base['t'].unique())
    t2c, is_cik_valid = load_cik_maps_and_validity()
    fund_lookup = build_pit_fundamental_lookup(formations, cutoff=cutoff)
    ed_map = load_earnings_reaction_dates(cutoff=cutoff)

    H_idx = H_all.set_index(['t', 'ticker'])
    rows = []
    for _, r in P_base.iterrows():
        t_val = pd.Timestamp(r['t'])
        tk = r['ticker']
        st, sym = r['store'], r['sym']
        df_s = QE.series(st, sym)
        if df_s is None:
            continue
        feats = compute_price_features_at_t(df_s, t_val, r_qqq, r_spy, r_xlk)
        if not feats:
            continue

        cik = t2c.get(tk) if is_cik_valid(tk, t_val) else None
        ear_1, ear_4 = compute_ear_at_t(df_s, cik, t_val, ed_map, c_qqq, cal)
        feats['cik'] = cik
        feats['ear_latest'] = ear_1
        feats['ear_sum4'] = ear_4

        if cik is not None and (cik, t_val) in fund_lookup.index:
            frow = fund_lookup.loc[(cik, t_val)]
            if isinstance(frow, pd.DataFrame):
                frow = frow.iloc[-1]
            for fc in ['rev_yoy_q', 'rev_accel_q', 'eps_yoy_sym_q', 'eps_accel_q', 'eps_ttm_yoy_sym']:
                feats[fc] = float(frow[fc]) if pd.notna(frow[fc]) else np.nan
        else:
            for fc in ['rev_yoy_q', 'rev_accel_q', 'eps_yoy_sym_q', 'eps_accel_q', 'eps_ttm_yoy_sym']:
                feats[fc] = np.nan

        # Attach holding return (for backtest evaluation only; never used in signal!)
        if cutoff is None:
            if vendor == 'tiingo':
                r_v, st_v, sym_v, fl_v, ed_v, xd_v = QE.hold_return(tk, t_val, mode='open', open_stores=['tiingo_api', 'yahoo', 'wikibulk'])
                feats['hold_ret'] = float(r_v) if np.isfinite(r_v) else np.nan
                feats['ret_store'] = st_v
                feats['ret_sym'] = sym_v
            elif (t_val, tk) in H_idx.index:
                hrow = H_idx.loc[(t_val, tk)]
                feats['hold_ret'] = float(hrow['ret'])
                feats['ret_store'] = hrow['ret_store']
                feats['ret_sym'] = hrow['ret_sym']
            else:
                feats['hold_ret'] = np.nan
                feats['ret_store'] = st
                feats['ret_sym'] = sym
        else:
            feats['hold_ret'] = np.nan
            feats['ret_store'] = st
            feats['ret_sym'] = sym

        feats['t'] = t_val
        feats['ticker'] = tk
        feats['store'] = st
        feats['sym'] = sym
        rows.append(feats)

    if cutoff is not None:
        QE.CUTOFF = None
        QE._series_cut.cache_clear()

    df_out = pd.DataFrame(rows)
    df_out = attach_composite_fund_mom(df_out)
    return df_out


def build_tech_selection_panel(vendor='primary', cutoff=None):
    r_qqq, r_spy, r_xlk = load_benchmarks()
    cal = QE.calendar()
    c_spy = QE.series('yahoo', 'SPY')['adjclose'].dropna()

    formations = [pd.Timestamp(t) for t in TE.formations()]
    if cutoff is not None:
        cut_dt = pd.Timestamp(cutoff)
        formations = [t for t in formations if t <= cut_dt]

    t2c, is_cik_valid = load_cik_maps_and_validity()
    fund_lookup = build_pit_fundamental_lookup(formations, cutoff=cutoff)
    ed_map = load_earnings_reaction_dates(cutoff=cutoff)

    # Second-vendor (Tiingo-first) helper for Tech universe
    TIINGO_EXCLUDE = {'LSI', 'ALTR', 'ACS', 'TLAB', 'CPWR'}
    TIINGO_WINDOW = {'SNDK': ('2025-02-13', None), 'CA': (None, '2018-11-05'), 'DELL': ('2016-08-17', None)}
    ALIAS_T = {'FB': 'META', 'JDSU': 'VIAV', 'CSC': 'DXC', 'ERTS': 'EA', 'MOT': 'MSI', 'SAI': 'LDOS', 'YHOO': 'AABA',
               'NLOK': 'GEN', 'SYMC': 'GEN', 'FLT': 'CPAY', 'HRS': 'LHX', 'CDAY': 'DAY', 'FISV': 'FI'}

    def load_tiingo_tech_df(tk):
        if tk in TIINGO_EXCLUDE:
            return None, None
        sym = ALIAS_T.get(tk, tk)
        df = QE.series('tiingo_api', sym)
        if df is not None:
            df = df.copy()
            src_name = f'tiingo_api:{sym}'
        else:
            df_p = QE.series('raw_tiingo', sym)
            if df_p is None:
                df_p = QE.series('raw_ndx', sym)
            if df_p is None:
                return None, None
            df = df_p.copy()
            src_name = f'raw_tiingo:{sym}'
        a, b = TIINGO_WINDOW.get(tk, (None, None))
        if a:
            df = df[df.index >= pd.Timestamp(a)]
        if b:
            df = df[df.index <= pd.Timestamp(b)]
        return (df if len(df) else None), src_name

    rows = []
    for t_val in formations:
        univ = TE.it_universe(t_val, 'main')
        for tk in univ:
            df_chosen = None
            src_chosen, sym_chosen = None, None
            mom_val = np.nan

            tdf_full = None
            if vendor == 'tiingo':
                tdf, tsrc = load_tiingo_tech_df(tk)
                if tdf is not None:
                    tdf_full = tdf
                    tdf_use = tdf.loc[:pd.Timestamp(cutoff)] if cutoff is not None else tdf
                    m_v = TE._momentum_from_df(tdf_use, t_val)
                    if np.isfinite(m_v):
                        df_chosen = tdf_use
                        src_chosen, sym_chosen = tsrc, ALIAS_T.get(tk, tk)
                        mom_val = float(m_v)

            if df_chosen is None:
                for df_seg, src, sym, note in TE.segments(tk):
                    df_use = df_seg.loc[:pd.Timestamp(cutoff)] if cutoff is not None else df_seg
                    m_v = TE._momentum_from_df(df_use, t_val)
                    if np.isfinite(m_v):
                        df_chosen = df_use
                        src_chosen, sym_chosen = src, sym
                        mom_val = float(m_v)
                        break

            if df_chosen is None or not np.isfinite(mom_val):
                continue

            feats = compute_price_features_at_t(df_chosen, t_val, r_qqq, r_spy, r_xlk)
            if not feats:
                continue
            # Ensure mom_12_1 matches TE._momentum_from_df exact value
            feats['mom_12_1'] = mom_val
            feats['sharpe_mom_12_1'] = mom_val / feats['vol_12_1'] if feats['vol_12_1'] > 0 else np.nan

            cik = t2c.get(tk) if is_cik_valid(tk, t_val) else None
            ear_1, ear_4 = compute_ear_at_t(df_chosen, cik, t_val, ed_map, c_spy, cal)
            feats['cik'] = cik
            feats['ear_latest'] = ear_1
            feats['ear_sum4'] = ear_4

            if cik is not None and (cik, t_val) in fund_lookup.index:
                frow = fund_lookup.loc[(cik, t_val)]
                if isinstance(frow, pd.DataFrame):
                    frow = frow.iloc[-1]
                for fc in ['rev_yoy_q', 'rev_accel_q', 'eps_yoy_sym_q', 'eps_accel_q', 'eps_ttm_yoy_sym']:
                    feats[fc] = float(frow[fc]) if pd.notna(frow[fc]) else np.nan
            else:
                for fc in ['rev_yoy_q', 'rev_accel_q', 'eps_yoy_sym_q', 'eps_accel_q', 'eps_ttm_yoy_sym']:
                    feats[fc] = np.nan

            # Holding return from t+1d open to next month t+1d open
            if cutoff is None:
                ret_val = np.nan
                if vendor == 'tiingo' and tdf_full is not None:
                    d0 = QE.first_td_after(t_val, 1)
                    d1 = QE.first_td_after(t_val + pd.offsets.MonthEnd(1), 1)
                    ocol = 'adjopen' if 'adjopen' in tdf_full.columns else 'adj_open'
                    if d0 in tdf_full.index and d1 in tdf_full.index and ocol in tdf_full.columns:
                        if np.isfinite(tdf_full.at[d0, ocol]) and np.isfinite(tdf_full.at[d1, ocol]):
                            ret_val = float(tdf_full.at[d1, ocol] / tdf_full.at[d0, ocol] - 1.0)
                if not np.isfinite(ret_val):
                    h_ret, _ = TE.hold_return(tk, t_val, 'open')
                    ret_val = float(h_ret) if np.isfinite(h_ret) else np.nan
                feats['hold_ret'] = ret_val
            else:
                feats['hold_ret'] = np.nan

            feats['t'] = t_val
            feats['ticker'] = tk
            feats['store'] = src_chosen
            feats['sym'] = sym_chosen
            rows.append(feats)

    df_out = pd.DataFrame(rows)
    df_out = attach_composite_fund_mom(df_out)
    return df_out


# =============================================================================
# 5. Physical Truncation Test Across All New Factor Families (A, B, C, D)
# =============================================================================
def run_truncation_audit(df_qqq_full, df_tech_full):
    cutoffs = ['2011-12-31', '2015-06-30', '2018-12-31', '2021-12-31', '2024-06-30']
    check_cols = [
        'mom_12_1', 'vol_12_1', 'fip_smooth_12_1', 'non_jump_mom_12_1',
        'res_ret_qqq_12_1', 'res_sharpe_qqq_12_1', 'res_ret_xlk_12_1', 'res_sharpe_xlk_12_1',
        'ear_latest', 'rev_yoy_q', 'rev_accel_q', 'eps_yoy_sym_q', 'eps_accel_q', 'fund_mom_comp',
        'prox_52wh_t'
    ]
    rows = []
    for cut_str in cutoffs:
        cut_dt = pd.Timestamp(cut_str)
        q_trunc = build_qqq_selection_panel(vendor='primary', cutoff=cut_dt)
        t_trunc = build_tech_selection_panel(vendor='primary', cutoff=cut_dt)

        q_ref = df_qqq_full[df_qqq_full['t'] <= cut_dt].set_index(['t', 'ticker'])
        q_tr = q_trunc.set_index(['t', 'ticker'])
        t_ref = df_tech_full[df_tech_full['t'] <= cut_dt].set_index(['t', 'ticker'])
        t_tr = t_trunc.set_index(['t', 'ticker'])

        max_diff_q = 0.0
        for c in check_cols:
            a, b = q_ref[c], q_tr[c]
            both_valid = a.notna() & b.notna()
            na_mismatch = int((a.isna() != b.isna()).sum())
            diff = float((a[both_valid] - b[both_valid]).abs().max()) if both_valid.any() else 0.0
            max_diff_q = max(max_diff_q, diff, float(na_mismatch))

        max_diff_t = 0.0
        for c in check_cols:
            a, b = t_ref[c], t_tr[c]
            both_valid = a.notna() & b.notna()
            na_mismatch = int((a.isna() != b.isna()).sum())
            diff = float((a[both_valid] - b[both_valid]).abs().max()) if both_valid.any() else 0.0
            max_diff_t = max(max_diff_t, diff, float(na_mismatch))

        rows.append({
            'Cutoff_Date': cut_str,
            'QQQ_Rows_Checked': len(q_tr),
            'Tech_Rows_Checked': len(t_tr),
            'QQQ_Max_Abs_Diff_All_15_Factors': max_diff_q,
            'Tech_Max_Abs_Diff_All_15_Factors': max_diff_t,
            'Status': 'PASS (0.00e+00)' if (max_diff_q < 1e-12 and max_diff_t < 1e-12) else 'FAIL',
        })
        print(f"  Truncation cutoff {cut_str}: QQQ max_diff={max_diff_q:.2e}, Tech max_diff={max_diff_t:.2e}")
    return pd.DataFrame(rows)


def main():
    os.makedirs(HERE, exist_ok=True)
    p_qqq = os.path.join(HERE, 'qqq_selection_panel.parquet')
    p_tech = os.path.join(HERE, 'tech_selection_panel.parquet')
    p_qqq_t = os.path.join(HERE, 'qqq_selection_panel_tiingo.parquet')
    p_tech_t = os.path.join(HERE, 'tech_selection_panel_tiingo.parquet')

    if all(os.path.exists(p) for p in [p_qqq, p_tech, p_qqq_t, p_tech_t]) and '--rebuild' not in sys.argv:
        print('Loading existing selection panels from disk...')
        df_qqq = pd.read_parquet(p_qqq)
        df_tech = pd.read_parquet(p_tech)
    else:
        print('=== [1/4] Building QQQ Primary Selection Panel (2008-12 .. 2026-08) ===')
        df_qqq = build_qqq_selection_panel(vendor='primary')
        df_qqq.to_parquet(p_qqq, index=False)
        print(f'  Saved qqq_selection_panel.parquet ({len(df_qqq)} rows, {df_qqq["t"].nunique()} months)')

        print('=== [2/4] Building Tech Primary Selection Panel (2008-12 .. 2026-08) ===')
        df_tech = build_tech_selection_panel(vendor='primary')
        df_tech.to_parquet(p_tech, index=False)
        print(f'  Saved tech_selection_panel.parquet ({len(df_tech)} rows, {df_tech["t"].nunique()} months)')

        print('=== [3/4] Building Second-Vendor (Tiingo-First) Selection Panels ===')
        df_qqq_t = build_qqq_selection_panel(vendor='tiingo')
        df_qqq_t.to_parquet(p_qqq_t, index=False)
        df_tech_t = build_tech_selection_panel(vendor='tiingo')
        df_tech_t.to_parquet(p_tech_t, index=False)
        print(f'  Saved Tiingo-first panels: QQQ={len(df_qqq_t)} rows, Tech={len(df_tech_t)} rows')

    print('=== [4/4] Running Physical Truncation Test Across All 15 New Features ===')
    df_trunc = run_truncation_audit(df_qqq, df_tech)
    df_trunc.to_csv(os.path.join(HERE, '00_pit_truncation_audit.csv'), index=False)
    print('=== PANEL BUILD & TRUNCATION AUDIT COMPLETE ===')


if __name__ == '__main__':
    main()
