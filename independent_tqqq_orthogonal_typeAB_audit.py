#!/usr/bin/env python3
"""
Independent Clean-Room Audit: Orthogonal Crisis-Type Dual-Core (Type A + Type B) for TQQQ + SEP
===============================================================================================
Tests the economic-cycle hypothesis (without any Midterm Election calendar rule):
- Type C (Inflation & Monetary Tightening, e.g., 2022): Handled by primary FOMC `SEP = OFF` -> Cash (SGOV/BIL).
- Inside `SEP = ON`, major TQQQ drawdowns arise from two mutually orthogonal mechanisms:
  1. Type B (Credit & Option Panic / Exogenous Liquidity Shock, e.g., 2020-02, 2020-03, 2020-09):
     - Credit Spread Widening: (DBAA - DGS10) 21-trading-day change > +10bp (strictly lagged by 1 business day per H.15 release).
     - Pure Nasdaq-100 Variance Risk Premium (fixing the S&P 500 VIX vs Nasdaq-100 Vol21 cross-index mismatch):
       * Because Nasdaq-100 VXN has a normal structural risk premium of +3.19 vol points over QQQ_Vol21 (positive 79.1% of days,
         whereas S&P 500 VIX is 2.93 vol points lower than VXN so `VIX - QQQ_Vol21 > 0` implicitly de-meaned VRP by ~3 vol pts),
         we test both raw `VXN - Vol21 > 0` AND de-meaned/standardized Pure Nasdaq-100 VRP:
         - Volatility-space rolling 3Y Z-score: `Z_756d(VXN - QQQ_Vol21) > 0`
         - Variance-space rolling 3Y Z-score: `Z_756d(VXN^2 - QQQ_Vol21^2) > 0`
  2. Type A (Earnings Euphoria Valuation Compression, e.g., 2018-10, 2018-12, 2021-05, 2026-02..06):
     - Numerator (Analyst Euphoria): Wayback Machine PIT S&P 500 IT Forward 4Q Operating EPS YoY >= +24.0%
       (strictly `available_date <= t`, top quartile Q4 euphoria where forward expectations are maxed out).
     - Denominator (Discount Rate / Liquidity Tightening):
       * Variant A1: 10Y TIPS Real Yield (DFII10, strictly lagged by 1 business day per H.15) 63-trading-day (3M) change > 0bp.
       * Variant A2: Federal Reserve Bank Reserves (WRESBAL, strictly lagged by 7 calendar days per H.4.1 release) 4-week average YoY < 0%.
"""

import os
import json
import numpy as np
import pandas as pd
from scipy.stats import fisher_exact, mannwhitneyu
import outputs.remediation_full_audit_20261104.run_full_8point_remediation_audit as r8
import independent_v4_symmetric_sharpe_top2_audit as v4_eng

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE_DIR, "outputs", "v4_symmetric_sharpe_top2_20261113")
os.makedirs(OUT_DIR, exist_ok=True)


def load_fred(sid):
    with open(os.path.join(BASE_DIR, "data", "fred", f"{sid}.json")) as f:
        return pd.Series({
            pd.Timestamp(r[0]): float(r[1])
            for r in json.load(f)["values"]
            if r[1] not in (None, ".", "")
        }).sort_index()


def build_wayback_it_pit_lookup():
    vint = pd.read_csv(os.path.join(BASE_DIR, "outputs", "sector_eps_then_momentum_20261030", "recovered_sector_eps_vintages.csv"))
    vint["available_date"] = pd.to_datetime(vint["available_date"])
    vint["quarter_end"] = pd.to_datetime(vint["quarter_end"])
    it = vint[(vint["sector"] == "Information Technology") & (vint["basis"] == "operating")].copy()
    v_meta = it.groupby("vintage_id")["available_date"].first().reset_index().sort_values("available_date")

    def get_vintage_stats(t_dt):
        elig = v_meta[v_meta["available_date"] <= t_dt]
        if elig.empty:
            return None
        vid = elig.iloc[-1]["vintage_id"]
        dt_v = elig.iloc[-1]["available_date"]
        if (t_dt - dt_v).days > 120:
            return None
        g = it[it["vintage_id"] == vid].drop_duplicates(subset=["quarter"], keep="last").sort_values("quarter_end")
        act = g[g["status"] == "actual"].tail(4)
        est = g[g["status"] == "estimate"].head(4)
        if len(act) < 4 or len(est) < 2:
            return None
        return vid, dt_v, g, float(act["eps"].sum()), float(est["eps"].mean() * 4.0)

    def get_it_fwd_yoy(t_dt):
        if t_dt < pd.Timestamp("2014-01-31"):
            return np.nan, None
        cur = get_vintage_stats(t_dt)
        if cur is None:
            return np.nan, None
        prev_12m = get_vintage_stats(t_dt - pd.Timedelta(days=365))
        if prev_12m is None or prev_12m[4] <= 0:
            return np.nan, cur[1].strftime("%Y-%m-%d")
        return (cur[4] / prev_12m[4] - 1.0) * 100.0, cur[1].strftime("%Y-%m-%d")

    return get_it_fwd_yoy


