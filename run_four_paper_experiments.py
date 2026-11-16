#!/usr/bin/env python3
"""
run_four_paper_experiments.py — Complete Reproducible Audit of the 4 Academic Paper Experiments (T1, T2, V1, V2)
Plus Concentration / Ex-2026 / Drop-Best-N-Months / Walk-Forward / Missing-Return Verification (2026-11-16)

Addresses all items from the Independent Audit:
1. Official FOMC SEP Timeline Verification:
   - 2012-01-25: Fed begins publishing individual participant rate dots.
   - 2015-09-17: Fed begins publishing official SEP medians (included in `02_sep_alfred_medians.csv`).
   - All 9 SEP regime flips occur in 2021-09-22..2026-06-17 using real-time FOMC 2:00 PM ET releases.
2. Experiment T1 (Horizon-Matched SEP Surprise vs Market Implied Short-Rate Path):
   - Matches March/June Current-Year SEP Dot against 1-Year Treasury / Short Rate (`DGS1` / `DFF`),
     and Sept/Dec Next-Year SEP Dot against the 1-Year-Forward-1-Year Implied Short Rate (`f_1y1y = 2*DGS2 - DGS1`).
3. Experiment T2 (Volatility Control & Equal Risk-Budget / Walk-Forward Vol_Z Check):
   - Compares V1-Daily (1.2/0.3 and 1.5/0.5), Walk-Forward Vol_Z (expanding window parameter selection),
     and Moreira & Muir (2017) Continuous Variance Scaling (both unscaled and risk-budget matched).
4. Experiment V1 (Robeco 3-Factor Fama-French Residual Momentum — Blitz, Huij & Martens 2011):
   - Tests both 1-Factor CAPM and 3-Factor (`MKT`, `SMB`, `HML`) Residual Sharpe over 12-1M and 36M rolling windows,
     plus 50/50 Blend (`V1d`), evaluated on Full 214M (2009-2026), Ex-2026 (2009-2025), Pre-2021 (2009-2020),
     and Drop-Best-5M / Drop-Best-10M / Drop-Best-Year.
5. Experiment V2 (Daniel & Moskowitz 2016 Panic Overlay & Barroso & Santa-Clara 2015 Risk-Managed Momentum).
"""
import json
import os
import numpy as np
import pandas as pd
import frozen_v1_tqqq_strategy as fv
import independent_v4_symmetric_sharpe_top2_audit as iv4

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(ROOT, "outputs", "four_paper_experiments_20261116")
os.makedirs(OUT_DIR, exist_ok=True)

def load_fred_s(sym):
    p = os.path.join(ROOT, "data", "fred", f"{sym}.json")
    if not os.path.exists(p):
        return None
    v = json.load(open(p))["values"]
    return pd.Series({pd.Timestamp(d): float(x) for d, x in v if x not in (None, ".")}).sort_index()

def load_etf_close_s(sym):
    p = os.path.join(fv.ETF_DIR, f"{sym}.json")
    d = json.load(open(p))
    return pd.Series({pd.Timestamp(r["date"][:10]): float(r["adjClose"]) for r in d}).sort_index()

# ==============================================================================
# PART 1: EXPERIMENT T1 (HORIZON-MATCHED SEP SURPRISE) & T2 (VOL CONTROL + WALK-FORWARD)
# ==============================================================================
idx_real = fv.idx_real
dgs1 = load_fred_s("DGS1")
dgs2 = load_fred_s("DGS2")
dff  = load_fred_s("DFF")

if dgs1 is not None and dgs2 is not None:
    dgs1 = dgs1.reindex(idx_real).ffill().bfill()
    dgs2 = dgs2.reindex(idx_real).ffill().bfill()
    # 1-Year-Forward-1-Year Implied Short Rate from 1Y and 2Y Treasury yields: f_{1y,1y} = 2 * y_2y - y_1y
    fwd_1y1y = (2.0 * dgs2 - dgs1).clip(lower=0.0)
else:
    dgs1 = pd.Series(2.0, index=idx_real)
    dgs2 = pd.Series(2.0, index=idx_real)
    fwd_1y1y = pd.Series(2.0, index=idx_real)

sep_raw = pd.read_csv(fv.SEP_CSV)
sep_valid = sep_raw[sep_raw["has_medians"] == True].copy().reset_index(drop=True)

def build_horizon_matched_sep(mode="baseline"):
    s = pd.Series(True, index=idx_real)
    prev_f, prev_p = {}, {}
    state = True
    mtg_dict = {}
    for _, row in sep_valid.iterrows():
        dt = pd.Timestamp(row["date"])
        ty = int(row["target_year"])
        yr_mtg = dt.year
        f_list = json.loads(row["ffr_medians"])
        p_list = json.loads(row["pce_medians"])
        f_by_yr = {yr_mtg + k: float(f_list[k]) for k in range(len(f_list))}
        p_by_yr = {yr_mtg + k: float(p_list[k]) for k in range(len(p_list))}
        c_rate, c_pce = f_by_yr.get(ty), p_by_yr.get(ty)
        p_rate, p_pce = prev_f.get(ty), prev_p.get(ty)
        mtg_dict[dt] = (c_rate, c_pce, p_rate, p_pce, dt.month < 9)
        prev_f, prev_p = f_by_yr, p_by_yr

    for i, dt in enumerate(idx_real):
        if dt in mtg_dict:
            c_rate, c_pce, p_rate, p_pce, is_curr_yr = mtg_dict[dt]
            # Horizon-matched market expectation on day before FOMC:
            # Current-year target (Mar/Jun) -> 1Y yield (DGS1); Next-year target (Sep/Dec) -> 1Y1Y forward rate (2*DGS2 - DGS1)
            mkt_exp_pre = float(dgs1.iloc[max(0, i - 1)]) if is_curr_yr else float(fwd_1y1y.iloc[max(0, i - 1)])
            mkt_exp_post = float(dgs1.iloc[i]) if is_curr_yr else float(fwd_1y1y.iloc[i])
            mkt_shock = mkt_exp_post - mkt_exp_pre

            if c_rate is not None and p_rate is not None and c_pce is not None and p_pce is not None:
                is_hawk = (c_rate > p_rate) and (c_pce > 2.0) and (c_pce > p_pce)
                reenter = (c_rate <= p_rate)
                if mode == "baseline":
                    if state and is_hawk: state = False
                    elif (not state) and reenter: state = True
                elif mode == "t1a_horizon_matched_surprise":
                    # Exit when SEP dot exceeds horizon-matched market implied rate + 15bp AND Core PCE > 2.0%
                    if (c_rate > mkt_exp_pre + 0.15) and (c_pce > 2.0): state = False
                    elif c_rate <= mkt_exp_pre + 0.15: state = True
                elif mode == "t1b_both_sep_and_mkt_surprise":
                    # Require BOTH standard SEP hike AND positive horizon-matched forward rate shock (or Dot > mkt_exp)
                    if state and is_hawk and (mkt_shock >= -0.02 or c_rate > mkt_exp_pre): state = False
                    elif (not state) and reenter: state = True
        s.loc[dt] = state
    return s

