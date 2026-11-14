#!/usr/bin/env python3
"""
Zero-Revision Market-Priced Combination Audit for TQQQ + SEP (2026-11-14)
=========================================================================
Tests combinations built strictly from 100% unrevised market quotes (verified via ALFRED):
1. VRP (Variance Risk Premium / Forward Panic Spread) = VIXCLS(t) - QQQ_Vol21(t):
   - VRP > 0 means 30-day forward implied volatility (VIX) exceeds trailing 21-day realized volatility (Vol21).
   - Automatically separates Pre-Crash Option Hedging (VRP > 0: 2011-07, 2020-01, 2020-02, 2020-08)
     from Post-Crash Volatility Flush (VRP << 0: 2018-12-31 [-10.7], 2020-03-31 [-35.4], where V-shaped rebounds start).
2. Credit Spread Widening = (DBAA - DGS10) 21-trading-day change (strictly lagged by 1 business day per H.15 ALFRED release).
3. Institutional Positioning = Crowding_Z (BofA Cash Z + CFTC ES AM Net Z, strict release-date PIT from 2010-08).
4. Macro Policy Gridlock = V3 Midterm Election Flip (Unified -> Divided Government December: 2010-12, 2018-12, 2022-12).
"""

import os
import json
import numpy as np
import pandas as pd
import outputs.remediation_full_audit_20261104.run_full_8point_remediation_audit as r8
import independent_v4_symmetric_sharpe_top2_audit as v4_eng

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE_DIR, "outputs", "v4_symmetric_sharpe_top2_20261113")
os.makedirs(OUT_DIR, exist_ok=True)


def wilson_ci(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2.0 * n)) / denom
    half = (z * np.sqrt((p * (1.0 - p) + z * z / (4.0 * n)) / n)) / denom
    return (max(0.0, (center - half) * 100.0), min(100.0, (center + half) * 100.0))


def load_fred(sid):
    with open(os.path.join(BASE_DIR, "data", "fred", f"{sid}.json")) as f:
        return pd.Series({pd.Timestamp(r[0]): float(r[1]) for r in json.load(f)["values"] if r[1] not in (None, ".", "")}).sort_index()


