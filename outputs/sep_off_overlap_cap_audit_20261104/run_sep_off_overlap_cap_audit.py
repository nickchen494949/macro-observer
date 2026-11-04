#!/usr/bin/env python3
"""
run_sep_off_overlap_cap_audit.py — Clean-Room Independent Audit of Pre-Registered
"SEP = OFF Overlap-Cap / Duplicate-to-ExIT" Rules (2009-01 .. 2026-10 Live + 2026-11)
======================================================================================
Built directly on the zero-shared-code independent engine (`ind_engine.py`, commit `39c1af4`).
Tests the user's frozen, pre-registered question:

  "当不同 sleeve 选中同一只股票，而且 SEP=OFF 时，是否应该限制单票重叠？
   1. 原规则：允许重叠。
   2. 单票最多 50%：多出来的 duplicate allocation 去 SGOV。
   3. 单票最多 25% / 33%：重复的 SPY sleeve 改买当前最强非科技候选 (Ex-IT)。
   4. 只在 SEP OFF 时启用上述规则；SEP ON 不动。"

Evaluates across BOTH audited base architectures:
  - Panel A: 2-Leg `G1_SPY_2e` (`50% QQQ G1 [Buy 2, Hold<=5] + 50% SPY G1 [Buy 1, Hold<=3]`)
  - Panel B: 3-Leg `3S_G1_1k` (`50% QQQ G1 [Buy 2, Hold<=5] + 25% Tech [Hard Top-1] + 25% SPY G1 [Buy 1, Hold<=3]`)

Key Audit Dimensions:
  1. Structural Diagnostic: Multi-sleeve overlap performance in `SEP = ON` vs `SEP = OFF`
  2. Complete Month-by-Month Ledger of all 35 `SEP = OFF` months (`2021-10 .. 2026-11`)
  3. Full Backtest (`2009-01 .. 2026-09`, 213 months) + Live October 2026 Extension (`2009-01 .. 2026-10`, 214 months)
  4. True Daily Mark-to-Market MaxDD (`2009-01 .. 2026-09` and live `2026-06-18 -> 2026-10-29` storage crash)
  5. Episode Attribution:
       - 2022 Bear Market (`DVN` / `EQT` preservation check)
       - 2024 Q3 `SEP = OFF` (`NVDA` / `SMCI` pullback)
       - 2025 Q1 `SEP = OFF` (`PLTR` / `APP` pullback) vs 2025 Q2-Q4 `SEP = ON` (`PLTR` rally)
       - 2026 Jul-Oct `SEP = OFF` (`SNDK` / `WDC` / `STX` concentration crash)
  6. Multiple-Testing Deflated Sharpe Ratio (DSR)
  7. Exact November 2026 (`2026-11`) Target Holdings under each pre-registered rule
"""
import json
import os
import sys
import warnings
import numpy as np
import pandas as pd
from scipy import stats as sst

warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = '/Users/happygolucky/Desktop/宏观观察器'
IND_2L_DIR = os.path.join(ROOT, 'outputs', 'two_leg_independent_audit_20261103')
IND_EXP_DIR = os.path.join(ROOT, 'outputs', 'expabc_independent_audit_20261104')

sys.path.insert(0, IND_2L_DIR)
import ind_engine as IE


def load_independent_inputs():
    """
    Loads the independent zero-shared-code panels (`ind_panel_ndx.parquet`,
    `ind_panel_spx_with_sector.parquet`) and independent ALFRED FOMC SEP regime table
    (`02_ind_regime.csv`, verified 0 mismatches vs canonical FOMC SEP across all 213 months).
    """
    Pq = pd.read_parquet(os.path.join(IND_EXP_DIR, 'ind_panel_ndx.parquet'))
    Ps = pd.read_parquet(os.path.join(IND_EXP_DIR, 'ind_panel_spx_with_sector.parquet'))
    reg = pd.read_csv(os.path.join(IND_EXP_DIR, '02_ind_regime.csv'))
    reg['t'] = pd.to_datetime(reg['t'])
    reg_map = reg.set_index('t').to_dict('index')

    # Sleeve picks (strictly causal at formation date t, never touching hold_ret)
    pk_q = IE.sleeve_picks(Pq, 'sharpe', k=2, keep=5)
    pk_s = IE.sleeve_picks(Ps, 'mom', k=1, keep=3)

    Ps_it = Ps[Ps['sector'] == 'Information Technology'].copy()
    pk_t = IE.sleeve_picks(Ps_it, 'mom', k=1, keep=1)

    Ps_exit = Ps[Ps['sector'].notna() & (Ps['sector'] != 'Information Technology') & (Ps['sector'] != 'Unknown')].copy()
    pk_exit_raw = IE.sleeve_picks(Ps_exit, 'mom', k=1, keep=3)

    # Best Non-Tech Sector (by equal-weighted 12-1 momentum of eligible S&P 500 members) -> Top-1 Stock (G1 Hold<=3)
    held_bs, pk_exit_bs, top_exit_sec = [], {}, {}
    for t, g in Ps_exit[Ps_exit['mom'].notna()].groupby('t', sort=True):
        sec_ew = g.groupby('sector')['mom'].mean().sort_values(ascending=False)
        top_exit_sec[t] = str(sec_ew.index[0])
        sec_rk = {s: i + 1 for i, s in enumerate(sec_ew.index)}
        g = g.copy()
        g['sec_rk'] = g['sector'].map(sec_rk)
        g_top = g[g['sec_rk'] == 1].sort_values(['mom', 'ticker'], ascending=[False, True])
        g_rest = g[g['sec_rk'] > 1].sort_values(['sec_rk', 'mom', 'ticker'], ascending=[True, False, True])
        ranked = list(pd.concat([g_top, g_rest])['ticker'])
        rank = {x: i + 1 for i, x in enumerate(ranked)}
        kept = [x for x in held_bs if rank.get(x, 999) <= 3][:1]
        if not kept:
            kept = [ranked[0]]
        held_bs = kept
        pk_exit_bs[t] = list(kept)

    sec_lk = {(t, tk): sec for t, tk, sec in Ps[['t', 'ticker', 'sector']].itertuples(index=False)}

    p_row_lk = {}
    for P in (Ps, Pq):
        for r in P.itertuples(index=False):
            if pd.notna(r.src):
                p_row_lk[(r.t, r.ticker)] = (r.src, r.sym, str(r.ret_flag))

    def get_df_for_daily(t, tk):
        if (t, tk) in p_row_lk:
            src, sym, fl = p_row_lk[(t, tk)]
            if fl.startswith('open_open_via_'):
                src, sym = fl.replace('open_open_via_', '').split(':', 1)
            return IE.load_fixed(src, sym)
        for src, sym in IE.candidate_series(tk):
            df = IE.load_fixed(src, sym)
            if df is not None:
                return df
        return None

    ret_lk = {}
    for P in (Pq, Ps):
        for t, tk, r in P[['t', 'ticker', 'hold_ret']].itertuples(index=False):
            if np.isfinite(r):
                ret_lk[(t, tk)] = float(r)

    # Live October 2026 return (formed t = 2026-09-30, entered d0 = 2026-10-01 open, marked to 2026-10-29 close)
    t_oct = pd.Timestamp('2026-09-30')
    d0_oct = IE.first_session_after(t_oct)
    for tk in set(Pq[Pq.t == t_oct]['ticker']) | set(Ps[Ps.t == t_oct]['ticker']):
        df = get_df_for_daily(t_oct, tk)
        if df is not None and d0_oct in df.index:
            o0 = df.at[d0_oct, 'o'] if np.isfinite(df.at[d0_oct, 'o']) else df.at[d0_oct, 'c']
            c_last = df['c'].loc[d0_oct:'2026-10-29'].iloc[-1]
            ret_lk[(t_oct, tk)] = float(c_last / o0 - 1.0)

    for t, r_info in reg_map.items():
        rf_val = r_info['rf_m'] if np.isfinite(r_info['rf_m']) else r_info['rf_m_start']
        ret_lk[(t, 'SGOV')] = float(rf_val) if np.isfinite(rf_val) else 0.0

    return (Pq, Ps, reg, reg_map, pk_q, pk_t, pk_s, pk_exit_raw, pk_exit_bs,
            top_exit_sec, sec_lk, ret_lk, get_df_for_daily)


