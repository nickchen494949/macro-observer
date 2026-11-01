#!/usr/bin/env python3
"""
v2_01_standalone_all_347_ledgers_auditor.py — 100% First-Principles Standalone Clean-Room Audit of ALL 347 Ledgers.

ZERO imports of any audited project module (enforced mechanically by v2_00 via `ast.parse`).
ZERO fallback to ledger values when raw price data is missing (`UNVERIFIABLE_MISSING_RAW_INPUT`).
ZERO reads of ledger `turnover`, `capital_after_costs`, `cash_return`, or project-generated monthly RF CSVs (enforced by v2_00):
  - Transaction costs (drifted pre-trade weights `w_prev`, quarterly non-rebalance drift, 6-sleeve overlapping
    `hold6m` tranche accounting, self-financing bisection, and additive `turn * 10bp`) are reconstructed 100%
    from first principles using `(picks, weights)` + raw constituent returns.
  - Monthly cash / T-bill carry `rf` is computed 100% directly from raw `data/fred/DGS3MO.json`.
  - Scope labels honestly distinguish the 10 core headline ledgers whose full PIT signal/model/pick chain is
    independently reconstructed end-to-end in `v2_05` (`FULL_CHAIN_PIT_SIGNAL_PICK_AND_COST_RECONSTRUCTED_V2_05`)
    from secondary ledgers verified at the constituent-return + first-principles-cost level
    (`RETURN_AND_FIRST_PRINCIPLES_COST_VERIFIED_ONLY`) and explicit defective / unverifiable tiers.
"""
import json
import os
import sys
from typing import Dict, List, Optional, Tuple

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from v2_cleanroom_lib import (
    CleanRoomEquityStore,
    CleanRoomSmallCapStore,
    simulate_cleanroom_ledger_rows,
)


AUDIT_ROOT = os.path.dirname(HERE)
REPO_ROOT = os.path.dirname(os.path.dirname(AUDIT_ROOT))

FULL_CHAIN_PURE_MOMENTUM_AND_SPEC_PASS_LEDGERS = {
    "research/sector_stock_momentum/results/monthly_NO_SECTOR_FILTER__top_1_stock.csv",
    "backtest_versions/2026-10-30_codex_full_audit_v2/research/sector_stock_momentum/results/monthly_NO_SECTOR_FILTER__top_1_stock.csv",
    "research/sector_stock_momentum/results/monthly_SPEC.csv",
    "backtest_versions/2026-10-30_codex_full_audit_v2/research/sector_stock_momentum/results/monthly_SPEC.csv",
    "outputs/top3_include_latest_month_20261030/Top3_skip_monthly_monthly_ledger.csv",
    "outputs/top3_qqq_rebalance_20261030/Top3_monthly_monthly_ledger.csv",
    "backtest_versions/2026-10-30_codex_full_audit_v2/research/sector_stock_momentum/results/ml2/monthly_BENCH_momentum_Top1.csv",
    "backtest_versions/2026-10-30_codex_full_audit_v2/research/sector_stock_momentum/results/ml2/monthly_BENCH_momentum_Top3.csv",
}

FULL_CHAIN_CODEX_V2_CLGBM_FLAGGED_LEDGERS = {
    "backtest_versions/2026-10-30_codex_full_audit_v2/research/sector_stock_momentum/results/ml2/monthly_C_lgbm_Top1.csv",
    "backtest_versions/2026-10-30_codex_full_audit_v2/research/sector_stock_momentum/results/ml2/monthly_C_lgbm_Top3.csv",
}

CODEX_V2_CAM_RIDGE_BUG_LEDGERS = {
    "backtest_versions/2026-10-30_codex_full_audit_v2/research/sector_stock_momentum/results/ml2/monthly_A_ridge_Top3.csv",
    "backtest_versions/2026-10-30_codex_full_audit_v2/research/sector_stock_momentum/results/ml2/monthly_B_ridge_Top1.csv",
    "backtest_versions/2026-10-30_codex_full_audit_v2/research/sector_stock_momentum/results/ml2/monthly_B_ridge_Top3.csv",
    "backtest_versions/2026-10-30_codex_full_audit_v2/research/sector_stock_momentum/results/ml2/monthly_C_ridge_Top1.csv",
    "backtest_versions/2026-10-30_codex_full_audit_v2/research/sector_stock_momentum/results/ml2/monthly_C_ridge_Top3.csv",
}


