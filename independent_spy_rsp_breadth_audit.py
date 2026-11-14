#!/usr/bin/env python3
"""
Independent Clean-Room Audit: SPY/RSP Leadership Concentration & Market Breadth Signals
========================================================================================
Executes all 5 adversarial verification experiments requested in the Second-Round Audit:
  1. Reconcile the 22-month vs 15-month/14-month ledger discrepancy by exporting the exact
     Python-computed 22-month ledger (`spy_rsp_z12_ma50_22m_ledger.csv`), showing why the
     script reported 15 months / 6 crashes (`2011-09` true `rsp_dev50 = -3.58% > -4%`, and
     `2018-03` `-15.65%` was triggered rather than `2018-10`), while confirming the auditor's
     core critique that the `-4%` filter loses `2020-03 (-45.00%)` crash protection.
  2. Single-Factor Decomposition & Conditional Incremental Information Test:
     Compare `RSP < MA50` alone, `SPY/RSP Z > 1.2` alone, and their interaction `SPY/RSP Z > 1.2 & RSP < MA50`,
     plus test whether `SPY/RSP Z > 1.2` adds statistically significant crash discrimination
     INSIDE the `RSP < MA50` sub-sample (controlling for RSP's own trend).
  3. Zero-Line Cliff & Boundary Stress Test (without re-selecting parameters):
     Test `RSP_dev50 < +0.5%, 0.0%, -0.25%, -0.50%, -1.00%`, moving average windows
     `MA40, MA45, MA50, MA55, MA60`, trend windows `504d, 756d, 1008d`, and signal timing
     shifts (`t-1` day, `t` close, `t+1` day delay).
  4. Multi-Crisis Leave-Out & Cluster-Collapsed Independence Audit:
     Year-by-year net log-wealth attribution (after 10bp turnover costs), leaving out
     `2018 & 2020`, `2011 & 2015-16`, and ALL crisis years (`2011, 2015-16, 2018, 2020, 2025`),
     plus episode-level (first-trigger entry month only) Fisher exact test.
  5. Independent Market & True Point-in-Time (PIT) S&P 500 Constituent Breadth Migration:
     Using true PIT S&P 500 constituent monthly breadth (`% of S&P 500 stocks with 1M return > 0`,
     `% with 12-1 momentum > 0`, PIT Advance-Decline Line, Sector-ETF `% > MA50`, and `QQQ / QQQE`).
"""

import os
import json
import numpy as np
import pandas as pd
from scipy.stats import fisher_exact, mannwhitneyu, spearmanr, beta
import outputs.remediation_full_audit_20261104.run_full_8point_remediation_audit as r8
import independent_v4_symmetric_sharpe_top2_audit as v4_eng

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE_DIR, "outputs", "v4_symmetric_sharpe_top2_20261113")
os.makedirs(OUT_DIR, exist_ok=True)

COST_BP = 0.0010


def rolling_log_trend_z(s: pd.Series, w: int = 756) -> pd.Series:
    y = np.log(s.values.astype(float))
    n = len(y)
    z = np.full(n, np.nan)
    x = np.arange(w, dtype=float)
    xm = x.mean()
    xss = np.sum((x - xm) ** 2)
    for i in range(w - 1, n):
        yi = y[i - w + 1 : i + 1]
        if np.isnan(yi).any():
            continue
        ym = yi.mean()
        b = np.sum((x - xm) * (yi - ym)) / xss
        a = ym - b * xm
        res = yi - (a + b * x)
        sd = np.std(res, ddof=2)
        if sd > 1e-12:
            z[i] = res[-1] / sd
    return pd.Series(z, index=s.index)


def clopper_pearson_upper(k: int, n: int, alpha: float = 0.05) -> float:
    """Two-sided (1-alpha) Clopper-Pearson exact upper confidence bound (alpha/2 in upper tail)."""
    if k >= n:
        return 1.0
    return float(beta.ppf(1.0 - alpha / 2.0, k + 1, n - k))


