#!/usr/bin/env python3
"""
Point-in-Time Audit: US Equity Valuation (PE / CAPE / NDX SEC PIT PE / Real ERP)
Combined with Leverage Ratio (FINRA Margin) & Liquidity/Cash Water Levels (BofA Cash, CFTC, WRESBAL)
====================================================================================================
Tests the user's hypothesis:
  "What if we combine leverage ratio, cash water levels, etc. with US equity P/E?"

Strict Point-in-Time (PIT) Rules Enforced:
1. Valuation Metrics (Zero Look-Ahead):
   - `NDX_SEC_PIT_PE`: Bottom-up Nasdaq-100 constituent Implied P/E (`1 / Median(E/P)`) computed strictly
     from SEC EDGAR 10-K/10-Q filings where `eps_diluted_approx_ttm_available_date <= t` (as-first-reported).
   - `SP500_PE_PIT`: S&P 500 price at month-end `t` divided by trailing 12M S&P 500 EPS lagged by 3 full
     months (`t - 3M`, ensuring 100% quarterly reporting completion), chained after 2025-09 via SEC EDGAR S&P 500 PIT EPS.
   - `CAPE_PIT`: S&P 500 price at month-end `t` scaled against Shiller 10Y real earnings denominator lagged by 3M.
   - `Real_ERP_SPX_PIT` & `Real_ERP_NDX_PIT`: Earnings Yield (`100 / PE_PIT`) minus 10Y Real Interest Rate (`DFII10`).
2. Leverage & Cash Water Level Metrics (Zero Look-Ahead):
   - `FINRA_Margin_YoY_PIT` & `Margin_Excess_YoY_PIT`: Strictly lagged by 1 full month (`t - 1M`) to match
     FINRA's mid-next-month release schedule. `Margin_Excess_YoY` = `Margin_YoY(t-1M) - SPX_YoY(t-1M)`.
   - `BofA_Cash_PIT` & `BofA_Cash_Z36`: Strictly using survey released mid-month `<= t`.
   - `CFTC_ES_AM_Z36_PIT`: Strictly active ONLY from `2013-07-31` onward (36M window after `2010-07-22` launch).
   - `WRESBAL_4W_YoY_PIT`: 4-week average of weekly Fed reserves released on or before `t` vs 52 weeks prior.
"""

import os
import json
import numpy as np
import pandas as pd
from scipy.stats import spearmanr, fisher_exact

import outputs.remediation_full_audit_20261104.run_full_8point_remediation_audit as r8
import independent_v4_symmetric_sharpe_top2_audit as v4_eng
import research.sector_stock_momentum.fundamentals_pit as fp
import outputs.pure_momentum_1985_2026_audit.build_portable_inputs_from_raw as bpi

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE_DIR, "outputs", "v4_symmetric_sharpe_top2_20261113")
os.makedirs(OUT_DIR, exist_ok=True)


def load_json_series(rel_path):
    with open(os.path.join(BASE_DIR, rel_path)) as f:
        d = json.load(f)
    return pd.Series({
        pd.Timestamp(r[0]): float(r[1])
        for r in d["values"]
        if r[1] not in (None, ".", "")
    }).sort_index()


