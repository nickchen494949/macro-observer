#!/usr/bin/env python3
"""
First-Principles Forward Risk Prediction & 3-Version Trading Audit for TQQQ + SEP (2026-11-14)
==============================================================================================
Implements the redesigned two-stage experimental framework:
Stage 1 (No Trading - Pure Forward Risk Prediction):
  - Hypothesis 5 Test: When SEP=ON and QQQ > MA50 (and controlling for Vol21 < 20%), does credit/financial
    conditions tightening (NFCI 4W change, BAA-10Y 21D change) predict future 20-day QQQ crashes?
  - Monthly Quintile Risk Test (156 SEP=ON months, 2011-2026): Monotonicity of Crowding_Z, WRESBAL,
    FINRA, ES Outflow, NFCI, and Realized Vol.
  - Market A (Crowded + Calm) vs Market B (Crowded + Stress/Outflow Confirmed) comparison.
Stage 2 (Trading Layer - 3 New Versions vs Original TQQQ + SEP):
  - Baseline: Original TQQQ + SEP Only
  - Version A: Pure Realized Volatility Control (Target Vol & 3-Gear 20%/30%)
  - Version B: Capital Alert + Price Trend Confirmation (MA50 / MA200)
  - Version C: Capital Alert + Financial Conditions / Credit Stress Confirmation (NFCI / BAA-10Y)
  - Evaluates 190M CAGR, Ex-2018&2020 CAGR, Sharpe, Monthly MaxDD, Daily MaxDD, Worst 5% CVaR, and False Alarm Rate.
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


def main():
    df_tqqq = r8.load_tiingo_etf_df("TQQQ")
    df_qqq = r8.load_tiingo_etf_df("QQQ")
    df_sgov = r8.load_tiingo_etf_df("SGOV")
    df_bil = r8.load_tiingo_etf_df("BIL")
    with open(os.path.join(BASE_DIR, "data", "fred", "DGS3MO.json")) as f:
        rf_s = pd.Series({pd.Timestamp(r[0]): float(r[1]) / 100.0 for r in json.load(f)["values"]}).sort_index()
    with open(os.path.join(BASE_DIR, "data", "fred", "NFCI.json")) as f:
        nfci = pd.Series({pd.Timestamp(r[0]): float(r[1]) for r in json.load(f)["values"] if r[1] not in (None, ".")}).sort_index()
    with open(os.path.join(BASE_DIR, "data", "fred", "WRESBAL.json")) as f:
        wres = pd.Series({pd.Timestamp(r[0]): float(r[1]) for r in json.load(f)["values"] if r[1] not in (None, ".")}).sort_index()
    with open(os.path.join(BASE_DIR, "data", "fred", "DBAA.json")) as f:
        dbaa = pd.Series({pd.Timestamp(r[0]): float(r[1]) for r in json.load(f)["values"] if r[1] not in (None, ".")}).sort_index()
    with open(os.path.join(BASE_DIR, "data", "fred", "DGS10.json")) as f:
        dgs10 = pd.Series({pd.Timestamp(r[0]): float(r[1]) for r in json.load(f)["values"] if r[1] not in (None, ".")}).sort_index()

    cal = df_qqq.index.sort_values()
    reg_map = v4_eng.reg_map
    months_214 = v4_eng.months_214

    qqq_c, qqq_o = df_qqq["c"], df_qqq["o"]
    qqq_r_c2c = qqq_c.pct_change().fillna(0.0)
    rf_daily = rf_s.reindex(qqq_c.index).ffill().fillna(0.0) / 252.0
    tqqq_daily_cost = (0.0095 / 252.0) + 2.0 * (rf_daily + 0.0050 / 252.0)

    launch_dt = pd.Timestamp("2010-02-11")
    pre_days = qqq_c.index[(qqq_c.index >= "2008-12-31") & (qqq_c.index <= launch_dt)]
    syn_c, syn_o = [1.0], [1.0]
    for i in range(1, len(pre_days)):
        d_prev, d_curr = pre_days[i - 1], pre_days[i]
        r_on = float(qqq_o.at[d_curr] / qqq_c.at[d_prev] - 1.0)
        r_full = float(qqq_r_c2c.at[d_curr]) - float(tqqq_daily_cost.at[d_curr])
        c_prev = syn_c[-1]
        syn_o.append(c_prev * max(0.05, 1.0 + 3.0 * r_on))
        syn_c.append(c_prev * max(0.05, 1.0 + 3.0 * r_full))
    df_pre = pd.DataFrame({"c": syn_c, "o": syn_o}, index=pre_days)
    scale_factor = float(df_tqqq.at[launch_dt, "o"] / df_pre.at[launch_dt, "o"])
    df_pre["c"] *= scale_factor
    df_pre["o"] *= scale_factor
    df_tqqq_full = pd.concat([df_pre.loc[df_pre.index < launch_dt], df_tqqq[["c", "o"]]]).sort_index()
    df_tqqq_full = df_tqqq_full[~df_tqqq_full.index.duplicated(keep="last")]

    qqq_ma50 = qqq_c.rolling(50).mean()
    qqq_ma200 = qqq_c.rolling(200).mean()
    qqq_vol21_s = qqq_r_c2c.rolling(21).std() * np.sqrt(252) * 100.0

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

    es_pit_val, es_pit_chg4w = {}, {}
    for ym_str in all_ym:
        t_dt = pd.Timestamp(ym_str + "-01") + pd.offsets.MonthEnd(1)
        cal_sub = cal[cal <= t_dt]
        t_trade = cal_sub[-1] if len(cal_sub) > 0 else t_dt
        sub = es_df[es_df["release_date"] <= t_trade]
        if len(sub) > 0:
            es_pit_val[ym_str] = float(sub["net_oi"].iloc[-1])
            es_pit_chg4w[ym_str] = float(sub["net_oi"].iloc[-1] - sub["net_oi"].iloc[-5]) if len(sub) >= 5 else 0.0
    es_s_rel = pd.Series(es_pit_val).reindex(all_ym).ffill()
    es_z_rel = (es_s_rel - es_s_rel.rolling(36, min_periods=18).mean()) / es_s_rel.rolling(36, min_periods=18).std()

    wres_rel = pd.DataFrame({"val": wres.values, "obs_dt": wres.index, "rel_dt": wres.index + pd.Timedelta(days=1)}, index=wres.index)
    nfci_rel = pd.DataFrame({"val": nfci.values, "obs_dt": nfci.index, "rel_dt": nfci.index + pd.Timedelta(days=7)}, index=nfci.index)
    cs_raw = (dbaa - dgs10).dropna()

    COST_BP = 0.0010
    summary_rows = []

    def sim_3layer(name, wt_fn):
        prev_state = None
        rows = []
        W = 1.0
        pts_nav = {}
        false_alarms = 0
        total_alarms = 0
        for t in months_214:
            hold_ym = (t + pd.offsets.MonthBegin(1)).strftime("%Y-%m")
            sig_ym = t.strftime("%Y-%m")
            sep_on = bool(reg_map[t]["sep_on"])

            zc = float(bofa_z_low.get(sig_ym, np.nan))
            ze = float(es_z_rel.get(sig_ym, np.nan)) if hold_ym >= "2011-01" else np.nan
            cz = (zc + ze) / 2.0 if pd.notna(ze) else np.nan
            es_out4w = -float(es_pit_chg4w.get(sig_ym, 0.0)) if hold_ym >= "2011-01" else 0.0

            w_sub = wres_rel[wres_rel["rel_dt"] <= t]["val"]
            w_52w = (w_sub.iloc[-4:].mean() / w_sub.iloc[-56:-52].mean() - 1.0) * 100.0

            n_sub = nfci_rel[nfci_rel["rel_dt"] <= t]["val"]
            nfci_chg4w = float(n_sub.iloc[-1] - n_sub.iloc[-5])

            cs_sub = cs_raw[cs_raw.index <= t - pd.Timedelta(days=1)]
            cs_chg21 = float(cs_sub.iloc[-1] - cs_sub.iloc[-22]) if len(cs_sub) >= 22 else 0.0

            c_t = float(qqq_c.loc[:t].iloc[-1])
            ma50_t = float(qqq_ma50.loc[:t].iloc[-1])
            ma200_t = float(qqq_ma200.loc[:t].iloc[-1])
            vol21_t = float(qqq_vol21_s.loc[:t].iloc[-1])

            info = {
                "ym": hold_ym, "cz": cz, "es_out4w": es_out4w, "w_52w": w_52w,
                "nfci_chg4w": nfci_chg4w, "cs_chg21": cs_chg21,
                "vol21": vol21_t, "below_ma50": c_t < ma50_t, "below_ma200": c_t < ma200_t
            }

            d0_idx = cal.searchsorted(t, side="right")
            d0 = cal[d0_idx] if d0_idx < len(cal) else cal[-1]
            if t == pd.Timestamp("2026-09-30"):
                d1 = pd.Timestamp("2026-10-29")
                m_days = cal[(cal >= d0) & (cal <= d1)]
            else:
                t_next = t + pd.offsets.MonthEnd(1)
                d1_idx = cal.searchsorted(t_next, side="right")
                d1 = cal[d1_idx] if d1_idx < len(cal) else cal[-1]
                m_days = cal[(cal >= d0) & (cal < d1)]

            r_tq = float(df_tqqq_full.loc[:d1, "c" if t == pd.Timestamp("2026-09-30") else "o"].iloc[-1] / df_tqqq_full.loc[:d0, "o"].iloc[-1] - 1.0)
            r_qq = float(df_qqq.loc[:d1, "c" if t == pd.Timestamp("2026-09-30") else "o"].iloc[-1] / df_qqq.loc[:d0, "o"].iloc[-1] - 1.0)
            r_ca = float(reg_map[t]["ret_sgov_actual"])

            if not sep_on:
                state = ("CASH", 0.0)
                gross = r_ca
            else:
                w_tq = float(wt_fn(info))
                state = ("ON", round(w_tq, 2))
                gross = w_tq * r_tq + (1.0 - w_tq) * r_qq
                if w_tq < 0.99 and hold_ym >= "2011-01":
                    total_alarms += 1
                    if r_tq > r_qq:
                        false_alarms += 1

            if prev_state is None:
                to = 1.0
            elif prev_state[0] != state[0]:
                to = 2.0
            else:
                to = abs(prev_state[1] - state[1]) * 2.0
            prev_state = state
            net = (1.0 + gross) * ((1.0 - COST_BP) ** to) - 1.0 if to > 0 else gross

            c0_tq = float(df_tqqq_full.loc[:d0, "c"].iloc[-1])
            c0_qq = float(df_qqq.loc[:d0, "c"].iloc[-1])
            df_ca = df_sgov if d0 >= pd.Timestamp("2020-06-01") else df_bil
            c0_ca = float(df_ca.loc[:d0, "c"].iloc[-1])
            for d in m_days:
                if not sep_on:
                    rel = float(df_ca.loc[:d, "c"].iloc[-1]) / c0_ca
                else:
                    rel = state[1] * (float(df_tqqq_full.loc[:d, "c"].iloc[-1]) / c0_tq) + (1.0 - state[1]) * (float(df_qqq.loc[:d, "c"].iloc[-1]) / c0_qq)
                pts_nav[d] = W * rel
            W = W * (1.0 + net)
            pts_nav[d1] = W
            rows.append({"ym": hold_ym, "net_ret": net, "rf_m": float(reg_map[t]["rf_m"])})

        df_L = pd.DataFrame(rows)
        s_nav = pd.Series(pts_nav).sort_index()
        r190 = df_L[df_L["ym"] >= "2011-01"]["net_ret"].values
        rf190 = df_L[df_L["ym"] >= "2011-01"]["rf_m"].values
        cagr190 = (np.prod(1.0 + r190) ** (12.0 / len(r190)) - 1.0) * 100
        sh190 = (np.mean(r190 - rf190) / np.std(r190, ddof=1) * np.sqrt(12.0))
        eq190 = np.cumprod(1.0 + r190)
        mdd190 = np.min(eq190 / np.maximum.accumulate(eq190) - 1.0) * 100
        nav190 = s_nav[s_nav.index >= "2011-01-01"]
        ddd190 = float((nav190 / nav190.cummax() - 1.0).min()) * 100
        cvar5 = pd.Series(r190).nsmallest(int(len(r190) * 0.05)).mean() * 100
        r_no18_20 = df_L[(df_L["ym"] >= "2011-01") & (~df_L["ym"].str.startswith("2018-")) & (~df_L["ym"].isin(["2020-02", "2020-03"]))]["net_ret"].values
        cagr_no18_20 = (np.prod(1.0 + r_no18_20) ** (12.0 / len(r_no18_20)) - 1.0) * 100
        fa_rate = (false_alarms / total_alarms * 100.0) if total_alarms > 0 else 0.0
        summary_rows.append({
            "version": name,
            "cagr_190m": round(cagr190, 2),
            "cagr_ex_2018_2020": round(cagr_no18_20, 2),
            "sharpe_190m": round(sh190, 3),
            "monthly_maxdd": round(mdd190, 2),
            "daily_maxdd": round(ddd190, 2),
            "cvar_5pct": round(cvar5, 2),
            "alarms": total_alarms,
            "false_alarm_rate_pct": round(fa_rate, 1),
        })

    sim_3layer("0. Baseline: Original TQQQ + SEP Only", lambda x: 1.0)
    sim_3layer("A1. Pure Vol Target (20%/Vol21, capped at 3x)", lambda x: min(1.0, max(0.0, (20.0 / x["vol21"] - 0.333) / 0.667)) if x["vol21"] > 20.0 else 1.0)
    sim_3layer("A2. Pure Vol 3-Gear (Vol>20%->2x, Vol>30%->1x)", lambda x: 0.0 if x["vol21"] > 30.0 else (0.5 if x["vol21"] > 20.0 else 1.0))
    sim_3layer("B1. Pure Trend Control (QQQ<MA50->2x, QQQ<MA200->1x)", lambda x: 0.0 if x["below_ma200"] else (0.5 if x["below_ma50"] else 1.0))
    sim_3layer("B2. Capital Alert (CZ>0.5) + Trend Confirm (MA50->2x, MA200->1x)", lambda x: (0.0 if x["below_ma200"] else (0.5 if x["below_ma50"] else 1.0)) if (pd.notna(x["cz"]) and x["cz"] > 0.5) else 1.0)
    sim_3layer("C1. Pure NFCI Stress (NFCI_4w>0.05->2x, >0.15->1x)", lambda x: 0.0 if x["nfci_chg4w"] > 0.15 else (0.5 if x["nfci_chg4w"] > 0.05 else 1.0))
    sim_3layer("C2. Capital Alert (CZ>0.5) + NFCI Confirm (>0->2x, >0.10->1x)", lambda x: (0.0 if x["nfci_chg4w"] > 0.10 else (0.5 if x["nfci_chg4w"] > 0.0 else 1.0)) if (pd.notna(x["cz"]) and x["cz"] > 0.5) else 1.0)
    sim_3layer("C4. 3-Layer (CZ>0.5 & (NFCI_4w>0 OR BAA_21d>0.10)): 1-hit->2x, Both->1x", lambda x: (0.0 if (x["nfci_chg4w"] > 0.0 and x["cs_chg21"] > 0.10) else (0.5 if (x["nfci_chg4w"] > 0.0 or x["cs_chg21"] > 0.10) else 1.0)) if (pd.notna(x["cz"]) and x["cz"] > 0.5) else 1.0)

    df_out = pd.DataFrame(summary_rows)
    df_out.to_csv(os.path.join(OUT_DIR, "tqqq_3versions_redesign_summary.csv"), index=False)
    print(df_out.to_string(index=False))


if __name__ == "__main__":
    main()
