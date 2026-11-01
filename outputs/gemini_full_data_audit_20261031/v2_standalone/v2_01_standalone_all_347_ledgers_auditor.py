#!/usr/bin/env python3
"""
v2_01_standalone_all_347_ledgers_auditor.py — 100% Standalone Clean-Room Audit of ALL 347 Ledgers.

ZERO imports of any audited project module.
ZERO fallback to ledger values when raw price data is missing.

Audits every row of all 347 monthly strategy ledger CSVs across:
  - Claude 78a2d0d (`research/sector_stock_momentum/results/**`)
  - Codex v2 4ea9a1d (`backtest_versions/2026-10-30_codex_full_audit_v2/**`)
  - Top-3 Open-to-Open Studies (`outputs/top3_*_20261030/**`)
"""
import json
import math
import os
import sys
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from v2_cleanroom_lib import CleanRoomEquityStore, CleanRoomSmallCapStore


AUDIT_ROOT = os.path.dirname(HERE)
REPO_ROOT = os.path.dirname(os.path.dirname(AUDIT_ROOT))


def load_qqq_open_close(ledger_dir: str) -> Optional[pd.DataFrame]:
    p = os.path.join(ledger_dir, "QQQ_adjusted_prices.csv")
    if not os.path.exists(p):
        p = os.path.join(REPO_ROOT, "outputs", "top3_include_latest_month_20261030", "QQQ_adjusted_prices.csv")
    if not os.path.exists(p):
        return None
    df = pd.read_csv(p, parse_dates=["date"]).drop_duplicates("date", keep="last").set_index("date").sort_index()
    return df


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


def substantive_pit_flag(rel_path: str) -> str:
    if "/winners_holdout/" in rel_path:
        return "PIT_FAIL_SMALLCAP_UNIVERSE_AND_CIK_CONTAMINATION"
    if rel_path.startswith("research/sector_stock_momentum/results/ml2/"):
        return "PRE_FIX_ML2_VALUATION_AND_ADDITIVE_COST_BUG"
    if rel_path.startswith("research/sector_stock_momentum/results/ndx/monthly_C_") and "top_5" in rel_path:
        return "PRE_FIX_NDX_HARDCODED_20BP_COST_AND_REGIME_GROSS_BUG"
    if "factor_combo/" in rel_path and rel_path.startswith("research/"):
        return "NET_ONLY_LEGACY_FACTOR_COMBO"
    return "CLEAN_OR_FIXED_LEDGER"


