#!/usr/bin/env python3
"""
ML3 EXTENSION: QQQ (NASDAQ-100 PIT) & IWM (SMALL/MID-CAP PIT) POOLS
===================================================================
Strictly isolated in `outputs/ml3_feature_discovery_20261102/`.
Zero modification to baseline files in `research/sector_stock_momentum/`.

Runs the exact same ML3 Feature Discovery -> Nested Rolling Frozen OOS framework on:
  1. QQQ Pool (Point-in-Time Nasdaq-100 Constituents, ~100 stocks/month, 2011..2026.09):
     - `QQQ_Top30` (`12-1` Momentum Top-30 inside QQQ -> ML picks Top-1 / Top-3)
     - `QQQ_Top50` (`12-1` Momentum Top-50 inside QQQ -> ML picks Top-1 / Top-3)
     - `QQQ_Full100` (All ~100 eligible QQQ constituents -> ML picks Top-1 / Top-3)
     - `SP500_Union_QQQ_Top50` (`S&P 500 U QQQ` `12-1` Momentum Top-50 -> ML picks Top-1 / Top-3)
     - Across Tiers:
       * `T0_Pure_Momentum_12_1`
       * `T1_SetA_Price_Only` (18 features)
       * `T2_SetB_Price_Plus_Snapshot` (39 features)
       * `T3a_SetC4_Trajectory_Core` (57 features)
       * `T3S_InSample_Feature_Discovery` (78 features -> pruned in-sample on Train+Val -> Frozen OOS)
       * `T3a_ZeroCAGRPeek_RankVal` (Zero CAGR peeking in validation)
       * `T3a_ZeroTune_FixedNL7` (Fixed `num_leaves=7`, zero tuning)
       * Linear `Ridge` comparison
       * Benchmarks: `QQQ ETF` and `SPY ETF` (Open-to-Open / Next-Session).

  2. IWM / Small-Mid-Cap Pool (Non-S&P 500 Liquid Small/Mid-Cap Universe: close >= $5, 63d median DV >= $5M):
     - Evaluates `IWM_Top50` (`12-1` Momentum Top-50 inside Small/Mid-Cap -> ML picks Top-1 / Top-3 / Top-5):
       * Mode A (In-Universe Walk-Forward): Trained on Small/Mid-Cap Top-50 (`2011..Y-1`) -> Predicts Small/Mid-Cap Top-50 (`Y`).
       * Mode B (Zero-Shot Transfer from S&P 500): Trained ONLY on S&P 500 Top-50 (`2011..Y-1`) -> Predicts Small/Mid-Cap Top-50 (`Y`).
     - Evaluates both:
       * `T1_SetA_Price_Only` (100% immune to SEC CIK survivorship bias)
       * `T2_SetB_Price_Plus_Snapshot` & `T3a_SetC4_Trajectory_Core` & `T3S_InSample_Feature_Discovery`
     - Reports across 3 Windows with Base (`0%`), `-30%`, and `-100%` Delisting Stress Tests:
       * `OOS_2019_2026.09 (93m, 8 Folds)`
       * `OOS_2015_2026.09 (141m, 12 Folds)`
       * `WIKI_DelistingComplete_2015_2018.02 (38m)` (WIKI delisting-complete window)
     - Benchmarks: `IWM ETF`, `Equal-Weight Small/Mid-Cap Universe`, and `Pure 12-1 Momentum Top-1 / Top-3 / Top-5`.
"""

import glob
import json
import os
import shutil
import sys
import warnings
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy.stats import norm
from sklearn.linear_model import Ridge

warnings.filterwarnings("ignore")

REPO_ROOT = Path("/Users/happygolucky/Desktop/宏观观察器").resolve()
SSM_DIR = REPO_ROOT / "research" / "sector_stock_momentum"
OUT_DIR = REPO_ROOT / "outputs" / "ml3_feature_discovery_20261102"
LEDGER_DIR = OUT_DIR / "ledgers_qqq_iwm"
OUT_DIR.mkdir(parents=True, exist_ok=True)
LEDGER_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(SSM_DIR))
sys.path.insert(0, str(OUT_DIR))
import backtest as bt  # noqa: E402
import earnings_factor as ear_mod  # noqa: E402
import explosive_factors as ef  # noqa: E402
import factor_screen as fs  # noqa: E402
from factor_screen import nw_se, ranked  # noqa: E402
from fundamentals_pit import cik_valid  # noqa: E402
import ml2_features as mf  # noqa: E402
import ml2_run as m2  # noqa: E402
import ml_features as mlf  # noqa: E402
import ndx_expand as ne  # noqa: E402
import ndx_universe as nu  # noqa: E402
import winners_holdout as wh  # noqa: E402
import winners_tracks as wt  # noqa: E402
from run_ml3_feature_discovery import (  # noqa: E402
    SET_A,
    SET_B,
    SET_C4,
    SET_C8_ALL,
    SET_C8_SUMMARY,
    TEST_YEARS,
    compute_period_metrics,
    find_delta_days,
    fit_predict_model,
    in_sample_feature_discovery,
)


def load_etf_monthly_returns(symbol, form_dates, S=None):
    """Loads QQQ or IWM daily prices from data/yahoo/<symbol>.json and computes next-session monthly returns."""
    p = REPO_ROOT / "data" / "yahoo" / f"{symbol}.json"
    j = json.load(open(p))
    s = pd.Series([v[1] for v in j["values"]], index=pd.to_datetime([v[0] for v in j["values"]]), dtype=float)
    s = s[~s.index.duplicated(keep="last")].sort_index()
    if S is not None and "daily" in S:
        S["daily"][symbol] = s.reindex(S["daily"].index).ffill()
    sess = s.dropna().index
    rows = []
    for t in form_dates:
        t_next = t + pd.offsets.MonthEnd(1)
        i0 = sess.searchsorted(t, side="right")
        i1 = sess.searchsorted(t_next, side="right")
        if i0 < len(sess) and i1 < len(sess):
            r = float(s.iloc[i1] / s.iloc[i0] - 1.0)
        else:
            r = 0.0
        rows.append((t_next, r))
    df = pd.DataFrame(rows, columns=["month", "net"]).set_index("month")
    df["gross"] = df["net"]
    df["turnover"] = 0.0
    df["exposure"] = 1.0
    df["picks"] = symbol
    df["weights"] = "1.00000"
    return df