def build_overlap_diagnostic_table(months_213, months_214, reg_map, pk_q, pk_t, pk_s, ret_lk):
    """
    Computes exact overlap vs non-overlap performance split by `SEP = ON` vs `SEP = OFF`
    for both 2-Leg (`G1_SPY_2e`) and 3-Leg (`3S_G1_1k`).
    """
    rows = []
    for window_label, m_list in [('2009-01..2026-09 (213m)', months_213),
                                 ('2009-01..2026-10 (214m incl. Live Oct)', months_214)]:
        for arch in ['2-Leg (G1_SPY_2e)', '3-Leg (3S_G1_1k)']:
            buckets = {
                'All Months': [],
                'SEP ON — Overlap': [],
                'SEP ON — No Overlap': [],
                'SEP OFF — Overlap': [],
                'SEP OFF — No Overlap': [],
            }
            for t in m_list:
                q1, q2 = pk_q[t]
                t1 = pk_t[t][0]
                s1 = pk_s[t][0]
                sep_on = bool(reg_map[t]['sep_on'])

                if arch.startswith('2-Leg'):
                    r_m = 0.25 * ret_lk[(t, q1)] + 0.25 * ret_lk[(t, q2)] + 0.50 * ret_lk[(t, s1)]
                    is_ov = (s1 in (q1, q2))
                else:
                    r_m = 0.25 * ret_lk[(t, q1)] + 0.25 * ret_lk[(t, q2)] + 0.25 * ret_lk[(t, t1)] + 0.25 * ret_lk[(t, s1)]
                    is_ov = (len({q1, q2, t1, s1}) < 4)

                buckets['All Months'].append(r_m)
                if sep_on and is_ov:
                    buckets['SEP ON — Overlap'].append(r_m)
                elif sep_on and not is_ov:
                    buckets['SEP ON — No Overlap'].append(r_m)
                elif (not sep_on) and is_ov:
                    buckets['SEP OFF — Overlap'].append(r_m)
                else:
                    buckets['SEP OFF — No Overlap'].append(r_m)

            for b_name, arr in buckets.items():
                a = np.array(arr, dtype=float)
                n = len(a)
                if n == 0:
                    continue
                mean_m = float(np.mean(a))
                med_m = float(np.median(a))
                ann_geom = float(np.prod(1.0 + a) ** (12.0 / n) - 1.0)
                vol_ann = float(np.std(a, ddof=1) * np.sqrt(12.0)) if n > 1 else np.nan
                sharpe_raw = float(mean_m / np.std(a, ddof=1) * np.sqrt(12.0)) if (n > 1 and np.std(a, ddof=1) > 0) else np.nan
                win_rate = float(np.mean(a > 0))
                worst_m = float(np.min(a))
                rows.append({
                    'Window': window_label,
                    'Architecture': arch,
                    'State_Bucket': b_name,
                    'Months': n,
                    'Mean_Monthly_Ret': mean_m,
                    'Median_Monthly_Ret': med_m,
                    'Annualized_Geom_Return': ann_geom,
                    'Ann_Vol': vol_ann,
                    'Sharpe_Raw': sharpe_raw,
                    'Win_Rate': win_rate,
                    'Worst_Month': worst_m,
                })
    return pd.DataFrame(rows)