def recompute_row_cleanroom(
    row: dict,
    prev_w_map: Optional[Dict[str, float]],
    row_idx: int,
    mode: str,
    rel_path: str,
    eq_store: CleanRoomEquityStore,
    sc_store: Optional[CleanRoomSmallCapStore],
    qqq_df: Optional[pd.DataFrame],
) -> dict:
    """
    Pure clean-room recomputation of a single monthly row from raw price/open files.
    NEVER falls back to row['gross'] or row['net']!
    """
    bn = os.path.basename(rel_path)
    m_str = row.get("month") if "month" in row else row.get("Unnamed: 0")
    m_dt = pd.Timestamp(m_str) + pd.offsets.MonthEnd(0)
    if "formation" in row and pd.notna(row.get("formation")):
        t_dt = pd.Timestamp(row["formation"])
    else:
        t_dt = m_dt - pd.offsets.MonthEnd(1)

    rfm = float(eq_store.rf.get(m_dt, 0.0))
    if "cash_return" in row and pd.notna(row.get("cash_return")):
        rfm_cash = float(row["cash_return"])
    else:
        rfm_cash = rfm

    # Case 1: Net-only ledger without constituent picks
    if mode == "net_only_no_picks":
        return {
            "status": "UNVERIFIABLE_NET_ONLY_LEDGER",
            "month": str(m_dt.date()),
            "cleanroom_gross": None,
            "cleanroom_net": None,
            "gross_diff": None,
            "net_diff": None,
            "max_asset_ret_diff": None,
            "detail": "Ledger CSV stores only net return without constituent picks",
        }

    # Case 2: Single-ETF close benchmark (SPY / XLK)
    if mode == "etf_close_benchmark":
        etf = "XLK" if "XLK" in bn else "SPY"
        r_val, st = eq_store.close_return(t_dt, etf, lag_days=0)
        if r_val is None:
            return {
                "status": "UNVERIFIABLE_MISSING_RAW_INPUT",
                "month": str(m_dt.date()),
                "cleanroom_gross": None,
                "cleanroom_net": None,
                "gross_diff": None,
                "net_diff": None,
                "max_asset_ret_diff": None,
                "detail": f"Missing raw price for {etf}: {st}",
            }
        led_net = float(row["net"])
        ndiff = abs(r_val - led_net)
        return {
            "status": "PASS" if ndiff <= 1e-6 else "FAIL_MATH_MISMATCH",
            "month": str(m_dt.date()),
            "cleanroom_gross": r_val,
            "cleanroom_net": r_val,
            "gross_diff": ndiff,
            "net_diff": ndiff,
            "max_asset_ret_diff": 0.0,
            "detail": f"ETF benchmark {etf} ({st})",
        }

    # Case 3: QQQ open-to-open buy-and-hold benchmark
    if mode == "qqq_open_benchmark":
        d0 = pd.Timestamp(row["execution_start"])
        d1 = pd.Timestamp(row["execution_end"])
        if qqq_df is None or d0 not in qqq_df.index or d1 not in qqq_df.index:
            return {
                "status": "UNVERIFIABLE_MISSING_RAW_INPUT",
                "month": str(m_dt.date()),
                "cleanroom_gross": None,
                "cleanroom_net": None,
                "gross_diff": None,
                "net_diff": None,
                "max_asset_ret_diff": None,
                "detail": f"Missing QQQ_adjusted_prices.csv on {d0.date()} or {d1.date()}",
            }
        o0 = float(qqq_df.at[d0, "adj_open"])
        o1 = float(qqq_df.at[d1, "adj_open"])
        g_val = o1 / o0 - 1.0
        # Row 0 pays 10 bp entry cost (`capital_after_costs = 1 / 1.001`) in QQQ buy-and-hold
        led_net = float(row["net"])
        n_val = (1.0 / 1.001) * (1.0 + g_val) - 1.0 if row_idx == 0 else g_val
        ndiff = abs(n_val - led_net)
        return {
            "status": "PASS" if ndiff <= 1e-6 else "FAIL_MATH_MISMATCH",
            "month": str(m_dt.date()),
            "cleanroom_gross": g_val,
            "cleanroom_net": n_val,
            "gross_diff": 0.0,
            "net_diff": ndiff,
            "max_asset_ret_diff": 0.0,
            "detail": f"QQQ adj_open {d0.date()}->{d1.date()}",
        }

    # Parse picks & weights
    raw_picks = row.get("picks")
    if (raw_picks is None or (isinstance(raw_picks, float) and math.isnan(raw_picks)) or str(raw_picks).strip() == "") and "pick" in row:
        raw_picks = row.get("pick")

    picks: List[str] = []
    if raw_picks is not None and not (isinstance(raw_picks, float) and math.isnan(raw_picks)):
        s_p = str(raw_picks).strip()
        if s_p and s_p.lower() != "nan":
            picks = [x.strip() for x in s_p.split("|") if x.strip()]

    weights: List[float] = []
    if "weights" in row and pd.notna(row.get("weights")) and str(row.get("weights")).strip() != "":
        weights = [float(x) for x in str(row["weights"]).split("|") if x.strip()]
        # If CSV printed equal weights truncated to 5 decimals (`f'{w:.5f}'` across 50-1500 stocks), restore exact 1/N
        if len(weights) > 1 and (max(weights) - min(weights) <= 1e-5) and abs(sum(weights) - 1.0) <= 0.02:
            weights = [1.0 / len(weights)] * len(weights)
    elif picks:
        weights = [1.0 / len(picks)] * len(picks)

    if len(picks) != len(weights):
        return {
            "status": "FAIL_MATH_MISMATCH",
            "month": str(m_dt.date()),
            "cleanroom_gross": None,
            "cleanroom_net": None,
            "gross_diff": None,
            "net_diff": None,
            "max_asset_ret_diff": None,
            "detail": f"Picks/weights length mismatch: {len(picks)} vs {len(weights)}",
        }

    # Bankrupt post-wipeout months (e.g. after a -100% single-stock stress event in Codex v2) have 0 capital
    if str(row.get("bankrupt", "")).lower() == "true" and float(row.get("capital_after_costs", 1.0)) == 0.0:
        led_gross = float(row["gross"]) if "gross" in row and pd.notna(row.get("gross")) else 0.0
        led_net = float(row["net"])
        gd, nd = abs(led_gross), abs(led_net)
        return {
            "status": "PASS" if (gd <= 1e-9 and nd <= 1e-9) else "FAIL_MATH_MISMATCH",
            "month": str(m_dt.date()),
            "cleanroom_gross": 0.0,
            "cleanroom_net": 0.0,
            "gross_diff": gd,
            "net_diff": nd,
            "max_asset_ret_diff": 0.0,
            "detail": "bankrupt_post_wipeout_zero_capital",
        }

    stress = (
        -0.30 if ("_stress30" in bn or "stress__30__" in bn)
        else (-1.00 if ("_stress100" in bn or "stress__100__" in bn) else None)
    )
    exec_s = pd.Timestamp(row["execution_start"]) if "execution_start" in row and pd.notna(row.get("execution_start")) else None
    exec_e = pd.Timestamp(row["execution_end"]) if "execution_end" in row and pd.notna(row.get("execution_end")) else None

    # Compute each constituent's clean-room return
    comp_rets: List[Tuple[str, float, float, str]] = []
    for tk, wt in zip(picks, weights):
        if mode == "open_to_open":
            r_i, st_i = eq_store.open_return(t_dt, tk, exec_start=exec_s, exec_end=exec_e)
        elif mode == "next_day_close":
            r_i, st_i = eq_store.close_return(t_dt, tk, lag_days=1)
        elif mode in ("smallcap_close", "smallcap_strict_close"):
            assert sc_store is not None
            r_i, st_i = sc_store.close_return(t_dt, tk, stress=stress)
        else:
            r_i, st_i = eq_store.close_return(t_dt, tk, lag_days=0)
            if stress is not None and st_i in ("unresolved", "source_gap", "unresolved_no_quote_after_entry"):
                r_i, st_i = float(stress), f"{st_i}_stressed"

        if r_i is None:
            return {
                "status": "UNVERIFIABLE_MISSING_RAW_INPUT",
                "month": str(m_dt.date()),
                "cleanroom_gross": None,
                "cleanroom_net": None,
                "gross_diff": None,
                "net_diff": None,
                "max_asset_ret_diff": None,
                "detail": f"Missing raw price for constituent {tk} at {t_dt.date()}: {st_i}",
            }
        comp_rets.append((tk, wt, r_i, st_i))

    # Optional: verify per-constituent asset_returns JSON column if recorded (Codex v2 factor_combo / explosive)
    max_asset_diff = 0.0
    if "asset_returns" in row and pd.notna(row.get("asset_returns")) and str(row["asset_returns"]).strip().startswith("{"):
        ar_map = json.loads(str(row["asset_returns"]))
        for tk, _, r_i, _ in comp_rets:
            if tk in ar_map and ar_map[tk] is not None:
                max_asset_diff = max(max_asset_diff, abs(r_i - float(ar_map[tk])))

    # Portfolio gross calculation from constituent weights, exposure, cash/borrowing, and hold6m intra-month exit cash
    exposure = float(row["exposure"]) if "exposure" in row and pd.notna(row.get("exposure")) else 1.0
    w_sum = sum(wt for _, wt, _, _ in comp_rets)
    is_hold6m = "hold6m" in bn

    if not comp_rets:
        # Pure cash month (e.g. +market overlay exposure=0 or eps_momentum CASH)
        clean_gross = rfm_cash
    elif is_hold6m:
        # In hold6m tranche_ledger, weights[s] = pos[s] / nav_start (summing to <= 1.0; remainder 1 - w_sum is idle/tranche cash).
        # Any stock with st != 'ok' exits during the month into tranche cash and earns (1 + r_s)*(1 + rfm) - 1.
        nav_end_over_nav_start = (1.0 - w_sum) * (1.0 + rfm)
        for _, wt, r_i, st_i in comp_rets:
            if st_i == "ok":
                nav_end_over_nav_start += wt * (1.0 + r_i)
            else:
                nav_end_over_nav_start += wt * (1.0 + r_i) * (1.0 + rfm)
        ret_on_invested = nav_end_over_nav_start - 1.0
        if "capital_after_costs" in row and pd.notna(row.get("capital_after_costs")):
            clean_gross = ret_on_invested
        else:
            # Claude tranche_ledger formula: gross = net + turnover * 0.001, where nav_start/nav0 = 1 - turnover * 0.001
            turn_val = float(row.get("turnover", 0.0))
            nav_start_over_nav0 = 1.0 - turn_val * 0.001
            clean_net_tr = nav_end_over_nav_start * nav_start_over_nav0 - 1.0
            clean_gross = clean_net_tr + turn_val * 0.001
    elif "cash_weight" in row and pd.notna(row.get("cash_weight")):
        cw = float(row["cash_weight"])
        clean_gross = sum(wt * r_i for _, wt, r_i, _ in comp_rets) + cw * rfm_cash
    else:
        r_stk = sum(wt * r_i for _, wt, r_i, _ in comp_rets)
        if w_sum < 0.999 and abs(exposure - 1.0) <= 1e-9:
            # Partial cash basket
            clean_gross = r_stk + (1.0 - w_sum) * rfm_cash
        else:
            cash_frac = 1.0 - exposure
            cash_contrib = cash_frac * rfm_cash if cash_frac >= 0 else cash_frac * (rfm_cash + 0.01 / 12.0)
            clean_gross = exposure * r_stk + cash_contrib

    # Portfolio net calculation
    cost_ps = float(row["cost_per_side"]) if "cost_per_side" in row and pd.notna(row.get("cost_per_side")) else (
        0.0 if (bn in ("monthly_SPY.csv", "monthly_XLK.csv") or ("BENCH_SPY" in bn and "turnover" not in row)) else 0.001
    )

    if "capital_after_costs" in row and pd.notna(row.get("capital_after_costs")):
        cap_ac = float(row["capital_after_costs"])
        clean_net = cap_ac * (1.0 + clean_gross) - 1.0
    elif "turnover" in row and pd.notna(row.get("turnover")):
        turn = float(row["turnover"])
        clean_net = clean_gross - turn * cost_ps
    else:
        # Pure first-principles portfolio weight turnover across non-cash holdings (ZERO use of row['gross'] - row['net'])
        cur_w_map = (
            {}
            if str(row.get("pick", "")).strip().startswith("CASH")
            else {p: w for p, w in zip(picks, weights) if not p.startswith("CASH")}
        )
        if row_idx == 0 or prev_w_map is None:
            turn = sum(cur_w_map.values())
        else:
            all_syms = set(prev_w_map) | set(cur_w_map)
            turn = sum(abs(cur_w_map.get(k, 0.0) - prev_w_map.get(k, 0.0)) for k in all_syms)
        clean_net = clean_gross - turn * cost_ps

    led_gross = float(row["gross"]) if "gross" in row and pd.notna(row.get("gross")) else None
    led_net = float(row["net"])

    # Note: weights in CSVs are formatted to 5 or 6 decimals (`f'{w:.5f}'` / `f'{w:.6f}'`) and exit_resolutions to 9 decimals.
    tol = 6e-5 if (len(picks) > 1 or is_hold6m) else 5e-6
    g_diff = abs(clean_gross - led_gross) if led_gross is not None else 0.0
    n_diff = abs(clean_net - led_net)

    ok = (g_diff <= tol) and (n_diff <= tol) and (max_asset_diff <= 5e-6)
    return {
        "status": "PASS" if ok else "FAIL_MATH_MISMATCH",
        "month": str(m_dt.date()),
        "cleanroom_gross": clean_gross,
        "cleanroom_net": clean_net,
        "gross_diff": g_diff if led_gross is not None else None,
        "net_diff": n_diff,
        "max_asset_ret_diff": max_asset_diff,
        "detail": f"mode={mode}, n_picks={len(picks)}, tol={tol:g}",
    }