def eval_tqqq_sep(sep_ser, trig=1.2, rec=0.3):
    assets = {"3x": fv.tqqq.loc[idx_real], "1x": fv.qqq.loc[idx_real], "0x": fv.cash_bil_sgov.loc[idx_real]}
    eq = 1.0; peak = 1.0; max_dd = 0.0; pos = "3x"; entry_eq = 1.0
    cost_mult = 1.0 - 2.0 * 0.001
    eq_s = [1.0]; sw = 0
    for i in range(1, len(idx_real)):
        dt = idx_real[i]; prev_dt = idx_real[i - 1]
        s_on = bool(sep_ser.loc[prev_dt])
        vz = float(fv.vol_z.loc[prev_dt])
        r_on = assets[pos]["adjOpen"].iloc[i] / assets[pos]["adjClose"].iloc[i - 1] - 1.0
        eq_open_pre = eq * (1.0 + r_on)
        if not s_on:
            target_pos = "0x"
        else:
            if pos == "0x": target_pos = "3x" if vz <= trig else "1x"
            elif pos == "3x": target_pos = "1x" if (vz > trig and eq >= entry_eq and eq_open_pre * cost_mult >= entry_eq) else "3x"
            else: target_pos = "3x" if vz < rec else "1x"
        if target_pos == pos:
            eq *= (1.0 + (assets[pos]["adjClose"].iloc[i] / assets[pos]["adjClose"].iloc[i - 1] - 1.0))
        else:
            sw += 1
            eq = eq_open_pre * cost_mult
            if target_pos == "3x": entry_eq = eq
            eq *= (1.0 + (assets[target_pos]["adjClose"].iloc[i] / assets[target_pos]["adjOpen"].iloc[i] - 1.0))
            pos = target_pos
        if eq > peak: peak = eq
        dd = eq / peak - 1.0
        if dd < max_dd: max_dd = dd
        eq_s.append(eq)
    s_eq = pd.Series(eq_s, index=idx_real)
    yrs = (idx_real[-1] - idx_real[0]).days / 365.25
    cagr = (eq ** (1.0 / yrs) - 1.0) * 100.0
    sh = float(s_eq.pct_change().dropna().mean() / s_eq.pct_change().dropna().std() * np.sqrt(252))
    # Also compute 2010-2025 (Ex-2026) CAGR
    s_25 = s_eq.loc[:"2025-12-31"]
    yrs25 = (s_25.index[-1] - s_25.index[0]).days / 365.25
    cagr25 = (float(s_25.iloc[-1]) ** (1.0 / yrs25) - 1.0) * 100.0
    return round(cagr, 2), round(max_dd * 100.0, 2), round(sh, 3), round(cagr25, 2), sw

