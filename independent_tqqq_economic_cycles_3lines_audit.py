#!/usr/bin/env python3
"""
Three Independent Economic Cycle Research Lines Audit for TQQQ + SEP
====================================================================
Tests the three theory-driven hypotheses proposed by the user across their natural
forecast horizons (1M, 3M, 6M, 12M), under 100% Point-in-Time (PIT) data rules
(SEC EDGAR filing dates + 1 day, Wayback S&P DJI EPS estimate vintages, and ALFRED
realtime vintages), evaluating both forward returns/drawdowns and the 3x daily-reset
volatility-compounding condition:
    g_3x ≈ 3*mu - 4.5*sigma^2 - Cost

Research Line A (Highest Priority): Profit Cycle × Real Interest Rate Cycle (4 Quadrants)
  - Track A1 (2010-03..2026-10, Live TQQQ & QQQ): SEC EDGAR 10-K/10-Q as-first-reported
    Nasdaq-100 constituent earnings diffusion (available_date = filed + 1 day <= t) × 10Y TIPS (DFII10).
  - Track A2 (2014-04..2026-10, Live TQQQ & QQQ): Wayback-archived S&P 500 IT Analyst Forward
    Consensus EPS 3M Revisions (available_date <= t) × 10Y TIPS (DFII10).
  - Track A3 (1999-04..2026-10, Full QQQ History incl. 2000 Dot-Com Type A & 2008 GFC Type B):
    ALFRED Point-in-Time Corporate Profits (CP) & Core Capex Orders (NEWORDER) × 10Y Real Rate.

Research Line B (High Priority): Monetary Policy Room & Inflation Constraint under SEP = ON
  - Compares SEP = ON (and Fed easing) when ALFRED PIT Core PCE / CPI & Market Breakevens
    (T5YIFR, T10YIE) are Anchored vs Inflation-Constrained, and distinguishes
    "Disinflationary / Healthy Easing (Profit Up + Rate Down)" vs "Rescue Easing (Profit Down + Rate Down)".

Research Line C (Medium Priority): Debt Service Burden (BIS DSR & ALFRED TDSP) × Future Volatility
  - Tests whether elevated/rising Debt Service Ratio (BIS US Private Nonfinancial DSR & ALFRED TDSP)
    predicts 1M, 3M, 6M, 12M future realized volatility sigma, volatility compounding drag (-4.5*sigma^2),
    and breakdown of the 3x log-growth condition (g_3x > g_1x).
"""

import os
import json
import numpy as np
import pandas as pd
from scipy.stats import spearmanr, mannwhitneyu, ttest_ind

import outputs.remediation_full_audit_20261104.run_full_8point_remediation_audit as r8
import independent_v4_symmetric_sharpe_top2_audit as v4_eng
import research.sector_stock_momentum.fundamentals_pit as fp

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE_DIR, "outputs", "v4_symmetric_sharpe_top2_20261113")
os.makedirs(OUT_DIR, exist_ok=True)


# =============================================================================
# 1. Point-in-Time Data Loaders (ALFRED Vintages, SEC EDGAR PIT, Wayback EPS)
# =============================================================================
def load_fred(sid):
    p = os.path.join(BASE_DIR, "data", "fred", f"{sid}.json")
    with open(p) as f:
        return pd.Series({
            pd.Timestamp(r[0]): float(r[1])
            for r in json.load(f)["values"]
            if r[1] not in (None, ".", "")
        }).sort_index()


def load_yahoo(sid):
    p = os.path.join(BASE_DIR, "data", "yahoo", f"{sid}.json")
    with open(p) as f:
        return pd.Series({
            pd.Timestamp(r[0]): float(r[1])
            for r in json.load(f)["values"]
            if r[1] not in (None, ".", "")
        }).sort_index()


def load_alfred_df(sid):
    p = os.path.join(BASE_DIR, "data", "alfred", f"{sid}_vintages.json")
    with open(p) as f:
        obs = json.load(f)["observations"]
    df = pd.DataFrame(obs)
    df["date"] = pd.to_datetime(df["date"])
    df["realtime_start"] = pd.to_datetime(df["realtime_start"])
    df["realtime_end"] = pd.to_datetime(df["realtime_end"].replace("9999-12-31", "2099-12-31"))
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.dropna(subset=["value"]).sort_values(["date", "realtime_start"]).reset_index(drop=True)


def alfred_pit_series_asof(df_alf, t_dt):
    """Return the exact historical time series visible on date t_dt (realtime_start <= t_dt)."""
    sub = df_alf[df_alf["realtime_start"] <= t_dt]
    if sub.empty:
        return pd.Series(dtype=float)
    dedup = sub.drop_duplicates(subset=["date"], keep="last")
    return pd.Series(dedup["value"].values, index=dedup["date"].values).sort_index()


def alfred_yoy_and_3m_asof(df_alf, t_dt, periods_yoy=12, periods_short=3):
    """Compute YoY growth and short-term change strictly from the ALFRED vintage visible on t_dt."""
    s = alfred_pit_series_asof(df_alf, t_dt)
    if len(s) < periods_yoy + 1:
        return np.nan, np.nan, np.nan
    cur = float(s.iloc[-1])
    prev_y = float(s.iloc[-1 - periods_yoy])
    prev_s = float(s.iloc[-1 - periods_short])
    yoy = (cur / prev_y - 1.0) * 100.0 if prev_y > 0 else np.nan
    chg_s = (cur / prev_s - 1.0) * 100.0 if prev_s > 0 else np.nan
    # Also compute YoY 1 period ago (to know if YoY growth is accelerating or decelerating)
    if len(s) >= periods_yoy + 2:
        yoy_prev = (float(s.iloc[-2]) / float(s.iloc[-2 - periods_yoy]) - 1.0) * 100.0
    else:
        yoy_prev = np.nan
    return yoy, chg_s, yoy - yoy_prev