def main():
    df_tqqq = r8.load_tiingo_etf_df("TQQQ")
    df_qqq = r8.load_tiingo_etf_df("QQQ")
    df_sgov = r8.load_tiingo_etf_df("SGOV")
    df_bil = r8.load_tiingo_etf_df("BIL")

    rf_s = load_fred("DGS3MO") / 100.0
    vix = load_fred("VIXCLS")
    dbaa = load_fred("DBAA")
    dgs10 = load_fred("DGS10")

    cal = df_qqq.index.sort_values()
    reg_map = v4_eng.reg_map
    months_214 = v4_eng.months_214

    qqq_c, qqq_o = df_qqq["c"], df_qqq["o"]
    qqq_r = qqq_c.pct_change().fillna(0.0)
    rf_daily = rf_s.reindex(qqq_c.index).ffill().fillna(0.0) / 252.0
    tqqq_daily_cost = (0.0095 / 252.0) + 2.0 * (rf_daily + 0.0050 / 252.0)
    launch_dt = pd.Timestamp("2010-02-11")
    pre_days = qqq_c.index[(qqq_c.index >= "2008-12-31") & (qqq_c.index <= launch_dt)]
    syn_c, syn_o = [1.0], [1.0]
    for i in range(1, len(pre_days)):
        d_prev, d_curr = pre_days[i - 1], pre_days[i]
        r_on = float(qqq_o.at[d_curr] / qqq_c.at[d_prev] - 1.0)
        r_full = float(qqq_r.at[d_curr]) - float(tqqq_daily_cost.at[d_curr])
        syn_o.append(syn_c[-1] * max(0.05, 1.0 + 3.0 * r_on))
        syn_c.append(syn_c[-1] * max(0.05, 1.0 + 3.0 * r_full))
    df_pre = pd.DataFrame({"c": syn_c, "o": syn_o}, index=pre_days)
    scale_factor = float(df_tqqq.at[launch_dt, "o"] / df_pre.at[launch_dt, "o"])
    df_pre["c"] *= scale_factor
    df_pre["o"] *= scale_factor
    df_tqqq_full = pd.concat([df_pre.loc[df_pre.index < launch_dt], df_tqqq[["c", "o"]]]).sort_index()
    df_tqqq_full = df_tqqq_full[~df_tqqq_full.index.duplicated(keep="last")]

    all_ym = pd.date_range("1999-01-01", "2026-11-01", freq="ME").strftime("%Y-%m")
    with open(os.path.join(BASE_DIR, "data", "valuation", "BOFA_FMS_CASH.json")) as f:
        bofa_df = pd.DataFrame(json.load(f)["values"], columns=["date", "cash"])
    bofa_s = pd.Series(dict(zip(bofa_df["date"].str.slice(0, 7), bofa_df["cash"]))).reindex(all_ym).ffill()
    bofa_z_low = -(bofa_s - bofa_s.rolling(36, min_periods=18).mean()) / bofa_s.rolling(36, min_periods=18).std()

    with open(os.path.join(BASE_DIR, "data", "valuation", "CFTC_ES_AM_NET.json")) as f:
        es_df = pd.DataFrame(json.load(f)["values"], columns=["date", "net_oi"]).assign(
            date=lambda x: pd.to_datetime(x["date"])
        ).set_index("date").sort_index()
    es_df["release_date"] = es_df.index + pd.Timedelta(days=3)
    es_pit_val = {}
    for ym_str in all_ym:
        t_dt = pd.Timestamp(ym_str + "-01") + pd.offsets.MonthEnd(1)
        cal_sub = cal[cal <= t_dt]
        t_trade = cal_sub[-1] if len(cal_sub) > 0 else t_dt
        sub = es_df[es_df["release_date"] <= t_trade]
        if len(sub) > 0:
            es_pit_val[ym_str] = float(sub["net_oi"].iloc[-1])
    es_s_rel = pd.Series(es_pit_val).reindex(all_ym).ffill()
    es_z_rel = (es_s_rel - es_s_rel.rolling(36, min_periods=18).mean()) / es_s_rel.rolling(36, min_periods=18).std()

    vix_d = vix.reindex(cal).ffill()
    vol21_d = qqq_r.rolling(21).std() * np.sqrt(252) * 100.0
    cs_baa_d = (dbaa - dgs10).reindex(cal).ffill()

    m_rows = []
    for t in months_214:
        hold_ym = (t + pd.offsets.MonthBegin(1)).strftime("%Y-%m")
        sig_ym = t.strftime("%Y-%m")
        sep_on = bool(reg_map[t]["sep_on"])

        d0_idx = cal.searchsorted(t, side="right")
        d0 = cal[d0_idx] if d0_idx < len(cal) else cal[-1]
        if t == pd.Timestamp("2026-09-30"):
            d1 = pd.Timestamp("2026-10-29")
            m_days = cal[(cal >= d0) & (cal <= d1)]
            p_col = "c"
        else:
            t_next = t + pd.offsets.MonthEnd(1)
            d1_idx = cal.searchsorted(t_next, side="right")
            d1 = cal[d1_idx] if d1_idx < len(cal) else cal[-1]
            m_days = cal[(cal >= d0) & (cal < d1)]
            p_col = "o"

        r_tq = float(df_tqqq_full.loc[:d1, p_col].iloc[-1] / df_tqqq_full.loc[:d0, "o"].iloc[-1] - 1.0)
        r_qq = float(df_qqq.loc[:d1, p_col].iloc[-1] / df_qqq.loc[:d0, "o"].iloc[-1] - 1.0)
        r_ca = float(reg_map[t]["ret_sgov_actual"])
        tq_m_closes = df_tqqq_full.loc[m_days, "c"]
        tq_m_dd = float((tq_m_closes / tq_m_closes.cummax() - 1.0).min()) if len(tq_m_closes) > 0 else 0.0

        vix_now = float(vix_d.loc[:t].iloc[-1])
        vix_chg21 = float(vix_d.loc[:t].iloc[-1] - vix_d.loc[:t].iloc[-22])
        vol21_now = float(vol21_d.loc[:t].iloc[-1])
        vrp = vix_now - vol21_now

        # Strictly lagged by 1 business day for FRED H.15 DBAA & DGS10 publication
        t_lag1 = cal[max(0, cal.searchsorted(t) - 1)]
        cs_now = float(cs_baa_d.loc[:t_lag1].iloc[-1])
        cs_prev21 = float(cs_baa_d.loc[:t_lag1].iloc[-22])
        cs_baa_chg21 = cs_now - cs_prev21

        zc = float(bofa_z_low.get(sig_ym, np.nan))
        ze = float(es_z_rel.get(sig_ym, np.nan)) if hold_ym >= "2011-01" else np.nan
        cz = (zc + ze) / 2.0 if pd.notna(ze) else zc

        m_rows.append({
            "t": t, "t_str": t.strftime("%Y-%m-%d"), "t_lag1_str": t_lag1.strftime("%Y-%m-%d"),
            "ym": hold_ym, "sep_on": sep_on,
            "vix_now": vix_now, "vix_chg21": vix_chg21, "vol21_now": vol21_now, "vrp": vrp,
            "cs_now": cs_now, "cs_prev21": cs_prev21, "cs_baa_chg21": cs_baa_chg21,
            "cz": cz, "r_tq": r_tq, "r_qq": r_qq, "r_ca": r_ca, "tq_m_dd": tq_m_dd,
            "rf_m": float(reg_map[t]["rf_m"]), "d0": d0, "d1": d1, "m_days": m_days
        })

    df_M = pd.DataFrame(m_rows)

    # =========================================================================
    # STAGE 1: Mutually Exclusive 4-Quadrant Forward Risk Partition (156 SEP=ON Months)
    # =========================================================================
    print("==========================================================================================")
    print("STAGE 1: 4-QUADRANT FORWARD RISK PARTITION (CREDIT SPREAD x VRP, N=156 SEP=ON MONTHS)")
    print("==========================================================================================")
    sub_on = df_M[(df_M["ym"] >= "2011-01") & (df_M["sep_on"])].copy()

    def quad_fn(r):
        cs_wide = r["cs_baa_chg21"] > 0.10
        vrp_pos = r["vrp"] > 0.0
        if not cs_wide and not vrp_pos:
            return "Q1: Credit Calm (<=10bp) & VRP <= 0 (Realized >= Implied)"
        if not cs_wide and vrp_pos:
            return "Q2: Credit Calm (<=10bp) & VRP > 0 (Normal Option Premium)"
        if cs_wide and not vrp_pos:
            return "Q3: Credit Widening (>10bp) BUT VRP <= 0 (Post-Flush / V-Rebound)"
        return "Q4 [DANGER]: Credit Widening (>10bp) AND VRP > 0 (Pre-Crash Stress)"

    sub_on["quad"] = sub_on.apply(quad_fn, axis=1)
    for q_lbl in sorted(sub_on["quad"].unique()):
        g = sub_on[sub_on["quad"] == q_lbl]
        n = len(g)
        k = int((g["r_tq"] <= -0.15).sum())
        ci_lo, ci_hi = wilson_ci(k, n)
        print(f"  {q_lbl:68s} | N={n:3d} | Next-M TQQQ={g['r_tq'].mean()*100:+6.2f}% | "
              f"Intra-M DD={g['tq_m_dd'].mean()*100:6.2f}% | Crash(<-15%)={k:2d}/{n:2d} ({k/n*100:4.1f}%, CI [{ci_lo:4.1f}%..{ci_hi:4.1f}%])")

    # =========================================================================
    # STAGE 2: Item-by-Item Audit of All Triggered Months (Combo 1 & Combo 2)
    # =========================================================================
    print("\n==========================================================================================")
    print("STAGE 2: ITEM-BY-ITEM AUDIT OF ALL TRIGGERED MONTHS (2011-2026)")
    print("==========================================================================================")
    trig = sub_on[(sub_on["cs_baa_chg21"] > 0.10) & (sub_on["vrp"] > 0.0) | (sub_on["ym"].isin(["2010-12", "2018-12", "2022-12"]))].copy()
    audit_list = []
    for _, r in trig.iterrows():
        reason = []
        if r["cs_baa_chg21"] > 0.10 and r["vrp"] > 0.0:
            reason.append("BAA_21d>10bp & VRP>0")
        if r["ym"] in ["2010-12", "2018-12", "2022-12"]:
            reason.append("Midterm Flip (Unified->Divided)")
        audit_list.append({
            "hold_ym": r["ym"],
            "form_date_t": r["t_str"],
            "h15_lag1_dt": r["t_lag1_str"],
            "reason": " + ".join(reason),
            "baa10y_prev21": round(r["cs_prev21"], 2),
            "baa10y_now": round(r["cs_now"], 2),
            "baa10y_chg21_bp": round(r["cs_baa_chg21"] * 100.0, 1),
            "vix_close": round(r["vix_now"], 2),
            "qqq_vol21": round(r["vol21_now"], 2),
            "vrp_vix_minus_vol21": round(r["vrp"], 2),
            "crowding_z": round(r["cz"], 2),
            "tqqq_ret_pct": round(r["r_tq"] * 100.0, 2),
            "qqq_ret_pct": round(r["r_qq"] * 100.0, 2),
            "saved_vs_tqqq_pct": round((r["r_qq"] - r["r_tq"]) * 100.0, 2),
        })
    df_trig = pd.DataFrame(audit_list)
    df_trig.to_csv(os.path.join(OUT_DIR, "tqqq_vrp_credit_combo_triggered_months.csv"), index=False)
    print(df_trig.to_string(index=False))

    # =========================================================================
    # STAGE 3: Full Backtest & Threshold Robustness Grid (Zero Cliff Verification)
    # =========================================================================
    COST_BP = 0.0010
    summary_rows = []

    def run_bt(name, wt_fn, start_ym="2011-01"):
        prev_state = None
        rows = []
        W = 1.0
        pts_nav = {}
        false_alarms = 0
        total_alarms = 0
        for _, r in df_M.iterrows():
            hold_ym = r["ym"]
            sep_on = r["sep_on"]
            if not sep_on:
                state = ("CASH", 0.0)
                gross = r["r_ca"]
            else:
                res_w = wt_fn(r)
                if isinstance(res_w, tuple):
                    mode, w_tq = res_w
                else:
                    mode, w_tq = "ON", float(res_w)
                if mode == "CASH":
                    state = ("CASH", 0.0)
                    gross = r["r_ca"]
                else:
                    state = ("ON", round(w_tq, 3))
                    gross = w_tq * r["r_tq"] + (1.0 - w_tq) * r["r_qq"]
                if (mode == "CASH" or w_tq < 0.99) and hold_ym >= start_ym:
                    total_alarms += 1
                    if r["r_tq"] > gross:
                        false_alarms += 1

            if prev_state is None:
                to = 1.0
            elif prev_state[0] != state[0]:
                to = 2.0
            else:
                to = abs(prev_state[1] - state[1]) * 2.0
            prev_state = state
            net = (1.0 + gross) * ((1.0 - COST_BP) ** to) - 1.0 if to > 0 else gross

            d0, d1, m_days = r["d0"], r["d1"], r["m_days"]
            c0_tq = float(df_tqqq_full.loc[:d0, "c"].iloc[-1])
            c0_qq = float(df_qqq.loc[:d0, "c"].iloc[-1])
            df_ca = df_sgov if d0 >= pd.Timestamp("2020-06-01") else df_bil
            c0_ca = float(df_ca.loc[:d0, "c"].iloc[-1])
            for d in m_days:
                if state[0] == "CASH":
                    rel = float(df_ca.loc[:d, "c"].iloc[-1]) / c0_ca
                else:
                    rel = state[1] * (float(df_tqqq_full.loc[:d, "c"].iloc[-1]) / c0_tq) + (1.0 - state[1]) * (float(df_qqq.loc[:d, "c"].iloc[-1]) / c0_qq)
                pts_nav[d] = W * rel
            W = W * (1.0 + net)
            pts_nav[d1] = W
            rows.append({"ym": hold_ym, "net_ret": net, "rf_m": r["rf_m"]})

        df_L = pd.DataFrame(rows)
        s_nav = pd.Series(pts_nav).sort_index()
        sub_L = df_L[df_L["ym"] >= start_ym]
        r_vec = sub_L["net_ret"].values
        rf_vec = sub_L["rf_m"].values
        cagr = (np.prod(1.0 + r_vec) ** (12.0 / len(r_vec)) - 1.0) * 100.0
        sh = (np.mean(r_vec - rf_vec) / np.std(r_vec, ddof=1) * np.sqrt(12.0))
        eq = np.cumprod(1.0 + r_vec)
        mdd = np.min(eq / np.maximum.accumulate(eq) - 1.0) * 100.0
        nav_sub = s_nav[s_nav.index >= pd.Timestamp(start_ym + "-01")]
        ddd = float((nav_sub / nav_sub.cummax() - 1.0).min()) * 100.0
        cvar5 = pd.Series(r_vec).nsmallest(max(1, int(len(r_vec) * 0.05))).mean() * 100.0
        r_no18_20 = sub_L[(~sub_L["ym"].str.startswith("2018-")) & (~sub_L["ym"].isin(["2020-02", "2020-03"]))]["net_ret"].values
        cagr_no18_20 = (np.prod(1.0 + r_no18_20) ** (12.0 / len(r_no18_20)) - 1.0) * 100.0
        fa_rate = (false_alarms / total_alarms * 100.0) if total_alarms > 0 else 0.0
        summary_rows.append({
            "version": name,
            "cagr_190m": round(cagr, 2),
            "cagr_ex_2018_2020": round(cagr_no18_20, 2),
            "sharpe": round(sh, 3),
            "monthly_maxdd": round(mdd, 2),
            "daily_maxdd": round(ddd, 2),
            "cvar_5pct": round(cvar5, 2),
            "alarms": total_alarms,
            "false_alarm_rate_pct": round(fa_rate, 1),
        })

    run_bt("0. Baseline: Original TQQQ + SEP Only", lambda r: 1.0)
    run_bt("Combo 1: Credit Spread + VRP (BAA_21d > 10bp & VIX > Vol21 -> 1x QQQ)",
           lambda r: 0.0 if (r["cs_baa_chg21"] > 0.10 and r["vrp"] > 0.0) else 1.0)
    run_bt("Combo 2: Crowding + Credit + VRP (CZ > 0 & BAA_21d > 8bp & VIX > Vol21 -> 1x QQQ)",
           lambda r: 0.0 if (pd.notna(r["cz"]) and r["cz"] > 0.0 and r["cs_baa_chg21"] > 0.08 and r["vrp"] > 0.0) else 1.0)
    run_bt("Combo 3: V3 Midterm Election Flip Only (2010-12 / 2018-12 / 2022-12 -> SGOV)",
           lambda r: ("CASH", 0.0) if r["ym"] in ["2010-12", "2018-12", "2022-12"] else 1.0)
    run_bt("Combo 4: Credit + VRP (Combo 1) + V3 Midterm Flip (Combo 3)",
           lambda r: ("CASH", 0.0) if r["ym"] in ["2010-12", "2018-12", "2022-12"] else (0.0 if (r["cs_baa_chg21"] > 0.10 and r["vrp"] > 0.0) else 1.0))

    # Threshold Robustness Grid for Combo 1 (varying BAA_21d threshold from 6bp to 16bp and VRP threshold from -1 to +3)
    for baa_th in [0.06, 0.08, 0.10, 0.12, 0.15]:
        for vrp_th in [-1.0, 0.0, 1.0, 2.0]:
            run_bt(f"  Grid: BAA_21d > {int(baa_th*100)}bp & VRP > {vrp_th:+.1f}",
                   lambda r, b=baa_th, v=vrp_th: 0.0 if (r["cs_baa_chg21"] > b and r["vrp"] > v) else 1.0)

    print("\n==========================================================================================")
    print("STAGE 3: PERFORMANCE & 20-CELL THRESHOLD ROBUSTNESS GRID (2011-2026, 190M)")
    print("==========================================================================================")
    df_sum = pd.DataFrame(summary_rows)
    df_sum.to_csv(os.path.join(OUT_DIR, "tqqq_vrp_credit_combo_summary_and_grid.csv"), index=False)
    print(df_sum.to_string(index=False))


if __name__ == "__main__":
    main()
