#!/usr/bin/env python3
"""
ML3 EXTENSION: XLK (HISTORICAL POINT-IN-TIME S&P 500 TECH POOL)
================================================================
Strictly isolated in `outputs/ml3_feature_discovery_20261102/`.
Zero modification to baseline files in `research/sector_stock_momentum/`.

Tests the hypothesis:
  "Does restricting the universe to Historical Point-in-Time US Large-Cap Tech (XLK)
   deliver higher CAGR / better super-winner capture than S&P 500 or QQQ?"

Evaluates 6 XLK / Tech PIT Pool Configurations across 2015-2026.09 (12 Folds) and 2019-2026.09 (8 Folds):
  1. `XLK_Full_PIT` (~68 S&P 500 Information Technology PIT stocks/month -> ML picks Top-1 / Top-3)
  2. `XLK_Top30_PIT` (12-1 Momentum Top-30 inside XLK PIT -> ML picks Top-1 / Top-3, In-Pool Trained)
  3. `XLK_Top20_PIT` (12-1 Momentum Top-20 inside XLK PIT -> ML picks Top-1 / Top-3, In-Pool Trained)
  4. `XLK_Top20_TrainFullXLK` (Trained on Full XLK PIT ~68/m -> Predicts inside XLK 12-1 Momentum Top-20)
  5. `XLK_Top20_TrainSP500Top50` (Trained on S&P 500 12-1 Top-50 -> Predicts inside XLK 12-1 Momentum Top-20)
  6. `XLK_Strict_SEC_SIC_PIT` (100% SEC EDGAR SIC-Code Tech PIT Pool, zero Wikipedia/Yahoo sector input:
     Both Pure 12-1 Momentum Top-1/Top-3 and ML Top-1/Top-3 on Full & Top-20)

Across Feature Tiers:
  - `T0_Pure_Momentum_12_1` (Top-1 / Top-3)
  - `T1_SetA_Price_Only` (18 price/vol/regime features)
  - `T2_SetB_Price_Plus_Snapshot` (39 price + single-quarter SEC snapshot features)
  - `T3a_SetC4_Trajectory_Core` (57 price + snapshot + 18 core multi-quarter trajectory features)
  - `T3b_SetC8_Summary_Slopes_68` (68 features: +8Q slopes, Operating Margin, ROIC, CapEx)
  - `T3S_InSample_Feature_Discovery` (78 features -> pruned in-sample on Train+Val -> Frozen OOS)
  - `T3a_SetC4_ZeroCAGRPeek_RankVal` (Zero CAGR peeking in validation)
  - `T3a_SetC4_ZeroTune_FixedNL7` (Fixed `num_leaves=7`, zero tuning)
  - Linear `Ridge` comparison
  - Benchmarks: `XLK ETF Buy & Hold`, `QQQ ETF Buy & Hold`, `SPY ETF Buy & Hold` (Open-to-Open).
"""

import glob
import json
import sys
import warnings
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy.stats import norm  # noqa: E402
from sklearn.linear_model import Ridge

warnings.filterwarnings("ignore")

REPO_ROOT = Path("/Users/happygolucky/Desktop/宏观观察器").resolve()
SSM_DIR = REPO_ROOT / "research" / "sector_stock_momentum"
OUT_DIR = REPO_ROOT / "outputs" / "ml3_feature_discovery_20261102"
LEDGER_XLK_DIR = OUT_DIR / "ledgers_xlk"
OUT_DIR.mkdir(parents=True, exist_ok=True)
LEDGER_XLK_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(SSM_DIR))
sys.path.insert(0, str(OUT_DIR))
import backtest as bt  # noqa: E402
from factor_screen import nw_se, ranked  # noqa: E402
import ml2_run as m2  # noqa: E402
import winners_tracks as wt  # noqa: E402
from run_ml3_feature_discovery import (  # noqa: E402
    SET_A,
    SET_B,
    SET_C4,
    SET_C8_ALL,
    SET_C8_SUMMARY,
    TEST_YEARS,
    build_or_load_ml3_panel,
    compute_period_metrics,
    fit_predict_model,
    in_sample_feature_discovery,
)
from run_ml3_qqq_iwm_pools import load_etf_monthly_returns  # noqa: E402


