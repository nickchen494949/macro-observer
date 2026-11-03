#!/usr/bin/env python3
"""
run_selection_hypotheses_audit.py — Clean-Room Adversarial Audit of Stock-Selection Hypotheses A, B, C, D on Core3
==================================================================================================================
Tests the 3 pre-registered stock-selection hypotheses (plus 2nd-tier 52-Week-High proximity) STRICTLY IN ISOLATION
(never mixing A + B + C together):

  - Hypothesis A (Priority #1): Momentum Consistency / Frog in the Pan (Da, Gurun, Warachka 2014, RFS)
  - Hypothesis B (Priority #2): Residual Momentum (Blitz, Huij, Martens 2011, JEMP)
  - Hypothesis C (Priority #3): Price Momentum + Fundamental / Earnings Momentum (Novy-Marx 2015 / PEAD)
  - Hypothesis D (2nd Tier):    52-Week-High Proximity (George & Hwang 2004, JF)

For EVERY hypothesis independently, executes the complete 7-step adversarial protocol:
  1. Control vs Single Hypothesis (QQQ Sleeve Top-2 alone, Tech Sleeve Top-1 alone, and Combined Core3 50/50)
  2. Rank #1 vs Rank #2 Diagnostic (does the hypothesis fix QQQ Rank #1 25.06% vs Rank #2 55.23%?)
  3. Parameter Neighborhood Grid (pool sizes N, weights w, lookback windows 6m/12m/18m)
  4. Subperiod Stability (2009-2018, 2019-2026, 2015-2026, 2022 Bear Market)
  5. Leave-One-Winner-Out (NVDA, SNDK, PLTR, TSLA, MU, WDC, AMD) & Remove Top-5 Best Months
  6. Second Vendor (Tiingo-First) End-to-End Replication
  7. True Daily Mark-to-Market MaxDD (5651ec2 & Open-to-Close) + Cumulative Multiple-Testing DSR
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
# 1. Core Monthly & Daily Portfolio Simulation Engines
# =============================================================================
def load_rf():
    fn = os.path.join(ROOT, 'data', 'fred', 'DGS3MO.json')
    d = json.load(open(fn))['values']
    s = pd.Series({pd.Timestamp(dt): float(v) / 100.0 for dt, v in d if v is not None and v != '.'}).sort_index()
    rf_monthly = s.resample('ME').last() / 12.0
    cal = QE.calendar()
    cal_days = cal[(cal >= '2009-01-02') & (cal <= '2026-10-01')]
    s_al = s.reindex(cal_days.union(s.index)).sort_index().ffill().reindex(cal_days).fillna(0.0)
    rf_daily = (1.0 + s_al) ** (1.0 / 252.0) - 1.0
    return rf_monthly, rf_daily, cal_days


def select_candidates_for_month(g, rule_spec, k=2, target_rank=None):
    """
    Given a single formation month's DataFrame `g` of eligible candidates, select top `k` tickers
    (or a specific `target_rank` 1, 2, 3 for rank-by-rank diagnostics) using `rule_spec`:

    rule_spec dict keys:
      - 'type':
          * 'score': sort descending by column `score_col` (or custom expression `expr_fn(g)`)
          * 'pool_rerank': take top `pool_n` by `base_col`, then re-rank those `pool_n` candidates by
                           `rerank_col` (or `rerank_fn(sub)`). If `rerank_col` has NaNs (e.g. missing early XBRL),
                           candidates with valid `rerank_col` are ranked by `(1 - w_base) * pct_rerank + w_base * pct_base`,
                           and candidates with NaN keep their `pct_base` (so missing fundamental data neither gets an
                           artificial boost nor gets dropped).
          * 'veto': sort descending by `base_col`, then drop any candidate in top `pool_n` that violates `veto_fn(row)`
                    (falling back to unvetoed order if fewer than `k` survive).
          * 'rank_blend': within top `pool_n` (or full universe if `pool_n` is None), compute
                          `score = pct_rank(base_col) + w * pct_rank(sec_col)` (where missing `sec_col` defaults to 0.5).
    """
    rtype = rule_spec['type']
    base_col = rule_spec.get('base_col', 'sharpe_mom_12_1')
    sub = g.dropna(subset=[base_col, 'hold_ret']).copy()
    if sub.empty:
        return []

    if rtype == 'score':
        if 'expr_fn' in rule_spec:
            sub['_sc'] = rule_spec['expr_fn'](sub)
        else:
            sc_col = rule_spec['score_col']
            sub['_sc'] = sub[sc_col]
        sub = sub.dropna(subset=['_sc']).sort_values(['_sc', 'ticker'], ascending=[False, True]).reset_index(drop=True)

    elif rtype == 'pool_rerank':
        pool_n = int(rule_spec['pool_n'])
        rerank_col = rule_spec['rerank_col']
        w_base = float(rule_spec.get('w_base', 0.0))
        require_pos_mom = bool(rule_spec.get('require_pos_mom', False))
        if require_pos_mom:
            pos_sub = sub[sub['mom_12_1'] > 0]
            if len(pos_sub) >= k:
                sub = pos_sub
        pool = sub.sort_values([base_col, 'ticker'], ascending=[False, True]).head(pool_n).copy()
        if pool[rerank_col].notna().sum() >= k:
            # Rank within the top-N pool
            rk_base = pool[base_col].rank(pct=True, ascending=True)
            rk_sec = pool[rerank_col].rank(pct=True, ascending=True)
            # If a candidate in the pool has NaN for rerank_col (e.g. foreign ADR without 10-Q), assign neutral 0.5
            rk_sec_filled = rk_sec.fillna(0.5)
            if w_base > 0:
                pool['_sc'] = (1.0 - w_base) * rk_sec_filled + w_base * rk_base
            else:
                # Pure secondary rerank among those with valid signal; tie-break by base_col
                pool['_sc'] = rk_sec_filled + 1e-4 * rk_base
            sub = pool.sort_values(['_sc', base_col, 'ticker'], ascending=[False, False, True]).reset_index(drop=True)
        else:
            sub = pool.reset_index(drop=True)

    elif rtype == 'veto':
        pool_n = int(rule_spec.get('pool_n', 6))
        veto_fn = rule_spec['veto_fn']
        pool = sub.sort_values([base_col, 'ticker'], ascending=[False, True]).head(pool_n).copy()
        keep_mask = ~pool.apply(veto_fn, axis=1)
        kept = pool[keep_mask]
        rejected = pool[~keep_mask]
        sub = pd.concat([kept, rejected], ignore_index=True)

    elif rtype == 'rank_blend':
        pool_n = rule_spec.get('pool_n', None)
        sec_col = rule_spec['sec_col']
        w = float(rule_spec.get('w', 0.50))
        if pool_n is not None:
            pool = sub.sort_values([base_col, 'ticker'], ascending=[False, True]).head(int(pool_n)).copy()
        else:
            pool = sub.copy()
        rk_b = pool[base_col].rank(pct=True, ascending=True)
        rk_s = pool[sec_col].rank(pct=True, ascending=True).fillna(0.5)
        pool['_sc'] = rk_b + w * rk_s
        sub = pool.sort_values(['_sc', base_col, 'ticker'], ascending=[False, False, True]).reset_index(drop=True)

    else:
        raise ValueError(f'Unknown rule_spec type: {rtype}')

    if target_rank is not None:
        idx = int(target_rank) - 1
        if idx < len(sub):
            return [sub.iloc[idx]]
        return [sub.iloc[-1]]
    return [sub.iloc[i] for i in range(min(k, len(sub)))]


def run_sleeve_backtest(panel_df, rule_spec, k=2, target_rank=None, cost_bp=10.0, linear_cost=True, exclude_tickers=None):
    """
    Run a single sleeve (QQQ Top-2 or Tech Top-1) across all 213 months with exact drifted-weight turnover.
    Matches frozen QQQ Top-2 (linear_cost=True, initial entry cost=2*c) and frozen Tech S1 (linear_cost=False, initial sides=1.0).
    """
    c = cost_bp / 1e4
    df = panel_df
    if exclude_tickers:
        df = df[~df['ticker'].isin(set(exclude_tickers))]

    prev_w = {}
    rows = []
    for t_val, g in df.groupby('t', sort=True):
        m_dt = pd.Timestamp(t_val) + pd.offsets.MonthEnd(1)
        chosen_rows = select_candidates_for_month(g, rule_spec, k=k, target_rank=target_rank)
        picks = [r['ticker'] for r in chosen_rows]
        rets = [float(r['hold_ret']) for r in chosen_rows]
        w = {p: 1.0 / len(picks) for p in picks}
        gross = float(sum(w[p] * r for p, r in zip(picks, rets)))

        if not prev_w:
            # Match exact initial entry convention of QQQ (2.0 sides -> 20bp) vs Tech S1 (1.0 side -> 10bp)
            to = 2.0 if linear_cost else 1.0
        else:
            to = float(sum(abs(w.get(tk, 0.0) - prev_w.get(tk, 0.0)) for tk in set(w) | set(prev_w)))

        if linear_cost:
            net = gross - to * c
        else:
            net = (1.0 + gross) * ((1.0 - c) ** to) - 1.0 if to > 0 else gross

        tot = sum(w[p] * (1.0 + r) for p, r in zip(picks, rets))
        prev_w = {p: w[p] * (1.0 + r) / tot for p, r in zip(picks, rets)} if tot > 0 else {}

        rows.append({
            'month': m_dt,
            'formation_t': pd.Timestamp(t_val),
            'picks': '|'.join(picks),
            'rets': '|'.join(f'{r:.6f}' for r in rets),
            'gross': gross,
            'turnover': to,
            'net': net,
        })
    return pd.DataFrame(rows).set_index('month')


def combine_core3(L_qqq, L_tech, w_q=0.50, w_t=0.50):
    """Combine QQQ sleeve and Tech sleeve into 50/50 Core3 (matching Frozen Core3 Sleeve-Avg 43.85% convention)."""
    common_m = L_qqq.index.intersection(L_tech.index)
    r_net = w_q * L_qqq.loc[common_m, 'net'] + w_t * L_tech.loc[common_m, 'net']
    r_gross = w_q * L_qqq.loc[common_m, 'gross'] + w_t * L_tech.loc[common_m, 'gross']
    to = w_q * L_qqq.loc[common_m, 'turnover'] + w_t * L_tech.loc[common_m, 'turnover']
    out = pd.DataFrame({
        'formation_t': L_qqq.loc[common_m, 'formation_t'],
        'qqq_picks': L_qqq.loc[common_m, 'picks'],
        'tech_picks': L_tech.loc[common_m, 'picks'],
        'gross': r_gross,
        'turnover': to,
        'net': r_net,
    }, index=common_m)
    return out


# =============================================================================
# 2. Daily Mark-to-Market Path Builder for Any Core3 Selection Variant
# =============================================================================
_DAILY_STOCK_CACHE = {}


def load_daily_stock_series(sleeve, tk, t_form, qqq_lookup):
    t_form = pd.Timestamp(t_form)
    if sleeve == 'qqq':
        st, sym = qqq_lookup.get((t_form, tk), ('yahoo', tk))
        ckey = ('qqq', st, sym)
        if ckey not in _DAILY_STOCK_CACHE:
            df = QE.series(st, sym)
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
        df_raw, src, sym, _ = chosen
        ckey = ('tech', tk, src, sym, str(df_raw.index.min().date()), str(df_raw.index.max().date()))
        if ckey not in _DAILY_STOCK_CACHE:
            df = pd.DataFrame({
                'adjclose': df_raw['adjclose'],
                'adjopen': df_raw['adj_open'] if 'adj_open' in df_raw.columns else np.nan,
            }, index=df_raw.index).sort_index()
            df = df[~df.index.duplicated(keep='last')]
            df['adjopen_clean'] = df['adjopen'].where(df['adjopen'].notna() & (df['adjopen'] > 0), df['adjclose'])
            _DAILY_STOCK_CACHE[ckey] = df
        return _DAILY_STOCK_CACHE[ckey]


def compute_daily_drawdowns_for_core3(L_core3, cal_days, qqq_lookup):
    """
    Compute both:
      - `Daily_MaxDD_5651ec2`: Entry-day close normalized daily drawdown (matches -46.76% on Frozen Core3)
      - `True_Daily_MaxDD_O2C`: Exact Open-to-Close daily drawdown (matches -49.68% on Frozen Core3)
    """
    W = 1.0
    pts_c56 = {}
    pts_o2c = {}

    for m_dt, row in L_core3.iterrows():
        t_form = pd.Timestamp(row['formation_t'])
        e_d = QE.first_td_after(t_form, 1)
        x_d = QE.first_td_after(m_dt, 1)
        m_days = cal_days[(cal_days >= e_d) & (cal_days < x_d)]
        if not len(m_days):
            continue

        q_pks = str(row['qqq_picks']).split('|')
        t_pk = str(row['tech_picks']).split('|')[0]
        s0 = load_daily_stock_series('qqq', q_pks[0], t_form, qqq_lookup)
        s1 = load_daily_stock_series('qqq', q_pks[1] if len(q_pks) > 1 else q_pks[0], t_form, qqq_lookup)
        s2 = load_daily_stock_series('tech', t_pk, t_form, qqq_lookup)

        p0_e = float(s0.loc[:e_d, 'adjopen_clean'].iloc[-1])
        p1_e = float(s1.loc[:e_d, 'adjopen_clean'].iloc[-1])
        p2_e = float(s2.loc[:e_d, 'adjopen_clean'].iloc[-1])

        m_cost = float(row['gross'] - row['net'])
        W_after_entry = W * (1.0 - m_cost)

        vq0, vt0 = 1.0, 1.0
        for d_i, d in enumerate(m_days):
            v_q = 0.5 * (float(s0.loc[:d, 'adjclose'].iloc[-1]) / p0_e) + 0.5 * (float(s1.loc[:d, 'adjclose'].iloc[-1]) / p1_e)
            v_t = float(s2.loc[:d, 'adjclose'].iloc[-1]) / p2_e
            if d_i == 0:
                vq0, vt0 = v_q, v_t
            pts_c56[d] = W * (0.5 * (v_q / vq0) + 0.5 * (v_t / vt0))
            pts_o2c[d] = W_after_entry * (0.5 * v_q + 0.5 * v_t)

        W = W * (1.0 + float(row['net']))
        pts_c56[x_d] = W
        pts_o2c[x_d] = W

    s_c56 = pd.Series(pts_c56).sort_index()
    s_c56 = s_c56[~s_c56.index.duplicated(keep='last')]
    s_o2c = pd.Series(pts_o2c).sort_index()
    s_o2c = s_o2c[~s_o2c.index.duplicated(keep='last')]

    dd_c56 = float((s_c56 / s_c56.cummax() - 1.0).min())
    dd_o2c = float((s_o2c / s_o2c.cummax() - 1.0).min())
    return dd_c56, dd_o2c, s_c56, s_o2c


# =============================================================================
# 3. Statistical Summary Helper
# =============================================================================
def summarize_series(name, hyp_family, r_m, rf_monthly, to_series=None, dd_c56=np.nan, dd_o2c=np.nan, ref_r=None):
    r_m = r_m.dropna()
    n = len(r_m)
    cagr_all = float((np.prod(1.0 + r_m)) ** (12.0 / n) - 1.0)
    vol_m = float(r_m.std(ddof=1) * np.sqrt(12.0))
    ex_m = r_m - rf_monthly.reindex(r_m.index).ffill().fillna(0.0)
    sharpe_m = float(ex_m.mean() / r_m.std(ddof=1) * np.sqrt(12.0)) if r_m.std(ddof=1) > 0 else np.nan
    neg = r_m[r_m < 0]
    sortino = float(ex_m.mean() * 12.0 / (neg.std(ddof=1) * np.sqrt(12.0))) if len(neg) > 1 else np.nan
    w = np.concatenate([[1.0], np.cumprod(1.0 + r_m.values)])
    maxdd_m = float((w / np.maximum.accumulate(w) - 1.0).min())
    calmar_m = cagr_all / abs(maxdd_m) if maxdd_m < 0 else np.nan

    def sub_cagr(a, b):
        sub = r_m.loc[a:b]
        return float((np.prod(1.0 + sub)) ** (12.0 / len(sub)) - 1.0) if len(sub) else np.nan

    ret_2022 = float(np.prod(1.0 + r_m.loc['2022-01-01':'2022-12-31']) - 1.0)

    # Newey-West t-stat of monthly active return vs Frozen Core3 Control
    nw_t_vs_ref = np.nan
    if ref_r is not None:
        diff = (r_m - ref_r.reindex(r_m.index)).dropna().values
        if len(diff) >= 24 and np.std(diff, ddof=1) > 1e-9:
            e = diff - diff.mean()
            L_len = len(diff)
            v = (e @ e) / L_len
            for lag in range(1, 7):
                v += 2.0 * (1.0 - lag / 7.0) * (e[lag:] @ e[:-lag]) / L_len
            if v > 0:
                nw_t_vs_ref = float(diff.mean() / np.sqrt(v / L_len))

    return {
        'Variant': name,
        'Hypothesis': hyp_family,
        'CAGR_09_26': cagr_all,
        'Sharpe_m': sharpe_m,
        'Sortino_m': sortino,
        'Monthly_Vol': vol_m,
        'Monthly_MaxDD': maxdd_m,
        'Calmar_Monthly': calmar_m,
        'Daily_MaxDD_5651ec2': dd_c56,
        'Daily_MaxDD_O2C': dd_o2c,
        'CAGR_2009_2018': sub_cagr('2009-01-31', '2018-12-31'),
        'CAGR_2019_2026': sub_cagr('2019-01-31', '2026-09-30'),
        'CAGR_2015_2026': sub_cagr('2015-01-31', '2026-09-30'),
        'Ret_2022': ret_2022,
        'Avg_Monthly_TO': float(to_series.mean()) if to_series is not None else np.nan,
        'NW_t_vs_Control': nw_t_vs_ref,
    }


def main():
    print('=== STARTING CLEAN-ROOM ADVERSARIAL AUDIT OF STOCK-SELECTION HYPOTHESES A, B, C, D ===')
    df_qqq = pd.read_parquet(os.path.join(HERE, 'qqq_selection_panel.parquet'))
    df_tech = pd.read_parquet(os.path.join(HERE, 'tech_selection_panel.parquet'))
    df_qqq_t = pd.read_parquet(os.path.join(HERE, 'qqq_selection_panel_tiingo.parquet'))
    df_tech_t = pd.read_parquet(os.path.join(HERE, 'tech_selection_panel_tiingo.parquet'))

    rf_monthly, rf_daily, cal_days = load_rf()
    qqq_lookup = {(pd.Timestamp(r['t']), r['ticker']): (r['ret_store'], r['ret_sym']) for _, r in df_qqq.iterrows()}

    # Frozen Control Rules
    ctrl_qqq_spec = {'type': 'score', 'base_col': 'sharpe_mom_12_1', 'score_col': 'sharpe_mom_12_1'}
    ctrl_tech_spec = {'type': 'score', 'base_col': 'mom_12_1', 'score_col': 'mom_12_1'}

    L_qqq_ctrl = run_sleeve_backtest(df_qqq, ctrl_qqq_spec, k=2, linear_cost=True)
    L_tech_ctrl = run_sleeve_backtest(df_tech, ctrl_tech_spec, k=1, linear_cost=False)
    L_core3_ctrl = combine_core3(L_qqq_ctrl, L_tech_ctrl)
    r_ctrl = L_core3_ctrl['net']

    dd56_ctrl, ddo2c_ctrl, _, _ = compute_daily_drawdowns_for_core3(L_core3_ctrl, cal_days, qqq_lookup)
    print(f"Control Core3 verified: CAGR={(np.prod(1+r_ctrl)**(12/len(r_ctrl))-1)*100:.2f}%, "
          f"MonthDD={summarize_series('', '', r_ctrl, rf_monthly)['Monthly_MaxDD']*100:.2f}%, "
          f"DailyDD(5651)={dd56_ctrl*100:.2f}%, DailyDD(O2C)={ddo2c_ctrl*100:.2f}%")

    all_monthly_series = {'00. Core3 Control [FROZEN]': r_ctrl}
    master_rows = []
    sleeve_rows = []

    def eval_core3_pair(label, hyp, q_spec, t_spec, compute_daily=True):
        Lq = run_sleeve_backtest(df_qqq, q_spec, k=2, linear_cost=True)
        Lt = run_sleeve_backtest(df_tech, t_spec, k=1, linear_cost=False)
        Lc = combine_core3(Lq, Lt)
        dd56, ddo2c = (np.nan, np.nan)
        if compute_daily:
            dd56, ddo2c, _, _ = compute_daily_drawdowns_for_core3(Lc, cal_days, qqq_lookup)
        row = summarize_series(label, hyp, Lc['net'], rf_monthly, Lc['turnover'], dd56, ddo2c, ref_r=r_ctrl)
        # Also record standalone QQQ sleeve and Tech sleeve CAGRs & MaxDDs
        sq = summarize_series(label + ' [QQQ]', hyp, Lq['net'], rf_monthly, Lq['turnover'], ref_r=L_qqq_ctrl['net'])
        st = summarize_series(label + ' [Tech]', hyp, Lt['net'], rf_monthly, Lt['turnover'], ref_r=L_tech_ctrl['net'])
        row['QQQ_Sleeve_CAGR'] = sq['CAGR_09_26']
        row['QQQ_Sleeve_MaxDD'] = sq['Monthly_MaxDD']
        row['Tech_Sleeve_CAGR'] = st['CAGR_09_26']
        row['Tech_Sleeve_MaxDD'] = st['Monthly_MaxDD']
        master_rows.append(row)
        all_monthly_series[label] = Lc['net']
        print(f"  {label:<66} | Core3={row['CAGR_09_26']*100:6.2f}% | MonthDD={row['Monthly_MaxDD']*100:6.2f}% | "
              f"DailyDD(5651)={dd56*100:6.2f}% | Sharpe={row['Sharpe_m']:4.2f} | QQQ={sq['CAGR_09_26']*100:5.2f}% | "
              f"Tech={st['CAGR_09_26']*100:5.2f}% | t={row['NW_t_vs_Control']:+5.2f}")
        return Lc, Lq, Lt, row

    # Record Control
    print('\n--- [0] Baseline Controls ---')
    eval_core3_pair('00. Core3 Control (50% QQQ Sharpe-Mom Top-2 + 50% Tech Mom Top-1) [FROZEN]',
                    '0. Control', ctrl_qqq_spec, ctrl_tech_spec)
    raw_qqq_spec = {'type': 'score', 'base_col': 'mom_12_1', 'score_col': 'mom_12_1'}
    eval_core3_pair('00b. Core1 Control (50% QQQ Raw 12-1 Mom Top-2 + 50% Tech Mom Top-1)',
                    '0. Control', raw_qqq_spec, ctrl_tech_spec)

    # =========================================================================
    # HYPOTHESIS A: Momentum Consistency / Frog in the Pan (Da, Gurun, Warachka 2014)
    # =========================================================================
    print('\n--- [A] Hypothesis A: Momentum Consistency / Frog in the Pan (FIP, Isolated) ---')
    # A1. Pre-registered Two-Stage Filter: Top-N Momentum Pool -> Pick Most Continuous (FIP_Smooth)
    # First test Sleeve Attribution for canonical Top-5 QQQ pool / Top-3 Tech pool:
    a_qqq_pool5 = {'type': 'pool_rerank', 'base_col': 'sharpe_mom_12_1', 'pool_n': 5, 'rerank_col': 'fip_smooth_12_1'}
    a_tech_pool3 = {'type': 'pool_rerank', 'base_col': 'mom_12_1', 'pool_n': 3, 'rerank_col': 'fip_smooth_12_1'}
    eval_core3_pair('A1a. FIP on QQQ Only (QQQ Sharpe Top-5 -> FIP Top-2; Tech Control)',
                    'A. FIP / Consistency', a_qqq_pool5, ctrl_tech_spec)
    eval_core3_pair('A1b. FIP on Tech Only (QQQ Control; Tech Mom Top-3 -> FIP Top-1)',
                    'A. FIP / Consistency', ctrl_qqq_spec, a_tech_pool3)
    eval_core3_pair('A1c. FIP on Both Sleeves (QQQ Top-5->FIP Top-2 + Tech Top-3->FIP Top-1)',
                    'A. FIP / Consistency', a_qqq_pool5, a_tech_pool3)

    # A2. Neighborhood Grid of Pool Sizes N for QQQ (N in {3, 4, 5, 6, 8, 10}) and M for Tech (M in {2, 3, 4, 5})
    for n_q, m_t in [(3, 2), (4, 2), (4, 3), (5, 2), (6, 3), (8, 4), (10, 5)]:
        qs = {'type': 'pool_rerank', 'base_col': 'sharpe_mom_12_1', 'pool_n': n_q, 'rerank_col': 'fip_smooth_12_1'}
        ts = {'type': 'pool_rerank', 'base_col': 'mom_12_1', 'pool_n': m_t, 'rerank_col': 'fip_smooth_12_1'}
        eval_core3_pair(f'A2. FIP Pool Grid: QQQ Top-{n_q}->FIP Top-2 + Tech Top-{m_t}->FIP Top-1',
                        'A. FIP Neighborhood', qs, ts)

    # A3. FIP on Raw 12-1 Momentum Pool (testing whether FIP works without vol scaling too)
    for n_q, m_t in [(4, 2), (5, 3), (6, 3)]:
        qs = {'type': 'pool_rerank', 'base_col': 'mom_12_1', 'pool_n': n_q, 'rerank_col': 'fip_smooth_12_1'}
        ts = {'type': 'pool_rerank', 'base_col': 'mom_12_1', 'pool_n': m_t, 'rerank_col': 'fip_smooth_12_1'}
        eval_core3_pair(f'A3. FIP on Raw Mom Pool: QQQ Raw Top-{n_q}->FIP Top-2 + Tech Top-{m_t}->FIP Top-1',
                        'A. FIP on Raw Mom', qs, ts)

    # A4. Zero-Parameter Continuous Multiplicative FIP Score & Non-Jump Momentum (removing top 5 jump days)
    qs_mult = {'type': 'score', 'base_col': 'sharpe_mom_12_1',
               'expr_fn': lambda d: d['sharpe_mom_12_1'] * (1.0 + d['fip_smooth_12_1'])}
    ts_mult = {'type': 'score', 'base_col': 'mom_12_1',
               'expr_fn': lambda d: d['mom_12_1'] * (1.0 + d['fip_smooth_12_1'])}
    eval_core3_pair('A4a. Zero-Param Multiplicative: Score = BaseMom * (1 + FIP_Smooth)',
                    'A. FIP Zero-Param', qs_mult, ts_mult)

    qs_nonjump = {'type': 'score', 'base_col': 'non_jump_mom_12_1',
                  'expr_fn': lambda d: d['non_jump_mom_12_1'] / d['vol_12_1']}
    ts_nonjump = {'type': 'score', 'base_col': 'non_jump_mom_12_1', 'score_col': 'non_jump_mom_12_1'}
    eval_core3_pair('A4b. Zero-Param Non-Jump Mom (12-1 Return Excluding 5 Biggest Jump Days)',
                    'A. FIP Zero-Param', qs_nonjump, ts_nonjump)

    # A5. Anti-Jump Veto on Rank #1 (only drop a winner if its 5 biggest days > 60% of 12-1 gain or FIP < 0)
    veto_jump = lambda r: (r['fip_smooth_12_1'] < 0.0) or (r['mom_12_1'] > 0 and (r['max_ret_5d_12_1'] / max(r['mom_12_1'], 0.01) > 0.65))
    qs_veto = {'type': 'veto', 'base_col': 'sharpe_mom_12_1', 'pool_n': 5, 'veto_fn': veto_jump}
    ts_veto = {'type': 'veto', 'base_col': 'mom_12_1', 'pool_n': 3, 'veto_fn': veto_jump}
    eval_core3_pair('A5. Anti-Jump Veto (Drop Winner Only If FIP<0 or Top5Days > 65% of Gain)',
                    'A. FIP Veto', qs_veto, ts_veto)

    # A6. Neighbor Definitions of Consistency: 6-1 FIP Smooth & Monthly Win-Rate (11 months)
    qs_fip6 = {'type': 'pool_rerank', 'base_col': 'sharpe_mom_12_1', 'pool_n': 5, 'rerank_col': 'fip_smooth_6_1'}
    ts_fip6 = {'type': 'pool_rerank', 'base_col': 'mom_12_1', 'pool_n': 3, 'rerank_col': 'fip_smooth_6_1'}
    eval_core3_pair('A6a. Neighbor Window: 6-1 FIP Smooth (QQQ Top-5 / Tech Top-3)',
                    'A. FIP Neighbors', qs_fip6, ts_fip6)

    qs_winm = {'type': 'pool_rerank', 'base_col': 'sharpe_mom_12_1', 'pool_n': 5, 'rerank_col': 'win_months_11'}
    ts_winm = {'type': 'pool_rerank', 'base_col': 'mom_12_1', 'pool_n': 3, 'rerank_col': 'win_months_11'}
    eval_core3_pair('A6b. Neighbor Definition: Monthly Win-Rate Across 11 Formation Months',
                    'A. FIP Neighbors', qs_winm, ts_winm)

    # A7. Rank Blend inside Top-10 Pool (w in {0.25, 0.50, 0.75, 1.00})
    for w_fip in (0.25, 0.50, 0.75, 1.00):
        qs_rb = {'type': 'rank_blend', 'base_col': 'sharpe_mom_12_1', 'sec_col': 'fip_smooth_12_1', 'pool_n': 10, 'w': w_fip}
        ts_rb = {'type': 'rank_blend', 'base_col': 'mom_12_1', 'sec_col': 'fip_smooth_12_1', 'pool_n': 10, 'w': w_fip}
        eval_core3_pair(f'A7. Rank Blend (Top-10 Pool): Rank(Mom) + {w_fip:.2f} * Rank(FIP)',
                        'A. FIP Rank Blend', qs_rb, ts_rb)

    # =========================================================================
    # HYPOTHESIS B: Residual Momentum (Blitz, Huij, Martens 2011, JEMP)
    # =========================================================================
    print('\n--- [B] Hypothesis B: Residual Momentum (Stripping Market / Sector Beta, Isolated) ---')
    # B1. Pure Replacement of Total-Return Momentum with Market/Sector-Hedged Residual Momentum
    b_qqq_sh = {'type': 'score', 'base_col': 'res_sharpe_qqq_12_1', 'score_col': 'res_sharpe_qqq_12_1'}
    b_qqq_ret = {'type': 'score', 'base_col': 'res_ret_qqq_12_1', 'score_col': 'res_ret_qqq_12_1'}
    b_tech_spy_ret = {'type': 'score', 'base_col': 'res_ret_spy_12_1', 'score_col': 'res_ret_spy_12_1'}
    b_tech_spy_sh = {'type': 'score', 'base_col': 'res_sharpe_spy_12_1', 'score_col': 'res_sharpe_spy_12_1'}
    b_tech_xlk_ret = {'type': 'score', 'base_col': 'res_ret_xlk_12_1', 'score_col': 'res_ret_xlk_12_1'}
    b_tech_xlk_sh = {'type': 'score', 'base_col': 'res_sharpe_xlk_12_1', 'score_col': 'res_sharpe_xlk_12_1'}
    b_qqq_2f_sh = {'type': 'score', 'base_col': 'res_sharpe_2f_12_1', 'score_col': 'res_sharpe_2f_12_1'}
    b_tech_2f_ret = {'type': 'score', 'base_col': 'res_ret_2f_12_1', 'score_col': 'res_ret_2f_12_1'}
    b_tech_2f_sh = {'type': 'score', 'base_col': 'res_sharpe_2f_12_1', 'score_col': 'res_sharpe_2f_12_1'}

    # Sleeve attribution first
    eval_core3_pair('B1a. Residual Mom on QQQ Only (QQQ ResSharpe vs QQQ; Tech Control)',
                    'B. Residual Momentum', b_qqq_sh, ctrl_tech_spec)
    eval_core3_pair('B1b. Residual Mom on Tech Only (QQQ Control; Tech ResRet vs XLK)',
                    'B. Residual Momentum', ctrl_qqq_spec, b_tech_xlk_ret)
    eval_core3_pair('B1c. Residual Mom on Tech Only (QQQ Control; Tech ResSharpe vs XLK)',
                    'B. Residual Momentum', ctrl_qqq_spec, b_tech_xlk_sh)
    eval_core3_pair('B1d. Residual Mom on Both: QQQ ResSharpe(QQQ) + Tech ResRet(XLK)',
                    'B. Residual Momentum', b_qqq_sh, b_tech_xlk_ret)
    eval_core3_pair('B1e. Residual Mom on Both: QQQ ResSharpe(QQQ) + Tech ResSharpe(XLK)',
                    'B. Residual Momentum', b_qqq_sh, b_tech_xlk_sh)
    eval_core3_pair('B1f. Residual Mom on Both: QQQ ResRet(QQQ) + Tech ResRet(XLK)',
                    'B. Residual Momentum', b_qqq_ret, b_tech_xlk_ret)
    eval_core3_pair('B1g. Residual Mom on Both: QQQ ResSharpe(QQQ) + Tech ResRet(SPY)',
                    'B. Residual Momentum', b_qqq_sh, b_tech_spy_ret)
    eval_core3_pair('B1h. 2-Factor Residual (SPY+XLK): QQQ ResSharpe(2F) + Tech ResRet(2F)',
                    'B. Residual Momentum', b_qqq_2f_sh, b_tech_2f_ret)
    eval_core3_pair('B1i. 2-Factor Residual (SPY+XLK): QQQ ResSharpe(2F) + Tech ResSharpe(2F)',
                    'B. Residual Momentum', b_qqq_2f_sh, b_tech_2f_sh)

    # B2. Blitz-Huij-Martens Standardized Sum of Daily Residuals (mean / std * sqrt(252))
    b_qqq_blitz = {'type': 'score', 'base_col': 'res_blitz_qqq_12_1', 'score_col': 'res_blitz_qqq_12_1'}
    b_tech_blitz = {'type': 'score', 'base_col': 'res_blitz_xlk_12_1', 'score_col': 'res_blitz_xlk_12_1'}
    eval_core3_pair('B2. Exact Blitz-Huij-Martens Standardized Residual Sum (QQQ + XLK)',
                    'B. Residual Momentum', b_qqq_blitz, b_tech_blitz)

    # B3. Two-Stage Pool: Top-N Raw/Sharpe Momentum -> Pick Highest Residual Momentum (Alpha Confirmation)
    for n_q, m_t in [(3, 2), (4, 2), (5, 3), (8, 4)]:
        qs = {'type': 'pool_rerank', 'base_col': 'sharpe_mom_12_1', 'pool_n': n_q, 'rerank_col': 'res_sharpe_qqq_12_1'}
        ts = {'type': 'pool_rerank', 'base_col': 'mom_12_1', 'pool_n': m_t, 'rerank_col': 'res_ret_xlk_12_1'}
        eval_core3_pair(f'B3. Top-N Pool -> Best Residual Mom (QQQ Top-{n_q}, Tech Top-{m_t})',
                        'B. Residual Pool Grid', qs, ts)

    # B4. Window Neighborhood Checks (6-1 Residual Mom and 18-1 Beta Estimation Window)
    b_qqq_6 = {'type': 'score', 'base_col': 'res_sharpe_qqq_6_1', 'score_col': 'res_sharpe_qqq_6_1'}
    b_tech_6 = {'type': 'score', 'base_col': 'res_ret_xlk_6_1', 'score_col': 'res_ret_xlk_6_1'}
    eval_core3_pair('B4a. Neighbor Window: 6-1 Residual Momentum (QQQ ResSharpe + Tech ResRet)',
                    'B. Residual Neighbors', b_qqq_6, b_tech_6)

    b_qqq_18 = {'type': 'score', 'base_col': 'res_sharpe_qqq_b18', 'score_col': 'res_sharpe_qqq_b18'}
    b_tech_18 = {'type': 'score', 'base_col': 'res_ret_xlk_b18', 'score_col': 'res_ret_xlk_b18'}
    eval_core3_pair('B4b. Neighbor Window: 18-1 Beta Estimation Applied to 12-1 Return',
                    'B. Residual Neighbors', b_qqq_18, b_tech_18)

    # =========================================================================
    # HYPOTHESIS C: Price + Fundamental / Earnings Momentum (Novy-Marx 2015 / PEAD)
    # =========================================================================
    print('\n--- [C] Hypothesis C: Price + Fundamental / Earnings Momentum (Strictly PIT, Isolated) ---')
    # C1. Individual Fundamental / PEAD Metrics Tested Inside Top-5 QQQ / Top-3 Tech Price Momentum Pool
    fund_metrics = [
        ('ear_latest', '3-Day Earnings Announcement Return (EAR, 8-K Item 2.02)'),
        ('ear_sum4', '4-Quarter Cumulative EAR'),
        ('rev_yoy_q', 'Quarterly Revenue YoY Growth'),
        ('rev_accel_q', 'Quarterly Revenue Growth Acceleration (Delta Rev YoY)'),
        ('eps_yoy_sym_q', 'Quarterly Diluted EPS Symmetric YoY Growth'),
        ('eps_accel_q', 'Quarterly Diluted EPS Growth Acceleration (Delta EPS YoY)'),
        ('eps_ttm_yoy_sym', 'TTM Diluted EPS Symmetric YoY Growth'),
        ('op_accel_comp', 'Operating Acceleration Composite (Rev + EPS YoY & Accel)'),
        ('pead_comp', 'PEAD Composite (EAR + 4Q EAR + Quarterly EPS YoY)'),
        ('fund_mom_comp', 'All-In Fundamental Momentum Composite (EAR + Rev + EPS)'),
    ]
    for fcol, flabel in fund_metrics:
        qs = {'type': 'pool_rerank', 'base_col': 'sharpe_mom_12_1', 'pool_n': 5, 'rerank_col': fcol}
        ts = {'type': 'pool_rerank', 'base_col': 'mom_12_1', 'pool_n': 3, 'rerank_col': fcol}
        eval_core3_pair(f'C1. Price Pool (QQQ Top-5 / Tech Top-3) -> {flabel}',
                        'C. Price + Fundamental Mom', qs, ts)

    # C2. Sleeve Attribution for Fundamental Momentum Composite (`fund_mom_comp` and `ear_latest`)
    c_qqq_fcomp = {'type': 'pool_rerank', 'base_col': 'sharpe_mom_12_1', 'pool_n': 5, 'rerank_col': 'fund_mom_comp'}
    c_tech_fcomp = {'type': 'pool_rerank', 'base_col': 'mom_12_1', 'pool_n': 3, 'rerank_col': 'fund_mom_comp'}
    eval_core3_pair('C2a. FundMom Composite on QQQ Only (QQQ Top-5->FundMom; Tech Control)',
                    'C. Sleeve Attribution', c_qqq_fcomp, ctrl_tech_spec)
    eval_core3_pair('C2b. FundMom Composite on Tech Only (QQQ Control; Tech Top-3->FundMom)',
                    'C. Sleeve Attribution', ctrl_qqq_spec, c_tech_fcomp)

    c_qqq_ear = {'type': 'pool_rerank', 'base_col': 'sharpe_mom_12_1', 'pool_n': 5, 'rerank_col': 'ear_latest'}
    c_tech_ear = {'type': 'pool_rerank', 'base_col': 'mom_12_1', 'pool_n': 3, 'rerank_col': 'ear_latest'}
    eval_core3_pair('C2c. EAR (8-K Drift) on QQQ Only (QQQ Top-5->EAR; Tech Control)',
                    'C. Sleeve Attribution', c_qqq_ear, ctrl_tech_spec)
    eval_core3_pair('C2d. EAR (8-K Drift) on Tech Only (QQQ Control; Tech Top-3->EAR)',
                    'C. Sleeve Attribution', ctrl_qqq_spec, c_tech_ear)

    # C3. Parameter Neighborhood Grid of Pool Sizes (N, M) for `fund_mom_comp` and `op_accel_comp`
    for n_q, m_t in [(3, 2), (4, 2), (4, 3), (6, 3), (8, 4), (10, 5)]:
        qs = {'type': 'pool_rerank', 'base_col': 'sharpe_mom_12_1', 'pool_n': n_q, 'rerank_col': 'fund_mom_comp'}
        ts = {'type': 'pool_rerank', 'base_col': 'mom_12_1', 'pool_n': m_t, 'rerank_col': 'fund_mom_comp'}
        eval_core3_pair(f'C3. FundMom Pool Grid: QQQ Top-{n_q}->FundMom + Tech Top-{m_t}->FundMom',
                        'C. FundMom Neighborhood', qs, ts)

    # C4. Fundamental Confirmation / Veto Filter (Keep Rank #1 unless EAR < 0 or Operating Momentum < Median)
    veto_neg_ear = lambda r: pd.notna(r['ear_latest']) and (float(r['ear_latest']) < -0.01)
    qs_v_ear = {'type': 'veto', 'base_col': 'sharpe_mom_12_1', 'pool_n': 5, 'veto_fn': veto_neg_ear}
    ts_v_ear = {'type': 'veto', 'base_col': 'mom_12_1', 'pool_n': 3, 'veto_fn': veto_neg_ear}
    eval_core3_pair('C4a. Earnings Veto: Drop Winner Only If Latest 8-K EAR < -1%',
                    'C. Fundamental Veto', qs_v_ear, ts_v_ear)

    veto_weak_fund = lambda r: pd.notna(r['fund_mom_comp']) and (float(r['fund_mom_comp']) < 0.40)
    qs_v_f = {'type': 'veto', 'base_col': 'sharpe_mom_12_1', 'pool_n': 5, 'veto_fn': veto_weak_fund}
    ts_v_f = {'type': 'veto', 'base_col': 'mom_12_1', 'pool_n': 3, 'veto_fn': veto_weak_fund}
    eval_core3_pair('C4b. Fundamental Veto: Drop Winner Only If FundMom Rank < 40th Pct',
                    'C. Fundamental Veto', qs_v_f, ts_v_f)

    # C5. Rank Blend inside Top-10 Pool (Rank(PriceMom) + w * Rank(FundMom))
    for w_f in (0.25, 0.50, 0.75, 1.00):
        qs_rb = {'type': 'rank_blend', 'base_col': 'sharpe_mom_12_1', 'sec_col': 'fund_mom_comp', 'pool_n': 10, 'w': w_f}
        ts_rb = {'type': 'rank_blend', 'base_col': 'mom_12_1', 'sec_col': 'fund_mom_comp', 'pool_n': 10, 'w': w_f}
        eval_core3_pair(f'C5. Rank Blend (Top-10 Pool): Rank(PriceMom) + {w_f:.2f} * Rank(FundMom)',
                        'C. FundMom Rank Blend', qs_rb, ts_rb)

    # =========================================================================
    # HYPOTHESIS D (2nd Tier): 52-Week-High Proximity (George & Hwang 2004)
    # =========================================================================
    print('\n--- [D] Hypothesis D (2nd Tier): 52-Week-High Proximity (Isolated) ---')
    for n_q, m_t in [(3, 2), (5, 3), (8, 4)]:
        qs = {'type': 'pool_rerank', 'base_col': 'sharpe_mom_12_1', 'pool_n': n_q, 'rerank_col': 'prox_52wh_t'}
        ts = {'type': 'pool_rerank', 'base_col': 'mom_12_1', 'pool_n': m_t, 'rerank_col': 'prox_52wh_t'}
        eval_core3_pair(f'D1. 52W-High Pool Grid: QQQ Top-{n_q}->52WH + Tech Top-{m_t}->52WH',
                        'D. 52W-High Proximity', qs, ts)

    qs_d_mult = {'type': 'score', 'base_col': 'sharpe_mom_12_1',
                 'expr_fn': lambda d: d['sharpe_mom_12_1'] * d['prox_52wh_t']}
    ts_d_mult = {'type': 'score', 'base_col': 'mom_12_1',
                 'expr_fn': lambda d: d['mom_12_1'] * d['prox_52wh_t']}
    eval_core3_pair('D2. Zero-Param Multiplicative: Score = BaseMom * (Close / High252)',
                    'D. 52W-High Proximity', qs_d_mult, ts_d_mult)

    df_master = pd.DataFrame(master_rows)
    df_master.to_csv(os.path.join(HERE, '01_all_selection_hypotheses_summary.csv'), index=False)

    # =========================================================================
    # 4. Single-Rank Diagnostic (Rank #1 vs Rank #2 vs Rank #3 Under Each Hypothesis)
    # =========================================================================
    print('\n--- [Diagnostic] Rank #1 vs Rank #2 vs Rank #3 Monotonicity Audit ---')
    rank_diag_specs = [
        ('0. Control (QQQ Sharpe-Mom / Tech Raw Mom)', ctrl_qqq_spec, ctrl_tech_spec),
        ('A1. FIP Pool (QQQ Top-5->FIP / Tech Top-3->FIP)', a_qqq_pool5, a_tech_pool3),
        ('A4a. FIP Multiplicative (BaseMom * (1+FIP))', qs_mult, ts_mult),
        ('A5. Anti-Jump Veto', qs_veto, ts_veto),
        ('B1. Residual Momentum (QQQ ResSharpe / Tech ResRet XLK)', b_qqq_sh, b_tech_xlk_ret),
        ('B1e. Residual Sharpe Both (QQQ ResSharpe / Tech ResSharpe XLK)', b_qqq_sh, b_tech_xlk_sh),
        ('C1. Price Pool -> FundMom Composite (Top-5 / Top-3)', c_qqq_fcomp, c_tech_fcomp),
        ('C4b. Fundamental Veto (Drop if FundMom < 40th Pct)', qs_v_f, ts_v_f),
        ('D1. 52W-High Pool (Top-5 / Top-3)',
         {'type': 'pool_rerank', 'base_col': 'sharpe_mom_12_1', 'pool_n': 5, 'rerank_col': 'prox_52wh_t'},
         {'type': 'pool_rerank', 'base_col': 'mom_12_1', 'pool_n': 3, 'rerank_col': 'prox_52wh_t'}),
    ]
    rk_rows = []
    for label, qs, ts in rank_diag_specs:
        row_rk = {'Hypothesis_Method': label}
        for rk in (1, 2, 3):
            Lq_rk = run_sleeve_backtest(df_qqq, qs, k=1, target_rank=rk, linear_cost=True)
            sq_rk = summarize_series('', '', Lq_rk['net'], rf_monthly)
            row_rk[f'QQQ_Rank{rk}_CAGR'] = sq_rk['CAGR_09_26']
            row_rk[f'QQQ_Rank{rk}_Sharpe'] = sq_rk['Sharpe_m']
            row_rk[f'QQQ_Rank{rk}_MaxDD'] = sq_rk['Monthly_MaxDD']
        for rk in (1, 2, 3):
            Lt_rk = run_sleeve_backtest(df_tech, ts, k=1, target_rank=rk, linear_cost=False)
            st_rk = summarize_series('', '', Lt_rk['net'], rf_monthly)
            row_rk[f'Tech_Rank{rk}_CAGR'] = st_rk['CAGR_09_26']
            row_rk[f'Tech_Rank{rk}_Sharpe'] = st_rk['Sharpe_m']
            row_rk[f'Tech_Rank{rk}_MaxDD'] = st_rk['Monthly_MaxDD']
        rk_rows.append(row_rk)
        print(f"  {label:<58} | QQQ R1/R2/R3: {row_rk['QQQ_Rank1_CAGR']*100:5.1f}% / {row_rk['QQQ_Rank2_CAGR']*100:5.1f}% / {row_rk['QQQ_Rank3_CAGR']*100:5.1f}% | "
              f"Tech R1/R2/R3: {row_rk['Tech_Rank1_CAGR']*100:5.1f}% / {row_rk['Tech_Rank2_CAGR']*100:5.1f}% / {row_rk['Tech_Rank3_CAGR']*100:5.1f}%")

    df_rk = pd.DataFrame(rk_rows)
    df_rk.to_csv(os.path.join(HERE, '02_rank1_vs_rank2_diagnostic.csv'), index=False)

    # =========================================================================
    # 5. Leave-One-Winner-Out & Outlier Month Removal Audit Across Hypotheses
    # =========================================================================
    print('\n--- [Check 5] Leave-One-Winner-Out & Best-5-Months Removal Across Hypotheses ---')
    rep_specs = [
        ('0. Control Core3 [FROZEN]', ctrl_qqq_spec, ctrl_tech_spec),
        ('A1c. FIP Pool (QQQ Top-5->FIP, Tech Top-3->FIP)', a_qqq_pool5, a_tech_pool3),
        ('A4a. FIP Multiplicative (BaseMom * (1+FIP))', qs_mult, ts_mult),
        ('A5. Anti-Jump Veto', qs_veto, ts_veto),
        ('B1d. Residual Mom (QQQ ResSharpe + Tech ResRet XLK)', b_qqq_sh, b_tech_xlk_ret),
        ('B3. Residual Pool (QQQ Top-5->Res, Tech Top-3->Res)',
         {'type': 'pool_rerank', 'base_col': 'sharpe_mom_12_1', 'pool_n': 5, 'rerank_col': 'res_sharpe_qqq_12_1'},
         {'type': 'pool_rerank', 'base_col': 'mom_12_1', 'pool_n': 3, 'rerank_col': 'res_ret_xlk_12_1'}),
        ('C1. FundMom Composite Pool (QQQ Top-5, Tech Top-3)', c_qqq_fcomp, c_tech_fcomp),
        ('C4b. Fundamental Veto (FundMom >= 40th Pct)', qs_v_f, ts_v_f),
        ('D1. 52W-High Pool (QQQ Top-5, Tech Top-3)',
         {'type': 'pool_rerank', 'base_col': 'sharpe_mom_12_1', 'pool_n': 5, 'rerank_col': 'prox_52wh_t'},
         {'type': 'pool_rerank', 'base_col': 'mom_12_1', 'pool_n': 3, 'rerank_col': 'prox_52wh_t'}),
    ]
    super_winners = ['NVDA', 'SNDK', 'PLTR', 'TSLA', 'MU', 'WDC', 'AMD']
    loo_rows = []
    for label, qs, ts in rep_specs:
        Lc_base = combine_core3(
            run_sleeve_backtest(df_qqq, qs, k=2, linear_cost=True),
            run_sleeve_backtest(df_tech, ts, k=1, linear_cost=False)
        )
        r_b = Lc_base['net']
        s_b = summarize_series(label, '', r_b, rf_monthly)
        # Zero out top 5 best months
        r_no5 = r_b.copy()
        top5_m = r_no5.nlargest(5).index
        r_no5.loc[top5_m] = 0.0
        cagr_no5 = float((np.prod(1.0 + r_no5)) ** (12.0 / len(r_no5)) - 1.0)

        row_l = {
            'Strategy': label,
            'Full_CAGR': s_b['CAGR_09_26'],
            'Drop_Best_5_Months_CAGR': cagr_no5,
        }
        for sw in super_winners:
            Lq_sw = run_sleeve_backtest(df_qqq, qs, k=2, linear_cost=True, exclude_tickers=[sw])
            Lt_sw = run_sleeve_backtest(df_tech, ts, k=1, linear_cost=False, exclude_tickers=[sw])
            Lc_sw = combine_core3(Lq_sw, Lt_sw)
            row_l[f'Ban_{sw}_CAGR'] = float((np.prod(1.0 + Lc_sw['net'])) ** (12.0 / len(Lc_sw)) - 1.0)
        # Simultaneous ban of top 3 winners (NVDA + SNDK + PLTR)
        Lq_3 = run_sleeve_backtest(df_qqq, qs, k=2, linear_cost=True, exclude_tickers=['NVDA', 'SNDK', 'PLTR'])
        Lt_3 = run_sleeve_backtest(df_tech, ts, k=1, linear_cost=False, exclude_tickers=['NVDA', 'SNDK', 'PLTR'])
        Lc_3 = combine_core3(Lq_3, Lt_3)
        row_l['Ban_NVDA_SNDK_PLTR_CAGR'] = float((np.prod(1.0 + Lc_3['net'])) ** (12.0 / len(Lc_3)) - 1.0)
        loo_rows.append(row_l)

    df_loo = pd.DataFrame(loo_rows)
    df_loo.to_csv(os.path.join(HERE, '03_leave_one_winner_out.csv'), index=False)

    # =========================================================================
    # 6. Second-Vendor (Tiingo-First) End-to-End Replication Across Hypotheses
    # =========================================================================
    print('\n--- [Check 6] Second-Vendor (Tiingo-First) Replication Across Hypotheses ---')
    vendor_rows = []
    for label, qs, ts in rep_specs:
        Lc_p = combine_core3(
            run_sleeve_backtest(df_qqq, qs, k=2, linear_cost=True),
            run_sleeve_backtest(df_tech, ts, k=1, linear_cost=False)
        )
        Lc_t = combine_core3(
            run_sleeve_backtest(df_qqq_t, qs, k=2, linear_cost=True),
            run_sleeve_backtest(df_tech_t, ts, k=1, linear_cost=False)
        )
        sp = summarize_series(label, '', Lc_p['net'], rf_monthly)
        st = summarize_series(label, '', Lc_t['net'], rf_monthly)
        corr_pt = float(Lc_p['net'].corr(Lc_t['net']))
        # Exact pick match rate across 213 months
        q_match = float((Lc_p['qqq_picks'] == Lc_t['qqq_picks']).mean())
        t_match = float((Lc_p['tech_picks'] == Lc_t['tech_picks']).mean())
        vendor_rows.append({
            'Strategy': label,
            'Primary_CAGR': sp['CAGR_09_26'],
            'Tiingo_First_CAGR': st['CAGR_09_26'],
            'CAGR_Diff_bp': (st['CAGR_09_26'] - sp['CAGR_09_26']) * 1e4,
            'Primary_Sharpe': sp['Sharpe_m'],
            'Tiingo_First_Sharpe': st['Sharpe_m'],
            'Primary_Monthly_MaxDD': sp['Monthly_MaxDD'],
            'Tiingo_First_Monthly_MaxDD': st['Monthly_MaxDD'],
            'Monthly_Return_Corr': corr_pt,
            'QQQ_Exact_Pick_Match': q_match,
            'Tech_Exact_Pick_Match': t_match,
        })
        print(f"  {label:<52} | Primary={sp['CAGR_09_26']*100:6.2f}% vs Tiingo={st['CAGR_09_26']*100:6.2f}% (corr={corr_pt:.4f})")

    df_vend = pd.DataFrame(vendor_rows)
    df_vend.to_csv(os.path.join(HERE, '04_second_vendor_replication.csv'), index=False)

    # =========================================================================
    # 7. Cumulative Multiple-Testing Deflated Sharpe Ratio (DSR) Audit
    # =========================================================================
    print('\n--- [Check 7] Cumulative Multiple-Testing Deflated Sharpe Ratio (DSR) ---')
    repo_trials_df = pd.read_csv(os.path.join(QQQ_DIR, 'm_repo_trials.csv'))
    n_prev = 644  # 481 repo + 39 A/B/C + 59 Core3 audit + 65 tech brakes
    n_this = len(all_monthly_series) - 1
    n_total = n_prev + n_this

    new_srs = [s.mean() / s.std(ddof=1) for s in all_monthly_series.values() if s.std(ddof=1) > 0]
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
    rf_al = rf_monthly.reindex(r_ctrl.index).ffill().fillna(0.0)
    for label, qs, ts in rep_specs:
        Lc_p = combine_core3(
            run_sleeve_backtest(df_qqq, qs, k=2, linear_cost=True),
            run_sleeve_backtest(df_tech, ts, k=1, linear_cost=False)
        )
        rm = Lc_p['net']
        ex = (rm - rf_al).dropna().values
        dsr_ex, sr_ann, sr0_ann = dsr_calc(ex, n_total, sr_var)
        # Also DSR under isolated hypothesis family trial count (N = n_this)
        dsr_iso, _, sr0_iso = dsr_calc(ex, n_this, sr_var)
        diff = (rm - r_ctrl).dropna().values
        if np.std(diff, ddof=1) > 1e-7:
            ir_ann = float(diff.mean() / np.std(diff, ddof=1) * np.sqrt(12.0))
        else:
            ir_ann = 0.0
        dsr_rows.append({
            'Strategy': label,
            'N_Cumulative_Trials': n_total,
            'N_Selection_Trials_This_Round': n_this,
            'Excess_Sharpe_Ann': sr_ann,
            'Null_Max_SR0_Cumulative': sr0_ann,
            'DSR_Cumulative_All_Trials': dsr_ex,
            'DSR_Selection_Round_Only': dsr_iso,
            'Active_IR_vs_Control': ir_ann,
        })
    df_dsr = pd.DataFrame(dsr_rows)
    df_dsr.to_csv(os.path.join(HERE, '05_multiple_testing_dsr.csv'), index=False)

    # =========================================================================
    # 8. 2D Parameter Sensitivity Grid for A5 Anti-Jump Veto
    # =========================================================================
    print('\n--- [Check 8] 2D Parameter Sensitivity Grid for A5 Anti-Jump Veto ---')
    a5_grid_rows = []
    for fip_th in [-0.02, 0.0, 0.02, None]:
        for jump_th in [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, None]:
            if fip_th is None and jump_th is None:
                continue
            def make_veto(ft, jt):
                def fn(r):
                    c1 = (r['fip_smooth_12_1'] < ft) if ft is not None else False
                    c2 = (r['mom_12_1'] > 0 and (r['max_ret_5d_12_1'] / max(r['mom_12_1'], 0.01) > jt)) if jt is not None else False
                    return c1 or c2
                return fn
            vf = make_veto(fip_th, jump_th)
            qs_g = {'type': 'veto', 'base_col': 'sharpe_mom_12_1', 'pool_n': 5, 'veto_fn': vf}
            ts_g = {'type': 'veto', 'base_col': 'mom_12_1', 'pool_n': 3, 'veto_fn': vf}
            Lq_g = run_sleeve_backtest(df_qqq, qs_g, k=2, linear_cost=True)
            Lt_g = run_sleeve_backtest(df_tech, ts_g, k=1, linear_cost=False)
            Lc_g = combine_core3(Lq_g, Lt_g)
            sg = summarize_series('', '', Lc_g['net'], rf_monthly, Lc_g['turnover'], ref_r=r_ctrl)
            sq_g = summarize_series('', '', Lq_g['net'], rf_monthly)
            st_g = summarize_series('', '', Lt_g['net'], rf_monthly)
            a5_grid_rows.append({
                'FIP_Threshold': str(fip_th),
                'Jump5d_Share_Threshold': str(jump_th),
                'Core3_CAGR_09_26': sg['CAGR_09_26'],
                'Sharpe_m': sg['Sharpe_m'],
                'Monthly_MaxDD': sg['Monthly_MaxDD'],
                'QQQ_Sleeve_CAGR': sq_g['CAGR_09_26'],
                'Tech_Sleeve_CAGR': st_g['CAGR_09_26'],
                'CAGR_2009_2018': sg['CAGR_2009_2018'],
                'CAGR_2019_2026': sg['CAGR_2019_2026'],
                'NW_t_vs_Control': sg['NW_t_vs_Control'],
                'Beats_Control': bool(sg['CAGR_09_26'] > master_rows[0]['CAGR_09_26']),
            })
    df_a5g = pd.DataFrame(a5_grid_rows)
    df_a5g.to_csv(os.path.join(HERE, '06_a5_veto_sensitivity_grid.csv'), index=False)
    print(f'=== COMPLETED ALL {n_this} STOCK-SELECTION HYPOTHESIS TESTS (GRAND TOTAL TRIALS = {n_total}) ===')


if __name__ == '__main__':
    main()
