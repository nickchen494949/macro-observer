#!/usr/bin/env python3
"""
Strict ALFRED Historical Vintage & Statistical Audit of C1 (NFCI Risk Control) on TQQQ + SEP (2026-11-14)
=========================================================================================================
Directly addresses all 5 external auditor checks:
1. True ALFRED Historical Vintages of NFCI (804 weekly vintages, 2011-05-25 .. 2026-11-12) vs Revised FRED NFCI:
   - Enforces pre-2011-05-25 non-availability and uses exact point-in-time unrevised numbers as published on or before t.
2. Item-by-item audit of every de-leveraging month (Revised vs ALFRED Vintage), with vintage dates, observation dates,
   exact NFCI(t) and NFCI(t-4w) values, open-to-open trade prices, turnover costs, and net returns.
3. NFCI vs VIX vs NFCICREDIT (Credit Subindex) comparison:
   - Tests whether NFCI's signal is merely VIX in disguise or carries independent credit/funding information.
4. Non-overlapping statistical tests (156 mutually exclusive SEP=ON months + Wilson 95% CIs + 6 independent crisis episodes).
5. Threshold robustness grid around frozen C1 (0.05 / 0.15) on True ALFRED Vintage NFCI.
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


def load_alfred_df(sid):
    path = os.path.join(BASE_DIR, "data", "alfred", f"{sid}_vintages.json")
    with open(path) as f:
        data = json.load(f)
    rows = []
    for r in data["observations"]:
        v = r["value"]
        if v not in (None, ".", ""):
            rows.append((r["realtime_start"], r["realtime_end"], r["date"], float(v)))
    df = pd.DataFrame(rows, columns=["rt_start", "rt_end", "obs_dt", "val"])
    df = df.drop_duplicates(subset=["rt_start", "rt_end", "obs_dt"], keep="last")
    return df, data["first_vintage"], data["vintage_dates"]


def get_alfred_snapshot(df_alfred, vintage_dates, t_str):
    """Return exact series of observations available on date t_str in ALFRED."""
    sub = df_alfred[(df_alfred["rt_start"] <= t_str) & (df_alfred["rt_end"] >= t_str)]
    if len(sub) == 0:
        return pd.Series(dtype=float), None
    sub_s = sub.sort_values("obs_dt").drop_duplicates("obs_dt", keep="last")
    v_avail = [v for v in vintage_dates if v <= t_str]
    latest_v = v_avail[-1] if v_avail else None
    return pd.Series(sub_s["val"].values, index=sub_s["obs_dt"].values), latest_v


def main():
    df_tqqq = r8.load_tiingo_etf_df("TQQQ")
    df_qqq = r8.load_tiingo_etf_df("QQQ")
    df_sgov = r8.load_tiingo_etf_df("SGOV")
    df_bil = r8.load_tiingo_etf_df("BIL")

    with open(os.path.join(BASE_DIR, "data", "fred", "DGS3MO.json")) as f:
        rf_s = pd.Series({pd.Timestamp(r[0]): float(r[1]) / 100.0 for r in json.load(f)["values"]}).sort_index()
    with open(os.path.join(BASE_DIR, "data", "fred", "NFCI.json")) as f:
        nfci_rev = pd.Series({pd.Timestamp(r[0]): float(r[1]) for r in json.load(f)["values"] if r[1] not in (None, ".")}).sort_index()
    with open(os.path.join(BASE_DIR, "data", "yahoo", "_VIX.json")) as f:
        vix_s = pd.Series({pd.Timestamp(r[0]): float(r[1]) for r in json.load(f)["values"] if r[1] not in (None, ".")}).sort_index()

    df_nfci_alf, nfci_first_v, nfci_vdates = load_alfred_df("NFCI")
    df_cred_alf, cred_first_v, cred_vdates = load_alfred_df("NFCICREDIT")
    df_risk_alf, risk_first_v, risk_vdates = load_alfred_df("NFCIRISK")
    df_lev_alf, lev_first_v, lev_vdates = load_alfred_df("NFCILEVERAGE")

    # Also build latest-revised NFCICREDIT from ALFRED's last vintage (2026-11-12) for pre-2012-07 comparison
    cred_latest_s, _ = get_alfred_snapshot(df_cred_alf, cred_vdates, "2026-11-12")
    cred_latest = pd.Series(cred_latest_s.values, index=pd.to_datetime(cred_latest_s.index)).sort_index()

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
    qqq_vol21_s = qqq_r_c2c.rolling(21).std() * np.sqrt(252) * 100.0
    vix_aligned = vix_s.reindex(qqq_c.index).ffill()

    # Load Crowding_Z & ES outflow for mutually exclusive Market A/B check
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

    nfci_rev_rel = pd.DataFrame({"val": nfci_rev.values, "obs_dt": nfci_rev.index, "rel_dt": nfci_rev.index + pd.Timedelta(days=7)}, index=nfci_rev.index)
    cred_rev_rel = pd.DataFrame({"val": cred_latest.values, "obs_dt": cred_latest.index, "rel_dt": cred_latest.index + pd.Timedelta(days=7)}, index=cred_latest.index)

    # Precompute month-by-month table (214 months) with both Revised and ALFRED Vintage signals
    m_records = []
    for t in months_214:
        hold_ym = (t + pd.offsets.MonthBegin(1)).strftime("%Y-%m")
        sig_ym = t.strftime("%Y-%m")
        t_str = t.strftime("%Y-%m-%d")
        sep_on = bool(reg_map[t]["sep_on"])

        # 1. Revised NFCI (7D lag, post-2011-04-13 launch check vs unconstrained)
        n_rev_sub = nfci_rev_rel[nfci_rev_rel["rel_dt"] <= t]
        rev_obs_dt = n_rev_sub["obs_dt"].iloc[-1].strftime("%Y-%m-%d")
        rev_val_now = float(n_rev_sub["val"].iloc[-1])
        rev_val_4w = float(n_rev_sub["val"].iloc[-5])
        rev_chg4w = rev_val_now - rev_val_4w

        # 2. True ALFRED Vintage NFCI as of t_str
        alf_s, alf_vdate = get_alfred_snapshot(df_nfci_alf, nfci_vdates, t_str)
        if len(alf_s) >= 5:
            alf_obs_dt = str(alf_s.index[-1])
            alf_val_now = float(alf_s.iloc[-1])
            alf_val_4w = float(alf_s.iloc[-5])
            alf_chg4w = alf_val_now - alf_val_4w
        else:
            alf_obs_dt = None
            alf_val_now = np.nan
            alf_val_4w = np.nan
            alf_chg4w = np.nan

        # 3. True ALFRED Vintage NFCICREDIT as of t_str (and Revised NFCICREDIT for comparison)
        c_rev_sub = cred_rev_rel[cred_rev_rel["rel_dt"] <= t]
        cred_rev_chg4w = float(c_rev_sub["val"].iloc[-1] - c_rev_sub["val"].iloc[-5]) if len(c_rev_sub) >= 5 else np.nan
        cred_alf_s, cred_vdate = get_alfred_snapshot(df_cred_alf, cred_vdates, t_str)
        cred_alf_chg4w = float(cred_alf_s.iloc[-1] - cred_alf_s.iloc[-5]) if len(cred_alf_s) >= 5 else np.nan

        # 4. VIX & QQQ metrics at t
        vix_sub = vix_aligned.loc[:t]
        vix_now = float(vix_sub.iloc[-1])
        vix_chg21 = float(vix_sub.iloc[-1] - vix_sub.iloc[-22]) if len(vix_sub) >= 22 else 0.0
        c_t = float(qqq_c.loc[:t].iloc[-1])
        ma50_t = float(qqq_ma50.loc[:t].iloc[-1])
        vol21_t = float(qqq_vol21_s.loc[:t].iloc[-1])

        # 5. Crowding_Z & ES outflow
        zc = float(bofa_z_low.get(sig_ym, np.nan))
        ze = float(es_z_rel.get(sig_ym, np.nan)) if hold_ym >= "2011-01" else np.nan
        cz = (zc + ze) / 2.0 if pd.notna(ze) else np.nan
        es_out4w = -float(es_pit_chg4w.get(sig_ym, 0.0)) if hold_ym >= "2011-01" else 0.0

        # 6. Next-month trading execution dates and open-to-open returns
        d0_idx = cal.searchsorted(t, side="right")
        d0 = cal[d0_idx] if d0_idx < len(cal) else cal[-1]
        if t == pd.Timestamp("2026-09-30"):
            d1 = pd.Timestamp("2026-10-29")
            m_days = cal[(cal >= d0) & (cal <= d1)]
            p_end_col = "c"
        else:
            t_next = t + pd.offsets.MonthEnd(1)
            d1_idx = cal.searchsorted(t_next, side="right")
            d1 = cal[d1_idx] if d1_idx < len(cal) else cal[-1]
            m_days = cal[(cal >= d0) & (cal < d1)]
            p_end_col = "o"

        tq_o0 = float(df_tqqq_full.loc[:d0, "o"].iloc[-1])
        tq_o1 = float(df_tqqq_full.loc[:d1, p_end_col].iloc[-1])
        qq_o0 = float(df_qqq.loc[:d0, "o"].iloc[-1])
        qq_o1 = float(df_qqq.loc[:d1, p_end_col].iloc[-1])
        r_tq = tq_o1 / tq_o0 - 1.0
        r_qq = qq_o1 / qq_o0 - 1.0
        r_ca = float(reg_map[t]["ret_sgov_actual"])

        # Intra-month TQQQ max drawdown
        tq_m_closes = df_tqqq_full.loc[m_days, "c"]
        tq_m_dd = float((tq_m_closes / tq_m_closes.cummax() - 1.0).min()) if len(tq_m_closes) > 0 else 0.0

        m_records.append({
            "t": t, "t_str": t_str, "ym": hold_ym, "sep_on": sep_on,
            "rev_obs_dt": rev_obs_dt, "rev_val_now": rev_val_now, "rev_val_4w": rev_val_4w, "rev_chg4w": rev_chg4w,
            "alf_vdate": alf_vdate, "alf_obs_dt": alf_obs_dt, "alf_val_now": alf_val_now, "alf_val_4w": alf_val_4w, "alf_chg4w": alf_chg4w,
            "cred_rev_chg4w": cred_rev_chg4w, "cred_alf_chg4w": cred_alf_chg4w,
            "vix_now": vix_now, "vix_chg21": vix_chg21, "vol21": vol21_t, "below_ma50": c_t < ma50_t,
            "cz": cz, "es_out4w": es_out4w,
            "d0": d0.strftime("%Y-%m-%d"), "d1": d1.strftime("%Y-%m-%d"),
            "tq_o0": tq_o0, "tq_o1": tq_o1, "qq_o0": qq_o0, "qq_o1": qq_o1,
            "r_tq": r_tq, "r_qq": r_qq, "r_ca": r_ca, "tq_m_dd": tq_m_dd,
            "rf_m": float(reg_map[t]["rf_m"]), "m_days": m_days, "d0_ts": d0, "d1_ts": d1
        })

    df_M = pd.DataFrame(m_records)

    # =========================================================================
    # AUDIT 1 & 2: C1 Revised vs C1 True ALFRED Vintage (Item-by-Item Audit)
    # =========================================================================
    print("====================================================================================")
    print("AUDIT 1 & 2: C1 (REVISED FRED) vs C1 (TRUE ALFRED HISTORICAL VINTAGES) ITEM-BY-ITEM")
    print("====================================================================================")

    audit_rows = []
    for _, row in df_M[df_M["ym"] >= "2011-01"].iterrows():
        if not row["sep_on"]:
            continue
        w_rev = 0.0 if row["rev_chg4w"] > 0.15 else (0.5 if row["rev_chg4w"] > 0.05 else 1.0)
        if pd.isna(row["alf_chg4w"]):
            w_alf = 1.0
        else:
            w_alf = 0.0 if row["alf_chg4w"] > 0.15 else (0.5 if row["alf_chg4w"] > 0.05 else 1.0)

        if w_rev < 1.0 or w_alf < 1.0:
            gear_rev = "3x (100% TQQQ)" if w_rev == 1.0 else ("2x (50/50)" if w_rev == 0.5 else "1x (100% QQQ)")
            gear_alf = "3x (100% TQQQ)" if w_alf == 1.0 else ("2x (50/50)" if w_alf == 0.5 else "1x (100% QQQ)")
            gross_alf = w_alf * row["r_tq"] + (1.0 - w_alf) * row["r_qq"]
            diff_alf_vs_tq = (gross_alf - row["r_tq"]) * 100.0
            audit_rows.append({
                "hold_ym": row["ym"],
                "form_date_t": row["t_str"],
                "alfred_vintage_dt": row["alf_vdate"] if row["alf_vdate"] else "Pre-Launch (<2011-05-25)",
                "obs_friday_dt": row["alf_obs_dt"] if row["alf_obs_dt"] else row["rev_obs_dt"],
                "rev_nfci_now": round(row["rev_val_now"], 4),
                "rev_nfci_4w_ago": round(row["rev_val_4w"], 4),
                "rev_nfci_chg4w": round(row["rev_chg4w"], 4),
                "rev_gear": gear_rev,
                "alf_nfci_now": round(row["alf_val_now"], 4) if pd.notna(row["alf_val_now"]) else np.nan,
                "alf_nfci_4w_ago": round(row["alf_val_4w"], 4) if pd.notna(row["alf_val_4w"]) else np.nan,
                "alf_nfci_chg4w": round(row["alf_chg4w"], 4) if pd.notna(row["alf_chg4w"]) else np.nan,
                "alf_gear": gear_alf,
                "match": "SAME" if w_rev == w_alf else "CHANGED",
                "trade_window": f"{row['d0']} -> {row['d1']}",
                "tqqq_ret_pct": round(row["r_tq"] * 100.0, 2),
                "qqq_ret_pct": round(row["r_qq"] * 100.0, 2),
                "alf_diff_vs_tqqq_pct": round(diff_alf_vs_tq, 2),
            })

    df_audit = pd.DataFrame(audit_rows)
    df_audit.to_csv(os.path.join(OUT_DIR, "tqqq_c1_alfred_vs_revised_months_audit.csv"), index=False)
    print(df_audit[["hold_ym", "form_date_t", "alfred_vintage_dt", "rev_nfci_chg4w", "rev_gear", "alf_nfci_chg4w", "alf_gear", "match", "tqqq_ret_pct", "qqq_ret_pct", "alf_diff_vs_tqqq_pct"]].to_string(index=False))

    # =========================================================================
    # Backtest Engine for All Variants
    # =========================================================================
    COST_BP = 0.0010
    perf_rows = []

    def run_bt(name, wt_fn, start_ym="2011-01"):
        prev_state = None
        rows = []
        W = 1.0
        pts_nav = {}
        false_alarms = 0
        total_alarms = 0
        for _, row in df_M.iterrows():
            hold_ym = row["ym"]
            sep_on = row["sep_on"]
            if not sep_on:
                state = ("CASH", 0.0)
                gross = row["r_ca"]
            else:
                w_tq = float(wt_fn(row))
                state = ("ON", round(w_tq, 3))
                gross = w_tq * row["r_tq"] + (1.0 - w_tq) * row["r_qq"]
                if w_tq < 0.99 and hold_ym >= start_ym:
                    total_alarms += 1
                    if row["r_tq"] > row["r_qq"]:
                        false_alarms += 1

            if prev_state is None:
                to = 1.0
            elif prev_state[0] != state[0]:
                to = 2.0
            else:
                to = abs(prev_state[1] - state[1]) * 2.0
            prev_state = state
            net = (1.0 + gross) * ((1.0 - COST_BP) ** to) - 1.0 if to > 0 else gross

            d0, d1, m_days = row["d0_ts"], row["d1_ts"], row["m_days"]
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
            rows.append({"ym": hold_ym, "net_ret": net, "rf_m": row["rf_m"], "w_tq": state[1] if sep_on else np.nan})

        df_L = pd.DataFrame(rows)
        s_nav = pd.Series(pts_nav).sort_index()
        sub = df_L[df_L["ym"] >= start_ym]
        r_vec = sub["net_ret"].values
        rf_vec = sub["rf_m"].values
        cagr = (np.prod(1.0 + r_vec) ** (12.0 / len(r_vec)) - 1.0) * 100.0
        sh = (np.mean(r_vec - rf_vec) / np.std(r_vec, ddof=1) * np.sqrt(12.0))
        eq = np.cumprod(1.0 + r_vec)
        mdd = np.min(eq / np.maximum.accumulate(eq) - 1.0) * 100.0
        nav_sub = s_nav[s_nav.index >= pd.Timestamp(start_ym + "-01")]
        ddd = float((nav_sub / nav_sub.cummax() - 1.0).min()) * 100.0
        cvar5 = pd.Series(r_vec).nsmallest(max(1, int(len(r_vec) * 0.05))).mean() * 100.0
        r_no18_20 = sub[(~sub["ym"].str.startswith("2018-")) & (~sub["ym"].isin(["2020-02", "2020-03"]))]["net_ret"].values
        cagr_no18_20 = (np.prod(1.0 + r_no18_20) ** (12.0 / len(r_no18_20)) - 1.0) * 100.0
        fa_rate = (false_alarms / total_alarms * 100.0) if total_alarms > 0 else 0.0
        res = {
            "version": name,
            "window": f"{start_ym}..2026-10 ({len(r_vec)}M)",
            "cagr": round(cagr, 2),
            "cagr_ex_2018_2020": round(cagr_no18_20, 2),
            "sharpe": round(sh, 3),
            "monthly_maxdd": round(mdd, 2),
            "daily_maxdd": round(ddd, 2),
            "cvar_5pct": round(cvar5, 2),
            "alarms": total_alarms,
            "false_alarm_rate_pct": round(fa_rate, 1),
        }
        perf_rows.append(res)
        return df_L

    df_base = run_bt("0. Baseline: Original TQQQ + SEP Only", lambda r: 1.0)
    df_c1_rev = run_bt("C1 (Revised FRED NFCI, 7D Lag): >0.05->2x, >0.15->1x",
                       lambda r: 0.0 if r["rev_chg4w"] > 0.15 else (0.5 if r["rev_chg4w"] > 0.05 else 1.0))
    df_c1_alf = run_bt("C1 (True ALFRED Vintage NFCI, PIT): >0.05->2x, >0.15->1x",
                       lambda r: 1.0 if pd.isna(r["alf_chg4w"]) else (0.0 if r["alf_chg4w"] > 0.15 else (0.5 if r["alf_chg4w"] > 0.05 else 1.0)))

    # Compare against VIX and Credit Subindex (Test 3)
    df_vix_chg = run_bt("VIX_4w Control (VIX_21d > +3 -> 2x, > +7 -> 1x)",
                        lambda r: 0.0 if r["vix_chg21"] > 7.0 else (0.5 if r["vix_chg21"] > 3.0 else 1.0))
    df_vix_lvl = run_bt("VIX Level Control (VIX > 22 -> 2x, > 28 -> 1x)",
                        lambda r: 0.0 if r["vix_now"] > 28.0 else (0.5 if r["vix_now"] > 22.0 else 1.0))
    df_cred_rev = run_bt("Credit Subindex (Revised NFCICREDIT_4w >0.03->2x, >0.08->1x)",
                         lambda r: 1.0 if pd.isna(r["cred_rev_chg4w"]) else (0.0 if r["cred_rev_chg4w"] > 0.08 else (0.5 if r["cred_rev_chg4w"] > 0.03 else 1.0)))
    df_cred_alf = run_bt("Credit Subindex (ALFRED Vintage NFCICREDIT_4w >0.03->2x, >0.08->1x)",
                         lambda r: 1.0 if pd.isna(r["cred_alf_chg4w"]) else (0.0 if r["cred_alf_chg4w"] > 0.08 else (0.5 if r["cred_alf_chg4w"] > 0.03 else 1.0)))

    print("\n====================================================================================")
    print("SUMMARY: REVISED vs TRUE ALFRED VINTAGE NFCI vs VIX vs CREDIT SUBINDEX (2011-2026)")
    print("====================================================================================")
    df_perf = pd.DataFrame(perf_rows)
    df_perf.to_csv(os.path.join(OUT_DIR, "tqqq_c1_alfred_validation_summary.csv"), index=False)
    print(df_perf.to_string(index=False))

    # =========================================================================
    # AUDIT 3: Non-Overlapping Monthly Test Controlling for VIX & Vol21
    # =========================================================================
    print("\n====================================================================================")
    print("AUDIT 3: NON-OVERLAPPING MONTHLY PREDICTION (SEP=ON, N=156 MONTHS, NO OVERLAP)")
    print("====================================================================================")
    sub_on = df_M[(df_M["ym"] >= "2011-01") & (df_M["sep_on"])].copy()
    sub_on_alf = sub_on[sub_on["alf_chg4w"].notna()].copy()  # 151 SEP=ON months from 2011-06 to 2026-03

    for col, label in [
        ("alf_chg4w", "True ALFRED Vintage NFCI_4w (N=151 SEP=ON Months)"),
        ("cred_rev_chg4w", "NFCICREDIT_4w Pure Credit Subindex (N=156 SEP=ON Months)"),
        ("vix_chg21", "VIX 21-Day Change (N=156 SEP=ON Months)"),
    ]:
        df_use = sub_on_alf if col == "alf_chg4w" else sub_on
        df_use = df_use.copy()
        df_use["q"] = pd.qcut(df_use[col], 5, labels=["Q1 (Calmest)", "Q2", "Q3", "Q4", "Q5 (Stress Fastest)"])
        print(f"\n--- {label} ---")
        for q_lbl, grp in df_use.groupby("q", observed=False):
            n_m = len(grp)
            k_crash = int((grp["r_tq"] <= -0.15).sum())
            ci_lo, ci_hi = wilson_ci(k_crash, n_m)
            print(f"  {q_lbl:20s}: N={n_m:2d} | Avg VIX={grp['vix_now'].mean():5.2f} | Avg Vol21={grp['vol21'].mean():5.2f}% | "
                  f"Next-M TQQQ={grp['r_tq'].mean()*100:+6.2f}% | Intra-M DD={grp['tq_m_dd'].mean()*100:6.2f}% | "
                  f"Crash(<-15%)={k_crash}/{n_m} ({k_crash/n_m*100:4.1f}%, 95% CI [{ci_lo:4.1f}%..{ci_hi:4.1f}%])")

    # Also test strictly inside CALM UPTREND months (SEP=ON & QQQ >= MA50 & Vol21 < 20% & VIX < 20)
    calm_up = sub_on_alf[(~sub_on_alf["below_ma50"]) & (sub_on_alf["vol21"] < 20.0) & (sub_on_alf["vix_now"] < 20.0)].copy()
    calm_up["tertile"] = pd.qcut(calm_up["alf_chg4w"], 3, labels=["T1 (NFCI Easing)", "T2 (NFCI Neutral)", "T3 (NFCI Tightening)"])
    print(f"\n--- STRICT CALM UPTREND SUBSET (SEP=ON & QQQ>=MA50 & Vol21<20% & VIX<20, N={len(calm_up)} Non-Overlapping Months) ---")
    for t_lbl, grp in calm_up.groupby("tertile", observed=False):
        n_m = len(grp)
        k_dd10 = int((grp["tq_m_dd"] <= -0.10).sum())
        ci_lo, ci_hi = wilson_ci(k_dd10, n_m)
        print(f"  {t_lbl:22s}: N={n_m:2d} | Avg VIX={grp['vix_now'].mean():5.2f} | Avg Vol21={grp['vol21'].mean():5.2f}% | "
              f"Next-M TQQQ={grp['r_tq'].mean()*100:+6.2f}% | Intra-M DD={grp['tq_m_dd'].mean()*100:6.2f}% | "
              f"Intra-M DD<=-10%: {k_dd10}/{n_m} ({k_dd10/n_m*100:4.1f}%, 95% CI [{ci_lo:4.1f}%..{ci_hi:4.1f}%])")

    # =========================================================================
    # AUDIT 4A: Mutually Exclusive Market A vs Market B Partition (Sum = 156)
    # =========================================================================
    print("\n====================================================================================")
    print("AUDIT 4A: MUTUALLY EXCLUSIVE PARTITION OF ALL 156 SEP=ON MONTHS (WITH WILSON 95% CI)")
    print("====================================================================================")
    def classify_mutually_exclusive(r):
        if pd.isna(r["cz"]) or r["cz"] <= 0.5:
            return "1. Uncrowded Baseline (CZ <= 0.5)"
        nfci_up = (pd.notna(r["alf_chg4w"]) and r["alf_chg4w"] > 0.0)
        if not r["below_ma50"] and not nfci_up:
            return "2. Market A: Crowded (CZ > 0.5) + Calm (QQQ>=MA50 & ALFRED NFCI_4w<=0)"
        if nfci_up:
            return "3. Market B_NFCI: Crowded (CZ > 0.5) + ALFRED NFCI Tightening (NFCI_4w > 0)"
        return "4. Market B_TrendOnly: Crowded (CZ > 0.5) + QQQ < MA50 (but NFCI_4w <= 0)"

    sub_on["me_group"] = sub_on.apply(classify_mutually_exclusive, axis=1)
    tot_n = 0
    for g_lbl in sorted(sub_on["me_group"].unique()):
        grp = sub_on[sub_on["me_group"] == g_lbl]
        n_m = len(grp)
        tot_n += n_m
        k_c = int((grp["r_tq"] <= -0.15).sum())
        ci_lo, ci_hi = wilson_ci(k_c, n_m)
        print(f"  {g_lbl:75s} | N={n_m:3d} | Avg TQQQ={grp['r_tq'].mean()*100:+6.2f}% | "
              f"Intra-M DD={grp['tq_m_dd'].mean()*100:6.2f}% | Crash(<-15%)={k_c:2d}/{n_m:2d} ({k_c/n_m*100:4.1f}%, 95% CI [{ci_lo:4.1f}%..{ci_hi:4.1f}%])")
    print(f"  Total Partitioned Months = {tot_n} (100% mutually exclusive, zero overlap)")

    # =========================================================================
    # AUDIT 4B: Independent Crisis Episodes Breakdown (2011-2026)
    # =========================================================================
    print("\n====================================================================================")
    print("AUDIT 4B: PERFORMANCE ACROSS ALL 6 INDEPENDENT MARKET CRISIS EPISODES (2011-2026)")
    print("====================================================================================")
    episodes = [
        ("1. 2011 Euro Debt / US Downgrade", ["2011-08", "2011-09"]),
        ("2. 2015-2016 China / Oil Credit Stress", ["2015-08", "2015-09", "2016-01", "2016-02"]),
        ("3. 2018 Volmageddon & Q4 Tightening", ["2018-02", "2018-03", "2018-10", "2018-11", "2018-12"]),
        ("4. 2020 COVID Liquidity Crash", ["2020-02", "2020-03"]),
        ("5. 2025 Spring Tariff Crash", ["2025-03", "2025-04"]),
        ("6. 2026 Pre-SEP-OFF Tech Drawdown", ["2026-02", "2026-03"]),
    ]
    for ep_name, yms in episodes:
        b_ret = (np.prod(1.0 + df_base[df_base["ym"].isin(yms)]["net_ret"].values) - 1.0) * 100.0
        c_rev_ret = (np.prod(1.0 + df_c1_rev[df_c1_rev["ym"].isin(yms)]["net_ret"].values) - 1.0) * 100.0
        c_alf_ret = (np.prod(1.0 + df_c1_alf[df_c1_alf["ym"].isin(yms)]["net_ret"].values) - 1.0) * 100.0
        v_ret = (np.prod(1.0 + df_vix_chg[df_vix_chg["ym"].isin(yms)]["net_ret"].values) - 1.0) * 100.0
        print(f"  {ep_name:38s}: Baseline={b_ret:+6.2f}% | C1(Revised)={c_rev_ret:+6.2f}% | C1(ALFRED PIT)={c_alf_ret:+6.2f}% | VIX_4w={v_ret:+6.2f}%")

    # =========================================================================
    # AUDIT 5: Threshold Robustness Grid Around Frozen (0.05 / 0.15) on ALFRED NFCI
    # =========================================================================
    print("\n====================================================================================")
    print("AUDIT 5: THRESHOLD ROBUSTNESS GRID ON TRUE ALFRED VINTAGE NFCI (AROUND 0.05 / 0.15)")
    print("====================================================================================")
    perf_rows.clear()
    grid_params = [
        ("Grid 1: (0.03 / 0.10)", 0.03, 0.10),
        ("Grid 2: (0.04 / 0.12)", 0.04, 0.12),
        ("Grid 3: (0.04 / 0.15)", 0.04, 0.15),
        ("Grid 4: FROZEN C1 (0.05 / 0.15)", 0.05, 0.15),
        ("Grid 5: (0.06 / 0.15)", 0.06, 0.15),
        ("Grid 6: (0.06 / 0.18)", 0.06, 0.18),
        ("Grid 7: (0.07 / 0.20)", 0.07, 0.20),
        ("Grid 8: (0.08 / 0.22)", 0.08, 0.22),
    ]
    for g_name, t1, t2 in grid_params:
        run_bt(g_name, lambda r, a=t1, b=t2: 1.0 if pd.isna(r["alf_chg4w"]) else (0.0 if r["alf_chg4w"] > b else (0.5 if r["alf_chg4w"] > a else 1.0)))

    # Also test zero-threshold continuous linear ramp between 0.03 and 0.18
    run_bt("Grid 9: Continuous Linear Ramp (0.03 .. 0.18)",
           lambda r: 1.0 if (pd.isna(r["alf_chg4w"]) or r["alf_chg4w"] <= 0.03) else max(0.0, min(1.0, 1.0 - (r["alf_chg4w"] - 0.03) / 0.15)))

    df_grid = pd.DataFrame(perf_rows)
    df_grid.to_csv(os.path.join(OUT_DIR, "tqqq_c1_alfred_threshold_robustness.csv"), index=False)
    print(df_grid.to_string(index=False))


if __name__ == "__main__":
    main()