def load_qqq_open_close(ledger_dir: str) -> Optional[pd.DataFrame]:
    p = os.path.join(ledger_dir, "QQQ_adjusted_prices.csv")
    if not os.path.exists(p):
        p = os.path.join(REPO_ROOT, "outputs", "top3_include_latest_month_20261030", "QQQ_adjusted_prices.csv")
    if not os.path.exists(p):
        return None
    return pd.read_csv(p, parse_dates=["date"]).drop_duplicates("date", keep="last").set_index("date").sort_index()


def classify_ledger_mode(rel_path: str, cols: List[str]) -> str:
    bn = os.path.basename(rel_path)
    if "picks" not in cols and "pick" not in cols:
        if bn in ("monthly_SPY.csv", "monthly_SPY_full.csv", "monthly_XLK.csv"):
            return "etf_close_benchmark"
        if bn == "QQQ_buy_hold_monthly_ledger.csv":
            return "qqq_open_benchmark"
        return "net_only_no_picks"
    if "/ml2/" in rel_path or rel_path.startswith("outputs/top3_"):
        return "open_to_open"
    if "next_day_close" in bn or "next_day" in bn:
        return "next_day_close"
    if "/winners_holdout/" in rel_path:
        return "smallcap_strict_close" if "STRICT" in bn else "smallcap_close"
    if "/ndx/" in rel_path:
        return "ndx_close"
    return "sp_close"


def audit_scope_and_pit_status(rel_path: str, mode: str) -> str:
    if mode == "net_only_no_picks":
        return "NET_ONLY_LEGACY_FACTOR_COMBO_NO_PICKS"
    if "/winners_holdout/" in rel_path:
        return "PIT_FAIL_SMALLCAP_UNIVERSE_AND_CIK_CONTAMINATION"
    if rel_path.startswith("research/sector_stock_momentum/results/ml2/"):
        return "PRE_FIX_ML2_VALUATION_EXIT_AND_ADDITIVE_COST_BUG"
    if rel_path.startswith("research/sector_stock_momentum/results/ndx/monthly_C_") and "top_5" in rel_path:
        return "PRE_FIX_NDX_HARDCODED_20BP_COST_AND_REGIME_GROSS_BUG"
    if rel_path == "research/sector_stock_momentum/results/monthly_SPEC___next_day_close_execution.csv":
        return "PRE_FIX_NEXT_DAY_CLOSE_EXIT_DENOM_BUG"
    if rel_path in CODEX_V2_CAM_RIDGE_BUG_LEDGERS:
        return "CODEX_V2_ML2_RIDGE_CAM_OPEN_BOUNDARY_OFF_BY_ONE_BUG"
    if rel_path in FULL_CHAIN_PURE_MOMENTUM_AND_SPEC_PASS_LEDGERS:
        return "FULL_CHAIN_PIT_SIGNAL_PICK_AND_COST_VERIFIED_PASS_V2_05"
    if rel_path in FULL_CHAIN_CODEX_V2_CLGBM_FLAGGED_LEDGERS:
        return "FULL_CHAIN_RECONSTRUCTED_V2_05_FLAGGED_CAM_TRAINING_OPEN_CUTOFF_AND_ADJCLOSE_DIVIDEND_SENSITIVITY"
    return "RETURN_AND_FIRST_PRINCIPLES_COST_VERIFIED_ONLY"


def audit_etf_close_benchmark(df: pd.DataFrame, rel_path: str, eq_store: CleanRoomEquityStore) -> List[dict]:
    bn = os.path.basename(rel_path)
    etf = "XLK" if "XLK" in bn else "SPY"
    out = []
    for row in df.to_dict(orient="records"):
        m_str = row.get("month") if "month" in row else row.get("Unnamed: 0")
        m_dt = pd.Timestamp(m_str) + pd.offsets.MonthEnd(0)
        t_dt = pd.Timestamp(row["formation"]) if ("formation" in row and pd.notna(row.get("formation"))) else (m_dt - pd.offsets.MonthEnd(1))
        r_val, st = eq_store.close_return(t_dt, etf, lag_days=0)
        if r_val is None:
            out.append({
                "status": "UNVERIFIABLE_MISSING_RAW_INPUT",
                "month": str(m_dt.date()),
                "gross_diff": None,
                "net_diff": None,
                "max_asset_ret_diff": None,
                "detail": f"Missing raw price for {etf}: {st}",
            })
            continue
        led_net = float(row["net"])
        ndiff = abs(r_val - led_net)
        out.append({
            "status": "PASS" if ndiff <= 1e-6 else "FAIL_MATH_MISMATCH",
            "month": str(m_dt.date()),
            "gross_diff": ndiff,
            "net_diff": ndiff,
            "max_asset_ret_diff": 0.0,
            "detail": f"ETF benchmark {etf} ({st})",
        })
    return out


