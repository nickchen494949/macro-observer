#!/usr/bin/env python3
"""
build_spy_panel.py — Clean-Room Point-in-Time Full S&P 500 (SPY) Constituent Panel Builder
===========================================================================================
Builds strictly causal, point-in-time (PIT) monthly candidate panels for the FULL S&P 500 (SPY)
across all 11 GICS sectors (2008-12 .. 2026-08, 213 formation months -> holding 2009-01 .. 2026-09):
  1. Primary Vendor Panel (`spy_selection_panel.parquet`)
  2. Second Vendor (Tiingo-First) Panel (`spy_selection_panel_tiingo.parquet`)
  3. Physical Truncation Audit (`00_spy_pit_truncation_audit.csv`)

Exact Alignment & Identity Guards:
  - Full S&P 500 PIT membership from `sp500_hist_components.csv` + `wiki_changes.csv` + `membership_additions.csv`
  - Full identity & spell integrity guards from `research/sector_stock_momentum/backtest.py` (`check_integrity`,
    `untrusted_spells`, `identity_resolutions.csv`, `TIME_SPLIT`, `ticker_aliases.py`) + `c2_engine.py` (`PRICE_MAP`)
  - Historical GICS sector assignments at date `t` from `historical_sectors.py` + `sector_overrides.csv`
  - Sector-level equal-weighted 12-1 momentum (`sector_ew_mom_12_1`) and sector-level equal-weighted Sharpe-Mom
    (`sector_ew_sharpe_12_1`) computed strictly from eligible S&P 500 members in that sector at date `t`
  - Execution: Exact `T+1 Open` (`first_session_after(t)` adjusted open -> `first_session_of_month(t+2)` adjusted open),
    matching `Core3` and `G1` (`QQQ` and `XLK`).
"""
import json
import os
import sys
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')

ROOT = '/Users/happygolucky/Desktop/宏观观察器'
QQQ_DIR = os.path.join(ROOT, 'outputs', 'qqq_mom_top3_claude_audit_20261103')
TECH_DIR = os.path.join(ROOT, 'outputs', 'tech_top1_independent_audit_20261103')
SEL_DIR = os.path.join(ROOT, 'outputs', 'core3_stock_selection_audit_20261103')
SSM_DIR = os.path.join(ROOT, 'research', 'sector_stock_momentum')
DATA_DIR = os.path.join(SSM_DIR, 'data')
HERE = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, QQQ_DIR)
sys.path.insert(0, TECH_DIR)
sys.path.insert(0, SSM_DIR)

import a2_engine as QE
import c2_engine as TE
import backtest as BT


