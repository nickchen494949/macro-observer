#!/usr/bin/env python3
"""
run_structural_blindspots_audit.py — Clean-Room Adversarial Audit of the 5 Overlooked
Structural & Academic Mechanisms in Core3 (Hypotheses E, F, G, H, I)
=====================================================================================
Strictly isolated, pre-registered tests on frozen Core3:
  - Baseline Control (Core3 Frozen):
      50% QQQ Sharpe-Momentum Top-2 + 50% Historical S&P 500 IT Tech 12-1 Momentum Top-1 [S1]
      Month-end signal at t, T+1 Open execution, 10 bp/side cost, 1.0x unlevered, Cash = 0%.

  - Hypothesis E: Cross-Sleeve Overlap & Concentration Mechanics
      * Forensic attribution of Overlap Months (75% single-stock weight when Tech #1 is in QQQ Top-2)
        vs Non-Overlap Months (50% / 25% / 25% across 3 distinct stocks).
      * E1: De-Overlap (guarantee 3 distinct stocks: QQQ yields to Tech, Tech yields to QQQ, or 33.3% x 3).
      * E2: Single-stock weight cap (40%, 50%, 60%) redistributing excess to the 2nd QQQ stock.
      * E3: Single-stock weight cap (50%) redistributing 25% overflow to QQQ Rank #3.
      * E4: Inverse-volatility weighting across the selected Core3 holdings (21d / 63d / 252d stock vol).

  - Hypothesis F: Skip-Month ([t-1m, t]) Breakdown Veto & Signal Freshness (Novy-Marx 2012)
      * F1: Skip-month crash veto (veto candidate if ret_1m < {-5%, -10%, -15%, -20%}; 100% equity invested).
      * F2: Formation-date trend breakdown veto (veto candidate if Close[t] < SMA50 / SMA100 / SMA200).
      * F3: Formation-date 21-day peak drawdown veto (veto candidate if dd_peak_21d_t < {-12%, -15%, -20%}).
      * F4: Shorter microstructure skip window (12-1w [skip 5 trading days] and 12-0 [skip 0 days]).

  - Hypothesis G: Rank-Boundary Hysteresis / Buy-Hold Buffer Rules (Novy-Marx & Velikov 2016, RFS)
      * G1: Buffer on QQQ only (Buy Top-2, Hold while Rank <= K_keep for K_keep in {3, 4, 5}).
      * G2: Buffer on Tech only (Buy Top-1, Hold while Rank <= M_keep for M_keep in {2, 3, 4}).
      * G3: Full 2D buffer grid (K_keep in {3, 4, 5, 6} x M_keep in {2, 3, 4}).
      * G4: Jegadeesh-Titman overlapping multi-month tranches (K_hold = 2 months and K_hold = 3 months).

  - Hypothesis H: Portfolio-Own Realized Volatility Scaling & Crash State
      * H1/H2: Barroso & Santa-Clara (2015, JFE) scaling by the selected 3-stock basket's OWN
        trailing 21d / 63d realized volatility (including pairwise covariance), Cash = 0%.
      * H3: Zero-cash intra-portfolio de-risking (shift to de-overlapped inverse-vol weights when basket vol > 40%/45%).
      * H4: Daniel & Moskowitz (2016, JFE) bear-rebound momentum crash state protection.

  - Hypothesis I: Sleeve-Asymmetric Domain Rules (Cross-Sector QQQ Physics vs Pure-Tech S&P 500 IT Physics)
      * I1: QQQ Rank #2/#3 diagnostics across subperiods.
      * I2: QQQ Non-Biotech / Non-Healthcare filter (testing whether NDX Biotech spikes degrade QQQ Rank #1).
      * I3: Sleeve-specific confirmation (QQQ 4Q-EAR / FundMom + Tech Pure Price Mom or Anti-Jump Veto).
"""
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
HERE = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, QQQ_DIR)
sys.path.insert(0, TECH_DIR)

import a2_engine as QE
import c2_engine as TE

COST_BP = 0.0010  # 10 bp per side

# Historical Nasdaq-100 Biotech / Healthcare / Pharma tickers (GICS 35)
NDX_BIOTECH_HEALTHCARE = {
    'AMGN', 'BIIB', 'CELG', 'GILD', 'GENZ', 'ILMN', 'ISRG', 'LIFE', 'MRNA', 'MYL',
    'REGN', 'VRTX', 'ALXN', 'BMRN', 'INCY', 'SGEN', 'SHPG', 'TEVA', 'ENDP', 'ESRX',
    'HOLX', 'IDXX', 'ALGN', 'DXCM', 'CERN', 'HSIC', 'PRGO', 'STLD_DUMMY', 'BCR', 'CEPH',
    'CHIR', 'IVX', 'MEDI', 'MLNM', 'PDLI', 'SEPR', 'SIGA', 'TECH', 'VTRS', 'AZN', 'BNTX'
}


# =============================================================================
# 1. Price Series Cache & Strictly Causal Formation-Date Feature Augmentation
# =============================================================================
_PRICE_CACHE = {}


def get_adjclose(univ, store, sym):
    key = (univ, store, sym)
    if key not in _PRICE_CACHE:
        if ':' in str(store):
            st_base = str(store).split(':')[0]
            df = QE.series(st_base, sym)
            if df is None and st_base == 'raw_tiingo':
                df = QE.series('raw_ndx', sym)
        else:
            df = QE.series(store, sym) if str(univ).lower() == 'qqq' else TE.load_source(store, sym)
        if df is None or 'adjclose' not in df.columns:
            _PRICE_CACHE[key] = pd.Series(dtype=float)
        else:
            _PRICE_CACHE[key] = df['adjclose'].dropna().sort_index()
    return _PRICE_CACHE[key]


_RET_CACHE = {}


def get_daily_ret(univ, store, sym):
    key = (univ, store, sym)
    if key not in _RET_CACHE:
        c = get_adjclose(univ, store, sym)
        _RET_CACHE[key] = c.pct_change().dropna() if len(c) else pd.Series(dtype=float)
    return _RET_CACHE[key]


def compute_extra_features_at_t(c_full, t, r_qqq_full, cutoff=None):
    """
    Strictly causal extraction of skip-month, SMA distance, short-skip momentum,
    21d peak drawdown, and own realized vol at formation date t.
    If `cutoff` is provided, physically truncates `c_full` and `r_qqq_full` at `cutoff` first.
    """
    t = pd.Timestamp(t)
    if cutoff is not None:
        cut_ts = pd.Timestamp(cutoff)
        c_full = c_full.loc[:cut_ts]
        r_qqq_full = r_qqq_full.loc[:cut_ts]

    c_all = c_full.loc[:t]
    if len(c_all) < 120:
        return {}

    t_s1 = t - pd.offsets.MonthEnd(1)
    t_l12 = t - pd.offsets.MonthEnd(12)

    def px_me(dt):
        s = c_all.loc[:dt]
        if not len(s) or (dt - s.index[-1]).days > 7:
            return np.nan
        return float(s.iloc[-1])

    p_t = px_me(t)
    p_s1 = px_me(t_s1)
    p_l12 = px_me(t_l12)
    if not (np.isfinite(p_t) and np.isfinite(p_s1) and np.isfinite(p_l12) and p_s1 > 0 and p_l12 > 0):
        return {}

    # 1. Skipped month return [t-1m, t]
    ret_1m = p_t / p_s1 - 1.0
    # 2. Full 12-0 momentum [t-12m, t] (no skip)
    mom_12_0 = p_t / p_l12 - 1.0
    # 3. 1-Week skip momentum [t-12m, t-5d] (skipping 5 trading days instead of 21)
    p_s1w = float(c_all.iloc[-6]) if len(c_all) >= 6 else p_s1
    mom_12_1w = p_s1w / p_l12 - 1.0

    # 4. Realized volatilities
    r_all = c_all.pct_change().dropna()
    rq_12_0 = r_qqq_full.loc[t_l12:t]
    common_12_0 = r_all.index.intersection(rq_12_0.index)
    vol_12_0 = float(np.std(r_all.loc[common_12_0].values, ddof=1) * np.sqrt(252.0)) if len(common_12_0) >= 120 else np.nan

    rq_12_1 = r_qqq_full.loc[t_l12:t_s1]
    common_12_1 = r_all.index.intersection(rq_12_1.index)
    vol_12_1 = float(np.std(r_all.loc[common_12_1].values, ddof=1) * np.sqrt(252.0)) if len(common_12_1) >= 120 else np.nan

    sharpe_mom_12_0 = mom_12_0 / vol_12_0 if (np.isfinite(vol_12_0) and vol_12_0 > 0) else np.nan
    sharpe_mom_12_1w = mom_12_1w / vol_12_1 if (np.isfinite(vol_12_1) and vol_12_1 > 0) else np.nan

    # 5. Formation-date SMA distances (Close[t] / SMA_L[t] - 1)
    sma50 = float(c_all.iloc[-50:].mean()) if len(c_all) >= 50 else float(c_all.mean())
    sma100 = float(c_all.iloc[-100:].mean()) if len(c_all) >= 100 else float(c_all.mean())
    sma200 = float(c_all.iloc[-200:].mean()) if len(c_all) >= 200 else float(c_all.mean())
    dist_sma50_t = p_t / sma50 - 1.0 if sma50 > 0 else np.nan
    dist_sma100_t = p_t / sma100 - 1.0 if sma100 > 0 else np.nan
    dist_sma200_t = p_t / sma200 - 1.0 if sma200 > 0 else np.nan

    # 6. Drawdown from last 21 trading days' peak at formation date t
    peak_21d = float(c_all.iloc[-21:].max()) if len(c_all) >= 21 else float(c_all.max())
    dd_peak_21d_t = p_t / peak_21d - 1.0 if peak_21d > 0 else np.nan

    # 7. Stock's own 21d and 63d realized volatility at formation date t
    vol_21d_t = float(np.std(r_all.iloc[-21:].values, ddof=1) * np.sqrt(252.0)) if len(r_all) >= 21 else vol_12_1
    vol_63d_t = float(np.std(r_all.iloc[-63:].values, ddof=1) * np.sqrt(252.0)) if len(r_all) >= 63 else vol_12_1

    return {
        'ret_1m': ret_1m,
        'mom_12_0': mom_12_0,
        'mom_12_1w': mom_12_1w,
        'vol_12_0': vol_12_0,
        'sharpe_mom_12_0': sharpe_mom_12_0,
        'sharpe_mom_12_1w': sharpe_mom_12_1w,
        'dist_sma50_t': dist_sma50_t,
        'dist_sma100_t': dist_sma100_t,
        'dist_sma200_t': dist_sma200_t,
        'dd_peak_21d_t': dd_peak_21d_t,
        'vol_21d_t': vol_21d_t,
        'vol_63d_t': vol_63d_t,
    }


