#!/usr/bin/env python3
"""
Standalone Strict-PIT Audit of TQQQ + SEP + Capital & Liquidity Observation (2026-11-14)
========================================================================================
Tests whether Capital & Liquidity Observation can genuinely improve `TQQQ + SEP`
under all 4 strict external audit requirements:
1. Strict Point-in-Time (PIT) publication lags:
   - CFTC TFF (`CFTC_ES_AM_NET`): disabled before 2011-01 (launched 2010-07-22, backfilled 2010-12-03).
   - BofA FMS Cash (`BOFA_FMS_CASH`): verified mid-month survey release dates.
   - Fed Bank Reserves (`WRESBAL`): weekly H.4.1 release (t - 2 days lag).
   - FINRA Margin Debt (`FINRA_MARGIN_DEBT`): 1-month publication lag (`shift(1)`).
2. Ex-COVID Deletion Test (`Ex-2020-02 & 2020-03`): must beat `TQQQ + SEP Only` (`63.48%` in 214M, `58.17%` in 190M) even without COVID.
3. Drawdown Reduction Test: must materially cut both Monthly MaxDD (`-54.16%`) and Daily MaxDD (`-71.94%`).
4. Parameter Stability Grid: no single-point parameter cliff across thresholds.
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


def run_capital_liquidity_audit():
    df_tqqq = r8.load_tiingo_etf_df("TQQQ")
    df_qqq = r8.load_tiingo_etf_df("QQQ")
    df_sgov = r8.load_tiingo_etf_df("SGOV")
    df_bil = r8.load_tiingo_etf_df("BIL")
    with open(os.path.join(BASE_DIR, "data", "fred", "DGS3MO.json")) as f:
        rf_s = pd.Series({pd.Timestamp(r[0]): float(r[1]) / 100.0 for r in json.load(f)["values"]}).sort_index()

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

    all_ym = pd.date_range("1999-01-01", "2026-11-01", freq="ME").strftime("%Y-%m")
    with open(os.path.join(BASE_DIR, "data", "valuation", "BOFA_FMS_CASH.json")) as f:
        bofa_df = pd.DataFrame(json.load(f)["values"], columns=["date", "cash"])
    bofa_s = pd.Series(dict(zip(bofa_df["date"].str.slice(0, 7), bofa_df["cash"]))).reindex(all_ym).ffill()
    bofa_z_low = -(bofa_s - bofa_s.rolling(36, min_periods=18).mean()) / bofa_s.rolling(36, min_periods=18).std()

    with open(os.path.join(BASE_DIR, "data", "valuation", "CFTC_ES_AM_NET.json")) as f:
        es_df = pd.DataFrame(json.load(f)["values"], columns=["date", "net_oi"]).assign(
            date=lambda x: pd.to_datetime(x["date"])
        ).set_index("date").sort_index()
    es_m = es_df["net_oi"].resample("ME").last()
    es_s = pd.Series({d.strftime("%Y-%m"): v for d, v in es_m.items()}).reindex(all_ym).ffill()
    es_z = (es_s - es_s.rolling(36, min_periods=18).mean()) / es_s.rolling(36, min_periods=18).std()

    with open(os.path.join(BASE_DIR, "data", "valuation", "FINRA_MARGIN_DEBT.json")) as f:
        fin_df = pd.DataFrame(json.load(f)["values"], columns=["date", "debt"])
    fin_s = pd.Series(dict(zip(fin_df["date"].str.slice(0, 7), fin_df["debt"]))).reindex(all_ym).ffill()
    fin_s_pit = fin_s.shift(1)  # 1-month publication lag for strict PIT
    fin_yoy_pit = (fin_s_pit / fin_s_pit.shift(12) - 1.0) * 100.0
    fin_z_yoy = (fin_yoy_pit - fin_yoy_pit.rolling(36, min_periods=18).mean()) / fin_yoy_pit.rolling(36, min_periods=18).std()

    with open(os.path.join(BASE_DIR, "data", "fred", "WRESBAL.json")) as f:
        wres = pd.Series({pd.Timestamp(r[0]): float(r[1]) for r in json.load(f)["values"] if r[1] is not None}).sort_index()

    COST_BP = 0.0010

    def sim_strategy(cond_fn):
        prev_asset = None
        rows = []
        W = 1.0
        pts_nav = {}
        for t in months_214:
            hold_ym = (t + pd.offsets.MonthBegin(1)).strftime("%Y-%m")
            sig_ym = t.strftime("%Y-%m")
            sep_on = bool(reg_map[t]["sep_on"])
            zc = float(bofa_z_low.get(sig_ym, np.nan))
            ze = float(es_z.get(sig_ym, np.nan)) if hold_ym >= "2011-01" else np.nan
            zf_y = float(fin_z_yoy.get(sig_ym, np.nan))
            fyoy = float(fin_yoy_pit.get(sig_ym, 0.0))
            cz = (zc + ze) / 2.0 if pd.notna(ze) else np.nan

            w_sub = wres[wres.index <= t - pd.Timedelta(days=2)]
            w_yoy = (w_sub.iloc[-1] / w_sub.iloc[-52] - 1.0) * 100.0 if len(w_sub) >= 53 else 0.0

            info = {"ym": hold_ym, "zc": zc, "ze": ze, "zf_y": zf_y, "fyoy": fyoy, "cz": cz, "w_yoy": w_yoy}

            if not sep_on:
                asset = "CASH"
            elif cond_fn(info):
                asset = "QQQ"
            else:
                asset = "TQQQ"

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

            if asset == "TQQQ":
                df_act = df_tqqq_full
                p0 = float(df_act.loc[:d0, "o"].iloc[-1])
                p1 = float(df_act.loc[:d1, "c"].iloc[-1]) if t == pd.Timestamp("2026-09-30") else float(df_act.loc[:d1, "o"].iloc[-1])
                gross = p1 / p0 - 1.0
            elif asset == "QQQ":
                df_act = df_qqq
                p0 = float(df_act.loc[:d0, "o"].iloc[-1])
                p1 = float(df_act.loc[:d1, "c"].iloc[-1]) if t == pd.Timestamp("2026-09-30") else float(df_act.loc[:d1, "o"].iloc[-1])
                gross = p1 / p0 - 1.0
            else:
                gross = float(reg_map[t]["ret_sgov_actual"])
                df_act = df_sgov if d0 >= pd.Timestamp("2020-06-01") else df_bil

            to = 1.0 if prev_asset is None else (2.0 if prev_asset != asset else 0.0)
            prev_asset = asset
            net = (1.0 + gross) * ((1.0 - COST_BP) ** to) - 1.0 if to > 0 else gross

            c0 = float(df_act.loc[:d0, "c"].iloc[-1])
            for d in m_days:
                cd = float(df_act.loc[:d, "c"].iloc[-1])
                pts_nav[d] = W * (cd / c0)
            W = W * (1.0 + net)
            pts_nav[d1] = W

            rows.append({
                "t": t.strftime("%Y-%m-%d"),
                "ym": hold_ym,
                "sep_on": sep_on,
                "wresbal_yoy": round(w_yoy, 2),
                "finra_yoy_pit": round(fyoy, 2),
                "z_finra_yoy_pit": round(zf_y, 3) if pd.notna(zf_y) else np.nan,
                "crowding_z_pit": round(cz, 3) if pd.notna(cz) else np.nan,
                "asset": asset,
                "net_ret": net,
                "rf_m": float(reg_map[t]["rf_m"]),
            })
        df_L = pd.DataFrame(rows)
        s_nav = pd.Series(pts_nav).sort_index()

        def calc_stats(sub_L, d_start):
            r = sub_L["net_ret"].values
            rf = sub_L["rf_m"].values
            cagr = (np.prod(1.0 + r) ** (12.0 / len(r)) - 1.0) * 100
            sh = (np.mean(r - rf) / np.std(r, ddof=1) * np.sqrt(12.0))
            eq = np.cumprod(1.0 + r)
            m_dd = np.min(eq / np.maximum.accumulate(eq) - 1.0) * 100
            nav_sub = s_nav[s_nav.index >= d_start]
            d_dd = float((nav_sub / nav_sub.cummax() - 1.0).min()) * 100
            r_nc = sub_L[~sub_L["ym"].isin(["2020-02", "2020-03"])]["net_ret"].values
            cagr_nc = (np.prod(1.0 + r_nc) ** (12.0 / len(r_nc)) - 1.0) * 100
            return cagr, cagr_nc, sh, m_dd, d_dd

        s214 = calc_stats(df_L, "2009-01-01")
        s190 = calc_stats(df_L[df_L["ym"] >= "2011-01"], "2011-01-01")
        trig = df_L[df_L["asset"] == "QQQ"]["ym"].tolist()
        return df_L, s214, s190, trig

    summary = []
    configs = [
        ("0. Baseline: TQQQ + SEP Only", lambda x: False),
        ("1. Gen-1 (Old): Crowding_Z >= 1.2 (Ignores Fed Reserves)", lambda x: pd.notna(x["cz"]) and x["cz"] >= 1.2),
    ]
    for th in [0.75, 0.80, 0.85, 0.90, 0.95, 1.00, 1.05, 1.10, 1.15, 1.20]:
        configs.append((f"2. Gen-2 (Reserves Drain + Crowding_Z >= {th:.2f})", lambda x, th=th: pd.notna(x["cz"]) and x["cz"] >= th and x["w_yoy"] < 0.0))
    for th in [0.75, 0.80, 0.85, 0.90, 0.95, 1.00, 1.05, 1.10, 1.15, 1.20]:
        configs.append((f"3. Gen-3 (Reserves Drain + FINRA Not Washed Out + Crowding_Z >= {th:.2f})", lambda x, th=th: pd.notna(x["cz"]) and x["cz"] >= th and x["w_yoy"] < 0.0 and x["fyoy"] > -5.0))

    for name, fn in configs:
        df_L, s214, s190, trig = sim_strategy(fn)
        if "Gen-3" in name and "0.85" in name:
            df_L.to_csv(os.path.join(OUT_DIR, "tqqq_gen3_capital_liquidity_214m_ledger.csv"), index=False)
        summary.append({
            "strategy": name,
            "n_delev_months": len(trig),
            "cagr_214m": round(s214[0], 2),
            "ex_covid_cagr_214m": round(s214[1], 2),
            "sharpe_214m": round(s214[2], 3),
            "monthly_maxdd_214m": round(s214[3], 2),
            "daily_maxdd_214m": round(s214[4], 2),
            "cagr_190m_2011_2026": round(s190[0], 2),
            "ex_covid_cagr_190m": round(s190[1], 2),
            "delev_months": " ".join(trig),
        })

    df_sum = pd.DataFrame(summary)
    df_sum.to_csv(os.path.join(OUT_DIR, "tqqq_capital_liquidity_upgrade_summary.csv"), index=False)
    print(df_sum.drop(columns=["delev_months"]).to_string(index=False))


if __name__ == "__main__":
    run_capital_liquidity_audit()