def main() -> None:
    inv_path = os.path.join(AUDIT_ROOT, "04_all_ledgers_inventory.csv")
    inv = pd.read_csv(inv_path)
    print(f"[v2_01] Building clean-room standalone raw price/open stores (0 project imports)...")

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
            sp_s = get_eq_store(ssm_rel, False)
            sc_stores[k] = CleanRoomSmallCapStore(REPO_ROOT, sp_s, strict=strict)
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

        ssm_rel = (
            "backtest_versions/2026-10-30_codex_full_audit_v2/research/sector_stock_momentum"
            if rel_path.startswith("backtest_versions/2026-10-30_codex_full_audit_v2/")
            else "research/sector_stock_momentum"
        )
        include_ndx = (mode == "ndx_close") or ("top3_qqq" in rel_path)
        eq_s = get_eq_store(ssm_rel, include_ndx)
        sc_s = (
            get_sc_store(ssm_rel, mode == "smallcap_strict_close")
            if mode in ("smallcap_close", "smallcap_strict_close")
            else None
        )
        qqq_df = load_qqq_open_close(os.path.dirname(full_path)) if mode == "qqq_open_benchmark" else None

        total_months_audited += len(df)
        if mode == "net_only_no_picks":
            ledger_rows.append({
                "ledger_index": idx,
                "file": rel_path,
                "mode": mode,
                "months": len(df),
                "recomputed_pass_months": 0,
                "unverifiable_months": len(df),
                "fail_months": 0,
                "max_gross_diff": None,
                "max_net_diff": None,
                "max_asset_ret_diff": None,
                "cleanroom_verdict": "UNVERIFIABLE_NET_ONLY_LEDGER",
                "substantive_pit_flag": substantive_pit_flag(rel_path),
            })
            continue

        pass_m, unv_m, fail_m = 0, 0, 0
        max_gd, max_nd, max_ad = 0.0, 0.0, 0.0
        prev_w_map: Optional[Dict[str, float]] = None

        for r_i, row_dict in enumerate(df.to_dict(orient="records")):
            res = recompute_row_cleanroom(row_dict, prev_w_map, r_i, mode, rel_path, eq_s, sc_s, qqq_df)
            p_raw = row_dict.get("picks")
            if (p_raw is None or (isinstance(p_raw, float) and math.isnan(p_raw)) or str(p_raw).strip() == "") and "pick" in row_dict:
                p_raw = row_dict.get("pick")
            ps_cur = [x.strip() for x in str(p_raw).split("|") if x.strip() and str(p_raw).lower() != "nan"] if pd.notna(p_raw) else []
            if "weights" in row_dict and pd.notna(row_dict.get("weights")) and str(row_dict.get("weights")).strip() != "":
                ws_cur = [float(x) for x in str(row_dict["weights"]).split("|") if x.strip()]
            elif ps_cur:
                ws_cur = [1.0 / len(ps_cur)] * len(ps_cur)
            else:
                ws_cur = []
            if str(row_dict.get("pick", "")).strip().startswith("CASH"):
                prev_w_map = {}
            else:
                prev_w_map = {p: w for p, w in zip(ps_cur, ws_cur) if not p.startswith("CASH")}

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
                if len(mismatches_detail) < 100:
                    mismatches_detail.append({"file": rel_path, **res})
            else:
                fail_m += 1
                if res["gross_diff"] is not None:
                    max_gd = max(max_gd, res["gross_diff"])
                if res["net_diff"] is not None:
                    max_nd = max(max_nd, res["net_diff"])
                if len(mismatches_detail) < 100:
                    mismatches_detail.append({"file": rel_path, **res})

        if fail_m > 0:
            verdict = "FAIL_CLEANROOM_MATH_MISMATCH"
        elif unv_m > 0:
            verdict = "PARTIAL_UNVERIFIABLE_MISSING_RAW_INPUT"
        else:
            verdict = "PASS_CLEANROOM_CONSTITUENT_RECOMPUTED"

        ledger_rows.append({
            "ledger_index": idx,
            "file": rel_path,
            "mode": mode,
            "months": len(df),
            "recomputed_pass_months": pass_m,
            "unverifiable_months": unv_m,
            "fail_months": fail_m,
            "max_gross_diff": max_gd,
            "max_net_diff": max_nd,
            "max_asset_ret_diff": max_ad,
            "cleanroom_verdict": verdict,
            "substantive_pit_flag": substantive_pit_flag(rel_path),
        })

    out_df = pd.DataFrame(ledger_rows)
    out_csv = os.path.join(HERE, "v2_01_all_347_ledgers_cleanroom_audit.csv")
    out_df.to_csv(out_csv, index=False)

    verdict_counts = out_df["cleanroom_verdict"].value_counts().to_dict()
    pit_counts = out_df["substantive_pit_flag"].value_counts().to_dict()
    recomp_sub = out_df[out_df["cleanroom_verdict"] == "PASS_CLEANROOM_CONSTITUENT_RECOMPUTED"]

    summary = {
        "zero_project_imports": True,
        "zero_fallback_to_ledger": True,
        "total_ledgers_audited": len(out_df),
        "total_strategy_months_in_347_ledgers": int(total_months_audited),
        "total_strategy_months_cleanroom_recomputed_pass": int(total_months_recomputed),
        "cleanroom_verdict_counts": verdict_counts,
        "substantive_pit_flag_counts": pit_counts,
        "max_gross_diff_across_all_passing_ledgers": float(recomp_sub["max_gross_diff"].max()) if len(recomp_sub) else None,
        "max_net_diff_across_all_passing_ledgers": float(recomp_sub["max_net_diff"].max()) if len(recomp_sub) else None,
        "unverifiable_net_only_ledgers": out_df[out_df["cleanroom_verdict"] == "UNVERIFIABLE_NET_ONLY_LEDGER"]["file"].tolist(),
        "mismatches_or_unverifiable_sample": mismatches_detail[:40],
    }
    out_json = os.path.join(HERE, "v2_01_all_347_ledgers_cleanroom_summary.json")
    with open(out_json, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False)

    print(f"[v2_01] Audited {len(out_df)} ledgers ({total_months_audited} months). Verdict breakdown:")
    for k, v in verdict_counts.items():
        print(f"  {k}: {v}")
    if mismatches_detail:
        print(f"[v2_01] Sample non-pass rows ({len(mismatches_detail)} logged):")
        for item in mismatches_detail[:10]:
            print(" ", item)


if __name__ == "__main__":
    main()