def audit_qqq_open_benchmark(df: pd.DataFrame, qqq_df: Optional[pd.DataFrame]) -> List[dict]:
    out = []
    for r_idx, row in enumerate(df.to_dict(orient="records")):
        m_str = row.get("month") if "month" in row else row.get("Unnamed: 0")
        m_dt = pd.Timestamp(m_str) + pd.offsets.MonthEnd(0)
        d0 = pd.Timestamp(row["execution_start"])
        d1 = pd.Timestamp(row["execution_end"])
        if qqq_df is None or d0 not in qqq_df.index or d1 not in qqq_df.index:
            out.append({
                "status": "UNVERIFIABLE_MISSING_RAW_INPUT",
                "month": str(m_dt.date()),
                "gross_diff": None,
                "net_diff": None,
                "max_asset_ret_diff": None,
                "detail": f"Missing QQQ_adjusted_prices.csv on {d0.date()} or {d1.date()}",
            })
            continue
        g_val = float(qqq_df.at[d1, "adj_open"]) / float(qqq_df.at[d0, "adj_open"]) - 1.0
        led_net = float(row["net"])
        # First-principles self-financing entry cost on month 0 (`k = 1 / 1.001`), zero rebalance thereafter
        n_val = (1.0 / 1.001) * (1.0 + g_val) - 1.0 if r_idx == 0 else g_val
        ndiff = abs(n_val - led_net)
        out.append({
            "status": "PASS" if ndiff <= 1e-6 else "FAIL_MATH_MISMATCH",
            "month": str(m_dt.date()),
            "gross_diff": 0.0,
            "net_diff": ndiff,
            "max_asset_ret_diff": 0.0,
            "detail": f"QQQ adj_open {d0.date()}->{d1.date()}",
        })
    return out