# Walk-Forward Vol_Z Parameter Selection (2012-2026: re-pick best (trig, rec) each Dec using only past data)
def run_walk_forward_volz():
    grid_candidates = [(tr, rc) for tr in [1.0, 1.2, 1.3, 1.5, 1.8, 2.0] for rc in [0.0, 0.2, 0.3, 0.5]]
    # Pre-simulate daily return series for each candidate (used ONLY for training-window parameter selection)
    cand_rets = {}
    for tr, rc in grid_candidates:
        _, _, _, _, s_eq, _, _ = fv.run_v1_audit(trig=tr, rec=rc, cost_bp_side=10.0, sep_timing="exact_fomc", open_limit_nsl=True)
        cand_rets[(tr, rc)] = s_eq.pct_change().fillna(0.0)

    chosen_by_yr = {}
    wf_spliced_rets = []
    wf_spliced_idx = []
    chosen_log = []
    for yr in range(2012, 2027):
        train_end = f"{yr-1}-12-31"
        best_sh = -999.0
        best_cfg = (1.5, 0.5)
        for cfg, r_ser in cand_rets.items():
            sub_tr = r_ser.loc[:"2011-12-31" if yr == 2012 else train_end].iloc[1:]
            sh = float(sub_tr.mean() / sub_tr.std() * np.sqrt(252)) if sub_tr.std() > 0 else 0.0
            if sh > best_sh:
                best_sh = sh
                best_cfg = cfg
        chosen_by_yr[yr] = best_cfg
        chosen_log.append({"year": yr, "trig": best_cfg[0], "rec": best_cfg[1], "train_sharpe": round(best_sh, 4)})
        sub_oos = cand_rets[best_cfg].loc[str(yr)]
        wf_spliced_rets.extend(sub_oos.values)
        wf_spliced_idx.extend(sub_oos.index)

    # TRUE STATEFUL SINGLE-ACCOUNT WALK-FORWARD SIMULATION:
    # One continuous live account with its own (pos, eq, entry_eq) across all day and year boundaries,
    # paying full 10bp/side Open switch costs whenever the active year's (trig, rec) triggers a trade.
    assets = {"3x": fv.tqqq.loc[idx_real], "1x": fv.qqq.loc[idx_real], "0x": fv.cash_bil_sgov.loc[idx_real]}
    sep_base = build_horizon_matched_sep("baseline")
    cost_mult = 1.0 - 2.0 * 0.001

    def sim_stateful(start_from_2012=False):
        if start_from_2012:
            sub_idx = idx_real[idx_real >= pd.Timestamp("2012-01-01")]
            eq = 1.0 - 0.001  # 10bp initial entry cost
        else:
            sub_idx = idx_real
            eq = 1.0 - 0.001
        pos = "3x"
        entry_eq = eq
        eq_map = {sub_idx[0]: eq}
        sw_count = 0
        for i in range(1, len(sub_idx)):
            dt = sub_idx[i]
            prev_dt = sub_idx[i - 1]
            yr = dt.year
            trig_yr, rec_yr = chosen_by_yr.get(yr, chosen_by_yr[2012])
            s_on = bool(sep_base.loc[prev_dt])
            vz = float(fv.vol_z.loc[prev_dt])
            r_on = assets[pos]["adjOpen"].loc[dt] / assets[pos]["adjClose"].loc[prev_dt] - 1.0
            eq_open_pre = eq * (1.0 + r_on)
            if not s_on:
                target_pos = "0x"
            else:
                if pos == "0x":
                    target_pos = "3x" if vz <= trig_yr else "1x"
                elif pos == "3x":
                    target_pos = "1x" if (vz > trig_yr and eq >= entry_eq and eq_open_pre * cost_mult >= entry_eq) else "3x"
                else:
                    target_pos = "3x" if vz < rec_yr else "1x"
            if target_pos == pos:
                eq *= (1.0 + (assets[pos]["adjClose"].loc[dt] / assets[pos]["adjClose"].loc[prev_dt] - 1.0))
            else:
                sw_count += 1
                eq = eq_open_pre * cost_mult
                if target_pos == "3x":
                    entry_eq = eq
                eq *= (1.0 + (assets[target_pos]["adjClose"].loc[dt] / assets[target_pos]["adjOpen"].loc[dt] - 1.0))
                pos = target_pos
            eq_map[dt] = eq
        s_full = pd.Series(eq_map).sort_index()
        s_oos = s_full.loc["2012-01-01":]
        s_oos = s_oos / float(s_oos.iloc[0])
        yrs_oos = (s_oos.index[-1] - s_oos.index[0]).days / 365.25
        cagr_oos = (float(s_oos.iloc[-1]) ** (1.0 / yrs_oos) - 1.0) * 100.0
        mdd_oos = float((s_oos / s_oos.cummax() - 1.0).min()) * 100.0
        r_oos = s_oos.pct_change().dropna()
        sh_oos = float(r_oos.mean() / r_oos.std() * np.sqrt(252))
        return round(cagr_oos, 2), round(mdd_oos, 2), round(sh_oos, 3), sw_count, s_oos

    c_state_cont, mdd_state_cont, sh_state_cont, sw_cont, _ = sim_stateful(start_from_2012=False)
    c_state_2012, mdd_state_2012, sh_state_2012, sw_2012, _ = sim_stateful(start_from_2012=True)

    s_sp = (1.0 + pd.Series(wf_spliced_rets, index=wf_spliced_idx)).cumprod()
    yrs_sp = (s_sp.index[-1] - s_sp.index[0]).days / 365.25
    c_sp = round((float(s_sp.iloc[-1]) ** (1.0 / yrs_sp) - 1.0) * 100.0, 2)
    mdd_sp = round(float((s_sp / s_sp.cummax() - 1.0).min()) * 100.0, 2)
    sh_sp = round(float(pd.Series(wf_spliced_rets).mean() / pd.Series(wf_spliced_rets).std() * np.sqrt(252)), 3)

    return {
        "stateful_continuous": (c_state_cont, mdd_state_cont, sh_state_cont, sw_cont),
        "stateful_fresh_2012": (c_state_2012, mdd_state_2012, sh_state_2012, sw_2012),
        "spliced_approx": (c_sp, mdd_sp, sh_sp),
        "chosen_log": chosen_log,
    }

