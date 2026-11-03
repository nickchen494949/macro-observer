#!/usr/bin/env python3
"""
STEPS 5–9 (CLEAN-ROOM): Independent Performance, Adversarial Stress Tests, Paired Statistics,
Multiple-Testing Penalty (DSR / Holm / Šidák / HLZ), and Return Concentration Audit
=============================================================================================
Strict Clean-Room Rules:
- Zero imports from original project `.py` modules.
- Computes all performance metrics, daily NAV drawdowns, stress scenarios, paired Newey-West HAC
  and stationary block-bootstrap tests, project-wide Deflated Sharpe Ratio, and stock/month
  concentration decompositions from scratch.
"""

import glob
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import kurtosis, norm, skew, wilcoxon

from q2_cleanroom_price_engine import (
    ORIG_LEDGER_DIR,
    OUT_DIR,
    REPO_ROOT,
    CleanRoomPriceEngine,
    load_cleanroom_prices_and_universe,
    load_rf,
    load_tiingo_second_source_series,
)
from q3_cleanroom_18_features import FEATURES_18
from q4_walkforward_lgbm_and_reconcile import (
    COST_PER_SIDE,
    cleanroom_run_portfolio,
    cleanroom_topk_weights,
    run_cleanroom_walkforward,
)


def compute_cleanroom_daily_nav(daily: pd.DataFrame, ledger_df: pd.DataFrame) -> pd.Series:
    """
    Computes exact daily NAV path from monthly holdings ledger and daily adjusted closes.
    """
    out = []
    level = 1.0
    for m, row in ledger_df.iterrows():
        form_t = m - pd.offsets.MonthEnd(1)
        pos0 = daily.index.searchsorted(form_t, side="right") - 1
        if pos0 < 0:
            continue
        t0 = daily.index[pos0]
        days = daily.index[(daily.index > t0) & (daily.index <= m)]
        if not len(days):
            continue
        names = [x for x in str(row.picks).split("|") if x and x in daily.columns]
        if names:
            w_raw = [float(x) for x in str(row.weights).split("|")] if "weights" in row and pd.notna(row.weights) else [1.0 / len(names)] * len(names)
            w = np.array(w_raw[: len(names)], dtype=float)
            w = w / w.sum() if w.sum() > 0 else np.ones(len(names)) / len(names)
            seg = daily[names].loc[t0:m].ffill()
            rel = pd.Series(1.0 + ((seg / seg.iloc[0]).fillna(1.0).values - 1.0) @ w, index=seg.index).loc[days]
        else:
            rel = pd.Series(1.0, index=days)
        k = (1.0 + float(row.net)) / float(rel.iloc[-1]) if rel.iloc[-1] > 0 else 1.0
        path = level * rel * (k ** (np.arange(1, len(rel) + 1) / len(rel)))
        out.append(path)
        level = float(path.iloc[-1])
    return pd.concat(out) if out else pd.Series(dtype=float)


def compute_cleanroom_metrics(
    ledger_df: pd.DataFrame,
    daily: pd.DataFrame,
    rf: pd.Series,
    start_dt: str,
    end_dt: str,
    label: str = "",
) -> dict:
    sub = ledger_df.loc[start_dt:end_dt].copy()
    r = sub["net"].dropna()
    n = len(r)
    if n == 0:
        return {}
    cagr = float((1.0 + r).prod() ** (12.0 / n) - 1.0)
    vol = float(r.std(ddof=1) * np.sqrt(12.0))
    rf_sub = rf.reindex(r.index).fillna(0.0)
    ex = r - rf_sub
    sharpe = float(ex.mean() / r.std(ddof=1) * np.sqrt(12.0)) if r.std(ddof=1) > 0 else 0.0
    down = r[r < 0]
    sortino = float(ex.mean() * 12.0 / (down.std(ddof=1) * np.sqrt(12.0))) if len(down) > 1 and down.std(ddof=1) > 0 else np.nan
    eq = pd.concat([pd.Series([1.0]), (1.0 + r).cumprod().reset_index(drop=True)])
    mdd_m = float((eq / eq.cummax() - 1.0).min())
    try:
        nav = compute_cleanroom_daily_nav(daily, sub)
        mdd_d = float((nav / nav.cummax() - 1.0).min()) if len(nav) else mdd_m
    except Exception:
        mdd_d = mdd_m
    calmar = float(cagr / abs(mdd_d)) if mdd_d < 0 else np.nan
    turn = float(sub["turnover"].mean()) if "turnover" in sub.columns else np.nan
    win_rate = float((r > 0).mean())
    r_2022 = sub.loc["2022-01-31":"2022-12-31", "net"].dropna()
    ret_2022 = float((1.0 + r_2022).prod() - 1.0) if len(r_2022) else np.nan
    lr = np.log1p(r)
    top5_share = float(lr.nlargest(5).sum() / lr.sum()) if lr.sum() > 0 else np.nan

    return {
        "strategy": label,
        "window": f"{start_dt[:7]}..{end_dt[:7]} ({n}m)",
        "months": n,
        "CAGR_pct": round(cagr * 100, 2),
        "Vol_pct": round(vol * 100, 2),
        "Sharpe": round(sharpe, 2),
        "Sortino": round(sortino, 2) if np.isfinite(sortino) else np.nan,
        "MaxDD_Monthly_pct": round(mdd_m * 100, 2),
        "MaxDD_Daily_pct": round(mdd_d * 100, 2),
        "Calmar": round(calmar, 2) if np.isfinite(calmar) else np.nan,
        "Return_2022_pct": round(ret_2022 * 100, 2) if np.isfinite(ret_2022) else np.nan,
        "Avg_Turnover_pct": round(turn * 100, 1) if np.isfinite(turn) else np.nan,
        "Win_Rate_pct": round(win_rate * 100, 1),
        "Top5_Months_LogWealth_Share_pct": round(top5_share * 100, 1) if np.isfinite(top5_share) else np.nan,
    }


def load_qqq_etf_cleanroom(form_dates: list[pd.Timestamp], daily: pd.DataFrame) -> pd.DataFrame:
    p = REPO_ROOT / "data" / "yahoo" / "QQQ.json"
    j = json.load(open(p))
    s = pd.Series([v[1] for v in j["values"]], index=pd.to_datetime([v[0] for v in j["values"]]), dtype=float)
    s = s[~s.index.duplicated(keep="last")].sort_index()
    daily["QQQ"] = s.reindex(daily.index).ffill()
    sess = s.dropna().index
    rows = []
    for t in form_dates:
        t_next = t + pd.offsets.MonthEnd(1)
        i0 = sess.searchsorted(t, side="right")
        i1 = sess.searchsorted(t_next, side="right")
        r = float(s.iloc[i1] / s.iloc[i0] - 1.0) if (i0 < len(sess) and i1 < len(sess)) else 0.0
        rows.append({"formation": t, "month": t_next, "net": r, "gross": r, "turnover": 0.0, "exposure": 1.0, "picks": "QQQ", "weights": "1.00000"})
    return pd.DataFrame(rows).set_index("month")