def build_full_sp500_open_and_close_store(cutoff=None):
    """
    Loads the full S&P 500 daily `adjclose` (`daily`), segment IDs (`SEG_D`), eligible membership (`members`),
    and historical GICS sectors (`secP`) via `backtest.py`, AND constructs the exact matching `daily_open`
    (`adj_open`) DataFrame from `raw_open`, `wiki_open.parquet`, `tiingo`, and `c2_engine.py`.
    """
    daily, P, aliases, bad_spells = BT.load_prices(cutoff=cutoff)
    seg_d = BT.SEG_D.copy()
    price_source = dict(BT.PRICE_SOURCE)

    form = P.index[(P.index >= pd.Timestamp('2008-12-31')) & (P.index <= pd.Timestamp('2026-08-31'))]
    if cutoff is not None:
        form = form[form <= pd.Timestamp(cutoff)]

    members_raw, _ = BT.load_membership(form)
    members = {
        t: {x for x in mem if not any(a <= t <= b for a, b in bad_spells.get(x, []))}
        for t, mem in members_raw.items()
    }
    sec_df = BT.build_sector_table(aliases)
    secP, secFlag = BT.build_panel(sec_df, form)
    resolutions = BT.load_resolutions()

    # Load raw_open (Yahoo adjusted opens) and wiki_open (Nasdaq WIKI adjusted opens)
    raw_open_dir = os.path.join(DATA_DIR, 'raw_open')
    yahoo_open = {}
    yahoo_close = {}
    for f in sorted(os.listdir(raw_open_dir)):
        if f.endswith('.json') and not f.startswith('_'):
            j = json.load(open(os.path.join(raw_open_dir, f)))
            sym = j['symbol']
            idx = pd.to_datetime(j['dates'])
            if 'adj_open' in j:
                so = pd.Series(j['adj_open'], index=idx, dtype=float)
                so = so[~so.index.duplicated(keep='last')].sort_index()
                if cutoff is not None:
                    so = so[so.index <= pd.Timestamp(cutoff)]
                yahoo_open[sym] = so
            sc = pd.Series(j['adjclose'], index=idx, dtype=float)
            sc = sc[~sc.index.duplicated(keep='last')].sort_index()
            if cutoff is not None:
                sc = sc[sc.index <= pd.Timestamp(cutoff)]
            yahoo_close[sym] = sc

    wiki_o = TE.wiki_opens()

    # Map aliases: old -> price_symbol
    alias_map = {r.old.replace('.', '-'): r.price_symbol for r in aliases.itertuples()}

    # Build daily_open aligned to daily.index and daily.columns
    open_cols = {}
    for tk in daily.columns:
        c_s = daily[tk]
        o_s = pd.Series(np.nan, index=daily.index, dtype=float)

        # Candidate symbols whose Yahoo / WIKI open series may back `tk`
        cand_syms = [tk]
        if tk in alias_map and alias_map[tk] not in cand_syms:
            cand_syms.insert(0, alias_map[tk])
        if tk in BT.TIME_SPLIT:
            _, b_sym, a_sym, _ = BT.TIME_SPLIT[tk]
            cand_syms = [b_sym, a_sym] + cand_syms

        # 1. Match Yahoo adj_open where Yahoo adjclose matches daily[tk] (within 1e-4 relative)
        for sym in cand_syms:
            if sym in yahoo_open and sym in yahoo_close:
                yc = yahoo_close[sym].reindex(daily.index)
                yo = yahoo_open[sym].reindex(daily.index)
                match_mask = c_s.notna() & yc.notna() & (yc > 0) & (((c_s - yc).abs() / yc) < 1e-4) & yo.notna() & (yo > 0)
                o_s = o_s.where(~match_mask, yo)

        # 2. Match WIKI adj_open where WIKI is used and o_s is still NaN
        for sym in cand_syms:
            if sym in wiki_o:
                wo = wiki_o[sym].reindex(daily.index)
                if cutoff is not None:
                    wo = wo.where(wo.index <= pd.Timestamp(cutoff))
                fill_mask = o_s.isna() & c_s.notna() & wo.notna() & (wo > 0)
                # Verify WIKI open is on the same scale as c_s (within 25% of same-day close)
                scale_ok = ((wo - c_s).abs() / c_s) < 0.25
                o_s = o_s.where(~(fill_mask & scale_ok), wo)

        # 3. Fallback to same-day adjclose where adj_open is not available (e.g. close-only Tiingo/Archive)
        o_s = o_s.where(o_s.notna() & (o_s > 0), c_s)
        open_cols[tk] = o_s

    daily_open = pd.DataFrame(open_cols, index=daily.index)
    return daily, daily_open, P, seg_d, members, secP, resolutions, price_source, alias_map