def augment_panel(df_panel, univ, r_qqq_full):
    extra_rows = []
    for _, r in df_panel.iterrows():
        c_full = get_adjclose(univ, r['store'], r['sym'])
        feats = compute_extra_features_at_t(c_full, r['t'], r_qqq_full)
        extra_rows.append(feats)
    df_extra = pd.DataFrame(extra_rows, index=df_panel.index)
    out = df_panel.copy()
    for col in df_extra.columns:
        out[col] = df_extra[col]
    return out


def run_physical_truncation_test(df_qqq, df_tech, r_qqq_full):
    cutoffs = ['2011-12-31', '2015-06-30', '2018-12-31', '2021-12-31', '2024-06-30']
    check_cols = [
        'ret_1m', 'mom_12_0', 'mom_12_1w', 'vol_12_0', 'sharpe_mom_12_0', 'sharpe_mom_12_1w',
        'dist_sma50_t', 'dist_sma100_t', 'dist_sma200_t', 'dd_peak_21d_t', 'vol_21d_t', 'vol_63d_t'
    ]
    rows = []
    for cut in cutoffs:
        cut_ts = pd.Timestamp(cut)
        # Sample all rows AT the cutoff formation month-end (and 2 prior month-ends) for speed & exactness
        q_sub = df_qqq[pd.to_datetime(df_qqq['t']) <= cut_ts]
        t_sub = df_tech[pd.to_datetime(df_tech['t']) <= cut_ts]
        q_sample = q_sub[pd.to_datetime(q_sub['t']) >= (cut_ts - pd.offsets.MonthEnd(3))]
        t_sample = t_sub[pd.to_datetime(t_sub['t']) >= (cut_ts - pd.offsets.MonthEnd(3))]

        max_q = 0.0
        for _, r in q_sample.iterrows():
            c_full = get_adjclose('QQQ', r['store'], r['sym'])
            f_trunc = compute_extra_features_at_t(c_full, r['t'], r_qqq_full, cutoff=cut)
            for c in check_cols:
                v1, v2 = r[c], f_trunc.get(c, np.nan)
                if pd.isna(v1) and pd.isna(v2):
                    continue
                if pd.isna(v1) != pd.isna(v2):
                    max_q = max(max_q, 1.0)
                else:
                    max_q = max(max_q, abs(float(v1) - float(v2)))

        max_t = 0.0
        for _, r in t_sample.iterrows():
            c_full = get_adjclose('Tech', r['store'], r['sym'])
            f_trunc = compute_extra_features_at_t(c_full, r['t'], r_qqq_full, cutoff=cut)
            for c in check_cols:
                v1, v2 = r[c], f_trunc.get(c, np.nan)
                if pd.isna(v1) and pd.isna(v2):
                    continue
                if pd.isna(v1) != pd.isna(v2):
                    max_t = max(max_t, 1.0)
                else:
                    max_t = max(max_t, abs(float(v1) - float(v2)))

        rows.append({
            'Cutoff_Date': cut,
            'QQQ_Rows_Eligible': len(q_sub),
            'Tech_Rows_Eligible': len(t_sub),
            'QQQ_Max_Abs_Diff_12_New_Features': max_q,
            'Tech_Max_Abs_Diff_12_New_Features': max_t,
            'Status': 'PASS (0.00e+00)' if (max_q == 0.0 and max_t == 0.0) else 'FAIL',
        })
    return pd.DataFrame(rows)


# =============================================================================
# 2. Flexible Portfolio & Sleeve Simulation Engines
# =============================================================================
def rank_candidates_at_t(g, spec, exclude_tickers=None):
    """
    Returns ordered DataFrame of candidates at formation month-end t according to `spec`.
    """
    d = g.copy()
    if exclude_tickers:
        d = d[~d['ticker'].isin(exclude_tickers)]
    if spec.get('exclude_set'):
        d = d[~d['ticker'].isin(spec['exclude_set'])]

    base_col = spec.get('base_col', 'sharpe_mom_12_1')
    d = d[d[base_col].notna() & d['hold_ret'].notna()].copy()
    if len(d) == 0:
        return d

    stype = spec['type']
    if stype == 'score':
        sc = spec['score_col']
        d = d[d[sc].notna()].sort_values(sc, ascending=False)
        return d

    elif stype == 'pool_rerank':
        pool_n = spec['pool_n']
        rerank_col = spec['rerank_col']
        asc = spec.get('rerank_asc', False)
        pool = d.sort_values(base_col, ascending=False).head(pool_n).copy()
        pool_valid = pool[pool[rerank_col].notna()].sort_values([rerank_col, base_col], ascending=[asc, False])
        pool_na = pool[pool[rerank_col].isna()].sort_values(base_col, ascending=False)
        rest = d.sort_values(base_col, ascending=False).iloc[pool_n:]
        return pd.concat([pool_valid, pool_na, rest], axis=0)

    elif stype == 'veto':
        pool_n = spec.get('pool_n', 10)
        veto_fn = spec['veto_fn']
        pool = d.sort_values(base_col, ascending=False).head(pool_n).copy()
        pass_mask = ~pool.apply(veto_fn, axis=1)
        passed = pool[pass_mask]
        failed = pool[~pass_mask]
        rest = d.sort_values(base_col, ascending=False).iloc[pool_n:]
        return pd.concat([passed, failed, rest], axis=0)

    elif stype == 'rank_blend':
        pool_n = spec.get('pool_n', 10)
        sec_col = spec['sec_col']
        w = spec.get('w', 0.25)
        pool = d.sort_values(base_col, ascending=False).head(pool_n).copy()
        r1 = pool[base_col].rank(pct=True, ascending=True)
        r2 = pool[sec_col].rank(pct=True, ascending=True)
        r2 = r2.fillna(0.5)
        pool['_blend'] = (1.0 - w) * r1 + w * r2
        pool = pool.sort_values(['_blend', base_col], ascending=False)
        rest = d.sort_values(base_col, ascending=False).iloc[pool_n:]
        return pd.concat([pool, rest], axis=0)

    raise ValueError(f'Unknown spec type: {stype}')