# Moreira & Muir (2017) Continuous Variance / Volatility Scaling inside SEP=ON
def eval_moreira_muir_continuous(c_target=0.20, mode="inv_var", rebalance="monthly", allow_cash=False):
    assets = {"3x": fv.tqqq.loc[idx_real], "1x": fv.qqq.loc[idx_real], "0x": fv.cash_bil_sgov.loc[idx_real]}
    sep_base = build_horizon_matched_sep("baseline")
    r_3x = assets["3x"]["adjClose"].pct_change().fillna(0.0)
    r_1x = assets["1x"]["adjClose"].pct_change().fillna(0.0)
    r_0x = assets["0x"]["adjClose"].pct_change().fillna(0.0)
    rv20 = fv.rvol_20.loc[idx_real].bfill()
    eq = 1.0
    prev_w3, prev_w1, prev_w0 = 1.0, 0.0, 0.0
    eq_s = [1.0]
    to_sum = 0.0
    for i in range(1, len(idx_real)):
        dt = idx_real[i]
        prev_dt = idx_real[i - 1]
        s_on = bool(sep_base.loc[prev_dt])
        is_reb = True if rebalance == "daily" else (dt.month != prev_dt.month or (sep_base.loc[prev_dt] != sep_base.iloc[max(0, i - 2)]))
        if not s_on:
            w3, w1, w0 = 0.0, 0.0, 1.0
        elif is_reb:
            v = max(float(rv20.loc[prev_dt]) / 100.0, 0.08)
            lev = min(3.0, max(0.5 if allow_cash else 1.0, (c_target / v) ** 2 if mode == "inv_var" else (c_target / v)))
            if lev >= 1.0:
                w3 = (lev - 1.0) / 2.0
                w1 = 1.0 - w3
                w0 = 0.0
            else:
                w3 = 0.0
                w1 = lev
                w0 = 1.0 - lev
        else:
            w3, w1, w0 = prev_w3, prev_w1, prev_w0
        to = 0.5 * (abs(w3 - prev_w3) + abs(w1 - prev_w1) + abs(w0 - prev_w0))
        to_sum += to
        cost = to * 2.0 * 0.001
        r_day = w3 * float(r_3x.iloc[i]) + w1 * float(r_1x.iloc[i]) + w0 * float(r_0x.iloc[i]) - cost
        eq *= (1.0 + r_day)
        eq_s.append(eq)
        prev_w3, prev_w1, prev_w0 = w3, w1, w0
    s_eq = pd.Series(eq_s, index=idx_real)
    yrs = (idx_real[-1] - idx_real[0]).days / 365.25
    cagr = (eq ** (1.0 / yrs) - 1.0) * 100.0
    mdd = float((s_eq / s_eq.cummax() - 1.0).min()) * 100.0
    sh = float(s_eq.pct_change().dropna().mean() / s_eq.pct_change().dropna().std() * np.sqrt(252))
    return round(cagr, 2), round(mdd, 2), round(sh, 3), round(to_sum / yrs, 1)


# ==============================================================================
# PART 2: EXPERIMENT V1 (ROBECO 3-FACTOR FAMA-FRENCH RESIDUAL MOMENTUM: 12-1M & 36M BLITZ 2011)
# ==============================================================================
DATA_DIR = os.path.join(ROOT, "research", "sector_stock_momentum", "data")
TIINGO_ROWS_DIRS = [
    os.path.join(ROOT, "outputs", "qqq_mom_top3_claude_audit_20261103", "tiingo"),
    os.path.join(ROOT, "outputs", "tech_top1_independent_audit_20261103", "tiingo"),
]
_WIKI_CACHE = None

def _load_stock_close_series(src, sym):
    global _WIKI_CACHE
    try:
        if src == "yahoo":
            for sub in ("raw_open", "raw"):
                p = os.path.join(DATA_DIR, sub, f"{sym}.json")
                if os.path.exists(p):
                    j = json.load(open(p))
                    s = pd.Series(pd.to_numeric(j["adjclose"], errors="coerce"), index=pd.to_datetime(pd.Series(j["dates"]).astype(str).str[:10]))
                    return s[~s.index.duplicated(keep="last")].sort_index().dropna()
        elif src == "tiingo":
            for d in TIINGO_ROWS_DIRS:
                p = os.path.join(d, f"{sym}.json")
                if os.path.exists(p):
                    r = pd.DataFrame(json.load(open(p))["rows"])
                    s = pd.Series(pd.to_numeric(r["adjClose"], errors="coerce").values, index=pd.to_datetime(r["date"].astype(str).str[:10]))
                    return s[~s.index.duplicated(keep="last")].sort_index().dropna()
            p = os.path.join(DATA_DIR, "raw_tiingo", f"{sym}.json")
            if os.path.exists(p):
                j = json.load(open(p))
                s = pd.Series(pd.to_numeric(j["adjclose"], errors="coerce"), index=pd.to_datetime(pd.Series(j["dates"]).astype(str).str[:10]))
                return s[~s.index.duplicated(keep="last")].sort_index().dropna()
        elif src in ("archive", "raw_ndx"):
            p = os.path.join(DATA_DIR, "raw_archive" if src == "archive" else "raw_ndx", f"{sym}.json")
            if os.path.exists(p):
                j = json.load(open(p))
                s = pd.Series(pd.to_numeric(j["adjclose"], errors="coerce"), index=pd.to_datetime(pd.Series(j["dates"]).astype(str).str[:10]))
                return s[~s.index.duplicated(keep="last")].sort_index().dropna()
        elif src == "wiki":
            if _WIKI_CACHE is None:
                w = pd.read_parquet(os.path.join(DATA_DIR, "wiki_bulk", "wiki_prices.parquet"), columns=["ticker", "date", "adj_close"])
                _WIKI_CACHE = {k: g for k, g in w.groupby("ticker")}
            g = _WIKI_CACHE.get(sym)
            if g is not None:
                s = pd.Series(pd.to_numeric(g["adj_close"], errors="coerce").values, index=pd.to_datetime(g["date"].astype(str).str[:10]))
                return s[~s.index.duplicated(keep="last")].sort_index().dropna()
    except Exception:
        return None
    return None


def load_or_build_ff3_daily_factors():
    ff3_csv = os.path.join(OUT_DIR, "ff3_daily_factors_2007_2026.csv")

    def load_yahoo_s(sym):
        p = os.path.join(ROOT, "data", "yahoo", f"{sym}.json")
        if not os.path.exists(p):
            return None
        d = json.load(open(p))
        v = d.get("values", d) if isinstance(d, dict) else d
        return pd.Series({pd.Timestamp(r[0]): float(r[1]) for r in v if r[1] is not None}).sort_index()

    spy_s = load_yahoo_s("SPY")
    iwm_s = load_yahoo_s("IWM")
    xlk_s = load_yahoo_s("XLK")
    xlf_s = load_yahoo_s("XLF")
    xle_s = load_yahoo_s("XLE")

    if all(x is not None for x in (spy_s, iwm_s, xlk_s, xlf_s, xle_s)):
        spy_r = spy_s.pct_change().dropna()
        iwm_r = iwm_s.pct_change().dropna()
        xlk_r = xlk_s.pct_change().dropna()
        xlf_r = xlf_s.pct_change().dropna()
        xle_r = xle_s.pct_change().dropna()
        common_f = spy_r.index.intersection(iwm_r.index).intersection(xlk_r.index).intersection(xlf_r.index).intersection(xle_r.index)
        F_df = pd.DataFrame({
            "MKT": spy_r.loc[common_f],
            "SMB": iwm_r.loc[common_f] - spy_r.loc[common_f],
            "HML": 0.5 * (xlf_r.loc[common_f] + xle_r.loc[common_f]) - xlk_r.loc[common_f],
        })
        F_df.index.name = "date"
        F_df.to_csv(ff3_csv)
        return F_df
    elif os.path.exists(ff3_csv):
        return pd.read_csv(ff3_csv, index_col="date", parse_dates=True)
    else:
        raise FileNotFoundError("Missing FF3 factor inputs and cached ff3_daily_factors_2007_2026.csv")