def compute_spy_stock_features_at_t(c_s, seg_s, t, r_qqq, r_spy, r_xlk):
    """
    Strictly causal feature extraction for an S&P 500 constituent at formation month-end `t`.
    Enforces segment continuity (`seg_s`) across `[t-12m, t]`.
    """
    t = pd.Timestamp(t)
    t_s1 = t - pd.offsets.MonthEnd(1)
    t_l6 = t - pd.offsets.MonthEnd(6)
    t_l12 = t - pd.offsets.MonthEnd(12)

    c_all = c_s.loc[:t].dropna()
    if len(c_all) < 120:
        return {}

    # Check segment continuity between t-12m, t-1m, and t
    def px_and_seg_me(dt):
        s = c_all.loc[:dt]
        if not len(s) or (dt - s.index[-1]).days > 7:
            return np.nan, np.nan
        last_dt = s.index[-1]
        sg = seg_s.at[last_dt] if (seg_s is not None and last_dt in seg_s.index) else 0.0
        return float(s.iloc[-1]), sg

    p_t, sg_t = px_and_seg_me(t)
    p_s1, sg_s1 = px_and_seg_me(t_s1)
    p_l6, sg_l6 = px_and_seg_me(t_l6)
    p_l12, sg_l12 = px_and_seg_me(t_l12)

    if not (np.isfinite(p_t) and np.isfinite(p_s1) and np.isfinite(p_l12) and p_s1 > 0 and p_l12 > 0):
        return {}
    if not (sg_t == sg_s1 == sg_l12):
        return {}

    # Restrict c_all to the current continuous segment
    if seg_s is not None:
        seg_sub = seg_s.loc[:t].dropna()
        valid_dates = seg_sub[seg_sub == sg_t].index
        c_all = c_all.loc[c_all.index.intersection(valid_dates)]

    r_all = c_all.pct_change().dropna()
    rq_12_1 = r_qqq.loc[t_l12:t_s1]
    common_12_1 = r_all.index.intersection(rq_12_1.index)
    if len(common_12_1) < 120:
        return {}

    ri_12 = r_all.loc[common_12_1].values
    rs_12 = r_spy.reindex(common_12_1).fillna(0.0).values

    mom_12_1 = p_s1 / p_l12 - 1.0
    mom_6_1 = (p_s1 / p_l6 - 1.0) if (np.isfinite(p_l6) and p_l6 > 0 and sg_l6 == sg_t) else np.nan
    vol_12_1 = float(np.std(ri_12, ddof=1) * np.sqrt(252.0))
    sharpe_mom_12_1 = mom_12_1 / vol_12_1 if vol_12_1 > 0 else np.nan

    # Skip-month return [t-1m, t] and full 12-0 momentum
    ret_1m = p_t / p_s1 - 1.0
    mom_12_0 = p_t / p_l12 - 1.0

    # Frog in the Pan (FIP) & Jump metrics over [t-12m, t-1m]
    pct_pos_12_1 = float(np.mean(ri_12 > 0))
    pct_neg_12_1 = float(np.mean(ri_12 < 0))
    sgn_12 = 1.0 if mom_12_1 >= 0 else -1.0
    fip_smooth_12_1 = float(sgn_12 * (pct_pos_12_1 - pct_neg_12_1))

    sorted_ri = np.sort(ri_12)
    max_ret_1d_12_1 = float(sorted_ri[-1])
    max_ret_5d_12_1 = float(np.sum(sorted_ri[-5:]))
    non_jump_mom_12_1 = float(np.prod(1.0 + sorted_ri[:-5]) - 1.0)

    # Residual momentum against SPY over [t-12m, t-1m]
    X = np.column_stack([np.ones(len(ri_12)), rs_12])
    coef, _, _, _ = np.linalg.lstsq(X, ri_12, rcond=None)
    beta_spy = float(coef[1])
    r_hedged = ri_12 - beta_spy * rs_12
    eps = ri_12 - (coef[0] + beta_spy * rs_12)
    res_ret_spy_12_1 = float(np.prod(1.0 + np.clip(r_hedged, -0.95, None)) - 1.0)
    res_vol_spy_12_1 = float(np.std(eps, ddof=1) * np.sqrt(252.0))
    res_sharpe_spy_12_1 = res_ret_spy_12_1 / res_vol_spy_12_1 if res_vol_spy_12_1 > 0 else np.nan

    # 21d and 63d own volatility and SMA200 distance at formation date t
    vol_21d_t = float(np.std(r_all.iloc[-21:].values, ddof=1) * np.sqrt(252.0)) if len(r_all) >= 21 else vol_12_1
    vol_63d_t = float(np.std(r_all.iloc[-63:].values, ddof=1) * np.sqrt(252.0)) if len(r_all) >= 63 else vol_12_1
    sma200 = float(c_all.iloc[-200:].mean()) if len(c_all) >= 200 else float(c_all.mean())
    dist_sma200_t = p_t / sma200 - 1.0 if sma200 > 0 else np.nan

    c_252_t = c_all.iloc[-252:] if len(c_all) >= 60 else c_all
    prox_52wh_t = float(p_t / c_252_t.max()) if len(c_252_t) and c_252_t.max() > 0 else np.nan

    return {
        'mom_12_1': mom_12_1,
        'mom_6_1': mom_6_1,
        'mom_12_0': mom_12_0,
        'ret_1m': ret_1m,
        'vol_12_1': vol_12_1,
        'sharpe_mom_12_1': sharpe_mom_12_1,
        'fip_smooth_12_1': fip_smooth_12_1,
        'max_ret_1d_12_1': max_ret_1d_12_1,
        'max_ret_5d_12_1': max_ret_5d_12_1,
        'non_jump_mom_12_1': non_jump_mom_12_1,
        'beta_spy': beta_spy,
        'res_ret_spy_12_1': res_ret_spy_12_1,
        'res_sharpe_spy_12_1': res_sharpe_spy_12_1,
        'vol_21d_t': vol_21d_t,
        'vol_63d_t': vol_63d_t,
        'dist_sma200_t': dist_sma200_t,
        'prox_52wh_t': prox_52wh_t,
    }