def build_8q_extra_from_root(form, root_dir):
    """Builds the 19 extra 8Q trajectory features from a combined fundamentals root directory."""
    one = pd.Timedelta(days=1)
    q, _ = mf.quarterly_table(str(root_dir))
    L = pd.concat([
        pd.read_parquet(
            f,
            columns=["cik", "tag", "ddate", "qtrs", "uom", "value", "filed", "is_first_report"],
        )
        for f in glob.glob(os.path.join(root_dir, "data", "fundamentals", "pit_long", "*.parquet"))
    ])
    L = L.dropna(subset=["cik", "ddate", "filed"]).copy()
    L["cik"] = L["cik"].astype(int)
    L["ddate"] = pd.to_datetime(L.ddate)
    L["filed"] = pd.to_datetime(L.filed)
    q = q.dropna(subset=["cik", "ddate"]).copy()
    q["cik"] = q["cik"].astype(int)
    q["ddate"] = pd.to_datetime(q["ddate"])
    op = mf._first(L, ["OperatingIncomeLoss"], 1).rename(columns={"value": "opinc", "filed": "f_opinc"})
    assets = mf._first(L, ["Assets"], 0).rename(columns={"value": "assets", "filed": "f_assets"})
    cash = mf._first(L, ["CashAndCashEquivalentsAtCarryingValue"], 0).rename(columns={"value": "cash", "filed": "f_cash"})
    liab_c = mf._first(L, ["LiabilitiesCurrent"], 0).rename(columns={"value": "liab_c", "filed": "f_liab_c"})
    for t_df in (op, assets, cash, liab_c):
        t_df = t_df.dropna(subset=["cik", "ddate"]).copy()
        t_df["cik"] = t_df["cik"].astype(int)
        q = pd.merge_asof(
            q.sort_values("ddate"),
            t_df.sort_values("ddate"),
            on="ddate",
            by="cik",
            tolerance=pd.Timedelta(days=10),
            direction="nearest",
        )
    q = q.sort_values(["cik", "ddate"]).reset_index(drop=True)
    mx = lambda *c: pd.concat([q[x] for x in c], axis=1).max(axis=1, skipna=False)
    q["opm"] = q.opinc / q.revenue.where(q.revenue > 0)
    q["av_opm"] = mx("f_opinc", "filed_revenue") + one
    inv_cap = (q.assets - q.cash.fillna(0) - q.liab_c.fillna(0)).where(lambda s: s > 0)
    q["roic_q"] = (q.opinc * 4.0) / inv_cap
    q["av_roic"] = mx("f_opinc", "f_assets") + one

    capex = mf._first(L, ["PaymentsToAcquirePropertyPlantAndEquipment"], 4).rename(
        columns={"value": "capex", "filed": "f_capex"}
    )
    rev_a = mf._first(
        L,
        ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"],
        4,
    ).rename(columns={"value": "rev_a", "filed": "f_rev_a"})
    C_ann = capex.merge(rev_a, on=["cik", "ddate"], how="inner").sort_values(["cik", "ddate"])
    C_ann["capex_rev"] = C_ann.capex / C_ann.rev_a.where(C_ann.rev_a > 0)
    C_ann["av_capex_rev"] = pd.concat([C_ann.f_capex, C_ann.f_rev_a], axis=1).max(axis=1, skipna=False) + one
    Cg = {c: g for c, g in C_ann.groupby("cik")}

    T = np.array(sorted(pd.DatetimeIndex(form)), dtype="datetime64[ns]")
    out = []
    extra_cols = [
        "rev_g_q4", "rev_g_q5", "rev_g_q6", "rev_g_q7", "rev_g_slope_8q",
        "epsg_q4", "epsg_q5", "epsg_q6", "epsg_q7", "epsg_slope_8q",
        "gm_chg_8q", "nm_chg_8q", "opm_q0", "opm_chg_4q", "opm_chg_8q",
        "roic_q0", "roic_chg_4q", "capex_rev", "capex_chg_4q",
    ]
    for c, g in q.groupby("cik"):
        pe = g.ddate.values
        arr = {k: g[k].values.astype(float) for k in ["rev_g", "epsg", "gm", "nm", "opm", "roic_q"]}
        av = {
            k: g[a].values
            for k, a in [
                ("rev_g", "av_rev_g"),
                ("epsg", "av_epsg"),
                ("gm", "av_gm"),
                ("nm", "av_nm"),
                ("opm", "av_opm"),
                ("roic_q", "av_roic"),
            ]
        }
        gc = Cg.get(c)
        for t in T:
            rec = {"t": t, "cik": c}
            fresh = lambda d: len(d) and (t - d[0]).astype("timedelta64[D]").astype(int) <= 200
            v, d = mf._series_asof(arr["rev_g"], av["rev_g"], pe, t, 8)
            if fresh(d):
                for i in range(4, min(8, len(v))):
                    rec[f"rev_g_q{i}"] = v[i]
                if len(v) >= 6:
                    rec["rev_g_slope_8q"] = np.polyfit(np.arange(len(v)), v[::-1], 1)[0]
            v, d = mf._series_asof(arr["epsg"], av["epsg"], pe, t, 8)
            if fresh(d):
                for i in range(4, min(8, len(v))):
                    rec[f"epsg_q{i}"] = v[i]
                if len(v) >= 6:
                    rec["epsg_slope_8q"] = np.polyfit(np.arange(len(v)), v[::-1], 1)[0]
            for k, n8 in [("gm", "gm_chg_8q"), ("nm", "nm_chg_8q")]:
                v, d = mf._series_asof(arr[k], av[k], pe, t, 12)
                if fresh(d):
                    rec[n8] = find_delta_days(v, d, 680, 780)
            v, d = mf._series_asof(arr["opm"], av["opm"], pe, t, 12)
            if fresh(d):
                rec["opm_q0"] = v[0]
                rec["opm_chg_4q"] = find_delta_days(v, d, 330, 400)
                rec["opm_chg_8q"] = find_delta_days(v, d, 680, 780)
            v, d = mf._series_asof(arr["roic_q"], av["roic_q"], pe, t, 12)
            if fresh(d):
                rec["roic_q0"] = v[0]
                rec["roic_chg_4q"] = find_delta_days(v, d, 330, 400)
            if gc is not None:
                m = (gc.av_capex_rev.values <= t) & np.isfinite(gc.capex_rev.values.astype(float))
                vv, dd = gc.capex_rev.values[m].astype(float), gc.ddate.values[m]
                if len(vv) and (t - dd[-1]).astype("timedelta64[D]").astype(int) <= 455:
                    rec["capex_rev"] = vv[-1]
                    if len(vv) >= 2 and (dd[-1] - dd[-2]).astype("timedelta64[D]").astype(int) in range(330, 400):
                        rec["capex_chg_4q"] = vv[-1] - vv[-2]
            if len(rec) > 2:
                out.append(rec)
    H8 = pd.DataFrame(out)
    for k in extra_cols:
        if k not in H8:
            H8[k] = np.nan
    H8["t"] = pd.to_datetime(H8.t)
    return H8[["t", "cik"] + extra_cols]


# ==============================================================================
# PART 1: BUILD OR LOAD QQQ (NASDAQ-100 PIT) & S&P 500 U QQQ PANEL
# ==============================================================================
def setup_qqq_union_isolated():
    """Loads S&P 500 U Nasdaq-100 prices & membership without modifying any file in research/sector_stock_momentum."""
    scratch_res = OUT_DIR / "_scratch_ndx_res"
    scratch_union = OUT_DIR / "_scratch_ndx_union"
    orig_res, orig_scratch = nu.RES_NDX, nu.SCRATCH
    try:
        nu.RES_NDX = str(scratch_res)
        nu.SCRATCH = str(scratch_union)
        U = nu.setup("2010-12-31", "2026-08-31")
    finally:
        nu.RES_NDX, nu.SCRATCH = orig_res, orig_scratch
        shutil.rmtree(scratch_res, ignore_errors=True)
        shutil.rmtree(scratch_union, ignore_errors=True)
    return U