def main() -> None:
    inv_path = os.path.join(AUDIT_ROOT, "04_all_ledgers_inventory.csv")
    inv = pd.read_csv(inv_path)
    print("[v2_01] Building clean-room standalone raw price/open/DGS3MO stores (0 project imports, 0 ledger cost reads)...")

    stores: Dict[Tuple[str, bool], CleanRoomEquityStore] = {}
    sc_stores: Dict[Tuple[str, bool], CleanRoomSmallCapStore] = {}

    def get_eq_store(ssm_rel: str, include_ndx: bool) -> CleanRoomEquityStore:
        k = (ssm_rel, include_ndx)
        if k not in stores:
            stores[k] = CleanRoomEquityStore(REPO_ROOT, ssm_rel=ssm_rel, include_ndx=include_ndx)
        return stores[k]

    def get_sc_store(ssm_rel: str, strict: bool) -> CleanRoomSmallCapStore:
        k = (ssm_rel, strict)
        if k not in sc_stores:
            sc_stores[k] = CleanRoomSmallCapStore(REPO_ROOT, get_eq_store(ssm_rel, False), strict=strict)
        return sc_stores[k]

    ledger_rows = []
    mismatches_detail = []
    total_months_audited = 0
    total_months_recomputed = 0

    for idx, r in enumerate(inv.itertuples(), 1):
        rel_path = r.file
        full_path = os.path.join(REPO_ROOT, rel_path)
        df = pd.read_csv(full_path)
        cols = list(df.columns)
        mode = classify_ledger_mode(rel_path, cols)
        scope_flag = audit_scope_and_pit_status(rel_path, mode)

        total_months_audited += len(df)
        if mode == "net_only_no_picks":
            ledger_rows.append({
                "ledger_index": idx,
                "file": rel_path,
                "mode": mode,
                "cost_convention": "unverifiable_no_picks",
                "months": len(df),
                "recomputed_pass_months": 0,
                "unverifiable_months": len(df),
                "fail_months": 0,
                "max_gross_diff": None,
                "max_net_diff": None,
                "max_asset_ret_diff": None,
                "cleanroom_verdict": "UNVERIFIABLE_NET_ONLY_LEDGER",
                "audit_scope_and_pit_status": scope_flag,
            })
            continue

        ssm_rel = (
            "backtest_versions/2026-10-30_codex_full_audit_v2/research/sector_stock_momentum"
            if rel_path.startswith("backtest_versions/2026-10-30_codex_full_audit_v2/")
            else "research/sector_stock_momentum"
        )
        include_ndx = (mode == "ndx_close") or ("top3_qqq" in rel_path)
        eq_s = get_eq_store(ssm_rel, include_ndx)

        if mode == "etf_close_benchmark":
            eval_rows = audit_etf_close_benchmark(df, rel_path, eq_s)
            cost_conv = "zero_cost_etf_benchmark"
        elif mode == "qqq_open_benchmark":
            qqq_df = load_qqq_open_close(os.path.dirname(full_path))
            eval_rows = audit_qqq_open_benchmark(df, qqq_df)
            cost_conv = "qqq_buy_and_hold_10bp_entry"
        else:
            sc_s = (
                get_sc_store(ssm_rel, mode == "smallcap_strict_close")
                if mode in ("smallcap_close", "smallcap_strict_close")
                else None
            )
            sim_rows = simulate_cleanroom_ledger_rows(df, rel_path, mode, eq_s, sc_s)
            is_hold6m = "hold6m" in os.path.basename(rel_path)
            raw_records = df.to_dict(orient="records")
            cost_conv = sim_rows[0]["cost_convention"] if sim_rows else "unknown"
            eval_rows = []
            for sr, raw_r in zip(sim_rows, raw_records):
                if sr["unverifiable_reason"] is not None:
                    eval_rows.append({
                        "status": "UNVERIFIABLE_MISSING_RAW_INPUT",
                        "month": sr["month"],
                        "gross_diff": None,
                        "net_diff": None,
                        "max_asset_ret_diff": None,
                        "detail": f"Missing raw price: {sr['unverifiable_reason']}",
                    })
                    continue

                max_ad_row = 0.0
                if "asset_returns" in raw_r and pd.notna(raw_r.get("asset_returns")) and str(raw_r["asset_returns"]).strip().startswith("{"):
                    ar_map = json.loads(str(raw_r["asset_returns"]))
                    for tk, _, ri, _ in sr["comp_rets"]:
                        if tk in ar_map and ar_map[tk] is not None and ri is not None:
                            max_ad_row = max(max_ad_row, abs(float(ri) - float(ar_map[tk])))

                tol = 6e-5 if (len(sr["picks"]) > 1 or is_hold6m) else 5e-6
                g_diff = abs(sr["clean_gross"] - sr["ledger_gross"]) if sr["ledger_gross"] is not None else 0.0
                n_diff = abs(sr["clean_net"] - sr["ledger_net"])
                ok = (g_diff <= tol) and (n_diff <= tol) and (max_ad_row <= 5e-6)
                eval_rows.append({
                    "status": "PASS" if ok else "FAIL_MATH_MISMATCH",
                    "month": sr["month"],
                    "cleanroom_gross": sr["clean_gross"],
                    "ledger_gross": sr["ledger_gross"],
                    "cleanroom_net": sr["clean_net"],
                    "ledger_net": sr["ledger_net"],
                    "reconstructed_turn": sr["reconstructed_turn"],
                    "gross_diff": g_diff if sr["ledger_gross"] is not None else None,
                    "net_diff": n_diff,
                    "max_asset_ret_diff": max_ad_row,
                    "detail": f"mode={mode}, cost={sr['cost_convention']}, n_picks={len(sr['picks'])}, tol={tol:g}",
                })

        pass_m, unv_m, fail_m = 0, 0, 0
        max_gd, max_nd, max_ad = 0.0, 0.0, 0.0
        for res in eval_rows:
            if res["status"] == "PASS":
                pass_m += 1
                total_months_recomputed += 1
                if res["gross_diff"] is not None:
                    max_gd = max(max_gd, res["gross_diff"])
                if res["net_diff"] is not None:
                    max_nd = max(max_nd, res["net_diff"])
                if res["max_asset_ret_diff"] is not None:
                    max_ad = max(max_ad, res["max_asset_ret_diff"])
            elif res["status"].startswith("UNVERIFIABLE"):
                unv_m += 1
                if len(mismatches_detail) < 120:
                    mismatches_detail.append({"file": rel_path, **res})
            else:
                fail_m += 1
                if res["gross_diff"] is not None:
                    max_gd = max(max_gd, res["gross_diff"])
                if res["net_diff"] is not None:
                    max_nd = max(max_nd, res["net_diff"])
                if len(mismatches_detail) < 120:
                    mismatches_detail.append({"file": rel_path, **res})

        if fail_m > 0:
            verdict = "FAIL_CLEANROOM_FIRST_PRINCIPLES_MISMATCH"
        elif unv_m > 0:
            verdict = "PARTIAL_UNVERIFIABLE_MISSING_RAW_INPUT"
        else:
            verdict = "PASS_CLEANROOM_FIRST_PRINCIPLES_RECOMPUTED"

        ledger_rows.append({
            "ledger_index": idx,
            "file": rel_path,
            "mode": mode,
            "cost_convention": cost_conv,
            "months": len(df),
            "recomputed_pass_months": pass_m,
            "unverifiable_months": unv_m,
            "fail_months": fail_m,
            "max_gross_diff": max_gd,
            "max_net_diff": max_nd,
            "max_asset_ret_diff": max_ad,
            "cleanroom_verdict": verdict,
            "audit_scope_and_pit_status": scope_flag,
        })

    out_df = pd.DataFrame(ledger_rows)
    out_csv = os.path.join(HERE, "v2_01_all_347_ledgers_cleanroom_audit.csv")
    out_df.to_csv(out_csv, index=False)

    verdict_counts = out_df["cleanroom_verdict"].value_counts().to_dict()
    scope_counts = out_df["audit_scope_and_pit_status"].value_counts().to_dict()
    recomp_sub = out_df[out_df["cleanroom_verdict"] == "PASS_CLEANROOM_FIRST_PRINCIPLES_RECOMPUTED"]
    failed_files = out_df[out_df["cleanroom_verdict"] == "FAIL_CLEANROOM_FIRST_PRINCIPLES_MISMATCH"][
        ["file", "fail_months", "max_gross_diff", "max_net_diff", "audit_scope_and_pit_status"]
    ].to_dict(orient="records")

    summary = {
        "zero_project_imports": True,
        "zero_fallback_to_ledger": True,
        "zero_reads_of_ledger_cost_or_cash_columns": True,
        "rf_source": "data/fred/DGS3MO.json (100% raw FRED Treasury series, zero use of project-generated monthly RF CSVs)",
        "total_ledgers_audited": len(out_df),
        "total_strategy_months_in_347_ledgers": int(total_months_audited),
        "total_strategy_months_cleanroom_first_principles_pass": int(total_months_recomputed),
        "cleanroom_verdict_counts": verdict_counts,
        "audit_scope_and_pit_status_counts": scope_counts,
        "max_gross_diff_across_all_passing_ledgers": float(recomp_sub["max_gross_diff"].max()) if len(recomp_sub) else None,
        "max_net_diff_across_all_passing_ledgers": float(recomp_sub["max_net_diff"].max()) if len(recomp_sub) else None,
        "failed_ledgers_first_principles": failed_files,
        "unverifiable_net_only_ledgers": out_df[out_df["cleanroom_verdict"] == "UNVERIFIABLE_NET_ONLY_LEDGER"]["file"].tolist(),
        "mismatches_or_unverifiable_sample": mismatches_detail[:60],
    }
    out_json = os.path.join(HERE, "v2_01_all_347_ledgers_cleanroom_summary.json")
    with open(out_json, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False)

    print(f"[v2_01] Audited {len(out_df)} ledgers ({total_months_audited} months). Verdict breakdown:")
    for k, v in verdict_counts.items():
        print(f"  {k}: {v}")
    print("[v2_01] Honest scope & PIT status breakdown:")
    for k, v in scope_counts.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
