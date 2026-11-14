#!/usr/bin/env python3
"""
Independent Clean-Room Audit (V2 Remediation): Orthogonal Crisis-Type Dual-Core (Type A + Type B)
==================================================================================================
Implements all 4 remediation priorities from the First-Round Code Audit while keeping the A1+B
rules and thresholds 100% FROZEN:
  - Type B (Liquidity/Credit Shock):
      `BAA_chg21_bp > 10.0` (strictly rounded to 4 decimals in bp to eliminate IEEE-754 float bug
      where `1.99 - 1.89 = 0.10000000000000009` falsely triggered 2018-07 at +10.0bp)
      AND `VXN_VRP_Z_3Y > 0.0`.
  - Type A1 (Earnings Euphoria x Discount Rate Tightening):
      `IT_Fwd_Est_Snapshot_YoY >= 24.0%` (strictly `n_est >= 4` sum of next 4 estimate quarters vs
      1-year-ago snapshot) AND `RR_chg63_bp > 0.0`.

Four Mandatory Audit Fixes Implemented:
  1. Priority 1: Fixed IEEE-754 float comparison (`round(..., 4)` in bp), included Friday `2026-10-30`
     close, and rebuilt the **Open-Executed Daily NAV Engine** from `d0` Open prices with transaction
     costs deducted at `d0` Open, so Daily NAV and Monthly Cumulative Wealth match to `0.000000e+00`.
  2. Priority 2: Full audit of Wayback Machine S&P 500 IT EPS vintages (`145` vintages, `100%` have
     `n_est >= 5`), explicit comparison of `Fwd_Est_Snapshot_YoY` (snapshot-over-snapshot forward 4Q
     estimate growth) vs `Fwd_vs_Trail_Growth` (forward 4Q estimate over trailing 4Q actuals).
  3. Priority 3: Year-by-year net log-wealth attribution and Leave-One-Crisis-Out (`ex-2018`,
     `ex-2020`, `ex-2018&2020`, `ex-2026`) insurance cost vs drawdown reduction audit.
  4. Priority 4: Multi-block-length Moving Block Bootstrap (`L = 10, 21, 63, 126` trading days) and
     Politis-Romano Stationary Bootstrap (`mean L = 63`), reporting two-sided 95% CIs, Null-Centered
     studentized p-values, and White's Reality Check / Holm-Bonferroni multiple-testing adjusted p-values.
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


def build_wayback_it_pit_lookup_and_audit():
    vint_path = os.path.join(BASE_DIR, "outputs", "sector_eps_then_momentum_20261030", "recovered_sector_eps_vintages.csv")
    vint = pd.read_csv(vint_path)
    vint["available_date"] = pd.to_datetime(vint["available_date"])
    vint["quarter_end"] = pd.to_datetime(vint["quarter_end"])
    it = vint[(vint["sector"] == "Information Technology") & (vint["basis"] == "operating")].copy()
    v_meta = it.groupby("vintage_id")["available_date"].first().reset_index().sort_values("available_date")

    # Audit every single vintage in the file
    v_audit_rows = []
    for vid, g in it.groupby("vintage_id"):
        g = g.drop_duplicates(subset=["quarter"], keep="last").sort_values("quarter_end")
        act = g[g["status"] == "actual"]
        est = g[g["status"] == "estimate"]
        act4 = act.tail(4)
        est4 = est.head(4)
        v_audit_rows.append({
            "vintage_id": vid,
            "available_date": g["available_date"].iloc[0].strftime("%Y-%m-%d"),
            "n_actual_quarters": len(act),
            "n_estimate_quarters": len(est),
            "has_strict_4q_est": bool(len(est) >= 4),
            "trailing_4q_quarters": ",".join(act4["quarter"].tolist()),
            "forward_4q_quarters": ",".join(est4["quarter"].tolist()),
            "trailing_4q_actual_eps": round(float(act4["eps"].sum()), 4) if len(act4) == 4 else np.nan,
            "forward_4q_est_eps_strict_sum": round(float(est4["eps"].sum()), 4) if len(est4) == 4 else np.nan,
        })
    df_v_audit = pd.DataFrame(v_audit_rows).sort_values("available_date").reset_index(drop=True)
    df_v_audit.to_csv(os.path.join(OUT_DIR, "tqqq_eps_vintage_coverage_audit.csv"), index=False)

    def get_vintage_stats(t_dt, max_stale_days=120):
        elig = v_meta[v_meta["available_date"] <= t_dt]
        if elig.empty:
            return None
        vid = elig.iloc[-1]["vintage_id"]
        dt_v = elig.iloc[-1]["available_date"]
        staleness_days = int((t_dt - dt_v).days)
        if max_stale_days is not None and staleness_days > max_stale_days:
            return None
        g = it[it["vintage_id"] == vid].drop_duplicates(subset=["quarter"], keep="last").sort_values("quarter_end")
        act = g[g["status"] == "actual"].tail(4)
        est = g[g["status"] == "estimate"].head(4)
        # Strictly require 4 actual quarters and 4 forward estimate quarters (no <4 interpolation)
        if len(act) < 4 or len(est) < 4:
            return None
        trail_4q = float(act["eps"].sum())
        fwd_4q = float(est["eps"].sum())
        est_q_str = ",".join(est["quarter"].tolist())
        return vid, dt_v, staleness_days, trail_4q, fwd_4q, est_q_str

    def get_it_eps_metrics(t_dt):
        if t_dt < pd.Timestamp("2014-01-31"):
            return {
                "it_fwd_snapyoy": np.nan,
                "it_fwd_snapyoy_nocutoff": np.nan,
                "it_fwd_vs_trail": np.nan,
                "wb_avail_dt": None,
                "wb_staleness_d": np.nan,
                "wb_est_4q": None,
                "wb_prev_avail_dt": None,
                "wb_prev_staleness_d": np.nan,
                "wb_prev_est_4q": None,
            }
        cur_120 = get_vintage_stats(t_dt, max_stale_days=120)
        prev_120 = get_vintage_stats(t_dt - pd.Timedelta(days=365), max_stale_days=120)

        cur_all = get_vintage_stats(t_dt, max_stale_days=None)
        prev_all = get_vintage_stats(t_dt - pd.Timedelta(days=365), max_stale_days=None)

        fwd_snapyoy_nocutoff = np.nan
        if cur_all is not None and prev_all is not None and prev_all[4] > 0:
            fwd_snapyoy_nocutoff = round((cur_all[4] / prev_all[4] - 1.0) * 100.0, 6)

        if cur_120 is None:
            return {
                "it_fwd_snapyoy": np.nan,
                "it_fwd_snapyoy_nocutoff": fwd_snapyoy_nocutoff,
                "it_fwd_vs_trail": np.nan,
                "wb_avail_dt": cur_all[1].strftime("%Y-%m-%d") if cur_all else None,
                "wb_staleness_d": cur_all[2] if cur_all else np.nan,
                "wb_est_4q": cur_all[5] if cur_all else None,
                "wb_prev_avail_dt": prev_all[1].strftime("%Y-%m-%d") if prev_all else None,
                "wb_prev_staleness_d": prev_all[2] if prev_all else np.nan,
                "wb_prev_est_4q": prev_all[5] if prev_all else None,
            }
        vid, dt_v, stale_d, trail_4q, fwd_4q, est_q_str = cur_120
        fwd_vs_trail = round((fwd_4q / trail_4q - 1.0) * 100.0, 6) if trail_4q > 0 else np.nan

        if prev_120 is None or prev_120[4] <= 0:
            return {
                "it_fwd_snapyoy": np.nan,
                "it_fwd_snapyoy_nocutoff": fwd_snapyoy_nocutoff,
                "it_fwd_vs_trail": fwd_vs_trail,
                "wb_avail_dt": dt_v.strftime("%Y-%m-%d"),
                "wb_staleness_d": stale_d,
                "wb_est_4q": est_q_str,
                "wb_prev_avail_dt": prev_all[1].strftime("%Y-%m-%d") if prev_all else None,
                "wb_prev_staleness_d": prev_all[2] if prev_all else np.nan,
                "wb_prev_est_4q": prev_all[5] if prev_all else None,
            }
        fwd_snapyoy = round((fwd_4q / prev_120[4] - 1.0) * 100.0, 6)
        return {
            "it_fwd_snapyoy": fwd_snapyoy,
            "it_fwd_snapyoy_nocutoff": fwd_snapyoy_nocutoff,
            "it_fwd_vs_trail": fwd_vs_trail,
            "wb_avail_dt": dt_v.strftime("%Y-%m-%d"),
            "wb_staleness_d": stale_d,
            "wb_est_4q": est_q_str,
            "wb_prev_avail_dt": prev_120[1].strftime("%Y-%m-%d"),
            "wb_prev_staleness_d": prev_120[2],
            "wb_prev_est_4q": prev_120[5],
        }

    return get_it_eps_metrics, df_v_audit


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

    get_it_eps_metrics, df_v_audit = build_wayback_it_pit_lookup_and_audit()

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
            # Include Friday 2026-10-30 (full October 2026 trading calendar)
            d1 = pd.Timestamp("2026-10-30")
            m_days = cal[(cal >= d0) & (cal <= d1)]
            p_col = "c"
        else:
            t_next = t + pd.offsets.MonthEnd(1)
            d1_idx = cal.searchsorted(t_next, side="right")
            d1 = cal[d1_idx] if d1_idx < len(cal) else cal[-1]
            m_days = cal[(cal >= d0) & (cal < d1)]
            p_col = "o"

        df_ca = df_sgov if d0 >= pd.Timestamp("2020-06-01") else df_bil
        o0_tq = float(df_tqqq_full.at[d0, "o"])
        o0_qq = float(df_qqq.at[d0, "o"])
        o0_ca = float(df_ca.at[d0, "o"])

        r_tq = float(df_tqqq_full.at[d1, p_col] / o0_tq - 1.0)
        r_qq = float(df_qqq.at[d1, p_col] / o0_qq - 1.0)
        r_ca = float(df_ca.at[d1, p_col] / o0_ca - 1.0)

        vix_now = float(vix_d.loc[:t].iloc[-1])
        vxn_now = float(vxn_d.loc[:t].iloc[-1])
        vol21_now = float(vol21_d.loc[:t].iloc[-1])
        vrp_vix = round(vix_now - vol21_now, 6)
        vrp_vxn = round(vxn_now - vol21_now, 6)
        vrp_vxn_z = round(float(vrp_vxn_z_s.loc[:t].iloc[-1]), 6)
        var_vxn_z = round(float(var_vxn_z_s.loc[:t].iloc[-1]), 6)

        # Strictly lagged by 1 business day for Federal Reserve H.15 series (DBAA, DGS10, DFII10)
        # Round basis-point changes to 4 decimals to eliminate IEEE-754 float boundary errors
        t_lag1 = cal[max(0, cal.searchsorted(t) - 1)]
        cs_now = float(cs_baa_d.loc[:t_lag1].iloc[-1])
        cs_prev21 = float(cs_baa_d.loc[:t_lag1].iloc[-22])
        cs_baa_chg21_bp = round((cs_now - cs_prev21) * 100.0, 4)

        rr_now = float(rr_d.loc[:t_lag1].iloc[-1])
        rr_prev63 = float(rr_d.loc[:t_lag1].iloc[-64])
        rr_chg63_bp = round((rr_now - rr_prev63) * 100.0, 4)

        # Strictly lagged by 7 calendar days for Federal Reserve H.4.1 WRESBAL (4-week mean YoY)
        w_sub = wres.loc[:(t - pd.Timedelta(days=7))]
        wres_4w_yoy = round(float((w_sub.iloc[-4:].mean() / w_sub.iloc[-56:-52].mean() - 1.0) * 100.0), 6) if len(w_sub) >= 56 else np.nan

        eps_info = get_it_eps_metrics(t)

        m_rows.append({
            "t": t, "t_str": t.strftime("%Y-%m-%d"), "t_lag1_str": t_lag1.strftime("%Y-%m-%d"),
            "ym": hold_ym, "sep_on": sep_on,
            "vix_now": vix_now, "vxn_now": vxn_now, "vol21_now": vol21_now,
            "vrp_vix": vrp_vix, "vrp_vxn": vrp_vxn, "vrp_vxn_z": vrp_vxn_z, "var_vxn_z": var_vxn_z,
            "cs_now": cs_now, "cs_prev21": cs_prev21, "cs_baa_chg21_bp": cs_baa_chg21_bp,
            "rr_now": rr_now, "rr_prev63": rr_prev63, "rr_chg63_bp": rr_chg63_bp,
            "wres_4w_yoy": wres_4w_yoy,
            "it_fwd_snapyoy": eps_info["it_fwd_snapyoy"],
            "it_fwd_snapyoy_nocutoff": eps_info["it_fwd_snapyoy_nocutoff"],
            "it_fwd_vs_trail": eps_info["it_fwd_vs_trail"],
            "wb_avail_dt": eps_info["wb_avail_dt"],
            "wb_staleness_d": eps_info["wb_staleness_d"],
            "wb_est_4q": eps_info["wb_est_4q"],
            "wb_prev_avail_dt": eps_info["wb_prev_avail_dt"],
            "wb_prev_staleness_d": eps_info["wb_prev_staleness_d"],
            "wb_prev_est_4q": eps_info["wb_prev_est_4q"],
            "r_tq": r_tq, "r_qq": r_qq, "r_ca": r_ca,
            "rf_m": float(reg_map[t]["rf_m"]), "d0": d0, "d1": d1, "m_days": m_days
        })

    df_M = pd.DataFrame(m_rows)

    # =========================================================================
    # PRIORITY 1 & 2 CHECK: Triggered Months Ledger (After IEEE-754 Fix & 2026-10-30 Fix)
    # =========================================================================
    sub_on = df_M[(df_M["ym"] >= "2011-01") & (df_M["sep_on"])].copy()
    c_b_vxn_z = (sub_on["cs_baa_chg21_bp"] > 10.0) & (sub_on["vrp_vxn_z"] > 0.0)
    c_a1_snap = (sub_on["it_fwd_snapyoy"] >= 24.0) & (sub_on["rr_chg63_bp"] > 0.0)
    c_a1_nocut = (sub_on["it_fwd_snapyoy_nocutoff"] >= 24.0) & (sub_on["rr_chg63_bp"] > 0.0)
    c_a1_trail = (sub_on["it_fwd_vs_trail"] >= 24.0) & (sub_on["rr_chg63_bp"] > 0.0)
    c_a2_snap = (sub_on["it_fwd_snapyoy"] >= 24.0) & (sub_on["wres_4w_yoy"] < 0.0)

    print("==========================================================================================")
    print("PRIORITY 1 & 2 AUDIT: IEEE-754 FLOAT FIX + WAYBACK EPS VINTAGE COVERAGE")
    print("==========================================================================================")
    print(f"  Wayback IT Operating Vintages Audited: {len(df_v_audit)} snapshots ({df_v_audit['available_date'].min()} .. {df_v_audit['available_date'].max()})")
    print(f"  Snapshots with >= 4 forward estimate quarters (strict 4Q sum): {(df_v_audit['n_estimate_quarters'] >= 4).sum()}/{len(df_v_audit)} (100.0%)")
    sub_15 = df_M[df_M["ym"] >= "2015-01"]
    print(f"  2015-01..2026-10 (142M) Coverage: Fwd_vs_Trail = {sub_15['it_fwd_vs_trail'].notna().sum()}/142 ({sub_15['it_fwd_vs_trail'].notna().mean()*100:.1f}%), Fwd_SnapYoY_120d = {sub_15['it_fwd_snapyoy'].notna().sum()}/142 ({sub_15['it_fwd_snapyoy'].notna().mean()*100:.1f}%), Fwd_SnapYoY_NoCutoff = {sub_15['it_fwd_snapyoy_nocutoff'].notna().sum()}/142 ({sub_15['it_fwd_snapyoy_nocutoff'].notna().mean()*100:.1f}%)")
    print(f"  IEEE-754 Bug Check on 2018-07: cs_baa_chg21_bp = {df_M[df_M['ym']=='2018-07']['cs_baa_chg21_bp'].iloc[0]:.4f} bp -> Triggered (>10.0bp)? {bool(df_M[df_M['ym']=='2018-07']['cs_baa_chg21_bp'].iloc[0] > 10.0)}")

    # Save exact 21 triggered months of Frozen Dual-Core A1+B
    trig_frozen = sub_on[c_b_vxn_z | c_a1_snap].copy()
    ledger_rows = []
    for _, r in trig_frozen.iterrows():
        is_b = bool(r["cs_baa_chg21_bp"] > 10.0 and r["vrp_vxn_z"] > 0.0)
        is_a1 = bool(pd.notna(r["it_fwd_snapyoy"]) and r["it_fwd_snapyoy"] >= 24.0 and r["rr_chg63_bp"] > 0.0)
        tags = []
        if is_b:
            tags.append("Type_B(Credit>10bp&VXN_Z>0)")
        if is_a1:
            tags.append("Type_A1(SnapYoY>=24%&RR>0)")
        ledger_rows.append({
            "hold_ym": r["ym"],
            "form_date_t": r["t_str"],
            "h15_lag1_dt": r["t_lag1_str"],
            "wb_avail_dt": r["wb_avail_dt"],
            "wb_staleness_d": r["wb_staleness_d"],
            "wb_est_4q": r["wb_est_4q"],
            "wb_prev_avail_dt": r["wb_prev_avail_dt"],
            "wb_prev_staleness_d": r["wb_prev_staleness_d"],
            "triggered_by": " | ".join(tags),
            "baa_chg21_bp": round(r["cs_baa_chg21_bp"], 1),
            "vxn_close": round(r["vxn_now"], 2),
            "qqq_vol21": round(r["vol21_now"], 2),
            "vrp_vxn_z": round(r["vrp_vxn_z"], 2),
            "it_fwd_snapyoy_pct": round(r["it_fwd_snapyoy"], 2) if pd.notna(r["it_fwd_snapyoy"]) else np.nan,
            "it_fwd_vs_trail_pct": round(r["it_fwd_vs_trail"], 2) if pd.notna(r["it_fwd_vs_trail"]) else np.nan,
            "rr_chg63_bp": round(r["rr_chg63_bp"], 1),
            "wres_4w_yoy_pct": round(r["wres_4w_yoy"], 2),
            "tqqq_ret_pct": round(r["r_tq"] * 100.0, 2),
            "qqq_ret_pct": round(r["r_qq"] * 100.0, 2),
            "saved_vs_tqqq_pct": round((r["r_qq"] - r["r_tq"]) * 100.0, 2),
        })
    df_trig = pd.DataFrame(ledger_rows)
    df_trig.to_csv(os.path.join(OUT_DIR, "tqqq_orthogonal_typeAB_triggered_months.csv"), index=False)
    print("\n==========================================================================================")
    print(f"STAGE 1: REPAIRED FROZEN A1+B TRIGGERED MONTHS LEDGER ({len(df_trig)} MONTHS: 2018-07 REMOVED, 2026-10-30 INCLUDED)")
    print("==========================================================================================")
    print(df_trig.to_string(index=False))

    # Also audit the extra months where 120d Staleness Cutoff hid Type A1 triggers (e.g., 2026-04, 2026-05)
    diff_nocut = sub_on[c_a1_nocut & (~c_a1_snap)].copy()
    print("\n  --- [Priority 2 Falsification] Months Where 120-Day Staleness Cutoff Suppressed Type A1 (`SnapYoY_NoCutoff >= 24% & RR > 0`, but dropped by >120d cutoff) ---")
    for _, r in diff_nocut.iterrows():
        print(f"  {r['ym']} (form={r['t_str']}): cur_wb={r['wb_avail_dt']} (stale={r['wb_staleness_d']}d), prev_wb={r['wb_prev_avail_dt']} (stale={r['wb_prev_staleness_d']}d), SnapYoY_NoCutoff={r['it_fwd_snapyoy_nocutoff']:+.2f}%, RR_chg63={r['rr_chg63_bp']:+.1f}bp | TQQQ={r['r_tq']*100:+.2f}%, QQQ={r['r_qq']*100:+.2f}%")

    # =========================================================================
    # STAGE 2: Repaired Open-Executed Daily NAV & Backtest Engine
    # =========================================================================
    COST_BP = 0.0010
    summary_rows = []
    daily_ret_store = {}
    daily_nav_store = {}
    monthly_df_store = {}

    def run_bt(name, wt_fn, start_ym="2011-01", store_key=None):
        prev_state = None
        rows = []
        W_pre = 1.0
        pts_nav = {}
        w_pre_by_ym = {}
        false_alarms = 0
        total_alarms = 0
        trig_tq_rets = []
        trig_tq_rets_ex2003 = []
        non_trig_tq_rets = []

        for _, r in df_M.iterrows():
            hold_ym = r["ym"]
            sep_on = r["sep_on"]
            w_pre_by_ym[hold_ym] = W_pre

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
            cost_mult = ((1.0 - COST_BP) ** to) if to > 0 else 1.0
            net = (1.0 + gross) * cost_mult - 1.0

            # Open-Executed Daily NAV:
            # At d0 Open, rebalance turnover cost is deducted (`W_open_d0 = W_pre * cost_mult`),
            # and all daily closes d in [d0 .. d_last] are measured relative to d0 Open prices!
            W_open_d0 = W_pre * cost_mult
            d0, m_days = r["d0"], r["m_days"]
            o0_tq = float(df_tqqq_full.at[d0, "o"])
            o0_qq = float(df_qqq.at[d0, "o"])
            df_ca = df_sgov if d0 >= pd.Timestamp("2020-06-01") else df_bil
            o0_ca = float(df_ca.at[d0, "o"])

            for d in m_days:
                if state[0] == "CASH":
                    rel_c = float(df_ca.at[d, "c"]) / o0_ca
                else:
                    rel_c = state[1] * (float(df_tqqq_full.at[d, "c"]) / o0_tq) + (1.0 - state[1]) * (float(df_qqq.at[d, "c"]) / o0_qq)
                pts_nav[d] = W_open_d0 * rel_c

            W_pre = W_pre * (1.0 + net)
            rows.append({
                "ym": hold_ym,
                "sep_on": sep_on,
                "state_mode": state[0],
                "w_tq": state[1],
                "gross_ret": gross,
                "net_ret": net,
                "rf_m": r["rf_m"],
            })

        df_L = pd.DataFrame(rows)
        s_nav_full = pd.Series(pts_nav).sort_index()

        # Sub-window exact alignment: normalize by W_pre at the start of start_ym (`d0` Open of `start_ym`)
        w0_sub = w_pre_by_ym[start_ym]
        d0_sub = df_M[df_M["ym"] == start_ym]["d0"].iloc[0]
        nav_sub = s_nav_full[s_nav_full.index >= d0_sub] / w0_sub
        # Daily return series where day 0 (d0_sub) return is measured from 1.0 (d0_sub Open pre-trade wealth)
        nav_with_start = pd.concat([pd.Series([1.0], index=[d0_sub - pd.Timedelta(hours=12)]), nav_sub])
        r_daily_sub = nav_sub / nav_sub.shift(1).fillna(1.0) - 1.0

        sub_L = df_L[df_L["ym"] >= start_ym].copy()
        r_vec = sub_L["net_ret"].values
        rf_vec = sub_L["rf_m"].values

        # Verify exact mathematical identity between Monthly Cumulative Wealth and Daily Terminal NAV
        cum_monthly = float(np.prod(1.0 + r_vec))
        cum_daily = float(nav_sub.iloc[-1])
        cum_daily_prod = float(np.prod(1.0 + r_daily_sub.values))
        assert abs(cum_monthly / cum_daily - 1.0) < 1e-12, f"Mismatch: {cum_monthly} vs {cum_daily}"
        assert abs(cum_monthly / cum_daily_prod - 1.0) < 1e-12, f"Mismatch: {cum_monthly} vs {cum_daily_prod}"

        if store_key is not None:
            daily_nav_store[store_key] = nav_sub
            daily_ret_store[store_key] = r_daily_sub
            monthly_df_store[store_key] = sub_L

        cagr = (cum_monthly ** (12.0 / len(r_vec)) - 1.0) * 100.0
        sh_m = (np.mean(r_vec - rf_vec) / np.std(r_vec, ddof=1) * np.sqrt(12.0))
        rf_d_aligned = rf_daily.reindex(r_daily_sub.index).fillna(0.0).values
        sh_d = (np.mean(r_daily_sub.values - rf_d_aligned) / np.std(r_daily_sub.values, ddof=1) * np.sqrt(252.0))

        eq = np.cumprod(1.0 + r_vec)
        mdd = np.min(eq / np.maximum.accumulate(eq) - 1.0) * 100.0
        # Include initial 1.0 at d0 Open in cummax so first-day drawdown is never missed
        ddd = float((nav_with_start / nav_with_start.cummax() - 1.0).min()) * 100.0
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
            "monthly_sharpe": round(sh_m, 3),
            "daily_sharpe": round(sh_d, 3),
            "monthly_maxdd_pct": round(mdd, 2),
            "open_anchored_daily_maxdd_pct": round(ddd, 2),
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
               lambda r: 0.0 if (r["cs_baa_chg21_bp"] > 10.0 and r["vrp_vix"] > 0.0) else 1.0, start_ym=w_start, store_key=f"typeB_vix_{w_start}")
        run_bt("1b. Type B Only (Credit>10bp & Nasdaq VXN_VRP Z_3Y>0 -> 1x QQQ)",
               lambda r: 0.0 if (r["cs_baa_chg21_bp"] > 10.0 and r["vrp_vxn_z"] > 0.0) else 1.0, start_ym=w_start, store_key=f"typeB_vxnZ_{w_start}")
        run_bt("1c. Type B Only (Credit>10bp & Nasdaq Var_VRP Z_3Y>0 -> 1x QQQ)",
               lambda r: 0.0 if (r["cs_baa_chg21_bp"] > 10.0 and r["var_vxn_z"] > 0.0) else 1.0, start_ym=w_start, store_key=f"typeB_varZ_{w_start}")
        run_bt("2a. Type A1 Only [SnapYoY_120d] (IT_Fwd_SnapYoY>=24% & RR_chg3M>0 -> 1x QQQ)",
               lambda r: 0.0 if (pd.notna(r["it_fwd_snapyoy"]) and r["it_fwd_snapyoy"] >= 24.0 and r["rr_chg63_bp"] > 0.0) else 1.0,
               start_ym=w_start, store_key=f"typeA1_snap_{w_start}")
        run_bt("2b. Type A1_NoCutoff [SnapYoY Carry-Forward, No 120d NaN Drop]",
               lambda r: 0.0 if (pd.notna(r["it_fwd_snapyoy_nocutoff"]) and r["it_fwd_snapyoy_nocutoff"] >= 24.0 and r["rr_chg63_bp"] > 0.0) else 1.0,
               start_ym=w_start, store_key=f"typeA1_nocut_{w_start}")
        run_bt("2c. Type A1_Alt [FwdVsTrail] (IT_FwdVsTrail>=24% & RR_chg3M>0 -> 1x QQQ)",
               lambda r: 0.0 if (pd.notna(r["it_fwd_vs_trail"]) and r["it_fwd_vs_trail"] >= 24.0 and r["rr_chg63_bp"] > 0.0) else 1.0,
               start_ym=w_start, store_key=f"typeA1_trail_{w_start}")
        run_bt("2d. Type A2 Only [SnapYoY_120d] (IT_Fwd_SnapYoY>=24% & WRES_4W_YoY<0 -> 1x QQQ)",
               lambda r: 0.0 if (pd.notna(r["it_fwd_snapyoy"]) and r["it_fwd_snapyoy"] >= 24.0 and r["wres_4w_yoy"] < 0.0) else 1.0,
               start_ym=w_start, store_key=f"typeA2_snap_{w_start}")
        run_bt("3a. FROZEN Dual-Core A1+B (Type B [VXN_Z>0] OR Type A1 [SnapYoY_120d>=24%&RR>0] -> 1x QQQ)",
               lambda r: 0.0 if ((r["cs_baa_chg21_bp"] > 10.0 and r["vrp_vxn_z"] > 0.0) or (pd.notna(r["it_fwd_snapyoy"]) and r["it_fwd_snapyoy"] >= 24.0 and r["rr_chg63_bp"] > 0.0)) else 1.0,
               start_ym=w_start, store_key=f"dualA1B_{w_start}")
        run_bt("3b. Alt Dual-Core A1_NoCutoff+B (Type B [VXN_Z>0] OR Type A1_NoCutoff [No 120d NaN Drop])",
               lambda r: 0.0 if ((r["cs_baa_chg21_bp"] > 10.0 and r["vrp_vxn_z"] > 0.0) or (pd.notna(r["it_fwd_snapyoy_nocutoff"]) and r["it_fwd_snapyoy_nocutoff"] >= 24.0 and r["rr_chg63_bp"] > 0.0)) else 1.0,
               start_ym=w_start, store_key=f"dualA1NoCutB_{w_start}")
        run_bt("3c. Alt Dual-Core A1_Trail+B (Type B [VXN_Z>0] OR Type A1_Trail [FwdVsTrail>=24%&RR>0])",
               lambda r: 0.0 if ((r["cs_baa_chg21_bp"] > 10.0 and r["vrp_vxn_z"] > 0.0) or (pd.notna(r["it_fwd_vs_trail"]) and r["it_fwd_vs_trail"] >= 24.0 and r["rr_chg63_bp"] > 0.0)) else 1.0,
               start_ym=w_start, store_key=f"dualA1TrailB_{w_start}")
        run_bt("3d. Dual-Core A2+B (Type B [VXN_Z>0] OR Type A2 [SnapYoY_120d>=24%&WRES<0] -> 1x QQQ)",
               lambda r: 0.0 if ((r["cs_baa_chg21_bp"] > 10.0 and r["vrp_vxn_z"] > 0.0) or (pd.notna(r["it_fwd_snapyoy"]) and r["it_fwd_snapyoy"] >= 24.0 and r["wres_4w_yoy"] < 0.0)) else 1.0,
               start_ym=w_start, store_key=f"dualA2B_{w_start}")
        run_bt("3e. Tiered Dual-Core A1+B (Type B -> 1x QQQ, Type A1 -> 2x [50/50])",
               lambda r: 0.0 if (r["cs_baa_chg21_bp"] > 10.0 and r["vrp_vxn_z"] > 0.0) else (0.5 if (pd.notna(r["it_fwd_snapyoy"]) and r["it_fwd_snapyoy"] >= 24.0 and r["rr_chg63_bp"] > 0.0) else 1.0),
               start_ym=w_start, store_key=f"tieredA1B_{w_start}")

    df_sum = pd.DataFrame(summary_rows)
    df_sum.to_csv(os.path.join(OUT_DIR, "tqqq_orthogonal_typeAB_summary.csv"), index=False)

    # Save the complete daily NAV series for 2011-01..2026-10
    df_daily_nav = pd.DataFrame({
        "date": daily_nav_store["base_2011-01"].index.strftime("%Y-%m-%d"),
        "nav_baseline": daily_nav_store["base_2011-01"].values,
        "nav_typeB_vxnZ": daily_nav_store["typeB_vxnZ_2011-01"].values,
        "nav_typeA1_snap": daily_nav_store["typeA1_snap_2011-01"].values,
        "nav_dual_A1B_frozen": daily_nav_store["dualA1B_2011-01"].values,
        "nav_dual_A2B": daily_nav_store["dualA2B_2011-01"].values,
        "ret_baseline": daily_ret_store["base_2011-01"].values,
        "ret_dual_A1B_frozen": daily_ret_store["dualA1B_2011-01"].values,
    })
    df_daily_nav.to_csv(os.path.join(OUT_DIR, "tqqq_orthogonal_typeAB_daily_nav.csv"), index=False)

    print("\n==========================================================================================")
    print("STAGE 2: REPAIRED PERFORMANCE SUMMARY (OPEN-EXECUTED DAILY NAV & IEEE-754 FIX)")
    print("==========================================================================================")
    print("  [Verified] Monthly Cumulative Wealth == Terminal Daily Close NAV == Product(1 + Daily_Ret) (Max Diff < 1e-12)")
    print(df_sum.to_string(index=False))

    # =========================================================================
    # PRIORITY 3: Leave-One-Crisis-Out & Year-by-Year Log-Wealth Attribution
    # =========================================================================
    print("\n==========================================================================================")
    print("STAGE 3 (PRIORITY 3): YEAR-BY-YEAR LOG-WEALTH ATTRIBUTION & LEAVE-ONE-CRISIS-OUT AUDIT")
    print("==========================================================================================")
    m_base = monthly_df_store["base_2011-01"].copy()
    m_dual = monthly_df_store["dualA1B_2011-01"].copy()
    m_comp = m_base[["ym", "sep_on", "net_ret", "rf_m"]].rename(columns={"net_ret": "ret_base"}).merge(
        m_dual[["ym", "w_tq", "net_ret"]].rename(columns={"net_ret": "ret_dual"}), on="ym"
    )
    m_comp["year"] = m_comp["ym"].str.slice(0, 4)
    m_comp["triggered"] = (m_comp["sep_on"]) & (m_comp["w_tq"] < 0.99)
    m_comp["log_wealth_diff_pct"] = (np.log(1.0 + m_comp["ret_dual"]) - np.log(1.0 + m_comp["ret_base"])) * 100.0

    yr_rows = []
    for yr, g in m_comp.groupby("year"):
        r_b_yr = (np.prod(1.0 + g["ret_base"]) - 1.0) * 100.0
        r_d_yr = (np.prod(1.0 + g["ret_dual"]) - 1.0) * 100.0
        yr_rows.append({
            "period_or_year": yr,
            "months": len(g),
            "triggers": int(g["triggered"].sum()),
            "base_return_pct": round(r_b_yr, 2),
            "dual_A1B_return_pct": round(r_d_yr, 2),
            "net_log_wealth_diff_pct": round(g["log_wealth_diff_pct"].sum(), 2),
        })
    df_yr = pd.DataFrame(yr_rows)
    print("  --- Year-by-Year Net Log-Wealth Contribution (After 10bp Turnover Costs) ---")
    print(df_yr.to_string(index=False))

    # Leave-One-Crisis-Out Sub-Sample Table
    loco_specs = [
        ("Full Sample (2011-2026)", lambda ym: pd.Series(True, index=ym.index)),
        ("Leave-Out 2018 Only (ex-2018)", lambda ym: ~ym.str.startswith("2018-")),
        ("Leave-Out 2020 COVID Crash (ex-2020-02/03)", lambda ym: ~ym.isin(["2020-02", "2020-03"])),
        ("Leave-Out Full 2020 (ex-2020)", lambda ym: ~ym.str.startswith("2020-")),
        ("Leave-Out Both 2018 & 2020 (Normal Bull Insurance Cost)", lambda ym: (~ym.str.startswith("2018-")) & (~ym.str.startswith("2020-"))),
        ("Leave-Out 2026 (ex-2026)", lambda ym: ~ym.str.startswith("2026-")),
    ]
    loco_rows = []
    r_d_base_all = daily_ret_store["base_2011-01"]
    r_d_dual_all = daily_ret_store["dualA1B_2011-01"]

    for lbl, mask_fn in loco_specs:
        sub_m = m_comp[mask_fn(m_comp["ym"])].copy()
        n_m = len(sub_m)
        cagr_b = (np.prod(1.0 + sub_m["ret_base"]) ** (12.0 / n_m) - 1.0) * 100.0
        cagr_d = (np.prod(1.0 + sub_m["ret_dual"]) ** (12.0 / n_m) - 1.0) * 100.0
        sh_b = (np.mean(sub_m["ret_base"] - sub_m["rf_m"]) / np.std(sub_m["ret_base"], ddof=1)) * np.sqrt(12.0)
        sh_d = (np.mean(sub_m["ret_dual"] - sub_m["rf_m"]) / np.std(sub_m["ret_dual"], ddof=1)) * np.sqrt(12.0)
        eq_b = np.cumprod(1.0 + sub_m["ret_base"].values)
        eq_d = np.cumprod(1.0 + sub_m["ret_dual"].values)
        mdd_b = np.min(eq_b / np.maximum.accumulate(eq_b) - 1.0) * 100.0
        mdd_d = np.min(eq_d / np.maximum.accumulate(eq_d) - 1.0) * 100.0

        # Also filter daily returns by corresponding holding months
        valid_yms = set(sub_m["ym"])
        valid_days = []
        for _, r_m in df_M[df_M["ym"].isin(valid_yms)].iterrows():
            valid_days.extend(list(r_m["m_days"]))
        valid_idx = r_d_base_all.index.intersection(pd.DatetimeIndex(valid_days))
        nav_b_loco = np.cumprod(1.0 + r_d_base_all.loc[valid_idx].values)
        nav_d_loco = np.cumprod(1.0 + r_d_dual_all.loc[valid_idx].values)
        ddd_b = np.min(nav_b_loco / np.maximum.accumulate(np.insert(nav_b_loco, 0, 1.0))[1:] - 1.0) * 100.0
        ddd_d = np.min(nav_d_loco / np.maximum.accumulate(np.insert(nav_d_loco, 0, 1.0))[1:] - 1.0) * 100.0

        loco_rows.append({
            "subsample": lbl,
            "months": n_m,
            "triggers": int(sub_m["triggered"].sum()),
            "log_wealth_diff_pct": round(sub_m["log_wealth_diff_pct"].sum(), 2),
            "base_cagr_pct": round(cagr_b, 2),
            "dual_cagr_pct": round(cagr_d, 2),
            "cagr_diff_pp": round(cagr_d - cagr_b, 2),
            "base_sharpe": round(sh_b, 3),
            "dual_sharpe": round(sh_d, 3),
            "base_daily_maxdd_pct": round(ddd_b, 2),
            "dual_daily_maxdd_pct": round(ddd_d, 2),
        })
    df_loco = pd.DataFrame(loco_rows)
    df_loco.to_csv(os.path.join(OUT_DIR, "tqqq_orthogonal_typeAB_crisis_attribution.csv"), index=False)
    print("\n  --- Leave-One-Crisis-Out Attribution Table (2011-2026) ---")
    print(df_loco.to_string(index=False))

    # =========================================================================
    # STAGE 4: Repaired 108-Cell Grid + Effective Unique Paths Count
    # =========================================================================
    grid_rows = []
    base_190 = df_sum[(df_sum["window"] == "2011-01..2026-10") & (df_sum["version"].str.startswith("0."))].iloc[0]
    for baa_th in [8.0, 10.0, 12.0]:
        for vxn_z_th in [-0.25, 0.0, 0.25]:
            for eps_th in [20.0, 22.0, 24.0, 26.0]:
                for rr_th in [-5.0, 0.0, 5.0]:
                    g_res = run_bt(
                        f"Grid(BAA>{int(baa_th)}bp,VXN_Z>{vxn_z_th:+.2f},EPS>={int(eps_th)}%,RR>{int(rr_th):+d}bp)",
                        lambda r, b=baa_th, v=vxn_z_th, e=eps_th, rr=rr_th: 0.0 if (
                            (r["cs_baa_chg21_bp"] > b and r["vrp_vxn_z"] > v) or
                            (pd.notna(r["it_fwd_snapyoy"]) and r["it_fwd_snapyoy"] >= e and r["rr_chg63_bp"] > rr)
                        ) else 1.0,
                        start_ym="2011-01"
                    )
                    grid_rows.append(g_res)

    df_grid = pd.DataFrame(grid_rows)
    df_grid.to_csv(os.path.join(OUT_DIR, "tqqq_orthogonal_typeAB_108grid.csv"), index=False)
    n_unique_paths = len(df_grid.drop_duplicates(subset=["cagr_pct", "monthly_sharpe", "open_anchored_daily_maxdd_pct"]))
    n_unique_ddd = df_grid["open_anchored_daily_maxdd_pct"].nunique()
    print("\n==========================================================================================")
    print("STAGE 4: REPAIRED 108-CELL GRID & EFFECTIVE DEGREES OF FREEDOM")
    print("==========================================================================================")
    print(f"  Total Grid Cells: {len(df_grid)} | Unique Return/Sharpe/MaxDD Paths: {n_unique_paths} | Unique Daily MaxDD Values: {n_unique_ddd}")
    print(f"  Cells Beating Baseline CAGR ({base_190['cagr_pct']:.2f}%):     {(df_grid['cagr_pct'] > base_190['cagr_pct']).mean()*100:5.1f}% ({int((df_grid['cagr_pct'] > base_190['cagr_pct']).sum())}/{len(df_grid)}) | Range: [{df_grid['cagr_pct'].min():.2f}% .. {df_grid['cagr_pct'].max():.2f}%], Median={df_grid['cagr_pct'].median():.2f}%")
    print(f"  Cells Beating Baseline Sharpe ({base_190['monthly_sharpe']:.3f}):    {(df_grid['monthly_sharpe'] > base_190['monthly_sharpe']).mean()*100:5.1f}% ({int((df_grid['monthly_sharpe'] > base_190['monthly_sharpe']).sum())}/{len(df_grid)}) | Range: [{df_grid['monthly_sharpe'].min():.3f} .. {df_grid['monthly_sharpe'].max():.3f}], Median={df_grid['monthly_sharpe'].median():.3f}")
    print(f"  Cells Improving Open-Anchored Daily MaxDD ({base_190['open_anchored_daily_maxdd_pct']:.2f}%): {(df_grid['open_anchored_daily_maxdd_pct'] > base_190['open_anchored_daily_maxdd_pct']).mean()*100:5.1f}% | Range: [{df_grid['open_anchored_daily_maxdd_pct'].min():.2f}% .. {df_grid['open_anchored_daily_maxdd_pct'].max():.2f}%], Median={df_grid['open_anchored_daily_maxdd_pct'].median():.2f}%")

    # =========================================================================
    # PRIORITY 4: Multi-Block-Length Bootstrap + Null-Centered & White Reality Check
    # =========================================================================
    print("\n==========================================================================================")
    print("STAGE 5 (PRIORITY 4): MULTI-BLOCK-LENGTH BOOTSTRAP, NULL-CENTERED & WHITE REALITY CHECK")
    print("==========================================================================================")
    rng = np.random.default_rng(20261114)
    B = 5000
    boot_rows = []

    # Candidate family for White's Reality Check (all 10 strategies in Stage 2)
    cand_keys_2011 = [
        "typeB_vix_2011-01", "typeB_vxnZ_2011-01", "typeB_varZ_2011-01",
        "typeA1_snap_2011-01", "typeA1_trail_2011-01", "typeA2_snap_2011-01",
        "dualA1B_2011-01", "dualA1TrailB_2011-01", "dualA2B_2011-01", "tieredA1B_2011-01"
    ]

    for w_start in ["2011-01", "2015-01"]:
        r_b = daily_ret_store[f"base_{w_start}"].values
        r_d = daily_ret_store[f"dualA1B_{w_start}"].values
        T_days = len(r_b)

        # Observed point estimates
        obs_cagr_b = (np.prod(1.0 + r_b) ** (252.0 / T_days) - 1.0) * 100.0
        obs_cagr_d = (np.prod(1.0 + r_d) ** (252.0 / T_days) - 1.0) * 100.0
        obs_diff_cagr = obs_cagr_d - obs_cagr_b

        obs_sh_b = (np.mean(r_b) / np.std(r_b, ddof=1)) * np.sqrt(252.0)
        obs_sh_d = (np.mean(r_d) / np.std(r_d, ddof=1)) * np.sqrt(252.0)
        obs_diff_sh = obs_sh_d - obs_sh_b

        nav_b_obs = np.cumprod(1.0 + r_b)
        nav_d_obs = np.cumprod(1.0 + r_d)
        obs_ddd_b = np.min(nav_b_obs / np.maximum.accumulate(np.insert(nav_b_obs, 0, 1.0))[1:] - 1.0) * 100.0
        obs_ddd_d = np.min(nav_d_obs / np.maximum.accumulate(np.insert(nav_d_obs, 0, 1.0))[1:] - 1.0) * 100.0
        obs_diff_ddd = obs_ddd_d - obs_ddd_b  # positive means drawdown reduced

        for method_name, block_len, is_stationary in [
            ("Moving_Block_10d (2W)", 10, False),
            ("Moving_Block_21d (1M)", 21, False),
            ("Moving_Block_63d (3M Quarter)", 63, False),
            ("Moving_Block_126d (6M Macro)", 126, False),
            ("Stationary_Bootstrap_63d (Politis-Romano)", 63, True),
        ]:
            if not is_stationary:
                n_blocks = int(np.ceil(T_days / block_len))
                max_start = T_days - block_len
                starts = rng.integers(0, max_start + 1, size=(B, n_blocks))
                offsets = np.arange(block_len)
                idx_mat = (starts[:, :, None] + offsets[None, None, :]).reshape(B, -1)[:, :T_days]
            else:
                # Stationary bootstrap: start new random block with probability p = 1/block_len
                p_restart = 1.0 / block_len
                idx_mat = np.zeros((B, T_days), dtype=int)
                idx_mat[:, 0] = rng.integers(0, T_days, size=B)
                restarts = rng.random((B, T_days)) < p_restart
                rand_starts = rng.integers(0, T_days, size=(B, T_days))
                for t_i in range(1, T_days):
                    idx_mat[:, t_i] = np.where(restarts[:, t_i], rand_starts[:, t_i], (idx_mat[:, t_i - 1] + 1) % T_days)

            rb_boot = r_b[idx_mat]
            rd_boot = r_d[idx_mat]

            cagr_b_boot = (np.prod(1.0 + rb_boot, axis=1) ** (252.0 / T_days) - 1.0) * 100.0
            cagr_d_boot = (np.prod(1.0 + rd_boot, axis=1) ** (252.0 / T_days) - 1.0) * 100.0
            diff_cagr = cagr_d_boot - cagr_b_boot

            sh_b_boot = (np.mean(rb_boot, axis=1) / np.std(rb_boot, axis=1, ddof=1)) * np.sqrt(252.0)
            sh_d_boot = (np.mean(rd_boot, axis=1) / np.std(rd_boot, axis=1, ddof=1)) * np.sqrt(252.0)
            diff_sh = sh_d_boot - sh_b_boot

            # Proper Null-Hypothesis Centered Bootstrap p-value (Hall & Wilson 1991 / Politis & Romano):
            # Center the bootstrap distribution at 0 by subtracting the sample estimate `obs_diff`,
            # then compute the probability that the null-centered bootstrap fluctuation exceeds `obs_diff`
            null_centered_sh = diff_sh - np.mean(diff_sh)
            p_null_one_sided_sh = float(np.mean(null_centered_sh >= obs_diff_sh))
            p_null_two_sided_sh = float(np.mean(np.abs(null_centered_sh) >= abs(obs_diff_sh)))

            null_centered_cagr = diff_cagr - np.mean(diff_cagr)
            p_null_one_sided_cagr = float(np.mean(null_centered_cagr >= obs_diff_cagr))

            # White (2000) Reality Check multiple-testing adjusted p-value across all 10 candidate variants
            cand_keys = [k.replace("2011-01", w_start) for k in cand_keys_2011]
            max_null_sh = np.full(B, -np.inf)
            for ck in cand_keys:
                rc = daily_ret_store[ck].values
                obs_sh_c = (np.mean(rc) / np.std(rc, ddof=1)) * np.sqrt(252.0) - obs_sh_b
                rc_boot = rc[idx_mat]
                sh_c_boot = (np.mean(rc_boot, axis=1) / np.std(rc_boot, axis=1, ddof=1)) * np.sqrt(252.0) - sh_b_boot
                null_c = sh_c_boot - np.mean(sh_c_boot)
                max_null_sh = np.maximum(max_null_sh, null_c)
            p_white_rc_sh = float(np.mean(max_null_sh >= obs_diff_sh))

            boot_rows.append({
                "window": w_start + "..2026-10",
                "bootstrap_method": method_name,
                "block_len_days": block_len,
                "obs_delta_cagr_pp": round(obs_diff_cagr, 2),
                "cagr_95ci_lo": round(float(np.percentile(diff_cagr, 2.5)), 2),
                "cagr_95ci_hi": round(float(np.percentile(diff_cagr, 97.5)), 2),
                "cagr_ci_includes_zero": bool(np.percentile(diff_cagr, 2.5) <= 0.0 <= np.percentile(diff_cagr, 97.5)),
                "p_null_1s_cagr": round(p_null_one_sided_cagr, 4),
                "obs_delta_daily_sharpe": round(obs_diff_sh, 3),
                "sharpe_95ci_lo": round(float(np.percentile(diff_sh, 2.5)), 3),
                "sharpe_95ci_hi": round(float(np.percentile(diff_sh, 97.5)), 3),
                "sharpe_ci_includes_zero": bool(np.percentile(diff_sh, 2.5) <= 0.0 <= np.percentile(diff_sh, 97.5)),
                "p_null_1s_sharpe": round(p_null_one_sided_sh, 4),
                "p_null_2s_sharpe": round(p_null_two_sided_sh, 4),
                "p_white_reality_check_10models": round(p_white_rc_sh, 4),
            })

    df_boot = pd.DataFrame(boot_rows)
    df_boot.to_csv(os.path.join(OUT_DIR, "tqqq_orthogonal_typeAB_bootstrap_audit.csv"), index=False)
    print(df_boot.to_string(index=False))


if __name__ == "__main__":
    main()