def build_or_load_qqq_panel(U, px_union):
    panel_path = OUT_DIR / "panel_ml3_qqq_union.parquet"
    if panel_path.exists():
        X_union = pd.read_parquet(panel_path)
        X_union["mkt_ret12_x_beta"] = X_union["mkt_ret12"] * X_union["beta_12m"]
        X_union["mkt_vol3m_x_vol"] = X_union["mkt_vol3m"] * X_union["vol_3m"]
        return X_union

    daily, P, form = U["daily"], U["P"], U["form"]
    # Reuse S&P 500 rows from panel_ml3_full.parquet and only compute NDX-only rows, then combine!
    sp_panel = pd.read_parquet(OUT_DIR / "panel_ml3_full.parquet")
    sp_panel["mkt_ret12_x_beta"] = sp_panel["mkt_ret12"] * sp_panel["beta_12m"]
    sp_panel["mkt_vol3m_x_vol"] = sp_panel["mkt_vol3m"] * sp_panel["vol_3m"]
    sp_panel["in_sp"] = True
    sp_panel["in_ndx"] = [s in U["members_nd"].get(t, set()) for t, s in zip(sp_panel.t, sp_panel.ticker)]

    # Identify NDX-only eligible (t, ticker) pairs
    eng_nd = bt.Engine(P, daily, U["members"], U["secP"], form)
    ndx_only_rows = []
    sec_mean_map = {}
    for t in form:
        df_elig, _ = eng_nd.eligible(t, 12)
        if df_elig.empty:
            continue
        sec_mean = df_elig.groupby("sector").mom.transform("mean")
        for s in df_elig.index:
            sec_mean_map[(t, s)] = (df_elig.at[s, "sector"], float(sec_mean[s]), float(df_elig.at[s, "mom"]))
            if s not in U["members_sp"].get(t, set()) and s in U["members_nd"].get(t, set()):
                ndx_only_rows.append((t, s))

    print(f"   Building 78 PIT features for {len(ndx_only_rows)} NDX-only stock-months...", flush=True)
    pf, px_m = mlf.price_features(daily, P, form)
    smooth, _, _ = ef.price_extras(daily, P, form)

    # Scratch fundamentals root combining fundamentals + fundamentals_ndx inside OUT_DIR
    f_root = OUT_DIR / "_scratch_fund_ndx"
    shutil.rmtree(f_root, ignore_errors=True)
    fd = f_root / "data" / "fundamentals"
    os.makedirs(fd / "pit_long", exist_ok=True)
    a_ep = pd.read_parquet(SSM_DIR / "data" / "fundamentals" / "eps_quarterly_pit.parquet")
    b_ep = pd.read_parquet(SSM_DIR / "data" / "fundamentals_ndx" / "eps_quarterly_pit.parquet")
    b_ep = b_ep[~b_ep.cik.isin(set(a_ep.cik.dropna()))]
    pd.concat([a_ep, b_ep], ignore_index=True).to_parquet(fd / "eps_quarterly_pit.parquet", index=False)
    for src_sub in ["fundamentals", "fundamentals_ndx"]:
        d_p = SSM_DIR / "data" / src_sub / "pit_long"
        for fn in sorted(os.listdir(d_p)):
            if fn.endswith(".parquet"):
                os.symlink(d_p / fn, fd / "pit_long" / f"{src_sub}_{fn}")

    t2c = ne.t2c_map()
    keep_dirs = (mlf.HERE, ef.HERE, fs.HERE)
    try:
        mlf.HERE = ef.HERE = fs.HERE = str(f_root)
        F_pan = mlf.fundamental_panel(form).set_index(["t", "cik"])
        Q_pan = ef.quarterly_factors(form).set_index(["cik", "t"])
        grid_nd = pd.DataFrame(ndx_only_rows, columns=["t", "ticker"])
        grid_nd["cik"] = [ne.cik_at(t2c.get(s, []), t) for t, s in zip(grid_nd.t, grid_nd.ticker)]
        grid_nd.loc[[c is not None and not cik_valid(s, t) for t, s, c in zip(grid_nd.t, grid_nd.ticker, grid_nd.cik)], "cik"] = np.nan
        N_pan = fs.build_new(grid_nd.dropna(subset=["cik"]))
        H4_pan = mf.history_features(form, root=str(f_root))
        H8_pan = build_8q_extra_from_root(form, str(f_root))
    finally:
        mlf.HERE, ef.HERE, fs.HERE = keep_dirs
        shutil.rmtree(f_root, ignore_errors=True)

    # Assemble NDX-only panel
    res = bt.load_resolutions()
    records = []
    for t, s, c in zip(grid_nd.t, grid_nd.ticker, grid_nd.cik):
        sec, sec_m, mom12 = sec_mean_map.get((t, s), ("Unknown", np.nan, np.nan))
        rec = {
            "t": t,
            "ticker": s,
            "cik": c,
            "sector": sec,
            "sector_mom": sec_m,
            "mom_12_1_secrel": mom12 - sec_m if np.isfinite(mom12) and np.isfinite(sec_m) else np.nan,
            "in_sp": False,
            "in_ndx": True,
        }
        for k, v in pf.items():
            rec[k] = v.at[t, s] if s in v.columns else np.nan
        rec["smooth"] = smooth.at[t, s] if s in smooth.columns else np.nan
        rec["mom_accel"] = rec["mom_3_1"] - rec["mom_12_1"] * 3.0 / 11.0 if np.isfinite(rec.get("mom_3_1", np.nan)) and np.isfinite(rec.get("mom_12_1", np.nan)) else np.nan

        if pd.notna(c):
            ci = int(c)
            if (t, ci) in F_pan.index:
                f_row = F_pan.loc[(t, ci)]
                price = px_m.at[t, s] if s in px_m.columns else np.nan
                for k in ["eps_g", "eps_g_m5", "eps_g_sym", "margin", "margin_chg", "rev_g", "sue", "days_since_filing"]:
                    rec[k] = f_row[k]
                rec["deps_p"] = f_row["deps"] / price if price and price > 0 else np.nan
                rec["ep"] = f_row["eps_diluted_approx_ttm_adj"] / price if price and price > 0 else np.nan
                sh = f_row["diluted_shares_adj"]
                rec["log_mcap"] = np.log(sh * price) if np.isfinite(sh) and sh > 0 and price and price > 0 else np.nan
            if (ci, t) in Q_pan.index:
                for k in ["eps_accel", "rev_g_q", "rev_accel", "gm_chg", "rd_int"]:
                    rec[k] = Q_pan.at[(ci, t), k]

        r_oo, st_oo = px_union.ret(t, s, res)
        rec["ret_oo"] = r_oo
        rec["status_oo"] = st_oo
        records.append(rec)

    X_nd = pd.DataFrame(records)
    N_pan["cik"] = N_pan.cik.astype(float)
    X_nd = X_nd.merge(N_pan, on=["t", "cik"], how="left")
    mcap = np.exp(X_nd.log_mcap)
    X_nd["sp"] = X_nd.revenue_ttm / mcap
    X_nd["bm"] = X_nd.equity / mcap
    X_nd["div_yield"] = X_nd["div"] / mcap
    X_nd["buyback_yield"] = X_nd.rep / mcap
    X_nd["cfo_yield"] = X_nd.cfo / mcap
    X_nd = X_nd.drop(columns=["revenue_ttm", "equity", "div", "rep", "cfo"])

    # Attach EAR and ear_sum4
    E_nd = ear_mod.ear_events(daily, X_nd)
    X_nd = ear_mod.attach(X_nd, E_nd)

    # Attach market context and dv_ratio
    ctx = sp_panel[["t", "mkt_ret12", "mkt_above200", "mkt_vol3m"]].drop_duplicates("t")
    X_nd = X_nd.merge(ctx, on="t", how="left")

    dvr = {}
    for v_dir, r_dir in [(SSM_DIR / "data" / "raw_volume", SSM_DIR / "data" / "raw"), (SSM_DIR / "data" / "raw_ndx", SSM_DIR / "data" / "raw_ndx")]:
        if not v_dir.exists():
            continue
        for fn in os.listdir(v_dir):
            if fn.endswith(".json") and not fn.startswith("_"):
                j = json.load(open(v_dir / fn))
                if "volume" not in j or not j["volume"]:
                    continue
                r_obj = j if "close" in j else (json.load(open(r_dir / fn)) if (r_dir / fn).exists() else None)
                if r_obj is None or "close" not in r_obj:
                    continue
                v_s = pd.Series([x if x is not None else np.nan for x in j["volume"]], index=pd.to_datetime(j["dates"]), dtype=float)
                c_s = pd.Series([x if x is not None else np.nan for x in r_obj["close"]], index=pd.to_datetime(r_obj["dates"]), dtype=float)
                dv = (v_s * c_s.reindex(v_s.index)).dropna()
                if len(dv) >= 180:
                    dvr[fn[:-5]] = dv.rolling(63, min_periods=40).median() / dv.rolling(252, min_periods=180).median()
    DVR = pd.DataFrame(dvr)
    dpos = DVR.index.searchsorted(form, side="right") - 1
    DVR_m = DVR.iloc[dpos].set_axis(form)
    X_nd["dv_ratio"] = [DVR_m.at[t, s] if s in DVR_m.columns else np.nan for t, s in zip(X_nd.t, X_nd.ticker)]

    H4_pan["cik"] = H4_pan.cik.astype(float)
    H8_pan["cik"] = H8_pan.cik.astype(float)
    X_nd = X_nd.merge(H4_pan, on=["t", "cik"], how="left")
    X_nd = X_nd.merge(H8_pan, on=["t", "cik"], how="left")
    X_nd["mkt_ret12_x_beta"] = X_nd["mkt_ret12"] * X_nd["beta_12m"]
    X_nd["mkt_vol3m_x_vol"] = X_nd["mkt_vol3m"] * X_nd["vol_3m"]

    # Combine S&P 500 + NDX-only
    common_cols = [c for c in sp_panel.columns if c in X_nd.columns] + ["in_sp", "in_ndx"]
    common_cols = list(dict.fromkeys(common_cols))
    X_union = pd.concat([sp_panel[common_cols], X_nd[common_cols]], ignore_index=True)
    X_union = X_union.sort_values(["t", "mom_12_1", "ticker"], ascending=[True, False, True]).reset_index(drop=True)
    X_union["mom_rank_union"] = X_union.groupby("t").cumcount() + 1

    # Also compute within-QQQ momentum rank
    X_union["mom_rank_qqq"] = np.nan
    qqq_mask = X_union["in_ndx"].astype(bool)
    X_union.loc[qqq_mask, "mom_rank_qqq"] = (
        X_union[qqq_mask].sort_values(["t", "mom_12_1", "ticker"], ascending=[True, False, True]).groupby("t").cumcount() + 1
    )

    X_union.to_parquet(panel_path, index=False)
    return X_union


