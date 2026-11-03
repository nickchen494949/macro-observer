#!/usr/bin/env python3
"""
STEP 4 (CLEAN-ROOM): Standalone LightGBM Walk-Forward Training & Month-by-Month Reconciliation
===============================================================================================
Strict Clean-Room Rules:
- Zero imports from original project `.py` modules.
- Reconstructs cross-sectional feature ranking (`pct=True - 0.5`), target rank label,
  and annual walk-forward LightGBM regression (`n_estimators=300, learning_rate=0.05,
  max_depth=3, num_leaves in {7, 15}, min_child_samples=100, subsample=0.8,
  colsample_bytree=0.8, random_state=7`) from scratch.
- Compares 6 clean-room training protocols:
  1) `Mode_A1_HybridRepro_Purged_Nov30`: Exact clean-room replication of commit `a455ed7`
     (`val <= Y-1-11-30`, `tr2 <= Y-1-11-30`, hybrid S&P/NDX `sector_mom` & `dv_ratio`).
  2) `Mode_A2_HybridRepro_UnpurgedVal_Dec31`: Exact clean-room replication of commit `20d6cbf`
     (`val <= Y-1-12-31`, `tr2 <= Y-1-11-30`).
  3) `Mode_A3_HybridRepro_UnpurgedBoth_Dec31`: What if both `val` and `tr2` used `<= Y-1-12-31`?
  4) `Mode_B1_PureQQQ_Purged_Nov30`: 100% pure standalone QQQ features (`sector_mom` strictly
     within Nasdaq-100; uniform `dv_ratio`), strictly purged at `Y-1-11-30`.
  5) `Mode_B2_PureQQQ_FixedNL7`: Pure standalone QQQ features + fixed `num_leaves=7` (zero val tuning).
  6) `Mode_B3_PureQQQ_RankVal`: Pure standalone QQQ features + rank-IC validation (zero CAGR peeking).
- Produces a complete month-by-month reconciliation (`step4_month_by_month_reconciliation.csv`)
  and fold-by-fold hyperparameter choice table (`step4_fold_hyperparameter_audit.csv`).
"""

import os
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from q2_cleanroom_price_engine import (
    ORIG_LEDGER_DIR,
    OUT_DIR,
    CleanRoomPriceEngine,
    load_cleanroom_prices_and_universe,
    load_rf,
)
from q3_cleanroom_18_features import FEATURES_18

COST_PER_SIDE = 0.0010
TEST_YEARS = list(range(2015, 2027))