def main():
    etf_list = [
        "QQQ", "SPY", "RSP", "QQQE", "QTEC", "TQQQ", "QLD", "SGOV", "BIL",
        "XLK", "XLF", "XLV", "XLE", "XLI", "XLY", "XLP", "XLU", "XLB"
    ]
    dfs = {s: r8.load_tiingo_etf_df(s) for s in etf_list}
    cal = dfs["QQQ"].index.sort_values()
    reg_map = v4_eng.reg_map
    months_214 = v4_eng.months_214

    c_qqq = dfs["QQQ"]["c"].reindex(cal).ffill()
    c_spy = dfs["SPY"]["c"].reindex(cal).ffill()
    c_rsp = dfs["RSP"]["c"].reindex(cal).ffill()

    qqqe_l = dfs["QQQE"]["c"]
    qtec_l = dfs["QTEC"]["c"].reindex(cal).ffill()
    launch_qqqe = pd.Timestamp("2012-03-21")
    scale_qqqe = float(qqqe_l.at[launch_qqqe] / qtec_l.at[launch_qqqe])
    c_qqqe = pd.concat([qtec_l.loc[qtec_l.index < launch_qqqe] * scale_qqqe, qqqe_l]).reindex(cal).ffill()

    r_sr = c_spy / c_rsp
    r_qqe = c_qqq / c_qqqe

    # Precompute trend Z-scores and moving average deviations across windows
    sr_tz_504 = rolling_log_trend_z(r_sr, 504)
    sr_tz_756 = rolling_log_trend_z(r_sr, 756)
    sr_tz_1008 = rolling_log_trend_z(r_sr, 1008)
    sr_dev200 = (r_sr / r_sr.rolling(200).mean() - 1.0) * 100.0

    qqe_tz_756 = rolling_log_trend_z(r_qqe, 756)
    qqe_dev200 = (r_qqe / r_qqe.rolling(200).mean() - 1.0) * 100.0

    rsp_dev = {
        w: (c_rsp / c_rsp.rolling(w).mean() - 1.0) * 100.0
        for w in [40, 45, 50, 55, 60, 100, 200]
    }
    qqq_dev50 = (c_qqq / c_qqq.rolling(50).mean() - 1.0) * 100.0
    qqqe_dev50 = (c_qqqe / c_qqqe.rolling(50).mean() - 1.0) * 100.0

    # 9 GICS Sector ETFs daily % > MA50 and daily Sector A/D line
    sec_etfs = ["XLK", "XLF", "XLV", "XLE", "XLI", "XLY", "XLP", "XLU", "XLB"]
    sec_c_df = pd.DataFrame({s: dfs[s]["c"].reindex(cal).ffill() for s in sec_etfs})
    sec_ma50_df = sec_c_df.rolling(50).mean()
    sec_pct_ma50 = (sec_c_df > sec_ma50_df).mean(axis=1) * 100.0

    # =========================================================================
    # Construct True Point-in-Time (PIT) S&P 500 & Nasdaq-100 Constituent Breadth
    # from v4_eng.p_spx and v4_eng.p_ndx
    # =========================================================================
    p_spx = v4_eng.p_spx
    p_ndx = v4_eng.p_ndx

    sp_pit_adv1m = {}
    sp_pit_mom_pos = {}
    sp_pit_net_ad = {}
    ndx_pit_adv1m = {}

    for t, g in p_spx.groupby("t"):
        v1 = g["ret_1m"].dropna()
        vm = g["mom"].dropna()
        sp_pit_adv1m[t] = float((v1 > 0).mean() * 100.0) if len(v1) > 0 else np.nan
        sp_pit_net_ad[t] = float(((v1 > 0).mean() - (v1 < 0).mean())) if len(v1) > 0 else 0.0
        sp_pit_mom_pos[t] = float((vm > 0).mean() * 100.0) if len(vm) > 0 else np.nan

    for t, g in p_ndx.groupby("t"):
        v1 = g["ret_1m"].dropna()
        ndx_pit_adv1m[t] = float((v1 > 0).mean() * 100.0) if len(v1) > 0 else np.nan

    # Cumulative monthly PIT S&P 500 Advance-Decline Line & its 3-month MA
    ad_s = pd.Series(sp_pit_net_ad).sort_index().cumsum()
    ad_ma3 = ad_s.rolling(3).mean()
    sp_ad_below_ma3 = (ad_s < ad_ma3).to_dict()

    # =========================================================================
    # Build Monthly Dataset (2011-01 .. 2026-10, 190 Months, SEP=ON 156 Months)
    # =========================================================================
    m_rows = []
    for t in months_214:
        hold_ym = (t + pd.offsets.MonthBegin(1)).strftime("%Y-%m")
        if hold_ym < "2011-01":
            continue
        sep_on = bool(reg_map[t]["sep_on"])
        t_pos = cal.searchsorted(t, side="right") - 1
        t_tr = cal[t_pos]
        t_minus1 = cal[max(0, t_pos - 1)]
        t_plus1 = cal[min(len(cal) - 1, t_pos + 1)]

        d0_idx = cal.searchsorted(t, side="right")
        d0 = cal[d0_idx] if d0_idx < len(cal) else cal[-1]
        d0_plus1 = cal[min(len(cal) - 1, d0_idx + 1)]

        if t == pd.Timestamp("2026-09-30"):
            d1 = pd.Timestamp("2026-10-30")
            m_days = cal[(cal >= d0) & (cal <= d1)]
            p_col = "c"
        else:
            t_next = t + pd.offsets.MonthEnd(1)
            d1_idx = cal.searchsorted(t_next, side="right")
            d1 = cal[d1_idx] if d1_idx < len(cal) else cal[-1]
            m_days = cal[(cal >= d0) & (cal < d1)]
            p_col = "o"

        df_ca = dfs["SGOV"] if d0 >= pd.Timestamp("2020-06-01") else dfs["BIL"]
        r_tq = float(dfs["TQQQ"].at[d1, p_col] / dfs["TQQQ"].at[d0, "o"] - 1.0)
        r_qq = float(dfs["QQQ"].at[d1, p_col] / dfs["QQQ"].at[d0, "o"] - 1.0)
        r_ca = float(df_ca.at[d1, p_col] / df_ca.at[d0, "o"] - 1.0)

        # 1-day delayed execution return (signal observed at d0 close = t_plus1, executed at d0_plus1 open)
        r_tq_d1 = float(dfs["TQQQ"].at[d1, p_col] / dfs["TQQQ"].at[d0_plus1, "o"] - 1.0)
        r_qq_d1 = float(dfs["QQQ"].at[d1, p_col] / dfs["QQQ"].at[d0_plus1, "o"] - 1.0)
        r_tq_firstday = float(dfs["TQQQ"].at[d0_plus1, "o"] / dfs["TQQQ"].at[d0, "o"] - 1.0)
        r_qq_firstday = float(dfs["QQQ"].at[d0_plus1, "o"] / dfs["QQQ"].at[d0, "o"] - 1.0)

        m_rows.append({
            "t": t,
            "t_tr_str": t_tr.strftime("%Y-%m-%d"),
            "ym": hold_ym,
            "sep_on": sep_on,
            "r_tq": r_tq,
            "r_qq": r_qq,
            "r_ca": r_ca,
            "r_tq_d1": r_tq_d1,
            "r_qq_d1": r_qq_d1,
            "r_tq_firstday": r_tq_firstday,
            "r_qq_firstday": r_qq_firstday,
            "rf_m": float(reg_map[t]["rf_m"]),
            "d0": d0,
            "d0_plus1": d0_plus1,
            "d1": d1,
            "m_days": m_days,
            "sr_tz504": float(sr_tz_504.at[t_tr]),
            "sr_tz756": float(sr_tz_756.at[t_tr]),
            "sr_tz1008": float(sr_tz_1008.at[t_tr]),
            "sr_dev200": float(sr_dev200.at[t_tr]),
            "qqe_tz756": float(qqe_tz_756.at[t_tr]),
            "qqe_dev200": float(qqe_dev200.at[t_tr]),
            "rsp_dev40": float(rsp_dev[40].at[t_tr]),
            "rsp_dev45": float(rsp_dev[45].at[t_tr]),
            "rsp_dev50": float(rsp_dev[50].at[t_tr]),
            "rsp_dev55": float(rsp_dev[55].at[t_tr]),
            "rsp_dev60": float(rsp_dev[60].at[t_tr]),
            "rsp_dev100": float(rsp_dev[100].at[t_tr]),
            "rsp_dev200": float(rsp_dev[200].at[t_tr]),
            "qqq_dev50": float(qqq_dev50.at[t_tr]),
            "qqqe_dev50": float(qqqe_dev50.at[t_tr]),
            # Signal at t-1 trading day
            "sr_tz756_tm1": float(sr_tz_756.at[t_minus1]),
            "rsp_dev50_tm1": float(rsp_dev[50].at[t_minus1]),
            # Signal at t+1 trading day (d0 close)
            "sr_tz756_tp1": float(sr_tz_756.at[t_plus1]),
            "rsp_dev50_tp1": float(rsp_dev[50].at[t_plus1]),
            # True PIT Constituent Breadth & Sector Breadth
            "sp_pit_adv1m": sp_pit_adv1m.get(t, np.nan),
            "sp_pit_mom_pos": sp_pit_mom_pos.get(t, np.nan),
            "sp_ad_below_ma3": bool(sp_ad_below_ma3.get(t, False)),
            "ndx_pit_adv1m": ndx_pit_adv1m.get(t, np.nan),
            "sec_pct_ma50": float(sec_pct_ma50.at[t_tr]),
        })

    df = pd.DataFrame(m_rows)
    on = df[df["sep_on"]].copy().reset_index(drop=True)
    on["crash15"] = (on["r_tq"] <= -0.15).astype(int)

    # =========================================================================
    # EXPERIMENT 1: Reconcile the 22-Month vs 15-Month / 14-Month Ledger Contradiction
    # =========================================================================
    print("==========================================================================================")
    print("EXPERIMENT 1: RECONCILING THE 22-MONTH LEDGER & 15 vs 14 MONTH DISCREPANCY")
    print("==========================================================================================")
    c13_mask = (on["sr_tz756"] > 1.2) & (on["rsp_dev50"] < 0.0)
    c13_df = on[c13_mask].copy().reset_index(drop=True)
    c13_df["saved_pct"] = (c13_df["r_qq"] - c13_df["r_tq"]) * 100.0
    c13_df["log_wealth_diff_pct"] = (np.log(1.0 + c13_df["r_qq"]) - np.log(1.0 + c13_df["r_tq"])) * 100.0
    c13_df["in_noWash_gt_neg4"] = c13_df["rsp_dev50"] > -4.0
    c13_df["in_cliff_0_to_neg05"] = c13_df["rsp_dev50"] >= -0.5

    export_cols = [
        "ym", "t_tr_str", "sr_tz756", "sr_dev200", "rsp_dev50", "qqq_dev50",
        "sp_pit_adv1m", "r_tq", "r_qq", "saved_pct", "log_wealth_diff_pct",
        "crash15", "in_noWash_gt_neg4", "in_cliff_0_to_neg05"
    ]
    c13_export = c13_df[export_cols].copy()
    c13_export["r_tq"] = (c13_export["r_tq"] * 100.0).round(2)
    c13_export["r_qq"] = (c13_export["r_qq"] * 100.0).round(2)
    c13_export["saved_pct"] = c13_export["saved_pct"].round(2)
    c13_export["log_wealth_diff_pct"] = c13_export["log_wealth_diff_pct"].round(2)
    c13_export["sr_tz756"] = c13_export["sr_tz756"].round(4)
    c13_export["sr_dev200"] = c13_export["sr_dev200"].round(4)
    c13_export["rsp_dev50"] = c13_export["rsp_dev50"].round(4)
    c13_export["qqq_dev50"] = c13_export["qqq_dev50"].round(4)
    c13_export["sp_pit_adv1m"] = c13_export["sp_pit_adv1m"].round(2)
    c13_export.to_csv(os.path.join(OUT_DIR, "spy_rsp_z12_ma50_22m_ledger.csv"), index=False)

    print(c13_export.to_string(index=False))
    n_nowash = int(c13_df["in_noWash_gt_neg4"].sum())
    c_nowash = int(c13_df[c13_df["in_noWash_gt_neg4"]]["crash15"].sum())
    n_wash = int((~c13_df["in_noWash_gt_neg4"]).sum())
    c_wash = int(c13_df[~c13_df["in_noWash_gt_neg4"]]["crash15"].sum())
    print(f"\n  [Exact Count in True Python Ledger]:")
    print(f"    Total Triggered (Z > 1.2 & RSP < MA50): {len(c13_df)} months, {int(c13_df['crash15'].sum())} crashes")
    print(f"    Excluded by RSP_dev50 <= -4.0%        : {n_wash} months ({', '.join(c13_df[~c13_df['in_noWash_gt_neg4']]['ym'].tolist())}), {c_wash} crash (2020-03: -45.00%)")
    print(f"    Remaining (-4.0% < RSP_dev50 < 0.0%)  : {n_nowash} months, {c_nowash} crashes ({', '.join(c13_df[c13_df['in_noWash_gt_neg4'] & (c13_df['crash15']==1)]['ym'].tolist())})")

    # Also check Clopper-Pearson on SPY/RSP <= MA200 (strict 0.0% theoretical boundary vs +0.20% quintile boundary)
    le0 = on[on["sr_dev200"] <= 0.0]
    le020 = on[on["sr_dev200"] <= 0.20]
    print(f"\n  [Clopper-Pearson Audit of 'Low-Risk State']:")
    print(f"    Post-hoc Q1+Q2 boundary (SPY/RSP_dev200 <= +0.20%): {int(le020['crash15'].sum())}/{len(le020)} crashes | 95% 2-sided CP Upper Bound = {clopper_pearson_upper(int(le020['crash15'].sum()), len(le020))*100:.2f}%")
    print(f"    Prior theoretical boundary (SPY/RSP <= MA200, 0.0%): {int(le0['crash15'].sum())}/{len(le0)} crashes | 95% 2-sided CP Upper Bound = {clopper_pearson_upper(int(le0['crash15'].sum()), len(le0))*100:.2f}%")

    # =========================================================================
    # Open-Executed Daily NAV Backtest Helper
    # =========================================================================
    def run_bt(cond_fn, delay_1d=False):
        prev_state = None
        W_pre = 1.0
        pts_nav = {}
        rets = []
        for _, r in df.iterrows():
            if not r["sep_on"]:
                state = ("CASH", 0.0)
                gross = r["r_ca"]
            else:
                trig = bool(cond_fn(r))
                w_tq = 0.0 if trig else 1.0
                state = ("ON", w_tq)
                if not delay_1d:
                    gross = w_tq * r["r_tq"] + (1.0 - w_tq) * r["r_qq"]
                else:
                    prev_w = prev_state[1] if (prev_state is not None and prev_state[0] == "ON") else 1.0
                    g_day1 = prev_w * r["r_tq_firstday"] + (1.0 - prev_w) * r["r_qq_firstday"]
                    g_rest = w_tq * r["r_tq_d1"] + (1.0 - w_tq) * r["r_qq_d1"]
                    gross = (1.0 + g_day1) * (1.0 + g_rest) - 1.0

            if prev_state is None:
                to = 1.0
            elif prev_state[0] != state[0]:
                to = 2.0
            else:
                to = abs(prev_state[1] - state[1]) * 2.0
            prev_state = state
            cost_mult = ((1.0 - COST_BP) ** to) if to > 0 else 1.0
            net = (1.0 + gross) * cost_mult - 1.0

            W_open_d0 = W_pre * cost_mult
            d0, m_days = r["d0"], r["m_days"]
            o0_tq = float(dfs["TQQQ"].at[d0, "o"])
            o0_qq = float(dfs["QQQ"].at[d0, "o"])
            df_ca = dfs["SGOV"] if d0 >= pd.Timestamp("2020-06-01") else dfs["BIL"]
            o0_ca = float(df_ca.at[d0, "o"])
            for d in m_days:
                if state[0] == "CASH":
                    rel_c = float(df_ca.at[d, "c"]) / o0_ca
                else:
                    rel_c = state[1] * (float(dfs["TQQQ"].at[d, "c"]) / o0_tq) + (1.0 - state[1]) * (float(dfs["QQQ"].at[d, "c"]) / o0_qq)
                pts_nav[d] = W_open_d0 * rel_c
            W_pre = W_pre * (1.0 + net)
            rets.append({"ym": r["ym"], "sep_on": r["sep_on"], "w_tq": state[1], "net": net, "rf": r["rf_m"]})

        rdf = pd.DataFrame(rets)
        s_nav = pd.Series(pts_nav).sort_index()
        d_ret = s_nav.pct_change().dropna()
        c26 = (np.prod(1.0 + rdf["net"]) ** (12.0 / len(rdf)) - 1.0) * 100.0
        r25 = rdf[rdf["ym"] <= "2025-12"]
        c25 = (np.prod(1.0 + r25["net"]) ** (12.0 / len(r25)) - 1.0) * 100.0
        rex = rdf[~rdf["ym"].str[:4].isin(["2018", "2020"])]
        cex1820 = (np.prod(1.0 + rex["net"]) ** (12.0 / len(rex)) - 1.0) * 100.0
        ex_m = rdf["net"] - rdf["rf"]
        m_sh = (ex_m.mean() / ex_m.std(ddof=1)) * np.sqrt(12.0)
        d_sh = (d_ret.mean() / d_ret.std(ddof=1)) * np.sqrt(252.0)
        eq_m = np.cumprod(1.0 + rdf["net"].values)
        m_mdd = np.min(eq_m / np.maximum.accumulate(eq_m) - 1.0) * 100.0
        d_mdd = ((s_nav / s_nav.cummax()) - 1.0).min() * 100.0
        return {
            "rdf": rdf, "s_nav": s_nav,
            "c25": c25, "c26": c26, "cex1820": cex1820,
            "m_sh": m_sh, "d_sh": d_sh, "m_mdd": m_mdd, "d_mdd": d_mdd
        }

    # =========================================================================
    # EXPERIMENT 2: Single-Factor Decomposition & Conditional Incremental Info
    # =========================================================================
    print("\n==========================================================================================")
    print("EXPERIMENT 2: SINGLE-FACTOR DECOMPOSITION & INCREMENTAL INFORMATION OF SPY/RSP Z > 1.2")
    print("==========================================================================================")
    decomp_specs = [
        ("0. Baseline (100% TQQQ in SEP=ON)", lambda r: False),
        ("1. Single Factor A: RSP < MA50 Alone", lambda r: r["rsp_dev50"] < 0.0),
        ("2. Single Factor B: SPY/RSP Z > 1.2 Alone", lambda r: r["sr_tz756"] > 1.2),
        ("3. Combined (A & B): SPY/RSP Z > 1.2 & RSP < MA50", lambda r: r["sr_tz756"] > 1.2 and r["rsp_dev50"] < 0.0),
        ("4. Reverse Check: RSP < MA50 & SPY/RSP Z <= 1.2", lambda r: r["sr_tz756"] <= 1.2 and r["rsp_dev50"] < 0.0),
        ("5. Combined + NoWash: Z > 1.2 & -4% < RSP_dev50 < 0%", lambda r: r["sr_tz756"] > 1.2 and -4.0 < r["rsp_dev50"] < 0.0),
    ]
    decomp_rows = []
    base_res = run_bt(lambda r: False)
    for name, fn in decomp_specs:
        m_on = on.apply(fn, axis=1)
        sub = on[m_on]
        rest = on[~m_on]
        c_in = int(sub["crash15"].sum())
        c_out = int(rest["crash15"].sum())
        fp = fisher_exact([[c_in, len(sub) - c_in], [c_out, len(rest) - c_out]], alternative="greater")[1] if len(sub) > 0 else 1.0
        mp = mannwhitneyu(sub["r_tq"], rest["r_tq"], alternative="less")[1] if (0 < len(sub) < len(on)) else 1.0
        bt = run_bt(fn)
        log_diff = float((np.log(1.0 + bt["rdf"]["net"]) - np.log(1.0 + base_res["rdf"]["net"])).sum() * 100.0)
        decomp_rows.append({
            "strategy": name,
            "trig_m": len(sub),
            "crashes": f"{c_in}/{len(sub)}",
            "tq_mean_pct": round(sub["r_tq"].mean() * 100.0, 2) if len(sub) > 0 else np.nan,
            "tq_med_pct": round(sub["r_tq"].median() * 100.0, 2) if len(sub) > 0 else np.nan,
            "fisher_p": round(fp, 4),
            "mwu_p": round(mp, 4),
            "net_log_wealth_diff_pct": round(log_diff, 2),
            "cagr_11_25": round(bt["c25"], 2),
            "cagr_11_26": round(bt["c26"], 2),
            "cagr_ex18_20": round(bt["cex1820"], 2),
            "m_sharpe": round(bt["m_sh"], 3),
            "d_sharpe": round(bt["d_sh"], 3),
            "open_daily_mdd": round(bt["d_mdd"], 2),
        })
    df_decomp = pd.DataFrame(decomp_rows)
    df_decomp.to_csv(os.path.join(OUT_DIR, "spy_rsp_single_factor_decomposition.csv"), index=False)
    print(df_decomp.to_string(index=False))

    # Direct conditional test inside RSP < MA50 (35 months total: 22 with Z > 1.2 vs 13 with Z <= 1.2)
    rsp_weak = on[on["rsp_dev50"] < 0.0].copy()
    g_hi = rsp_weak[rsp_weak["sr_tz756"] > 1.2]
    g_lo = rsp_weak[rsp_weak["sr_tz756"] <= 1.2]
    fp_cond = fisher_exact(
        [[int(g_hi["crash15"].sum()), len(g_hi) - int(g_hi["crash15"].sum())],
         [int(g_lo["crash15"].sum()), len(g_lo) - int(g_lo["crash15"].sum())]],
        alternative="greater"
    )[1]
    mp_cond = mannwhitneyu(g_hi["r_tq"], g_lo["r_tq"], alternative="less")[1]
    print(f"\n  [Conditional Test Inside All {len(rsp_weak)} Months Where RSP < MA50]:")
    print(f"    - When SPY/RSP Z > +1.2  (N={len(g_hi):2d}): TQQQ Mean = {g_hi['r_tq'].mean()*100:+6.2f}%, Med = {g_hi['r_tq'].median()*100:+6.2f}%, Crashes = {int(g_hi['crash15'].sum())}/{len(g_hi)} ({g_hi['crash15'].mean()*100:.1f}%), Gross Log-Wealth Saved = {(np.log(1+g_hi['r_qq'])-np.log(1+g_hi['r_tq'])).sum()*100:+.2f}")
    print(f"    - When SPY/RSP Z <= +1.2 (N={len(g_lo):2d}): TQQQ Mean = {g_lo['r_tq'].mean()*100:+6.2f}%, Med = {g_lo['r_tq'].median()*100:+6.2f}%, Crashes = {int(g_lo['crash15'].sum())}/{len(g_lo)} ({g_lo['crash15'].mean()*100:.1f}%), Gross Log-Wealth Saved = {(np.log(1+g_lo['r_qq'])-np.log(1+g_lo['r_tq'])).sum()*100:+.2f} | Months: {', '.join(g_lo['ym'].tolist())}")
    print(f"    - Conditional Difference (High Z vs Low Z given RSP < MA50): Fisher p = {fp_cond:.4f}, Mann-Whitney U p = {mp_cond:.4f}")

    # =========================================================================
    # EXPERIMENT 3: Zero-Line Cliff & Boundary Stress Test
    # =========================================================================
    print("\n==========================================================================================")
    print("EXPERIMENT 3: ZERO-LINE CLIFF & BOUNDARY STRESS TEST (THRESHOLD / MA WINDOW / LAG)")
    print("==========================================================================================")
    buckets = [
        ("Near-Zero Cliff (-0.5% <= RSP_dev50 < 0.0%)", (c13_df["rsp_dev50"] >= -0.5) & (c13_df["rsp_dev50"] < 0.0)),
        ("Moderate Breakdown (-2.0% <= RSP_dev50 < -0.5%)", (c13_df["rsp_dev50"] >= -2.0) & (c13_df["rsp_dev50"] < -0.5)),
        ("Clear Breakdown (-4.0% < RSP_dev50 < -2.0%)", (c13_df["rsp_dev50"] > -4.0) & (c13_df["rsp_dev50"] < -2.0)),
        ("Deep Washout (RSP_dev50 <= -4.0%)", c13_df["rsp_dev50"] <= -4.0),
    ]
    print("  --- Breakdown of the 22 Triggered Months by RSP_dev50 Depth (True Python Ledger) ---")
    tot_lw = c13_df["log_wealth_diff_pct"].sum()
    for b_lbl, b_mask in buckets:
        sub_b = c13_df[b_mask]
        lw_b = sub_b["log_wealth_diff_pct"].sum()
        print(f"    {b_lbl:<48}: N={len(sub_b):2d} | Crashes={int(sub_b['crash15'].sum())}/{len(sub_b):2d} | Gross Log-Wealth Diff = {lw_b:+6.2f} ({lw_b/tot_lw*100:5.1f}% of {tot_lw:+.2f}) | Months: {', '.join(sub_b['ym'].tolist())}")

    stress_specs = [
        ("A0. Frozen: Z_3Y > 1.2 & RSP_dev50 < 0.0% (t close)", lambda r: r["sr_tz756"] > 1.2 and r["rsp_dev50"] < 0.0, False),
        ("A1. Threshold +0.5%: Z_3Y > 1.2 & RSP_dev50 < +0.5%", lambda r: r["sr_tz756"] > 1.2 and r["rsp_dev50"] < 0.5, False),
        ("A2. Threshold -0.25%: Z_3Y > 1.2 & RSP_dev50 < -0.25%", lambda r: r["sr_tz756"] > 1.2 and r["rsp_dev50"] < -0.25, False),
        ("A3. Threshold -0.50%: Z_3Y > 1.2 & RSP_dev50 < -0.50%", lambda r: r["sr_tz756"] > 1.2 and r["rsp_dev50"] < -0.50, False),
        ("A4. Threshold -1.00%: Z_3Y > 1.2 & RSP_dev50 < -1.00%", lambda r: r["sr_tz756"] > 1.2 and r["rsp_dev50"] < -1.00, False),
        ("B1. Window MA40: Z_3Y > 1.2 & RSP < MA40", lambda r: r["sr_tz756"] > 1.2 and r["rsp_dev40"] < 0.0, False),
        ("B2. Window MA45: Z_3Y > 1.2 & RSP < MA45", lambda r: r["sr_tz756"] > 1.2 and r["rsp_dev45"] < 0.0, False),
        ("B3. Window MA55: Z_3Y > 1.2 & RSP < MA55", lambda r: r["sr_tz756"] > 1.2 and r["rsp_dev55"] < 0.0, False),
        ("B4. Window MA60: Z_3Y > 1.2 & RSP < MA60", lambda r: r["sr_tz756"] > 1.2 and r["rsp_dev60"] < 0.0, False),
        ("C1. Trend 2Y (504d): Z_2Y > 1.2 & RSP < MA50", lambda r: r["sr_tz504"] > 1.2 and r["rsp_dev50"] < 0.0, False),
        ("C2. Trend 4Y (1008d): Z_4Y > 1.2 & RSP < MA50", lambda r: r["sr_tz1008"] > 1.2 and r["rsp_dev50"] < 0.0, False),
        ("D1. Signal 1 Day Earlier (t-1 close, exec d0 open)", lambda r: r["sr_tz756_tm1"] > 1.2 and r["rsp_dev50_tm1"] < 0.0, False),
        ("D2. Signal 1 Day Later (d0 close, exec d0+1 open)", lambda r: r["sr_tz756_tp1"] > 1.2 and r["rsp_dev50_tp1"] < 0.0, True),
        ("D3. Signal at t close, Execution Delayed 1 Day (d0+1 open)", lambda r: r["sr_tz756"] > 1.2 and r["rsp_dev50"] < 0.0, True),
    ]
    stress_rows = []
    for s_name, s_fn, is_d1 in stress_specs:
        m_on = on.apply(s_fn, axis=1)
        sub = on[m_on]
        rest = on[~m_on]
        c_in = int(sub["crash15"].sum())
        c_out = int(rest["crash15"].sum())
        fp = fisher_exact([[c_in, len(sub) - c_in], [c_out, len(rest) - c_out]], alternative="greater")[1]
        bt = run_bt(s_fn, delay_1d=is_d1)
        lw_diff = float((np.log(1.0 + bt["rdf"]["net"]) - np.log(1.0 + base_res["rdf"]["net"])).sum() * 100.0)
        stress_rows.append({
            "variant": s_name,
            "trig_m": len(sub),
            "crashes": f"{c_in}/{len(sub)}",
            "fisher_p": round(fp, 4),
            "net_log_wealth_diff_pct": round(lw_diff, 2),
            "cagr_11_25": round(bt["c25"], 2),
            "cagr_11_26": round(bt["c26"], 2),
            "cagr_ex18_20": round(bt["cex1820"], 2),
            "m_sharpe": round(bt["m_sh"], 3),
            "open_daily_mdd": round(bt["d_mdd"], 2),
        })
    df_stress = pd.DataFrame(stress_rows)
    df_stress.to_csv(os.path.join(OUT_DIR, "spy_rsp_boundary_stress_test.csv"), index=False)
    print("\n" + df_stress.to_string(index=False))

    # =========================================================================
    # EXPERIMENT 4: Multi-Crisis Leave-Out & Cluster-Collapsed Independence Audit
    # =========================================================================
    print("\n==========================================================================================")
    print("EXPERIMENT 4: YEAR-BY-YEAR LOG-WEALTH ATTRIBUTION, MULTI-CRISIS LEAVE-OUT & EPISODE TEST")
    print("==========================================================================================")
    bt_c13 = run_bt(lambda r: r["sr_tz756"] > 1.2 and r["rsp_dev50"] < 0.0)
    m_comp = base_res["rdf"][["ym", "sep_on", "net", "rf"]].rename(columns={"net": "ret_base"}).merge(
        bt_c13["rdf"][["ym", "w_tq", "net"]].rename(columns={"net": "ret_c13"}), on="ym"
    )
    m_comp["year"] = m_comp["ym"].str.slice(0, 4)
    m_comp["triggered"] = (m_comp["sep_on"]) & (m_comp["w_tq"] < 0.99)
    m_comp["net_log_diff_pct"] = (np.log(1.0 + m_comp["ret_c13"]) - np.log(1.0 + m_comp["ret_base"])) * 100.0

    yr_rows = []
    for yr, g in m_comp.groupby("year"):
        yr_rows.append({
            "year": yr,
            "months": len(g),
            "triggers": int(g["triggered"].sum()),
            "base_ret_pct": round((np.prod(1.0 + g["ret_base"]) - 1.0) * 100.0, 2),
            "c13_ret_pct": round((np.prod(1.0 + g["ret_c13"]) - 1.0) * 100.0, 2),
            "net_log_wealth_diff_pct": round(g["net_log_diff_pct"].sum(), 2),
        })
    df_yr = pd.DataFrame(yr_rows)
    print("  --- Year-by-Year Net Log-Wealth Contribution (After 10bp Turnover Costs) ---")
    print(df_yr[df_yr["triggers"] > 0].to_string(index=False))
    print(f"  Total Net Log-Wealth Advantage (2011-2026, all 190M): {m_comp['net_log_diff_pct'].sum():+.2f} log-pct points")

    leave_out_specs = [
        ("Full Sample (2011-2026, 190M)", []),
        ("Leave-Out 2018 & 2020", ["2018", "2020"]),
        ("Leave-Out 2011 & 2015-2016", ["2011", "2015", "2016"]),
        ("Leave-Out 2011, 2015, 2018, 2020", ["2011", "2015", "2018", "2020"]),
        ("Leave-Out 2011, 2015-16, 2018, 2020 (All 4 Major Crises)", ["2011", "2015", "2016", "2018", "2020"]),
        ("Leave-Out 2011, 2015-16, 2018, 2020, 2025 (All 5 Windows)", ["2011", "2015", "2016", "2018", "2020", "2025"]),
    ]
    lo_rows = []
    for lbl, drop_yrs in leave_out_specs:
        sub_m = m_comp[~m_comp["year"].isin(drop_yrs)].copy()
        n_m = len(sub_m)
        cb = (np.prod(1.0 + sub_m["ret_base"]) ** (12.0 / n_m) - 1.0) * 100.0
        cc = (np.prod(1.0 + sub_m["ret_c13"]) ** (12.0 / n_m) - 1.0) * 100.0
        sb = (np.mean(sub_m["ret_base"] - sub_m["rf"]) / np.std(sub_m["ret_base"], ddof=1)) * np.sqrt(12.0)
        sc = (np.mean(sub_m["ret_c13"] - sub_m["rf"]) / np.std(sub_m["ret_c13"], ddof=1)) * np.sqrt(12.0)
        lo_rows.append({
            "subsample": lbl,
            "months": n_m,
            "triggers_left": int(sub_m["triggered"].sum()),
            "base_cagr_pct": round(cb, 2),
            "c13_cagr_pct": round(cc, 2),
            "cagr_diff_pp": round(cc - cb, 2),
            "net_log_wealth_diff_pct": round(sub_m["net_log_diff_pct"].sum(), 2),
            "base_sharpe": round(sb, 3),
            "c13_sharpe": round(sc, 3),
        })
    df_lo = pd.DataFrame(lo_rows)
    df_lo.to_csv(os.path.join(OUT_DIR, "spy_rsp_multi_crisis_leave_out.csv"), index=False)
    print("\n  --- Multi-Crisis Leave-Out Audit Table ---")
    print(df_lo.to_string(index=False))

    # Episode-Collapsed Independence Test (First-Trigger Entry Months Only)
    on_c = on.copy()
    on_c["trig"] = (on_c["sr_tz756"] > 1.2) & (on_c["rsp_dev50"] < 0.0)
    on_c["first_trig"] = on_c["trig"] & (~on_c["trig"].shift(1, fill_value=False))
    ft_sub = on_c[on_c["first_trig"]]
    ft_rest = on_c[~on_c["trig"]]
    fp_ft = fisher_exact(
        [[int(ft_sub["crash15"].sum()), len(ft_sub) - int(ft_sub["crash15"].sum())],
         [int(ft_rest["crash15"].sum()), len(ft_rest) - int(ft_rest["crash15"].sum())]],
        alternative="greater"
    )[1]
    print(f"\n  [Episode Independence Check — First-Trigger Entry Months Only (Signal Flips 0 -> 1)]:")
    print(f"    Independent Signal Entry Events: N = {len(ft_sub)} ({', '.join(ft_sub['ym'].tolist())})")
    print(f"    Crashes on First Entry Month   : {int(ft_sub['crash15'].sum())}/{len(ft_sub)} ({ft_sub['crash15'].mean()*100:.1f}%) vs Non-Triggered {int(ft_rest['crash15'].sum())}/{len(ft_rest)} ({ft_rest['crash15'].mean()*100:.1f}%) | Fisher exact p = {fp_ft:.4f}")
    print(f"    First-Entry-Month TQQQ Mean    : {ft_sub['r_tq'].mean()*100:+.2f}% (Median {ft_sub['r_tq'].median()*100:+.2f}%), Gross Log-Wealth Saved = {(np.log(1+ft_sub['r_qq'])-np.log(1+ft_sub['r_tq'])).sum()*100:+.2f}")

    # =========================================================================
    # EXPERIMENT 5: Independent Market & True PIT Constituent Breadth Migration
    # =========================================================================
    print("\n==========================================================================================")
    print("EXPERIMENT 5: MIGRATION TO TRUE PIT S&P 500 CONSTITUENT BREADTH, A/D LINE & QQQ/QQQE")
    print("==========================================================================================")
    mig_specs = [
        ("0. Baseline (100% TQQQ in SEP=ON)", lambda r: False),
        ("1. Benchmark: SPY/RSP Z > 1.2 & RSP < MA50", lambda r: r["sr_tz756"] > 1.2 and r["rsp_dev50"] < 0.0),
        ("2. True PIT Breadth Alone: S&P 500 1M Adv% < 50%", lambda r: r["sp_pit_adv1m"] < 50.0),
        ("3. SPY/RSP Z > 1.2 & True S&P 500 1M Adv% < 50%", lambda r: r["sr_tz756"] > 1.2 and r["sp_pit_adv1m"] < 50.0),
        ("4. SPY/RSP Z > 1.2 & True S&P 500 PIT A/D Line < MA3", lambda r: r["sr_tz756"] > 1.2 and r["sp_ad_below_ma3"]),
        ("5. SPY/RSP Z > 1.2 & S&P Sector ETFs % > MA50 < 50%", lambda r: r["sr_tz756"] > 1.2 and r["sec_pct_ma50"] < 50.0),
        ("6. Nasdaq Migration: QQQ/QQQE Z > 1.2 & RSP < MA50", lambda r: r["qqe_tz756"] > 1.2 and r["rsp_dev50"] < 0.0),
        ("7. Nasdaq Migration: QQQ/QQQE Z > 1.2 & QQQE < MA50", lambda r: r["qqe_tz756"] > 1.2 and r["qqqe_dev50"] < 0.0),
        ("8. Nasdaq Migration: QQQ/QQQE Z > 1.2 & NDX 1M Adv% < 50%", lambda r: r["qqe_tz756"] > 1.2 and r["ndx_pit_adv1m"] < 50.0),
    ]
    mig_rows = []
    for m_name, m_fn in mig_specs:
        m_on = on.apply(m_fn, axis=1)
        sub = on[m_on]
        rest = on[~m_on]
        c_in = int(sub["crash15"].sum())
        c_out = int(rest["crash15"].sum())
        fp = fisher_exact([[c_in, len(sub) - c_in], [c_out, len(rest) - c_out]], alternative="greater")[1] if len(sub) > 0 else 1.0
        mp = mannwhitneyu(sub["r_tq"], rest["r_tq"], alternative="less")[1] if (0 < len(sub) < len(on)) else 1.0
        bt = run_bt(m_fn)
        lw_diff = float((np.log(1.0 + bt["rdf"]["net"]) - np.log(1.0 + base_res["rdf"]["net"])).sum() * 100.0)
        mig_rows.append({
            "strategy": m_name,
            "trig_m": len(sub),
            "crashes": f"{c_in}/{len(sub)}",
            "fisher_p": round(fp, 4),
            "mwu_p": round(mp, 4),
            "net_log_wealth_diff_pct": round(lw_diff, 2),
            "cagr_11_25": round(bt["c25"], 2),
            "cagr_11_26": round(bt["c26"], 2),
            "cagr_ex18_20": round(bt["cex1820"], 2),
            "m_sharpe": round(bt["m_sh"], 3),
            "open_daily_mdd": round(bt["d_mdd"], 2),
        })
    df_mig = pd.DataFrame(mig_rows)
    df_mig.to_csv(os.path.join(OUT_DIR, "spy_rsp_independent_breadth_migration.csv"), index=False)
    print(df_mig.to_string(index=False))


if __name__ == "__main__":
    main()