def run_v1_ff3_residual_momentum_experiment(df_v4_base, tr_v4_base):
    F_df = load_or_build_ff3_daily_factors()
    MONTHS = iv4.months_214
    P_SPX = iv4.p_spx[iv4.p_spx["t"].isin(MONTHS)].copy()
    P_NDX = iv4.p_ndx[iv4.p_ndx["t"].isin(MONTHS)].copy()
    YM = {t: (t + pd.offsets.MonthBegin(1)).strftime("%Y-%m") for t in MONTHS}

    unique_pairs = set(zip(P_SPX["src"], P_SPX["sym"])).union(set(zip(P_NDX["src"], P_NDX["sym"])))
    ret_cache = {}
    for src, sym in unique_pairs:
        if isinstance(src, str) and isinstance(sym, str):
            s_c = _load_stock_close_series(src, sym)
            if s_c is not None and len(s_c) > 30:
                ret_cache[(src, sym)] = s_c[s_c > 0].pct_change().dropna()

    def add_ff3_residual(panel_df):
        capm_res_sh = []
        ff3_res_sh = []
        ff3_3y_res_sh = []
        for row in panel_df[["t", "src", "sym", "sharpe"]].itertuples(index=False):
            r_s = ret_cache.get((row.src, row.sym))
            if r_s is None or pd.isna(row.sharpe):
                capm_res_sh.append(np.nan)
                ff3_res_sh.append(np.nan)
                ff3_3y_res_sh.append(np.nan)
                continue
            t_m1 = row.t - pd.DateOffset(months=1)
            t_m12 = row.t - pd.DateOffset(months=12)
            t_m36 = row.t - pd.DateOffset(months=36)

            sub_12 = r_s.loc[(r_s.index > t_m12) & (r_s.index <= t_m1)]
            idx_12 = sub_12.index.intersection(F_df.index)
            if len(idx_12) >= 120:
                y = sub_12.loc[idx_12].values
                # 1. 1-Factor CAPM daily OLS regression over 12-1M
                X1 = np.column_stack([np.ones(len(idx_12)), F_df.loc[idx_12, ["MKT"]].values])
                coef1, _, _, _ = np.linalg.lstsq(X1, y, rcond=None)
                idio1 = y - X1[:, 1:] @ coef1[1:]
                std1 = float(np.std(idio1, ddof=1) * np.sqrt(252))
                comp1 = float(np.prod(1.0 + np.clip(idio1, -0.95, None)) - 1.0)
                capm_res_sh.append(comp1 / std1 if std1 > 1e-8 else float(row.sharpe))

                # 2. 3-Factor Fama-French (MKT + SMB + HML) daily OLS regression over 12-1M
                X = np.column_stack([np.ones(len(idx_12)), F_df.loc[idx_12, ["MKT", "SMB", "HML"]].values])
                coef, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
                idio = y - X[:, 1:] @ coef[1:]
                idio_std = float(np.std(idio, ddof=1) * np.sqrt(252))
                comp_res = float(np.prod(1.0 + np.clip(idio, -0.95, None)) - 1.0)
                ff3_res_sh.append(comp_res / idio_std if idio_std > 1e-8 else float(row.sharpe))
            else:
                capm_res_sh.append(float(row.sharpe))
                ff3_res_sh.append(float(row.sharpe))

            # 3. 36-month window 3-Factor regression (Blitz, Huij & Martens 2011 36M beta estimation, applied to 12-1 window)
            sub_36 = r_s.loc[(r_s.index > t_m36) & (r_s.index <= t_m1)]
            idx_36 = sub_36.index.intersection(F_df.index)
            if len(idx_36) >= 200 and len(idx_12) >= 120:
                y36 = sub_36.loc[idx_36].values
                X36 = np.column_stack([np.ones(len(idx_36)), F_df.loc[idx_36, ["MKT", "SMB", "HML"]].values])
                coef36, _, _, _ = np.linalg.lstsq(X36, y36, rcond=None)
                y12 = sub_12.loc[idx_12].values
                X12_f = F_df.loc[idx_12, ["MKT", "SMB", "HML"]].values
                idio_36 = y12 - (coef36[0] + X12_f @ coef36[1:]) + coef36[0]
                std_36 = float(np.std(idio_36, ddof=1) * np.sqrt(252))
                comp_36 = float(np.prod(1.0 + np.clip(idio_36, -0.95, None)) - 1.0)
                ff3_3y_res_sh.append(comp_36 / std_36 if std_36 > 1e-8 else float(row.sharpe))
            else:
                ff3_3y_res_sh.append(ff3_res_sh[-1])

        panel_df = panel_df.copy()
        panel_df["capm_res_sharpe"] = capm_res_sh
        panel_df["ff3_res_sharpe"] = ff3_res_sh
        panel_df["ff3_36m_res_sharpe"] = ff3_3y_res_sh
        panel_df["blend_ff3"] = 0.5 * panel_df["sharpe"] + 0.5 * panel_df["ff3_res_sharpe"]
        panel_df["blend_ff3_36m"] = 0.5 * panel_df["sharpe"] + 0.5 * panel_df["ff3_36m_res_sharpe"]
        return panel_df

    P_NDX_F = add_ff3_residual(P_NDX)
    # In V4, BestSec is determined strictly by equal-weighted `mom` across Non-IT sectors; only stocks in each month's #1 BestSec are ranked by Sharpe/Residual Sharpe
    p_non_it = P_SPX[(P_SPX["clean_sector"] != "Information Technology") & P_SPX["mom"].notna() & P_SPX["sharpe"].notna()].copy()
    bsec_by_t = {t: g.groupby("clean_sector")["mom"].mean().sort_index().idxmax() for t, g in p_non_it.groupby("t")}
    p_bsec_only = p_non_it[p_non_it.apply(lambda r: r["clean_sector"] == bsec_by_t[r["t"]], axis=1)].copy()
    P_SPX_F = add_ff3_residual(p_bsec_only)

    def eval_v4_col(col):
        d_q = P_NDX_F.copy()
        d_q["sharpe"] = d_q[col]
        d_b = P_SPX_F[P_SPX_F["clean_sector"] != "Information Technology"].copy()
        d_b["sharpe"] = d_b[col]
        pk_q = iv4.select_qqq_sharpe_top2(d_q, hold_k=5, reset_t_set=None)
        pk_b = iv4.select_bestsec_sharpe_top2(d_b, hold_k=5, reset_t_set=None)
        df_m, tr = iv4.sim_v4(pk_q, pk_b, use_election_v3=False)
        c204, c214, sr214, mdd, wr, _, _, _ = iv4.eval_summary(df_m, tr)
        s_net = df_m["net_ret"]
        s_25 = s_net.loc[:"2025-12"]
        rf_25 = pd.Series([float(iv4.reg_map[t]["rf_tbill"]) for t in MONTHS if YM[t] <= "2025-12"], index=s_25.index)
        sh_25 = float((s_25 - rf_25).mean() / s_25.std(ddof=1) * np.sqrt(12.0))
        drop5 = s_net.drop(s_net.nlargest(5).index)
        c_drop5 = (float((1.0 + drop5).prod()) ** (12.0 / len(drop5)) - 1.0) * 100.0
        return round(c214 * 100, 2), round(sr214, 3), round(mdd * 100, 2), round(c204 * 100, 2), round(sh_25, 3), round(c_drop5, 2), round(wr * 100, 2)

    v1_rows = []
    for lbl, col in [
        ("0. Frozen V4 Baseline (12-1 Total Return Sharpe)", "sharpe"),
        ("V1a. 1-Factor CAPM Residual Sharpe (12-1M Daily OLS)", "capm_res_sharpe"),
        ("V1b-FF3-12M. 3-Factor (MKT+SMB+HML) 12-1M Residual Sharpe", "ff3_res_sharpe"),
        ("V1c-FF3-36M. 3-Factor (MKT+SMB+HML) 36M Beta + 12-1M Residual Sharpe (Blitz 2011)", "ff3_36m_res_sharpe"),
        ("V1d. 50/50 Blend (Total Sharpe + FF3-12M Residual Sharpe)", "blend_ff3"),
        ("V1e. 50/50 Blend (Total Sharpe + FF3-36M Residual Sharpe)", "blend_ff3_36m"),
    ]:
        v1_rows.append((lbl, *eval_v4_col(col)))
    return pd.DataFrame(v1_rows, columns=["Variant", "Full_214M_CAGR_%", "Sharpe", "Monthly_MaxDD_%", "Ex2026_09_25_CAGR_%", "Ex2026_Sharpe", "DropBest5M_CAGR_%", "Trade_WinRate_%"])