def cleanroom_rank_features(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    return df.groupby("t")[cols].rank(pct=True) - 0.5


def cleanroom_rank_target(df: pd.DataFrame) -> pd.Series:
    return df.groupby("t")["ret_oo"].rank(pct=True) - 0.5


def cleanroom_run_portfolio(
    W: dict[pd.Timestamp, dict[str, float]],
    px_eng: CleanRoomPriceEngine,
    rf: pd.Series,
    cost_per_side: float = COST_PER_SIDE,
    extra_slippage_per_side: float = 0.0,
    stress_unresolved: float | None = None,
) -> pd.DataFrame:
    """
    Standalone portfolio ledger builder with drifted pre-trade weights and per-side transaction cost + slippage.
    """
    rows = []
    w_prev = {}
    total_fee_rate = cost_per_side + extra_slippage_per_side

    for t in sorted(W.keys()):
        w = W[t]
        hold_m = t + pd.offsets.MonthEnd(1)
        rets = {}
        for s in w:
            r_, st_ = px_eng.ret(t, s)
            if stress_unresolved is not None and st_ in ("unresolved", "source_gap"):
                r_ = stress_unresolved
            rets[s] = (r_, st_)

        r_stk = sum(w[s] * rets[s][0] for s in w) if w else 0.0
        target = {s: w[s] for s in w}
        turn = sum(abs(target.get(s, 0.0) - w_prev.get(s, 0.0)) for s in set(target) | set(w_prev))
        gross = float(r_stk)
        net = float(gross - turn * total_fee_rate)

        grow = {s: target[s] * (1.0 + rets[s][0]) for s in w if rets[s][1] == "ok"}
        w_prev = {s: v / (1.0 + gross) for s, v in grow.items()} if gross > -1.0 else {}

        rows.append({
            "formation": t,
            "month": hold_m,
            "net": net,
            "gross": gross,
            "turnover": float(turn),
            "exposure": 1.0,
            "picks": "|".join(w.keys()),
            "weights": "|".join(f"{w[s]:.5f}" for s in w),
            "status": "|".join(rets[s][1] for s in w),
        })
    return pd.DataFrame(rows).set_index("month")


def cleanroom_topk_weights(df: pd.DataFrame, score_col: str, k: int = 1, rank_slice: tuple[int, int] | None = None) -> dict[pd.Timestamp, dict[str, float]]:
    W = {}
    for t, g in df.dropna(subset=[score_col]).groupby("t", sort=True):
        s_g = g.sort_values([score_col, "ticker"], ascending=[False, True])
        if rank_slice is not None:
            r0, r1 = rank_slice
            top = s_g.ticker.iloc[r0:r1].tolist()
        else:
            top = s_g.ticker.head(k).tolist()
        if top:
            W[t] = {s: 1.0 / len(top) for s in top}
    return W


def cleanroom_fit_predict_lgbm(
    R_tr: np.ndarray,
    y_tr: np.ndarray,
    R_te: np.ndarray,
    num_leaves: int,
    min_child_samples: int = 100,
    seed: int = 7,
) -> np.ndarray:
    mdl = lgb.LGBMRegressor(
        n_estimators=300,
        learning_rate=0.05,
        num_leaves=num_leaves,
        max_depth=3,
        min_child_samples=min_child_samples,
        subsample=0.8,
        subsample_freq=1,
        colsample_bytree=0.8,
        random_state=seed,
        verbose=-1,
    )
    mdl.fit(R_tr, y_tr)
    return mdl.predict(R_te)


def run_cleanroom_walkforward(
    df_panel: pd.DataFrame,
    px_eng: CleanRoomPriceEngine,
    rf: pd.Series,
    cols: list[str] = FEATURES_18,
    k: int = 1,
    val_end_mode: str = "nov30",       # 'nov30' or 'dec31'
    refit_end_mode: str = "nov30",     # 'nov30' or 'dec31'
    val_criterion: str = "val_cagr",   # 'val_cagr', 'val_rank', 'fixed_nl7', 'fixed_nl15'
    seed: int = 7,
) -> tuple[pd.DataFrame, dict]:
    D = df_panel.copy().reset_index(drop=True)
    R_all = cleanroom_rank_features(D, cols)
    y_all = cleanroom_rank_target(D)
    D["score"] = np.nan

    med_size = D.groupby("t").size().median()
    min_c = 50 if med_size <= 40 else (100 if med_size <= 110 else 200)
    fold_info = {}

    for Y in TEST_YEARS:
        tr_start = pd.Timestamp("2011-01-31")
        tr_end = pd.Timestamp(f"{Y - 3}-11-30")
        val_end = pd.Timestamp(f"{Y - 1}-11-30") if val_end_mode == "nov30" else pd.Timestamp(f"{Y - 1}-12-31")
        refit_end = pd.Timestamp(f"{Y - 1}-11-30") if refit_end_mode == "nov30" else pd.Timestamp(f"{Y - 1}-12-31")

        tr = D[(D.t >= tr_start) & (D.t <= tr_end) & D.ret_oo.notna()]
        val = D[(D.t >= pd.Timestamp(f"{Y - 2}-01-31")) & (D.t <= val_end) & D.ret_oo.notna()]
        te = D[D.t.dt.year == Y]
        if te.empty or tr.empty:
            continue

        val_metrics = {}
        if val_criterion == "fixed_nl7":
            best_nl = 7
        elif val_criterion == "fixed_nl15":
            best_nl = 15
        else:
            best_nl, best_v = 7, -np.inf
            for nl in (7, 15):
                pred_v = cleanroom_fit_predict_lgbm(
                    R_all.loc[tr.index, cols].values,
                    y_all.loc[tr.index].values,
                    R_all.loc[val.index, cols].values,
                    num_leaves=nl,
                    min_child_samples=min_c,
                    seed=seed,
                )
                v_df = val.copy()
                v_df["s"] = pred_v
                if val_criterion == "val_cagr":
                    w_v = cleanroom_topk_weights(v_df, "s", k=k)
                    led_v = cleanroom_run_portfolio(w_v, px_eng, rf)
                    r_v = led_v.net
                    metric = float((1.0 + r_v).prod() ** (12.0 / len(r_v)) - 1.0)
                else:
                    v_df["r_rk"] = y_all.loc[val.index]
                    metric = float(v_df.sort_values(["t", "s"], ascending=[True, False]).groupby("t").head(5)["r_rk"].mean())
                val_metrics[nl] = round(metric * 100, 3) if val_criterion == "val_cagr" else round(metric, 5)
                if metric > best_v:
                    best_nl, best_v = nl, metric

        tr2 = D[(D.t >= tr_start) & (D.t <= refit_end) & D.ret_oo.notna()]
        pred_te = cleanroom_fit_predict_lgbm(
            R_all.loc[tr2.index, cols].values,
            y_all.loc[tr2.index].values,
            R_all.loc[te.index, cols].values,
            num_leaves=best_nl,
            min_child_samples=min_c,
            seed=seed,
        )
        D.loc[te.index, "score"] = pred_te
        fold_info[Y] = {
            "test_year": Y,
            "chosen_num_leaves": best_nl,
            "val_end": val_end.strftime("%Y-%m-%d"),
            "refit_end": refit_end.strftime("%Y-%m-%d"),
            "n_train_rows": len(tr),
            "n_val_rows": len(val),
            "n_refit_rows": len(tr2),
            "val_metric_nl7": val_metrics.get(7, np.nan),
            "val_metric_nl15": val_metrics.get(15, np.nan),
        }

    return D, fold_info


def main():
    print("Step 4: Running clean-room LightGBM walk-forward & month-by-month reconciliation...", flush=True)
    U = load_cleanroom_prices_and_universe()
    px_eng = CleanRoomPriceEngine(U, mode="open")
    rf = load_rf(pd.date_range("2009-01-31", "2026-10-31", freq="ME"))

    df_hybrid = pd.read_parquet(OUT_DIR / "cleanroom_panel_qqq_hybrid_repro.parquet")
    df_pure = pd.read_parquet(OUT_DIR / "cleanroom_panel_qqq_pure_standalone.parquet")

    modes = [
        ("Mode_A1_HybridRepro_Purged_Nov30", df_hybrid, "nov30", "nov30", "val_cagr"),
        ("Mode_A2_HybridRepro_UnpurgedVal_Dec31", df_hybrid, "dec31", "nov30", "val_cagr"),
        ("Mode_A3_HybridRepro_UnpurgedBoth_Dec31", df_hybrid, "dec31", "dec31", "val_cagr"),
        ("Mode_B1_PureQQQ_Purged_Nov30", df_pure, "nov30", "nov30", "val_cagr"),
        ("Mode_B2_PureQQQ_FixedNL7", df_pure, "nov30", "nov30", "fixed_nl7"),
        ("Mode_B3_PureQQQ_RankVal", df_pure, "nov30", "nov30", "val_rank"),
    ]

    ledgers = {}
    preds_by_mode = {}
    fold_rows = []

    for m_name, panel, v_end, r_end, v_crit in modes:
        D_pred, f_info = run_cleanroom_walkforward(
            panel, px_eng, rf, cols=FEATURES_18, k=1,
            val_end_mode=v_end, refit_end_mode=r_end, val_criterion=v_crit, seed=7
        )
        sub = D_pred[(D_pred.t.dt.year >= 2015) & (D_pred.t.dt.year <= 2026)].copy()
        W = cleanroom_topk_weights(sub, "score", k=1)
        led = cleanroom_run_portfolio(W, px_eng, rf).loc["2015-01-31":"2026-09-30"]
        ledgers[m_name] = led
        preds_by_mode[m_name] = sub
        led.to_csv(OUT_DIR / f"ledger__{m_name}.csv")
        for yr, info in f_info.items():
            fold_rows.append({"mode": m_name, **info})

    df_folds = pd.DataFrame(fold_rows)
    df_folds.to_csv(OUT_DIR / "step4_fold_hyperparameter_audit.csv", index=False)

    # Load original target ledger for month-by-month reconciliation
    orig_led = pd.read_csv(ORIG_LEDGER_DIR / "QQQ_Full100__T1_SetA_Price_Only__lgbm__Top1.csv", parse_dates=["month"]).set_index("month")

    # Build top-2 candidate lookup per month for Mode_A1 and Mode_B1
    def top2_lookup(sub_df):
        out = {}
        for t, g in sub_df.dropna(subset=["score"]).groupby("t"):
            s = g.sort_values(["score", "ticker"], ascending=[False, True])
            hm = t + pd.offsets.MonthEnd(1)
            r1 = s.iloc[0]
            r2 = s.iloc[1] if len(s) > 1 else r1
            out[hm] = (r1.ticker, float(r1.score), r2.ticker, float(r2.score), float(r1.score - r2.score))
        return out

    top2_a1 = top2_lookup(preds_by_mode["Mode_A1_HybridRepro_Purged_Nov30"])
    top2_b1 = top2_lookup(preds_by_mode["Mode_B1_PureQQQ_Purged_Nov30"])

    rec_rows = []
    for hm in orig_led.index:
        r_orig = orig_led.loc[hm]
        r_a1 = ledgers["Mode_A1_HybridRepro_Purged_Nov30"].loc[hm]
        r_a2 = ledgers["Mode_A2_HybridRepro_UnpurgedVal_Dec31"].loc[hm]
        r_a3 = ledgers["Mode_A3_HybridRepro_UnpurgedBoth_Dec31"].loc[hm]
        r_b1 = ledgers["Mode_B1_PureQQQ_Purged_Nov30"].loc[hm]
        r_b2 = ledgers["Mode_B2_PureQQQ_FixedNL7"].loc[hm]

        tk_a1, sc1_a1, tk2_a1, sc2_a1, gap_a1 = top2_a1.get(hm, ("", np.nan, "", np.nan, np.nan))
        tk_b1, sc1_b1, tk2_b1, sc2_b1, gap_b1 = top2_b1.get(hm, ("", np.nan, "", np.nan, np.nan))

        match_a1 = (str(r_orig.picks) == str(r_a1.picks)) and (abs(float(r_orig.net) - float(r_a1.net)) < 1e-12)
        match_b1 = (str(r_orig.picks) == str(r_b1.picks))

        explanation = "EXACT_MATCH"
        if not match_a1:
            explanation = f"DIFF_IN_REPRO: orig={r_orig.picks} vs A1={r_a1.picks}"
        elif not match_b1:
            explanation = (
                f"HYBRID_SECTOR_DVR_DIFF: orig/A1 picked {r_a1.picks} (RunnerUp={tk2_a1}, gap={gap_a1:.4f}) "
                f"while PureQQQ B1 picked {r_b1.picks} (RunnerUp={tk2_b1}, gap={gap_b1:.4f}) due to S&P vs QQQ sector_mom/dv_ratio rank shift"
            )

        rec_rows.append({
            "holding_month": hm.strftime("%Y-%m-%d"),
            "formation_month": (hm - pd.offsets.MonthEnd(1)).strftime("%Y-%m-%d"),
            "orig_pick": r_orig.picks,
            "A1_repro_purged_pick": r_a1.picks,
            "A2_unpurged_val_pick": r_a2.picks,
            "A3_unpurged_both_pick": r_a3.picks,
            "B1_pure_qqq_purged_pick": r_b1.picks,
            "B2_pure_qqq_fixed_nl7_pick": r_b2.picks,
            "orig_net": round(float(r_orig.net), 6),
            "A1_repro_purged_net": round(float(r_a1.net), 6),
            "A2_unpurged_val_net": round(float(r_a2.net), 6),
            "A3_unpurged_both_net": round(float(r_a3.net), 6),
            "B1_pure_qqq_purged_net": round(float(r_b1.net), 6),
            "B2_pure_qqq_fixed_nl7_net": round(float(r_b2.net), 6),
            "diff_orig_vs_A1_bps": round(float((r_a1.net - r_orig.net) * 10000), 4),
            "A1_score_top1": round(sc1_a1, 5) if np.isfinite(sc1_a1) else np.nan,
            "A1_runner_up": tk2_a1,
            "A1_score_gap_top1_top2": round(gap_a1, 5) if np.isfinite(gap_a1) else np.nan,
            "exact_match_orig_vs_A1": match_a1,
            "match_orig_vs_B1_pure_qqq": match_b1,
            "reconciliation_explanation": explanation,
        })

    df_rec = pd.DataFrame(rec_rows)
    df_rec.to_csv(OUT_DIR / "step4_month_by_month_reconciliation.csv", index=False)

    # Print summary of CAGRs across all 6 modes for 2019-2026.09 (93m) and 2015-2026.09 (140m)
    print(f"   Exact month-by-month matches (Orig Ledger vs Clean-Room Mode A1): {int(df_rec.exact_match_orig_vs_A1.sum())}/{len(df_rec)}")
    print(f"   Max |net return diff| (Orig vs Mode A1): {df_rec.diff_orig_vs_A1_bps.abs().max():.6f} bps")
    print(f"   Matches (Orig vs Mode A2 Unpurged Val Dec31): {int((df_rec.orig_pick == df_rec.A2_unpurged_val_pick).sum())}/{len(df_rec)}")
    print(f"   Matches (Orig vs Mode A3 Unpurged Val+Refit Dec31): {int((df_rec.orig_pick == df_rec.A3_unpurged_both_pick).sum())}/{len(df_rec)}")
    print(f"   Matches (Orig vs Mode B1 Pure Standalone QQQ): {int(df_rec.match_orig_vs_B1_pure_qqq.sum())}/{len(df_rec)}")

    print("\n   CAGR Comparison Across Modes:")
    for label, led in [("Original_Reported_Ledger", orig_led)] + list(ledgers.items()):
        r19 = led.loc["2019-01-31":"2026-09-30"].net
        r15 = led.loc["2015-01-31":"2026-09-30"].net
        c19 = float((1.0 + r19).prod() ** (12.0 / len(r19)) - 1.0) * 100
        c15 = float((1.0 + r15).prod() ** (12.0 / len(r15)) - 1.0) * 100
        print(f"   - {label:38s}: 2019-2026.09 ({len(r19)}m) CAGR = {c19:6.2f}% | 2015-2026.09 ({len(r15)}m) CAGR = {c15:6.2f}%")


if __name__ == "__main__":
    main()