def simulate_core3_flexible(df_qqq, df_tech, q_spec, t_spec, mode='standard',
                            mode_params=None, exclude_tickers=None, r_qqq_daily=None):
    """
    Unified monthly portfolio simulator supporting:
      - 'standard': 50% QQQ Top-2 (25% each) + 50% Tech Top-1 (50%)
      - 'deoverlap_q_yields': if Tech #1 is in QQQ Top-2, QQQ replaces duplicate with next ranked QQQ stock (50% / 25% / 25% in 3 distinct stocks)
      - 'deoverlap_t_yields': if Tech #1 is in QQQ Top-2, Tech replaces duplicate with Tech Rank #2 (25% / 25% / 50% in 3 distinct stocks)
      - 'deoverlap_eq3': 3 distinct stocks (Tech #1 + 2 non-dup QQQ stocks) at 33.33% each
      - 'cap_2stock': when overlap occurs (75% dup / 25% other QQQ), cap dup at `cap_w` (e.g. 0.50) and put `1 - cap_w` in other QQQ stock
      - 'cap_overflow_q3': when overlap occurs, cap dup at `cap_w` (e.g. 0.50), keep other QQQ at 0.25, put remaining `0.75 - cap_w` in QQQ #3
      - 'inv_vol': weight the selected distinct stocks inversely to their trailing vol (`vol_col` in {'vol_21d_t', 'vol_63d_t', 'vol_12_1'})
      - 'buffer': Hysteresis buffer rule (`q_keep` for QQQ k=2, `t_keep` for Tech k=1)
      - 'tranche_hold': Overlapping multi-month holding period (`n_tranches` in {2, 3})
      - 'port_vol_scale': Barroso & Santa-Clara (2015) portfolio-own realized volatility scaling (`win_d`, `target_vol`, Cash = 0%)
      - 'port_vol_derisk_eq': Zero-cash intra-portfolio de-risking when basket vol > threshold
      - 'dm_crash_brake': Daniel & Moskowitz (2016) bear-market rebound crash protection
      - 'qqq_ranks': custom QQQ rank indices (e.g., [2] for Rank #2 only, or [2, 3] for Rank #2+#3)
    Returns DataFrame indexed by `ym` with columns:
      `net`, `gross`, `turnover`, `exposure`, `n_distinct`, `max_single_w`, `is_overlap`, `holdings_dict`, `t_date`
    """
    if mode_params is None:
        mode_params = {}

    q_groups = {pd.Timestamp(t): g for t, g in df_qqq.groupby('t', sort=True)}
    t_groups = {pd.Timestamp(t): g for t, g in df_tech.groupby('t', sort=True)}
    common_ts = sorted(set(q_groups.keys()).intersection(set(t_groups.keys())))

    # State variables across months
    prev_q_weights = {}  # for separate sleeve accounting
    prev_t_weights = {}
    prev_port_weights = {}  # for unified portfolio accounting
    prev_q_held = []
    prev_t_held = []
    tranche_cohorts = []  # list of weight dicts for overlapping tranches
    global_meta_map = {}

    rows = []
    for idx_m, t in enumerate(common_ts):
        gq = q_groups[t]
        gt = t_groups[t]
        ym = (t + pd.offsets.MonthBegin(1)).strftime('%Y-%m')

        dq = rank_candidates_at_t(gq, q_spec, exclude_tickers=exclude_tickers)
        dt = rank_candidates_at_t(gt, t_spec, exclude_tickers=exclude_tickers)

        # Lookup map for holding returns at month t
        ret_map = {}
        vol_map = {}
        meta_map = {}
        for _, r in gq.iterrows():
            tk = r['ticker']
            ret_map[tk] = float(r['hold_ret'])
            vol_map[tk] = {
                'vol_21d_t': float(r['vol_21d_t']) if pd.notna(r['vol_21d_t']) else float(r['vol_12_1']),
                'vol_63d_t': float(r['vol_63d_t']) if pd.notna(r['vol_63d_t']) else float(r['vol_12_1']),
                'vol_12_1': float(r['vol_12_1']),
            }
            meta_map[tk] = ('qqq', r['store'], r['sym'])
            global_meta_map[tk] = ('qqq', r['store'], r['sym'])
        for _, r in gt.iterrows():
            tk = r['ticker']
            if tk not in ret_map:
                ret_map[tk] = float(r['hold_ret'])
            if tk not in vol_map:
                vol_map[tk] = {
                    'vol_21d_t': float(r['vol_21d_t']) if pd.notna(r['vol_21d_t']) else float(r['vol_12_1']),
                    'vol_63d_t': float(r['vol_63d_t']) if pd.notna(r['vol_63d_t']) else float(r['vol_12_1']),
                    'vol_12_1': float(r['vol_12_1']),
                }
            if tk not in meta_map:
                meta_map[tk] = ('tech', r['store'], r['sym'])
                global_meta_map[tk] = ('tech', r['store'], r['sym'])

        q_ranked = list(dq['ticker'].values)
        t_ranked = list(dt['ticker'].values)

        # Default picks: QQQ Top-2, Tech Top-1
        q_picks = q_ranked[:2]
        t_picks = t_ranked[:1]

        if mode == 'buffer':
            q_keep = mode_params.get('q_keep', 2)
            t_keep = mode_params.get('t_keep', 1)
            # QQQ k=2 with buffer q_keep
            q_top_keep = set(q_ranked[:q_keep])
            kept_q = [tk for tk in prev_q_held if tk in q_top_keep][:2]
            for tk in q_ranked:
                if len(kept_q) >= 2:
                    break
                if tk not in kept_q:
                    kept_q.append(tk)
            q_picks = kept_q
            prev_q_held = list(q_picks)

            # Tech k=1 with buffer t_keep
            t_top_keep = set(t_ranked[:t_keep])
            kept_t = [tk for tk in prev_t_held if tk in t_top_keep][:1]
            for tk in t_ranked:
                if len(kept_t) >= 1:
                    break
                if tk not in kept_t:
                    kept_t.append(tk)
            t_picks = kept_t
            prev_t_held = list(t_picks)

        elif mode == 'qqq_ranks':
            rk_list = mode_params['ranks']  # 1-based rank indices, e.g. [2] or [2, 3] or [1, 2, 3]
            q_picks = [q_ranked[r_idx - 1] for r_idx in rk_list if (r_idx - 1) < len(q_ranked)]
            if not q_picks and len(q_ranked):
                q_picks = [q_ranked[0]]

        # Check raw overlap between default QQQ Top-2 and Tech Top-1
        is_overlap = bool(len(t_picks) and (t_picks[0] in q_picks))

        # Construct target portfolio weights w_target (dict of ticker -> weight)
        w_target = {}
        exposure = 1.0

        if mode in ('standard', 'buffer', 'qqq_ranks', 'tranche_hold', 'port_vol_scale', 'port_vol_derisk_eq', 'dm_crash_brake'):
            for tk in q_picks:
                w_target[tk] = w_target.get(tk, 0.0) + 0.50 / len(q_picks)
            for tk in t_picks:
                w_target[tk] = w_target.get(tk, 0.0) + 0.50 / len(t_picks)

        elif mode == 'deoverlap_q_yields':
            # Tech gets its #1 (50%); QQQ picks top-2 distinct from Tech #1 (25% each)
            t_tk = t_picks[0]
            w_target[t_tk] = 0.50
            q_nondup = [tk for tk in q_ranked if tk != t_tk][:2]
            for tk in q_nondup:
                w_target[tk] = w_target.get(tk, 0.0) + 0.50 / len(q_nondup)

        elif mode == 'deoverlap_t_yields':
            # QQQ gets its Top-2 (25% each); Tech picks highest non-overlapping with QQQ Top-2 (50%)
            for tk in q_picks:
                w_target[tk] = 0.25
            t_nondup = [tk for tk in t_ranked if tk not in q_picks][:1]
            if not t_nondup:
                t_nondup = t_picks
            w_target[t_nondup[0]] = w_target.get(t_nondup[0], 0.0) + 0.50

        elif mode == 'deoverlap_eq3':
            t_tk = t_picks[0]
            q_nondup = [tk for tk in q_ranked if tk != t_tk][:2]
            distinct_3 = [t_tk] + q_nondup
            for tk in distinct_3:
                w_target[tk] = 1.0 / len(distinct_3)

        elif mode == 'cap_2stock':
            cap_w = mode_params['cap_w']  # e.g. 0.40, 0.50, 0.60
            if is_overlap and len(q_picks) == 2:
                dup_tk = t_picks[0]
                other_tk = [tk for tk in q_picks if tk != dup_tk][0]
                w_target[dup_tk] = cap_w
                w_target[other_tk] = 1.0 - cap_w
            else:
                for tk in q_picks:
                    w_target[tk] = w_target.get(tk, 0.0) + 0.25
                for tk in t_picks:
                    w_target[tk] = w_target.get(tk, 0.0) + 0.50

        elif mode == 'cap_overflow_q3':
            cap_w = mode_params.get('cap_w', 0.50)
            if is_overlap and len(q_picks) == 2 and len(q_ranked) >= 3:
                dup_tk = t_picks[0]
                other_tk = [tk for tk in q_picks if tk != dup_tk][0]
                q3_tk = [tk for tk in q_ranked if tk not in (dup_tk, other_tk)][0]
                w_target[dup_tk] = cap_w
                w_target[other_tk] = 0.25
                w_target[q3_tk] = 0.75 - cap_w
            else:
                for tk in q_picks:
                    w_target[tk] = w_target.get(tk, 0.0) + 0.25
                for tk in t_picks:
                    w_target[tk] = w_target.get(tk, 0.0) + 0.50

        elif mode == 'inv_vol':
            vcol = mode_params.get('vol_col', 'vol_63d_t')
            deov = mode_params.get('deoverlap', False)
            if deov:
                t_tk = t_picks[0]
                cands = [t_tk] + [tk for tk in q_ranked if tk != t_tk][:2]
            else:
                cands = list(dict.fromkeys(q_picks + t_picks))
            inv_vs = []
            for tk in cands:
                v = max(0.08, vol_map.get(tk, {}).get(vcol, 0.30))
                inv_vs.append(1.0 / v)
            s_iv = sum(inv_vs)
            for tk, iv in zip(cands, inv_vs):
                w_target[tk] = iv / s_iv

        # Handle overlapping multi-month cohorts (G4)
        if mode == 'tranche_hold':
            n_tr = mode_params.get('n_tranches', 2)
            tranche_cohorts.append(dict(w_target))
            if len(tranche_cohorts) > n_tr:
                tranche_cohorts.pop(0)
            w_comb = {}
            valid_cohorts = []
            for coh in tranche_cohorts:
                coh_valid = {tk: wv for tk, wv in coh.items() if tk in ret_map}
                s_c = sum(coh_valid.values())
                if s_c > 0:
                    valid_cohorts.append({tk: wv / s_c for tk, wv in coh_valid.items()})
            for coh in valid_cohorts:
                for tk, wv in coh.items():
                    w_comb[tk] = w_comb.get(tk, 0.0) + wv / len(valid_cohorts)
            w_target = w_comb

        # Compute portfolio-own trailing realized volatility at formation date t (H1 / H2 / H3)
        if mode in ('port_vol_scale', 'port_vol_derisk_eq'):
            win_d = mode_params.get('win_d', 21)
            # Reconstruct historical daily returns of w_target basket over [t - win_d trading days : t]
            q_cal = r_qqq_daily.loc[:t].iloc[-win_d:].index
            basket_daily = np.zeros(len(q_cal))
            for tk, wv in w_target.items():
                u_tk, st_tk, sym_tk = global_meta_map[tk]
                r_s = get_daily_ret(u_tk, st_tk, sym_tk).reindex(q_cal).fillna(0.0).values
                basket_daily += wv * r_s
            port_realized_vol = float(np.std(basket_daily, ddof=1) * np.sqrt(252.0)) if len(basket_daily) >= 10 else 0.30

            if mode == 'port_vol_scale':
                target_vol = mode_params['target_vol']
                exposure = min(1.0, target_vol / max(port_realized_vol, 0.05))
                w_target = {tk: wv * exposure for tk, wv in w_target.items()}
            elif mode == 'port_vol_derisk_eq':
                trig_vol = mode_params.get('trig_vol', 0.40)
                if port_realized_vol > trig_vol:
                    # De-overlap to 3 distinct stocks and weight by inverse 63d vol (stay 100% invested!)
                    t_tk = t_picks[0]
                    cands = [t_tk] + [tk for tk in q_ranked if tk != t_tk][:2]
                    inv_vs = [1.0 / max(0.08, vol_map.get(tk, {}).get('vol_63d_t', 0.30)) for tk in cands]
                    s_iv = sum(inv_vs)
                    w_target = {tk: iv / s_iv for tk, iv in zip(cands, inv_vs)}

        # Handle Daniel & Moskowitz (2016) Panic-Rebound Crash State (H4)
        if mode == 'dm_crash_brake':
            # Bear market indicator: QQQ trailing 12m return at t < 0
            q_cal_252 = r_qqq_daily.loc[:t].iloc[-252:]
            q_ret_12m = float(np.prod(1.0 + q_cal_252.values) - 1.0) if len(q_cal_252) >= 60 else 0.0
            q_ret_1m = float(np.prod(1.0 + q_cal_252.iloc[-21:].values) - 1.0) if len(q_cal_252) >= 21 else 0.0
            q_vol_21d = float(np.std(q_cal_252.iloc[-21:].values, ddof=1) * np.sqrt(252.0)) if len(q_cal_252) >= 21 else 0.15

            action = mode_params.get('action', 'scale_50')
            in_crash_state = (q_ret_12m < 0.0) and ((q_ret_1m > 0.02) or (q_vol_21d > 0.30))
            if in_crash_state:
                if action == 'scale_50':
                    exposure = 0.50
                    w_target = {tk: wv * 0.50 for tk, wv in w_target.items()}
                elif action == 'scale_75':
                    exposure = 0.75
                    w_target = {tk: wv * 0.75 for tk, wv in w_target.items()}
                elif action == 'switch_res_100':
                    # Stay 100% invested, switch to Residual Sharpe winners during bear rebound
                    dq_res = rank_candidates_at_t(gq, {'type': 'score', 'base_col': 'res_sharpe_qqq_12_1', 'score_col': 'res_sharpe_qqq_12_1'}, exclude_tickers=exclude_tickers)
                    dt_res = rank_candidates_at_t(gt, {'type': 'score', 'base_col': 'res_sharpe_xlk_12_1', 'score_col': 'res_sharpe_xlk_12_1'}, exclude_tickers=exclude_tickers)
                    w_target = {}
                    for tk in list(dq_res['ticker'].values)[:2]:
                        w_target[tk] = w_target.get(tk, 0.0) + 0.25
                    for tk in list(dt_res['ticker'].values)[:1]:
                        w_target[tk] = w_target.get(tk, 0.0) + 0.50

        # Exact Sleeve-Consistent or Unified Turnover & Net Return Accounting
        if mode in ('standard', 'buffer') and len(q_picks) == 2 and len(t_picks) == 1:
            # Match exact Sleeve 1 + Sleeve 2 accounting of Core3
            wq = {tk: 0.50 for tk in q_picks}
            wt = {t_picks[0]: 1.0}
            if not prev_q_weights:
                to_q = 2.0
            else:
                all_q = set(prev_q_weights) | set(wq)
                to_q = sum(abs(wq.get(k, 0.0) - prev_q_weights.get(k, 0.0)) for k in all_q)
            if not prev_t_weights:
                to_t = 1.0
            else:
                all_t = set(prev_t_weights) | set(wt)
                to_t = sum(abs(wt.get(k, 0.0) - prev_t_weights.get(k, 0.0)) for k in all_t)

            gross_q = sum(wv * ret_map.get(tk, 0.0) for tk, wv in wq.items())
            net_q = gross_q - COST_BP * to_q
            gross_t = sum(wv * ret_map.get(tk, 0.0) for tk, wv in wt.items())
            net_t = (1.0 + gross_t) * ((1.0 - COST_BP) ** to_t) - 1.0 if to_t > 0 else gross_t

            gross_p = 0.50 * gross_q + 0.50 * gross_t
            net_p = 0.50 * net_q + 0.50 * net_t
            to_p = 0.50 * to_q + 0.50 * to_t

            # Drift sleeve weights to end of month
            denom_q = sum(wv * (1.0 + ret_map.get(tk, 0.0)) for tk, wv in wq.items())
            prev_q_weights = {tk: wv * (1.0 + ret_map.get(tk, 0.0)) / denom_q for tk, wv in wq.items()} if denom_q > 0 else {}
            denom_t = sum(wv * (1.0 + ret_map.get(tk, 0.0)) for tk, wv in wt.items())
            prev_t_weights = {tk: wv * (1.0 + ret_map.get(tk, 0.0)) / denom_t for tk, wv in wt.items()} if denom_t > 0 else {}
        else:
            # Unified portfolio turnover accounting
            if not prev_port_weights:
                to_p = 1.50 * sum(w_target.values())
            else:
                all_k = set(prev_port_weights) | set(w_target)
                to_p = sum(abs(w_target.get(k, 0.0) - prev_port_weights.get(k, 0.0)) for k in all_k)
            gross_p = sum(wv * ret_map.get(tk, 0.0) for tk, wv in w_target.items())
            net_p = gross_p - COST_BP * to_p
            # Drift portfolio weights (including cash if exposure < 1)
            cash_w = max(0.0, 1.0 - sum(w_target.values()))
            denom_p = cash_w + sum(wv * (1.0 + ret_map.get(tk, 0.0)) for tk, wv in w_target.items())
            prev_port_weights = {tk: wv * (1.0 + ret_map.get(tk, 0.0)) / denom_p for tk, wv in w_target.items()} if denom_p > 0 else {}

        rows.append({
            'ym': ym,
            't_date': t,
            'gross': gross_p,
            'net': net_p,
            'turnover': to_p,
            'exposure': exposure,
            'n_distinct': len(w_target),
            'max_single_w': max(w_target.values()) if w_target else 0.0,
            'is_overlap': is_overlap,
            'holdings_dict': dict(w_target),
            'meta_map': dict(global_meta_map),
        })

    return pd.DataFrame(rows).set_index('ym')