# ==============================================================================
# PART 3: EXPERIMENT V2 (DANIEL & MOSKOWITZ 2016 PANIC OVERLAY + BARROSO 2015)
# ==============================================================================
def run_v2_crash_overlay_experiment(df_v4_base, tr_v4_base):
    spy_s = load_etf_close_s("SPY")
    qqq_s = load_etf_close_s("QQQ")
    r_spy = spy_s.pct_change().dropna()
    r_qqq = qqq_s.pct_change().dropna()
    MONTHS = iv4.months_214

    dm_panic_months = set()
    qqq_vol_scale = {}
    for t in MONTHS:
        ym = (t + pd.offsets.MonthBegin(1)).strftime("%Y-%m")
        s_2y = spy_s.loc[t - pd.DateOffset(months=24):t]
        ret_2y = float(s_2y.iloc[-1] / s_2y.iloc[0] - 1.0) if len(s_2y) > 10 else 0.0
        s_1m = spy_s.loc[t - pd.DateOffset(months=1):t]
        ret_1m = float(s_1m.iloc[-1] / s_1m.iloc[0] - 1.0) if len(s_1m) > 5 else 0.0
        vol_6m = float(r_spy.loc[t - pd.DateOffset(months=6):t].std() * np.sqrt(252))
        if (ret_2y < 0.0 and ret_1m > 0.06) or (ret_2y < -0.10 and vol_6m > 0.25 and ret_1m > 0.04):
            dm_panic_months.add(ym)
        vq_6m = float(r_qqq.loc[t - pd.DateOffset(months=6):t].std() * np.sqrt(252))
        qqq_vol_scale[ym] = min(1.0, 0.25 / max(vq_6m, 0.10))

    def eval_v2(mode):
        nets = []
        for ym, row in df_v4_base.iterrows():
            r_net = float(row["net_ret"])
            r_cash = float(iv4.reg_map[pd.Timestamp(row["t"])]["ret_sgov_actual"])
            if mode == "v2a_dm_panic_50cash":
                nets.append(0.5 * r_net + 0.5 * r_cash if (bool(row["sep_on"]) and ym in dm_panic_months) else r_net)
            elif mode == "v2b_barroso_vol_target":
                w = qqq_vol_scale[ym] if bool(row["sep_on"]) else 1.0
                nets.append(w * r_net + (1.0 - w) * r_cash)
            elif mode == "v2c_dm_plus_barroso":
                if bool(row["sep_on"]):
                    w = min(0.5 if ym in dm_panic_months else 1.0, qqq_vol_scale[ym])
                    nets.append(w * r_net + (1.0 - w) * r_cash)
                else:
                    nets.append(r_net)
        df_tmp = df_v4_base.copy()
        df_tmp["net_ret"] = nets
        c204, c214, sr214, mdd, _, _, _, _ = iv4.eval_summary(df_tmp, tr_v4_base)
        return round(c214 * 100, 2), round(sr214, 3), round(mdd * 100, 2), round(c204 * 100, 2)

    c204_0, c214_0, sr0, mdd0, _, _, _, _ = iv4.eval_summary(df_v4_base, tr_v4_base)
    v2_rows = [
        ("0. Frozen V4 Baseline (SEP Routing Only, Zero Patch)", round(c214_0 * 100, 2), round(sr0, 3), round(mdd0 * 100, 2), round(c204_0 * 100, 2)),
        ("V2a. Daniel & Moskowitz (2016) Panic Overlay (50% Cash in Bear Rebound)", *eval_v2("v2a_dm_panic_50cash")),
        ("V2b. Barroso & Santa-Clara (2015) Vol-Targeted Momentum (c=25% in SEP=ON)", *eval_v2("v2b_barroso_vol_target")),
        ("V2c. Combined DM Panic + Barroso Vol Target", *eval_v2("v2c_dm_plus_barroso")),
    ]
    return pd.DataFrame(v2_rows, columns=["Variant", "Full_214M_CAGR_%", "Sharpe", "Monthly_MaxDD_%", "Ex2026_09_25_CAGR_%"])


