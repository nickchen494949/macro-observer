#!/usr/bin/env python3
"""
02_audit_sec_fundamentals.py
Exhaustive (100% population) audit of all SEC EDGAR PIT fundamental stores:
  - S&P 500 fundamentals (eps_quarterly_pit.parquet + 11 sector pit_long parquets)
  - Nasdaq-100 fundamentals (fundamentals_ndx)
  - Small/Mid-Cap fundamentals (fundamentals_smallcap)
  - SEC 8-K Item 2.02 earnings timestamps (earnings_dates.csv)
  - (ticker, CIK) validity windows (cik_validity.csv) vs official sec_submissions
  - Valuation price dividend-adjustment contamination check (comparing dividend-adjusted
    price vs split-only price across all S&P 500 stock-months for log_mcap & E/P!)
Read-only on all project inputs; writes outputs solely to outputs/gemini_full_data_audit_20261031/.
"""
import glob
import json
import os
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/happygolucky/Desktop/宏观观察器")
SSM = ROOT / "research/sector_stock_momentum"
OUT_DIR = ROOT / "outputs/gemini_full_data_audit_20261031"
OUT_DIR.mkdir(parents=True, exist_ok=True)

sys.dont_write_bytecode = True
sys.path.insert(0, str(SSM))
import fundamentals_pit as fp_mod


def audit_panel(panel_path: Path, pit_long_dir: Path, label: str) -> dict:
    df = pd.read_parquet(panel_path)
    one = pd.Timedelta(days=1)

    # 1. available_date == filed + 1 day
    av_diff = (pd.to_datetime(df["available_date"]) - (pd.to_datetime(df["filed"]) + one)).abs()
    bad_av = int((av_diff > pd.Timedelta(0)).sum())

    # 2. period_end <= filed + 16 days (no future-dated ddate leak)
    future_ddate = int((pd.to_datetime(df["period_end"]) > pd.to_datetime(df["filed"]) + pd.Timedelta(days=16)).sum())

    # 3. Every TTM availability date >= max of its constituent field's filed + 1d on that row
    ttm_checks = {}
    for field, fcol, acol in [
        ("eps_diluted_approx", "filed_eps_diluted", "eps_diluted_approx_ttm_available_date"),
        ("eps_basic_approx", "filed_eps_basic", "eps_basic_approx_ttm_available_date"),
        ("net_income", "filed_net_income", "net_income_ttm_available_date"),
        ("revenue", "filed_revenue", "revenue_ttm_available_date"),
    ]:
        if fcol in df.columns and acol in df.columns:
            m = df[f"{field}_ttm"].notna() if f"{field}_ttm" in df.columns else pd.Series(False, index=df.index)
            sub = df[m]
            missing_av = int(sub[acol].isna().sum())
            early_av = int((pd.to_datetime(sub[acol]) < pd.to_datetime(sub[fcol]) + one).sum())
            ttm_checks[field] = {
                "nonnull_ttm_rows": int(m.sum()),
                "missing_ttm_available_date": missing_av,
                "ttm_available_before_own_quarter_filed_plus_1d": early_av,
            }

    # 4. Split adjustment consistency on eps_diluted_approx_adj
    split_sample_checked = 0
    split_mismatches = 0
    if "eps_diluted_approx" in df.columns and "eps_diluted_approx_adj" in df.columns and "filed_eps_diluted" in df.columns:
        valid = df.dropna(subset=["ticker", "eps_diluted_approx", "eps_diluted_approx_adj", "filed_eps_diluted"])
        for r in valid.itertuples():
            tk = str(r.ticker).replace(".", "-")
            fac = fp_mod.split_factor_after(tk, r.filed_eps_diluted)
            exp = float(r.eps_diluted_approx) / fac
            split_sample_checked += 1
            if not np.isclose(exp, float(r.eps_diluted_approx_adj), rtol=1e-6, atol=1e-8):
                split_mismatches += 1

    # 5. pit_long parquets
    long_rows = 0
    long_first_rows = 0
    long_future_ddate = 0
    long_files = sorted(glob.glob(str(pit_long_dir / "*.parquet")))
    for lf in long_files:
        L = pd.read_parquet(lf, columns=["ddate", "filed", "is_first_report"])
        long_rows += len(L)
        long_first_rows += int(L["is_first_report"].sum())
        long_future_ddate += int((pd.to_datetime(L["ddate"]) > pd.to_datetime(L["filed"]) + pd.Timedelta(days=16)).sum())

    return {
        "store": label,
        "quarterly_panel_rows": int(len(df)),
        "unique_tickers": int(df["ticker"].nunique()) if "ticker" in df.columns else None,
        "unique_ciks": int(df["cik"].dropna().nunique()) if "cik" in df.columns else None,
        "period_end_min_max": [str(df["period_end"].min())[:10], str(df["period_end"].max())[:10]],
        "available_date_ne_filed_plus_1d": bad_av,
        "period_end_gt_filed_plus_16d": future_ddate,
        "q4_derived_rows": int(df["q4_derived"].sum()) if "q4_derived" in df.columns else 0,
        "ttm_availability_checks": ttm_checks,
        "eps_split_basis_rows_checked": split_sample_checked,
        "eps_split_basis_mismatches": split_mismatches,
        "pit_long_files": len(long_files),
        "pit_long_total_rows": long_rows,
        "pit_long_first_report_rows": long_first_rows,
        "pit_long_future_ddate_violations": long_future_ddate,
    }