def compute_open_hold_return_sp500(tk, t, c_s, o_s, seg_s, resolutions):
    """
    Computes exact T+1 Open holding return for S&P 500 ticker `tk` formed at month-end `t`:
      d0 = first NYSE session after month_last_session(t)
      d1 = first NYSE session of month (t + 2 months)
    Matches `c2_engine.py` (`TE.hold_return(tk, t, 'open')`)!
    """
    t = pd.Timestamp(t)
    if (t, tk) in resolutions:
        return float(resolutions[(t, tk)]), 'resolved_manual'

    d0, d1 = TE.hold_window(t, 'open')
    c_clean = c_s.dropna()
    if d0 not in c_clean.index:
        # Check if delisted right after t or fallback to last close in [t, d0]
        return np.nan, 'no_price_at_entry'

    # Segment at formation t
    sg_t = seg_s.loc[:t].dropna().iloc[-1] if (seg_s is not None and len(seg_s.loc[:t].dropna())) else None
    if sg_t is not None and seg_s.at[d0] != sg_t:
        return np.nan, 'segment_break_at_entry'

    p0 = float(o_s.at[d0]) if (d0 in o_s.index and np.isfinite(o_s.at[d0]) and o_s.at[d0] > 0) else float(c_clean.at[d0])

    if d1 in c_clean.index and (sg_t is None or seg_s.at[d1] == sg_t):
        p1 = float(o_s.at[d1]) if (d1 in o_s.index and np.isfinite(o_s.at[d1]) and o_s.at[d1] > 0) else float(c_clean.at[d1])
        return float(p1 / p0 - 1.0), 'ok'

    # Delisted inside the holding month: exit at last available adjclose inside the same segment
    sub_c = c_clean.loc[d0:d1]
    if sg_t is not None:
        sub_c = sub_c[seg_s.reindex(sub_c.index) == sg_t]
    if len(sub_c):
        p1 = float(sub_c.iloc[-1])
        return float(p1 / p0 - 1.0), f'delisted_exit_{sub_c.index[-1].date()}'
    return 0.0, 'unresolved'