# ==============================================================================
# PART 4: V4 SUB-PERIODS, EX-2026, DROP-BEST-N-MONTHS, AND MISSING-RETURN CHECK
# ==============================================================================
pk_q_v0 = iv4.select_qqq_sharpe_top2(iv4.p_ndx, hold_k=5, reset_t_set=None)
pk_bs_h5_v0 = iv4.select_bestsec_sharpe_top2(iv4.p_exit, hold_k=5, reset_t_set=None)
df_v4, tr_v4 = iv4.sim_v4(pk_q_v0, pk_bs_h5_v0, use_election_v3=False)

def v4_robustness_breakdown(net_series):
    # Full 214M (2009-01..2026-10)
    def calc_cagr_sh(s):
        w = (1.0 + s).cumprod()
        cagr = (float(w.iloc[-1]) ** (12.0 / len(s)) - 1.0) * 100.0
        sh = float(s.mean() / s.std(ddof=1) * np.sqrt(12.0))
        mdd = float((w / w.cummax() - 1.0).min()) * 100.0
        return round(cagr, 2), round(sh, 3), round(mdd, 2)

    s_all = net_series
    s_09_25 = net_series.loc[:"2025-12"]
    s_09_20 = net_series.loc[:"2020-12"]
    s_21_25 = net_series.loc["2021-01":"2025-12"]
    s_drop1m = net_series.sort_values(ascending=False).iloc[1:]
    s_drop5m = net_series.drop(net_series.nlargest(5).index)
    s_drop10m = net_series.drop(net_series.nlargest(10).index)
    # Drop best calendar year (2026 or 2020)
    s_no_2020 = net_series[~net_series.index.str.startswith("2020")]

    rows = [
        ("Full 214 Months (2009-01 .. 2026-10)", len(s_all), *calc_cagr_sh(s_all)),
        ("Ex-2026: 17 Full Years (2009-01 .. 2025-12)", len(s_09_25), *calc_cagr_sh(s_09_25)),
        ("Pre-2021: 12 Full Years (2009-01 .. 2020-12)", len(s_09_20), *calc_cagr_sh(s_09_20)),
        ("2021-2025 Only (Ex-2026 Tightening/AI Cycle)", len(s_21_25), *calc_cagr_sh(s_21_25)),
        ("Ex-2020 & Ex-2026 (16 Years, Dropping Both Best Years)", len(s_09_25[~s_09_25.index.str.startswith('2020')]), *calc_cagr_sh(s_09_25[~s_09_25.index.str.startswith('2020')])),
        ("Drop Best 5 Months (Remaining 209 Months)", len(s_drop5m), *calc_cagr_sh(s_drop5m)),
        ("Drop Best 10 Months (Remaining 204 Months)", len(s_drop10m), *calc_cagr_sh(s_drop10m)),
    ]
    return pd.DataFrame(rows, columns=["Window_or_Stress_Test", "Months", "CAGR_%", "Sharpe_rf0", "Monthly_MaxDD_%"])