def build_ndx_and_spx_sec_pit_pe(months_list):
    """
    Compute 100% Point-in-Time Nasdaq-100 & S&P 500 Constituent Implied P/E (`1 / Median(E/P)`)
    and Median Positive P/E from SEC EDGAR 10-K/10-Q filings (`avail_eps_ttm <= t`).
    """
    p1 = pd.read_parquet(os.path.join(BASE_DIR, "research", "sector_stock_momentum", "data", "fundamentals", "eps_quarterly_pit.parquet"))
    p2 = pd.read_parquet(os.path.join(BASE_DIR, "research", "sector_stock_momentum", "data", "fundamentals_ndx", "eps_quarterly_pit.parquet"))
    df = pd.concat([p1, p2], ignore_index=True).drop_duplicates(subset=["ticker", "period_end", "filed"])
    df["avail_eps_ttm"] = pd.to_datetime(df["eps_diluted_approx_ttm_available_date"])
    df["period_end"] = pd.to_datetime(df["period_end"])

    p_ndx = v4_eng.p_ndx
    p_spx = v4_eng.p_spx

    # Pre-cache daily close series per ticker
    px_cache = {}
    all_tks = set(p_ndx["ticker"].unique()) | set(p_spx["ticker"].unique())
    for tk in all_tks:
        for src, sym in bpi.candidate_series(tk):
            s_df = bpi.load_fixed(src, sym)
            if s_df is not None and len(s_df) > 0:
                px_cache[tk] = s_df["c"]
                break

    out = {}
    for t in months_list:
        t_dt = pd.Timestamp(t)
        ndx_tks = set(p_ndx[p_ndx["t"] == t_dt]["ticker"])
        spx_tks = set(p_spx[p_spx["t"] == t_dt]["ticker"])

        sub = df[(df["avail_eps_ttm"] <= t_dt) & df["eps_diluted_approx_ttm_adj"].notna()].sort_values(["ticker", "period_end", "avail_eps_ttm"])
        latest = sub.groupby("ticker").tail(1)
        latest = latest[(t_dt - latest["period_end"]).dt.days <= 200]

        ndx_ey, spx_ey = [], []
        for row in latest.itertuples(index=False):
            tk = row.ticker
            if not fp.cik_valid(tk, t_dt):
                continue
            s_c = px_cache.get(tk)
            if s_c is None:
                continue
            s_sub = s_c.loc[:t_dt]
            if len(s_sub) == 0 or (t_dt - s_sub.index[-1]).days > 10:
                continue
            px = float(s_sub.iloc[-1])
            if px <= 0:
                continue
            ey = float(row.eps_diluted_approx_ttm_adj) / px
            if tk in ndx_tks:
                ndx_ey.append(ey)
            if tk in spx_tks:
                spx_ey.append(ey)

        ndx_med_ey = float(np.median(ndx_ey)) if len(ndx_ey) >= 25 else np.nan
        spx_med_ey = float(np.median(spx_ey)) if len(spx_ey) >= 100 else np.nan
        out[t_dt] = {
            "ndx_pit_pe": (1.0 / ndx_med_ey) if (np.isfinite(ndx_med_ey) and ndx_med_ey > 0) else np.nan,
            "ndx_pit_ey_pct": (ndx_med_ey * 100.0) if np.isfinite(ndx_med_ey) else np.nan,
            "spx_pit_pe": (1.0 / spx_med_ey) if (np.isfinite(spx_med_ey) and spx_med_ey > 0) else np.nan,
            "spx_pit_ey_pct": (spx_med_ey * 100.0) if np.isfinite(spx_med_ey) else np.nan,
        }
    return pd.DataFrame.from_dict(out, orient="index").sort_index()