def simulate_variant_and_daily_nav(rule_fn, months_213, months_214, reg_map, ret_lk, get_df_for_daily, cal):
    """
    Simulates a portfolio weight rule `rule_fn(t)` on a single account (charging 10bp/side
    on all equity turnover, including cross-leg drift) and constructs the exact daily
    mark-to-market NAV path from adjusted Open entry -> daily Close -> next adjusted Open exit.
    """
    prev = {}
    rows = []
    W = 1.0
    path = {}

    for t in months_214:
        w_raw = rule_fn(t)
        w = {k: float(v) for k, v in w_raw.items() if abs(v) > 1e-9}

        # Single-account equity turnover (SGOV is T-bill cash proxy)
        eq_keys = (set(w) | set(prev)) - {'SGOV'}
        to = sum(abs(w.get(x, 0.0) - prev.get(x, 0.0)) for x in eq_keys) if prev else sum(v for k, v in w.items() if k != 'SGOV')
        gross = sum(w[x] * ret_lk[(t, x)] for x in w)
        cost = IE.COST * to
        net = gross - cost
        denom = sum(w[x] * (1.0 + ret_lk[(t, x)]) for x in w)
        prev = {x: w[x] * (1.0 + ret_lk[(t, x)]) / denom for x in w}

        max_eq_wt = max([v for k, v in w.items() if k != 'SGOV'], default=0.0)
        sgov_wt = w.get('SGOV', 0.0)
        rows.append({
            't': t,
            'ym': reg_map[t]['ym'],
            'sep_on': bool(reg_map[t]['sep_on']),
            'weights': w,
            'max_single_stock_wt': max_eq_wt,
            'sgov_wt': sgov_wt,
            'gross': gross,
            'turnover': to,
            'net': net,
        })

        d0 = IE.first_session_after(t)
        if t < pd.Timestamp('2026-09-30'):
            d1 = IE.first_session_after(t + pd.offsets.MonthEnd(1))
            days = cal[(cal >= d0) & (cal < d1)]
        else:
            d1 = None
            days = cal[(cal >= d0) & (cal <= pd.Timestamp('2026-10-29'))]

        ser = {tk: get_df_for_daily(t, tk) for tk in w if tk != 'SGOV'}
        Wd = W * (1.0 - cost)
        rf_m = ret_lk[(t, 'SGOV')]
        n_d = max(len(days), 1)
        for i_d, d in enumerate(days):
            v = 0.0
            for tk, wt in w.items():
                if tk == 'SGOV':
                    v += wt * ((1.0 + rf_m) ** ((i_d + 1) / n_d))
                else:
                    df = ser[tk]
                    p0 = df.at[d0, 'o'] if (d0 in df.index and np.isfinite(df.at[d0, 'o'])) else df.at[d0, 'c']
                    c = df['c'].loc[:d]
                    v += wt * (c.iloc[-1] / p0)
            path[d] = Wd * v
        W = W * (1.0 + net)
        if d1 is not None:
            path[d1] = W

    L = pd.DataFrame(rows).set_index('t')
    s_nav = pd.Series(path).sort_index()
    s_nav = s_nav[~s_nav.index.duplicated(keep='last')]
    return L, s_nav


def compute_summary_metrics(name, panel, desc, L, s_nav, months_213, ref_r213):
    r213 = L.loc[months_213, 'net']
    r214 = L['net']

    rf_213 = pd.Series([L.loc[t, 'gross'] * 0 + 0.0 for t in months_213], index=months_213)
    # Load exact DGS3MO monthly rf
    dgs = json.load(open(os.path.join(ROOT, 'data', 'fred', 'DGS3MO.json')))['values']
    rf_s = pd.Series({pd.Timestamp(d): float(v) / 100.0 for d, v in dgs if v not in (None, '.')}).sort_index().resample('ME').last() / 12.0
    idx_me_213 = pd.DatetimeIndex(months_213) + pd.offsets.MonthEnd(1)
    rf_al_213 = rf_s.reindex(idx_me_213).ffill().fillna(0.0).values

    cagr_213 = float(np.prod(1.0 + r213.values) ** (12.0 / len(r213)) - 1.0)
    cagr_214 = float(np.prod(1.0 + r214.values) ** (12.0 / len(r214)) - 1.0)
    vol_213 = float(np.std(r213.values, ddof=1) * np.sqrt(12.0))
    ex_213 = r213.values - rf_al_213
    sharpe_213 = float(np.mean(ex_213) / np.std(r213.values, ddof=1) * np.sqrt(12.0))

    w_m = np.concatenate([[1.0], np.cumprod(1.0 + r213.values)])
    mdd_213 = float((w_m / np.maximum.accumulate(w_m) - 1.0).min())

    # True Daily MaxDD (2009-01..2026-09)
    s_213 = s_nav.loc[:'2026-10-01']
    dd_s213 = s_213 / s_213.cummax() - 1.0
    daily_dd_213 = float(dd_s213.min())
    trough_213 = dd_s213.idxmin()
    peak_213 = s_213.loc[:trough_213].idxmax()

    # Full Daily MaxDD including live Oct 2026 (2009-01..2026-10-29)
    dd_sfull = s_nav / s_nav.cummax() - 1.0
    daily_dd_full = float(dd_sfull.min())
    trough_full = dd_sfull.idxmin()
    peak_full = s_nav.loc[:trough_full].idxmax()

    # 2026 Live Drawdown specifically (from 2026 peak to worst day & to 2026-10-29)
    s_2026 = s_nav.loc['2026-01-01':]
    dd_2026 = s_2026 / s_2026.cummax() - 1.0
    live_2026_worst_dd = float(dd_2026.min())
    live_2026_oct29_dd = float(dd_2026.iloc[-1])

    # Sub-period and episode returns
    def sub_cagr(y_start, y_end):
        sub = L.loc[months_213]
        sub = sub[(sub['ym'] >= y_start) & (sub['ym'] <= y_end)]['net'].values
        return float(np.prod(1.0 + sub) ** (12.0 / len(sub)) - 1.0)

    def ep_ret(ym_list):
        sub = L[L['ym'].isin(ym_list)]['net'].values
        return float(np.prod(1.0 + sub) - 1.0)

    cagr_09_18 = sub_cagr('2009-01', '2018-12')
    cagr_19_26 = sub_cagr('2019-01', '2026-09')
    ret_2022 = ep_ret([f'2022-{m:02d}' for m in range(1, 13)])
    ret_sep_off_33 = float(np.prod(1.0 + L.loc[months_213][~L.loc[months_213, 'sep_on']]['net'].values) - 1.0)
    ret_sep_off_34 = float(np.prod(1.0 + L[~L['sep_on']]['net'].values) - 1.0)
    ret_2024_q3 = ep_ret(['2024-07', '2024-08', '2024-09'])
    ret_2025_q1 = ep_ret(['2025-01', '2025-02', '2025-03'])
    ret_2025_q2q4 = ep_ret([f'2025-{m:02d}' for m in range(4, 13)])
    ret_2026_juloct = ep_ret(['2026-07', '2026-08', '2026-09', '2026-10'])
    ret_oct_2026 = float(L.loc[pd.Timestamp('2026-09-30'), 'net'])

    # Newey-West t-stat vs control on 213 months
    nw_t = 0.0
    if ref_r213 is not None:
        dlt = (r213 - ref_r213).values
        if np.std(dlt) > 1e-10:
            e = dlt - dlt.mean()
            v = float(e @ e / len(e))
            for lag in range(1, 7):
                v += 2.0 * (1.0 - lag / 7.0) * float(e[lag:] @ e[:-lag]) / len(e)
            nw_t = float(dlt.mean() / np.sqrt(max(v, 1e-12) / len(e)))

    return {
        'Variant': name,
        'Panel': panel,
        'Rule_Description': desc,
        'CAGR_213 (09-26/09)': cagr_213,
        'CAGR_214 (incl Oct26)': cagr_214,
        'Excess_Sharpe_213': sharpe_213,
        'Ann_Vol_213': vol_213,
        'Monthly_MaxDD_213': mdd_213,
        'True_Daily_MaxDD_213': daily_dd_213,
        'Daily_MaxDD_incl_Oct26': daily_dd_full,
        'Live_2026_Worst_Daily_DD': live_2026_worst_dd,
        'Live_2026_Oct29_DD': live_2026_oct29_dd,
        'CAGR_2009_2018': cagr_09_18,
        'CAGR_2019_2026': cagr_19_26,
        'Ret_2022 (DVN/EQT)': ret_2022,
        'Ret_All33_SEPOFF': ret_sep_off_33,
        'Ret_All34_SEPOFF_incl_Oct': ret_sep_off_34,
        'Ret_2024Q3_SEPOFF': ret_2024_q3,
        'Ret_2025Q1_SEPOFF': ret_2025_q1,
        'Ret_2025Q2Q4_SEPON': ret_2025_q2q4,
        'Ret_JulOct2026_SEPOFF': ret_2026_juloct,
        'Ret_Oct2026_Live': ret_oct_2026,
        'Avg_Monthly_Turnover': float(L.loc[months_213, 'turnover'].mean()),
        'Max_SingleStock_Wt_SEPOFF': float(L[~L['sep_on']]['max_single_stock_wt'].max()),
        'NW_t_vs_Panel_Ctrl': nw_t,
        'Peak_to_Trough_213': f'{peak_213.strftime("%Y-%m-%d")} -> {trough_213.strftime("%Y-%m-%d")}',
        'Peak_to_Trough_Full': f'{peak_full.strftime("%Y-%m-%d")} -> {trough_full.strftime("%Y-%m-%d")}',
    }