# ==============================================================================
# PART 2: BUILD OR LOAD IWM / SMALL-MID-CAP TOP-50 & FULL PANEL
# ==============================================================================
class SmallCapOpenPrices:
    """Open-to-open holding returns for Small/Mid-Cap universe (uses Yahoo raw_open, WIKI adj_open, or next-session close fallback)."""
    def __init__(self, A, P, src):
        self.A, self.P = A, P
        self.close1 = bt.Prices(A, P, 1)
        self.sess = A["SPY"].dropna().index
        self.used_open, self.used_close = 0, 0

        # Build Open matrix for columns in A where Yahoo raw_open or WIKI wiki_open exists
        O = pd.DataFrame(np.nan, index=A.index, columns=A.columns)
        od = SSM_DIR / "data" / "raw_open"
        W = pd.read_parquet(SSM_DIR / "data" / "wiki_bulk" / "wiki_open.parquet")
        wiki = {t: g.set_index("date").adj_open for t, g in W.groupby("ticker")}

        for s in A.columns:
            sc = str(src.get(s, ""))
            if sc == "wiki" and s in wiki:
                x = wiki[s]
                O[s] = x[~x.index.duplicated(keep="last")].reindex(A.index).where(A[s].notna())
            elif (od / f"{s}.json").exists():
                j = json.load(open(od / f"{s}.json"))
                x = pd.Series(j["adj_open"], index=pd.to_datetime(j["dates"]), dtype=float)
                O[s] = x[~x.index.duplicated(keep="last")].reindex(A.index).where(A[s].notna())
        self.O = O

    def _next_session(self, t):
        i = self.sess.searchsorted(t, side="right")
        return self.sess[i] if i < len(self.sess) else None

    def ret(self, t, s, res):
        r1, st = self.close1.ret(t, s, res)
        if st != "ok":
            return r1, st
        d0 = self._next_session(t)
        d1 = self._next_session(t + pd.offsets.MonthEnd(1))
        if d0 is None or d1 is None or s not in self.O.columns:
            self.used_close += 1
            return r1, st
        o0, o1 = self.O.at[d0, s], self.O.at[d1, s]
        seg = bt.SEG_D
        same = seg is None or s not in seg.columns or seg.at[d0, s] == seg.at[d1, s]
        if np.isfinite(o0) and np.isfinite(o1) and o0 > 0 and same:
            self.used_open += 1
            return float(o1 / o0 - 1.0), "ok"
        self.used_close += 1
        return r1, st