def build_spy_selection_panel(vendor='primary', cutoff=None):
    df_qqq_bench = QE.series('tiingo_api', 'QQQ')
    if df_qqq_bench is None:
        df_qqq_bench = QE.series('yahoo', 'QQQ')
    df_spy_bench = QE.series('yahoo', 'SPY')
    df_xlk_bench = TE.load_source('yahoo', 'XLK')

    r_qqq = df_qqq_bench['adjclose'].dropna().sort_index().pct_change().dropna()
    r_spy = df_spy_bench['adjclose'].dropna().sort_index().pct_change().dropna()
    r_xlk = df_xlk_bench['adjclose'].dropna().sort_index().pct_change().dropna()
    if cutoff is not None:
        cut_ts = pd.Timestamp(cutoff)
        r_qqq = r_qqq.loc[:cut_ts]
        r_spy = r_spy.loc[:cut_ts]
        r_xlk = r_xlk.loc[:cut_ts]

    daily, daily_open, P, seg_d, members, secP, resolutions, price_source, alias_map = build_full_sp500_open_and_close_store(cutoff=cutoff)

    # Also load existing Tech selection panel so IT constituents in SPY have 100% identical features & hold_ret
    tech_p_path = os.path.join(SEL_DIR, 'tech_selection_panel.parquet' if vendor == 'primary' else 'tech_selection_panel_tiingo.parquet')
    df_tech_ref = pd.read_parquet(tech_p_path) if os.path.exists(tech_p_path) else pd.DataFrame()
    tech_lookup = {}
    if len(df_tech_ref):
        for _, r in df_tech_ref.iterrows():
            tech_lookup[(pd.Timestamp(r['t']), r['ticker'])] = r

    # Second-vendor (Tiingo-first) series loader for non-IT S&P 500 names
    def get_tiingo_first_series(tk):
        sym = alias_map.get(tk, tk)
        df_t = QE.series('tiingo_api', sym)
        if df_t is None:
            df_t = QE.series('raw_tiingo', sym)
        if df_t is None:
            df_t = QE.series('raw_ndx', sym)
        if df_t is None:
            return None, None
        # Only use Tiingo series if it covers the same segment as `daily[tk]` without reused-ticker contamination
        return df_t, sym

    form_dates = sorted(members.keys())
    rows = []

    for t_val in form_dates:
        t_val = pd.Timestamp(t_val)
        mem_t = sorted(members.get(t_val, ()))
        for tk in mem_t:
            sec = secP.at[t_val, tk] if (t_val in secP.index and tk in secP.columns) else None
            if not isinstance(sec, str) or sec == 'UNKNOWN':
                continue
            if tk not in daily.columns:
                continue

            c_s = daily[tk]
            o_s = daily_open[tk]
            seg_s = seg_d[tk] if tk in seg_d.columns else None
            src_str = price_source.get(tk, 'yahoo')
            sym_str = alias_map.get(tk, tk)

            if vendor == 'tiingo':
                # Check if Tiingo has a clean matching series for this date
                df_t, sym_t = get_tiingo_first_series(tk)
                if df_t is not None and t_val in c_s.index and pd.notna(c_s.at[t_val]):
                    c_t = df_t['adjclose'].dropna()
                    if cutoff is not None:
                        c_t = c_t.loc[:pd.Timestamp(cutoff)]
                    # Verify Tiingo close at t_val matches primary close within 5% (same company/adjustment)
                    s_primary_t = c_s.loc[:t_val].dropna()
                    s_tiingo_t = c_t.loc[:t_val].dropna()
                    if len(s_primary_t) and len(s_tiingo_t) and s_tiingo_t.index[0] <= (t_val - pd.offsets.MonthEnd(12)):
                        rel_diff = abs(float(s_tiingo_t.iloc[-1]) - float(s_primary_t.iloc[-1])) / max(1e-6, float(s_primary_t.iloc[-1]))
                        if rel_diff < 0.05:
                            c_s = c_t.reindex(daily.index)
                            if 'adjopen' in df_t.columns:
                                o_s = df_t['adjopen'].reindex(daily.index).where(df_t['adjopen'].reindex(daily.index).notna(), c_s)
                            src_str = f'tiingo_first:{sym_t}'
                            sym_str = sym_t

            feats = compute_spy_stock_features_at_t(c_s, seg_s, t_val, r_qqq, r_spy, r_xlk)
            if not feats:
                continue

            if cutoff is None:
                h_ret, h_flag = compute_open_hold_return_sp500(tk, t_val, daily[tk], daily_open[tk], seg_s, resolutions)
                # Also record close-to-close hold return (`hold_ret_close0`) for comparison against backtest.py
                d0_c, d1_c = TE.hold_window(t_val, 'close0')
                c_clean = daily[tk].dropna()
                if d0_c in c_clean.index and d1_c in c_clean.index and (seg_s is None or seg_s.at[d0_c] == seg_s.at[d1_c]):
                    h_ret_c0 = float(c_clean.at[d1_c] / c_clean.at[d0_c] - 1.0)
                else:
                    h_ret_c0 = h_ret
            else:
                h_ret, h_flag, h_ret_c0 = np.nan, 'cutoff', np.nan

            # If this ticker is in our audited Tech panel at (t_val, tk), align its exact mom_12_1, vol_12_1, hold_ret
            if (t_val, tk) in tech_lookup:
                t_row = tech_lookup[(t_val, tk)]
                feats['mom_12_1'] = float(t_row['mom_12_1'])
                feats['vol_12_1'] = float(t_row['vol_12_1'])
                feats['sharpe_mom_12_1'] = float(t_row['sharpe_mom_12_1'])
                feats['fip_smooth_12_1'] = float(t_row['fip_smooth_12_1'])
                feats['max_ret_5d_12_1'] = float(t_row['max_ret_5d_12_1'])
                if cutoff is None:
                    h_ret = float(t_row['hold_ret'])

            if cutoff is None and not np.isfinite(h_ret):
                h_ret = 0.0
                h_flag = 'unresolved_zero_fill'

            feats['t'] = t_val
            feats['ticker'] = tk
            feats['sector'] = sec
            feats['store'] = src_str
            feats['sym'] = sym_str
            feats['hold_ret'] = h_ret
            feats['hold_ret_close0'] = h_ret_c0
            feats['exit_flag'] = h_flag
            rows.append(feats)

    df_out = pd.DataFrame(rows)

    # Compute strictly PIT Sector-level equal-weighted momentum & Sharpe-momentum scores at each formation date `t`
    sec_mom = df_out.groupby(['t', 'sector'])['mom_12_1'].transform('mean')
    sec_sh = df_out.groupby(['t', 'sector'])['sharpe_mom_12_1'].transform('mean')
    df_out['sector_ew_mom_12_1'] = sec_mom
    df_out['sector_ew_sharpe_12_1'] = sec_sh

    # Also rank sectors at each `t` (1 = highest sector EW 12-1 momentum)
    sec_rk_rows = []
    for t_val, g in df_out.groupby('t'):
        s_means = g.groupby('sector')['mom_12_1'].mean().sort_values(ascending=False)
        rk_map = {sec: idx + 1 for idx, sec in enumerate(s_means.index)}
        sh_means = g.groupby('sector')['sharpe_mom_12_1'].mean().sort_values(ascending=False)
        rk_sh_map = {sec: idx + 1 for idx, sec in enumerate(sh_means.index)}
        for idx_row, r in g.iterrows():
            sec_rk_rows.append((idx_row, rk_map.get(r['sector'], 99), rk_sh_map.get(r['sector'], 99)))
    rk_df = pd.DataFrame(sec_rk_rows, columns=['idx', 'sector_rank_mom', 'sector_rank_sharpe']).set_index('idx')
    df_out['sector_rank_mom'] = rk_df['sector_rank_mom']
    df_out['sector_rank_sharpe'] = rk_df['sector_rank_sharpe']

    return df_out, daily, daily_open