def build_sec_edgar_ndx_profit_pit(months_list):
    """
    Strictly Point-in-Time Nasdaq-100 Constituent Earnings Diffusion & Growth from SEC 10-K/10-Q.
    Uses ONLY filings where (filed_net_income + 1 day <= t) and cik_valid(tk, t), as-first-reported.
    """
    p1 = pd.read_parquet(os.path.join(BASE_DIR, "research", "sector_stock_momentum", "data", "fundamentals", "eps_quarterly_pit.parquet"))
    p2 = pd.read_parquet(os.path.join(BASE_DIR, "research", "sector_stock_momentum", "data", "fundamentals_ndx", "eps_quarterly_pit.parquet"))
    df = pd.concat([p1, p2], ignore_index=True).drop_duplicates(subset=["ticker", "period_end", "filed"])
    df["period_end"] = pd.to_datetime(df["period_end"])
    df["avail_ni"] = pd.to_datetime(df["filed_net_income"]) + pd.Timedelta(days=1)
    df["avail_rev"] = pd.to_datetime(df["filed_revenue"]) + pd.Timedelta(days=1)
    df["avail_ni_ttm"] = pd.to_datetime(df["net_income_ttm_available_date"])

    p_ndx = v4_eng.p_ndx
    out = {}
    for t in months_list:
        t_dt = pd.Timestamp(t)
        ndx_tks = set(p_ndx[p_ndx["t"] == t_dt]["ticker"])
        if not ndx_tks:
            out[t_dt] = {"n_valid": 0, "breadth_yoy": np.nan, "median_ni_yoy": np.nan, "breadth_rev_yoy": np.nan}
            continue
        sub = df[df["ticker"].isin(ndx_tks) & (df["avail_ni"] <= t_dt) & df["net_income"].notna()].sort_values(["ticker", "period_end", "avail_ni"])
        n_valid, n_pos = 0, 0
        yoy_list = []
        for tk, g in sub.groupby("ticker"):
            if not fp.cik_valid(tk, t_dt):
                continue
            g_d = g.drop_duplicates(subset=["period_end"], keep="last").sort_values("period_end")
            if len(g_d) < 2:
                continue
            cur = g_d.iloc[-1]
            if (t_dt - cur["period_end"]).days > 200:
                continue
            diffs = (cur["period_end"] - g_d["period_end"]).dt.days
            prev_y = g_d[(diffs >= 330) & (diffs <= 400)]
            if len(prev_y) > 0:
                ni_cur = float(cur["net_income"])
                ni_old = float(prev_y.iloc[-1]["net_income"])
                n_valid += 1
                if ni_cur > ni_old:
                    n_pos += 1
                if abs(ni_old) > 1e-3:
                    yoy_list.append((ni_cur - ni_old) / abs(ni_old))
        out[t_dt] = {
            "n_valid": n_valid,
            "breadth_yoy": (n_pos / n_valid * 100.0) if n_valid >= 25 else np.nan,
            "median_ni_yoy": (float(np.median(yoy_list)) * 100.0) if len(yoy_list) >= 25 else np.nan,
        }
    df_out = pd.DataFrame.from_dict(out, orient="index").sort_index()
    df_out["breadth_chg_3m"] = df_out["breadth_yoy"].diff(3)
    df_out["breadth_chg_6m"] = df_out["breadth_yoy"].diff(6)
    df_out["median_yoy_chg_3m"] = df_out["median_ni_yoy"].diff(3)
    return df_out


def build_wayback_it_forward_eps_revisions(months_list):
    """
    Strictly Point-in-Time Analyst Forward Consensus Operating EPS Revisions for S&P 500 IT
    from Wayback-archived S&P Dow Jones Indices spreadsheets (available_date <= t).
    """
    vint = pd.read_csv(os.path.join(BASE_DIR, "outputs", "sector_eps_then_momentum_20261030", "recovered_sector_eps_vintages.csv"))
    vint["available_date"] = pd.to_datetime(vint["available_date"])
    vint["quarter_end"] = pd.to_datetime(vint["quarter_end"])
    it = vint[(vint["sector"] == "Information Technology") & (vint["basis"] == "operating")].copy()

    # Group by vintage_id
    v_meta = it.groupby("vintage_id")["available_date"].first().reset_index().sort_values("available_date")

    out = {}
    for t in months_list:
        t_dt = pd.Timestamp(t)
        elig_v = v_meta[v_meta["available_date"] <= t_dt]
        if elig_v.empty:
            out[t_dt] = {"it_fwd_rev_3m_pct": np.nan, "it_fwd_vs_trail_pct": np.nan}
            continue
        vid_now = elig_v.iloc[-1]["vintage_id"]
        dt_now = elig_v.iloc[-1]["available_date"]
        if (t_dt - dt_now).days > 120:
            out[t_dt] = {"it_fwd_rev_3m_pct": np.nan, "it_fwd_vs_trail_pct": np.nan}
            continue

        # Find vintage ~3 months earlier (between 60 and 135 days before t_dt)
        elig_prev = v_meta[(v_meta["available_date"] <= t_dt - pd.Timedelta(days=60)) &
                           (v_meta["available_date"] >= t_dt - pd.Timedelta(days=150))]
        g_now = it[it["vintage_id"] == vid_now].drop_duplicates(subset=["quarter"], keep="last").sort_values("quarter_end")

        # Forward 4 quarters vs trailing 4 actual quarters in current vintage
        act_now = g_now[g_now["status"] == "actual"].tail(4)
        est_now = g_now[g_now["status"] == "estimate"].head(4)
        if len(act_now) == 4 and len(est_now) >= 2:
            trail_4q = float(act_now["eps"].sum())
            fwd_4q = float(est_now["eps"].mean() * 4.0)
            fwd_vs_trail = (fwd_4q / trail_4q - 1.0) * 100.0 if trail_4q > 0 else np.nan
        else:
            fwd_vs_trail = np.nan

        rev_3m = np.nan
        if not elig_prev.empty:
            # Pick vintage closest to t_dt - 91 days
            idx_best = (elig_prev["available_date"] - (t_dt - pd.Timedelta(days=91))).abs().idxmin()
            vid_prev = elig_prev.loc[idx_best, "vintage_id"]
            g_prev = it[it["vintage_id"] == vid_prev].drop_duplicates(subset=["quarter"], keep="last")
            # Compare identical forward quarters (quarter_end >= t_dt - 30 days)
            fwd_qs = g_now[g_now["quarter_end"] >= t_dt - pd.Timedelta(days=45)][["quarter", "eps"]].rename(columns={"eps": "eps_now"})
            merged = fwd_qs.merge(g_prev[["quarter", "eps"]].rename(columns={"eps": "eps_prev"}), on="quarter", how="inner")
            if len(merged) >= 2 and merged["eps_prev"].sum() > 0:
                rev_3m = (merged["eps_now"].sum() / merged["eps_prev"].sum() - 1.0) * 100.0

        out[t_dt] = {"it_fwd_rev_3m_pct": rev_3m, "it_fwd_vs_trail_pct": fwd_vs_trail}
    return pd.DataFrame.from_dict(out, orient="index").sort_index()