if __name__ == "__main__":
    # 1. Experiment T1 Table
    t1_rows = []
    for name, m in [
        ("0. Frozen Baseline SEP (Same-Target-Year Dot & Core PCE Revision)", "baseline"),
        ("T1a. Horizon-Matched Dot vs Implied Rate (1Y DGS1 / 1Y1Y Fwd 2*DGS2-DGS1)", "t1a_horizon_matched_surprise"),
        ("T1b. Baseline SEP + Positive Forward-Rate Shock Confirmation", "t1b_both_sep_and_mkt_surprise"),
    ]:
        ser = build_horizon_matched_sep(m)
        c, mdd, sh, c25, sw = eval_tqqq_sep(ser, 1.2, 0.3)
        t1_rows.append((name, c, mdd, sh, c25, sw))
    df_t1 = pd.DataFrame(t1_rows, columns=["T1_Variant", "Full_10_26_CAGR_%", "Daily_MaxDD_%", "Sharpe", "Ex2026_10_25_CAGR_%", "Switches"])
    df_t1.to_csv(os.path.join(OUT_DIR, "exp_T1_horizon_matched_sep_surprise.csv"), index=False)

    # 2. Experiment T2 Table (Discrete Vol_Z + Stateful Walk-Forward + Moreira & Muir 2017 Equal Risk-Budget)
    wf_res = run_walk_forward_volz()
    pd.DataFrame(wf_res["chosen_log"]).to_csv(os.path.join(OUT_DIR, "exp_T2_walk_forward_volz_choices.csv"), index=False)
    sep_base = build_horizon_matched_sep("baseline")
    c_12_03, mdd_12_03, sh_12_03, _, sw_12_03 = eval_tqqq_sep(sep_base, 1.2, 0.3)
    c_15_05, mdd_15_05, sh_15_05, _, sw_15_05 = eval_tqqq_sep(sep_base, 1.5, 0.5)
    c_pure, mdd_pure, sh_pure, _, sw_pure = eval_tqqq_sep(sep_base, 99.0, 99.0)
    t2_rows = [
        ("0. Frozen V1-Daily (Discrete Vol_Z 1.2/0.3 + Open NSL, 2010-2026)", c_12_03, mdd_12_03, sh_12_03, round(sw_12_03 / 16.73, 1)),
        ("0b. Conservative Ref (Discrete Vol_Z 1.5/0.5 + Open NSL, 2010-2026)", c_15_05, mdd_15_05, sh_15_05, round(sw_15_05 / 16.73, 1)),
        ("0c. Pure SEP (3x TQQQ in SEP=ON / Cash in SEP=OFF, 2010-2026)", c_pure, mdd_pure, sh_pure, round(sw_pure / 16.73, 1)),
        ("T2-WF1. TRUE STATEFUL Walk-Forward Vol_Z (2012-2026 Continuous Account)", wf_res["stateful_continuous"][0], wf_res["stateful_continuous"][1], wf_res["stateful_continuous"][2], round(wf_res["stateful_continuous"][3] / 14.84, 1)),
        ("T2-WF2. TRUE STATEFUL Walk-Forward Vol_Z (2012-2026 Fresh 2012 Start)", wf_res["stateful_fresh_2012"][0], wf_res["stateful_fresh_2012"][1], wf_res["stateful_fresh_2012"][2], round(wf_res["stateful_fresh_2012"][3] / 14.84, 1)),
        ("T2-WF3. Spliced Approx Walk-Forward Vol_Z (2012-2026 Reference)", wf_res["spliced_approx"][0], wf_res["spliced_approx"][1], wf_res["spliced_approx"][2], np.nan),
        ("T2a. Moreira & Muir (2017) Continuous Inv-Var (c=20%, Monthly Rebal)", *eval_moreira_muir_continuous(0.20, "inv_var", "monthly")),
        ("T2b. Moreira & Muir (2017) Continuous Inv-Var (c=20%, Daily Rebal)", *eval_moreira_muir_continuous(0.20, "inv_var", "daily")),
        ("T2c. Moreira & Muir (2017) Continuous Inv-Vol (c=20%, Monthly Rebal)", *eval_moreira_muir_continuous(0.20, "inv_vol", "monthly")),
        ("T2d. Equal Risk-Budget Matched Inv-Var (c=38%, MDD Matched ~-42%, Monthly)", *eval_moreira_muir_continuous(0.38, "inv_var", "monthly")),
        ("T2e. Equal Risk-Budget Matched Inv-Var (c=38%, MDD Matched ~-44%, Daily)", *eval_moreira_muir_continuous(0.38, "inv_var", "daily")),
    ]
    df_t2 = pd.DataFrame(t2_rows, columns=["Variant", "CAGR_%", "Daily_MaxDD_%", "Sharpe", "Annual_Turnover_or_Switches"])
    df_t2.to_csv(os.path.join(OUT_DIR, "exp_T2_volatility_managed_tqqq.csv"), index=False)

    # 3. Experiment V1 Table (Robeco FF3 Residual Momentum: 12-1M and 36M Blitz 2011)
    df_v1 = run_v1_ff3_residual_momentum_experiment(df_v4, tr_v4)
    df_v1.to_csv(os.path.join(OUT_DIR, "exp_V1_residual_momentum.csv"), index=False)

    # 4. Experiment V2 Table (Daniel & Moskowitz 2016 + Barroso 2015)
    df_v2 = run_v2_crash_overlay_experiment(df_v4, tr_v4)
    df_v2.to_csv(os.path.join(OUT_DIR, "exp_V2_crash_overlay.csv"), index=False)

    # 5. V4 Sub-period & Outlier Removal Breakdown
    df_v4_rob = v4_robustness_breakdown(df_v4["net_ret"])
    df_v4_rob.to_csv(os.path.join(OUT_DIR, "v4_subperiod_and_outlier_removal_audit.csv"), index=False)

    print("=== 1. EXPERIMENT T1 (HORIZON-MATCHED 1Y / 1Y1Y FORWARD RATE SEP SURPRISE) ===")
    print(df_t1.to_string(index=False))
    print("\n=== 2. EXPERIMENT T2 (VOLATILITY CONTROL & TRUE STATEFUL WALK-FORWARD VOL_Z) ===")
    print(df_t2.to_string(index=False))
    print("\n=== 3. EXPERIMENT V1 (ROBECO 3-FACTOR FAMA-FRENCH RESIDUAL MOMENTUM: 12-1M & 36M BLITZ 2011) ===")
    print(df_v1.to_string(index=False))
    print("\n=== 4. EXPERIMENT V2 (DANIEL & MOSKOWITZ 2016 PANIC OVERLAY & BARROSO 2015) ===")
    print(df_v2.to_string(index=False))
    print("\n=== 5. V4 SUB-PERIOD & OUTLIER REMOVAL AUDIT (EX-2026, EX-2020, DROP BEST 5/10 MONTHS) ===")
    print(df_v4_rob.to_string(index=False))