def build_or_load_iwm_smallcap_panel():
    panel_path = OUT_DIR / "panel_ml3_iwm_top50.parquet"
    form = pd.date_range("2010-12-31", "2026-08-31", freq="ME")
    os.environ["STRICT"] = "0"
    A, P, U, mom, src = wh.load(form)
    px_sc = SmallCapOpenPrices(A, P, src)
    S_sc = {
        "px": px_sc,
        "res": bt.load_resolutions(),
        "daily": A,
        "rf": bt.load_rf(pd.date_range("2009-01-31", "2026-10-31", freq="ME")),
    }
    if panel_path.exists():
        return pd.read_parquet(panel_path), S_sc, U, mom

    print("   Building 78-feature PIT panel for Small/Mid-Cap (IWM) Top-50 Momentum Pool...", flush=True)
    # Load pre-built price features from features_holdout.parquet
    Xh = pd.read_parquet(SSM_DIR / "results" / "winners_holdout" / "features_holdout.parquet")
    Xh = Xh[Xh.t >= "2010-12-31"].copy()
    Xh = Xh.sort_values(["t", "mom_12_1", "ticker"], ascending=[True, False, True]).reset_index(drop=True)
    Xh["mom_rank"] = Xh.groupby("t").cumcount() + 1

    # Take Top-50 per month for the Small/Mid-Cap Momentum Pool (9,450 stock-months)
    D_sc = Xh[Xh.mom_rank <= 50].copy().reset_index(drop=True)

    # Re-populate PIT SEC fundamentals (Set B + Set C4 + Set C8) on D_sc from fundamentals + fundamentals_smallcap
    f_root = OUT_DIR / "_scratch_fund_iwm"
    shutil.rmtree(f_root, ignore_errors=True)
    fd = f_root / "data" / "fundamentals"
    os.makedirs(fd / "pit_long", exist_ok=True)
    a_ep = pd.read_parquet(SSM_DIR / "data" / "fundamentals" / "eps_quarterly_pit.parquet")
    b_ep = pd.read_parquet(SSM_DIR / "data" / "fundamentals_smallcap" / "eps_quarterly_pit.parquet")
    b_ep = b_ep[~b_ep.cik.isin(set(a_ep.cik.dropna()))]
    pd.concat([a_ep, b_ep], ignore_index=True).to_parquet(fd / "eps_quarterly_pit.parquet", index=False)
    for src_sub in ["fundamentals", "fundamentals_smallcap"]:
        d_p = SSM_DIR / "data" / src_sub / "pit_long"
        for fn in sorted(os.listdir(d_p)):
            if fn.endswith(".parquet"):
                os.symlink(d_p / fn, fd / "pit_long" / f"{src_sub}_{fn}")

    pos = A.index.searchsorted(form, side="right") - 1
    px_m = A.iloc[pos].set_axis(form)

    keep_dirs = (mlf.HERE, ef.HERE, fs.HERE)
    try:
        mlf.HERE = ef.HERE = fs.HERE = str(f_root)
        F_pan = mlf.fundamental_panel(form).set_index(["t", "cik"])
        Q_pan = ef.quarterly_factors(form).set_index(["cik", "t"])
        N_pan = fs.build_new(D_sc[["t", "cik"]].dropna(subset=["cik"]))
        H4_pan = mf.history_features(form, root=str(f_root))
        H8_pan = build_8q_extra_from_root(form, str(f_root))
    finally:
        mlf.HERE, ef.HERE, fs.HERE = keep_dirs
        shutil.rmtree(f_root, ignore_errors=True)

    # Drop blanked fundamental columns from D_sc before merging fresh PIT fundamentals
    drop_f = [c for c in D_sc.columns if c not in ["t", "ticker", "cik", "mom_rank", "dist_sma200", "dist_sma50", "dist_52wh", "vol_3m", "vol_12m", "beta_12m", "maxret_1m", "mom_12_1", "mom_6_1", "mom_3_1", "rev_1m", "smooth", "mom_accel"]]
    D_sc = D_sc.drop(columns=drop_f)

    fcols = ["eps_g", "eps_g_m5", "eps_g_sym", "margin", "margin_chg", "rev_g", "sue", "days_since_filing"]
    for k in fcols + ["deps_p", "ep", "log_mcap", "eps_accel", "rev_g_q", "rev_accel", "gm_chg", "rd_int"]:
        D_sc[k] = np.nan

    for i in range(len(D_sc)):
        c = D_sc.cik.iat[i]
        if pd.isna(c):
            continue
        ci = int(c)
        t = D_sc.t.iat[i]
        s = D_sc.ticker.iat[i]
        if (t, ci) in F_pan.index:
            f_row = F_pan.loc[(t, ci)]
            price = px_m.at[t, s] if s in px_m.columns else np.nan
            for k in fcols:
                D_sc.iat[i, D_sc.columns.get_loc(k)] = f_row[k]
            if price and price > 0:
                D_sc.iat[i, D_sc.columns.get_loc("deps_p")] = f_row["deps"] / price
                D_sc.iat[i, D_sc.columns.get_loc("ep")] = f_row["eps_diluted_approx_ttm_adj"] / price
                sh = f_row["diluted_shares_adj"]
                if np.isfinite(sh) and sh > 0:
                    D_sc.iat[i, D_sc.columns.get_loc("log_mcap")] = np.log(sh * price)
        if (ci, t) in Q_pan.index:
            for k in ["eps_accel", "rev_g_q", "rev_accel", "gm_chg", "rd_int"]:
                D_sc.iat[i, D_sc.columns.get_loc(k)] = Q_pan.at[(ci, t), k]

    N_pan["cik"] = N_pan.cik.astype(float)
    D_sc = D_sc.merge(N_pan, on=["t", "cik"], how="left")
    mcap = np.exp(D_sc.log_mcap)
    D_sc["sp"] = D_sc.revenue_ttm / mcap
    D_sc["bm"] = D_sc.equity / mcap
    D_sc["div_yield"] = D_sc["div"] / mcap
    D_sc["buyback_yield"] = D_sc.rep / mcap
    D_sc["cfo_yield"] = D_sc.cfo / mcap
    D_sc = D_sc.drop(columns=["revenue_ttm", "equity", "div", "rep", "cfo"])

    # Attach EAR & ear_sum4 from earnings_dates.csv
    E_sc = ear_mod.ear_events(A, D_sc)
    D_sc = ear_mod.attach(D_sc, E_sc)

    # Attach market context & dv_ratio from daily_dv.parquet
    sp_panel = pd.read_parquet(OUT_DIR / "panel_ml3_full.parquet")
    ctx = sp_panel[["t", "mkt_ret12", "mkt_above200", "mkt_vol3m"]].drop_duplicates("t")
    D_sc = D_sc.merge(ctx, on="t", how="left")

    DV = pd.read_parquet(SSM_DIR / "data" / "smallcap" / "daily_dv.parquet").reindex(index=A.index)
    DVR = DV.rolling(63, min_periods=40).median() / DV.rolling(252, min_periods=180).median()
    DVR_m = DVR.iloc[pos].set_axis(form)
    D_sc["dv_ratio"] = [DVR_m.at[t, s] if s in DVR_m.columns else np.nan for t, s in zip(D_sc.t, D_sc.ticker)]
    D_sc["sector_mom"] = D_sc.groupby("t")["mom_12_1"].transform("mean")
    D_sc["mom_12_1_secrel"] = D_sc["mom_12_1"] - D_sc["sector_mom"]

    H4_pan["cik"] = H4_pan.cik.astype(float)
    H8_pan["cik"] = H8_pan.cik.astype(float)
    D_sc = D_sc.merge(H4_pan, on=["t", "cik"], how="left")
    D_sc = D_sc.merge(H8_pan, on=["t", "cik"], how="left")
    D_sc["mkt_ret12_x_beta"] = D_sc["mkt_ret12"] * D_sc["beta_12m"]
    D_sc["mkt_vol3m_x_vol"] = D_sc["mkt_vol3m"] * D_sc["vol_3m"]

    res = bt.load_resolutions()
    lab = [px_sc.ret(t, s, res) for t, s in zip(D_sc.t, D_sc.ticker)]
    D_sc["ret_oo"] = [r for r, _ in lab]
    D_sc["status_oo"] = [st for _, st in lab]

    D_sc.to_parquet(panel_path, index=False)
    return D_sc, S_sc, U, mom