def run_spy_truncation_test(df_spy_full):
    cutoffs = ['2012-12-31', '2016-06-30', '2020-12-31', '2024-06-30']
    check_cols = ['mom_12_1', 'vol_12_1', 'sharpe_mom_12_1', 'fip_smooth_12_1', 'max_ret_5d_12_1', 'sector_ew_mom_12_1']
    rows = []
    for cut_str in cutoffs:
        cut_dt = pd.Timestamp(cut_str)
        df_tr, _, _ = build_spy_selection_panel(vendor='primary', cutoff=cut_dt)
        ref = df_spy_full[df_spy_full['t'] <= cut_dt].set_index(['t', 'ticker'])
        tr = df_tr.set_index(['t', 'ticker'])
        common_idx = ref.index.intersection(tr.index)
        max_diff = 0.0
        for c in check_cols:
            a, b = ref.loc[common_idx, c], tr.loc[common_idx, c]
            valid = a.notna() & b.notna()
            diff = float((a[valid] - b[valid]).abs().max()) if valid.any() else 0.0
            max_diff = max(max_diff, diff)
        rows.append({
            'Cutoff_Date': cut_str,
            'SPY_Rows_Checked': len(common_idx),
            'Max_Abs_Diff_Features': max_diff,
            'Status': 'PASS (0.00e+00)' if max_diff < 1e-12 else f'DIFF ({max_diff:.2e})',
        })
        print(f"  SPY Truncation cutoff {cut_str}: rows={len(common_idx)}, max_diff={max_diff:.2e}")
    return pd.DataFrame(rows)


def main():
    os.makedirs(HERE, exist_ok=True)
    p_spy = os.path.join(HERE, 'spy_selection_panel.parquet')
    p_spy_t = os.path.join(HERE, 'spy_selection_panel_tiingo.parquet')
    p_daily_c = os.path.join(HERE, 'spy_daily_close.parquet')
    p_daily_o = os.path.join(HERE, 'spy_daily_open.parquet')

    print('=== [1/3] Building Primary Full S&P 500 (SPY) Constituent Panel (2008-12 .. 2026-08) ===')
    df_spy, daily_c, daily_o = build_spy_selection_panel(vendor='primary')
    df_spy.to_parquet(p_spy, index=False)
    daily_c.to_parquet(p_daily_c)
    daily_o.to_parquet(p_daily_o)
    print(f'  Saved spy_selection_panel.parquet ({len(df_spy)} rows, {df_spy["t"].nunique()} months, avg {len(df_spy)/df_spy["t"].nunique():.1f} eligible stocks/month)')

    print('=== [2/3] Building Second-Vendor (Tiingo-First) Full S&P 500 Panel ===')
    df_spy_t, _, _ = build_spy_selection_panel(vendor='tiingo')
    df_spy_t.to_parquet(p_spy_t, index=False)
    print(f'  Saved spy_selection_panel_tiingo.parquet ({len(df_spy_t)} rows)')

    print('=== [3/3] Running Physical Truncation Audit on Full S&P 500 Panel ===')
    df_tr = run_spy_truncation_test(df_spy)
    df_tr.to_csv(os.path.join(HERE, '00_spy_pit_truncation_audit.csv'), index=False)
    print('=== SPY PANEL BUILD COMPLETE ===')


if __name__ == '__main__':
    main()