def main():
    df_tqqq = r8.load_tiingo_etf_df("TQQQ")
    df_qqq = r8.load_tiingo_etf_df("QQQ")
    df_sgov = r8.load_tiingo_etf_df("SGOV")
    df_bil = r8.load_tiingo_etf_df("BIL")

    rf_s = load_fred("DGS3MO") / 100.0
    vix = load_fred("VIXCLS")
    vxn = load_fred("VXNCLS")
    dbaa = load_fred("DBAA")
    dgs10 = load_fred("DGS10")
    dfii10 = load_fred("DFII10")
    wres = load_fred("WRESBAL")

    get_it_fwd_yoy = build_wayback_it_pit_lookup()

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

    vix_d = vix.reindex(cal).ffill()
    vxn_d = vxn.reindex(cal).ffill()
    vol21_d = qqq_r.rolling(21).std() * np.sqrt(252) * 100.0
    vrp_vxn_s = vxn_d - vol21_d
    vrp_vxn_z_s = (vrp_vxn_s - vrp_vxn_s.rolling(756, min_periods=252).mean()) / vrp_vxn_s.rolling(756, min_periods=252).std()
    var_vxn_s = (vxn_d / 100.0) ** 2 - (vol21_d / 100.0) ** 2
    var_vxn_z_s = (var_vxn_s - var_vxn_s.rolling(756, min_periods=252).mean()) / var_vxn_s.rolling(756, min_periods=252).std()

    cs_baa_d = (dbaa - dgs10).reindex(cal).ffill()
    rr_d = dfii10.reindex(cal).ffill()

    m_rows = []
    for t in months_214:
        hold_ym = (t + pd.offsets.MonthBegin(1)).strftime("%Y-%m")
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

        # Same-day exchange-traded option indices (VIX & VXN) and QQQ 21d realized volatility
        vix_now = float(vix_d.loc[:t].iloc[-1])
        vxn_now = float(vxn_d.loc[:t].iloc[-1])
        vol21_now = float(vol21_d.loc[:t].iloc[-1])
        vrp_vix = vix_now - vol21_now
        vrp_vxn = vxn_now - vol21_now
        vrp_vxn_z = float(vrp_vxn_z_s.loc[:t].iloc[-1])
        var_vxn_z = float(var_vxn_z_s.loc[:t].iloc[-1])

        # Strictly lagged by 1 business day for Federal Reserve H.15 series (DBAA, DGS10, DFII10)
        t_lag1 = cal[max(0, cal.searchsorted(t) - 1)]
        cs_now = float(cs_baa_d.loc[:t_lag1].iloc[-1])
        cs_prev21 = float(cs_baa_d.loc[:t_lag1].iloc[-22])
        cs_baa_chg21 = cs_now - cs_prev21

        rr_now = float(rr_d.loc[:t_lag1].iloc[-1])
        rr_prev63 = float(rr_d.loc[:t_lag1].iloc[-64])
        rr_chg63 = rr_now - rr_prev63

        # Strictly lagged by 7 calendar days for Federal Reserve H.4.1 WRESBAL (4-week mean YoY)
        w_sub = wres.loc[:(t - pd.Timedelta(days=7))]
        wres_4w_yoy = float((w_sub.iloc[-4:].mean() / w_sub.iloc[-56:-52].mean() - 1.0) * 100.0) if len(w_sub) >= 56 else np.nan

        # Wayback PIT IT Forward EPS YoY
        it_fwd_yoy, wb_avail_dt = get_it_fwd_yoy(t)

        m_rows.append({
            "t": t, "t_str": t.strftime("%Y-%m-%d"), "t_lag1_str": t_lag1.strftime("%Y-%m-%d"),
            "ym": hold_ym, "sep_on": sep_on,
            "vix_now": vix_now, "vxn_now": vxn_now, "vol21_now": vol21_now,
            "vrp_vix": vrp_vix, "vrp_vxn": vrp_vxn, "vrp_vxn_z": vrp_vxn_z, "var_vxn_z": var_vxn_z,
            "cs_now": cs_now, "cs_baa_chg21": cs_baa_chg21,
            "rr_now": rr_now, "rr_chg63": rr_chg63,
            "wres_4w_yoy": wres_4w_yoy,
            "it_fwd_yoy": it_fwd_yoy, "wb_avail_dt": wb_avail_dt,
            "r_tq": r_tq, "r_qq": r_qq, "r_ca": r_ca,
            "rf_m": float(reg_map[t]["rf_m"]), "d0": d0, "d1": d1, "m_days": m_days
        })

    df_M = pd.DataFrame(m_rows)

    # =========================================================================
    # STAGE 1: Check VIX vs VXN (Same-Index Nasdaq-100 VRP Fix)
    # =========================================================================
    sub_on = df_M[(df_M["ym"] >= "2011-01") & (df_M["sep_on"])].copy()
    trig_b_vix = set(sub_on[(sub_on["cs_baa_chg21"] > 0.10) & (sub_on["vrp_vix"] > 0.0)]["ym"])
    trig_b_vxn_raw = set(sub_on[(sub_on["cs_baa_chg21"] > 0.10) & (sub_on["vrp_vxn"] > 0.0)]["ym"])
    trig_b_vxn_z = set(sub_on[(sub_on["cs_baa_chg21"] > 0.10) & (sub_on["vrp_vxn_z"] > 0.0)]["ym"])
    trig_b_var_z = set(sub_on[(sub_on["cs_baa_chg21"] > 0.10) & (sub_on["var_vxn_z"] > 0.0)]["ym"])
    print("==========================================================================================")
    print("STAGE 1: VIX vs VXN (SAME-INDEX NASDAQ-100 VRP FIX) AUDIT")
    print("==========================================================================================")
    print(f"  1. Cross-Index S&P VIX - QQQ_Vol21 > 0 (N={len(trig_b_vix)}):              {sorted(trig_b_vix)}")
    print(f"  2. Raw Nasdaq VXN - QQQ_Vol21 > 0 (N={len(trig_b_vxn_raw)}, un-centered):      {sorted(trig_b_vxn_raw)}")
    print(f"  3. Standardized Nasdaq VXN VRP Z_3Y > 0 (N={len(trig_b_vxn_z)}, Vol-Space):  {sorted(trig_b_vxn_z)}")
    print(f"  4. Standardized Nasdaq VXN^2-Vol21^2 Z_3Y > 0 (N={len(trig_b_var_z)}, Var-Space): {sorted(trig_b_var_z)}")

    # =========================================================================
    # STAGE 2: Item-by-Item Triggered Months Ledger (Type B [VXN_Z>0] + Type A1 / A2)
    # =========================================================================
    print("\n==========================================================================================")
    print("STAGE 2: ORTHOGONAL TRIGGERED MONTHS LEDGER (TYPE B [VXN_VRP_Z>0] vs TYPE A1 / A2)")
    print("==========================================================================================")
    c_b_vxn_z = (sub_on["cs_baa_chg21"] > 0.10) & (sub_on["vrp_vxn_z"] > 0.0)
    c_a1 = (sub_on["it_fwd_yoy"] >= 24.0) & (sub_on["rr_chg63"] > 0.0)
    c_a2 = (sub_on["it_fwd_yoy"] >= 24.0) & (sub_on["wres_4w_yoy"] < 0.0)

    trig_union = sub_on[c_b_vxn_z | c_a1 | c_a2].copy()
    ledger_rows = []
    for _, r in trig_union.iterrows():
        is_b = bool(r["cs_baa_chg21"] > 0.10 and r["vrp_vxn_z"] > 0.0)
        is_a1 = bool(pd.notna(r["it_fwd_yoy"]) and r["it_fwd_yoy"] >= 24.0 and r["rr_chg63"] > 0.0)
        is_a2 = bool(pd.notna(r["it_fwd_yoy"]) and r["it_fwd_yoy"] >= 24.0 and r["wres_4w_yoy"] < 0.0)
        tags = []
        if is_b:
            tags.append("Type_B(Credit+VXN_VRP_Z>0)")
        if is_a1:
            tags.append("Type_A1(Euphoria+RealRate)")
        if is_a2:
            tags.append("Type_A2(Euphoria+Reserves)")
        ledger_rows.append({
            "hold_ym": r["ym"],
            "form_date_t": r["t_str"],
            "h15_lag1_dt": r["t_lag1_str"],
            "wb_vintage_dt": r["wb_avail_dt"],
            "triggered_by": " | ".join(tags),
            "baa_chg21_bp": round(r["cs_baa_chg21"] * 100.0, 1),
            "vxn_close": round(r["vxn_now"], 2),
            "qqq_vol21": round(r["vol21_now"], 2),
            "vrp_vxn": round(r["vrp_vxn"], 2),
            "vrp_vxn_z": round(r["vrp_vxn_z"], 2),
            "it_fwd_yoy_pct": round(r["it_fwd_yoy"], 2) if pd.notna(r["it_fwd_yoy"]) else np.nan,
            "rr_chg63_bp": round(r["rr_chg63"] * 100.0, 1),
            "wres_4w_yoy_pct": round(r["wres_4w_yoy"], 2),
            "tqqq_ret_pct": round(r["r_tq"] * 100.0, 2),
            "qqq_ret_pct": round(r["r_qq"] * 100.0, 2),
            "saved_vs_tqqq_pct": round((r["r_qq"] - r["r_tq"]) * 100.0, 2),
        })
    df_trig = pd.DataFrame(ledger_rows)
    df_trig.to_csv(os.path.join(OUT_DIR, "tqqq_orthogonal_typeAB_triggered_months.csv"), index=False)
    print(df_trig.to_string(index=False))

    # =========================================================================
    # STAGE 3: Full Backtest Engine (with Daily NAV & 10bp Turnover Cost)
    # =========================================================================
    COST_BP = 0.0010
    summary_rows = []
    daily_nav_store = {}

    def run_bt(name, wt_fn, start_ym="2011-01", store_key=None):
        prev_state = None
        rows = []
        W = 1.0
        pts_nav = {}
        false_alarms = 0
        total_alarms = 0
        trig_tq_rets = []
        trig_tq_rets_ex2003 = []
        non_trig_tq_rets = []

        for _, r in df_M.iterrows():
            hold_ym = r["ym"]
            sep_on = r["sep_on"]
            if not sep_on:
                state = ("CASH", 0.0)
                gross = r["r_ca"]
            else:
                w_tq = float(wt_fn(r))
                state = ("ON", round(w_tq, 3))
                gross = w_tq * r["r_tq"] + (1.0 - w_tq) * r["r_qq"]
                if hold_ym >= start_ym:
                    if w_tq < 0.99:
                        total_alarms += 1
                        trig_tq_rets.append(r["r_tq"])
                        if hold_ym != "2020-03":
                            trig_tq_rets_ex2003.append(r["r_tq"])
                        if r["r_tq"] > gross:
                            false_alarms += 1
                    else:
                        non_trig_tq_rets.append(r["r_tq"])

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
        if store_key is not None:
            daily_nav_store[store_key] = s_nav[s_nav.index >= pd.Timestamp(start_ym + "-01")]

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

        if len(trig_tq_rets) > 0:
            a = sum(1 for x in trig_tq_rets if x <= -0.15)
            b = len(trig_tq_rets) - a
            c_cnt = sum(1 for x in non_trig_tq_rets if x <= -0.15)
            d_cnt = len(non_trig_tq_rets) - c_cnt
            _, fisher_p = fisher_exact([[a, b], [c_cnt, d_cnt]], alternative="greater")
            _, mwu_p = mannwhitneyu(trig_tq_rets, non_trig_tq_rets, alternative="less")
            crash_str = f"{a}/{len(trig_tq_rets)}"
            mean_tq = np.mean(trig_tq_rets) * 100.0
            mean_tq_ex2003 = np.mean(trig_tq_rets_ex2003) * 100.0 if len(trig_tq_rets_ex2003) > 0 else np.nan
        else:
            fisher_p, mwu_p, crash_str, mean_tq, mean_tq_ex2003 = np.nan, np.nan, "0/0", np.nan, np.nan

        res_dict = {
            "window": start_ym + "..2026-10",
            "version": name,
            "cagr_pct": round(cagr, 2),
            "cagr_ex_2018_2020_pct": round(cagr_no18_20, 2),
            "sharpe": round(sh, 3),
            "monthly_maxdd_pct": round(mdd, 2),
            "daily_maxdd_pct": round(ddd, 2),
            "cvar_5pct": round(cvar5, 2),
            "alarms": total_alarms,
            "crash15_hits": crash_str,
            "fisher_p": round(fisher_p, 4) if pd.notna(fisher_p) else np.nan,
            "mwu_p": round(mwu_p, 4) if pd.notna(mwu_p) else np.nan,
            "trig_tqqq_mean_pct": round(mean_tq, 2) if pd.notna(mean_tq) else np.nan,
            "trig_tqqq_ex202003_pct": round(mean_tq_ex2003, 2) if pd.notna(mean_tq_ex2003) else np.nan,
        }
        summary_rows.append(res_dict)
        return res_dict

    for w_start in ["2011-01", "2015-01"]:
        run_bt("0. Baseline: Original TQQQ + SEP Only",
               lambda r: 1.0, start_ym=w_start, store_key=f"base_{w_start}")
        run_bt("1a. Type B Only (Credit>10bp & S&P VIX>Vol21 -> 1x QQQ)",
               lambda r: 0.0 if (r["cs_baa_chg21"] > 0.10 and r["vrp_vix"] > 0.0) else 1.0, start_ym=w_start)
        run_bt("1b. Type B Only (Credit>10bp & Raw Nasdaq VXN>Vol21 -> 1x QQQ)",
               lambda r: 0.0 if (r["cs_baa_chg21"] > 0.10 and r["vrp_vxn"] > 0.0) else 1.0, start_ym=w_start)
        run_bt("1c. Type B Only (Credit>10bp & Nasdaq VXN_VRP Z_3Y>0 -> 1x QQQ)",
               lambda r: 0.0 if (r["cs_baa_chg21"] > 0.10 and r["vrp_vxn_z"] > 0.0) else 1.0, start_ym=w_start, store_key=f"typeB_vxnZ_{w_start}")
        run_bt("1d. Type B Only (Credit>10bp & Nasdaq Var_VRP Z_3Y>0 -> 1x QQQ)",
               lambda r: 0.0 if (r["cs_baa_chg21"] > 0.10 and r["var_vxn_z"] > 0.0) else 1.0, start_ym=w_start)
        run_bt("2a. Type A1 Only (IT_Fwd_YoY>=24% & RealRate_chg3M>0 -> 1x QQQ)",
               lambda r: 0.0 if (pd.notna(r["it_fwd_yoy"]) and r["it_fwd_yoy"] >= 24.0 and r["rr_chg63"] > 0.0) else 1.0, start_ym=w_start)
        run_bt("2b. Type A2 Only (IT_Fwd_YoY>=24% & WRES_4W_YoY<0 -> 1x QQQ)",
               lambda r: 0.0 if (pd.notna(r["it_fwd_yoy"]) and r["it_fwd_yoy"] >= 24.0 and r["wres_4w_yoy"] < 0.0) else 1.0, start_ym=w_start)
        run_bt("3a. Dual-Core A1+B (Type B [VXN_Z>0] OR Type A1 [Euphoria x RealRate] -> 1x QQQ)",
               lambda r: 0.0 if ((r["cs_baa_chg21"] > 0.10 and r["vrp_vxn_z"] > 0.0) or (pd.notna(r["it_fwd_yoy"]) and r["it_fwd_yoy"] >= 24.0 and r["rr_chg63"] > 0.0)) else 1.0,
               start_ym=w_start, store_key=f"dualA1B_{w_start}")
        run_bt("3b. Dual-Core A1+B_Var (Type B [Var_Z>0] OR Type A1 [Euphoria x RealRate] -> 1x QQQ)",
               lambda r: 0.0 if ((r["cs_baa_chg21"] > 0.10 and r["var_vxn_z"] > 0.0) or (pd.notna(r["it_fwd_yoy"]) and r["it_fwd_yoy"] >= 24.0 and r["rr_chg63"] > 0.0)) else 1.0,
               start_ym=w_start, store_key=f"dualA1Bvar_{w_start}")
        run_bt("3c. Dual-Core A2+B (Type B [VXN_Z>0] OR Type A2 [Euphoria x Reserves] -> 1x QQQ)",
               lambda r: 0.0 if ((r["cs_baa_chg21"] > 0.10 and r["vrp_vxn_z"] > 0.0) or (pd.notna(r["it_fwd_yoy"]) and r["it_fwd_yoy"] >= 24.0 and r["wres_4w_yoy"] < 0.0)) else 1.0,
               start_ym=w_start, store_key=f"dualA2B_{w_start}")
        run_bt("3d. Tiered Dual-Core (Type B [VXN_Z>0] -> 1x QQQ, Type A1 -> 2x [50/50])",
               lambda r: 0.0 if (r["cs_baa_chg21"] > 0.10 and r["vrp_vxn_z"] > 0.0) else (0.5 if (pd.notna(r["it_fwd_yoy"]) and r["it_fwd_yoy"] >= 24.0 and r["rr_chg63"] > 0.0) else 1.0),
               start_ym=w_start)

    df_sum = pd.DataFrame(summary_rows)
    df_sum.to_csv(os.path.join(OUT_DIR, "tqqq_orthogonal_typeAB_summary.csv"), index=False)
    print("\n==========================================================================================")
    print("STAGE 3: FULL PERFORMANCE & STATISTICAL SUMMARY (190M & 142M WINDOWS)")
    print("==========================================================================================")
    print(df_sum.to_string(index=False))

    # =========================================================================
    # STAGE 4: 108-Cell 4D Parameter Sensitivity Grid (2011-01..2026-10)
    # =========================================================================
    grid_rows = []
    base_190 = df_sum[(df_sum["window"] == "2011-01..2026-10") & (df_sum["version"].str.startswith("0."))].iloc[0]
    for baa_th in [0.08, 0.10, 0.12]:
        for vxn_z_th in [-0.25, 0.0, 0.25]:
            for eps_th in [20.0, 22.0, 24.0, 26.0]:
                for rr_th in [-0.05, 0.00, 0.05]:
                    g_res = run_bt(
                        f"Grid(BAA>{int(baa_th*100)}bp,VXN_Z>{vxn_z_th:+.2f},EPS>={int(eps_th)}%,RR>{rr_th:+.2f}%)",
                        lambda r, b=baa_th, v=vxn_z_th, e=eps_th, rr=rr_th: 0.0 if (
                            (r["cs_baa_chg21"] > b and r["vrp_vxn_z"] > v) or
                            (pd.notna(r["it_fwd_yoy"]) and r["it_fwd_yoy"] >= e and r["rr_chg63"] > rr)
                        ) else 1.0,
                        start_ym="2011-01"
                    )
                    grid_rows.append(g_res)

    df_grid = pd.DataFrame(grid_rows)
    df_grid.to_csv(os.path.join(OUT_DIR, "tqqq_orthogonal_typeAB_108grid.csv"), index=False)
    beat_cagr = (df_grid["cagr_pct"] > base_190["cagr_pct"]).mean() * 100.0
    beat_sh = (df_grid["sharpe"] > base_190["sharpe"]).mean() * 100.0
    beat_ddd = (df_grid["daily_maxdd_pct"] > base_190["daily_maxdd_pct"]).mean() * 100.0
    print("\n==========================================================================================")
    print("STAGE 4: 108-CELL 4D PARAMETER SENSITIVITY GRID SUMMARY (2011-01..2026-10)")
    print("==========================================================================================")
    print(f"  Total Grid Cells: {len(df_grid)} (BAA in {{8,10,12}}bp x VXN_Z in {{-0.25,0,+0.25}} x EPS in {{20,22,24,26}}% x RR in {{-5,0,+5}}bp)")
    print(f"  Cells Beating Baseline CAGR ({base_190['cagr_pct']:.2f}%):        {beat_cagr:5.1f}% ({int((df_grid['cagr_pct'] > base_190['cagr_pct']).sum())}/{len(df_grid)}) | Grid CAGR Range: [{df_grid['cagr_pct'].min():.2f}% .. {df_grid['cagr_pct'].max():.2f}%], Median={df_grid['cagr_pct'].median():.2f}%")
    print(f"  Cells Beating Baseline Sharpe ({base_190['sharpe']:.3f}):       {beat_sh:5.1f}% ({int((df_grid['sharpe'] > base_190['sharpe']).sum())}/{len(df_grid)}) | Grid Sharpe Range: [{df_grid['sharpe'].min():.3f} .. {df_grid['sharpe'].max():.3f}], Median={df_grid['sharpe'].median():.3f}")
    print(f"  Cells Improving Daily MaxDD ({base_190['daily_maxdd_pct']:.2f}%):    {beat_ddd:5.1f}% ({int((df_grid['daily_maxdd_pct'] > base_190['daily_maxdd_pct']).sum())}/{len(df_grid)}) | Grid Daily MaxDD Range: [{df_grid['daily_maxdd_pct'].min():.2f}% .. {df_grid['daily_maxdd_pct'].max():.2f}%], Median={df_grid['daily_maxdd_pct'].median():.2f}%")

    # =========================================================================
    # STAGE 5: 10-Trading-Day Moving Block Bootstrap (B = 5,000 Replications)
    # =========================================================================
    print("\n==========================================================================================")
    print("STAGE 5: 10-TRADING-DAY MOVING BLOCK BOOTSTRAP (B = 5,000 REPLICATIONS)")
    print("==========================================================================================")
    rng = np.random.default_rng(20261114)
    B = 5000
    block_len = 10

    for w_start in ["2011-01", "2015-01"]:
        nav_b = daily_nav_store[f"base_{w_start}"]
        nav_d = daily_nav_store[f"dualA1B_{w_start}"]
        idx_common = nav_b.index.intersection(nav_d.index)
        r_b = nav_b.loc[idx_common].pct_change().dropna().values
        r_d = nav_d.loc[idx_common].pct_change().dropna().values
        T_days = len(r_b)
        n_blocks = int(np.ceil(T_days / block_len))
        max_start = T_days - block_len

        starts = rng.integers(0, max_start + 1, size=(B, n_blocks))
        offsets = np.arange(block_len)
        idx_mat = (starts[:, :, None] + offsets[None, None, :]).reshape(B, -1)[:, :T_days]

        rb_boot = r_b[idx_mat]
        rd_boot = r_d[idx_mat]

        cagr_b = (np.prod(1.0 + rb_boot, axis=1) ** (252.0 / T_days) - 1.0) * 100.0
        cagr_d = (np.prod(1.0 + rd_boot, axis=1) ** (252.0 / T_days) - 1.0) * 100.0
        diff_cagr = cagr_d - cagr_b

        sh_b = (np.mean(rb_boot, axis=1) / np.std(rb_boot, axis=1, ddof=1)) * np.sqrt(252.0)
        sh_d = (np.mean(rd_boot, axis=1) / np.std(rd_boot, axis=1, ddof=1)) * np.sqrt(252.0)
        diff_sh = sh_d - sh_b

        p_cagr = np.mean(diff_cagr <= 0.0)
        p_sh = np.mean(diff_sh <= 0.0)
        print(f"  Window {w_start}..2026-10 ({T_days} trading days, 10-day blocks, B={B}):")
        print(f"    Delta CAGR (DualA1B - Baseline):   Mean={np.mean(diff_cagr):+5.2f}%, 95% CI [{np.percentile(diff_cagr, 2.5):+5.2f}% .. {np.percentile(diff_cagr, 97.5):+5.2f}%], Bootstrap p(<=0) = {p_cagr:.4f}")
        print(f"    Delta Sharpe (DualA1B - Baseline): Mean={np.mean(diff_sh):+5.3f}, 95% CI [{np.percentile(diff_sh, 2.5):+5.3f} .. {np.percentile(diff_sh, 97.5):+5.3f}], Bootstrap p(<=0) = {p_sh:.4f}")


if __name__ == "__main__":
    main()