_POOL_RANK_CACHE = {}
_POOL_DISC_CACHE = {}


def _get_pool_ranks(df):
    key = (len(df), str(df.ticker.iat[0]), str(df.ticker.iat[-1]))
    if key not in _POOL_RANK_CACHE:
        D = df.copy().reset_index(drop=True)
        R = ranked(D, SET_C8_ALL, fill=False)
        y = D.groupby("t").ret_oo.rank(pct=True) - 0.5
        _POOL_RANK_CACHE[key] = (D, R, y)
    return _POOL_RANK_CACHE[key]


def _get_pool_disc(key, Y, tr, val, cols, n_keep, R_src, y_src):
    dkey = (key, Y, n_keep)
    if dkey not in _POOL_DISC_CACHE:
        _POOL_DISC_CACHE[dkey] = in_sample_feature_discovery(tr, val, cols, n_keep, R_src, y_src)
    return _POOL_DISC_CACHE[dkey]


def run_pool_walk_forward(
    D_target,
    S_target,
    kind,
    cols,
    k,
    val_criterion="val_cagr",
    auto_discover=False,
    D_train_source=None,
):
    """
    Runs nested walk-forward on `D_target` (or transfers from `D_train_source` if provided).
    """
    D_base, R_target, y_target = _get_pool_ranks(D_target)
    D = D_base.copy()

    if D_train_source is not None:
        D_src, R_src, y_src = _get_pool_ranks(D_train_source)
        src_key = (len(D_src), str(D_src.ticker.iat[0]), str(D_src.ticker.iat[-1]))
    else:
        D_src, R_src, y_src = D, R_target, y_target
        src_key = (len(D), str(D.ticker.iat[0]), str(D.ticker.iat[-1]))

    D["score"] = np.nan
    min_c = 50 if D.groupby("t").size().median() <= 40 else (100 if D.groupby("t").size().median() <= 110 else 200)
    param_grid = [{"num_leaves": 7, "min_child_samples": min_c}, {"num_leaves": 15, "min_child_samples": min_c}] if kind == "lgbm" else [{"alpha": 1.0}, {"alpha": 10.0}, {"alpha": 100.0}]

    for Y in TEST_YEARS:
        tr_start = pd.Timestamp("2011-01-31")
        tr_end = pd.Timestamp(f"{Y - 3}-11-30")
        val = D_src[(D_src.t.dt.year >= Y - 2) & (D_src.t.dt.year <= Y - 1) & D_src.ret_oo.notna()]
        tr = D_src[(D_src.t >= tr_start) & (D_src.t <= tr_end) & D_src.ret_oo.notna()]
        te = D[D.t.dt.year == Y]
        if te.empty or tr.empty:
            continue

        if val_criterion == "fixed_nl7":
            best_params = param_grid[0] if kind == "lgbm" else param_grid[1]
            best_cols = _get_pool_disc(src_key, Y, tr, val, cols, 55, R_src, y_src) if auto_discover else cols
        else:
            best_params, best_cols, best_v = None, None, -np.inf
            cand_subsets = [
                ("C4_Core_57", SET_C4),
                ("AutoTop50", _get_pool_disc(src_key, Y, tr, val, cols, 50, R_src, y_src)),
                ("AutoTop60", _get_pool_disc(src_key, Y, tr, val, cols, 60, R_src, y_src)),
            ] if auto_discover else [("FixedSet", cols)]

            for _, use_cols in cand_subsets:
                for params in param_grid:
                    v = val.copy()
                    v["s"] = fit_predict_model(kind, params, tr, v, use_cols, True, R_src, y_src)
                    if val_criterion == "val_cagr" and D_train_source is None:
                        c = m2.net_cagr(S_target, m2.topk_weights(v, "s", k))
                    else:
                        v["r_rk"] = y_src.loc[v.index]
                        c = float(v.sort_values(["t", "s"], ascending=[True, False]).groupby("t").head(5)["r_rk"].mean())
                    if c > best_v:
                        best_params, best_cols, best_v = params, use_cols, c

        tr2 = D_src[(D_src.t >= tr_start) & (D_src.t <= pd.Timestamp(f"{Y - 1}-11-30")) & D_src.ret_oo.notna()]
        # Fit on tr2 (R_src) and predict on te (R_target)
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
        if tkey in _POOL_DISC_CACHE:
            D.loc[te.index, "score"] = _POOL_DISC_CACHE[tkey]
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
            _POOL_DISC_CACHE[tkey] = pred_te
            D.loc[te.index, "score"] = pred_te

    return D


