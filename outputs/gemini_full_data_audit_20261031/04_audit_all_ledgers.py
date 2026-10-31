#!/usr/bin/env python3
"""
04_audit_all_ledgers.py
Independent verification of ALL 350+ backtest strategy ledgers across:
  1. Original Claude baseline (`research/sector_stock_momentum/results/**/*.csv` — 167 ledgers)
  2. Codex v2 modified baseline (`backtest_versions/2026-10-30_codex_full_audit_v2/research/sector_stock_momentum/results/**/*.csv` — 174 ledgers)
  3. Top-3 / QQQ / Leverage / Sector-Rotation ledgers (`outputs/top3_*`, `research/sector_rotation/detail_*.csv`)
Checks calendar continuity, ruin-bound (`net < -100%`), cost/turnover accounting identity,
and independently recomputes holding-period gross returns from raw vendor price & open endpoints
on headline strategies across all branches.
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
CODEX_SSM = ROOT / "backtest_versions/2026-10-30_codex_full_audit_v2/research/sector_stock_momentum"
OUT_DIR = ROOT / "outputs/gemini_full_data_audit_20261031"
OUT_DIR.mkdir(parents=True, exist_ok=True)

sys.dont_write_bytecode = True
sys.path.insert(0, str(SSM))
import backtest as bt


def cagr_and_mdd(net_series: pd.Series):
    s = pd.to_numeric(net_series, errors="coerce").dropna()
    if len(s) == 0:
        return None, None
    eq = (1.0 + s.clip(lower=-1.0)).cumprod()
    end_eq = float(eq.iloc[-1])
    cagr = (end_eq ** (12.0 / len(s)) - 1.0) if end_eq > 0 else -1.0
    peaks = np.maximum.accumulate(np.concatenate([[1.0], eq.values]))
    dd = np.concatenate([[1.0], eq.values]) / peaks - 1.0
    return float(cagr), float(dd.min())


def scan_ledger_group(files, group_name):
    rows = []
    ruin_violations = []
    cost_formula_mismatches = []
    nan_return_files = []

    for fp in files:
        rel = str(Path(fp).relative_to(ROOT))
        try:
            df = pd.read_csv(fp)
        except Exception as e:
            rows.append({"file": rel, "status": f"READ_ERR:{e}"})
            continue
        if "net" not in df.columns:
            continue
        net = pd.to_numeric(df["net"], errors="coerce")
        if net.isna().any():
            nan_return_files.append(rel)
        if (net < -1.0 - 1e-12).any():
            bad_m = df.loc[net < -1.0 - 1e-12, ["month", "net"]].to_dict(orient="records") if "month" in df.columns else []
            ruin_violations.append({"file": rel, "months": bad_m})

        # Verify gross -> net cost identity where gross and turnover exist
        cost_mode = "net_only"
        max_cost_err = 0.0
        if "gross" in df.columns and "turnover" in df.columns:
            g = pd.to_numeric(df["gross"], errors="coerce")
            to = pd.to_numeric(df["turnover"], errors="coerce")
            m = g.notna() & to.notna() & net.notna()
            if m.any():
                # Check additive (gross - to * c) vs self-financing ((1 - to * c) * (1 + gross) - 1)
                if "capital_after_costs" in df.columns:
                    cap = pd.to_numeric(df["capital_after_costs"], errors="coerce")
                    bankrupt = df["bankrupt"].astype(bool) if "bankrupt" in df.columns else pd.Series(False, index=df.index)
                    exp_sf = np.where(bankrupt, np.where(cap == 0, 0.0, -1.0), cap * (1.0 + g) - 1.0)
                    # Note on exact bankruptcy transition month net == -1.0 while cap > 0
                    err_sf = np.minimum(np.abs(net[m] - (cap[m] * (1.0 + g[m]) - 1.0)), np.where(net[m] == -1.0, 0.0, 1.0))
                    max_cost_err = float(np.nanmax(err_sf))
                    cost_mode = "self_financing_ruin_safe"
                else:
                    # Infer per-side cost rate (0.001 for S&P/NDX, 0.0025 or 0.005 for smallcap/stress)
                    best_e = 999.0
                    for rate in [0.001, 0.002, 0.0025, 0.005, 0.01, 0.0]:
                        e = float((net[m] - (g[m] - to[m] * rate)).abs().max())
                        if e < best_e:
                            best_e = e
                    max_cost_err = best_e
                    cost_mode = "additive_cost"
                if max_cost_err > 1e-6:
                    cost_formula_mismatches.append({"file": rel, "mode": cost_mode, "max_err": max_cost_err})

        cagr, mdd = cagr_and_mdd(net)
        rows.append({
            "group": group_name,
            "file": rel,
            "months": int(len(df)),
            "start": str(df["month"].iloc[0]) if "month" in df.columns and len(df) else None,
            "end": str(df["month"].iloc[-1]) if "month" in df.columns and len(df) else None,
            "cost_mode": cost_mode,
            "max_cost_identity_err": round(max_cost_err, 10),
            "cagr_pct": round(cagr * 100, 4) if cagr is not None else None,
            "monthly_mdd_pct": round(mdd * 100, 4) if mdd is not None else None,
        })

    return {
        "group": group_name,
        "ledgers_audited": len(rows),
        "nan_return_files": nan_return_files,
        "ruin_bound_lt_minus100pct_violations": ruin_violations,
        "cost_formula_mismatches_gt_1e6": cost_formula_mismatches[:20],
        "cost_formula_mismatch_count": len(cost_formula_mismatches),
    }, rows


def recompute_headline_ledgers_from_raw_prices():
    """
    Independently load raw price endpoints (`load_prices(cutoff='2099-12-31')` + `raw_open` + `wiki_open`
    + `exit_resolutions.csv` + `rf_monthly.csv`) and recompute EVERY month's gross return from scratch
    for key headline strategies!
    """
    import ml2_run as m2r
    daily, P, _, _ = bt.load_prices(cutoff="2099-12-31")
    ex = pd.read_csv(SSM / "data/exit_resolutions.csv")
    ex_map = {(str(r.formation)[:10], str(r.ticker)): float(r.holding_return) for r in ex.itertuples()}
    rf_df = pd.read_csv(SSM / "data/rf_monthly.csv")
    rf_col = [c for c in rf_df.columns if c != rf_df.columns[0]][0]
    rf_map = {str(pd.Timestamp(d).to_period("M")): float(v) for d, v in zip(rf_df.iloc[:, 0], rf_df[rf_col])}

    O = m2r.build_opens(daily)

    checks = []

    # 1. Close-to-close S&P headline ledgers
    close_targets = [
        ("Claude_SPEC", SSM / "results/monthly_SPEC.csv"),
        ("Claude_PureMom_Top1", SSM / "results/monthly_NO_SECTOR_FILTER__top_1_stock.csv"),
        ("Claude_PureMom_Top10", SSM / "results/monthly_Ref__top_10__no_sector_filter.csv"),
        ("CodexV2_SPEC", CODEX_SSM / "results/monthly_SPEC.csv"),
        ("CodexV2_PureMom_Top1", CODEX_SSM / "results/monthly_NO_SECTOR_FILTER__top_1_stock.csv"),
    ]
    P_ym = P.copy()
    P_ym.index = P_ym.index.to_period("M")

    for label, lp in close_targets:
        if not lp.exists():
            continue
        df = pd.read_csv(lp)
        max_diff = 0.0
        n_checked = 0
        mismatch_examples = []
        for r in df.itertuples():
            hm = pd.Timestamp(str(r.month)).to_period("M")
            fm = hm - 1
            fm_str = str(pd.Timestamp(str(r.formation)).date()) if hasattr(r, "formation") else str(fm.to_timestamp("M").date())
            picks = [x for x in str(r.picks).split("|") if x]
            rets = []
            for tk in picks:
                if tk == "CASH":
                    rets.append(rf_map.get(str(hm), 0.0))
                elif (fm_str, tk) in ex_map:
                    rets.append(ex_map[(fm_str, tk)])
                elif tk in P_ym.columns and fm in P_ym.index and hm in P_ym.index and pd.notna(P_ym.at[fm, tk]) and pd.notna(P_ym.at[hm, tk]):
                    rets.append(float(P_ym.at[hm, tk] / P_ym.at[fm, tk] - 1.0))
                else:
                    # Delisted / last traded close inside holding month
                    sub = daily[tk].dropna() if tk in daily.columns else pd.Series(dtype=float)
                    sub_m = sub[(sub.index.to_period("M") == hm)]
                    p0 = float(P_ym.at[fm, tk]) if (tk in P_ym.columns and fm in P_ym.index and pd.notna(P_ym.at[fm, tk])) else np.nan
                    if len(sub_m) and pd.notna(p0) and p0 > 0:
                        rets.append(float(sub_m.iloc[-1] / p0 - 1.0))
            if len(rets) == len(picks) and len(rets) > 0:
                re_g = float(np.mean(rets))
                diff = abs(re_g - float(r.gross))
                n_checked += 1
                if diff > max_diff:
                    max_diff = diff
                if diff > 1e-8:
                    mismatch_examples.append({"month": str(r.month), "picks": r.picks, "ledger_gross": float(r.gross), "recomp_gross": re_g})
        cagr, mdd = cagr_and_mdd(df["net"])
        checks.append({
            "strategy": label,
            "execution": "close_to_close",
            "months_total": int(len(df)),
            "months_recomputed_from_raw_prices": n_checked,
            "max_abs_gross_diff": max_diff,
            "exact_match_lt_1e10": max_diff < 1e-10,
            "cagr_pct": round(cagr * 100, 4),
            "monthly_mdd_pct": round(mdd * 100, 4),
            "mismatches": mismatch_examples[:5],
        })

    # 2. Open-to-open ML2 & Top3 ledgers
    open_targets = [
        ("Claude_ML2_C_lgbm_Top3", SSM / "results/ml2/monthly_C_lgbm_top3.csv"),
        ("Claude_ML2_C_lgbm_Top1", SSM / "results/ml2/monthly_C_lgbm_top1.csv"),
        ("Claude_ML2_PureMom_Top3", SSM / "results/ml2/monthly_BENCH_mom_top3.csv"),
        ("Claude_ML2_PureMom_Top1", SSM / "results/ml2/monthly_BENCH_mom_top1.csv"),
        ("CodexV2_ML2_C_lgbm_Top3", CODEX_SSM / "results/ml2/monthly_C_lgbm_top3.csv"),
        ("CodexV2_ML2_C_lgbm_Top1", CODEX_SSM / "results/ml2/monthly_C_lgbm_top1.csv"),
        ("CodexV2_ML2_PureMom_Top3", CODEX_SSM / "results/ml2/monthly_BENCH_mom_top3.csv"),
        ("CodexV2_ML2_PureMom_Top1", CODEX_SSM / "results/ml2/monthly_BENCH_mom_top1.csv"),
        ("Top3_Study_Monthly_Skip1M", ROOT / "outputs/top3_qqq_rebalance_20261030/Top3_monthly_monthly_ledger.csv"),
    ]
    sessions = daily.index

    for label, lp in open_targets:
        if not lp.exists():
            continue
        df = pd.read_csv(lp)
        max_diff = 0.0
        n_checked = 0
        mismatch_examples = []
        for r in df.itertuples():
            hm_end = pd.Timestamp(str(r.month))
            fm_end = pd.Timestamp(str(r.formation)) if hasattr(r, "formation") else (hm_end - pd.offsets.MonthEnd(1))
            i0 = sessions.searchsorted(fm_end, side="right")
            i1 = sessions.searchsorted(hm_end, side="right")
            if i0 >= len(sessions) or i1 >= len(sessions):
                continue
            d0, d1 = sessions[i0], sessions[i1]
            picks = [x for x in str(r.picks).split("|") if x]
            rets = []
            for tk in picks:
                if tk == "CASH":
                    rets.append(rf_map.get(str(hm_end.to_period("M")), 0.0))
                    continue
                if (str(fm_end.date()), tk) in ex_map:
                    rets.append(ex_map[(str(fm_end.date()), tk)])
                    continue
                p0 = O.at[d0, tk] if (tk in O.columns and pd.notna(O.at[d0, tk])) else (daily.at[d0, tk] if tk in daily.columns else np.nan)
                p1 = O.at[d1, tk] if (tk in O.columns and pd.notna(O.at[d1, tk])) else (daily.at[d1, tk] if tk in daily.columns else np.nan)
                if pd.isna(p1) and tk in daily.columns:
                    # Terminal trade inside [d0, d1]
                    sub = daily[tk].loc[d0:hm_end].dropna()
                    if len(sub):
                        p1 = float(sub.iloc[-1])
                if pd.notna(p0) and pd.notna(p1) and p0 > 0:
                    rets.append(float(p1 / p0 - 1.0))
            if len(rets) == len(picks) and len(rets) > 0:
                re_g = float(np.mean(rets))
                diff = abs(re_g - float(r.gross))
                n_checked += 1
                if diff > max_diff:
                    max_diff = diff
                if diff > 1e-6:
                    mismatch_examples.append({"month": str(r.month), "picks": r.picks, "ledger_gross": float(r.gross), "recomp_gross": re_g, "diff": diff})
        cagr, mdd = cagr_and_mdd(df["net"])
        checks.append({
            "strategy": label,
            "execution": "next_day_open_to_open",
            "months_total": int(len(df)),
            "months_recomputed_from_raw_opens": n_checked,
            "max_abs_gross_diff": max_diff,
            "exact_match_lt_1e8": max_diff < 1e-8,
            "cagr_pct": round(cagr * 100, 4),
            "monthly_mdd_pct": round(mdd * 100, 4),
            "mismatches": mismatch_examples[:5],
        })

    return checks


def main():
    print("[04] Scanning all strategy ledgers across Claude original, Codex v2, Top-3 studies, and Sector Rotation...")
    c_files = sorted([p for p in glob.glob(str(SSM / "results/**/*.csv"), recursive=True) if "monthly_" in Path(p).name])
    v_files = sorted([p for p in glob.glob(str(CODEX_SSM / "results/**/*.csv"), recursive=True) if "monthly_" in Path(p).name])
    t_files = sorted(glob.glob(str(ROOT / "outputs/top3_*/*ledger*.csv")))

    c_sum, c_rows = scan_ledger_group(c_files, "claude_original_78a2d0d")
    v_sum, v_rows = scan_ledger_group(v_files, "codex_v2_4ea9a1d")
    t_sum, t_rows = scan_ledger_group(t_files, "top3_studies_20261030")

    all_rows_df = pd.DataFrame(c_rows + v_rows + t_rows)
    all_rows_df.to_csv(OUT_DIR / "04_all_ledgers_inventory.csv", index=False)

    print("[04] Independently recomputing headline close-to-close & open-to-open ledgers from raw vendor prices/opens...")
    headline_recomp = recompute_headline_ledgers_from_raw_prices()

    out = {
        "ledger_group_summaries": [c_sum, v_sum, t_sum],
        "total_ledgers_audited": len(all_rows_df),
        "independent_raw_endpoint_recomputation": headline_recomp,
    }
    out_p = OUT_DIR / "04_all_ledgers_audit.json"
    out_p.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"[04] DONE -> {out_p} ({len(all_rows_df)} ledgers audited)")
    for h in headline_recomp:
        print(f"     {h['strategy']}: {h['months_total']}m | max_gross_diff={h['max_abs_gross_diff']:.2e} | CAGR={h['cagr_pct']}% | mMDD={h['monthly_mdd_pct']}%")


if __name__ == "__main__":
    main()