# =============================================================================
# 3. True Daily Equity Curve & Drawdown Reconstruction for Arbitrary Holdings
# =============================================================================
_DAILY_STOCK_CACHE = {}


def load_daily_stock_series(sleeve, tk, t_form, store, sym):
    t_form = pd.Timestamp(t_form)
    if sleeve == 'qqq' or ':' in str(store):
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
    else:
        segs = TE.segments(tk)
        d0 = QE.first_td_after(t_form, 1)
        d1 = QE.first_td_after(t_form + pd.offsets.MonthEnd(1), 1)
        order = [x for x in segs if d0 in x[0].index and d1 in x[0].index] + \
                [x for x in segs if d0 in x[0].index and d1 not in x[0].index]
        chosen = order[0] if order else segs[0]
        df_raw, src, sym_c, _ = chosen
        ckey = ('tech', tk, src, sym_c, str(df_raw.index.min().date()), str(df_raw.index.max().date()))
        if ckey not in _DAILY_STOCK_CACHE:
            df = pd.DataFrame({
                'adjclose': df_raw['adjclose'],
                'adjopen': df_raw['adj_open'] if 'adj_open' in df_raw.columns else np.nan,
            }, index=df_raw.index).sort_index()
            df = df[~df.index.duplicated(keep='last')]
            df['adjopen_clean'] = df['adjopen'].where(df['adjopen'].notna() & (df['adjopen'] > 0), df['adjclose'])
            _DAILY_STOCK_CACHE[ckey] = df
        return _DAILY_STOCK_CACHE[ckey]


def compute_daily_dd_general(ledger_df, cal_days):
    """
    Reconstructs true daily equity curves for any monthly holdings dictionary `holdings_dict`
    under both:
      1. `5651ec2` Close-to-Close intra-month path + exact monthly net terminal lock (matches -46.76% on Frozen Core3)
      2. Exact Open-to-Close (`O2C`) execution path from first trading day open to next month first trading day open (matches -49.68% on Frozen Core3)
    """
    W = 1.0
    pts_c56 = {}
    pts_o2c = {}

    for ym, row in ledger_df.iterrows():
        t_form = pd.Timestamp(row['t_date'])
        m_dt = t_form + pd.offsets.MonthEnd(1)
        e_d = QE.first_td_after(t_form, 1)
        x_d = QE.first_td_after(m_dt, 1)
        m_days = cal_days[(cal_days >= e_d) & (cal_days < x_d)]
        if not len(m_days):
            continue

        w_dict = row['holdings_dict']
        meta_map = row['meta_map']
        cash_w = max(0.0, 1.0 - sum(w_dict.values()))

        s_map = {}
        pe_map = {}
        v0_map = {}
        for tk in w_dict:
            u_tk, st_tk, sym_tk = meta_map[tk]
            s_df = load_daily_stock_series(u_tk, tk, t_form, st_tk, sym_tk)
            s_map[tk] = s_df
            pe = float(s_df.loc[:e_d, 'adjopen_clean'].iloc[-1])
            pe_map[tk] = pe
            v0_map[tk] = float(s_df.loc[:m_days[0], 'adjclose'].iloc[-1]) / pe

        m_cost = float(row['gross'] - row['net'])
        W_after_entry = W * (1.0 - m_cost)

        for d in m_days:
            val_56 = cash_w * 1.0
            val_o2c = cash_w * 1.0
            for tk, wv in w_dict.items():
                s_df = s_map[tk]
                v_i = float(s_df.loc[:d, 'adjclose'].iloc[-1]) / pe_map[tk]
                val_56 += wv * (v_i / v0_map[tk])
                val_o2c += wv * v_i
            pts_c56[d] = W * val_56
            pts_o2c[d] = W_after_entry * val_o2c

        W = W * (1.0 + float(row['net']))
        pts_c56[x_d] = W
        pts_o2c[x_d] = W

    s_c56 = pd.Series(pts_c56).sort_index()
    s_c56 = s_c56[~s_c56.index.duplicated(keep='last')]
    s_o2c = pd.Series(pts_o2c).sort_index()
    s_o2c = s_o2c[~s_o2c.index.duplicated(keep='last')]
    dd_56 = float((s_c56 / s_c56.cummax() - 1.0).min())
    dd_o2c = float((s_o2c / s_o2c.cummax() - 1.0).min())
    return dd_56, dd_o2c


# =============================================================================
# 4. Statistical Summary Helper
# =============================================================================
def nw_tstat(x, lags=3):
    x = np.asarray(pd.Series(x).dropna(), float)
    n = len(x)
    if n < 6:
        return np.nan
    m = x.mean()
    e = x - m
    g0 = np.dot(e, e) / n
    v = g0
    for l in range(1, min(lags, n - 1) + 1):
        w = 1.0 - l / (lags + 1.0)
        gl = np.dot(e[l:], e[:-l]) / n
        v += 2.0 * w * gl
    se = np.sqrt(max(v, 1e-16) / n)
    return float(m / se)


def summarize_ledger(label, hyp, L, rf_m, ref_r=None, cal_days=None):
    r_m = L['net'].dropna()
    n = len(r_m)
    yrs = n / 12.0
    tot = float(np.prod(1.0 + r_m))
    cagr = tot ** (1.0 / yrs) - 1.0
    vol = float(r_m.std(ddof=1) * np.sqrt(12.0))
    rf_al = rf_m.reindex(r_m.index).ffill().fillna(0.0)
    ex = r_m - rf_al
    sharpe = float(ex.mean() / r_m.std(ddof=1) * np.sqrt(12.0)) if r_m.std(ddof=1) > 0 else np.nan
    dn = r_m[r_m < 0]
    sortino = float(ex.mean() * 12.0 / (dn.std(ddof=1) * np.sqrt(12.0))) if len(dn) > 1 and dn.std(ddof=1) > 0 else np.nan
    eq = (1.0 + r_m).cumprod()
    mdd = float((eq / eq.cummax() - 1.0).min())

    r_early = r_m[(r_m.index >= '2009-01') & (r_m.index <= '2018-12')]
    cagr_early = float((np.prod(1.0 + r_early)) ** (12.0 / len(r_early)) - 1.0) if len(r_early) else np.nan
    r_late = r_m[r_m.index >= '2019-01']
    cagr_late = float((np.prod(1.0 + r_late)) ** (12.0 / len(r_late)) - 1.0) if len(r_late) else np.nan
    r_22 = r_m[(r_m.index >= '2022-01') & (r_m.index <= '2022-12')]
    ret_22 = float(np.prod(1.0 + r_22) - 1.0) if len(r_22) else np.nan

    dd56, ddo2c = (np.nan, np.nan)
    if cal_days is not None:
        dd56, ddo2c = compute_daily_dd_general(L, cal_days)

    t_diff = np.nan
    if ref_r is not None:
        diff = (r_m - ref_r.reindex(r_m.index)).dropna()
        if np.std(diff) > 1e-8:
            t_diff = nw_tstat(diff, lags=3)

    return {
        'Variant': label,
        'Hypothesis': hyp,
        'CAGR_09_26': cagr,
        'Ann_Vol': vol,
        'Sharpe_m': sharpe,
        'Sortino_m': sortino,
        'Monthly_MaxDD': mdd,
        'Daily_MaxDD_5651ec2': dd56,
        'Daily_MaxDD_O2C': ddo2c,
        'Calmar_Daily': cagr / abs(dd56) if (np.isfinite(dd56) and dd56 < 0) else np.nan,
        'CAGR_2009_2018': cagr_early,
        'CAGR_2019_2026': cagr_late,
        'Ret_2022': ret_22,
        'Avg_Monthly_TO': float(L['turnover'].mean()),
        'Avg_Distinct_Stocks': float(L['n_distinct'].mean()),
        'Max_Single_Weight': float(L['max_single_w'].max()),
        'Avg_Exposure': float(L['exposure'].mean()),
        'NW_t_vs_Control': t_diff,
    }