def main():
    print("==================================================================", flush=True)
    print("PART 1: QQQ (NASDAQ-100 PIT CONSTITUENTS) & S&P 500 U QQQ ML3 TEST", flush=True)
    print("==================================================================", flush=True)
    U = setup_qqq_union_isolated()
    O_union = m2.build_opens(U["daily"])
    px_union = m2.OpenPrices(U["daily"], U["P"], O_union)
    S_union = {
        "px": px_union,
        "res": bt.load_resolutions(),
        "daily": U["daily"],
        "rf": bt.load_rf(pd.date_range("2009-01-31", "2026-10-31", freq="ME")),
    }
    X_union = build_or_load_qqq_panel(U, px_union)
    X_qqq = X_union[X_union["in_ndx"].astype(bool)].copy().reset_index(drop=True)
    print(f"   QQQ PIT Panel: {len(X_qqq)} stock-months, median {int(X_qqq.groupby('t').size().median())} stocks/month.", flush=True)

    qqq_pools = [
        ("QQQ_Top30", X_qqq[X_qqq.mom_rank_qqq <= 30].copy()),
        ("QQQ_Top50", X_qqq[X_qqq.mom_rank_qqq <= 50].copy()),
        ("QQQ_Full100", X_qqq.copy()),
        ("SP500_Union_QQQ_Top50", X_union[X_union.mom_rank_union <= 50].copy()),
    ]

    qqq_strategies = {}
    form_test = sorted(X_qqq[(X_qqq.t.dt.year >= 2015) & (X_qqq.t.dt.year <= 2026)].t.unique())
    qqq_strategies["BENCH__QQQ_ETF__BuyHold"] = load_etf_monthly_returns("QQQ", form_test, S_union)
    qqq_strategies["BENCH__SPY_ETF__BuyHold"] = wt.run_weights(S_union, {t: {"SPY": 1.0} for t in form_test}).loc["2015-01-31":"2026-09-30"]

    # Pure Momentum benchmarks on QQQ and SP500 U QQQ
    for p_name, D_p in [("QQQ", X_qqq), ("SP500_Union_QQQ", X_union)]:
        rk_col = "mom_rank_qqq" if p_name == "QQQ" else "mom_rank_union"
        sub_p = D_p[(D_p.t.dt.year >= 2015) & (D_p.t.dt.year <= 2026)]
        for k in (1, 3):
            W_m = {t: {s_: 1.0 / k for s_ in g.sort_values([rk_col, "ticker"]).ticker.head(k)} for t, g in sub_p.groupby("t")}
            qqq_strategies[f"{p_name}__T0_Pure_Momentum_12_1__Top{k}"] = (W_m, S_union)

    qqq_model_specs = [
        ("T1_SetA_Price_Only", "lgbm", SET_A, "val_cagr", False),
        ("T2_SetB_Price_Plus_Snapshot", "lgbm", SET_B, "val_cagr", False),
        ("T3a_SetC4_Trajectory_Core", "lgbm", SET_C4, "val_cagr", False),
        ("T3b_SetC8_Summary_Slopes_68", "lgbm", SET_C8_SUMMARY, "val_cagr", False),
        ("T3S_InSample_Feature_Discovery", "lgbm", SET_C8_ALL, "val_cagr", True),
        ("T3a_SetC4_ZeroCAGRPeek_RankVal", "lgbm", SET_C4, "val_rank", False),
        ("T3a_SetC4_ZeroTune_FixedNL7", "lgbm", SET_C4, "fixed_nl7", False),
        ("T3a_SetC4_Trajectory_Core", "ridge", SET_C4, "val_cagr", False),
    ]

    for pool_name, D_pool in qqq_pools:
        for tier_name, kind, cols, val_crit, auto_disc in qqq_model_specs:
            # Run full grid on QQQ_Top30 and QQQ_Top50; core tiers on QQQ_Full100 and SP500_Union_QQQ_Top50
            if pool_name in ("QQQ_Full100", "SP500_Union_QQQ_Top50") and tier_name not in (
                "T1_SetA_Price_Only",
                "T2_SetB_Price_Plus_Snapshot",
                "T3a_SetC4_Trajectory_Core",
                "T3S_InSample_Feature_Discovery",
            ):
                continue
            for k in (1, 3):
                sname = f"{pool_name}__{tier_name}__{kind}__Top{k}"
                D_res = run_pool_walk_forward(D_pool, S_union, kind, cols, k, val_criterion=val_crit, auto_discover=auto_disc)
                W = m2.topk_weights(D_res[(D_res.t.dt.year >= 2015) & (D_res.t.dt.year <= 2026)], "score", k)
                qqq_strategies[sname] = (W, S_union)
                print(f"   Done QQQ: {sname}", flush=True)

    # Evaluate QQQ summary table
    qqq_periods = [
        ("OOS_2019_2026.09 (93m, 8 Folds)", "2019-01-31", "2026-09-30"),
        ("OOS_2015_2026.09 (141m, 12 Folds)", "2015-01-31", "2026-09-30"),
        ("Sub_2015_2019 (60m)", "2015-01-31", "2019-12-31"),
        ("Sub_2020_2022 (36m)", "2020-01-31", "2022-12-31"),
        ("Sub_2023_2026.09 (45m)", "2023-01-31", "2026-09-30"),
    ]
    qqq_rows = []
    qqq_ledgers = {}
    for name, item in qqq_strategies.items():
        if isinstance(item, pd.DataFrame):
            df_base = item
            df_s30 = item
            df_s100 = item
        else:
            W, S_obj = item
            df_base = wt.run_weights(S_obj, W, stress=None).loc["2015-01-31":"2026-09-30"]
            df_s30 = wt.run_weights(S_obj, W, stress=-0.30).loc["2015-01-31":"2026-09-30"]
            df_s100 = wt.run_weights(S_obj, W, stress=-1.00).loc["2015-01-31":"2026-09-30"]
        qqq_ledgers[name] = df_base
        safe_fn = "".join(c if c.isalnum() else "_" for c in name) + ".csv"
        df_base.to_csv(LEDGER_DIR / safe_fn)
        for p_label, s_dt, e_dt in qqq_periods:
            r30 = df_s30.loc[s_dt:e_dt].net.dropna()
            r100 = df_s100.loc[s_dt:e_dt].net.dropna()
            c30 = float((1.0 + r30).prod() ** (12.0 / len(r30)) - 1.0) if len(r30) else np.nan
            c100 = float((1.0 + r100).prod() ** (12.0 / len(r100)) - 1.0) if len(r100) else np.nan
            rec = compute_period_metrics(S_union, df_base, p_label, s_dt, e_dt, stress_cagr_30=c30, stress_cagr_100=c100)
            rec["strategy"] = name
            qqq_rows.append(rec)

    df_qqq_sum = pd.DataFrame(qqq_rows)[[
        "strategy", "period", "months", "CAGR_pct", "Vol_pct", "Sharpe", "Sortino",
        "MaxDD_Monthly_pct", "MaxDD_Daily_pct", "Calmar", "Avg_Monthly_Turnover_pct",
        "Win_Rate_pct", "Stress_m30_CAGR_pct", "Stress_m100_CAGR_pct",
    ]]
    df_qqq_sum.to_csv(OUT_DIR / "ml3_qqq_summary_table.csv", index=False)

    print("\n==================================================================", flush=True)
    print("PART 2: IWM (SMALL/MID-CAP PIT UNIVERSE) ML3 TEST", flush=True)
    print("==================================================================", flush=True)
    D_sc, S_sc, U_sc, mom_sc = build_or_load_iwm_smallcap_panel()
    D_sc["mkt_ret12_x_beta"] = D_sc["mkt_ret12"] * D_sc["beta_12m"]
    D_sc["mkt_vol3m_x_vol"] = D_sc["mkt_vol3m"] * D_sc["vol_3m"]
    sp_panel = pd.read_parquet(OUT_DIR / "panel_ml3_full.parquet")
    sp_panel["mkt_ret12_x_beta"] = sp_panel["mkt_ret12"] * sp_panel["beta_12m"]
    sp_panel["mkt_vol3m_x_vol"] = sp_panel["mkt_vol3m"] * sp_panel["vol_3m"]
    D_sp50 = sp_panel[sp_panel.mom_rank <= 50].copy().reset_index(drop=True)
    print(f"   IWM Top-50 PIT Panel: {len(D_sc)} stock-months across {D_sc.t.nunique()} formation months.", flush=True)

    iwm_strategies = {}
    iwm_strategies["BENCH__IWM_ETF__BuyHold"] = load_etf_monthly_returns("IWM", form_test, S_sc)
    # Equal-weight Small/Mid-Cap Holdout Universe benchmark
    W_ew_sc = {t: {s_: 1.0 / len(U_sc[t]) for s_ in U_sc[t]} for t in form_test if U_sc.get(t)}
    iwm_strategies["BENCH__IWM_EqualWeight_Universe"] = (W_ew_sc, S_sc)

    sub_sc_test = D_sc[(D_sc.t.dt.year >= 2015) & (D_sc.t.dt.year <= 2026)]
    for k in (1, 3, 5):
        W_m = {t: {s_: 1.0 / k for s_ in g.sort_values(["mom_rank", "ticker"]).ticker.head(k)} for t, g in sub_sc_test.groupby("t")}
        iwm_strategies[f"IWM_Top50__T0_Pure_Momentum_12_1__Top{k}"] = (W_m, S_sc)

    iwm_specs = [
        # Mode A: Trained In-Universe on IWM Top-50
        ("InUniverse_Train", "T1_SetA_Price_Only_NoCIKSurv", "lgbm", SET_A, "val_cagr", False, None),
        ("InUniverse_Train", "T2_SetB_Price_Plus_Snapshot", "lgbm", SET_B, "val_cagr", False, None),
        ("InUniverse_Train", "T3a_SetC4_Trajectory_Core", "lgbm", SET_C4, "val_cagr", False, None),
        ("InUniverse_Train", "T3S_InSample_Feature_Discovery", "lgbm", SET_C8_ALL, "val_cagr", True, None),
        ("InUniverse_Train", "T3a_SetC4_ZeroCAGRPeek_RankVal", "lgbm", SET_C4, "val_rank", False, None),
        ("InUniverse_Train", "T1_SetA_Price_Only_NoCIKSurv", "ridge", SET_A, "val_cagr", False, None),
        ("InUniverse_Train", "T3a_SetC4_Trajectory_Core", "ridge", SET_C4, "val_cagr", False, None),
        # Mode B: Zero-Shot Transfer from S&P 500 Top-50 (Trained ONLY on S&P 500 -> Applied to IWM Top-50)
        ("TransferFromSP500", "T1_SetA_Price_Only_NoCIKSurv", "lgbm", SET_A, "val_rank", False, D_sp50),
        ("TransferFromSP500", "T2_SetB_Price_Plus_Snapshot", "lgbm", SET_B, "val_rank", False, D_sp50),
        ("TransferFromSP500", "T3a_SetC4_Trajectory_Core", "lgbm", SET_C4, "val_rank", False, D_sp50),
    ]

    for mode_tag, tier_name, kind, cols, val_crit, auto_disc, src_df in iwm_specs:
        for k in (1, 3, 5):
            sname = f"IWM_Top50__{mode_tag}__{tier_name}__{kind}__Top{k}"
            D_res = run_pool_walk_forward(
                D_sc,
                S_sc,
                kind,
                cols,
                k,
                val_criterion=val_crit,
                auto_discover=auto_disc,
                D_train_source=src_df,
            )
            W = m2.topk_weights(D_res[(D_res.t.dt.year >= 2015) & (D_res.t.dt.year <= 2026)], "score", k)
            iwm_strategies[sname] = (W, S_sc)
            print(f"   Done IWM: {sname}", flush=True)

    iwm_periods = [
        ("OOS_2019_2026.09 (93m, 8 Folds)", "2019-01-31", "2026-09-30"),
        ("OOS_2015_2026.09 (141m, 12 Folds)", "2015-01-31", "2026-09-30"),
        ("WIKI_DelistComplete_2015_2018.02 (38m)", "2015-01-31", "2018-02-28"),
        ("Sub_2020_2022 (36m)", "2020-01-31", "2022-12-31"),
        ("Sub_2023_2026.09 (45m)", "2023-01-31", "2026-09-30"),
    ]
    iwm_rows = []
    for name, item in iwm_strategies.items():
        if isinstance(item, pd.DataFrame):
            df_base = item
            df_s30 = item
            df_s100 = item
        else:
            W, S_obj = item
            df_base = wt.run_weights(S_obj, W, stress=None).loc["2015-01-31":"2026-09-30"]
            df_s30 = wt.run_weights(S_obj, W, stress=-0.30).loc["2015-01-31":"2026-09-30"]
            df_s100 = wt.run_weights(S_obj, W, stress=-1.00).loc["2015-01-31":"2026-09-30"]
        safe_fn = "".join(c if c.isalnum() else "_" for c in name) + ".csv"
        df_base.to_csv(LEDGER_DIR / safe_fn)
        for p_label, s_dt, e_dt in iwm_periods:
            r30 = df_s30.loc[s_dt:e_dt].net.dropna()
            r100 = df_s100.loc[s_dt:e_dt].net.dropna()
            c30 = float((1.0 + r30).prod() ** (12.0 / len(r30)) - 1.0) if len(r30) else np.nan
            c100 = float((1.0 + r100).prod() ** (12.0 / len(r100)) - 1.0) if len(r100) else np.nan
            rec = compute_period_metrics(S_sc, df_base, p_label, s_dt, e_dt, stress_cagr_30=c30, stress_cagr_100=c100)
            rec["strategy"] = name
            iwm_rows.append(rec)

    df_iwm_sum = pd.DataFrame(iwm_rows)[[
        "strategy", "period", "months", "CAGR_pct", "Vol_pct", "Sharpe", "Sortino",
        "MaxDD_Monthly_pct", "MaxDD_Daily_pct", "Calmar", "Avg_Monthly_Turnover_pct",
        "Win_Rate_pct", "Stress_m30_CAGR_pct", "Stress_m100_CAGR_pct",
    ]]
    df_iwm_sum.to_csv(OUT_DIR / "ml3_iwm_summary_table.csv", index=False)

    print("\n================ QQQ SUMMARY (OOS 2019-2026.09 & 2015-2026.09) ================", flush=True)
    p_q = df_qqq_sum[df_qqq_sum.period.isin(["OOS_2019_2026.09 (93m, 8 Folds)", "OOS_2015_2026.09 (141m, 12 Folds)"])]
    print(p_q[["strategy", "period", "CAGR_pct", "Sharpe", "MaxDD_Daily_pct", "Stress_m100_CAGR_pct"]].to_string(index=False), flush=True)

    print("\n================ IWM SUMMARY (OOS 2019-2026.09, 2015-2026.09, & WIKI 2015-2018.02) ================", flush=True)
    p_i = df_iwm_sum[df_iwm_sum.period.isin([
        "OOS_2019_2026.09 (93m, 8 Folds)",
        "OOS_2015_2026.09 (141m, 12 Folds)",
        "WIKI_DelistComplete_2015_2018.02 (38m)",
    ])]
    print(p_i[["strategy", "period", "CAGR_pct", "Sharpe", "MaxDD_Daily_pct", "Stress_m100_CAGR_pct"]].to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