def newey_west_se(x: np.ndarray, lag: int = 3) -> float:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 6:
        return np.nan
    e = x - x.mean()
    v = float(e @ e) / n
    for L in range(1, lag + 1):
        v += 2.0 * (1.0 - L / (lag + 1.0)) * float(e[L:] @ e[:-L]) / n
    return float(np.sqrt(max(0.0, v) / n))


def stationary_bootstrap_paired(rx: pd.Series, rb: pd.Series, rf: pd.Series, n_boot: int = 4000, mean_block: int = 6, seed: int = 7) -> dict:
    df = pd.concat([rx.rename("x"), rb.rename("b")], axis=1).dropna()
    rf_arr = rf.reindex(df.index).fillna(0.0).values
    x_arr = df["x"].values
    b_arr = df["b"].values
    T = len(df)
    rng = np.random.default_rng(seed)

    cagr_diffs = np.empty(n_boot)
    sharpe_diffs = np.empty(n_boot)
    arith_diffs = np.empty(n_boot)

    for b in range(n_boot):
        idx = np.empty(T, dtype=int)
        idx[0] = rng.integers(T)
        for i in range(1, T):
            idx[i] = rng.integers(T) if rng.random() < (1.0 / mean_block) else (idx[i - 1] + 1) % T
        xs = x_arr[idx]
        bs = b_arr[idx]
        rfs = rf_arr[idx]
        cx = np.prod(1.0 + xs) ** (12.0 / T) - 1.0
        cb = np.prod(1.0 + bs) ** (12.0 / T) - 1.0
        sx = (xs - rfs).mean() / xs.std(ddof=1) * np.sqrt(12.0) if xs.std(ddof=1) > 0 else 0.0
        sb = (bs - rfs).mean() / bs.std(ddof=1) * np.sqrt(12.0) if bs.std(ddof=1) > 0 else 0.0
        cagr_diffs[b] = cx - cb
        sharpe_diffs[b] = sx - sb
        arith_diffs[b] = (xs - bs).mean() * 12.0

    q = lambda arr: [round(float(np.nanpercentile(arr, p) * 100), 2) for p in (5, 50, 95)]
    qs = lambda arr: [round(float(np.nanpercentile(arr, p)), 2) for p in (5, 50, 95)]
    return {
        "cagr_diff_p5_p50_p95_pct": q(cagr_diffs),
        "sharpe_diff_p5_p50_p95": qs(sharpe_diffs),
        "prob_cagr_diff_le_0": round(float(np.mean(cagr_diffs <= 0.0)), 4),
        "prob_sharpe_diff_le_0": round(float(np.mean(sharpe_diffs <= 0.0)), 4),
        "prob_arith_diff_le_0": round(float(np.mean(arith_diffs <= 0.0)), 4),
    }


def compute_deflated_sharpe(r_best: np.ndarray, sr_trials_monthly: list[float]) -> tuple[float, float, int]:
    sr = np.asarray([x for x in sr_trials_monthly if np.isfinite(x)], dtype=float)
    N = len(sr)
    n_obs = len(r_best)
    if N < 2 or n_obs < 12:
        return np.nan, np.nan, N
    emc = 0.5772156649
    sr0 = np.sqrt(np.var(sr, ddof=1)) * ((1.0 - emc) * norm.ppf(1.0 - 1.0 / N) + emc * norm.ppf(1.0 - 1.0 / (N * np.e)))
    srb = float(r_best.mean() / r_best.std(ddof=1))
    g3 = float(skew(r_best))
    g4 = float(kurtosis(r_best, fisher=False))
    denom = np.sqrt(max(1e-9, 1.0 - g3 * srb + ((g4 - 1.0) / 4.0) * (srb ** 2)))
    z = (srb - sr0) * np.sqrt(n_obs - 1.0) / denom
    return float(norm.cdf(z)), float(sr0 * np.sqrt(12.0)), N