def paired_comparison_stats(rx, rb, S):
    j = pd.concat([rx.dropna(), rb.dropna()], axis=1, keys=["x", "b"]).dropna()
    cx = float((1.0 + j["x"]).prod() ** (12.0 / len(j)) - 1.0)
    cb = float((1.0 + j["b"]).prod() ** (12.0 / len(j)) - 1.0)
    diff_m = j["x"] - j["b"]
    se, _ = nw_se(diff_m.values, lag=3)
    t_nw = float(diff_m.mean() / se) if se and se > 0 else 0.0
    p_raw = float(2.0 * (1.0 - norm.cdf(abs(t_nw))))
    bs = bt.paired_bootstrap([j["x"].rename("x"), j["b"].rename("b")], S["rf"], n=2000)
    yd = (1.0 + j["x"]).groupby(j.index.year).prod() - (1.0 + j["b"]).groupby(j.index.year).prod()
    return {
        "CAGR_Model_pct": round(cx * 100, 2),
        "CAGR_Base_pct": round(cb * 100, 2),
        "CAGR_Diff_pct": round((cx - cb) * 100, 2),
        "Ann_Arith_Diff_pct": round(float(diff_m.mean() * 12 * 100), 2),
        "t_NW_HAC": round(t_nw, 2),
        "p_raw_two_sided": round(p_raw, 4),
        "Bootstrap_CAGR_Diff_p5_p50_p95": bs.get("x minus b: CAGR diff p5/p50/p95"),
        "Bootstrap_Share_Diff_le_0": round(float(bs.get("x minus b: share of resamples with CAGR diff <= 0", np.nan)), 4),
        "Years_Better": f"{int((yd > 0).sum())}/{int(len(yd))}",
    }


def attach_strict_sec_sic_tech(X):
    """
    100% SEC EDGAR SIC-Code Point-in-Time Tech flag (`in_sec_sic_tech`).
    Uses ONLY SEC EDGAR `sec_submissions/<cik>.json` SIC codes + official S&P GICS
    2018-09-24 and 2023-03-20 structure transition dates (zero Wikipedia/Yahoo sector input).
    """
    sic_map = {}
    for fn in glob.glob(str(SSM_DIR / "data" / "sec_submissions" / "*.json")):
        j = json.load(open(fn))
        c = int(j.get("cik", 0))
        sic = str(j.get("sic", "")).strip()
        if c and sic.isdigit():
            sic_map[c] = int(sic)

    sics = [sic_map.get(int(c), 0) if pd.notna(c) else 0 for c in X.cik]
    flags = []
    d_2018 = pd.Timestamp("2018-09-24")
    d_2023 = pd.Timestamp("2023-03-20")
    pre2018_it = {"GOOGL", "GOOG", "META", "FB", "TWTR", "EA", "ATVI", "TTWO", "EBAY", "YHOO"}
    pre2023_it = {"V", "MA", "PYPL", "FIS", "FISV", "GPN", "FLT", "JKHY", "ADP", "PAYX", "PAYC", "CDAY", "BR", "WU", "TSS", "ADS"}

    for t, tk, s in zip(X.t, X.ticker, sics):
        if t < d_2018 and tk in pre2018_it:
            flags.append(True)
            continue
        if t >= d_2018 and tk in pre2018_it:
            flags.append(False)
            continue
        if t < d_2023 and tk in pre2023_it:
            flags.append(True)
            continue
        if t >= d_2023 and tk in pre2023_it:
            flags.append(False)
            continue
        core = (3570 <= s <= 3579) or (3660 <= s <= 3679) or (7370 <= s <= 7379) or s in (3825, 3827, 5045, 5065)
        flags.append(bool(core))

    X = X.copy()
    X["sec_sic"] = sics
    X["in_sec_sic_tech"] = flags
    return X


_XLK_RANK_CACHE = {}
_XLK_DISC_CACHE = {}
_XLK_PRED_CACHE = {}