# =============================================================================
# 2. Build Multi-Horizon Forward Return & Volatility-Compounding Panel
# =============================================================================
def main():
    df_tqqq = r8.load_tiingo_etf_df("TQQQ")
    df_qqq_tiingo = r8.load_tiingo_etf_df("QQQ")
    yq_s = load_yahoo("QQQ")
    join_dt = df_qqq_tiingo.index.min()  # 2007-01-03
    scale_q = float(df_qqq_tiingo.at[join_dt, "c"] / yq_s.at[join_dt])
    yq_pre = yq_s.loc[yq_s.index < join_dt] * scale_q
    df_qqq_pre = pd.DataFrame({"c": yq_pre.values, "o": yq_pre.values}, index=yq_pre.index)
    df_qqq = pd.concat([df_qqq_pre, df_qqq_tiingo[["c", "o"]]]).sort_index()
    df_qqq = df_qqq[~df_qqq.index.duplicated(keep="last")]

    df_sgov = r8.load_tiingo_etf_df("SGOV")
    df_bil = r8.load_tiingo_etf_df("BIL")
    spy_c = load_yahoo("SPY")

    rf_s = load_fred("DGS3MO") / 100.0
    dff_s = load_fred("DFF")
    dfii10_s = load_fred("DFII10")
    dltiit_s = load_fred("DLTIIT")
    reaintr_s = load_fred("REAINTRATREARAT10Y")
    t10yie_s = load_fred("T10YIE")
    t5yifr_s = load_fred("T5YIFR")
    expinf10_s = load_fred("EXPINF10YR")
    mich_s = load_fred("MICH")

    # ALFRED Vintage archives
    alf_cp = load_alfred_df("CP")
    alf_neworder = load_alfred_df("NEWORDER")
    alf_pce = load_alfred_df("PCEPILFE")
    alf_cpi = load_alfred_df("CPIAUCSL")
    alf_ccpi = load_alfred_df("CPILFESL")
    alf_tdsp = load_alfred_df("TDSP")

    # Official BIS Debt Service Ratio for US (1999-Q1 .. 2026-Q1)
    with open(os.path.join(BASE_DIR, "data", "valuation", "BIS_DSR_US.json")) as f:
        bis_raw = json.load(f)["data"]

    def parse_bis_pit(rows):
        # Quarter Q1 ends Mar 31, published by BIS with ~1 quarter lag -> available at next quarter-end + 1 month (~120 days after quarter end)
        recs = []
        for q_str, val in rows:
            yr, q_num = int(q_str[:4]), int(q_str[-1])
            q_end = pd.Timestamp(yr, q_num * 3, 1) + pd.offsets.MonthEnd(1)
            avail_dt = q_end + pd.Timedelta(days=95)  # Strict 1-quarter publication lag
            recs.append((q_end, avail_dt, float(val)))
        return pd.DataFrame(recs, columns=["q_end", "avail_dt", "val"]).sort_values("q_end")

    bis_priv = parse_bis_pit(bis_raw["Private_Nonfinancial"])
    bis_corp = parse_bis_pit(bis_raw["Nonfinancial_Corporations"])
    bis_hh = parse_bis_pit(bis_raw["Households"])

    # Full monthly calendar from 1999-03-31 to 2026-09-30 (331 months of real QQQ data)
    cal = df_qqq.index.sort_values()
    qqq_c, qqq_o = df_qqq["c"], df_qqq["o"]
    qqq_r = qqq_c.pct_change().fillna(0.0)

    tqqq_c, tqqq_o = df_tqqq["c"], df_tqqq["o"]
    tqqq_r = tqqq_c.pct_change().fillna(0.0)

    months_full = pd.date_range("1999-03-31", "2026-09-30", freq="ME")
    reg_map_214 = v4_eng.reg_map

    # Precompute SEC EDGAR PIT & Wayback IT Forward EPS revisions
    sec_pit_df = build_sec_edgar_ndx_profit_pit([t for t in months_full if t >= pd.Timestamp("2008-12-31")])
    wb_pit_df = build_wayback_it_forward_eps_revisions([t for t in months_full if t >= pd.Timestamp("2013-12-31")])

    # Helper to compute forward h-month open-to-open return, realized vol, maxDD, and 3x compounding metrics
    def forward_metrics(t_dt, h_months):
        d0_idx = cal.searchsorted(t_dt, side="right")
        if d0_idx >= len(cal):
            return None
        d0 = cal[d0_idx]

        t_end = t_dt + pd.offsets.MonthEnd(h_months)
        if t_end > pd.Timestamp("2026-10-31"):
            return None
        if t_end == pd.Timestamp("2026-10-31"):
            d1 = pd.Timestamp("2026-10-29")
            p_col = "c"
            w_days = cal[(cal >= d0) & (cal <= d1)]
        else:
            d1_idx = cal.searchsorted(t_end, side="right")
            if d1_idx >= len(cal):
                return None
            d1 = cal[d1_idx]
            p_col = "o"
            w_days = cal[(cal >= d0) & (cal < d1)]

        if len(w_days) < 10:
            return None

        # QQQ metrics (Real ETF from 1999-03-10 onward)
        q_start = float(df_qqq.loc[:d0, "o"].iloc[-1])
        q_end = float(df_qqq.loc[:d1, p_col].iloc[-1])
        q_ret = q_end / q_start - 1.0
        q_daily = qqq_r.loc[w_days]
        q_vol_ann = float(q_daily.std(ddof=1) * np.sqrt(252.0))
        q_mu_ann = float(q_daily.mean() * 252.0)
        q_cum = (1.0 + q_daily).cumprod()
        q_mdd = float((q_cum / q_cum.cummax() - 1.0).min())

        # Risk-free rate over horizon
        rf_ann = float(rf_s.loc[:t_dt].iloc[-1]) if len(rf_s.loc[:t_dt]) else 0.02
        rf_h = (1.0 + rf_ann) ** (h_months / 12.0) - 1.0

        # Theoretical 3x annualized log-growth rate: g_3x = 3*mu - 4.5*sigma^2 - (2*rf + 0.0195)
        cost_3x_ann = 2.0 * rf_ann + 0.0195
        g_1x_theo_ann = q_mu_ann - 0.5 * (q_vol_ann ** 2)
        g_3x_theo_ann = 3.0 * q_mu_ann - 4.5 * (q_vol_ann ** 2) - cost_3x_ann
        vol_drag_3x_ann = 4.5 * (q_vol_ann ** 2)
        # Condition for 3x to beat 1x in log-compounding: mu > 2*sigma^2 + 0.5*cost_3x
        comp_spread_theo = g_3x_theo_ann - g_1x_theo_ann

        # Live TQQQ metrics (ONLY if d0 >= 2010-02-11, never mixing pre-2010 simulated TQQQ!)
        if d0 >= pd.Timestamp("2010-02-12"):
            tq_start = float(df_tqqq.loc[:d0, "o"].iloc[-1])
            tq_end = float(df_tqqq.loc[:d1, p_col].iloc[-1])
            tq_ret = tq_end / tq_start - 1.0
            tq_daily = tqqq_r.loc[w_days]
            tq_cum = (1.0 + tq_daily).cumprod()
            tq_mdd = float((tq_cum / tq_cum.cummax() - 1.0).min())
            g_tq_real_ann = float(np.log(max(1e-6, 1.0 + tq_ret)) * (12.0 / h_months))
            g_qq_real_ann = float(np.log(max(1e-6, 1.0 + q_ret)) * (12.0 / h_months))
        else:
            tq_ret = np.nan
            tq_mdd = np.nan
            g_tq_real_ann = np.nan
            g_qq_real_ann = float(np.log(max(1e-6, 1.0 + q_ret)) * (12.0 / h_months))

        return {
            f"qqq_ret_{h_months}m": q_ret * 100.0,
            f"qqq_ex_{h_months}m": (q_ret - rf_h) * 100.0,
            f"qqq_vol_{h_months}m": q_vol_ann * 100.0,
            f"qqq_mdd_{h_months}m": q_mdd * 100.0,
            f"g3x_theo_ann_{h_months}m": g_3x_theo_ann * 100.0,
            f"g1x_theo_ann_{h_months}m": g_1x_theo_ann * 100.0,
            f"comp_spread_theo_{h_months}m": comp_spread_theo * 100.0,
            f"vol_drag_3x_{h_months}m": vol_drag_3x_ann * 100.0,
            f"tqqq_live_ret_{h_months}m": tq_ret * 100.0 if np.isfinite(tq_ret) else np.nan,
            f"tqqq_live_mdd_{h_months}m": tq_mdd * 100.0 if np.isfinite(tq_mdd) else np.nan,
            f"g_tqqq_live_ann_{h_months}m": g_tq_real_ann * 100.0 if np.isfinite(g_tq_real_ann) else np.nan,
            f"g_qqq_real_ann_{h_months}m": g_qq_real_ann * 100.0,
        }

    rows = []
    for t in months_full:
        hold_ym = (t + pd.offsets.MonthBegin(1)).strftime("%Y-%m")
        # 1. SEP / Policy State
        if t in reg_map_214:
            sep_on = bool(reg_map_214[t]["sep_on"])
        else:
            # Pre-2009: Before FOMC SEP dot plot existed, check if Fed Funds Rate (DFF) was raised over prior 6M while Core PCE > 2.0%
            dff_cur = float(dff_s.loc[:t].iloc[-1])
            dff_6m = float(dff_s.loc[:t - pd.Timedelta(days=182)].iloc[-1])
            pce_yoy_pre, _, _ = alfred_yoy_and_3m_asof(alf_pce, t, 12, 3)
            sep_on = not ((dff_cur > dff_6m + 0.20) and (np.isfinite(pce_yoy_pre) and pce_yoy_pre > 2.0))

        # Fed Funds 6M change (is Fed easing/accommodative vs tightening?)
        dff_now = float(dff_s.loc[:t].iloc[-1])
        dff_6m_ago = float(dff_s.loc[:t - pd.Timedelta(days=182)].iloc[-1])
        dff_chg_6m = dff_now - dff_6m_ago

        # 2. Real Interest Rate (10Y TIPS DFII10 from 2003-01+, spliced with DLTIIT/REAINTRATREARAT10Y pre-2003)
        if len(dfii10_s.loc[:t]) >= 65:
            rr_now = float(dfii10_s.loc[:t].iloc[-1])
            rr_3m = float(dfii10_s.loc[:t - pd.Timedelta(days=91)].iloc[-1])
            rr_6m = float(dfii10_s.loc[:t - pd.Timedelta(days=182)].iloc[-1]) if len(dfii10_s.loc[:t - pd.Timedelta(days=182)]) else rr_3m
        elif len(dltiit_s.loc[:t]) >= 65:
            rr_now = float(dltiit_s.loc[:t].iloc[-1])
            rr_3m = float(dltiit_s.loc[:t - pd.Timedelta(days=91)].iloc[-1])
            rr_6m = float(dltiit_s.loc[:t - pd.Timedelta(days=182)].iloc[-1]) if len(dltiit_s.loc[:t - pd.Timedelta(days=182)]) else rr_3m
        else:
            rr_now = float(reaintr_s.loc[:t].iloc[-1])
            rr_3m = float(reaintr_s.loc[:t - pd.Timedelta(days=91)].iloc[-1])
            rr_6m = float(reaintr_s.loc[:t - pd.Timedelta(days=182)].iloc[-1])
        rr_chg_3m = rr_now - rr_3m
        rr_chg_6m = rr_now - rr_6m

        # 3. ALFRED Point-in-Time Corporate Profits (CP) & Core Capex Orders (NEWORDER)
        cp_yoy, cp_qoq, cp_accel = alfred_yoy_and_3m_asof(alf_cp, t, periods_yoy=4, periods_short=1)
        no_yoy, no_3m, no_accel = alfred_yoy_and_3m_asof(alf_neworder, t, periods_yoy=12, periods_short=3)

        # 4. ALFRED Point-in-Time Inflation & Market Breakevens
        pce_yoy, pce_3m, pce_accel = alfred_yoy_and_3m_asof(alf_pce, t, periods_yoy=12, periods_short=3)
        cpi_yoy, cpi_3m, _ = alfred_yoy_and_3m_asof(alf_cpi, t, periods_yoy=12, periods_short=3)
        ccpi_yoy, ccpi_3m, _ = alfred_yoy_and_3m_asof(alf_ccpi, t, periods_yoy=12, periods_short=3)

        if len(t10yie_s.loc[:t]) >= 65:
            bei_now = float(t10yie_s.loc[:t].iloc[-1])
            bei_3m = float(t10yie_s.loc[:t - pd.Timedelta(days=91)].iloc[-1])
        else:
            bei_now = float(expinf10_s.loc[:t].iloc[-1])
            bei_3m = float(expinf10_s.loc[:t - pd.Timedelta(days=91)].iloc[-1])
        bei_chg_3m = bei_now - bei_3m

        if len(t5yifr_s.loc[:t]) >= 65:
            f5y5y_now = float(t5yifr_s.loc[:t].iloc[-1])
            f5y5y_3m = float(t5yifr_s.loc[:t - pd.Timedelta(days=91)].iloc[-1])
        else:
            f5y5y_now = bei_now
            f5y5y_3m = bei_3m
        f5y5y_chg_3m = f5y5y_now - f5y5y_3m

        # 5. Debt Service Burden (BIS Private Nonfinancial DSR & ALFRED TDSP)
        b_p = bis_priv[bis_priv["avail_dt"] <= t]
        if len(b_p) >= 5:
            bis_dsr_priv = float(b_p.iloc[-1]["val"])
            bis_dsr_priv_yoy = bis_dsr_priv - float(b_p.iloc[-5]["val"])
            bis_dsr_priv_qoq = bis_dsr_priv - float(b_p.iloc[-2]["val"])
        else:
            bis_dsr_priv, bis_dsr_priv_yoy, bis_dsr_priv_qoq = np.nan, np.nan, np.nan

        b_c = bis_corp[bis_corp["avail_dt"] <= t]
        if len(b_c) >= 5:
            bis_dsr_corp = float(b_c.iloc[-1]["val"])
            bis_dsr_corp_yoy = bis_dsr_corp - float(b_c.iloc[-5]["val"])
        else:
            bis_dsr_corp, bis_dsr_corp_yoy = np.nan, np.nan

        tdsp_s = alfred_pit_series_asof(alf_tdsp, t)
        if len(tdsp_s) >= 5:
            tdsp_now = float(tdsp_s.iloc[-1])
            tdsp_yoy = tdsp_now - float(tdsp_s.iloc[-5])
        else:
            tdsp_now, tdsp_yoy = np.nan, np.nan

        # 6. Constituent SEC EDGAR PIT & Wayback Forward EPS
        sec_row = sec_pit_df.loc[t] if t in sec_pit_df.index else None
        wb_row = wb_pit_df.loc[t] if t in wb_pit_df.index else None

        rec = {
            "t": t,
            "hold_ym": hold_ym,
            "sep_on": sep_on,
            "dff_now": dff_now,
            "dff_chg_6m": dff_chg_6m,
            "rr_now": rr_now,
            "rr_chg_3m": rr_chg_3m,
            "rr_chg_6m": rr_chg_6m,
            "cp_yoy": cp_yoy,
            "cp_qoq": cp_qoq,
            "no_yoy": no_yoy,
            "no_3m": no_3m,
            "pce_yoy": pce_yoy,
            "pce_3m": pce_3m,
            "cpi_yoy": cpi_yoy,
            "ccpi_yoy": ccpi_yoy,
            "bei_now": bei_now,
            "bei_chg_3m": bei_chg_3m,
            "f5y5y_now": f5y5y_now,
            "f5y5y_chg_3m": f5y5y_chg_3m,
            "bis_dsr_priv": bis_dsr_priv,
            "bis_dsr_priv_yoy": bis_dsr_priv_yoy,
            "bis_dsr_corp": bis_dsr_corp,
            "bis_dsr_corp_yoy": bis_dsr_corp_yoy,
            "tdsp_now": tdsp_now,
            "tdsp_yoy": tdsp_yoy,
            "ndx_breadth_yoy": float(sec_row["breadth_yoy"]) if sec_row is not None else np.nan,
            "ndx_breadth_chg_3m": float(sec_row["breadth_chg_3m"]) if sec_row is not None else np.nan,
            "ndx_median_ni_yoy": float(sec_row["median_ni_yoy"]) if sec_row is not None else np.nan,
            "it_fwd_rev_3m_pct": float(wb_row["it_fwd_rev_3m_pct"]) if wb_row is not None else np.nan,
            "it_fwd_vs_trail_pct": float(wb_row["it_fwd_vs_trail_pct"]) if wb_row is not None else np.nan,
        }

        for h in (1, 3, 6, 12):
            fm = forward_metrics(t, h)
            if fm is not None:
                rec.update(fm)
        rows.append(rec)

    panel = pd.DataFrame(rows)
    panel.to_csv(os.path.join(OUT_DIR, "tqqq_econ_cycles_master_panel.csv"), index=False)

    # =========================================================================
    # Helper to summarize a regime grouping across 1M, 3M, 6M, 12M
    # =========================================================================
    def summarize_groups(df_sub, group_col, label_prefix):
        summary_rows = []
        for grp, g in df_sub.groupby(group_col, sort=True):
            row = {"Experiment": label_prefix, "Regime": grp, "N_Months": len(g)}
            for h in (1, 3, 6, 12):
                col_q = f"qqq_ret_{h}m"
                col_qv = f"qqq_vol_{h}m"
                col_qmdd = f"qqq_mdd_{h}m"
                col_g3 = f"g3x_theo_ann_{h}m"
                col_cs = f"comp_spread_theo_{h}m"
                col_tq = f"tqqq_live_ret_{h}m"
                col_tqmdd = f"tqqq_live_mdd_{h}m"
                col_gtq = f"g_tqqq_live_ann_{h}m"

                vq = g[col_q].dropna()
                row[f"QQQ_Mean_{h}M_%"] = float(vq.mean()) if len(vq) else np.nan
                row[f"QQQ_Win_{h}M_%"] = float((vq > 0).mean() * 100.0) if len(vq) else np.nan
                row[f"QQQ_Vol_{h}M_%"] = float(g[col_qv].dropna().mean()) if len(g[col_qv].dropna()) else np.nan
                row[f"QQQ_WorstDD_{h}M_%"] = float(g[col_qmdd].dropna().min()) if len(g[col_qmdd].dropna()) else np.nan
                row[f"Theo_g3x_Ann_{h}M_%"] = float(g[col_g3].dropna().mean()) if len(g[col_g3].dropna()) else np.nan
                row[f"Theo_3x_Beats_1x_{h}M_%"] = float((g[col_cs].dropna() > 0).mean() * 100.0) if len(g[col_cs].dropna()) else np.nan

                vtq = g[col_tq].dropna()
                if len(vtq) > 0:
                    row[f"TQQQ_Live_N_{h}M"] = len(vtq)
                    row[f"TQQQ_Live_Mean_{h}M_%"] = float(vtq.mean())
                    row[f"TQQQ_Live_GeoAnn_{h}M_%"] = float((np.exp(g[col_gtq].dropna().mean() / 100.0) - 1.0) * 100.0)
                    row[f"TQQQ_Live_WorstDD_{h}M_%"] = float(g[col_tqmdd].dropna().min())
                else:
                    row[f"TQQQ_Live_N_{h}M"] = 0
                    row[f"TQQQ_Live_Mean_{h}M_%"] = np.nan
                    row[f"TQQQ_Live_GeoAnn_{h}M_%"] = np.nan
                    row[f"TQQQ_Live_WorstDD_{h}M_%"] = np.nan
            summary_rows.append(row)
        return pd.DataFrame(summary_rows)

    # =========================================================================
    # EXPERIMENT A: Profit Cycle × Real Interest Rate (4 Quadrants)
    # =========================================================================
    print("=" * 105)
    print("EXPERIMENT A: PROFIT CYCLE × REAL INTEREST RATE CYCLE (4 QUADRANTS UNDER SEP = ON)")
    print("=" * 105)

    def make_quadrant(prof_up, rr_up):
        if pd.isna(prof_up) or pd.isna(rr_up):
            return np.nan
        if prof_up and (not rr_up):
            return "Q1_ProfitUp_RealRateDown (Best)"
        elif prof_up and rr_up:
            return "Q2_ProfitUp_RealRateUp (Expansion)"
        elif (not prof_up) and (not rr_up):
            return "Q3_ProfitDown_RealRateDown (BlindSpot)"
        else:
            return "Q4_ProfitDown_RealRateUp (DoubleSqueeze)"

    # Track A1: Live TQQQ Era (2010-06..2026-09, SEP=ON), Constituent SEC EDGAR PIT Earnings Breadth (3M Change >= 0 vs < 0)
    p_a1 = panel[(panel["t"] >= "2010-06-30") & (panel["sep_on"]) & panel["ndx_breadth_chg_3m"].notna()].copy()
    p_a1["quad_a1"] = [
        make_quadrant(b_chg >= 0.0, rr_chg > 0.0)
        for b_chg, rr_chg in zip(p_a1["ndx_breadth_chg_3m"], p_a1["rr_chg_3m"])
    ]
    df_a1 = summarize_groups(p_a1, "quad_a1", "A1_SEC_EDGAR_NDX_BreadthChg3M_SEP_ON")

    # Track A1b: SEC EDGAR PIT Earnings Breadth Level (>= 65% vs < 65% majority expansion)
    p_a1b = panel[(panel["t"] >= "2010-03-31") & (panel["sep_on"]) & panel["ndx_breadth_yoy"].notna()].copy()
    p_a1b["quad_a1b"] = [
        make_quadrant(b_lvl >= 65.0, rr_chg > 0.0)
        for b_lvl, rr_chg in zip(p_a1b["ndx_breadth_yoy"], p_a1b["rr_chg_3m"])
    ]
    df_a1b = summarize_groups(p_a1b, "quad_a1b", "A1b_SEC_EDGAR_NDX_BreadthLvl65_SEP_ON")

    # Track A2: Wayback Archived S&P 500 IT Analyst Forward EPS 3M Revision (>= 0 vs < 0, 2014-04..2026-06, SEP=ON)
    p_a2 = panel[(panel["t"] >= "2014-04-30") & (panel["sep_on"]) & panel["it_fwd_rev_3m_pct"].notna()].copy()
    p_a2["quad_a2"] = [
        make_quadrant(rev >= 0.0, rr_chg > 0.0)
        for rev, rr_chg in zip(p_a2["it_fwd_rev_3m_pct"], p_a2["rr_chg_3m"])
    ]
    df_a2 = summarize_groups(p_a2, "quad_a2", "A2_Wayback_IT_FwdEPS_Rev3M_SEP_ON")

    # Track A3: Full QQQ Cycle (1999-03..2026-09, incl. 2000 Dot-Com & 2008 GFC, SEP=ON)
    # Using ALFRED Vintage Corporate Profits YoY > 0 & Core Capex Orders (NEWORDER) YoY > 0
    p_a3 = panel[panel["sep_on"] & panel["cp_yoy"].notna() & panel["no_yoy"].notna()].copy()
    p_a3["prof_macro_up"] = (p_a3["cp_yoy"] > 0.0) & (p_a3["no_yoy"] > 0.0)
    p_a3["quad_a3"] = [
        make_quadrant(p_up, rr_chg > 0.0)
        for p_up, rr_chg in zip(p_a3["prof_macro_up"], p_a3["rr_chg_3m"])
    ]
    df_a3 = summarize_groups(p_a3, "quad_a3", "A3_Full1999_2026_ALFRED_CP_Capex_SEP_ON")

    df_exp_a = pd.concat([df_a1, df_a1b, df_a2, df_a3], ignore_index=True)
    df_exp_a.to_csv(os.path.join(OUT_DIR, "tqqq_expA_profit_real_rate_quadrants.csv"), index=False)

    cols_print = [
        "Experiment", "Regime", "N_Months",
        "QQQ_Mean_1M_%", "QQQ_Mean_3M_%", "QQQ_Mean_6M_%",
        "QQQ_Vol_3M_%", "Theo_g3x_Ann_3M_%",
        "TQQQ_Live_Mean_1M_%", "TQQQ_Live_Mean_3M_%", "TQQQ_Live_GeoAnn_3M_%", "TQQQ_Live_WorstDD_3M_%"
    ]
    print(df_exp_a[cols_print].to_string(index=False, float_format=lambda x: f"{x:.2f}"))

    # =========================================================================
    # EXPERIMENT B: Monetary Policy Room & Inflation Constraint
    # =========================================================================
    print("\n" + "=" * 105)
    print("EXPERIMENT B: MONETARY POLICY ROOM & INFLATION CONSTRAINT UNDER SEP = ON (AND FED EASING)")
    print("=" * 105)

    # Track B1: SEP = ON (1999-2026 Full & 2010-2026 Live TQQQ) split by ALFRED PIT Core PCE & Breakeven Stability
    p_b1 = panel[panel["sep_on"] & panel["pce_yoy"].notna()].copy()
    # Inflation constrained / unanchored risk: ALFRED PIT Core PCE YoY > 2.5% OR (Breakeven > 2.3% and rising > +15bp in 3M)
    p_b1["infl_state"] = np.where(
        (p_b1["pce_yoy"] <= 2.5) & ~((p_b1["bei_now"] > 2.3) & (p_b1["bei_chg_3m"] > 0.15)),
        "B1_Anchored_Inflation (PCE<=2.5% & BEI Stable)",
        "B2_Elevated_or_Unanchoring_Inflation (PCE>2.5% or BEI Surge)"
    )
    df_b_full = summarize_groups(p_b1, "infl_state", "B_Full1999_2026_SEP_ON")
    df_b_live = summarize_groups(p_b1[p_b1["t"] >= "2010-03-31"], "infl_state", "B_Live2010_2026_SEP_ON")

    # Track B2: Disentangling WHY the Fed is cutting / easing (dff_chg_6m <= -0.10% or rr_chg_6m <= -0.15%)
    # Celebration / Disinflation Easing (Profit Up + Inflation Anchored) vs Rescue Easing (Profit Down) vs Inflation-Constrained
    p_b2 = panel[panel["sep_on"] & panel["cp_yoy"].notna() & panel["no_yoy"].notna() & panel["pce_yoy"].notna()].copy()
    prof_up_vec = (p_b2["cp_yoy"] > 0.0) & (p_b2["no_yoy"] > 0.0)
    infl_anc_vec = (p_b2["pce_yoy"] <= 2.5)
    b2_labels = []
    for p_u, i_a in zip(prof_up_vec, infl_anc_vec):
        if p_u and i_a:
            b2_labels.append("1_Healthy_Anchored_Expansion (ProfitUp + PCE<=2.5%)")
        elif p_u and (not i_a):
            b2_labels.append("2_Inflationary_Boom (ProfitUp + PCE>2.5%)")
        elif (not p_u) and i_a:
            b2_labels.append("3_Rescue_Easing_Profit_Recession (ProfitDown + PCE<=2.5%)")
        else:
            b2_labels.append("4_Stagflation_Squeeze (ProfitDown + PCE>2.5%)")
    p_b2["policy_profit_regime"] = b2_labels
    df_b2 = summarize_groups(p_b2, "policy_profit_regime", "B2_PolicyRoom_x_ProfitCycle_1999_2026")

    df_exp_b = pd.concat([df_b_full, df_b_live, df_b2], ignore_index=True)
    df_exp_b.to_csv(os.path.join(OUT_DIR, "tqqq_expB_monetary_policy_inflation_constraint.csv"), index=False)
    print(df_exp_b[cols_print].to_string(index=False, float_format=lambda x: f"{x:.2f}"))

    # =========================================================================
    # EXPERIMENT C: Debt Service Burden (BIS DSR & ALFRED TDSP) × Future Volatility
    # =========================================================================
    print("\n" + "=" * 105)
    print("EXPERIMENT C: DEBT SERVICE RATIO (BIS DSR & ALFRED TDSP) × FUTURE VOLATILITY & 3x COMPOUNDING")
    print("=" * 105)

    p_c1 = panel[panel["bis_dsr_priv_yoy"].notna()].copy()
    p_c1["bis_dsr_state"] = np.where(
        p_c1["bis_dsr_priv_yoy"] <= 0.0,
        "C1_BIS_Private_DSR_Falling_or_Flat (YoY <= 0)",
        "C2_BIS_Private_DSR_Rising (YoY > 0, Debt BurdenTightening)"
    )
    df_c1_all = summarize_groups(p_c1, "bis_dsr_state", "C1_BIS_Private_DSR_1999_2026_All")
    df_c1_sep = summarize_groups(p_c1[p_c1["sep_on"]], "bis_dsr_state", "C1_BIS_Private_DSR_1999_2026_SEP_ON")

    p_c2 = panel[panel["bis_dsr_corp_yoy"].notna() & panel["sep_on"]].copy()
    p_c2["bis_corp_state"] = np.where(
        p_c2["bis_dsr_corp_yoy"] <= 0.2,
        "C1_BIS_Corp_DSR_Benign (YoY <= +0.2pp)",
        "C2_BIS_Corp_DSR_Rising (YoY > +0.2pp)"
    )
    df_c2_sep = summarize_groups(p_c2, "bis_corp_state", "C2_BIS_Corp_DSR_1999_2026_SEP_ON")

    p_c3 = panel[panel["tdsp_yoy"].notna() & panel["sep_on"]].copy()
    p_c3["tdsp_state"] = np.where(
        p_c3["tdsp_yoy"] <= 0.0,
        "C1_ALFRED_TDSP_Falling (YoY <= 0)",
        "C2_ALFRED_TDSP_Rising (YoY > 0)"
    )
    df_c3_sep = summarize_groups(p_c3, "tdsp_state", "C3_ALFRED_Household_TDSP_2006_2026_SEP_ON")

    df_exp_c = pd.concat([df_c1_all, df_c1_sep, df_c2_sep, df_c3_sep], ignore_index=True)
    df_exp_c.to_csv(os.path.join(OUT_DIR, "tqqq_expC_debt_service_volatility_compounding.csv"), index=False)

    cols_print_c = [
        "Experiment", "Regime", "N_Months",
        "QQQ_Vol_1M_%", "QQQ_Vol_3M_%", "QQQ_Vol_6M_%", "QQQ_Vol_12M_%",
        "QQQ_Mean_6M_%", "QQQ_Mean_12M_%",
        "Theo_g3x_Ann_6M_%", "Theo_g3x_Ann_12M_%",
        "TQQQ_Live_GeoAnn_6M_%", "TQQQ_Live_GeoAnn_12M_%"
    ]
    print(df_exp_c[cols_print_c].to_string(index=False, float_format=lambda x: f"{x:.2f}"))

    # Continuous correlation test across horizons (1M, 3M, 6M, 12M) for all 3 lines
    corr_rows = []
    predictors = [
        ("A_SEC_EDGAR_NDX_Breadth_YoY", "ndx_breadth_yoy", True),
        ("A_SEC_EDGAR_NDX_Breadth_Chg3M", "ndx_breadth_chg_3m", True),
        ("A_Wayback_IT_FwdEPS_Rev3M", "it_fwd_rev_3m_pct", True),
        ("A_ALFRED_CorpProfits_YoY", "cp_yoy", True),
        ("A_ALFRED_CoreCapex_NEWORDER_YoY", "no_yoy", True),
        ("A_RealRate_DFII10_Chg3M", "rr_chg_3m", True),
        ("B_ALFRED_CorePCE_YoY", "pce_yoy", True),
        ("B_Breakeven_10Y_Chg3M", "bei_chg_3m", True),
        ("C_BIS_Private_DSR_YoY", "bis_dsr_priv_yoy", True),
        ("C_BIS_Corp_DSR_YoY", "bis_dsr_corp_yoy", True),
        ("C_ALFRED_Household_TDSP_YoY", "tdsp_yoy", True),
    ]
    for name, col, sep_only in predictors:
        sub_df = panel[panel["sep_on"]] if sep_only else panel
        rec_c = {"Predictor": name, "N_Valid": int(sub_df[col].notna().sum())}
        for h in (1, 3, 6, 12):
            for target_lbl, target_col in [
                ("QQQ_Ret", f"qqq_ret_{h}m"),
                ("QQQ_Vol", f"qqq_vol_{h}m"),
                ("Theo_g3x", f"g3x_theo_ann_{h}m"),
                ("Live_TQQQ_Ret", f"tqqq_live_ret_{h}m"),
            ]:
                valid = sub_df[[col, target_col]].dropna()
                if len(valid) >= 20:
                    rho, pval = spearmanr(valid[col], valid[target_col])
                    rec_c[f"Rho_{target_lbl}_{h}M"] = float(rho)
                    rec_c[f"Pval_{target_lbl}_{h}M"] = float(pval)
                else:
                    rec_c[f"Rho_{target_lbl}_{h}M"] = np.nan
                    rec_c[f"Pval_{target_lbl}_{h}M"] = np.nan
        corr_rows.append(rec_c)

    df_corr = pd.DataFrame(corr_rows)
    df_corr.to_csv(os.path.join(OUT_DIR, "tqqq_econ_cycles_horizon_correlations.csv"), index=False)
    print("\n" + "=" * 105)
    print("SPEARMAN RANK CORRELATIONS ACROSS FORECAST HORIZONS (1M, 3M, 6M, 12M) UNDER SEP = ON")
    print("=" * 105)
    cols_corr_print = [
        "Predictor", "N_Valid",
        "Rho_QQQ_Ret_1M", "Rho_QQQ_Ret_3M", "Rho_QQQ_Ret_6M", "Rho_QQQ_Ret_12M",
        "Rho_QQQ_Vol_3M", "Rho_QQQ_Vol_6M", "Rho_QQQ_Vol_12M",
        "Rho_Theo_g3x_6M", "Rho_Live_TQQQ_Ret_6M"
    ]
    print(df_corr[cols_corr_print].to_string(index=False, float_format=lambda x: f"{x:+.3f}"))

    # =========================================================================
    # 3. Live TQQQ Era (2010-03..2026-10, 200 Real ETF Months) Frozen Execution Check
    # =========================================================================
    live_p = panel[panel["t"] >= pd.Timestamp("2010-02-28")].copy().reset_index(drop=True)
    # Add SPY open-to-open / close-to-close monthly return and SGOV/BIL return from reg_map_214
    spy_m_rets, cash_m_rets = [], []
    for t_dt in live_p["t"]:
        rm = reg_map_214[t_dt]
        cash_m_rets.append(float(rm["ret_sgov_actual"]))
        d0 = cal[cal.searchsorted(t_dt, side="right")]
        if t_dt == pd.Timestamp("2026-09-30"):
            d1 = pd.Timestamp("2026-10-29")
        else:
            t_next = t_dt + pd.offsets.MonthEnd(1)
            d1 = cal[cal.searchsorted(t_next, side="right")]
        spy_m_rets.append(float(spy_c.loc[:d1].iloc[-1] / spy_c.loc[:d0].iloc[-1] - 1.0))
    live_p["spy_ret_1m"] = spy_m_rets
    live_p["cash_ret_1m"] = cash_m_rets
    live_p["tqqq_ret_1m_dec"] = live_p["tqqq_live_ret_1m"] / 100.0
    live_p["qqq_ret_1m_dec"] = live_p["qqq_ret_1m"] / 100.0

    def eval_live_rule(name, weight_fn, sub_df):
        w_prev = None
        rets = []
        n_delev = 0
        for _, r in sub_df.iterrows():
            w_tq, w_qq, w_ca = weight_fn(r)
            if r["sep_on"] and w_tq < 0.99:
                n_delev += 1
            if w_prev is None:
                to = 0.0
            else:
                to = 0.5 * (abs(w_tq - w_prev[0]) + abs(w_qq - w_prev[1]) + abs(w_ca - w_prev[2]))
            w_prev = (w_tq, w_qq, w_ca)
            r_net = w_tq * r["tqqq_ret_1m_dec"] + w_qq * r["qqq_ret_1m_dec"] + w_ca * r["cash_ret_1m"] - to * 0.0020
            rets.append(r_net)
        arr = np.array(rets)
        n_m = len(arr)
        cagr = (np.prod(1.0 + arr) ** (12.0 / n_m) - 1.0) * 100.0
        vol = np.std(arr, ddof=1) * np.sqrt(12.0) * 100.0
        ex = arr - sub_df["cash_ret_1m"].values
        sr = (np.mean(ex) / np.std(ex, ddof=1)) * np.sqrt(12.0)
        eq = np.cumprod(1.0 + arr)
        mdd_m = (eq / np.maximum.accumulate(eq) - 1.0).min() * 100.0
        return {
            "Strategy": name, "N_Months": n_m, "Delev_Months_in_SEP_ON": n_delev,
            "CAGR_%": cagr, "Vol_Ann_%": vol, "Sharpe": sr, "Monthly_MaxDD_%": mdd_m
        }

    bt_rows = [
        eval_live_rule("0a_BuyHold_SPY (Live 2010-03..2026-10)", lambda r: (0.0, 0.0, 0.0), live_p),
        eval_live_rule("0b_BuyHold_QQQ (Live 2010-03..2026-10)", lambda r: (0.0, 1.0, 0.0), live_p),
        eval_live_rule("0c_BuyHold_TQQQ (Live 2010-03..2026-10)", lambda r: (1.0, 0.0, 0.0), live_p),
        eval_live_rule("1_Original_TQQQ_SEP (Frozen Baseline)", lambda r: (1.0, 0.0, 0.0) if r["sep_on"] else (0.0, 0.0, 1.0), live_p),
        eval_live_rule("2a_ExpA_ALFRED_Macro_Delev_Q3 (ProfitDown+RRDown -> QQQ)", lambda r: ((0.0, 1.0, 0.0) if ((not (r["cp_yoy"] > 0 and r["no_yoy"] > 0)) and r["rr_chg_3m"] <= 0) else (1.0, 0.0, 0.0)) if r["sep_on"] else (0.0, 0.0, 1.0), live_p),
        eval_live_rule("2b_ExpA_ALFRED_Macro_Delev_Q4 (ProfitDown+RRUp -> QQQ)", lambda r: ((0.0, 1.0, 0.0) if ((not (r["cp_yoy"] > 0 and r["no_yoy"] > 0)) and r["rr_chg_3m"] > 0) else (1.0, 0.0, 0.0)) if r["sep_on"] else (0.0, 0.0, 1.0), live_p),
        eval_live_rule("2c_ExpA_SEC_EDGAR_NDX_Delev_Q3 (BreadthDown+RRDown -> QQQ)", lambda r: ((0.0, 1.0, 0.0) if (pd.notna(r["ndx_breadth_chg_3m"]) and r["ndx_breadth_chg_3m"] < 0 and r["rr_chg_3m"] <= 0) else (1.0, 0.0, 0.0)) if r["sep_on"] else (0.0, 0.0, 1.0), live_p),
        eval_live_rule("2d_ExpA_Wayback_IT_FwdEPS_Delev_Q4 (FwdRev<0+RRUp -> QQQ)", lambda r: ((0.0, 1.0, 0.0) if (pd.notna(r["it_fwd_rev_3m_pct"]) and r["it_fwd_rev_3m_pct"] < 0 and r["rr_chg_3m"] > 0) else (1.0, 0.0, 0.0)) if r["sep_on"] else (0.0, 0.0, 1.0), live_p),
        eval_live_rule("3_ExpB_Inflation_Unanchored_Delev (PCE>2.5% or BEI Surge -> QQQ)", lambda r: ((0.0, 1.0, 0.0) if (r["pce_yoy"] > 2.5 or (r["bei_now"] > 2.3 and r["bei_chg_3m"] > 0.15)) else (1.0, 0.0, 0.0)) if r["sep_on"] else (0.0, 0.0, 1.0), live_p),
        eval_live_rule("4_ExpC_BIS_Private_DSR_Rising_Delev (DSR YoY>0 -> QQQ)", lambda r: ((0.0, 1.0, 0.0) if (pd.notna(r["bis_dsr_priv_yoy"]) and r["bis_dsr_priv_yoy"] > 0) else (1.0, 0.0, 0.0)) if r["sep_on"] else (0.0, 0.0, 1.0), live_p),
    ]
    # Fix SPY row using spy_ret_1m
    spy_arr = live_p["spy_ret_1m"].values
    spy_eq = np.cumprod(1.0 + spy_arr)
    spy_ex = spy_arr - live_p["cash_ret_1m"].values
    bt_rows[0] = {
        "Strategy": "0a_BuyHold_SPY (Live 2010-03..2026-10)", "N_Months": len(spy_arr), "Delev_Months_in_SEP_ON": 0,
        "CAGR_%": (spy_eq[-1] ** (12.0 / len(spy_arr)) - 1.0) * 100.0,
        "Vol_Ann_%": np.std(spy_arr, ddof=1) * np.sqrt(12.0) * 100.0,
        "Sharpe": (np.mean(spy_ex) / np.std(spy_ex, ddof=1)) * np.sqrt(12.0),
        "Monthly_MaxDD_%": (spy_eq / np.maximum.accumulate(spy_eq) - 1.0).min() * 100.0
    }
    df_bt = pd.DataFrame(bt_rows)
    df_bt.to_csv(os.path.join(OUT_DIR, "tqqq_econ_cycles_live2010_2026_backtest_check.csv"), index=False)
    print("\n" + "=" * 105)
    print("LIVE TQQQ ETF ERA (2010-03..2026-10, 200 MONTHS) FROZEN EXECUTION CHECK")
    print("=" * 105)
    print(df_bt.to_string(index=False, float_format=lambda x: f"{x:.2f}"))


if __name__ == "__main__":
    main()