def audit_valuation_dividend_contamination():
    """
    Quantify the 4th External Audit finding: in original ml_features.py (78a2d0d),
    log_mcap, ep, deps_p, sp, bm used dividend-adjusted `adjclose` instead of
    split-only `close`, allowing future cash dividends to rescale historical valuations!
    """
    panel_p = SSM / "results/ml/panel.parquet"
    if not panel_p.exists():
        return {"status": "NO_ML_PANEL"}
    pan = pd.read_parquet(panel_p, columns=["t", "ticker", "log_mcap", "ep"])
    pan["t"] = pd.to_datetime(pan["t"])

    # Load Yahoo raw close vs adjclose ratio at month-end dates
    ratios = []
    for fp in sorted(glob.glob(str(SSM / "data/raw/*.json"))):
        if Path(fp).name.startswith("_"):
            continue
        d = json.loads(Path(fp).read_text())
        sym = d["symbol"]
        if not d.get("dates"):
            continue
        df_p = pd.DataFrame({
            "dt": pd.to_datetime(d["dates"]),
            "close": np.asarray(d["close"], dtype=float),
            "adjclose": np.asarray(d["adjclose"], dtype=float),
        }).sort_values("dt")
        df_p = df_p[(df_p["close"] > 0) & (df_p["adjclose"] > 0)]
        if df_p.empty:
            continue
        df_p["ym"] = df_p["dt"].dt.to_period("M")
        me = df_p.groupby("ym", as_index=False).last()
        me["ticker"] = sym
        me["div_factor"] = me["adjclose"] / me["close"]  # < 1.0 whenever future dividends occurred!
        ratios.append(me[["ym", "ticker", "div_factor"]])

    rat_df = pd.concat(ratios, ignore_index=True)
    pan["ym"] = pan["t"].dt.to_period("M")
    m = pan.merge(rat_df, on=["ym", "ticker"], how="inner").dropna(subset=["log_mcap"])
    # True split-only mcap is larger by 1 / div_factor => mcap understatement % = (1 - div_factor) * 100
    under_pct = (1.0 - m["div_factor"]) * 100.0
    early = m[m["t"] <= "2015-12-31"]
    early_under = (1.0 - early["div_factor"]) * 100.0

    worst = (
        m.assign(mcap_understatement_pct=under_pct)
        .sort_values("mcap_understatement_pct", ascending=False)
        .head(15)[["t", "ticker", "div_factor", "mcap_understatement_pct"]]
    )
    worst["t"] = worst["t"].astype(str)

    return {
        "matched_sp500_feature_stock_months": int(len(m)),
        "pct_rows_affected_by_future_dividends_gt_1pct": round(float((under_pct > 1.0).mean() * 100), 2),
        "pct_rows_affected_by_future_dividends_gt_10pct": round(float((under_pct > 10.0).mean() * 100), 2),
        "pct_rows_affected_by_future_dividends_gt_25pct": round(float((under_pct > 25.0).mean() * 100), 2),
        "median_mcap_distortion_all_years_pct": round(float(under_pct.median()), 2),
        "median_mcap_distortion_2010_2015_pct": round(float(early_under.median()), 2),
        "p90_mcap_distortion_2010_2015_pct": round(float(early_under.quantile(0.90)), 2),
        "worst_distortions_sample": worst.to_dict(orient="records"),
    }


