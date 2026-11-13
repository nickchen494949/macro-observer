#!/usr/bin/env python3
"""
Standalone Apples-to-Apples Audit of TQQQ + SEP + Crowding_Z vs V4 Latest (2026-11-13)
======================================================================================
Addresses all 6 points of the External Audit Report:
1. Strict CFTC TFF Publication Date PIT Gate:
   - CFTC Traders in Financial Futures (TFF) report launched on 2010-07-22 and backfilled on 2010-12-03.
   - Therefore, Crowding_Z is strictly disabled (`NaN`) before holding month `2011-01` (formation `2010-12-31`).
2. Strict BofA FMS Monthly Survey PIT Audit:
   - Uses verified mid-month BofA FMS survey dates (including verified 2018-02 `4.7%`, 2018-09 `5.1%`, 2020-02 `4.0%`, 2020-03 `5.1%`).
3. Unified Apples-to-Apples Execution Engine (`Fix #8` standard):
   - T+1 adjusted Open execution (`d0 -> d1`)
   - Actual Tiingo market `TQQQ` (`adjOpen`, `adjClose`) from launch `2010-02-11` onward + exact daily-reset 3x QQQ (`0.95%/yr` fee + `2x` daily borrow `DGS3MO + 50bp`) for the 13 pre-launch months (`2009-01..2010-02`)
   - Actual Tiingo `SGOV` / `BIL` cash return when `SEP = OFF`
   - `10 bp/side` turnover cost on regime/gear switches
   - Reports 213M (`2009-01..2026-09`), 214M (`2009-01..2026-10`), and 190M (`2011-01..2026-10` 100% live TQQQ & live CFTC)
4. Month-by-Month & Event-Deletion Attribution (`Ex-COVID 2020-02 & 2020-03`).
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


def run_audit():
    df_tqqq = r8.load_tiingo_etf_df("TQQQ")
    df_qqq = r8.load_tiingo_etf_df("QQQ")
    df_sgov = r8.load_tiingo_etf_df("SGOV")
    df_bil = r8.load_tiingo_etf_df("BIL")
    with open(os.path.join(BASE_DIR, "data", "fred", "DGS3MO.json")) as f:
        rf_s = pd.Series({pd.Timestamp(r[0]): float(r[1]) / 100.0 for r in json.load(f)["values"]}).sort_index()

    cal = df_qqq.index.sort_values()
    reg_map = v4_eng.reg_map
    months_214 = v4_eng.months_214

    qqq_c = df_qqq["c"]
    qqq_o = df_qqq["o"]
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
        ).set_index("date")
    es_m = es_df["net_oi"].resample("ME").last()
    es_s = pd.Series({d.strftime("%Y-%m"): v for d, v in es_m.items()}).reindex(all_ym).ffill()
    es_z = (es_s - es_s.rolling(36, min_periods=18).mean()) / es_s.rolling(36, min_periods=18).std()

    crowding_z_map = ((bofa_z_low + es_z) / 2.0).to_dict()
    COST_BP = 0.0010

    def sim_3gear(mode="sep_only", th=1.2, pit_cftc=True):
        prev_asset = None
        rows = []
        W = 1.0
        pts_nav = {}
        for t in months_214:
            hold_ym = (t + pd.offsets.MonthBegin(1)).strftime("%Y-%m")
            sig_ym = t.strftime("%Y-%m")
            sep_on = bool(reg_map[t]["sep_on"])
            cz = crowding_z_map.get(sig_ym, np.nan)
            if pit_cftc and hold_ym < "2011-01":
                cz = np.nan

            if mode == "buy_hold":
                asset = "TQQQ"
            elif mode == "sep_only":
                asset = "TQQQ" if sep_on else "CASH"
            elif mode == "3gear":
                if not sep_on:
                    asset = "CASH"
                elif pd.notna(cz) and cz >= th:
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

            if prev_asset is None:
                to = 1.0
            elif prev_asset != asset:
                to = 2.0
            else:
                to = 0.0
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
                "sig_ym": sig_ym,
                "sep_on": sep_on,
                "bofa_cash": float(bofa_s.get(sig_ym, np.nan)),
                "z_cash": float(bofa_z_low.get(sig_ym, np.nan)),
                "es_am_net": float(es_s.get(sig_ym, np.nan)),
                "z_es": float(es_z.get(sig_ym, np.nan)),
                "crowding_z_pit": cz,
                "asset": asset,
                "turnover": to,
                "gross_ret": gross,
                "net_ret": net,
                "rf_m": float(reg_map[t]["rf_m"]),
            })
        return pd.DataFrame(rows), pd.Series(pts_nav).sort_index()

    def report_window(df_L, s_nav, start_ym, end_ym, d_start, d_end):
        sub = df_L[(df_L["ym"] >= start_ym) & (df_L["ym"] <= end_ym)]
        r = sub["net_ret"].values
        rf = sub["rf_m"].values
        cagr = (np.prod(1.0 + r) ** (12.0 / len(r)) - 1.0) * 100
        sh = (np.mean(r - rf) / np.std(r, ddof=1) * np.sqrt(12.0))
        eq = np.cumprod(1.0 + r)
        m_dd = np.min(eq / np.maximum.accumulate(eq) - 1.0) * 100
        nav_sub = s_nav[(s_nav.index >= d_start) & (s_nav.index <= d_end)]
        d_dd = float((nav_sub / nav_sub.cummax() - 1.0).min()) * 100
        sub_nc = sub[~sub["ym"].isin(["2020-02", "2020-03"])]
        r_nc = sub_nc["net_ret"].values
        cagr_nc = (np.prod(1.0 + r_nc) ** (12.0 / len(r_nc)) - 1.0) * 100
        return cagr, sh, m_dd, d_dd, cagr_nc

    L_bh, nav_bh = sim_3gear("buy_hold")
    L_sep, nav_sep = sim_3gear("sep_only")
    L_3g, nav_3g = sim_3gear("3gear", th=1.2, pit_cftc=True)

    L_3g.to_csv(os.path.join(OUT_DIR, "tqqq_crowding_z_strict_pit_214m_ledger.csv"), index=False)

    summary_rows = []
    for th in [1.0, 1.05, 1.1, 1.15, 1.2, 1.25, 1.3, 1.35, 1.4, 1.45, 1.5]:
        L_g, nav_g = sim_3gear("3gear", th=th, pit_cftc=True)
        n_trig = int((L_g["asset"] == "QQQ").sum())
        c213, s213, m213, d213, nc213 = report_window(L_g, nav_g, "2009-01", "2026-09", "2009-01-01", "2026-10-01")
        c214, s214, m214, d214, nc214 = report_window(L_g, nav_g, "2009-01", "2026-10", "2009-01-01", "2026-10-31")
        c190, s190, m190, d190, nc190 = report_window(L_g, nav_g, "2011-01", "2026-10", "2011-01-01", "2026-10-31")
        summary_rows.append({
            "threshold": round(th, 2),
            "triggered_months_in_sep_on": n_trig,
            "cagr_213m": round(c213, 2),
            "cagr_214m": round(c214, 2),
            "sharpe_214m": round(s214, 3),
            "monthly_maxdd_214m": round(m214, 2),
            "daily_maxdd_214m": round(d214, 2),
            "cagr_214m_ex_covid_2020_02_03": round(nc214, 2),
            "cagr_190m_live_2011_2026": round(c190, 2),
            "sharpe_190m_live_2011_2026": round(s190, 3),
        })
    df_sum = pd.DataFrame(summary_rows)
    df_sum.to_csv(os.path.join(OUT_DIR, "tqqq_crowding_z_strict_pit_grid_summary.csv"), index=False)
    print(df_sum.to_string(index=False))


if __name__ == "__main__":
    run_audit()