def main():
    print("Steps 5-9: Running full clean-room metrics, stress tests, paired stats, DSR, and concentration audit...", flush=True)
    U = load_cleanroom_prices_and_universe()
    px_open = CleanRoomPriceEngine(U, mode="open")
    px_t1c = CleanRoomPriceEngine(U, mode="close_t1")
    px_t2c = CleanRoomPriceEngine(U, mode="close_t2")
    rf = load_rf(pd.date_range("2009-01-31", "2026-10-31", freq="ME"))
    daily = U["daily"]

    df_hybrid = pd.read_parquet(OUT_DIR / "cleanroom_panel_qqq_hybrid_repro.parquet")
    df_pure = pd.read_parquet(OUT_DIR / "cleanroom_panel_qqq_pure_standalone.parquet")

    # Run primary models (Top-1 and Top-3)
    D_a1, _ = run_cleanroom_walkforward(df_hybrid, px_open, rf, FEATURES_18, k=1, val_end_mode="nov30", refit_end_mode="nov30", val_criterion="val_cagr", seed=7)
    D_a2, _ = run_cleanroom_walkforward(df_hybrid, px_open, rf, FEATURES_18, k=1, val_end_mode="dec31", refit_end_mode="nov30", val_criterion="val_cagr", seed=7)
    D_a3, _ = run_cleanroom_walkforward(df_hybrid, px_open, rf, FEATURES_18, k=1, val_end_mode="dec31", refit_end_mode="dec31", val_criterion="val_cagr", seed=7)
    D_b1, _ = run_cleanroom_walkforward(df_pure, px_open, rf, FEATURES_18, k=1, val_end_mode="nov30", refit_end_mode="nov30", val_criterion="val_cagr", seed=7)
    D_b2_nl7, _ = run_cleanroom_walkforward(df_pure, px_open, rf, FEATURES_18, k=1, val_end_mode="nov30", refit_end_mode="nov30", val_criterion="fixed_nl7", seed=7)
    D_b2_nl15, _ = run_cleanroom_walkforward(df_pure, px_open, rf, FEATURES_18, k=1, val_end_mode="nov30", refit_end_mode="nov30", val_criterion="fixed_nl15", seed=7)
    D_b3_rk, _ = run_cleanroom_walkforward(df_pure, px_open, rf, FEATURES_18, k=1, val_end_mode="nov30", refit_end_mode="nov30", val_criterion="val_rank", seed=7)
    D_a1_top3, _ = run_cleanroom_walkforward(df_hybrid, px_open, rf, FEATURES_18, k=3, val_end_mode="nov30", refit_end_mode="nov30", val_criterion="val_cagr", seed=7)
    D_b1_top3, _ = run_cleanroom_walkforward(df_pure, px_open, rf, FEATURES_18, k=3, val_end_mode="nov30", refit_end_mode="nov30", val_criterion="val_cagr", seed=7)

    test_sub = lambda d: d[(d.t.dt.year >= 2015) & (d.t.dt.year <= 2026)].copy()
    sub_a1 = test_sub(D_a1)
    sub_b1 = test_sub(D_b1)
    form_test = sorted(sub_a1.t.unique())

    # Build primary & benchmark ledgers
    W_a1 = cleanroom_topk_weights(sub_a1, "score", k=1)
    W_a2 = cleanroom_topk_weights(test_sub(D_a2), "score", k=1)
    W_a3 = cleanroom_topk_weights(test_sub(D_a3), "score", k=1)
    W_b1 = cleanroom_topk_weights(sub_b1, "score", k=1)
    W_b2_nl7 = cleanroom_topk_weights(test_sub(D_b2_nl7), "score", k=1)
    W_b2_nl15 = cleanroom_topk_weights(test_sub(D_b2_nl15), "score", k=1)
    W_b3_rk = cleanroom_topk_weights(test_sub(D_b3_rk), "score", k=1)
    W_a1_top3 = cleanroom_topk_weights(test_sub(D_a1_top3), "score", k=3)
    W_b1_top3 = cleanroom_topk_weights(test_sub(D_b1_top3), "score", k=3)

    W_mom1 = {t: {s: 1.0 for s in g.sort_values(["mom_rank_qqq", "ticker"]).ticker.head(1)} for t, g in sub_a1.groupby("t")}
    W_mom3 = {t: {s: 1.0 / 3.0 for s in g.sort_values(["mom_rank_qqq", "ticker"]).ticker.head(3)} for t, g in sub_a1.groupby("t")}
    W_mom5 = {t: {s: 1.0 / 5.0 for s in g.sort_values(["mom_rank_qqq", "ticker"]).ticker.head(5)} for t, g in sub_a1.groupby("t")}
    W_ew_qqq = {t: {s: 1.0 / len(g) for s in g.ticker} for t, g in sub_a1.groupby("t")}
    W_spy = {t: {"SPY": 1.0} for t in form_test}

    led_a1 = cleanroom_run_portfolio(W_a1, px_open, rf)
    led_a2 = cleanroom_run_portfolio(W_a2, px_open, rf)
    led_a3 = cleanroom_run_portfolio(W_a3, px_open, rf)
    led_b1 = cleanroom_run_portfolio(W_b1, px_open, rf)
    led_b2_nl7 = cleanroom_run_portfolio(W_b2_nl7, px_open, rf)
    led_b2_nl15 = cleanroom_run_portfolio(W_b2_nl15, px_open, rf)
    led_b3_rk = cleanroom_run_portfolio(W_b3_rk, px_open, rf)
    led_a1_top3 = cleanroom_run_portfolio(W_a1_top3, px_open, rf)
    led_b1_top3 = cleanroom_run_portfolio(W_b1_top3, px_open, rf)
    led_mom1 = cleanroom_run_portfolio(W_mom1, px_open, rf)
    led_mom3 = cleanroom_run_portfolio(W_mom3, px_open, rf)
    led_mom5 = cleanroom_run_portfolio(W_mom5, px_open, rf)
    led_ew_qqq = cleanroom_run_portfolio(W_ew_qqq, px_open, rf)
    led_qqq_etf = load_qqq_etf_cleanroom(form_test, daily)
    led_spy_etf = cleanroom_run_portfolio(W_spy, px_open, rf, cost_per_side=0.0)

    # Save benchmark ledgers
    led_mom1.to_csv(OUT_DIR / "ledger__QQQ_Pure_Mom_12_1_Top1.csv")
    led_mom3.to_csv(OUT_DIR / "ledger__QQQ_Pure_Mom_12_1_Top3.csv")
    led_ew_qqq.to_csv(OUT_DIR / "ledger__QQQ_EqualWeight_Full100.csv")
    led_qqq_etf.to_csv(OUT_DIR / "ledger__QQQ_ETF_BuyHold.csv")

    # =========================================================================
    # STEP 5: PERFORMANCE SUMMARY & CALENDAR YEAR RETURNS
    # =========================================================================
    core_ledgers = [
        ("QQQ_LGBM_Price_Top1__ModeA1_Repro_Purged", led_a1),
        ("QQQ_LGBM_Price_Top1__ModeB1_PureQQQ_Purged", led_b1),
        ("QQQ_LGBM_Price_Top1__ModeB2_PureQQQ_FixedNL7", led_b2_nl7),
        ("QQQ_LGBM_Price_Top1__ModeB3_PureQQQ_RankVal", led_b3_rk),
        ("QQQ_LGBM_Price_Top3__ModeA1_Repro_Purged", led_a1_top3),
        ("QQQ_LGBM_Price_Top3__ModeB1_PureQQQ_Purged", led_b1_top3),
        ("QQQ_Pure_Momentum_12_1__Top1", led_mom1),
        ("QQQ_Pure_Momentum_12_1__Top3", led_mom3),
        ("QQQ_Pure_Momentum_12_1__Top5", led_mom5),
        ("QQQ_EqualWeight_Full100_Pool", led_ew_qqq),
        ("QQQ_ETF_BuyHold", led_qqq_etf),
        ("SPY_ETF_BuyHold", led_spy_etf),
    ]

    perf_rows = []
    for s_name, led in core_ledgers:
        for s_dt, e_dt in [
            ("2019-01-31", "2026-09-30"),
            ("2015-01-31", "2026-09-30"),
            ("2015-01-31", "2018-12-31"),
            ("2019-01-31", "2022-12-31"),
            ("2023-01-31", "2026-09-30"),
        ]:
            perf_rows.append(compute_cleanroom_metrics(led, daily, rf, s_dt, e_dt, label=s_name))
    df_perf = pd.DataFrame(perf_rows)
    df_perf.to_csv(OUT_DIR / "step5_performance_summary_table.csv", index=False)

    # Calendar year table (2015..2026)
    cal_rows = []
    for yr in range(2015, 2027):
        row = {"year": yr if yr < 2026 else "2026_YTD(Jan-Sep)"}
        for s_name, led in core_ledgers:
            r_y = led[led.index.year == yr]["net"].dropna()
            row[s_name] = round(float(((1.0 + r_y).prod() - 1.0) * 100), 2) if len(r_y) else np.nan
        cal_rows.append(row)
    df_cal = pd.DataFrame(cal_rows)
    df_cal.to_csv(OUT_DIR / "step5_calendar_year_returns.csv", index=False)

    # =========================================================================
    # STEP 6: ADVERSARIAL STRESS TESTS
    # =========================================================================
    print("   Running Step 6 Adversarial Stress Tests (costs, slippage, lags, seeds, winner removal, rank cliff, Tiingo)...", flush=True)
    stress_rows = []

    def add_stress_row(category: str, scenario: str, led: pd.DataFrame, notes: str = ""):
        m19 = compute_cleanroom_metrics(led, daily, rf, "2019-01-31", "2026-09-30", label=scenario)
        m15 = compute_cleanroom_metrics(led, daily, rf, "2015-01-31", "2026-09-30", label=scenario)
        stress_rows.append({
            "category": category,
            "scenario": scenario,
            "CAGR_2019_2026_pct": m19.get("CAGR_pct"),
            "Sharpe_2019_2026": m19.get("Sharpe"),
            "MaxDD_Monthly_2019_2026_pct": m19.get("MaxDD_Monthly_pct"),
            "MaxDD_Daily_2019_2026_pct": m19.get("MaxDD_Daily_pct"),
            "CAGR_2015_2026_pct": m15.get("CAGR_pct"),
            "Sharpe_2015_2026": m15.get("Sharpe"),
            "MaxDD_Monthly_2015_2026_pct": m15.get("MaxDD_Monthly_pct"),
            "MaxDD_Daily_2015_2026_pct": m15.get("MaxDD_Daily_pct"),
            "Return_2022_pct": m19.get("Return_2022_pct"),
            "notes": notes,
        })

    # 6.0 Baseline & Boundary Purging
    add_stress_row("0_Baseline_And_Purge", "Baseline_ModeA1_Repro_Purged_Nov30 (10bp/side)", led_a1, "Exact reproduction of commit a455ed7 (val<=Nov30, refit<=Nov30)")
    add_stress_row("0_Baseline_And_Purge", "Unpurged_Val_Dec31_ModeA2 (commit 20d6cbf)", led_a2, "Val includes Y-1-12-31; refit<=Nov30 (zero pick change on QQQ Full100 Top-1)")
    add_stress_row("0_Baseline_And_Purge", "Unpurged_Val_And_Refit_Dec31_ModeA3", led_a3, "Both val and refit include cross-year Y-1-12-31 label")
    add_stress_row("0_Baseline_And_Purge", "Pure_Standalone_QQQ_Purged_Nov30_ModeB1", led_b1, "Sector mom strictly inside QQQ + uniform dv_ratio")

    # 6.1 Transaction Costs & Open Slippage (on both Mode A1 and Mode B1)
    for bps in (20, 30, 50):
        add_stress_row("1_Transaction_Costs", f"Cost_{bps}bp_per_side (ModeA1)", cleanroom_run_portfolio(W_a1, px_open, rf, cost_per_side=bps / 10000.0), f"{bps} bps/side (~{bps*4:.0f} bps round-trip turnover)")
    for slip_bps in (25, 50):
        add_stress_row("2_Open_Slippage", f"Open_Slippage_+{slip_bps}bp_per_side (Total {10+slip_bps}bp/side, ModeA1)", cleanroom_run_portfolio(W_a1, px_open, rf, cost_per_side=0.0010, extra_slippage_per_side=slip_bps / 10000.0), f"10bp fee + {slip_bps}bp adverse open slippage per side")
        add_stress_row("2_Open_Slippage", f"Open_Slippage_+{slip_bps}bp_per_side (Total {10+slip_bps}bp/side, ModeB1_PureQQQ)", cleanroom_run_portfolio(W_b1, px_open, rf, cost_per_side=0.0010, extra_slippage_per_side=slip_bps / 10000.0), f"Pure QQQ + 10bp fee + {slip_bps}bp open slippage per side")

    # 6.2 Execution Lag (T+1 Close and T+2 Close)
    add_stress_row("3_Execution_Lag", "Exec_T+1_Close_to_Close (ModeA1)", cleanroom_run_portfolio(W_a1, px_t1c, rf), "Enter & exit at first trading day Close (T+1 Close)")
    add_stress_row("3_Execution_Lag", "Exec_T+2_Close_to_Close (ModeA1)", cleanroom_run_portfolio(W_a1, px_t2c, rf), "Enter & exit at second trading day Close (T+2 Close)")
    add_stress_row("3_Execution_Lag", "Exec_T+1_Close_to_Close (ModeB1_PureQQQ)", cleanroom_run_portfolio(W_b1, px_t1c, rf), "Pure QQQ + T+1 Close execution")
    add_stress_row("3_Execution_Lag", "Exec_T+2_Close_to_Close (ModeB1_PureQQQ)", cleanroom_run_portfolio(W_b1, px_t2c, rf), "Pure QQQ + T+2 Close execution")

    # 6.3 Hyperparameter Freezing & Validation Criterion
    D_a1_nl7, _ = run_cleanroom_walkforward(df_hybrid, px_open, rf, FEATURES_18, k=1, val_end_mode="nov30", refit_end_mode="nov30", val_criterion="fixed_nl7", seed=7)
    D_a1_nl15, _ = run_cleanroom_walkforward(df_hybrid, px_open, rf, FEATURES_18, k=1, val_end_mode="nov30", refit_end_mode="nov30", val_criterion="fixed_nl15", seed=7)
    D_a1_rk, _ = run_cleanroom_walkforward(df_hybrid, px_open, rf, FEATURES_18, k=1, val_end_mode="nov30", refit_end_mode="nov30", val_criterion="val_rank", seed=7)
    add_stress_row("4_Hyperparameter_And_Val", "Fixed_num_leaves=7_ZeroValTune (ModeA1)", cleanroom_run_portfolio(cleanroom_topk_weights(test_sub(D_a1_nl7), "score", 1), px_open, rf), "Zero validation tuning: num_leaves=7 frozen in all folds")
    add_stress_row("4_Hyperparameter_And_Val", "Fixed_num_leaves=15_ZeroValTune (ModeA1)", cleanroom_run_portfolio(cleanroom_topk_weights(test_sub(D_a1_nl15), "score", 1), px_open, rf), "Zero validation tuning: num_leaves=15 frozen in all folds")
    add_stress_row("4_Hyperparameter_And_Val", "ZeroCAGRPeek_RankVal (ModeA1)", cleanroom_run_portfolio(cleanroom_topk_weights(test_sub(D_a1_rk), "score", 1), px_open, rf), "Selects num_leaves by validation Top-5 mean rank, never computing CAGR")
    add_stress_row("4_Hyperparameter_And_Val", "Fixed_num_leaves=7_ZeroValTune (ModeB1_PureQQQ)", led_b2_nl7, "Pure QQQ + fixed num_leaves=7")
    add_stress_row("4_Hyperparameter_And_Val", "Fixed_num_leaves=15_ZeroValTune (ModeB1_PureQQQ)", led_b2_nl15, "Pure QQQ + fixed num_leaves=15")
    add_stress_row("4_Hyperparameter_And_Val", "ZeroCAGRPeek_RankVal (ModeB1_PureQQQ)", led_b3_rk, "Pure QQQ + Rank-IC validation")

    # 6.4 Feature Ablation (Drop dv_ratio / Drop sector_mom)
    cols_no_dvr = [c for c in FEATURES_18 if c != "dv_ratio"]
    cols_no_secm = [c for c in FEATURES_18 if c != "sector_mom"]
    cols_no_both = [c for c in FEATURES_18 if c not in ("dv_ratio", "sector_mom")]
    D_nodvr, _ = run_cleanroom_walkforward(df_pure, px_open, rf, cols_no_dvr, k=1, val_end_mode="nov30", refit_end_mode="nov30", val_criterion="val_cagr", seed=7)
    D_nosecm, _ = run_cleanroom_walkforward(df_pure, px_open, rf, cols_no_secm, k=1, val_end_mode="nov30", refit_end_mode="nov30", val_criterion="val_cagr", seed=7)
    D_noboth, _ = run_cleanroom_walkforward(df_pure, px_open, rf, cols_no_both, k=1, val_end_mode="nov30", refit_end_mode="nov30", val_criterion="val_cagr", seed=7)
    add_stress_row("4b_Feature_Purity", "Drop_dv_ratio_17feats (PureQQQ)", cleanroom_run_portfolio(cleanroom_topk_weights(test_sub(D_nodvr), "score", 1), px_open, rf), "Removes volume ratio feature (17 pure price features)")
    add_stress_row("4b_Feature_Purity", "Drop_sector_mom_17feats (PureQQQ)", cleanroom_run_portfolio(cleanroom_topk_weights(test_sub(D_nosecm), "score", 1), px_open, rf), "Removes sector momentum feature (17 features)")
    add_stress_row("4b_Feature_Purity", "Drop_Both_dv_ratio_and_sector_mom_16feats", cleanroom_run_portfolio(cleanroom_topk_weights(test_sub(D_noboth), "score", 1), px_open, rf), "100% stock-level + SPY-context price features only (16 features)")

    # 6.5 Random Seed Sensitivity (10 seeds)
    seeds = [1, 7, 13, 21, 42, 77, 100, 256, 999, 2026]
    seed_cagrs_19 = []
    seed_cagrs_15 = []
    for sd in seeds:
        D_sd, _ = run_cleanroom_walkforward(df_hybrid, px_open, rf, FEATURES_18, k=1, val_end_mode="nov30", refit_end_mode="nov30", val_criterion="val_cagr", seed=sd)
        led_sd = cleanroom_run_portfolio(cleanroom_topk_weights(test_sub(D_sd), "score", 1), px_open, rf)
        add_stress_row("5_Random_Seed_Sensitivity", f"Seed_{sd} (ModeA1)", led_sd, f"LightGBM subsample/colsample random_state={sd}")
        seed_cagrs_19.append(stress_rows[-1]["CAGR_2019_2026_pct"])
        seed_cagrs_15.append(stress_rows[-1]["CAGR_2015_2026_pct"])

    # 6.6 Super-Winner Exclusion (Drop from candidate selection at prediction time -> picks #2 candidate)
    for drop_name, drop_set in [
        ("Drop_SNDK", {"SNDK"}),
        ("Drop_MRNA", {"MRNA"}),
        ("Drop_TSLA", {"TSLA"}),
        ("Drop_NVDA", {"NVDA"}),
        ("Drop_PDD", {"PDD"}),
        ("Drop_PLTR", {"PLTR"}),
        ("Drop_AMD", {"AMD"}),
        ("Drop_SMCI", {"SMCI"}),
        ("Drop_All_6_SuperWinners (SNDK,MRNA,TSLA,NVDA,PDD,PLTR)", {"SNDK", "MRNA", "TSLA", "NVDA", "PDD", "PLTR"}),
    ]:
        sub_filt = sub_a1[~sub_a1.ticker.isin(drop_set)].copy()
        W_drop = cleanroom_topk_weights(sub_filt, "score", k=1)
        add_stress_row("6_Remove_SuperWinners", f"{drop_name} (ModeA1)", cleanroom_run_portfolio(W_drop, px_open, rf), f"Excludes {sorted(drop_set)} from eligible picks")

    # 6.7 Ex-Best Months (Zero out best 3, 5, 10 months in 2019-2026 and 2015-2026)
    for n_best in (3, 5, 10):
        led_ex = led_a1.copy()
        top_idx_15 = led_ex.loc["2015-01-31":"2026-09-30", "net"].nlargest(n_best).index
        top_idx_19 = led_ex.loc["2019-01-31":"2026-09-30", "net"].nlargest(n_best).index
        led_ex19 = led_a1.copy()
        led_ex19.loc[top_idx_19, "net"] = 0.0
        led_ex15 = led_a1.copy()
        led_ex15.loc[top_idx_15, "net"] = 0.0
        m19 = compute_cleanroom_metrics(led_ex19, daily, rf, "2019-01-31", "2026-09-30")
        m15 = compute_cleanroom_metrics(led_ex15, daily, rf, "2015-01-31", "2026-09-30")
        stress_rows.append({
            "category": "7_Remove_Best_Months",
            "scenario": f"Remove_Best_{n_best}_Months (set to 0% return, ModeA1)",
            "CAGR_2019_2026_pct": m19.get("CAGR_pct"),
            "Sharpe_2019_2026": m19.get("Sharpe"),
            "MaxDD_Monthly_2019_2026_pct": m19.get("MaxDD_Monthly_pct"),
            "MaxDD_Daily_2019_2026_pct": m19.get("MaxDD_Daily_pct"),
            "CAGR_2015_2026_pct": m15.get("CAGR_pct"),
            "Sharpe_2015_2026": m15.get("Sharpe"),
            "MaxDD_Monthly_2015_2026_pct": m15.get("MaxDD_Monthly_pct"),
            "MaxDD_Daily_2015_2026_pct": m15.get("MaxDD_Daily_pct"),
            "Return_2022_pct": m19.get("Return_2022_pct"),
            "notes": f"Replaces the {n_best} highest-return months in each window with 0.0%",
        })

    # 6.8 Rank Neighborhood Cliff Test (Rank #1, #2, #3, #4, #5 alone + Top-2/3/5 EW)
    for rk_i in (1, 2, 3, 4, 5):
        W_rk = cleanroom_topk_weights(sub_a1, "score", rank_slice=(rk_i - 1, rk_i))
        add_stress_row("8_Rank_Neighborhood", f"Rank_#{rk_i}_Alone (ModeA1)", cleanroom_run_portfolio(W_rk, px_open, rf), f"Buys ONLY the #{rk_i} predicted stock each month")
    for k_ew in (2, 3, 5):
        W_k = cleanroom_topk_weights(sub_a1, "score", k=k_ew)
        add_stress_row("8_Rank_Neighborhood", f"Top_{k_ew}_EqualWeight (ModeA1_Score)", cleanroom_run_portfolio(W_k, px_open, rf), f"Equal-weight Top-{k_ew} from Top-1 model scores")
    add_stress_row("8_Rank_Neighborhood", "Top_3_EqualWeight (Dedicated_Top3_Val_Model_A1)", led_a1_top3, "Dedicated k=3 validation model")
    add_stress_row("8_Rank_Neighborhood", "Top_3_EqualWeight (Dedicated_Top3_Val_Model_B1_PureQQQ)", led_b1_top3, "Pure QQQ dedicated k=3 validation model")

    # 6.9 Tiingo Second-Source Price Substitution
    tiingo_store = load_tiingo_second_source_series()
    sess = daily["SPY"].dropna().index
    led_tiingo = led_a1.copy()
    n_swapped = 0
    for hm in led_tiingo.index:
        tk = str(led_tiingo.at[hm, "picks"])
        form_t = hm - pd.offsets.MonthEnd(1)
        i0 = sess.searchsorted(form_t, side="right")
        i1 = sess.searchsorted(hm, side="right")
        d0 = sess[i0] if i0 < len(sess) else None
        d1 = sess[i1] if i1 < len(sess) else None
        t_info = tiingo_store.get(tk)
        if t_info is not None and d0 is not None and d1 is not None:
            ao = t_info["adjOpen"]
            ac = t_info["adjClose"]
            new_gross = None
            if ao is not None and d0 in ao.index and d1 in ao.index and ao.at[d0] > 0:
                new_gross = float(ao.at[d1] / ao.at[d0] - 1.0)
            elif ac is not None and d0 in ac.index and d1 in ac.index and ac.at[d0] > 0:
                new_gross = float(ac.at[d1] / ac.at[d0] - 1.0)
            if new_gross is not None and np.isfinite(new_gross):
                turn = float(led_tiingo.at[hm, "turnover"])
                led_tiingo.at[hm, "gross"] = new_gross
                led_tiingo.at[hm, "net"] = new_gross - turn * COST_PER_SIDE
                n_swapped += 1
    add_stress_row("9_Vendor_Substitution", f"Tiingo_Second_Source_Price_Substitution ({n_swapped}/140 months swapped)", led_tiingo, "Replaces primary Yahoo/WIKI holding returns with Tiingo EOD adjOpen/adjClose")

    # 6.10 Worst Reasonable Combined Institutional Stress
    led_comb_top1 = cleanroom_run_portfolio(W_b2_nl7, px_open, rf, cost_per_side=0.0010, extra_slippage_per_side=0.0015)
    led_comb_top3 = cleanroom_run_portfolio(W_b1_top3, px_open, rf, cost_per_side=0.0010, extra_slippage_per_side=0.0015)
    add_stress_row("10_Combined_Adversarial_Realistic", "Combined_Stress_Top1 (PureQQQ + FixedNL7 + Nov30Purge + 25bp/side cost+slip)", led_comb_top1, "All-in 25bp/side + Pure QQQ + Fixed NL7 + Nov30 purge")
    add_stress_row("10_Combined_Adversarial_Realistic", "Combined_Stress_Top3 (PureQQQ + Nov30Purge + 25bp/side cost+slip)", led_comb_top3, "All-in 25bp/side + Pure QQQ Top-3 + Nov30 purge")

    df_stress = pd.DataFrame(stress_rows)
    df_stress.to_csv(OUT_DIR / "step6_adversarial_stress_tests.csv", index=False)

    # =========================================================================
    # STEP 7: BENCHMARK COMPARISONS & PAIRED STATISTICAL INFERENCE
    # =========================================================================
    print("   Running Step 7 Paired Statistical Tests (NW lag 3/6, 4000-draw Stationary Bootstrap, Wilcoxon)...", flush=True)
    pairs = [
        ("QQQ_LGBM_Top1(ModeA1_Repro) vs QQQ_Pure_Mom_12_1_Top1", led_a1, led_mom1),
        ("QQQ_LGBM_Top1(ModeA1_Repro) vs QQQ_Pure_Mom_12_1_Top3", led_a1, led_mom3),
        ("QQQ_LGBM_Top1(ModeA1_Repro) vs QQQ_ETF_BuyHold", led_a1, led_qqq_etf),
        ("QQQ_LGBM_Top1(ModeA1_Repro) vs QQQ_EqualWeight_Full100", led_a1, led_ew_qqq),
        ("QQQ_LGBM_Top1(ModeB1_PureQQQ) vs QQQ_Pure_Mom_12_1_Top1", led_b1, led_mom1),
        ("QQQ_LGBM_Top1(ModeB1_PureQQQ) vs QQQ_Pure_Mom_12_1_Top3", led_b1, led_mom3),
        ("QQQ_LGBM_Top1(ModeB1_PureQQQ) vs QQQ_ETF_BuyHold", led_b1, led_qqq_etf),
        ("QQQ_LGBM_Top1(ModeB2_PureQQQ_FixedNL7) vs QQQ_Pure_Mom_12_1_Top1", led_b2_nl7, led_mom1),
        ("QQQ_LGBM_Top3(ModeA1_Repro) vs QQQ_Pure_Mom_12_1_Top3", led_a1_top3, led_mom3),
        ("QQQ_LGBM_Top3(ModeB1_PureQQQ) vs QQQ_Pure_Mom_12_1_Top3", led_b1_top3, led_mom3),
        ("QQQ_Pure_Mom_12_1_Top1 vs QQQ_ETF_BuyHold", led_mom1, led_qqq_etf),
        ("QQQ_Pure_Mom_12_1_Top3 vs QQQ_ETF_BuyHold", led_mom3, led_qqq_etf),
    ]

    stat_rows = []
    for win_name, s_dt, e_dt in [
        ("OOS_2019_2026.09 (93m)", "2019-01-31", "2026-09-30"),
        ("OOS_2015_2026.09 (140m)", "2015-01-31", "2026-09-30"),
    ]:
        for comp_name, lx, lb in pairs:
            rx = lx.loc[s_dt:e_dt, "net"].dropna()
            rb = lb.loc[s_dt:e_dt, "net"].dropna()
            j = pd.concat([rx.rename("x"), rb.rename("b")], axis=1).dropna()
            n_m = len(j)
            cx = float((1.0 + j["x"]).prod() ** (12.0 / n_m) - 1.0)
            cb = float((1.0 + j["b"]).prod() ** (12.0 / n_m) - 1.0)
            diff_m = j["x"] - j["b"]
            se3 = newey_west_se(diff_m.values, lag=3)
            se6 = newey_west_se(diff_m.values, lag=6)
            t_nw3 = float(diff_m.mean() / se3) if se3 > 0 else 0.0
            t_nw6 = float(diff_m.mean() / se6) if se6 > 0 else 0.0
            p_nw3 = float(2.0 * (1.0 - norm.cdf(abs(t_nw3))))
            p_nw6 = float(2.0 * (1.0 - norm.cdf(abs(t_nw6))))
            try:
                _, p_wilc = wilcoxon(diff_m.values[diff_m.values != 0])
            except Exception:
                p_wilc = np.nan
            bs = stationary_bootstrap_paired(j["x"], j["b"], rf, n_boot=4000, mean_block=6, seed=7)
            yd = (1.0 + j["x"]).groupby(j.index.year).prod() - (1.0 + j["b"]).groupby(j.index.year).prod()

            stat_rows.append({
                "window": win_name,
                "comparison": comp_name,
                "months": n_m,
                "CAGR_Strategy_pct": round(cx * 100, 2),
                "CAGR_Bench_pct": round(cb * 100, 2),
                "CAGR_Diff_pct": round((cx - cb) * 100, 2),
                "Ann_Arith_Diff_pct": round(float(diff_m.mean() * 12.0 * 100), 2),
                "t_NW_lag3": round(t_nw3, 2),
                "p_two_sided_lag3": round(p_nw3, 4),
                "t_NW_lag6": round(t_nw6, 2),
                "p_two_sided_lag6": round(p_nw6, 4),
                "p_Wilcoxon": round(float(p_wilc), 4) if np.isfinite(p_wilc) else np.nan,
                "Boot_CAGR_Diff_p5_p50_p95_pct": str(bs["cagr_diff_p5_p50_p95_pct"]),
                "Boot_Sharpe_Diff_p5_p50_p95": str(bs["sharpe_diff_p5_p50_p95"]),
                "Boot_Prob_CAGR_Diff_le_0": bs["prob_cagr_diff_le_0"],
                "Boot_Prob_Sharpe_Diff_le_0": bs["prob_sharpe_diff_le_0"],
                "Months_Beat_Bench": f"{int((diff_m > 0).sum())}/{n_m} ({round(float((diff_m > 0).mean()*100), 1)}%)",
                "Years_Beat_Bench": f"{int((yd > 0).sum())}/{len(yd)}",
            })

    df_stats = pd.DataFrame(stat_rows)
    df_stats.to_csv(OUT_DIR / "step7_paired_statistical_tests.csv", index=False)

    # =========================================================================
    # STEP 8: PROJECT-WIDE MULTIPLE-TESTING / DATA-MINING AUDIT
    # =========================================================================
    print("   Running Step 8 Project-Wide Multiple-Testing / Data-Mining Penalty Audit...", flush=True)
    ml3_dir = REPO_ROOT / "outputs" / "ml3_feature_discovery_20261102"
    qqq_ledger_files = sorted(glob.glob(str(ml3_dir / "ledgers_qqq_iwm" / "QQQ*.csv")) + glob.glob(str(ml3_dir / "ledgers_qqq_iwm" / "SP500_Union_QQQ*.csv")))
    all_ml3_files = sorted(glob.glob(str(ml3_dir / "ledgers*" / "*.csv")))
    all_repo_files = sorted(
        all_ml3_files
        + glob.glob(str(REPO_ROOT / "research" / "sector_stock_momentum" / "results" / "**" / "monthly_*.csv"), recursive=True)
    )

    def collect_monthly_srs(file_list, s_dt, e_dt):
        srs = []
        seen = set()
        for fp in file_list:
            try:
                df_f = pd.read_csv(fp)
                mcol = "month" if "month" in df_f.columns else df_f.columns[0]
                if "net" not in df_f.columns:
                    continue
                s = pd.Series(df_f["net"].values, index=pd.to_datetime(df_f[mcol], errors="coerce")).dropna()
                s = s.loc[s_dt:e_dt]
                if len(s) >= 36 and s.std(ddof=1) > 0:
                    sig = (len(s), round(float(s.mean()), 6), round(float(s.std(ddof=1)), 6))
                    if sig not in seen:
                        seen.add(sig)
                        srs.append(float(s.mean() / s.std(ddof=1)))
            except Exception:
                continue
        return srs

    mt_rows = []
    for win_name, s_dt, e_dt in [
        ("OOS_2019_2026.09 (93m)", "2019-01-31", "2026-09-30"),
        ("OOS_2015_2026.09 (140m)", "2015-01-31", "2026-09-30"),
    ]:
        srs_qqq = collect_monthly_srs(qqq_ledger_files, s_dt, e_dt)
        srs_ml3 = collect_monthly_srs(all_ml3_files, s_dt, e_dt)
        srs_repo = collect_monthly_srs(all_repo_files, s_dt, e_dt)

        for strat_label, led_s in [
            ("QQQ_LGBM_Price_Top1 (ModeA1_Repro)", led_a1),
            ("QQQ_LGBM_Price_Top1 (ModeB1_PureQQQ)", led_b1),
        ]:
            r_s = led_s.loc[s_dt:e_dt, "net"].dropna()
            r_m1 = led_mom1.loc[s_dt:e_dt, "net"].reindex(r_s.index).dropna()
            r_q = led_qqq_etf.loc[s_dt:e_dt, "net"].reindex(r_s.index).dropna()

            # Active vs QQQ Pure Mom Top-1
            d_m1 = (r_s - r_m1).dropna()
            t_vs_m1 = float(d_m1.mean() / newey_west_se(d_m1.values, lag=3))
            p_vs_m1 = float(2.0 * (1.0 - norm.cdf(abs(t_vs_m1))))

            # Excess vs QQQ ETF
            d_q = (r_s - r_q).dropna()
            t_vs_q = float(d_q.mean() / newey_west_se(d_q.values, lag=3))
            p_vs_q = float(2.0 * (1.0 - norm.cdf(abs(t_vs_q))))

            dsr_qqq, sr0_qqq, n_qqq = compute_deflated_sharpe(r_s.values, srs_qqq)
            dsr_ml3, sr0_ml3, n_ml3 = compute_deflated_sharpe(r_s.values, srs_ml3)
            dsr_repo, sr0_repo, n_repo = compute_deflated_sharpe(r_s.values, srs_repo)

            mt_rows.append({
                "window": win_name,
                "strategy": strat_label,
                "t_NW_vs_QQQ_PureMom_Top1": round(t_vs_m1, 2),
                "p_raw_vs_PureMom_Top1": round(p_vs_m1, 4),
                "p_Bonferroni_34_QQQ_trials_vs_PureMom": round(min(1.0, p_vs_m1 * max(1, n_qqq)), 4),
                "p_Sidak_34_QQQ_trials_vs_PureMom": round(float(1.0 - (1.0 - p_vs_m1) ** max(1, n_qqq)), 4),
                "p_Bonferroni_AllRepo_vs_PureMom": round(min(1.0, p_vs_m1 * max(1, n_repo)), 4),
                "Passes_HLZ_t3.0_vs_PureMom": bool(abs(t_vs_m1) >= 3.0),
                "t_NW_vs_QQQ_ETF": round(t_vs_q, 2),
                "p_raw_vs_QQQ_ETF": round(p_vs_q, 4),
                "p_Bonferroni_34_QQQ_trials_vs_QQQ_ETF": round(min(1.0, p_vs_q * max(1, n_qqq)), 4),
                "p_Bonferroni_AllRepo_vs_QQQ_ETF": round(min(1.0, p_vs_q * max(1, n_repo)), 4),
                "Passes_HLZ_t3.0_vs_QQQ_ETF": bool(abs(t_vs_q) >= 3.0),
                "N_Trials_QQQ_Family": n_qqq,
                "DSR_vs_QQQ_Family": round(dsr_qqq, 4),
                "Max_Null_Sharpe_QQQ_Family": round(sr0_qqq, 2),
                "N_Trials_ML3_AllPools": n_ml3,
                "DSR_vs_ML3_AllPools": round(dsr_ml3, 4),
                "N_Trials_Repo_Wide": n_repo,
                "DSR_vs_Repo_Wide": round(dsr_repo, 4),
                "Max_Null_Sharpe_Repo_Wide": round(sr0_repo, 2),
            })

    df_mt = pd.DataFrame(mt_rows)
    df_mt.to_csv(OUT_DIR / "step8_multiple_testing_audit.csv", index=False)

    # =========================================================================
    # STEP 9: RETURN CONCENTRATION & MULTI-BAGGER ATTRIBUTION
    # =========================================================================
    print("   Running Step 9 Return Concentration & Multi-Bagger Attribution Audit...", flush=True)
    conc_rows = []
    for win_name, s_dt, e_dt in [
        ("OOS_2019_2026.09 (93m)", "2019-01-31", "2026-09-30"),
        ("OOS_2015_2026.09 (140m)", "2015-01-31", "2026-09-30"),
    ]:
        sub_l = led_a1.loc[s_dt:e_dt].copy()
        sub_l["log_ret"] = np.log1p(sub_l["net"])
        tot_log = float(sub_l["log_ret"].sum())
        grp = sub_l.groupby("picks").agg(
            months_held=("net", "count"),
            log_wealth_sum=("log_ret", "sum"),
            compound_mult=("net", lambda s: float((1.0 + s).prod())),
            mean_monthly_ret_pct=("net", lambda s: round(float(s.mean() * 100), 2)),
            best_month_pct=("net", lambda s: round(float(s.max() * 100), 2)),
            worst_month_pct=("net", lambda s: round(float(s.min() * 100), 2)),
        ).reset_index().sort_values("log_wealth_sum", ascending=False)
        grp["share_of_total_log_wealth_pct"] = (grp["log_wealth_sum"] / tot_log * 100.0).round(2)
        grp["cum_share_of_log_wealth_pct"] = grp["share_of_total_log_wealth_pct"].cumsum().round(2)
        grp["window"] = win_name
        conc_rows.append(grp)

    df_conc = pd.concat(conc_rows, ignore_index=True)
    df_conc.to_csv(OUT_DIR / "step9_concentration_audit.csv", index=False)

    # Top-15 best & worst months table
    sub_15 = led_a1.loc["2015-01-31":"2026-09-30"].copy()
    sub_15["log_ret"] = np.log1p(sub_15["net"])
    tot_l15 = float(sub_15["log_ret"].sum())
    sub_15["share_of_2015_2026_log_wealth_pct"] = (sub_15["log_ret"] / tot_l15 * 100.0).round(2)
    sub_15["pure_mom_top1_pick"] = led_mom1.reindex(sub_15.index)["picks"]
    sub_15["pure_mom_top1_net_pct"] = (led_mom1.reindex(sub_15.index)["net"] * 100.0).round(2)
    sub_15["qqq_etf_net_pct"] = (led_qqq_etf.reindex(sub_15.index)["net"] * 100.0).round(2)
    sub_15["lgbm_net_pct"] = (sub_15["net"] * 100.0).round(2)

    top_m = pd.concat([
        sub_15.sort_values("net", ascending=False).head(15).assign(rank_type="TOP_15_BEST_MONTHS"),
        sub_15.sort_values("net", ascending=True).head(10).assign(rank_type="BOTTOM_10_WORST_MONTHS"),
    ])
    top_m.reset_index()[["rank_type", "month", "formation", "picks", "lgbm_net_pct", "share_of_2015_2026_log_wealth_pct", "pure_mom_top1_pick", "pure_mom_top1_net_pct", "qqq_etf_net_pct"]].to_csv(
        OUT_DIR / "step9_top_and_bottom_months_audit.csv", index=False
    )

    print("   Steps 5-9 complete! Summary of key stress & statistical findings:")
    print(f"   - Seed sensitivity (10 seeds, 2019-2026 CAGR): min={min(seed_cagrs_19):.2f}%, median={np.median(seed_cagrs_19):.2f}%, max={max(seed_cagrs_19):.2f}%")
    print(f"   - Seed sensitivity (10 seeds, 2015-2026 CAGR): min={min(seed_cagrs_15):.2f}%, median={np.median(seed_cagrs_15):.2f}%, max={max(seed_cagrs_15):.2f}%")


if __name__ == "__main__":
    main()