def main():
    # Load master panel from previous 3-lines audit (contains exact forward 1M/3M/6M/12M QQQ & Live TQQQ metrics)
    master = pd.read_csv(os.path.join(OUT_DIR, "tqqq_econ_cycles_master_panel.csv"), parse_dates=["t"])

    df_tqqq = r8.load_tiingo_etf_df("TQQQ")
    df_qqq_tiingo = r8.load_tiingo_etf_df("QQQ")
    yq_s = load_json_series("data/yahoo/QQQ.json")
    join_dt = df_qqq_tiingo.index.min()
    scale_q = float(df_qqq_tiingo.at[join_dt, "c"] / yq_s.at[join_dt])
    yq_pre = yq_s.loc[yq_s.index < join_dt] * scale_q
    df_qqq = pd.concat([pd.DataFrame({"c": yq_pre.values, "o": yq_pre.values}, index=yq_pre.index), df_qqq_tiingo[["c", "o"]]]).sort_index()
    df_qqq = df_qqq[~df_qqq.index.duplicated(keep="last")]
    df_sgov = r8.load_tiingo_etf_df("SGOV")
    df_bil = r8.load_tiingo_etf_df("BIL")
    gspc_s = load_json_series("data/yahoo/_GSPC.json")
    spy_s = load_json_series("data/yahoo/SPY.json")

    # Valuation series
    sp_pe_raw = load_json_series("data/valuation/SP500_PE.json")
    cape_raw = load_json_series("data/valuation/SHILLER_CAPE.json")
    finra_s = load_json_series("data/valuation/FINRA_MARGIN_DEBT.json")
    bofa_s = load_json_series("data/valuation/BOFA_FMS_CASH.json")
    cftc_es_s = load_json_series("data/valuation/CFTC_ES_AM_NET.json")
    cftc_nq_s = load_json_series("data/valuation/CFTC_NQ_LEV_NET.json")
    wres_s = load_json_series("data/fred/WRESBAL.json")
    rf_s = load_json_series("data/fred/DGS3MO.json") / 100.0

    # Implied trailing EPS denominator from SP500_PE.json and Shiller 10Y real EPS from SHILLER_CAPE.json
    # Lagged by 3 months (91 days) so only fully reported earnings as of t-3M are in the denominator!
    gspc_m = gspc_s.resample("MS").first().reindex(sp_pe_raw.index, method="ffill")
    sp_eps_denom = (gspc_m / sp_pe_raw).dropna()
    gspc_cape_m = gspc_s.reindex(cape_raw.index, method="ffill")
    cape_eps10_denom = (gspc_cape_m / cape_raw).dropna()

    # Build SEC EDGAR PIT P/E for NDX and SPX (2009-2026)
    sec_pe_df = build_ndx_and_spx_sec_pit_pe([t for t in master["t"] if t >= pd.Timestamp("2008-12-31")])

    # Augment master panel with strictly PIT Valuation & Leverage/Liquidity metrics
    val_rows = []
    for _, r in master.iterrows():
        t = pd.Timestamp(r["t"])
        gspc_now = float(gspc_s.loc[:t].iloc[-1])
        gspc_1y = float(gspc_s.loc[:t - pd.Timedelta(days=365)].iloc[-1])
        spx_yoy = (gspc_now / gspc_1y - 1.0) * 100.0

        # 1. CAPE_PIT (Price(t) / Shiller_10Y_EPS(t - 91d))
        denom_cape_sub = cape_eps10_denom.loc[:t - pd.Timedelta(days=91)]
        cape_pit = float(gspc_now / denom_cape_sub.iloc[-1]) if len(denom_cape_sub) else np.nan

        # 2. SP500_PE_PIT (Price(t) / S&P_Trailing_EPS(t - 91d), chained post 2025-09 via SPX SEC PIT EY)
        denom_pe_sub = sp_eps_denom.loc[:t - pd.Timedelta(days=91)]
        if len(denom_pe_sub) > 0 and (t - denom_pe_sub.index[-1]).days <= 150:
            sp_pe_pit = float(gspc_now / denom_pe_sub.iloc[-1])
        elif t in sec_pe_df.index and pd.notna(sec_pe_df.loc[t, "spx_pit_pe"]):
            # Chain from 2025-09-30 using SPX SEC EDGAR PIT P/E ratio
            t_ref = pd.Timestamp("2025-09-30")
            pe_ref = float(gspc_s.loc[:t_ref].iloc[-1] / sp_eps_denom.loc[:t_ref - pd.Timedelta(days=91)].iloc[-1])
            sp_pe_pit = pe_ref * float(sec_pe_df.loc[t, "spx_pit_pe"] / sec_pe_df.loc[t_ref, "spx_pit_pe"])
        else:
            sp_pe_pit = np.nan

        # 3. NDX SEC EDGAR PIT P/E (2010-06..2026-10)
        ndx_pe_pit = float(sec_pe_df.loc[t, "ndx_pit_pe"]) if (t in sec_pe_df.index) else np.nan
        spx_sec_pe_pit = float(sec_pe_df.loc[t, "spx_pit_pe"]) if (t in sec_pe_df.index) else np.nan

        # 4. Real Equity Risk Premium (Real ERP = Earnings Yield - 10Y Real Rate rr_now)
        rr_now = float(r["rr_now"])
        erp_spx_pit = (100.0 / sp_pe_pit) - rr_now if (np.isfinite(sp_pe_pit) and sp_pe_pit > 0) else np.nan
        erp_cape_pit = (100.0 / cape_pit) - rr_now if (np.isfinite(cape_pit) and cape_pit > 0) else np.nan
        erp_ndx_pit = (100.0 / ndx_pe_pit) - rr_now if (np.isfinite(ndx_pe_pit) and ndx_pe_pit > 0) else np.nan

        # 5. FINRA Margin Debt (Strictly lagged by 1 month: at month-end t, use t - 25 days or earlier)
        t_finra_cutoff = t - pd.Timedelta(days=25)
        f_sub = finra_s.loc[:t_finra_cutoff]
        if len(f_sub) >= 13:
            finra_yoy = (float(f_sub.iloc[-1]) / float(f_sub.iloc[-13]) - 1.0) * 100.0
            # SPX YoY matched to FINRA date
            dt_f = f_sub.index[-1]
            dt_f_1y = f_sub.index[-13]
            spx_f_yoy = (float(gspc_s.loc[:dt_f].iloc[-1]) / float(gspc_s.loc[:dt_f_1y].iloc[-1]) - 1.0) * 100.0
            finra_excess_yoy = finra_yoy - spx_f_yoy
            # Rolling 36M Z-score of Margin / SPX ratio
            if len(f_sub) >= 36:
                f_36 = f_sub.tail(36)
                g_36 = gspc_s.reindex(f_36.index, method="ffill")
                ratio_36 = f_36 / g_36
                finra_spx_z36 = float((ratio_36.iloc[-1] - ratio_36.mean()) / ratio_36.std(ddof=1))
            else:
                finra_spx_z36 = np.nan
        else:
            finra_yoy, finra_excess_yoy, finra_spx_z36 = np.nan, np.nan, np.nan

        # 6. BofA FMS Cash Level (Strictly released <= t)
        b_sub = bofa_s.loc[:t]
        if len(b_sub) >= 1 and (t - b_sub.index[-1]).days <= 45:
            bofa_cash = float(b_sub.iloc[-1])
            b_win = b_sub.loc[b_sub.index >= t - pd.Timedelta(days=365 * 3)]
            bofa_cash_z36 = float((bofa_cash - b_win.mean()) / b_win.std(ddof=1)) if len(b_win) >= 12 else np.nan
        else:
            bofa_cash, bofa_cash_z36 = np.nan, np.nan

        # 7. CFTC Asset Manager ES Positioning (Strictly post 2010-07-22 launch, 36M rolling -> active >= 2013-07-31)
        if t >= pd.Timestamp("2013-07-31"):
            c_sub = cftc_es_s.loc[(cftc_es_s.index >= "2010-07-22") & (cftc_es_s.index <= t)]
            if len(c_sub) >= 30:
                c_win = c_sub.loc[c_sub.index >= t - pd.Timedelta(days=365 * 3)]
                cftc_es_z36 = float((c_sub.iloc[-1] - c_win.mean()) / c_win.std(ddof=1))
            else:
                cftc_es_z36 = np.nan
        else:
            cftc_es_z36 = np.nan

        # 8. Bank Reserves WRESBAL 4-Week Smoothed YoY (Strictly released <= t)
        w_sub = wres_s.loc[:t]
        if len(w_sub) >= 56:
            w_4w_now = float(w_sub.iloc[-4:].mean())
            w_4w_1y = float(w_sub.iloc[-56:-52].mean())
            wres_4w_yoy = (w_4w_now / w_4w_1y - 1.0) * 100.0
        else:
            wres_4w_yoy = np.nan

        val_rows.append({
            "t": t,
            "cape_pit": cape_pit,
            "sp_pe_pit": sp_pe_pit,
            "ndx_pe_pit": ndx_pe_pit,
            "spx_sec_pe_pit": spx_sec_pe_pit,
            "erp_spx_pit": erp_spx_pit,
            "erp_cape_pit": erp_cape_pit,
            "erp_ndx_pit": erp_ndx_pit,
            "finra_yoy": finra_yoy,
            "finra_excess_yoy": finra_excess_yoy,
            "finra_spx_z36": finra_spx_z36,
            "bofa_cash": bofa_cash,
            "bofa_cash_z36": bofa_cash_z36,
            "cftc_es_z36": cftc_es_z36,
            "wres_4w_yoy": wres_4w_yoy,
        })

    df_val = pd.DataFrame(val_rows)
    panel = master.merge(df_val, on="t", how="left")

    # Compute rolling 36M Z-scores / percentiles of Valuation to avoid fixed-threshold look-ahead across eras
    panel["cape_z36"] = (panel["cape_pit"] - panel["cape_pit"].rolling(36, min_periods=24).mean()) / panel["cape_pit"].rolling(36, min_periods=24).std(ddof=1)
    panel["sp_pe_z36"] = (panel["sp_pe_pit"] - panel["sp_pe_pit"].rolling(36, min_periods=24).mean()) / panel["sp_pe_pit"].rolling(36, min_periods=24).std(ddof=1)
    panel["ndx_pe_z36"] = (panel["ndx_pe_pit"] - panel["ndx_pe_pit"].rolling(36, min_periods=24).mean()) / panel["ndx_pe_pit"].rolling(36, min_periods=24).std(ddof=1)

    panel.to_csv(os.path.join(OUT_DIR, "tqqq_pe_leverage_liquidity_panel.csv"), index=False)

    # =========================================================================
    # PART 1: Standalone Spearman Correlations of Valuation & Leverage (SEP=ON)
    # =========================================================================
    sep = panel[panel["sep_on"]].copy()
    corr_vars = [
        ("Val_1_Shiller_CAPE_PIT", "cape_pit"),
        ("Val_2_SP500_Trailing_PE_PIT", "sp_pe_pit"),
        ("Val_3_NDX_SEC_EDGAR_PIT_PE (2011+)", "ndx_pe_pit"),
        ("Val_4_Real_ERP_SPX (EY - DFII10)", "erp_spx_pit"),
        ("Val_5_Real_ERP_NDX (EY - DFII10, 2011+)", "erp_ndx_pit"),
        ("Lev_1_FINRA_Margin_YoY_PIT (Lag 1M)", "finra_yoy"),
        ("Lev_2_FINRA_Margin_Excess_Over_SPX_YoY", "finra_excess_yoy"),
        ("Lev_3_FINRA_Margin_to_SPX_Z36", "finra_spx_z36"),
        ("Liq_1_BofA_FMS_Cash_Level_%", "bofa_cash"),
        ("Liq_2_CFTC_ES_AssetMgr_Z36 (2013-07+)", "cftc_es_z36"),
        ("Liq_3_WRESBAL_4W_Avg_YoY_%", "wres_4w_yoy"),
    ]

    c_rows = []
    for name, col in corr_vars:
        for era_lbl, sub in [
            ("Full_1999_2026", sep),
            ("Era1_1999_2009", sep[sep["t"] < "2010-01-01"]),
            ("Era2_2010_2026", sep[sep["t"] >= "2010-01-01"]),
        ]:
            v1 = sub[[col, "qqq_ret_1m"]].dropna()
            v3 = sub[[col, "qqq_ret_3m", "qqq_vol_3m", "g3x_theo_ann_3m"]].dropna()
            v6 = sub[[col, "qqq_ret_6m", "qqq_vol_6m", "g3x_theo_ann_6m"]].dropna()
            v12 = sub[[col, "qqq_ret_12m", "qqq_vol_12m"]].dropna()
            if len(v6) >= 20:
                r1, p1 = spearmanr(v1[col], v1["qqq_ret_1m"])
                r3, p3 = spearmanr(v3[col], v3["qqq_ret_3m"])
                r6, p6 = spearmanr(v6[col], v6["qqq_ret_6m"])
                r12, p12 = spearmanr(v12[col], v12["qqq_ret_12m"])
                rv6, pv6 = spearmanr(v6[col], v6["qqq_vol_6m"])
                rg6, pg6 = spearmanr(v6[col], v6["g3x_theo_ann_6m"])
                c_rows.append({
                    "Variable": name, "Era": era_lbl, "N": len(v6),
                    "Rho_Ret1M": r1, "Rho_Ret3M": r3, "Rho_Ret6M": r6, "Rho_Ret12M": r12,
                    "P_Ret6M": p6, "P_Ret12M": p12,
                    "Rho_Vol6M": rv6, "Rho_g3x6M": rg6, "P_g3x6M": pg6
                })

    df_c = pd.DataFrame(c_rows)
    df_c.to_csv(os.path.join(OUT_DIR, "tqqq_pe_leverage_correlations_by_era.csv"), index=False)
    print("=" * 110)
    print("PART 1: SPEARMAN CORRELATIONS OF VALUATION (PE / ERP) & LEVERAGE / WATER LEVELS ACROSS ERAS (SEP = ON)")
    print("=" * 110)
    print(df_c.to_string(index=False, float_format=lambda x: f"{x:+.3f}"))

    # =========================================================================
    # PART 2: 4-Quadrant Combinations: Valuation (PE / Real ERP) × Leverage / Water Level (SEP=ON)
    # =========================================================================
    def eval_quadrants(df_in, val_high_mask, lev_high_mask, combo_name):
        sub = df_in[val_high_mask.notna() & lev_high_mask.notna()].copy()
        v_h = val_high_mask.loc[sub.index].astype(bool)
        l_h = lev_high_mask.loc[sub.index].astype(bool)

        q_labels = []
        for vh, lh in zip(v_h, l_h):
            if (not vh) and (not lh):
                q_labels.append("Q1_ValNormal_LevBenign")
            elif (not vh) and lh:
                q_labels.append("Q2_ValNormal_LevStretched")
            elif vh and (not lh):
                q_labels.append("Q3_ValExpensive_LevBenign")
            else:
                q_labels.append("Q4_ValExpensive_LevStretched (HighRisk)")
        sub["Quad"] = q_labels

        q_rows = []
        for q_name, g in sub.groupby("Quad", sort=True):
            vtq_1m = g["tqqq_live_ret_1m"].dropna()
            vtq_3m = g["tqqq_live_ret_3m"].dropna()
            gtq_3m = g["g_tqqq_live_ann_3m"].dropna()
            q_rows.append({
                "Combo": combo_name,
                "Quadrant": q_name,
                "N_Months": len(g),
                "QQQ_1M_%": float(g["qqq_ret_1m"].dropna().mean()),
                "QQQ_3M_%": float(g["qqq_ret_3m"].dropna().mean()),
                "QQQ_6M_%": float(g["qqq_ret_6m"].dropna().mean()),
                "QQQ_Vol3M_%": float(g["qqq_vol_3m"].dropna().mean()),
                "Theo_g3x_3M_%": float(g["g3x_theo_ann_3m"].dropna().mean()),
                "QQQ_Crash1M_lt_m7_%": float((g["qqq_ret_1m"].dropna() < -7.0).mean() * 100.0),
                "TQQQ_Live_N": len(vtq_1m),
                "TQQQ_Live_1M_%": float(vtq_1m.mean()) if len(vtq_1m) else np.nan,
                "TQQQ_Live_3M_%": float(vtq_3m.mean()) if len(vtq_3m) else np.nan,
                "TQQQ_Live_GeoAnn3M_%": float((np.exp(gtq_3m.mean() / 100.0) - 1.0) * 100.0) if len(gtq_3m) else np.nan,
                "TQQQ_Crash1M_lt_m20_%": float((vtq_1m < -20.0).mean() * 100.0) if len(vtq_1m) else np.nan,
            })
        return pd.DataFrame(q_rows)

    # Test 6 clean, economically distinct combinations of Valuation × Leverage/Water Level:
    combos = [
        # Combo 1: Shiller CAPE High (> 28 or Z36 > 0.5) × FINRA Margin Excess Growth (> 0: Margin growing faster than SPX)
        ("1_CAPE(>28)_x_FINRA_MarginExcess(YoY>SPX)",
         sep["cape_pit"] > 28.0,
         sep["finra_excess_yoy"] > 0.0),

        # Combo 2: SP500 Trailing PE_PIT High (> 22) × FINRA Margin-to-SPX Z36 (> +0.5)
        ("2_SP500_PE(>22)_x_FINRA_SPX_Z36(>+0.5)",
         sep["sp_pe_pit"] > 22.0,
         sep["finra_spx_z36"] > 0.5),

        # Combo 3: Low Real ERP (SPX EY - DFII10 < 2.5%) × FINRA Margin Excess Growth (> 0)
        ("3_Low_Real_ERP(<2.5%)_x_FINRA_MarginExcess(>0)",
         sep["erp_spx_pit"] < 2.5,
         sep["finra_excess_yoy"] > 0.0),

        # Combo 4: NDX SEC EDGAR PIT P/E High (> 28x, 2011+) × FINRA Margin Excess Growth (> 0)
        ("4_NDX_SEC_PIT_PE(>28x)_x_FINRA_MarginExcess(>0)",
         sep["ndx_pe_pit"] > 28.0,
         sep["finra_excess_yoy"] > 0.0),

        # Combo 5: NDX SEC EDGAR PIT P/E High (> 28x, 2011+) × Low BofA FMS Cash Water Level (Z36 < -0.5)
        ("5_NDX_SEC_PIT_PE(>28x)_x_BofA_LowCash(Z36<-0.5)",
         sep["ndx_pe_pit"] > 28.0,
         sep["bofa_cash_z36"] < -0.5),

        # Combo 6: NDX SEC EDGAR PIT P/E High (> 28x, 2011+) × Bank Reserves Draining (WRESBAL 4W YoY < 0)
        ("6_NDX_SEC_PIT_PE(>28x)_x_WRESBAL_Drain(4W_YoY<0)",
         sep["ndx_pe_pit"] > 28.0,
         sep["wres_4w_yoy"] < 0.0),

        # Combo 7: NDX Real ERP Compressed (< 2.5%, 2011+) × Composite Leverage/Water Stretch (MarginExcess>0 & (CashZ<-0.5 or WRES<0))
        ("7_NDX_LowRealERP(<2.5%)_x_Lev_and_Water_Stretch",
         sep["erp_ndx_pit"] < 2.5,
         (sep["finra_excess_yoy"] > 0.0) & ((sep["bofa_cash_z36"] < -0.5) | (sep["wres_4w_yoy"] < 0.0))),
    ]

    q_dfs = []
    for c_name, v_m, l_m in combos:
        q_dfs.append(eval_quadrants(sep, v_m, l_m, c_name))
    df_quads = pd.concat(q_dfs, ignore_index=True)
    df_quads.to_csv(os.path.join(OUT_DIR, "tqqq_pe_leverage_4quadrants_summary.csv"), index=False)

    print("\n" + "=" * 110)
    print("PART 2: FOUR-QUADRANT INTERACTION: VALUATION (PE / REAL ERP) × LEVERAGE & WATER LEVEL (SEP = ON)")
    print("=" * 110)
    cols_q_print = [
        "Combo", "Quadrant", "N_Months",
        "QQQ_1M_%", "QQQ_3M_%", "QQQ_Vol3M_%", "Theo_g3x_3M_%",
        "TQQQ_Live_N", "TQQQ_Live_1M_%", "TQQQ_Live_GeoAnn3M_%", "TQQQ_Crash1M_lt_m20_%"
    ]
    print(df_quads[cols_q_print].to_string(index=False, float_format=lambda x: f"{x:.2f}"))

    # =========================================================================
    # PART 3: Live TQQQ Era (2010-03..2026-10, 200 Months) Backtest & Leave-Out Check
    # =========================================================================
    cal = df_qqq.index.sort_values()
    reg_map_214 = v4_eng.reg_map
    live_p = panel[panel["t"] >= pd.Timestamp("2010-02-28")].copy().reset_index(drop=True)

    cash_m_rets = [float(reg_map_214[t_dt]["ret_sgov_actual"]) for t_dt in live_p["t"]]
    live_p["cash_ret_1m"] = cash_m_rets
    live_p["tqqq_ret_1m_dec"] = live_p["tqqq_live_ret_1m"] / 100.0
    live_p["qqq_ret_1m_dec"] = live_p["qqq_ret_1m"] / 100.0

    def sim_live_strategy(name, q4_cond_fn, delev_mode="QQQ"):
        w_prev = None
        rets = []
        q4_months = []
        for _, r in live_p.iterrows():
            is_q4 = bool(q4_cond_fn(r)) if r["sep_on"] else False
            if not r["sep_on"]:
                w_tq, w_qq, w_ca = 0.0, 0.0, 1.0
            elif is_q4:
                q4_months.append(r["hold_ym"])
                if delev_mode == "QQQ":
                    w_tq, w_qq, w_ca = 0.0, 1.0, 0.0
                elif delev_mode == "HALF":
                    w_tq, w_qq, w_ca = 0.5, 0.5, 0.0
                else:
                    w_tq, w_qq, w_ca = 0.0, 0.0, 1.0
            else:
                w_tq, w_qq, w_ca = 1.0, 0.0, 0.0

            to = 0.0 if w_prev is None else 0.5 * (abs(w_tq - w_prev[0]) + abs(w_qq - w_prev[1]) + abs(w_ca - w_prev[2]))
            w_prev = (w_tq, w_qq, w_ca)
            r_net = w_tq * r["tqqq_ret_1m_dec"] + w_qq * r["qqq_ret_1m_dec"] + w_ca * r["cash_ret_1m"] - to * 0.0020
            rets.append(r_net)

        arr = np.array(rets)
        n_m = len(arr)
        cagr = (np.prod(1.0 + arr) ** (12.0 / n_m) - 1.0) * 100.0
        vol = np.std(arr, ddof=1) * np.sqrt(12.0) * 100.0
        ex = arr - live_p["cash_ret_1m"].values
        sr = (np.mean(ex) / np.std(ex, ddof=1)) * np.sqrt(12.0)
        eq = np.cumprod(1.0 + arr)
        mdd = (eq / np.maximum.accumulate(eq) - 1.0).min() * 100.0

        # Ex-2020-02/03 & Ex-2018-12 CAGR check
        mask_ex = ~live_p["hold_ym"].isin(["2018-12", "2020-02", "2020-03"]).values
        arr_ex = arr[mask_ex]
        cagr_ex = (np.prod(1.0 + arr_ex) ** (12.0 / len(arr_ex)) - 1.0) * 100.0

        return {
            "Strategy": name,
            "Delev_Mode": delev_mode,
            "N_Q4_Months": len(q4_months),
            "CAGR_Full_%": cagr,
            "Sharpe_Full": sr,
            "Monthly_MaxDD_%": mdd,
            "CAGR_Ex18_20_%": cagr_ex,
            "Sample_Q4_Months": ",".join(q4_months[:8]) + ("..." if len(q4_months) > 8 else "")
        }

    bt_list = [
        sim_live_strategy("0_Original_TQQQ_SEP (Baseline)", lambda r: False, "QQQ"),
        sim_live_strategy("1_CAPE(>28)_and_FINRA_MarginExcess(>0)", lambda r: (pd.notna(r["cape_pit"]) and r["cape_pit"] > 28.0) and (pd.notna(r["finra_excess_yoy"]) and r["finra_excess_yoy"] > 0.0), "QQQ"),
        sim_live_strategy("2_SP500_PE(>22)_and_FINRA_SPX_Z36(>+0.5)", lambda r: (pd.notna(r["sp_pe_pit"]) and r["sp_pe_pit"] > 22.0) and (pd.notna(r["finra_spx_z36"]) and r["finra_spx_z36"] > 0.5), "QQQ"),
        sim_live_strategy("3_Low_Real_ERP(<2.5%)_and_FINRA_MarginExcess(>0)", lambda r: (pd.notna(r["erp_spx_pit"]) and r["erp_spx_pit"] < 2.5) and (pd.notna(r["finra_excess_yoy"]) and r["finra_excess_yoy"] > 0.0), "QQQ"),
        sim_live_strategy("4_NDX_SEC_PIT_PE(>28x)_and_FINRA_MarginExcess(>0)", lambda r: (pd.notna(r["ndx_pe_pit"]) and r["ndx_pe_pit"] > 28.0) and (pd.notna(r["finra_excess_yoy"]) and r["finra_excess_yoy"] > 0.0), "QQQ"),
        sim_live_strategy("5_NDX_SEC_PIT_PE(>28x)_and_BofA_LowCash(Z36<-0.5)", lambda r: (pd.notna(r["ndx_pe_pit"]) and r["ndx_pe_pit"] > 28.0) and (pd.notna(r["bofa_cash_z36"]) and r["bofa_cash_z36"] < -0.5), "QQQ"),
        sim_live_strategy("6_NDX_SEC_PIT_PE(>28x)_and_WRESBAL_Drain(<0)", lambda r: (pd.notna(r["ndx_pe_pit"]) and r["ndx_pe_pit"] > 28.0) and (pd.notna(r["wres_4w_yoy"]) and r["wres_4w_yoy"] < 0.0), "QQQ"),
        sim_live_strategy("7_NDX_LowRealERP(<2.5%)_and_Lev_Water_Stretch", lambda r: (pd.notna(r["erp_ndx_pit"]) and r["erp_ndx_pit"] < 2.5) and (pd.notna(r["finra_excess_yoy"]) and r["finra_excess_yoy"] > 0.0) and ((pd.notna(r["bofa_cash_z36"]) and r["bofa_cash_z36"] < -0.5) or (pd.notna(r["wres_4w_yoy"]) and r["wres_4w_yoy"] < 0.0)), "QQQ"),
    ]
    df_bt_pe = pd.DataFrame(bt_list)
    df_bt_pe.to_csv(os.path.join(OUT_DIR, "tqqq_pe_leverage_live2010_2026_backtest.csv"), index=False)

    print("\n" + "=" * 110)
    print("PART 3: LIVE TQQQ ERA (2010-03..2026-10, 200 MONTHS) BACKTEST & EX-CRISIS ABLATION CHECK")
    print("=" * 110)
    print(df_bt_pe.to_string(index=False, float_format=lambda x: f"{x:.2f}"))


if __name__ == "__main__":
    main()