def _get_ranks(df):
    key = (len(df), str(df.ticker.iat[0]), str(df.ticker.iat[-1]), float(df.mom_12_1.iat[0]))
    if key not in _XLK_RANK_CACHE:
        D = df.copy().reset_index(drop=True)
        R = ranked(D, SET_C8_ALL, fill=False)
        y = D.groupby("t").ret_oo.rank(pct=True) - 0.5
        _XLK_RANK_CACHE[key] = (D, R, y)
    return _XLK_RANK_CACHE[key]


def _get_disc(key, Y, tr, val, cols, n_keep, R_src, y_src):
    dkey = (key, Y, n_keep)
    if dkey not in _XLK_DISC_CACHE:
        _XLK_DISC_CACHE[dkey] = in_sample_feature_discovery(tr, val, cols, n_keep, R_src, y_src)
    return _XLK_DISC_CACHE[dkey]


def run_xlk_walk_forward(
    D_target,
    S,
    kind,
    cols,
    k,
    val_criterion="val_cagr",
    auto_discover=False,
    D_train_source=None,
):
    D_base, R_target, y_target = _get_ranks(D_target)
    D = D_base.copy()

    if D_train_source is not None:
        D_src, R_src, y_src = _get_ranks(D_train_source)
    else:
        D_src, R_src, y_src = D, R_target, y_target

    src_key = (len(D_src), str(D_src.ticker.iat[0]), str(D_src.ticker.iat[-1]))
    D["score"] = np.nan
    med_n = D_src.groupby("t").size().median()
    min_c = 30 if med_n <= 25 else (50 if med_n <= 40 else 100)
    param_grid = (
        [{"num_leaves": 7, "min_child_samples": min_c}, {"num_leaves": 15, "min_child_samples": min_c}]
        if kind == "lgbm"
        else [{"alpha": 1.0}, {"alpha": 10.0}, {"alpha": 100.0}]
    )

    for Y in TEST_YEARS:
        tr_start = pd.Timestamp("2011-01-31")
        tr_end = pd.Timestamp(f"{Y - 3}-11-30")
        val_end = pd.Timestamp(f"{Y - 1}-11-30")  # 1-month embargo before test (Dec Y-1 exits in early Feb Y)
        val_src = D_src[(D_src.t >= pd.Timestamp(f"{Y - 2}-01-31")) & (D_src.t <= val_end) & D_src.ret_oo.notna()]
        val_tgt = D[(D.t >= pd.Timestamp(f"{Y - 2}-01-31")) & (D.t <= val_end) & D.ret_oo.notna()]
        tr = D_src[(D_src.t >= tr_start) & (D_src.t <= tr_end) & D_src.ret_oo.notna()]
        te = D[D.t.dt.year == Y]
        if te.empty or tr.empty:
            continue

        if val_criterion == "fixed_nl7":
            best_params = param_grid[0] if kind == "lgbm" else param_grid[1]
            best_cols = _get_disc(src_key, Y, tr, val_src, cols, 55, R_src, y_src) if auto_discover else cols
        else:
            best_params, best_cols, best_v = None, None, -np.inf
            cand_subsets = [
                ("C4_Core_57", SET_C4),
                ("AutoTop50", _get_disc(src_key, Y, tr, val_src, cols, 50, R_src, y_src)),
                ("AutoTop60", _get_disc(src_key, Y, tr, val_src, cols, 60, R_src, y_src)),
            ] if auto_discover else [("FixedSet", cols)]

            for _, use_cols in cand_subsets:
                for params in param_grid:
                    if D_train_source is None:
                        v = val_src.copy()
                        v["s"] = fit_predict_model(kind, params, tr, v, use_cols, True, R_src, y_src)
                        if val_criterion == "val_cagr":
                            c = m2.net_cagr(S, m2.topk_weights(v, "s", k))
                        else:
                            v["r_rk"] = y_src.loc[v.index]
                            c = float(v.sort_values(["t", "s"], ascending=[True, False]).groupby("t").head(5)["r_rk"].mean())
                    else:
                        # Fit on tr (D_src), evaluate on val_tgt (D_target)
                        v = val_tgt.copy()
                        R_tr = R_src.loc[tr.index, use_cols]
                        R_v = R_target.loc[v.index, use_cols]
                        y_tr = y_src.loc[tr.index].values
                        if kind == "ridge":
                            F_tr = pd.concat([R_tr.fillna(0.0), R_tr.isna().astype(float).add_suffix("_na")], axis=1).values
                            F_v = pd.concat([R_v.fillna(0.0), R_v.isna().astype(float).add_suffix("_na")], axis=1).values
                            mdl_v = Ridge(alpha=params["alpha"], random_state=7).fit(F_tr, y_tr)
                            v["s"] = mdl_v.predict(F_v)
                        else:
                            mdl_v = lgb.LGBMRegressor(
                                n_estimators=300,
                                learning_rate=0.05,
                                num_leaves=params["num_leaves"],
                                max_depth=3,
                                min_child_samples=params.get("min_child_samples", 100),
                                subsample=0.8,
                                subsample_freq=1,
                                colsample_bytree=0.8,
                                random_state=7,
                                verbose=-1,
                            ).fit(R_tr.values, y_tr)
                            v["s"] = mdl_v.predict(R_v.values)
                        if val_criterion == "val_cagr":
                            c = m2.net_cagr(S, m2.topk_weights(v, "s", k))
                        else:
                            v["r_rk"] = y_target.loc[v.index]
                            c = float(v.sort_values(["t", "s"], ascending=[True, False]).groupby("t").head(5)["r_rk"].mean())
                    if c > best_v:
                        best_params, best_cols, best_v = params, use_cols, c

        tr2 = D_src[(D_src.t >= tr_start) & (D_src.t <= pd.Timestamp(f"{Y - 1}-11-30")) & D_src.ret_oo.notna()]
        tkey = (
            id(R_src),
            id(R_target),
            int(tr2.index[0]),
            int(tr2.index[-1]),
            len(tr2),
            int(te.index[0]),
            int(te.index[-1]),
            len(te),
            kind,
            str(sorted(best_params.items())),
            tuple(best_cols),
        )
        if tkey in _XLK_PRED_CACHE:
            D.loc[te.index, "score"] = _XLK_PRED_CACHE[tkey]
        else:
            R_tr2 = R_src.loc[tr2.index, best_cols]
            R_te = R_target.loc[te.index, best_cols]
            y_tr2 = y_src.loc[tr2.index].values
            if kind == "ridge":
                F_tr = pd.concat([R_tr2.fillna(0.0), R_tr2.isna().astype(float).add_suffix("_na")], axis=1).values
                F_te = pd.concat([R_te.fillna(0.0), R_te.isna().astype(float).add_suffix("_na")], axis=1).values
                mdl = Ridge(alpha=best_params["alpha"], random_state=7).fit(F_tr, y_tr2)
                pred_te = mdl.predict(F_te)
            else:
                mdl = lgb.LGBMRegressor(
                    n_estimators=300,
                    learning_rate=0.05,
                    num_leaves=best_params["num_leaves"],
                    max_depth=3,
                    min_child_samples=best_params.get("min_child_samples", 100),
                    subsample=0.8,
                    subsample_freq=1,
                    colsample_bytree=0.8,
                    random_state=7,
                    verbose=-1,
                ).fit(R_tr2.values, y_tr2)
                pred_te = mdl.predict(R_te.values)
            _XLK_PRED_CACHE[tkey] = pred_te
            D.loc[te.index, "score"] = pred_te

    return D