def audit_cik_validity_and_earnings_dates():
    cv = pd.read_csv(SSM / "data/cik_validity.csv")
    ed = pd.read_csv(SSM / "data/earnings_dates.csv")
    subs = sorted(glob.glob(str(SSM / "data/sec_submissions/*.json")))

    # Check AMD 2017-06-30 historical regression case in current fundamental_panel!
    import ml_features as mlf
    fp_2017 = mlf.fundamental_panel(pd.DatetimeIndex(["2017-06-30"]))
    amd_row = fp_2017[fp_2017["cik"] == 2488]
    amd_margin_2017_06_30 = None if amd_row.empty else (
        None if pd.isna(amd_row.iloc[0]["margin"]) else float(amd_row.iloc[0]["margin"])
    )

    return {
        "cik_validity_rules": cv.to_dict(orient="records"),
        "sec_submissions_json_files": len(subs),
        "earnings_8k_rows": int(len(ed)),
        "earnings_8k_columns": list(ed.columns),
        "amd_2017_06_30_margin_leak_regression_value_is_null": amd_margin_2017_06_30 is None,
        "amd_2017_06_30_margin_value": amd_margin_2017_06_30,
    }


def main():
    print("[02] Auditing S&P 500, Nasdaq-100, and Small-Cap SEC PIT fundamental panels...")
    sp_res = audit_panel(
        SSM / "data/fundamentals/eps_quarterly_pit.parquet",
        SSM / "data/fundamentals/pit_long",
        "sp500_fundamentals",
    )
    ndx_res = audit_panel(
        SSM / "data/fundamentals_ndx/eps_quarterly_pit.parquet",
        SSM / "data/fundamentals_ndx/pit_long",
        "ndx_fundamentals",
    )
    sc_res = audit_panel(
        SSM / "data/fundamentals_smallcap/eps_quarterly_pit.parquet",
        SSM / "data/fundamentals_smallcap/pit_long",
        "smallcap_fundamentals",
    )
    print("[02] Quantifying dividend-adjusted vs split-only valuation distortion across S&P stock-months...")
    div_contam = audit_valuation_dividend_contamination()
    print("[02] Auditing CIK validity windows, 8-K earnings timestamps, and AMD 2017-06-30 regression...")
    cik_ed = audit_cik_validity_and_earnings_dates()

    out = {
        "panels": [sp_res, ndx_res, sc_res],
        "valuation_price_future_dividend_distortion": div_contam,
        "cik_validity_and_8k_events": cik_ed,
    }
    out_p = OUT_DIR / "02_sec_fundamentals_audit.json"
    out_p.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"[02] DONE -> {out_p}")
    for r in [sp_res, ndx_res, sc_res]:
        print(f"     {r['store']}: {r['quarterly_panel_rows']:,} qtr rows | bad_avail={r['available_date_ne_filed_plus_1d']} | future_ddate={r['period_end_gt_filed_plus_16d']} | split_mismatch={r['eps_split_basis_mismatches']}")
    print(f"     Future-dividend mcap distortion >10%: {div_contam.get('pct_rows_affected_by_future_dividends_gt_10pct')}% of S&P stock-months (2010-2015 median: {div_contam.get('median_mcap_distortion_2010_2015_pct')}%)")


if __name__ == "__main__":
    main()