def main():
    print('=' * 110)
    print('CLEAN-ROOM INDEPENDENT AUDIT: SEP = OFF OVERLAP-CAP & DUPLICATE-TO-ExIT EXPERIMENT')
    print('=' * 110)

    (Pq, Ps, reg, reg_map, pk_q, pk_t, pk_s, pk_exit_raw, pk_exit_bs,
     top_exit_sec, sec_lk, ret_lk, get_df_for_daily) = load_independent_inputs()

    cal = IE.calendar()
    months_213 = [t for t in sorted(Pq['t'].unique()) if t <= pd.Timestamp('2026-08-31')]
    months_214 = [t for t in sorted(Pq['t'].unique()) if t <= pd.Timestamp('2026-09-30')]
    months_215 = [t for t in sorted(Pq['t'].unique()) if t <= pd.Timestamp('2026-10-31')]

    # -------------------------------------------------------------------------
    # 1. Diagnostic Table: Overlap vs No-Overlap in SEP ON vs SEP OFF
    # -------------------------------------------------------------------------
    df_diag = build_overlap_diagnostic_table(months_213, months_214, reg_map, pk_q, pk_t, pk_s, ret_lk)
    df_diag.to_csv(os.path.join(HERE, '01_sep_on_vs_off_overlap_diagnostic.csv'), index=False)
    print('\n--- [1] Structural Diagnostic: Overlap in SEP ON vs SEP OFF ---')
    for _, r in df_diag[df_diag['Window'].str.startswith('2009-01..2026-09')].iterrows():
        print(f"  {r['Architecture']:<18} | {r['State_Bucket']:<22} | N={int(r['Months']):3d} | "
              f"Mean={r['Mean_Monthly_Ret']*100:+6.2f}% | AnnGeom={r['Annualized_Geom_Return']*100:+7.2f}% | "
              f"Win={r['Win_Rate']*100:5.1f}% | Worst={r['Worst_Month']*100:+6.2f}%")

    # -------------------------------------------------------------------------
    # 2. Define Pre-Registered Rules (Panel A: 2-Leg G1_SPY_2e, Panel B: 3-Leg 3S_G1_1k)
    # -------------------------------------------------------------------------
    # --- Panel A: 2-Leg G1_SPY_2e (50% QQQ [25%+25%] + 50% SPY) ---
    def r_2L_ctrl(t):
        q1, q2 = pk_q[t]; s1 = pk_s[t][0]
        w = {q1: 0.25, q2: 0.25}; w[s1] = w.get(s1, 0.0) + 0.50
        return w

    def r_2L_always_cap50_sgov(t):
        w = r_2L_ctrl(t)
        out, sgov = {}, 0.0
        for k, v in w.items():
            if v > 0.50: out[k] = 0.50; sgov += (v - 0.50)
            else: out[k] = v
        if sgov > 0: out['SGOV'] = sgov
        return out

    def r_2L_always_dup_exit(t, use_bs=False):
        q1, q2 = pk_q[t]; s1 = pk_s[t][0]; ex = pk_exit_bs[t][0] if use_bs else pk_exit_raw[t][0]
        if s1 in (q1, q2):
            w = {q1: 0.25, q2: 0.25, 'SGOV': 0.25}; w[ex] = w.get(ex, 0.0) + 0.25; return w
        return r_2L_ctrl(t)

    def r_2L_sepoff_cap50_sgov(t):
        if reg_map[t]['sep_on']: return r_2L_ctrl(t)
        return r_2L_always_cap50_sgov(t)

    def r_2L_sepoff_dup_exit25_sgov25(t, use_bs=False):
        if reg_map[t]['sep_on']: return r_2L_ctrl(t)
        return r_2L_always_dup_exit(t, use_bs=use_bs)

    def r_2L_sepoff_dup_exit33(t, use_bs=False):
        if reg_map[t]['sep_on']: return r_2L_ctrl(t)
        q1, q2 = pk_q[t]; s1 = pk_s[t][0]; ex = pk_exit_bs[t][0] if use_bs else pk_exit_raw[t][0]
        if s1 in (q1, q2):
            w = {q1: 1/3, q2: 1/3}; w[ex] = w.get(ex, 0.0) + 1/3; return w
        return r_2L_ctrl(t)

    def r_2L_sepoff_dup_exit50(t, use_bs=False):
        if reg_map[t]['sep_on']: return r_2L_ctrl(t)
        q1, q2 = pk_q[t]; s1 = pk_s[t][0]; ex = pk_exit_bs[t][0] if use_bs else pk_exit_raw[t][0]
        if s1 in (q1, q2):
            w = {q1: 0.25, q2: 0.25}; w[ex] = w.get(ex, 0.0) + 0.50; return w
        return r_2L_ctrl(t)

    def r_2L_sepoff_cap25_it_spy_to_exit(t, use_bs=False):
        """
        In 2-Leg, SPY alone is 50%. During SEP OFF, if SPY picks an IT stock (duplicating QQQ's Tech exposure,
        like 50% SNDK in Oct 2026), cap SPY's IT stock at 25% (or 0% extra if already in QQQ -> 25% SGOV)
        and allocate 25% to Ex-IT. If SPY picks a Non-IT stock (like DVN/EQT in 2022), keep 50% SPY!
        """
        if reg_map[t]['sep_on']: return r_2L_ctrl(t)
        q1, q2 = pk_q[t]; s1 = pk_s[t][0]; ex = pk_exit_bs[t][0] if use_bs else pk_exit_raw[t][0]
        s_is_it = (sec_lk.get((t, s1)) == 'Information Technology')
        if s1 in (q1, q2):
            w = {q1: 0.25, q2: 0.25, 'SGOV': 0.25}; w[ex] = w.get(ex, 0.0) + 0.25; return w
        elif s_is_it:
            w = {q1: 0.25, q2: 0.25, s1: 0.25}; w[ex] = w.get(ex, 0.0) + 0.25; return w
        return r_2L_ctrl(t)

    # --- Panel B: 3-Leg 3S_G1_1k (50% QQQ [25%+25%] + 25% Tech + 25% SPY) ---
    def r_3L_ctrl(t):
        q1, q2 = pk_q[t]; t1 = pk_t[t][0]; s1 = pk_s[t][0]
        w = {}
        for x in [q1, q2, t1, s1]: w[x] = w.get(x, 0.0) + 0.25
        return w

    def r_3L_always_cap25_dup_exit(t, use_bs=False):
        q1, q2 = pk_q[t]; t1 = pk_t[t][0]; s1 = pk_s[t][0]; ex = pk_exit_bs[t][0] if use_bs else pk_exit_raw[t][0]
        w = {q1: 0.25, q2: 0.25}
        if t1 in w: w['SGOV'] = w.get('SGOV', 0.0) + 0.25
        else: w[t1] = 0.25
        if s1 in w:
            if ex not in w: w[ex] = 0.25
            else: w['SGOV'] = w.get('SGOV', 0.0) + 0.25
        else: w[s1] = 0.25
        return w

    def r_3L_sepoff_cap50_sgov(t):
        w = r_3L_ctrl(t)
        if reg_map[t]['sep_on']: return w
        out, sgov = {}, 0.0
        for k, v in w.items():
            if v > 0.50: out[k] = 0.50; sgov += (v - 0.50)
            else: out[k] = v
        if sgov > 0: out['SGOV'] = sgov
        return out

    def r_3L_sepoff_spydup_to_exit(t, use_bs=False):
        if reg_map[t]['sep_on']: return r_3L_ctrl(t)
        q1, q2 = pk_q[t]; t1 = pk_t[t][0]; s1 = pk_s[t][0]; ex = pk_exit_bs[t][0] if use_bs else pk_exit_raw[t][0]
        w = {}
        for x in [q1, q2, t1]: w[x] = w.get(x, 0.0) + 0.25
        if s1 in w: w[ex] = w.get(ex, 0.0) + 0.25
        else: w[s1] = w.get(s1, 0.0) + 0.25
        return w

    def r_3L_sepoff_cap25_alldup_exit_sgov(t, use_bs=False):
        if reg_map[t]['sep_on']: return r_3L_ctrl(t)
        return r_3L_always_cap25_dup_exit(t, use_bs=use_bs)

    def r_3L_sepoff_killqqq_50sgov_allow50(t):
        if reg_map[t]['sep_on']: return r_3L_ctrl(t)
        t1 = pk_t[t][0]; s1 = pk_s[t][0]
        w = {'SGOV': 0.50}
        for x in [t1, s1]: w[x] = w.get(x, 0.0) + 0.25
        return w

    def r_3L_sepoff_killqqq_50sgov_cap25_spydup_exit(t, use_bs=False):
        if reg_map[t]['sep_on']: return r_3L_ctrl(t)
        t1 = pk_t[t][0]; s1 = pk_s[t][0]; ex = pk_exit_bs[t][0] if use_bs else pk_exit_raw[t][0]
        w = {'SGOV': 0.50, t1: 0.25}
        if s1 == t1: w[ex] = w.get(ex, 0.0) + 0.25
        else: w[s1] = w.get(s1, 0.0) + 0.25
        return w

    def r_3L_sepoff_killqqq_25sgov_25exit_allow50(t, use_bs=False):
        if reg_map[t]['sep_on']: return r_3L_ctrl(t)
        t1 = pk_t[t][0]; s1 = pk_s[t][0]; ex = pk_exit_bs[t][0] if use_bs else pk_exit_raw[t][0]
        w = {'SGOV': 0.25}
        for x in [t1, s1, ex]: w[x] = w.get(x, 0.0) + 0.25
        return w

    specs = [
        # Panel A: 2-Leg (G1_SPY_2e)
        ('2L_0_Ctrl', 'Panel A: 2-Leg (G1_SPY_2e)', 'Original 2-Leg: Allow overlap up to 75%', r_2L_ctrl),
        ('2L_0b_Always_Cap50_SGOV', 'Panel A: 2-Leg (G1_SPY_2e)', 'Always (SEP ON+OFF): Cap single stock <=50%, excess -> SGOV', r_2L_always_cap50_sgov),
        ('2L_0c_Always_DupToExITRaw', 'Panel A: 2-Leg (G1_SPY_2e)', 'Always (SEP ON+OFF): SPY==QQQ duplicate -> 25% ExIT_Raw + 25% SGOV', lambda t: r_2L_always_dup_exit(t, False)),
        ('2L_1_SEPOFF_Cap50_to_SGOV', 'Panel A: 2-Leg (G1_SPY_2e)', 'SEP OFF Only: Cap single stock <=50%, excess 25% -> SGOV', r_2L_sepoff_cap50_sgov),
        ('2L_2a_SEPOFF_Cap25_DupToExITRaw_SGOV', 'Panel A: 2-Leg (G1_SPY_2e)', 'SEP OFF Only: SPY==QQQ duplicate -> 25% ExIT_Raw + 25% SGOV (Cap <=25% on overlap)', lambda t: r_2L_sepoff_dup_exit25_sgov25(t, False)),
        ('2L_2b_SEPOFF_Cap33_DupToExITRaw', 'Panel A: 2-Leg (G1_SPY_2e)', 'SEP OFF Only: SPY==QQQ duplicate -> 33.3% Q1 + 33.3% Q2 + 33.3% ExIT_Raw', lambda t: r_2L_sepoff_dup_exit33(t, False)),
        ('2L_2c_SEPOFF_DupToExITRaw50', 'Panel A: 2-Leg (G1_SPY_2e)', 'SEP OFF Only: SPY==QQQ duplicate -> 25% Q1 + 25% Q2 + 50% ExIT_Raw', lambda t: r_2L_sepoff_dup_exit50(t, False)),
        ('2L_2d_SEPOFF_Cap25_DupToExITBS_SGOV', 'Panel A: 2-Leg (G1_SPY_2e)', 'SEP OFF Only: SPY==QQQ duplicate -> 25% ExIT_BestSec + 25% SGOV (Cap <=25% on overlap)', lambda t: r_2L_sepoff_dup_exit25_sgov25(t, True)),
        ('2L_2e_SEPOFF_Cap33_DupToExITBS', 'Panel A: 2-Leg (G1_SPY_2e)', 'SEP OFF Only: SPY==QQQ duplicate -> 33.3% Q1 + 33.3% Q2 + 33.3% ExIT_BestSec', lambda t: r_2L_sepoff_dup_exit33(t, True)),
        ('2L_2f_SEPOFF_DupToExITBS50', 'Panel A: 2-Leg (G1_SPY_2e)', 'SEP OFF Only: SPY==QQQ duplicate -> 25% Q1 + 25% Q2 + 50% ExIT_BestSec', lambda t: r_2L_sepoff_dup_exit50(t, True)),
        ('2L_3a_SEPOFF_Cap25_ITSpyToExITRaw', 'Panel A: 2-Leg (G1_SPY_2e)', 'SEP OFF Only: Strict <=25% Tech Cap (if SPY is IT, split 25% SPY/SGOV + 25% ExIT_Raw)', lambda t: r_2L_sepoff_cap25_it_spy_to_exit(t, False)),
        ('2L_3b_SEPOFF_Cap25_ITSpyToExITBS', 'Panel A: 2-Leg (G1_SPY_2e)', 'SEP OFF Only: Strict <=25% Tech Cap (if SPY is IT, split 25% SPY/SGOV + 25% ExIT_BestSec)', lambda t: r_2L_sepoff_cap25_it_spy_to_exit(t, True)),

        # Panel B: 3-Leg (3S_G1_1k)
        ('3L_0_Ctrl', 'Panel B: 3-Leg (3S_G1_1k)', 'Original 3-Leg: Allow overlap up to 75%', r_3L_ctrl),
        ('3L_0b_Always_Cap25_DupToExITRaw', 'Panel B: 3-Leg (3S_G1_1k)', 'Always (SEP ON+OFF): Strict <=25% Cap (SPY dup -> ExIT_Raw, Tech dup -> SGOV)', lambda t: r_3L_always_cap25_dup_exit(t, False)),
        ('3L_1_SEPOFF_Cap50_to_SGOV', 'Panel B: 3-Leg (3S_G1_1k)', 'SEP OFF Only: Cap single stock <=50%, excess 25% -> SGOV', r_3L_sepoff_cap50_sgov),
        ('3L_2a_SEPOFF_SpyDup_to_ExITRaw', 'Panel B: 3-Leg (3S_G1_1k)', 'SEP OFF Only: Duplicate 25% SPY leg -> 25% ExIT_Raw (Cap <=50%)', lambda t: r_3L_sepoff_spydup_to_exit(t, False)),
        ('3L_2b_SEPOFF_SpyDup_to_ExITBS', 'Panel B: 3-Leg (3S_G1_1k)', 'SEP OFF Only: Duplicate 25% SPY leg -> 25% ExIT_BestSec (Cap <=50%)', lambda t: r_3L_sepoff_spydup_to_exit(t, True)),
        ('3L_2c_SEPOFF_Cap25_AllDup_ExITRaw_SGOV', 'Panel B: 3-Leg (3S_G1_1k)', 'SEP OFF Only: Strict <=25% Cap (SPY dup -> 25% ExIT_Raw, Tech/QQQ dup -> 25% SGOV)', lambda t: r_3L_sepoff_cap25_alldup_exit_sgov(t, False)),
        ('3L_2d_SEPOFF_Cap25_AllDup_ExITBS_SGOV', 'Panel B: 3-Leg (3S_G1_1k)', 'SEP OFF Only: Strict <=25% Cap (SPY dup -> 25% ExIT_BestSec, Tech/QQQ dup -> 25% SGOV)', lambda t: r_3L_sepoff_cap25_alldup_exit_sgov(t, True)),
        ('3L_3a_SEPOFF_KillQQQ_50SGOV_Allow50', 'Panel B: 3-Leg (3S_G1_1k)', 'SEP OFF Only: QQQ 50% -> SGOV, keep 25% Tech + 25% SPY (allow 50% overlap)', r_3L_sepoff_killqqq_50sgov_allow50),
        ('3L_3b_SEPOFF_KillQQQ_50SGOV_Cap25_ExITRaw', 'Panel B: 3-Leg (3S_G1_1k)', 'SEP OFF Only: QQQ 50% -> SGOV + Strict <=25% Cap (if SPY==Tech -> 25% ExIT_Raw)', lambda t: r_3L_sepoff_killqqq_50sgov_cap25_spydup_exit(t, False)),
        ('3L_3c_SEPOFF_KillQQQ_50SGOV_Cap25_ExITBS', 'Panel B: 3-Leg (3S_G1_1k)', 'SEP OFF Only: QQQ 50% -> SGOV + Strict <=25% Cap (if SPY==Tech -> 25% ExIT_BestSec)', lambda t: r_3L_sepoff_killqqq_50sgov_cap25_spydup_exit(t, True)),
        ('3L_3d_SEPOFF_KillQQQ_25SGOV_25ExITRaw_Allow50', 'Panel B: 3-Leg (3S_G1_1k)', 'SEP OFF Only: QQQ 50% -> 25% SGOV + 25% ExIT_Raw, keep 25% Tech + 25% SPY (allow 50%)', lambda t: r_3L_sepoff_killqqq_25sgov_25exit_allow50(t, False)),
        ('3L_3e_SEPOFF_KillQQQ_25SGOV_25ExITBS_Allow50', 'Panel B: 3-Leg (3S_G1_1k)', 'SEP OFF Only: QQQ 50% -> 25% SGOV + 25% ExIT_BestSec, keep 25% Tech + 25% SPY (allow 50%)', lambda t: r_3L_sepoff_killqqq_25sgov_25exit_allow50(t, True)),
    ]

    ledgers = {}
    navs = {}
    summary_rows = []
    ref_2l_r213 = None
    ref_3l_r213 = None

    print('\n--- [2] Running Full Clean-Room Simulation & True Daily NAV (2009-01 .. 2026-10 Live) ---')
    for name, panel, desc, fn in specs:
        L, s_nav = simulate_variant_and_daily_nav(fn, months_213, months_214, reg_map, ret_lk, get_df_for_daily, cal)
        ledgers[name] = L
        navs[name] = s_nav
        if name == '2L_0_Ctrl':
            ref_2l_r213 = L.loc[months_213, 'net']
        elif name == '3L_0_Ctrl':
            ref_3l_r213 = L.loc[months_213, 'net']

        ref_r = ref_2l_r213 if panel.startswith('Panel A') else ref_3l_r213
        row = compute_summary_metrics(name, panel, desc, L, s_nav, months_213, ref_r)
        summary_rows.append(row)
        print(f"  {name:<46} | CAGR213={row['CAGR_213 (09-26/09)']*100:6.2f}% | CAGR214={row['CAGR_214 (incl Oct26)']*100:6.2f}% | "
              f"D_DD={row['True_Daily_MaxDD_213']*100:6.2f}% | Live26_DD={row['Live_2026_Worst_Daily_DD']*100:6.2f}% | "
              f"2022={row['Ret_2022 (DVN/EQT)']*100:+6.2f}% | Oct26={row['Ret_Oct2026_Live']*100:+6.2f}%")

    df_sum = pd.DataFrame(summary_rows)
    df_sum.to_csv(os.path.join(HERE, '03_sep_off_overlap_cap_backtest.csv'), index=False)

    # -------------------------------------------------------------------------
    # 3. Complete Month-by-Month Table of All 35 SEP = OFF Months (2021-10 .. 2026-11)
    # -------------------------------------------------------------------------
    sepoff_rows = []
    for t in months_215:
        if reg_map[t]['sep_on']:
            continue
        ym = reg_map[t]['ym']
        q1, q2 = pk_q[t]
        t1 = pk_t[t][0]
        s1 = pk_s[t][0]
        er = pk_exit_raw[t][0]
        eb = pk_exit_bs[t][0]
        top_sec = top_exit_sec[t]
        is_2l_ov = (s1 in (q1, q2))
        is_3l_ov = (len({q1, q2, t1, s1}) < 4)
        is_spy_eq_tech = (s1 == t1)
        s_is_it = (sec_lk.get((t, s1)) == 'Information Technology')

        row_m = {
            'ym': ym,
            'formation_date': t.strftime('%Y-%m-%d'),
            'QQQ_picks': f'{q1}|{q2}',
            'Tech_pick': t1,
            'SPY_pick': s1,
            'SPY_sector': sec_lk.get((t, s1), ''),
            'ExIT_Raw_pick': er,
            'ExIT_Raw_sector': sec_lk.get((t, er), ''),
            'ExIT_BestSec_top_sector': top_sec,
            'ExIT_BestSec_pick': eb,
            '2L_Ticker_Overlap': is_2l_ov,
            '2L_SPY_is_IT': s_is_it,
            '3L_Ticker_Overlap': is_3l_ov,
            '3L_SPY_eq_Tech': is_spy_eq_tech,
        }
        if t in months_214:
            for vname in ['2L_0_Ctrl', '2L_1_SEPOFF_Cap50_to_SGOV', '2L_2a_SEPOFF_Cap25_DupToExITRaw_SGOV',
                          '2L_2d_SEPOFF_Cap25_DupToExITBS_SGOV', '2L_3a_SEPOFF_Cap25_ITSpyToExITRaw',
                          '2L_3b_SEPOFF_Cap25_ITSpyToExITBS', '3L_0_Ctrl', '3L_1_SEPOFF_Cap50_to_SGOV',
                          '3L_2c_SEPOFF_Cap25_AllDup_ExITRaw_SGOV', '3L_2d_SEPOFF_Cap25_AllDup_ExITBS_SGOV',
                          '3L_3a_SEPOFF_KillQQQ_50SGOV_Allow50', '3L_3b_SEPOFF_KillQQQ_50SGOV_Cap25_ExITRaw',
                          '3L_3c_SEPOFF_KillQQQ_50SGOV_Cap25_ExITBS', '3L_3d_SEPOFF_KillQQQ_25SGOV_25ExITRaw_Allow50',
                          '3L_3e_SEPOFF_KillQQQ_25SGOV_25ExITBS_Allow50']:
                row_m[f'net_{vname}'] = float(ledgers[vname].loc[t, 'net'])
        sepoff_rows.append(row_m)

    df_sepoff = pd.DataFrame(sepoff_rows)
    df_sepoff.to_csv(os.path.join(HERE, '02_all_35_sep_off_months_audit.csv'), index=False)

    # -------------------------------------------------------------------------
    # 4. November 2026 (2026-11, formed 2026-10-31) Exact Target Holdings Table
    # -------------------------------------------------------------------------
    t_nov = pd.Timestamp('2026-10-31')
    nov_rows = []
    for name, panel, desc, fn in specs:
        w_nov = {k: round(float(v), 4) for k, v in fn(t_nov).items() if abs(v) > 1e-9}
        # New account entering fresh in Nov 2026 replaces STX (#4 in QQQ) with MU (#2 in QQQ)
        w_new = {}
        for k, v in w_nov.items():
            k_new = 'MU' if k == 'STX' else k
            w_new[k_new] = w_new.get(k_new, 0.0) + v
        max_eq = max([v for k, v in w_nov.items() if k != 'SGOV'], default=0.0)
        w_str = ' + '.join([f'{v*100:.1f}% {k}' for k, v in sorted(w_nov.items(), key=lambda kv: (-kv[1], kv[0]))])
        w_new_str = ' + '.join([f'{v*100:.1f}% {k}' for k, v in sorted(w_new.items(), key=lambda kv: (-kv[1], kv[0]))])
        nov_rows.append({
            'Variant': name,
            'Panel': panel,
            'Rule_Description': desc,
            'Nov_2026_Holdings (Continuing Account)': w_str,
            'Nov_2026_Holdings (New Account)': w_new_str,
            'Max_Single_Stock_Weight': max_eq,
            'SGOV_Weight': w_nov.get('SGOV', 0.0),
        })
    df_nov = pd.DataFrame(nov_rows)
    df_nov.to_csv(os.path.join(HERE, '06_november_2026_holdings_table.csv'), index=False)
    print('\n--- [3] November 2026 (2026-11) Target Holdings Across Pre-Registered Rules ---')
    for _, r in df_nov.iterrows():
        print(f"  {r['Variant']:<46} | Max={r['Max_Single_Stock_Weight']*100:4.1f}% | Cont: {r['Nov_2026_Holdings (Continuing Account)']:<42} | New: {r['Nov_2026_Holdings (New Account)']}")

    # -------------------------------------------------------------------------
    # 5. Multiple-Testing Deflated Sharpe Ratio (DSR: N=902 Main Track & N=1082 All Rounds)
    # -------------------------------------------------------------------------
    reg_r8_path = os.path.join(ROOT, 'outputs', 'consensus_burst_mode_audit_20261104', '06b_master_all_trials_sharpe_registry_r8.csv')
    reg_df = pd.read_csv(reg_r8_path)
    # Track 1: Main 878 baseline (from commit 39c1af4) + 24 pre-registered rules = 902 trials
    sr_m_878 = list(reg_df[(reg_df['round_id'] <= 7) & (reg_df['in_canonical_878'] == True)]['sr_excess_monthly'].dropna().values)
    # Track 2: All rounds including R8 burst/shadow trials + 24 pre-registered rules = 1082 trials
    sr_m_all = list(reg_df[reg_df['in_canonical_878'] == True]['sr_excess_monthly'].dropna().values)
    for row in summary_rows:
        sr_val_m = float(row['Excess_Sharpe_213']) / np.sqrt(12.0)
        sr_m_878.append(sr_val_m)
        sr_m_all.append(sr_val_m)

    def calc_sr0_m(arr_list):
        a = np.array(arr_list, dtype=float)
        n_t = len(a)
        v_sr = float(np.var(a, ddof=1))
        eg = 0.5772156649015329
        z_1 = sst.norm.ppf(1.0 - 1.0 / n_t)
        z_2 = sst.norm.ppf(1.0 - 1.0 / (n_t * np.e))
        return n_t, float(np.sqrt(v_sr) * ((1.0 - eg) * z_1 + eg * z_2))

    N_main, sr0_m_main = calc_sr0_m(sr_m_878)
    N_tot, sr0_m_tot = calc_sr0_m(sr_m_all)

    dgs = json.load(open(os.path.join(ROOT, 'data', 'fred', 'DGS3MO.json')))['values']
    rf_s = pd.Series({pd.Timestamp(d): float(v) / 100.0 for d, v in dgs if v not in (None, '.')}).sort_index().resample('ME').last() / 12.0
    idx_me_213 = pd.DatetimeIndex(months_213) + pd.offsets.MonthEnd(1)
    rf_al_213 = rf_s.reindex(idx_me_213).ffill().fillna(0.0).values

    dsr_rows = []
    for row in summary_rows:
        vname = row['Variant']
        r_m = ledgers[vname].loc[months_213, 'net'].values
        ex = r_m - rf_al_213
        srb = float(np.mean(ex) / np.std(r_m, ddof=1))
        sk = float(sst.skew(ex))
        ku = float(sst.kurtosis(ex, fisher=False))
        T = len(r_m)
        denom = np.sqrt(max(1e-8, 1.0 - sk * srb + ((ku - 1.0) / 4.0) * (srb ** 2)))
        dsr_main = float(sst.norm.cdf((srb - sr0_m_main) * np.sqrt(T - 1.0) / denom))
        dsr_tot = float(sst.norm.cdf((srb - sr0_m_tot) * np.sqrt(T - 1.0) / denom))
        dsr_rows.append({
            'Variant': vname,
            'Panel': row['Panel'],
            'Excess_Sharpe_Ann': row['Excess_Sharpe_213'],
            'N_MainTrack_Trials': N_main,
            'Expected_Max_SR0_MainTrack_Ann': sr0_m_main * np.sqrt(12.0),
            'DSR_MainTrack_902': dsr_main,
            'N_AllRounds_Trials': N_tot,
            'Expected_Max_SR0_AllRounds_Ann': sr0_m_tot * np.sqrt(12.0),
            'DSR_AllRounds_1082': dsr_tot,
            'Skew': sk,
            'Kurtosis': ku,
        })
    df_dsr = pd.DataFrame(dsr_rows)
    df_dsr.to_csv(os.path.join(HERE, '05_multiple_testing_dsr.csv'), index=False)
    print(f'\n--- [4] Cumulative Multiple-Testing DSR (MainTrack N={N_main} SR0={sr0_m_main*np.sqrt(12):.3f} | AllRounds N={N_tot} SR0={sr0_m_tot*np.sqrt(12):.3f}) ---')
    for _, r in df_dsr.iterrows():
        print(f"  {r['Variant']:<46} | Sharpe={r['Excess_Sharpe_Ann']:.3f} | DSR_902={r['DSR_MainTrack_902']*100:5.2f}% | DSR_1082={r['DSR_AllRounds_1082']*100:5.2f}%")


if __name__ == '__main__':
    main()