def main():
    print("==================================================================", flush=True)
    print("XLK HISTORICAL POINT-IN-TIME TECH POOL ML3 EXPERIMENT", flush=True)
    print("==================================================================", flush=True)
    daily, P, aliases, bad = bt.load_prices()
    O = m2.build_opens(daily)
    px = m2.OpenPrices(daily, P, O)
    S = {
        "px": px,
        "res": bt.load_resolutions(),
        "daily": daily,
        "rf": bt.load_rf(pd.date_range("2009-01-31", "2026-10-31", freq="ME")),
    }
    X = build_or_load_ml3_panel()
    X = attach_strict_sec_sic_tech(X)

    # 1. Historical GICS Information Technology PIT Pool (XLK)
    X_xlk = X[X["sector"] == "Information Technology"].copy()
    X_xlk = X_xlk.sort_values(["t", "mom_12_1", "ticker"], ascending=[True, False, True]).reset_index(drop=True)
    X_xlk["mom_rank_xlk"] = X_xlk.groupby("t").cumcount() + 1

    # 2. Strict SEC EDGAR SIC-Code Tech PIT Pool (Zero Wikipedia/Yahoo input)
    X_sic = X[X["in_sec_sic_tech"].astype(bool)].copy()
    X_sic = X_sic.sort_values(["t", "mom_12_1", "ticker"], ascending=[True, False, True]).reset_index(drop=True)
    X_sic["mom_rank_sic"] = X_sic.groupby("t").cumcount() + 1

    # 3. S&P 500 Top-50 Momentum Pool (for cross-pool training comparison)
    D_sp50 = X[X.mom_rank <= 50].copy().reset_index(drop=True)

    print(
        f"   XLK GICS PIT Pool: {len(X_xlk)} stock-months, median {int(X_xlk.groupby('t').size().median())} stocks/month.",
        flush=True,
    )
    print(
        f"   Strict SEC SIC Tech PIT Pool: {len(X_sic)} stock-months, median {int(X_sic.groupby('t').size().median())} stocks/month.",
        flush=True,
    )

    form_test = sorted(X_xlk[(X_xlk.t.dt.year >= 2015) & (X_xlk.t.dt.year <= 2026)].t.unique())
    strategies = {}
    strategies["BENCH__XLK_ETF__BuyHold"] = load_etf_monthly_returns("XLK", form_test, S)
    strategies["BENCH__QQQ_ETF__BuyHold"] = load_etf_monthly_returns("QQQ", form_test, S)
    strategies["BENCH__SPY_ETF__BuyHold"] = wt.run_weights(S, {t: {"SPY": 1.0} for t in form_test}).loc["2015-01-31":"2026-09-30"]

    # Pure 12-1 Momentum (T0) on XLK GICS PIT and Strict SEC SIC PIT
    for p_name, D_p, rk_col in [
        ("XLK_PIT", X_xlk, "mom_rank_xlk"),
        ("XLK_Strict_SEC_SIC", X_sic, "mom_rank_sic"),
    ]:
        sub_p = D_p[(D_p.t.dt.year >= 2015) & (D_p.t.dt.year <= 2026)]
        for k in (1, 3):
            W_m = {t: {s_: 1.0 / k for s_ in g.sort_values([rk_col, "ticker"]).ticker.head(k)} for t, g in sub_p.groupby("t")}
            strategies[f"{p_name}__T0_Pure_Momentum_12_1__Top{k}"] = W_m
        # Equal-weight XLK universe benchmark
        W_ew = {t: {s_: 1.0 / len(g) for s_ in g.ticker} for t, g in sub_p.groupby("t")}
        strategies[f"{p_name}__EqualWeight_Tech_Universe"] = W_ew

    xlk_pools = [
        ("XLK_Full_PIT", X_xlk.copy(), None),
        ("XLK_Top30_PIT", X_xlk[X_xlk.mom_rank_xlk <= 30].copy(), None),
        ("XLK_Top20_PIT", X_xlk[X_xlk.mom_rank_xlk <= 20].copy(), None),
        ("XLK_Top20_TrainFullXLK", X_xlk[X_xlk.mom_rank_xlk <= 20].copy(), X_xlk.copy()),
        ("XLK_Top20_TrainSP500Top50", X_xlk[X_xlk.mom_rank_xlk <= 20].copy(), D_sp50),
        ("XLK_Top30_TrainSP500Top50", X_xlk[X_xlk.mom_rank_xlk <= 30].copy(), D_sp50),
        ("XLK_Strict_SEC_SIC_Full", X_sic.copy(), None),
        ("XLK_Strict_SEC_SIC_Top20", X_sic[X_sic.mom_rank_sic <= 20].copy(), X_sic.copy()),
    ]

    model_specs = [
        ("T1_SetA_Price_Only", "lgbm", SET_A, "val_cagr", False),
        ("T2_SetB_Price_Plus_Snapshot", "lgbm", SET_B, "val_cagr", False),
        ("T3a_SetC4_Trajectory_Core", "lgbm", SET_C4, "val_cagr", False),
        ("T3b_SetC8_Summary_Slopes_68", "lgbm", SET_C8_SUMMARY, "val_cagr", False),
        ("T3S_InSample_Feature_Discovery", "lgbm", SET_C8_ALL, "val_cagr", True),
        ("T3a_SetC4_ZeroCAGRPeek_RankVal", "lgbm", SET_C4, "val_rank", False),
        ("T3a_SetC4_ZeroTune_FixedNL7", "lgbm", SET_C4, "fixed_nl7", False),
        ("T3a_SetC4_Trajectory_Core", "ridge", SET_C4, "val_cagr", False),
    ]

    for pool_name, D_pool, D_tr_src in xlk_pools:
        for tier_name, kind, cols, val_crit, auto_disc in model_specs:
            if pool_name in (
                "XLK_Top20_TrainFullXLK",
                "XLK_Top20_TrainSP500Top50",
                "XLK_Top30_TrainSP500Top50",
                "XLK_Strict_SEC_SIC_Full",
                "XLK_Strict_SEC_SIC_Top20",
            ) and tier_name not in (
                "T1_SetA_Price_Only",
                "T2_SetB_Price_Plus_Snapshot",
                "T3a_SetC4_Trajectory_Core",
                "T3S_InSample_Feature_Discovery",
                "T3a_SetC4_ZeroCAGRPeek_RankVal",
                "T3a_SetC4_ZeroTune_FixedNL7",
            ):
                continue
            for k in (1, 3):
                sname = f"{pool_name}__{tier_name}__{kind}__Top{k}"
                D_res = run_xlk_walk_forward(
                    D_pool,
                    S,
                    kind,
                    cols,
                    k,
                    val_criterion=val_crit,
                    auto_discover=auto_disc,
                    D_train_source=D_tr_src,
                )
                W = m2.topk_weights(D_res[(D_res.t.dt.year >= 2015) & (D_res.t.dt.year <= 2026)], "score", k)
                strategies[sname] = W
                print(f"   Done XLK: {sname}", flush=True)

    periods = [
        ("OOS_2019_2026.09 (93m, 8 Folds)", "2019-01-31", "2026-09-30"),
        ("OOS_2015_2026.09 (141m, 12 Folds)", "2015-01-31", "2026-09-30"),
        ("Sub_2015_2019 (60m)", "2015-01-31", "2019-12-31"),
        ("Sub_2020_2022 (36m)", "2020-01-31", "2022-12-31"),
        ("Sub_2023_2026.09 (45m)", "2023-01-31", "2026-09-30"),
    ]
    rows = []
    ledgers = {}
    for name, item in strategies.items():
        if isinstance(item, pd.DataFrame):
            df_base = item
            df_s30 = item
            df_s100 = item
        else:
            df_base = wt.run_weights(S, item, stress=None).loc["2015-01-31":"2026-09-30"]
            df_s30 = wt.run_weights(S, item, stress=-0.30).loc["2015-01-31":"2026-09-30"]
            df_s100 = wt.run_weights(S, item, stress=-1.00).loc["2015-01-31":"2026-09-30"]
        ledgers[name] = df_base
        safe_fn = "".join(c if c.isalnum() else "_" for c in name) + ".csv"
        df_base.to_csv(LEDGER_XLK_DIR / safe_fn)
        for p_label, s_dt, e_dt in periods:
            r30 = df_s30.loc[s_dt:e_dt].net.dropna()
            r100 = df_s100.loc[s_dt:e_dt].net.dropna()
            c30 = float((1.0 + r30).prod() ** (12.0 / len(r30)) - 1.0) if len(r30) else np.nan
            c100 = float((1.0 + r100).prod() ** (12.0 / len(r100)) - 1.0) if len(r100) else np.nan
            rec = compute_period_metrics(S, df_base, p_label, s_dt, e_dt, stress_cagr_30=c30, stress_cagr_100=c100)
            rec["strategy"] = name
            rows.append(rec)

    df_sum = pd.DataFrame(rows)[[
        "strategy", "period", "months", "CAGR_pct", "Vol_pct", "Sharpe", "Sortino",
        "MaxDD_Monthly_pct", "MaxDD_Daily_pct", "Calmar", "Avg_Monthly_Turnover_pct",
        "Win_Rate_pct", "Stress_m30_CAGR_pct", "Stress_m100_CAGR_pct",
    ]]
    df_sum.to_csv(OUT_DIR / "ml3_xlk_summary_table.csv", index=False)

    # Paired statistical comparisons on XLK
    comp_specs = [
        ("XLK_PIT Pure_Mom Top1 vs XLK_ETF BuyHold", "XLK_PIT__T0_Pure_Momentum_12_1__Top1", "BENCH__XLK_ETF__BuyHold"),
        ("XLK_PIT Pure_Mom Top3 vs XLK_ETF BuyHold", "XLK_PIT__T0_Pure_Momentum_12_1__Top3", "BENCH__XLK_ETF__BuyHold"),
        ("XLK_Strict_SEC_SIC Pure_Mom Top1 vs XLK_PIT Pure_Mom Top1", "XLK_Strict_SEC_SIC__T0_Pure_Momentum_12_1__Top1", "XLK_PIT__T0_Pure_Momentum_12_1__Top1"),
        ("XLK_Full_PIT Top1: T1_Price vs Pure_Mom", "XLK_Full_PIT__T1_SetA_Price_Only__lgbm__Top1", "XLK_PIT__T0_Pure_Momentum_12_1__Top1"),
        ("XLK_Full_PIT Top1: T3a_Trajectory vs Pure_Mom", "XLK_Full_PIT__T3a_SetC4_Trajectory_Core__lgbm__Top1", "XLK_PIT__T0_Pure_Momentum_12_1__Top1"),
        ("XLK_Full_PIT Top1: T3S_Discovery vs Pure_Mom", "XLK_Full_PIT__T3S_InSample_Feature_Discovery__lgbm__Top1", "XLK_PIT__T0_Pure_Momentum_12_1__Top1"),
        ("XLK_Full_PIT Top3: T1_Price vs Pure_Mom", "XLK_Full_PIT__T1_SetA_Price_Only__lgbm__Top3", "XLK_PIT__T0_Pure_Momentum_12_1__Top3"),
        ("XLK_Full_PIT Top3: T3a_Trajectory vs Pure_Mom", "XLK_Full_PIT__T3a_SetC4_Trajectory_Core__lgbm__Top3", "XLK_PIT__T0_Pure_Momentum_12_1__Top3"),
        ("XLK_Top30 Top1: T1_Price vs Pure_Mom", "XLK_Top30_PIT__T1_SetA_Price_Only__lgbm__Top1", "XLK_PIT__T0_Pure_Momentum_12_1__Top1"),
        ("XLK_Top30 Top3: T1_Price vs Pure_Mom", "XLK_Top30_PIT__T1_SetA_Price_Only__lgbm__Top3", "XLK_PIT__T0_Pure_Momentum_12_1__Top3"),
        ("XLK_Top30 Top3: T3a_Trajectory vs Pure_Mom", "XLK_Top30_PIT__T3a_SetC4_Trajectory_Core__lgbm__Top3", "XLK_PIT__T0_Pure_Momentum_12_1__Top3"),
        ("XLK_Top20 Top3: T3a_Trajectory vs Pure_Mom", "XLK_Top20_PIT__T3a_SetC4_Trajectory_Core__lgbm__Top3", "XLK_PIT__T0_Pure_Momentum_12_1__Top3"),
        ("XLK_Top20_TrainSP500Top50 Top1: T3a vs Pure_Mom", "XLK_Top20_TrainSP500Top50__T3a_SetC4_Trajectory_Core__lgbm__Top1", "XLK_PIT__T0_Pure_Momentum_12_1__Top1"),
        ("XLK_Top20_TrainSP500Top50 Top3: T3a vs Pure_Mom", "XLK_Top20_TrainSP500Top50__T3a_SetC4_Trajectory_Core__lgbm__Top3", "XLK_PIT__T0_Pure_Momentum_12_1__Top3"),
        ("XLK_Top30_TrainSP500Top50 Top1: T3a vs Pure_Mom", "XLK_Top30_TrainSP500Top50__T3a_SetC4_Trajectory_Core__lgbm__Top1", "XLK_PIT__T0_Pure_Momentum_12_1__Top1"),
        ("XLK_Top30_TrainSP500Top50 Top1: T3a_RankVal vs Pure_Mom", "XLK_Top30_TrainSP500Top50__T3a_SetC4_ZeroCAGRPeek_RankVal__lgbm__Top1", "XLK_PIT__T0_Pure_Momentum_12_1__Top1"),
        ("XLK_Top30_TrainSP500Top50 Top1: T3a_FixedNL7 vs Pure_Mom", "XLK_Top30_TrainSP500Top50__T3a_SetC4_ZeroTune_FixedNL7__lgbm__Top1", "XLK_PIT__T0_Pure_Momentum_12_1__Top1"),
        ("XLK_Top30_TrainSP500Top50 Top3: T3a_RankVal vs Pure_Mom", "XLK_Top30_TrainSP500Top50__T3a_SetC4_ZeroCAGRPeek_RankVal__lgbm__Top3", "XLK_PIT__T0_Pure_Momentum_12_1__Top3"),
        ("XLK_Top30_TrainSP500Top50 Top3: T3a_FixedNL7 vs Pure_Mom", "XLK_Top30_TrainSP500Top50__T3a_SetC4_ZeroTune_FixedNL7__lgbm__Top3", "XLK_PIT__T0_Pure_Momentum_12_1__Top3"),
        ("XLK_Strict_SEC_SIC_Full Top1: T1_Price vs Pure_Mom", "XLK_Strict_SEC_SIC_Full__T1_SetA_Price_Only__lgbm__Top1", "XLK_Strict_SEC_SIC__T0_Pure_Momentum_12_1__Top1"),
        ("XLK_Strict_SEC_SIC_Top20 Top3: T1_Price vs Pure_Mom", "XLK_Strict_SEC_SIC_Top20__T1_SetA_Price_Only__lgbm__Top3", "XLK_Strict_SEC_SIC__T0_Pure_Momentum_12_1__Top3"),
    ]
    comp_frames = []
    for w_label, s_dt, e_dt in [
        ("OOS_2019_2026.09 (93m)", "2019-01-31", "2026-09-30"),
        ("OOS_2015_2026.09 (141m)", "2015-01-31", "2026-09-30"),
    ]:
        w_recs = []
        for c_label, a_key, b_key in comp_specs:
            ra = ledgers[a_key].loc[s_dt:e_dt].net
            rb = ledgers[b_key].loc[s_dt:e_dt].net
            st = paired_comparison_stats(ra, rb, S)
            st["window"] = w_label
            st["comparison"] = c_label
            w_recs.append(st)
        df_w = pd.DataFrame(w_recs)
        order = df_w["p_raw_two_sided"].argsort().values
        holm = np.zeros(len(df_w))
        prev = 0.0
        for rank_idx, row_idx in enumerate(order):
            val_h = min(1.0, (len(df_w) - rank_idx) * df_w.loc[row_idx, "p_raw_two_sided"])
            prev = max(prev, val_h)
            holm[row_idx] = round(prev, 4)
        df_w["p_Holm_Bonferroni"] = holm
        comp_frames.append(df_w)
    df_comp = pd.concat(comp_frames, ignore_index=True)
    df_comp.to_csv(OUT_DIR / "ml3_xlk_paired_comparisons.csv", index=False)

    print("\n================ XLK SUMMARY (OOS 2019-2026.09 & 2015-2026.09) ================", flush=True)
    p_x = df_sum[df_sum.period.isin(["OOS_2019_2026.09 (93m, 8 Folds)", "OOS_2015_2026.09 (141m, 12 Folds)"])]
    print(p_x[["strategy", "period", "CAGR_pct", "Vol_pct", "Sharpe", "MaxDD_Daily_pct", "Win_Rate_pct"]].to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