# =============================================================================
# 5. Main Execution Suite (Hypotheses E, F, G, H, I)
# =============================================================================
def main():
    print('=== STARTING CLEAN-ROOM AUDIT OF OVERLOOKED STRUCTURAL & ACADEMIC MECHANISMS (E, F, G, H, I) ===')
    df_q_base = pd.read_parquet(os.path.join(SEL_DIR, 'qqq_selection_panel.parquet'))
    df_t_base = pd.read_parquet(os.path.join(SEL_DIR, 'tech_selection_panel.parquet'))
    df_qt_base = pd.read_parquet(os.path.join(SEL_DIR, 'qqq_selection_panel_tiingo.parquet'))
    df_tt_base = pd.read_parquet(os.path.join(SEL_DIR, 'tech_selection_panel_tiingo.parquet'))

    df_qqq_idx = QE.series('tiingo_api', 'QQQ')
    if df_qqq_idx is None:
        df_qqq_idx = QE.series('yahoo', 'QQQ')
    r_qqq_daily = df_qqq_idx['adjclose'].dropna().sort_index().pct_change().dropna()
    cal_days = df_qqq_idx['adjclose'].dropna().sort_index().index
    import json
    with open(os.path.join(ROOT, 'data', 'fred', 'DGS3MO.json')) as f:
        dgs = json.load(f)['values']
    rf_s = pd.Series(
        {pd.Timestamp(d): float(v) / 100.0 for d, v in dgs if v is not None},
        dtype=float
    ).sort_index()
    rf_m_raw = (1.0 + rf_s.resample('ME').last()) ** (1.0 / 12.0) - 1.0
    rf_monthly = pd.Series(rf_m_raw.values, index=rf_m_raw.index.strftime('%Y-%m'))

    print('Augmenting panels with strictly causal formation-date features (ret_1m, mom_12_0, mom_12_1w, SMA50/100/200, 21d peak DD, 21d/63d vol)...')
    df_qqq = augment_panel(df_q_base, 'QQQ', r_qqq_daily)
    df_tech = augment_panel(df_t_base, 'Tech', r_qqq_daily)
    df_qqq_t = augment_panel(df_qt_base, 'QQQ', r_qqq_daily)
    df_tech_t = augment_panel(df_tt_base, 'Tech', r_qqq_daily)

    print('Running Physical Truncation Look-Ahead Audit across 5 historical cutoffs x 12 new features...')
    df_trunc = run_physical_truncation_test(df_qqq, df_tech, r_qqq_daily)
    df_trunc.to_csv(os.path.join(HERE, '00_pit_truncation_audit.csv'), index=False)
    print(df_trunc.to_string(index=False))
    assert (df_trunc['QQQ_Max_Abs_Diff_12_New_Features'].max() == 0.0) and (df_trunc['Tech_Max_Abs_Diff_12_New_Features'].max() == 0.0)

    ctrl_q_spec = {'type': 'score', 'base_col': 'sharpe_mom_12_1', 'score_col': 'sharpe_mom_12_1'}
    ctrl_t_spec = {'type': 'score', 'base_col': 'mom_12_1', 'score_col': 'mom_12_1'}

    L_ctrl = simulate_core3_flexible(df_qqq, df_tech, ctrl_q_spec, ctrl_t_spec, mode='standard')
    r_ctrl = L_ctrl['net']

    master_rows = []
    all_series = {'00. Core3 Control [FROZEN]': r_ctrl}

    def run_and_record(label, hyp, q_spec, t_spec, mode='standard', mode_params=None):
        L = simulate_core3_flexible(df_qqq, df_tech, q_spec, t_spec, mode=mode,
                                    mode_params=mode_params, r_qqq_daily=r_qqq_daily)
        row = summarize_ledger(label, hyp, L, rf_monthly, ref_r=r_ctrl, cal_days=cal_days)
        master_rows.append(row)
        all_series[label] = L['net']
        print(f"  {label:<68} | CAGR={row['CAGR_09_26']*100:6.2f}% | MonthDD={row['Monthly_MaxDD']*100:6.2f}% | "
              f"DailyDD={row['Daily_MaxDD_5651ec2']*100:6.2f}% | Sharpe={row['Sharpe_m']:4.2f} | TO={row['Avg_Monthly_TO']:4.2f} | "
              f"2009-18={row['CAGR_2009_2018']*100:5.2f}% | 2019-26={row['CAGR_2019_2026']*100:5.2f}% | t={row['NW_t_vs_Control']:+5.2f}")
        return L, row

    print('\n--- [0] Baseline Control ---')
    run_and_record('00. Core3 Control (50% QQQ Sharpe-Mom Top-2 + 50% Tech Mom Top-1) [FROZEN]',
                   '0. Control', ctrl_q_spec, ctrl_t_spec, mode='standard')

    # =========================================================================
    # HYPOTHESIS E: Cross-Sleeve Overlap & Concentration Mechanics
    # =========================================================================
    print('\n--- [E] Hypothesis E: Cross-Sleeve Overlap & 75% Single-Stock Concentration ---')
    # First: Forensic attribution of Overlap Months vs Non-Overlap Months
    q_groups = {pd.Timestamp(t): g for t, g in df_qqq.groupby('t', sort=True)}
    t_groups = {pd.Timestamp(t): g for t, g in df_tech.groupby('t', sort=True)}
    common_ts = sorted(set(q_groups.keys()).intersection(set(t_groups.keys())))

    ov_details = []
    for t in common_ts:
        ym = (t + pd.offsets.MonthBegin(1)).strftime('%Y-%m')
        dq = rank_candidates_at_t(q_groups[t], ctrl_q_spec)
        dt = rank_candidates_at_t(t_groups[t], ctrl_t_spec)
        q1, q2, q3 = dq['ticker'].iloc[0], dq['ticker'].iloc[1], dq['ticker'].iloc[2]
        rq1, rq2, rq3 = float(dq['hold_ret'].iloc[0]), float(dq['hold_ret'].iloc[1]), float(dq['hold_ret'].iloc[2])
        t1, t2 = dt['ticker'].iloc[0], dt['ticker'].iloc[1]
        rt1, rt2 = float(dt['hold_ret'].iloc[0]), float(dt['hold_ret'].iloc[1])
        is_ov = (t1 in (q1, q2))
        dup_ret = rt1 if is_ov else np.nan
        nondup_q_ret = (rq2 if t1 == q1 else rq1) if is_ov else np.nan
        ov_details.append({
            'ym': ym,
            'is_overlap': is_ov,
            'q1': q1, 'q2': q2, 'q3': q3, 't1': t1, 't2': t2,
            'core3_net': float(L_ctrl.loc[ym, 'net']),
            'dup_75pct_stock_ret': dup_ret,
            'other_25pct_qqq_ret': nondup_q_ret,
            'qqq_rank3_replacement_ret': rq3 if is_ov else np.nan,
            'tech_rank2_replacement_ret': rt2 if is_ov else np.nan,
        })
    df_ov_det = pd.DataFrame(ov_details)
    ov_sub = df_ov_det[df_ov_det['is_overlap']]
    nonov_sub = df_ov_det[~df_ov_det['is_overlap']]

    ov_attrib_rows = [
        {
            'Subsample_or_Leg': 'All 213 Months (Full Core3 Baseline)',
            'N_Months': len(df_ov_det),
            'Share_of_Months': 1.0,
            'Mean_Monthly_Ret': float(df_ov_det['core3_net'].mean()),
            'Compound_Ann_Ret': float((np.prod(1.0 + df_ov_det['core3_net'])) ** (12.0 / len(df_ov_det)) - 1.0),
            'Ann_Vol': float(df_ov_det['core3_net'].std(ddof=1) * np.sqrt(12.0)),
            'Ann_Sharpe': float(df_ov_det['core3_net'].mean() / df_ov_det['core3_net'].std(ddof=1) * np.sqrt(12.0)),
            'Win_Rate': float((df_ov_det['core3_net'] > 0).mean()),
            'Worst_Month': float(df_ov_det['core3_net'].min()),
            'Best_Month': float(df_ov_det['core3_net'].max()),
        },
        {
            'Subsample_or_Leg': 'Overlap Months Only (75% Single-Stock Weight, 2 Distinct Stocks)',
            'N_Months': len(ov_sub),
            'Share_of_Months': len(ov_sub) / len(df_ov_det),
            'Mean_Monthly_Ret': float(ov_sub['core3_net'].mean()),
            'Compound_Ann_Ret': float((np.prod(1.0 + ov_sub['core3_net'])) ** (12.0 / len(ov_sub)) - 1.0),
            'Ann_Vol': float(ov_sub['core3_net'].std(ddof=1) * np.sqrt(12.0)),
            'Ann_Sharpe': float(ov_sub['core3_net'].mean() / ov_sub['core3_net'].std(ddof=1) * np.sqrt(12.0)),
            'Win_Rate': float((ov_sub['core3_net'] > 0).mean()),
            'Worst_Month': float(ov_sub['core3_net'].min()),
            'Best_Month': float(ov_sub['core3_net'].max()),
        },
        {
            'Subsample_or_Leg': 'Non-Overlap Months Only (50%/25%/25% Weights, 3 Distinct Stocks)',
            'N_Months': len(nonov_sub),
            'Share_of_Months': len(nonov_sub) / len(df_ov_det),
            'Mean_Monthly_Ret': float(nonov_sub['core3_net'].mean()),
            'Compound_Ann_Ret': float((np.prod(1.0 + nonov_sub['core3_net'])) ** (12.0 / len(nonov_sub)) - 1.0),
            'Ann_Vol': float(nonov_sub['core3_net'].std(ddof=1) * np.sqrt(12.0)),
            'Ann_Sharpe': float(nonov_sub['core3_net'].mean() / nonov_sub['core3_net'].std(ddof=1) * np.sqrt(12.0)),
            'Win_Rate': float((nonov_sub['core3_net'] > 0).mean()),
            'Worst_Month': float(nonov_sub['core3_net'].min()),
            'Best_Month': float(nonov_sub['core3_net'].max()),
        },
        {
            'Subsample_or_Leg': 'Inside Overlap Months: The 75%-Weighted Overlapping Stock (Both QQQ & Tech Winner)',
            'N_Months': len(ov_sub),
            'Share_of_Months': len(ov_sub) / len(df_ov_det),
            'Mean_Monthly_Ret': float(ov_sub['dup_75pct_stock_ret'].mean()),
            'Compound_Ann_Ret': float((np.prod(1.0 + ov_sub['dup_75pct_stock_ret'])) ** (12.0 / len(ov_sub)) - 1.0),
            'Ann_Vol': float(ov_sub['dup_75pct_stock_ret'].std(ddof=1) * np.sqrt(12.0)),
            'Ann_Sharpe': float(ov_sub['dup_75pct_stock_ret'].mean() / ov_sub['dup_75pct_stock_ret'].std(ddof=1) * np.sqrt(12.0)),
            'Win_Rate': float((ov_sub['dup_75pct_stock_ret'] > 0).mean()),
            'Worst_Month': float(ov_sub['dup_75pct_stock_ret'].min()),
            'Best_Month': float(ov_sub['dup_75pct_stock_ret'].max()),
        },
        {
            'Subsample_or_Leg': 'Inside Overlap Months: The 25%-Weighted Non-Overlapping 2nd QQQ Stock',
            'N_Months': len(ov_sub),
            'Share_of_Months': len(ov_sub) / len(df_ov_det),
            'Mean_Monthly_Ret': float(ov_sub['other_25pct_qqq_ret'].mean()),
            'Compound_Ann_Ret': float((np.prod(1.0 + ov_sub['other_25pct_qqq_ret'])) ** (12.0 / len(ov_sub)) - 1.0),
            'Ann_Vol': float(ov_sub['other_25pct_qqq_ret'].std(ddof=1) * np.sqrt(12.0)),
            'Ann_Sharpe': float(ov_sub['other_25pct_qqq_ret'].mean() / ov_sub['other_25pct_qqq_ret'].std(ddof=1) * np.sqrt(12.0)),
            'Win_Rate': float((ov_sub['other_25pct_qqq_ret'] > 0).mean()),
            'Worst_Month': float(ov_sub['other_25pct_qqq_ret'].min()),
            'Best_Month': float(ov_sub['other_25pct_qqq_ret'].max()),
        },
        {
            'Subsample_or_Leg': 'Inside Overlap Months: Replacement QQQ Rank #3 Stock (If De-Overlapped)',
            'N_Months': len(ov_sub),
            'Share_of_Months': len(ov_sub) / len(df_ov_det),
            'Mean_Monthly_Ret': float(ov_sub['qqq_rank3_replacement_ret'].mean()),
            'Compound_Ann_Ret': float((np.prod(1.0 + ov_sub['qqq_rank3_replacement_ret'])) ** (12.0 / len(ov_sub)) - 1.0),
            'Ann_Vol': float(ov_sub['qqq_rank3_replacement_ret'].std(ddof=1) * np.sqrt(12.0)),
            'Ann_Sharpe': float(ov_sub['qqq_rank3_replacement_ret'].mean() / ov_sub['qqq_rank3_replacement_ret'].std(ddof=1) * np.sqrt(12.0)),
            'Win_Rate': float((ov_sub['qqq_rank3_replacement_ret'] > 0).mean()),
            'Worst_Month': float(ov_sub['qqq_rank3_replacement_ret'].min()),
            'Best_Month': float(ov_sub['qqq_rank3_replacement_ret'].max()),
        },
        {
            'Subsample_or_Leg': 'Inside Overlap Months: Replacement Tech Rank #2 Stock (If Tech Yields)',
            'N_Months': len(ov_sub),
            'Share_of_Months': len(ov_sub) / len(df_ov_det),
            'Mean_Monthly_Ret': float(ov_sub['tech_rank2_replacement_ret'].mean()),
            'Compound_Ann_Ret': float((np.prod(1.0 + ov_sub['tech_rank2_replacement_ret'])) ** (12.0 / len(ov_sub)) - 1.0),
            'Ann_Vol': float(ov_sub['tech_rank2_replacement_ret'].std(ddof=1) * np.sqrt(12.0)),
            'Ann_Sharpe': float(ov_sub['tech_rank2_replacement_ret'].mean() / ov_sub['tech_rank2_replacement_ret'].std(ddof=1) * np.sqrt(12.0)),
            'Win_Rate': float((ov_sub['tech_rank2_replacement_ret'] > 0).mean()),
            'Worst_Month': float(ov_sub['tech_rank2_replacement_ret'].min()),
            'Best_Month': float(ov_sub['tech_rank2_replacement_ret'].max()),
        },
    ]
    df_ov_attrib = pd.DataFrame(ov_attrib_rows)
    df_ov_attrib.to_csv(os.path.join(HERE, '01_overlap_forensic_attribution.csv'), index=False)

    # E1–E4 Variants
    run_and_record('E1a. De-Overlap (QQQ Yields to Tech: Always 3 Distinct Stocks 50%/25%/25%)',
                   'E. Overlap & Concentration', ctrl_q_spec, ctrl_t_spec, mode='deoverlap_q_yields')
    run_and_record('E1b. De-Overlap (Tech Yields to QQQ: Always 3 Distinct Stocks 25%/25%/50%)',
                   'E. Overlap & Concentration', ctrl_q_spec, ctrl_t_spec, mode='deoverlap_t_yields')
    run_and_record('E1c. De-Overlap + Equal Weight (3 Distinct Stocks at 33.3% Each)',
                   'E. Overlap & Concentration', ctrl_q_spec, ctrl_t_spec, mode='deoverlap_eq3')

    for cap_w in (0.40, 0.50, 0.60):
        run_and_record(f'E2. Single-Stock Cap {int(cap_w*100)}% (Overlap 75/25 -> {int(cap_w*100)}/{int((1-cap_w)*100)} in Same 2 Stocks)',
                       'E. Overlap & Concentration', ctrl_q_spec, ctrl_t_spec,
                       mode='cap_2stock', mode_params={'cap_w': cap_w})

    run_and_record('E3. Single-Stock Cap 50% + Overflow 25% to QQQ Rank #3',
                   'E. Overlap & Concentration', ctrl_q_spec, ctrl_t_spec,
                   mode='cap_overflow_q3', mode_params={'cap_w': 0.50})

    for vcol, vname in [('vol_21d_t', '21d Vol'), ('vol_63d_t', '63d Vol'), ('vol_12_1', '252d Vol')]:
        run_and_record(f'E4a. Inverse-Vol Weighting Across Selected Core3 Stocks ({vname})',
                       'E. Overlap & Concentration', ctrl_q_spec, ctrl_t_spec,
                       mode='inv_vol', mode_params={'vol_col': vcol, 'deoverlap': False})
        run_and_record(f'E4b. De-Overlapped 3 Distinct Stocks + Inverse-Vol Weighting ({vname})',
                       'E. Overlap & Concentration', ctrl_q_spec, ctrl_t_spec,
                       mode='inv_vol', mode_params={'vol_col': vcol, 'deoverlap': True})

    # =========================================================================
    # HYPOTHESIS F: Skip-Month ([t-1m, t]) Breakdown Veto & Signal Freshness
    # =========================================================================
    print('\n--- [F] Hypothesis F: Skip-Month ([t-1m, t]) Breakdown Veto & Signal Freshness ---')
    for th in (-0.05, -0.10, -0.15, -0.20):
        vf_1m = lambda r, th=th: pd.notna(r['ret_1m']) and (float(r['ret_1m']) < th)
        qs_f1 = {'type': 'veto', 'base_col': 'sharpe_mom_12_1', 'pool_n': 5, 'veto_fn': vf_1m}
        ts_f1 = {'type': 'veto', 'base_col': 'mom_12_1', 'pool_n': 3, 'veto_fn': vf_1m}
        run_and_record(f'F1. Skip-Month Crash Veto: Drop Winner If ret_1m < {int(th*100)}% (Both Sleeves)',
                       'F. Skip-Month & Entry Trend Veto', qs_f1, ts_f1)

    # Sleeve attribution for F1 (-10% and -15%)
    for th in (-0.10, -0.15):
        vf_1m = lambda r, th=th: pd.notna(r['ret_1m']) and (float(r['ret_1m']) < th)
        qs_f1 = {'type': 'veto', 'base_col': 'sharpe_mom_12_1', 'pool_n': 5, 'veto_fn': vf_1m}
        ts_f1 = {'type': 'veto', 'base_col': 'mom_12_1', 'pool_n': 3, 'veto_fn': vf_1m}
        run_and_record(f'F1s. Skip-Month Veto ret_1m < {int(th*100)}% on QQQ Only (Tech Control)',
                       'F. Skip-Month & Entry Trend Veto', qs_f1, ctrl_t_spec)
        run_and_record(f'F1s. Skip-Month Veto ret_1m < {int(th*100)}% on Tech Only (QQQ Control)',
                       'F. Skip-Month & Entry Trend Veto', ctrl_q_spec, ts_f1)

    # F2. Formation-Date SMA Breakdown Veto (Close[t] < SMA50 / SMA100 / SMA200)
    for scol, sname in [('dist_sma50_t', 'SMA50'), ('dist_sma100_t', 'SMA100'), ('dist_sma200_t', 'SMA200')]:
        vf_sma = lambda r, sc=scol: pd.notna(r[sc]) and (float(r[sc]) < 0.0)
        qs_f2 = {'type': 'veto', 'base_col': 'sharpe_mom_12_1', 'pool_n': 5, 'veto_fn': vf_sma}
        ts_f2 = {'type': 'veto', 'base_col': 'mom_12_1', 'pool_n': 3, 'veto_fn': vf_sma}
        run_and_record(f'F2. Formation-Date Entry Trend Veto: Drop If Close[t] < {sname} (Both Sleeves)',
                       'F. Skip-Month & Entry Trend Veto', qs_f2, ts_f2)
        run_and_record(f'F2s. Entry Trend Veto Close[t] < {sname} on QQQ Only (Tech Control)',
                       'F. Skip-Month & Entry Trend Veto', qs_f2, ctrl_t_spec)
        run_and_record(f'F2s. Entry Trend Veto Close[t] < {sname} on Tech Only (QQQ Control)',
                       'F. Skip-Month & Entry Trend Veto', ctrl_q_spec, ts_f2)

    # F3. Formation-Date 21-Day Peak Drawdown Veto
    for dd_th in (-0.12, -0.15, -0.20):
        vf_dd = lambda r, th=dd_th: pd.notna(r['dd_peak_21d_t']) and (float(r['dd_peak_21d_t']) < th)
        qs_f3 = {'type': 'veto', 'base_col': 'sharpe_mom_12_1', 'pool_n': 5, 'veto_fn': vf_dd}
        ts_f3 = {'type': 'veto', 'base_col': 'mom_12_1', 'pool_n': 3, 'veto_fn': vf_dd}
        run_and_record(f'F3. 21-Day Peak Drawdown Veto: Drop If DD_21d < {int(dd_th*100)}% at Formation',
                       'F. Skip-Month & Entry Trend Veto', qs_f3, ts_f3)

    # F4. Shorter Microstructure Skip Horizon (12-1w [Skip 5 Trading Days] and 12-0 [Skip 0 Days])
    qs_12_1w = {'type': 'score', 'base_col': 'sharpe_mom_12_1w', 'score_col': 'sharpe_mom_12_1w'}
    ts_12_1w = {'type': 'score', 'base_col': 'mom_12_1w', 'score_col': 'mom_12_1w'}
    run_and_record('F4a. 1-Week Skip Momentum (12-1w: Skip 5 Trading Days Instead of 21) [Both]',
                   'F. Signal Freshness (Skip Horizon)', qs_12_1w, ts_12_1w)
    run_and_record('F4b. 1-Week Skip Momentum (12-1w) on QQQ Only + Tech 12-1m Control',
                   'F. Signal Freshness (Skip Horizon)', qs_12_1w, ctrl_t_spec)
    run_and_record('F4c. 1-Week Skip Momentum (12-1w) on Tech Only + QQQ 12-1m Control',
                   'F. Signal Freshness (Skip Horizon)', ctrl_q_spec, ts_12_1w)

    qs_12_0 = {'type': 'score', 'base_col': 'sharpe_mom_12_0', 'score_col': 'sharpe_mom_12_0'}
    ts_12_0 = {'type': 'score', 'base_col': 'mom_12_0', 'score_col': 'mom_12_0'}
    run_and_record('F4d. Zero-Skip Momentum (12-0: Include Most Recent Month [t-1m, t]) [Both]',
                   'F. Signal Freshness (Skip Horizon)', qs_12_0, ts_12_0)

    # =========================================================================
    # HYPOTHESIS G: Rank-Boundary Hysteresis / Buy-Hold Buffer Rules
    # =========================================================================
    print('\n--- [G] Hypothesis G: Rank-Boundary Hysteresis / Buy-Hold Buffer Rules ---')
    for qk in (3, 4, 5, 6):
        run_and_record(f'G1. QQQ Buffer Only: Buy Top-2, Hold While Top-{qk} (Tech Hard Top-1)',
                       'G. Buy-Hold Buffer & Horizon', ctrl_q_spec, ctrl_t_spec,
                       mode='buffer', mode_params={'q_keep': qk, 't_keep': 1})
    for tk in (2, 3, 4):
        run_and_record(f'G2. Tech Buffer Only: Buy Top-1, Hold While Top-{tk} (QQQ Hard Top-2)',
                       'G. Buy-Hold Buffer & Horizon', ctrl_q_spec, ctrl_t_spec,
                       mode='buffer', mode_params={'q_keep': 2, 't_keep': tk})
    for qk in (3, 4, 5):
        for tk in (2, 3):
            run_and_record(f'G3. Dual Buffer Grid: QQQ Hold<=Top-{qk} + Tech Hold<=Top-{tk}',
                           'G. Buy-Hold Buffer & Horizon', ctrl_q_spec, ctrl_t_spec,
                           mode='buffer', mode_params={'q_keep': qk, 't_keep': tk})

    for n_tr in (2, 3):
        run_and_record(f'G4. Overlapping {n_tr}-Month Holding Tranches (Jegadeesh-Titman K={n_tr}m)',
                       'G. Buy-Hold Buffer & Horizon', ctrl_q_spec, ctrl_t_spec,
                       mode='tranche_hold', mode_params={'n_tranches': n_tr})

    # =========================================================================
    # HYPOTHESIS H: Portfolio-Own Realized Volatility Scaling & Crash Protection
    # =========================================================================
    print('\n--- [H] Hypothesis H: Portfolio-Own Realized Volatility Scaling & Crash State ---')
    for win_d in (21, 63):
        for tvol in (0.25, 0.30, 0.35, 0.40):
            run_and_record(f'H1/H2. Barroso Portfolio-Own {win_d}d Vol Target {int(tvol*100)}% (Cash=0%)',
                           'H. Portfolio-Own Vol & Crash Brake', ctrl_q_spec, ctrl_t_spec,
                           mode='port_vol_scale', mode_params={'win_d': win_d, 'target_vol': tvol})

    for trig in (0.35, 0.40, 0.45):
        run_and_record(f'H3. Zero-Cash De-Risking: When Basket 21d Vol > {int(trig*100)}% -> 3-Stock InvVol (100% Invested)',
                       'H. Portfolio-Own Vol & Crash Brake', ctrl_q_spec, ctrl_t_spec,
                       mode='port_vol_derisk_eq', mode_params={'win_d': 21, 'trig_vol': trig})

    for act, alabel in [
        ('scale_50', 'Scale Exposure to 0.50x (Cash=0%)'),
        ('scale_75', 'Scale Exposure to 0.75x (Cash=0%)'),
        ('switch_res_100', 'Switch to Residual Sharpe Winners (100% Invested, 0% Cash)'),
    ]:
        run_and_record(f'H4. Daniel-Moskowitz Bear-Rebound Crash State -> {alabel}',
                       'H. Portfolio-Own Vol & Crash Brake', ctrl_q_spec, ctrl_t_spec,
                       mode='dm_crash_brake', mode_params={'action': act})

    # =========================================================================
    # HYPOTHESIS I: Sleeve-Asymmetric Domain Rules (QQQ vs Tech Physics)
    # =========================================================================
    print('\n--- [I] Hypothesis I: Sleeve-Asymmetric Domain Rules (Cross-Sector QQQ vs Pure-Tech) ---')
    run_and_record('I1a. QQQ Rank #2 Only (50%) + Tech Rank #1 (50%) [Skip Noisy QQQ Rank #1]',
                   'I. Sleeve-Asymmetric Physics', ctrl_q_spec, ctrl_t_spec,
                   mode='qqq_ranks', mode_params={'ranks': [2]})
    run_and_record('I1b. QQQ Rank #2 & #3 (25% Each) + Tech Rank #1 (50%) [Skip QQQ Rank #1]',
                   'I. Sleeve-Asymmetric Physics', ctrl_q_spec, ctrl_t_spec,
                   mode='qqq_ranks', mode_params={'ranks': [2, 3]})
    run_and_record('I1c. QQQ Top-3 (16.7% Each) + Tech Rank #1 (50%)',
                   'I. Sleeve-Asymmetric Physics', ctrl_q_spec, ctrl_t_spec,
                   mode='qqq_ranks', mode_params={'ranks': [1, 2, 3]})

    # I2. QQQ Non-Biotech / Non-Healthcare Filter
    qs_nobiotech = {'type': 'score', 'base_col': 'sharpe_mom_12_1', 'score_col': 'sharpe_mom_12_1',
                    'exclude_set': NDX_BIOTECH_HEALTHCARE}
    run_and_record('I2. QQQ Ex-Biotech/Healthcare Filter (Drop GICS 35 from QQQ; Tech Control)',
                   'I. Sleeve-Asymmetric Physics', qs_nobiotech, ctrl_t_spec)

    # I3. Asymmetric Fundamental / Anti-Jump Rules (Apply Each Filter ONLY Where Structurally Valid)
    qs_ear4 = {'type': 'pool_rerank', 'base_col': 'sharpe_mom_12_1', 'pool_n': 5, 'rerank_col': 'ear_sum4'}
    qs_rb25 = {'type': 'rank_blend', 'base_col': 'sharpe_mom_12_1', 'sec_col': 'fund_mom_comp', 'pool_n': 10, 'w': 0.25}
    veto_jump = lambda r: (r['fip_smooth_12_1'] < 0.0) or (r['mom_12_1'] > 0 and (r['max_ret_5d_12_1'] / max(r['mom_12_1'], 0.01) > 0.65))
    qs_a5 = {'type': 'veto', 'base_col': 'sharpe_mom_12_1', 'pool_n': 5, 'veto_fn': veto_jump}
    ts_a5 = {'type': 'veto', 'base_col': 'mom_12_1', 'pool_n': 3, 'veto_fn': veto_jump}

    run_and_record('I3a. Asymmetric: QQQ Top-5->4Q EAR Top-2 + Tech Control (Pure 12-1 Mom Top-1)',
                   'I. Sleeve-Asymmetric Physics', qs_ear4, ctrl_t_spec)
    run_and_record('I3b. Asymmetric: QQQ RankBlend(0.25 FundMom) + Tech Control (Pure 12-1 Mom Top-1)',
                   'I. Sleeve-Asymmetric Physics', qs_rb25, ctrl_t_spec)
    run_and_record('I3c. Asymmetric: QQQ Top-5->4Q EAR Top-2 + Tech A5 Anti-Jump Veto Top-1',
                   'I. Sleeve-Asymmetric Physics', qs_ear4, ts_a5)
    run_and_record('I3d. Asymmetric: QQQ Control + Tech A5 Anti-Jump Veto Top-1',
                   'I. Sleeve-Asymmetric Physics', ctrl_q_spec, ts_a5)

    df_master = pd.DataFrame(master_rows)
    df_master.to_csv(os.path.join(HERE, '02_all_structural_hypotheses_summary.csv'), index=False)

    # =========================================================================
    # 6. Leave-One-Winner-Out & Outlier Month Stress Test on Representative Variants
    # =========================================================================
    print('\n--- [Check 6] Leave-One-Winner-Out & Best-5-Months Removal Stress Audit ---')
    rep_variants = [
        ('0. Control Core3 [FROZEN]', ctrl_q_spec, ctrl_t_spec, 'standard', {}),
        ('E1a. De-Overlap (QQQ Yields: 3 Distinct Stocks 50/25/25)', ctrl_q_spec, ctrl_t_spec, 'deoverlap_q_yields', {}),
        ('E1c. De-Overlap Equal Weight (3 Distinct Stocks 33.3% Each)', ctrl_q_spec, ctrl_t_spec, 'deoverlap_eq3', {}),
        ('E2. Single-Stock Cap 50% (Same 2 Stocks)', ctrl_q_spec, ctrl_t_spec, 'cap_2stock', {'cap_w': 0.50}),
        ('E4a. Inverse-Vol Weighting (63d Vol)', ctrl_q_spec, ctrl_t_spec, 'inv_vol', {'vol_col': 'vol_63d_t', 'deoverlap': False}),
        ('F1. Skip-Month Crash Veto (ret_1m < -15%)',
         {'type': 'veto', 'base_col': 'sharpe_mom_12_1', 'pool_n': 5, 'veto_fn': lambda r: pd.notna(r['ret_1m']) and float(r['ret_1m']) < -0.15},
         {'type': 'veto', 'base_col': 'mom_12_1', 'pool_n': 3, 'veto_fn': lambda r: pd.notna(r['ret_1m']) and float(r['ret_1m']) < -0.15},
         'standard', {}),
        ('F2. Formation Trend Veto (Close[t] < SMA50)',
         {'type': 'veto', 'base_col': 'sharpe_mom_12_1', 'pool_n': 5, 'veto_fn': lambda r: pd.notna(r['dist_sma50_t']) and float(r['dist_sma50_t']) < 0.0},
         {'type': 'veto', 'base_col': 'mom_12_1', 'pool_n': 3, 'veto_fn': lambda r: pd.notna(r['dist_sma50_t']) and float(r['dist_sma50_t']) < 0.0},
         'standard', {}),
        ('F4a. 1-Week Skip Momentum (12-1w)', qs_12_1w, ts_12_1w, 'standard', {}),
        ('G1. QQQ Buffer Only (Buy Top-2, Hold<=Top-4; Tech Hard Top-1)', ctrl_q_spec, ctrl_t_spec, 'buffer', {'q_keep': 4, 't_keep': 1}),
        ('G1. QQQ Buffer Only (Buy Top-2, Hold<=Top-5; Tech Hard Top-1)', ctrl_q_spec, ctrl_t_spec, 'buffer', {'q_keep': 5, 't_keep': 1}),
        ('G3. Dual Buffer (QQQ Hold<=Top-3, Tech Hold<=Top-2)', ctrl_q_spec, ctrl_t_spec, 'buffer', {'q_keep': 3, 't_keep': 2}),
        ('G4. Overlapping 2-Month Tranches (K=2m)', ctrl_q_spec, ctrl_t_spec, 'tranche_hold', {'n_tranches': 2}),
        ('H1. Barroso Portfolio-Own 21d Vol Target 35%', ctrl_q_spec, ctrl_t_spec, 'port_vol_scale', {'win_d': 21, 'target_vol': 0.35}),
        ('H1. Barroso Portfolio-Own 21d Vol Target 40%', ctrl_q_spec, ctrl_t_spec, 'port_vol_scale', {'win_d': 21, 'target_vol': 0.40}),
        ('H4. Daniel-Moskowitz Crash State -> Switch ResMom', ctrl_q_spec, ctrl_t_spec, 'dm_crash_brake', {'action': 'switch_res_100'}),
        ('I2. QQQ Ex-Biotech/Healthcare + Tech Control', qs_nobiotech, ctrl_t_spec, 'standard', {}),
        ('I3a. Asymmetric: QQQ 4Q-EAR + Tech Control', qs_ear4, ctrl_t_spec, 'standard', {}),
        ('I3c. Asymmetric: QQQ 4Q-EAR + Tech A5 Anti-Jump Veto', qs_ear4, ts_a5, 'standard', {}),
    ]

    super_winners = ['NVDA', 'SNDK', 'PLTR', 'TSLA', 'MU', 'WDC', 'AMD']
    loo_rows = []
    for label, qs, ts, md, mp in rep_variants:
        L_b = simulate_core3_flexible(df_qqq, df_tech, qs, ts, mode=md, mode_params=mp, r_qqq_daily=r_qqq_daily)
        r_b = L_b['net']
        cagr_full = float((np.prod(1.0 + r_b)) ** (12.0 / len(r_b)) - 1.0)
        r_no5 = r_b.copy()
        r_no5.loc[r_no5.nlargest(5).index] = 0.0
        cagr_no5 = float((np.prod(1.0 + r_no5)) ** (12.0 / len(r_no5)) - 1.0)
        row_l = {'Strategy': label, 'Full_CAGR': cagr_full, 'Drop_Best_5_Months_CAGR': cagr_no5}
        for sw in super_winners:
            L_sw = simulate_core3_flexible(df_qqq, df_tech, qs, ts, mode=md, mode_params=mp,
                                           exclude_tickers=[sw], r_qqq_daily=r_qqq_daily)
            row_l[f'Ban_{sw}_CAGR'] = float((np.prod(1.0 + L_sw['net'])) ** (12.0 / len(L_sw)) - 1.0)
        L_3 = simulate_core3_flexible(df_qqq, df_tech, qs, ts, mode=md, mode_params=mp,
                                      exclude_tickers=['NVDA', 'SNDK', 'PLTR'], r_qqq_daily=r_qqq_daily)
        row_l['Ban_NVDA_SNDK_PLTR_CAGR'] = float((np.prod(1.0 + L_3['net'])) ** (12.0 / len(L_3)) - 1.0)
        loo_rows.append(row_l)

    df_loo = pd.DataFrame(loo_rows)
    df_loo.to_csv(os.path.join(HERE, '03_leave_one_winner_out.csv'), index=False)

    # =========================================================================
    # 7. Second-Vendor (Tiingo-First) End-to-End Replication
    # =========================================================================
    print('\n--- [Check 7] Second-Vendor (Tiingo-First) End-to-End Replication ---')
    vend_rows = []
    for label, qs, ts, md, mp in rep_variants:
        L_p = simulate_core3_flexible(df_qqq, df_tech, qs, ts, mode=md, mode_params=mp, r_qqq_daily=r_qqq_daily)
        L_t = simulate_core3_flexible(df_qqq_t, df_tech_t, qs, ts, mode=md, mode_params=mp, r_qqq_daily=r_qqq_daily)
        sp = summarize_ledger(label, '', L_p, rf_monthly)
        st = summarize_ledger(label, '', L_t, rf_monthly)
        corr_pt = float(L_p['net'].corr(L_t['net']))
        vend_rows.append({
            'Strategy': label,
            'Primary_CAGR': sp['CAGR_09_26'],
            'Tiingo_First_CAGR': st['CAGR_09_26'],
            'CAGR_Diff_bp': (st['CAGR_09_26'] - sp['CAGR_09_26']) * 1e4,
            'Primary_Sharpe': sp['Sharpe_m'],
            'Tiingo_First_Sharpe': st['Sharpe_m'],
            'Primary_Monthly_MaxDD': sp['Monthly_MaxDD'],
            'Tiingo_First_Monthly_MaxDD': st['Monthly_MaxDD'],
            'Monthly_Return_Corr': corr_pt,
        })
        print(f"  {label:<52} | Primary={sp['CAGR_09_26']*100:6.2f}% vs Tiingo={st['CAGR_09_26']*100:6.2f}% (corr={corr_pt:.4f})")

    df_vend = pd.DataFrame(vend_rows)
    df_vend.to_csv(os.path.join(HERE, '04_second_vendor_replication.csv'), index=False)

    # =========================================================================
    # 8. Cumulative Multiple-Testing Deflated Sharpe Ratio (DSR) Audit
    # =========================================================================
    print('\n--- [Check 8] Cumulative Multiple-Testing Deflated Sharpe Ratio (DSR) ---')
    repo_trials_df = pd.read_csv(os.path.join(QQQ_DIR, 'm_repo_trials.csv'))
    n_prev = 714  # 481 repo + 39 A/B/C + 59 Core3 audit + 65 tech brakes + 70 selection A/B/C/D
    n_this = len(all_series) - 1
    n_total = n_prev + n_this

    new_srs = [s.mean() / s.std(ddof=1) for s in all_series.values() if s.std(ddof=1) > 0]
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
    for label, qs, ts, md, mp in rep_variants:
        L_p = simulate_core3_flexible(df_qqq, df_tech, qs, ts, mode=md, mode_params=mp, r_qqq_daily=r_qqq_daily)
        rm = L_p['net'].dropna().values
        dsr_cum, sr_ann, sr0_ann = dsr_calc(rm, n_total, sr_var)
        dsr_this, _, _ = dsr_calc(rm, n_this, sr_var)
        diff = (L_p['net'] - r_ctrl).dropna().values
        ir_ann = float(diff.mean() / np.std(diff, ddof=1) * np.sqrt(12.0)) if np.std(diff, ddof=1) > 1e-7 else 0.0
        dsr_rows.append({
            'Strategy': label,
            'N_Cumulative_Trials': n_total,
            'N_This_Round_Trials': n_this,
            'Excess_Sharpe_Ann': sr_ann,
            'Null_Max_SR0_Cumulative': sr0_ann,
            'DSR_Cumulative_All_Trials': dsr_cum,
            'DSR_This_Round_Only': dsr_this,
            'Active_IR_vs_Control': ir_ann,
        })
    df_dsr = pd.DataFrame(dsr_rows)
    df_dsr.to_csv(os.path.join(HERE, '05_multiple_testing_dsr.csv'), index=False)
    print(f'=== COMPLETED ALL {n_this} STRUCTURAL & ACADEMIC TESTS (GRAND TOTAL TRIALS = {n_total}) ===')


if __name__ == '__main__':
    main()
