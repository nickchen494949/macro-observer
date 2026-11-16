#!/usr/bin/env python3
"""
run_six_new_paper_challengers.py — Clean-Room Challenger Evaluation & Audit Remediation of 6 Academic Papers (2026-11-16)
=========================================================================================================================
STRICT CHALLENGER & AUDIT REMEDIATION PROTOCOL:
1. Frozen V4 (`Symmetric_Sharpe_Top2_V4`) and Frozen V1-Daily TQQQ (`1.2/0.3 + Open NSL`) are UNCHANGED.
2. Audit Remediation #1 — P4 (`SUE` & `EAR`, Chan, Jegadeesh & Lakonishok 1996, JF):
   - True Dollar EPS Extraction: In `eps_quarterly_pit.parquet`, `filed_eps_diluted` is a `datetime64[ns]` filing-date
     metadata column, whereas actual dollar quarterly EPS values are stored in `eps_diluted_approx_adj` / `eps_diluted`
     (`float64`). We compute `SUE` strictly from true dollar quarterly EPS (`eps_diluted_approx_adj` / `eps_diluted`)
     matched against the exact year-ago quarter (`330 <= (period_end - period_end_lag4).days <= 400`) and standardized
     by the trailing 8-quarter EPS-change standard deviation (`min_periods=4`).
   - Proper Missing-Data Handling (No silent `0.0` fill): Missing `SUE` is kept as `NaN` so missing-data stocks are never
     artificially ranked above negative-surprise stocks (`SUE < 0`). We evaluate all 4 explicit treatments:
       (i)   `NaN-Last` inside `Sharpe Top-5` (default clean rule),
       (ii)  `Cross-Sectional Median Imputation` (missing `SUE` receives month-t universe median `SUE`),
       (iii) `Pre-Filter Valid SUE Only` (candidate pool restricted to stocks with non-null `SUE`),
       (iv)  `Zero-Fill (0.0)` (shown solely for audit comparison).
   - Simultaneous Exclusion of `2020-11` (`MRNA` outlier month): Every V4 challenger is evaluated both on Full 214M and
     Excluding `2020-11` (`Ex2020_11_CAGR_%` & `Sharpe_Ex2020_11`), plus `2012-2026` (mature XBRL coverage era).
   - Exact 3-Trading-Day `EAR` Window (`[tau-1, tau, tau+1]`): `EAR_3td` is computed over the exact 3 NYSE trading days
     centered on (a) the SEC filing date (`tau`) and (b) the peak-volume earnings announcement day within `[tau-10, tau]`,
     strictly capped at formation date `t` with `NaN` preserved for missing values.
3. Audit Remediation #2 — P5 (`EBP`, Gilchrist & Zakrajsek 2012, AER):
   - Regular monthly public updates of the Federal Reserve's `EBP` began in October 2016 (following the April 2016 FEDS Notes).
   - Therefore, `P5a-LiveEra` strictly disables `EBP` prior to `2016-11` (when the Oct 2016 release became available with
     a 1-month lag) and evaluates both the full period and the exact `2016-11-01 .. 2026-11-03` live publication window.
   - We also test unrevised daily FRED High-Yield Option-Adjusted Spread (`BAMLH0A0HYM2`, live since 1996) as a 100%
     revision-free credit spread signal across the entire `2010-2026` sample.
4. Audit Remediation #3 — P6 (`VRP`, Bollerslev, Tauchen & Zhou 2009, RFS):
   - Eliminates the cross-index mismatch (`VIX` vs `QQQ`) by computing two strictly index-matched, 21-trading-day
     (30-calendar-day) horizon-matched Variance Risk Premia:
       (a) `VRP_NDX = (VXN_t / 100)^2 - RV21_QQQ_t^2` (using official CBOE Nasdaq-100 Volatility Index `VXN` + `QQQ`),
       (b) `VRP_SPX = (VIX_t / 100)^2 - RV21_SPY_t^2` (using official CBOE S&P 500 Volatility Index `VIX` + `SPY`).
"""
import functools
import json
import os
import numpy as np
import pandas as pd
import frozen_v1_tqqq_strategy as fv
import independent_v4_symmetric_sharpe_top2_audit as iv4

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "research", "sector_stock_momentum", "data")
ETF_DIR = os.path.join(ROOT, "outputs", "remediation_full_audit_20261104", "tiingo_etfs")
TIINGO_ROWS_DIRS = [
    os.path.join(ROOT, "outputs", "qqq_mom_top3_claude_audit_20261103", "tiingo"),
    os.path.join(ROOT, "outputs", "tech_top1_independent_audit_20261103", "tiingo"),
]
OUT_DIR = os.path.join(ROOT, "outputs", "six_new_paper_challengers_20261116")
os.makedirs(OUT_DIR, exist_ok=True)


def _frame(dates, close, opn):
    idx = pd.to_datetime(pd.Series(list(dates)).astype(str).str[:10])
    df = pd.DataFrame({
        "c": pd.to_numeric(pd.Series(list(close)), errors="coerce").values,
        "o": (pd.to_numeric(pd.Series(list(opn)), errors="coerce").values if opn is not None else np.nan),
    }, index=idx.values)
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df = df[df["c"] > 0]
    df.loc[~(df["o"] > 0), "o"] = np.nan
    return df if len(df) else None


@functools.lru_cache(maxsize=1)
def _wiki():
    w = pd.read_parquet(os.path.join(DATA_DIR, "wiki_bulk", "wiki_prices.parquet"), columns=["ticker", "date", "adj_close"])
    o = pd.read_parquet(os.path.join(DATA_DIR, "wiki_bulk", "wiki_open.parquet"))
    w = w.merge(o, on=["ticker", "date"], how="left")
    return {k: g for k, g in w.groupby("ticker")}


@functools.lru_cache(maxsize=None)
def load_stock(src, sym):
    try:
        if src == "yahoo":
            for sub in ("raw_open", "raw"):
                p = os.path.join(DATA_DIR, sub, f"{sym}.json")
                if os.path.exists(p):
                    j = json.load(open(p))
                    return _frame(j["dates"], j["adjclose"], j.get("adj_open"))
        elif src == "tiingo":
            for d in TIINGO_ROWS_DIRS:
                p = os.path.join(d, f"{sym}.json")
                if os.path.exists(p):
                    r = pd.DataFrame(json.load(open(p))["rows"])
                    return _frame(r["date"], r["adjClose"], r.get("adjOpen"))
            p = os.path.join(DATA_DIR, "raw_tiingo", f"{sym}.json")
            if os.path.exists(p):
                j = json.load(open(p))
                return _frame(j["dates"], j["adjclose"], None)
        elif src in ("archive", "raw_ndx"):
            p = os.path.join(DATA_DIR, "raw_archive" if src == "archive" else "raw_ndx", f"{sym}.json")
            if os.path.exists(p):
                j = json.load(open(p))
                return _frame(j["dates"], j["adjclose"], j.get("adj_open"))
        elif src == "wiki":
            g = _wiki().get(sym)
            if g is not None:
                return _frame(g["date"], g["adj_close"], g["adj_open"] if "adj_open" in g else None)
    except Exception:
        return None
    return None


def load_etf(sym):
    df = pd.DataFrame(json.load(open(os.path.join(ETF_DIR, f"{sym}.json"))))
    df["date"] = pd.to_datetime(df["date"].str[:10])
    df = df.set_index("date").sort_index()
    df = df[~df.index.duplicated(keep="last")]
    return pd.DataFrame({"c": df["adjClose"].astype(float), "o": df["adjOpen"].astype(float)})


ETFS = {s: load_etf(s) for s in ["SPY", "QQQ", "SGOV", "BIL"]}
CAL = ETFS["SPY"].index
LAST_T = pd.Timestamp("2026-09-30")
LAST_D1 = pd.Timestamp("2026-10-29")


def next_session(dt):
    i = CAL.searchsorted(pd.Timestamp(dt), side="right")
    return CAL[i] if i < len(CAL) else None


MONTHS = iv4.months_214
YM = {t: (t + pd.offsets.MonthBegin(1)).strftime("%Y-%m") for t in MONTHS}
P_NDX = iv4.p_ndx[iv4.p_ndx["t"].isin(MONTHS)].copy()
P_SPX = iv4.p_spx[iv4.p_spx["t"].isin(MONTHS)].copy()

p_non_it = P_SPX[(P_SPX["clean_sector"] != "Information Technology") & P_SPX["mom"].notna() & P_SPX["sharpe"].notna()].copy()
BSEC_BY_T = {t: g.groupby("clean_sector")["mom"].mean().sort_index().idxmax() for t, g in p_non_it.groupby("t")}
P_BSEC = p_non_it[p_non_it.apply(lambda r: r["clean_sector"] == BSEC_BY_T[r["t"]], axis=1)].copy()

# ------------------------------------------------------------------------------
# 1. Load Raw Daily Close, Daily Dollar-Volume, and True Dollar PIT Quarterly EPS
# ------------------------------------------------------------------------------
unique_pairs = set(zip(P_BSEC["src"], P_BSEC["sym"])).union(set(zip(P_NDX["src"], P_NDX["sym"])))
close_cache = {}
ret_cache = {}
for src, sym in unique_pairs:
    if isinstance(src, str) and isinstance(sym, str):
        df_s = load_stock(src, sym)
        if df_s is not None and len(df_s) > 30:
            s_c = df_s["c"].dropna()
            s_c = s_c[s_c > 0]
            close_cache[(src, sym)] = s_c
            ret_cache[(src, sym)] = s_c.pct_change(fill_method=None).dropna()

dv_path = os.path.join(ROOT, "research", "sector_stock_momentum", "data", "smallcap", "daily_dv.parquet")
DV_DF = pd.read_parquet(dv_path) if os.path.exists(dv_path) else pd.DataFrame()
if not DV_DF.empty:
    DV_DF.index = pd.to_datetime(DV_DF.index)
    DV_DF = DV_DF.sort_index()

eps_spx_path = os.path.join(ROOT, "research", "sector_stock_momentum", "data", "fundamentals", "eps_quarterly_pit.parquet")
eps_ndx_path = os.path.join(ROOT, "research", "sector_stock_momentum", "data", "fundamentals_ndx", "eps_quarterly_pit.parquet")
eps_list = []
for ep in (eps_spx_path, eps_ndx_path):
    if os.path.exists(ep):
        eps_list.append(pd.read_parquet(ep))

EPS_TRUE_BY_TK = {}
EPS_OLD_BUG_BY_TK = {}
if eps_list:
    EPS_RAW = pd.concat(eps_list, ignore_index=True)
    EPS_RAW["filed"] = pd.to_datetime(EPS_RAW["filed"])
    EPS_RAW["available_date"] = pd.to_datetime(EPS_RAW["available_date"])
    EPS_RAW["period_end"] = pd.to_datetime(EPS_RAW["period_end"])

    # (A) True Dollar Quarterly EPS (`eps_diluted_approx_adj` / `eps_diluted` / `eps_basic`)
    e_adj = pd.to_numeric(EPS_RAW["eps_diluted_approx_adj"], errors="coerce")
    e_raw = (
        pd.to_numeric(EPS_RAW["eps_diluted_approx"], errors="coerce")
        .combine_first(pd.to_numeric(EPS_RAW["eps_diluted"], errors="coerce"))
        .combine_first(pd.to_numeric(EPS_RAW["eps_basic_approx"], errors="coerce"))
        .combine_first(pd.to_numeric(EPS_RAW["eps_basic"], errors="coerce"))
    )
    EPS_TRUE = EPS_RAW.copy()
    EPS_TRUE["eps_val"] = e_adj.combine_first(e_raw).astype(float)
    EPS_TRUE = EPS_TRUE.dropna(subset=["ticker", "period_end", "available_date", "eps_val"]).sort_values(["ticker", "period_end", "available_date"])
    for tk, g in EPS_TRUE.groupby("ticker"):
        g_first = g.drop_duplicates(subset=["period_end"], keep="first").sort_values("period_end").reset_index(drop=True)
        pe = g_first["period_end"].values
        ev = g_first["eps_val"].values
        lag4_val = np.full(len(g_first), np.nan)
        for i in range(len(g_first)):
            for j in range(i - 1, max(-1, i - 6), -1):
                days = (pe[i] - pe[j]) / np.timedelta64(1, "D")
                if 330 <= days <= 400:
                    lag4_val[i] = ev[j]
                    break
        g_first["eps_lag4"] = lag4_val
        g_first["eps_diff"] = g_first["eps_val"] - g_first["eps_lag4"]
        g_first["eps_diff_std"] = g_first["eps_diff"].rolling(8, min_periods=4).std(ddof=1)
        g_first["sue_true"] = (g_first["eps_diff"] / g_first["eps_diff_std"].replace(0.0, np.nan)).clip(-5.0, 5.0)
        EPS_TRUE_BY_TK[tk] = g_first.sort_values("available_date")

    # (B) Reproduce Old `9f84929` `filed_eps_diluted` timestamp bug solely for transparent audit table comparison
    EPS_BUG = EPS_RAW.copy()
    eb_dil = pd.to_numeric(EPS_BUG["filed_eps_diluted"], errors="coerce")
    eb_bas = pd.to_numeric(EPS_BUG["filed_eps_basic"], errors="coerce")
    EPS_BUG["eps_val"] = eb_dil.combine_first(eb_bas).astype(float)
    EPS_BUG = EPS_BUG.dropna(subset=["ticker", "available_date", "eps_val"]).sort_values(["ticker", "period_end", "available_date"])
    EPS_BUG_FIRST = EPS_BUG.drop_duplicates(subset=["ticker", "period_end"], keep="first").copy().reset_index(drop=True)
    EPS_BUG_FIRST["eps_lag4"] = EPS_BUG_FIRST.groupby("ticker")["eps_val"].shift(4).astype(float)
    EPS_BUG_FIRST["eps_diff"] = (EPS_BUG_FIRST["eps_val"] - EPS_BUG_FIRST["eps_lag4"]).astype(float)
    EPS_BUG_FIRST["eps_diff_std"] = (
        EPS_BUG_FIRST.groupby("ticker")["eps_diff"]
        .rolling(8, min_periods=4)
        .std(ddof=1)
        .reset_index(level=0, drop=True)
        .astype(float)
    )
    EPS_BUG_FIRST["sue"] = (EPS_BUG_FIRST["eps_diff"] / EPS_BUG_FIRST["eps_diff_std"].replace(0.0, np.nan)).clip(-5.0, 5.0)
    eps_pct = (EPS_BUG_FIRST["eps_diff"] / EPS_BUG_FIRST["eps_lag4"].abs().clip(lower=0.10)).clip(-5.0, 5.0)
    EPS_BUG_FIRST["sue"] = EPS_BUG_FIRST["sue"].combine_first(eps_pct)
    EPS_OLD_BUG_BY_TK = {tk: g.sort_values("available_date") for tk, g in EPS_BUG_FIRST.groupby("ticker")}

spy_ret = ETFS["SPY"]["c"].pct_change(fill_method=None).dropna()


# ------------------------------------------------------------------------------
# 2. Compute Paper Features (P1 FIP, P2 52W-High, P3 Volume, P4 True SUE & 3-TD EAR)
# ------------------------------------------------------------------------------
def enrich_panel_with_paper_features(df_in):
    fip_cont = []         # P1: %pos - %neg over 12-1M window (Da, Gurun & Warachka 2014)
    smooth_sh = []        # P1c: 12-1 Sharpe after removing top 5 single-day jump spikes
    gh_52w = []           # P2: P_t / max(P_{t-252..t}) (George & Hwang 2004)
    vol_ratio_3_12 = []   # P3: 3M / 12M dollar volume ratio (Lee & Swaminathan 2000)
    sue_true_nan = []     # P4a (Fixed): True Dollar Quarterly SUE (`NaN` preserved when missing!)
    sue_old_bug = []      # P4a (Old 9f84929): Timestamp-bug SUE with 0.0 fill (for audit reconciliation)
    ear_3td_filing = []   # P4b (Fixed): Exact 3 NYSE trading days [tau-1, tau, tau+1] around SEC filing date (`NaN` preserved)
    ear_3td_peakvol = []  # P4b-PeakVol: Exact 3 NYSE trading days around peak-volume earnings release day in [tau-10, tau]

    for row in df_in[["t", "ticker", "src", "sym", "mom", "vol", "sharpe"]].itertuples(index=False):
        s_c = close_cache.get((row.src, row.sym))
        r_s = ret_cache.get((row.src, row.sym))
        if s_c is None or r_s is None or pd.isna(row.sharpe):
            fip_cont.append(np.nan)
            smooth_sh.append(np.nan)
            gh_52w.append(np.nan)
            vol_ratio_3_12.append(np.nan)
            sue_true_nan.append(np.nan)
            sue_old_bug.append(0.0)
            ear_3td_filing.append(np.nan)
            ear_3td_peakvol.append(np.nan)
            continue

        t = row.t
        t_m1 = t - pd.offsets.MonthEnd(1)
        t_m12 = t - pd.offsets.MonthEnd(12)

        # P1: Frog-in-the-Pan (Da, Gurun & Warachka 2014) over [t_m12, t_m1]
        sub_r12 = r_s.loc[(r_s.index > t_m12) & (r_s.index <= t_m1)]
        if len(sub_r12) >= 120:
            rv = sub_r12.values
            pct_pos = float(np.mean(rv > 0))
            pct_neg = float(np.mean(rv < 0))
            sign_p = 1.0 if row.mom >= 0 else -1.0
            fip_cont.append(sign_p * (pct_pos - pct_neg))
            rv_sorted = np.sort(rv)
            rv_ex5 = rv_sorted[:-5]
            comp_ex5 = float(np.prod(1.0 + rv_ex5) - 1.0)
            std_ex5 = float(np.std(rv_ex5, ddof=1) * np.sqrt(252.0))
            smooth_sh.append(comp_ex5 / std_ex5 if std_ex5 > 1e-8 else float(row.sharpe))
        else:
            fip_cont.append(np.nan)
            smooth_sh.append(float(row.sharpe))

        # P2: 52-Week High Proximity (George & Hwang 2004): P_t / High_252(t)
        sub_c252 = s_c.loc[:t].iloc[-252:]
        if len(sub_c252) >= 60:
            gh_52w.append(float(sub_c252.iloc[-1] / sub_c252.max()))
        else:
            gh_52w.append(np.nan)

        # P3: Trading Volume / Dollar Volume (Lee & Swaminathan 2000)
        tk_dv = row.ticker if row.ticker in DV_DF.columns else (row.sym if row.sym in DV_DF.columns else None)
        if tk_dv is not None:
            s_dv = DV_DF[tk_dv].loc[:t].dropna().iloc[-252:]
            if len(s_dv) >= 120 and s_dv.mean() > 0:
                vol_ratio_3_12.append(float(s_dv.iloc[-63:].mean() / s_dv.mean()))
            else:
                vol_ratio_3_12.append(np.nan)
        else:
            vol_ratio_3_12.append(np.nan)

        # P4 (Fixed): True Dollar Quarterly SUE (`NaN` preserved) & Exact 3-Trading-Day EAR `[tau-1, tau, tau+1]`
        eg_true = EPS_TRUE_BY_TK.get(row.ticker)
        if eg_true is not None:
            eg_avail = eg_true[(eg_true["available_date"] <= t) & (eg_true["available_date"] >= t - pd.Timedelta(days=180))]
            if len(eg_avail):
                last_rep = eg_avail.iloc[-1]
                sue_true_nan.append(float(last_rep["sue_true"]) if pd.notna(last_rep["sue_true"]) else np.nan)
                f_dt = last_rep["filed"]
                r_upto_t = r_s.loc[:t]
                if len(r_upto_t) >= 5:
                    idx_tau = int(r_upto_t.index.searchsorted(f_dt, side="left"))
                    if idx_tau >= len(r_upto_t):
                        idx_tau = len(r_upto_t) - 1
                    # Exact 3 trading days [idx_tau - 1, idx_tau, idx_tau + 1] capped at t
                    i_start = max(0, idx_tau - 1)
                    i_end = min(len(r_upto_t) - 1, idx_tau + 1)
                    r_win = r_upto_t.iloc[i_start : i_end + 1]
                    m_win = spy_ret.reindex(r_win.index).fillna(0.0)
                    ear_3td_filing.append(float((1.0 + r_win).prod() - (1.0 + m_win).prod()))

                    # Also check peak-volume / peak-reaction announcement day within [idx_tau - 10, idx_tau]
                    # (captures 8-K press release date when issued prior to 10-Q/10-K filing)
                    w_start = max(0, idx_tau - 10)
                    cand_dates = r_upto_t.index[w_start : idx_tau + 1]
                    if tk_dv is not None and len(cand_dates) > 0:
                        dv_sub = DV_DF[tk_dv].reindex(cand_dates).dropna()
                        if len(dv_sub) > 0:
                            peak_dt = dv_sub.idxmax()
                            idx_pk = int(r_upto_t.index.get_loc(peak_dt))
                        else:
                            idx_pk = idx_tau
                    else:
                        idx_pk = idx_tau
                    p_start = max(0, idx_pk - 1)
                    p_end = min(len(r_upto_t) - 1, idx_pk + 1)
                    r_pwin = r_upto_t.iloc[p_start : p_end + 1]
                    m_pwin = spy_ret.reindex(r_pwin.index).fillna(0.0)
                    ear_3td_peakvol.append(float((1.0 + r_pwin).prod() - (1.0 + m_pwin).prod()))
                else:
                    ear_3td_filing.append(np.nan)
                    ear_3td_peakvol.append(np.nan)
            else:
                sue_true_nan.append(np.nan)
                ear_3td_filing.append(np.nan)
                ear_3td_peakvol.append(np.nan)
        else:
            sue_true_nan.append(np.nan)
            ear_3td_filing.append(np.nan)
            ear_3td_peakvol.append(np.nan)

        # Old 9f84929 SUE bug value for audit reconciliation
        eg_bug = EPS_OLD_BUG_BY_TK.get(row.ticker)
        if eg_bug is not None:
            eg_b_avail = eg_bug[(eg_bug["available_date"] <= t) & (eg_bug["available_date"] >= t - pd.Timedelta(days=180))]
            if len(eg_b_avail):
                b_val = eg_b_avail.iloc[-1]["sue"]
                sue_old_bug.append(float(b_val) if pd.notna(b_val) else 0.0)
            else:
                sue_old_bug.append(0.0)
        else:
            sue_old_bug.append(0.0)

    out = df_in.copy()
    out["fip_cont"] = fip_cont
    out["smooth_sh"] = smooth_sh
    out["gh_52w"] = gh_52w
    out["vol_ratio_3_12"] = vol_ratio_3_12
    out["sue_true"] = sue_true_nan
    out["sue_cs_median"] = out.groupby("t")["sue_true"].transform(lambda s: s.fillna(s.median()))
    out["sue_zero_fill"] = out["sue_true"].fillna(0.0)
    out["sue_old_bug"] = sue_old_bug
    out["ear_3td"] = ear_3td_filing
    out["ear_3td_cs_median"] = out.groupby("t")["ear_3td"].transform(lambda s: s.fillna(s.median()))
    out["ear_3td_peakvol"] = ear_3td_peakvol

    def add_cs_blends(df_p):
        df_p = df_p.copy()
        for col_new, name_blend in [
            ("fip_cont", "blend_fip"),
            ("gh_52w", "blend_gh52w"),
            ("vol_ratio_3_12", "blend_vol_high"),
            ("sue_true", "blend_sue"),
            ("ear_3td", "blend_ear"),
        ]:
            r_sh = df_p.groupby("t")["sharpe"].rank(pct=True)
            r_nf = df_p.groupby("t")[col_new].rank(pct=True)
            df_p[name_blend] = 0.5 * r_sh + 0.5 * r_nf.fillna(0.5)
        r_sh = df_p.groupby("t")["sharpe"].rank(pct=True)
        r_vlow = (-df_p["vol_ratio_3_12"]).groupby(df_p["t"]).rank(pct=True)
        df_p["blend_vol_low"] = 0.5 * r_sh + 0.5 * r_vlow.fillna(0.5)
        return df_p

    return add_cs_blends(out)


print("Computing P1 (FIP), P2 (52W High), P3 (Volume), P4 (True Dollar PIT SUE & Exact 3-TD EAR) features...")
NDX_E = enrich_panel_with_paper_features(P_NDX)
BSEC_E = enrich_panel_with_paper_features(P_BSEC)


# ------------------------------------------------------------------------------
# 3. Selection & Simulation Helpers for V4 Challengers (Including Ex-2020-11 & Daily MaxDD)
# ------------------------------------------------------------------------------
def select_top2_within_sharpe_top5(panel_df, tiebreaker_col, ascending_tie=False, hold_k=5, na_position="last", prefilter_valid=False):
    picks = {}
    held = []
    for t, g in panel_df.groupby("t", sort=True):
        gv = g[g["sharpe"].notna() & g["mom"].notna()].sort_values(["sharpe", "ticker"], ascending=[False, True]).reset_index(drop=True)
        if prefilter_valid:
            gv_valid = gv[gv[tiebreaker_col].notna()].reset_index(drop=True)
            if len(gv_valid) >= 5:
                gv = gv_valid
        rk_sh = {tk: i + 1 for i, tk in enumerate(gv["ticker"])}
        kept = [tk for tk in held if rk_sh.get(tk, 999) <= hold_k]
        top5 = gv.iloc[:5].copy()
        top5 = top5.sort_values(
            by=[tiebreaker_col, "sharpe", "ticker"],
            ascending=[ascending_tie, False, True],
            na_position=na_position,
        )
        for tk in top5["ticker"]:
            if len(kept) >= 2:
                break
            if tk not in kept:
                kept.append(tk)
        held = kept[:2]
        if "clean_sector" in panel_df.columns and (panel_df["clean_sector"] != "Information Technology").all():
            picks[t] = (held[0], held[1], BSEC_BY_T[t])
        else:
            picks[t] = (held[0], held[1])
    return picks


def eval_v4_challenger(label, pk_q, pk_bs):
    df_m, tr = iv4.sim_v4(pk_q, pk_bs, use_election_v3=False)
    c204, c214, sr214, mdd_m, wr, _, _, _ = iv4.eval_summary(df_m, tr)
    s_net = df_m["net_ret"]
    rf_all = pd.Series([float(iv4.reg_map[t]["rf_tbill"]) for t in MONTHS], index=s_net.index)

    # Complete 213M (to 2026-09)
    s_213 = s_net.loc[:"2026-09"]
    c213 = float(np.prod(1.0 + s_213) ** (12.0 / len(s_213)) - 1.0)

    # Excluding 2020-11 (Auditor Request #1: same-month comparison without 2020-11 MRNA outlier)
    s_ex_nov20 = s_net.drop("2020-11")
    rf_ex_nov20 = rf_all.drop("2020-11")
    c_ex_nov20 = float(np.prod(1.0 + s_ex_nov20) ** (12.0 / len(s_ex_nov20)) - 1.0)
    sh_ex_nov20 = float((s_ex_nov20 - rf_ex_nov20).mean() / s_ex_nov20.std(ddof=1) * np.sqrt(12.0))

    # 2012-2026 Mature XBRL Era (178M, >90% 8Q XBRL SUE coverage)
    s_12_26 = s_net.loc["2012-01":]
    rf_12_26 = rf_all.loc["2012-01":]
    c_12_26 = float(np.prod(1.0 + s_12_26) ** (12.0 / len(s_12_26)) - 1.0)
    sh_12_26 = float((s_12_26 - rf_12_26).mean() / s_12_26.std(ddof=1) * np.sqrt(12.0))

    s_25 = s_net.loc[:"2025-12"]
    rf_25 = rf_all.loc[:"2025-12"]
    sh_25 = float((s_25 - rf_25).mean() / s_25.std(ddof=1) * np.sqrt(12.0))
    drop5 = s_net.drop(s_net.nlargest(5).index)
    c_drop5 = float(np.prod(1.0 + drop5) ** (12.0 / len(drop5)) - 1.0)
    drop10 = s_net.drop(s_net.nlargest(10).index)
    c_drop10 = float(np.prod(1.0 + drop10) ** (12.0 / len(drop10)) - 1.0)
    ann_to = float(df_m["turnover_two_way"].mean() * 12.0)

    # Compute Open-Executed Daily NAV & Daily MaxDD
    nav, navs = 1.0, []
    for _, r in df_m.iterrows():
        w = json.loads(r["weights_json"])
        t = pd.Timestamp(r["t"])
        d0 = next_session(t)
        d1 = LAST_D1 if t == LAST_T else next_session(t + pd.offsets.MonthEnd(1))
        nav *= (1.0 - 0.0010 * float(r["turnover_two_way"]))
        series = {}
        for tk in w:
            if tk in ("CASH", "SGOV"):
                cs = "SGOV" if (d0 >= pd.Timestamp("2020-06-01") and d0 in ETFS["SGOV"].index) else "BIL"
                series[tk] = ETFS[cs]
            else:
                src_panel = P_NDX if bool(r["sep_on"]) else P_SPX
                hit = src_panel[(src_panel["t"] == t) & (src_panel["ticker"] == tk)]
                if len(hit) == 0:
                    hit = P_NDX[(P_NDX["t"] == t) & (P_NDX["ticker"] == tk)]
                row = hit.iloc[0]
                series[tk] = load_stock(row["src"], row["sym"])
        days = CAL[(CAL >= d0) & (CAL < d1)] if t != LAST_T else CAL[(CAL >= d0) & (CAL <= d1)]
        base = {}
        for tk, df_s in series.items():
            o = df_s.at[d0, "o"] if (d0 in df_s.index and np.isfinite(df_s.at[d0, "o"])) else (df_s.at[d0, "c"] if d0 in df_s.index else np.nan)
            base[tk] = o
        for d in days:
            v = 0.0
            for tk, wt in w.items():
                df_s = series[tk]
                px = df_s["c"].loc[:d]
                v += wt * (float(px.iloc[-1]) / base[tk] if len(px) else 1.0)
            navs.append(nav * v)
        v_end = 0.0
        for tk, wt in w.items():
            df_s = series[tk]
            if t == LAST_T:
                v_end += wt * float(df_s["c"].loc[:d1].iloc[-1]) / base[tk]
            elif d1 in df_s.index and np.isfinite(df_s.at[d1, "o"]):
                v_end += wt * df_s.at[d1, "o"] / base[tk]
            else:
                v_end += wt * float(df_s["c"].loc[:d1].iloc[-1]) / base[tk]
        nav *= v_end
    dn = np.asarray(navs, float)
    daily_mdd = float((dn / np.maximum.accumulate(dn) - 1.0).min())

    return {
        "Challenger_Variant": label,
        "Full_214M_CAGR_%": round(c214 * 100, 2),
        "Ex2020_11_CAGR_%": round(c_ex_nov20 * 100, 2),
        "Ex2026_09_25_CAGR_%": round(c204 * 100, 2),
        "Era2012_26_CAGR_%": round(c_12_26 * 100, 2),
        "Nov2020_Ret_%": round(float(s_net.loc["2020-11"]) * 100, 2),
        "Sharpe_214M": round(sr214, 3),
        "Sharpe_Ex2020_11": round(sh_ex_nov20, 3),
        "Sharpe_Ex2026": round(sh_25, 3),
        "Daily_MaxDD_%": round(daily_mdd * 100, 2),
        "Monthly_MaxDD_%": round(mdd_m * 100, 2),
        "DropBest10M_CAGR_%": round(c_drop10 * 100, 2),
        "Ann_TwoWay_Turnover": round(ann_to, 2),
        "Trade_WinRate_%": round(wr * 100, 2),
    }


def run_v4_col_challenger(label, col):
    d_q = NDX_E.copy()
    d_q["sharpe"] = d_q[col]
    d_b = BSEC_E.copy()
    d_b["sharpe"] = d_b[col]
    pk_q = iv4.select_qqq_sharpe_top2(d_q, hold_k=5, reset_t_set=None)
    pk_b = iv4.select_bestsec_sharpe_top2(d_b, hold_k=5, reset_t_set=None)
    return eval_v4_challenger(label, pk_q, pk_b)


# ------------------------------------------------------------------------------
# 4. Run All V4 Challengers & Dedicated P4 Missing-Data / Ex-2020-11 Audit Table
# ------------------------------------------------------------------------------
v4_challenger_rows = []

pk_q0 = iv4.select_qqq_sharpe_top2(NDX_E, hold_k=5, reset_t_set=None)
pk_b0 = iv4.select_bestsec_sharpe_top2(BSEC_E, hold_k=5, reset_t_set=None)
base_row = eval_v4_challenger("0. Frozen V4 Baseline (12-1 Sharpe, Top-2 / Hold<=5)", pk_q0, pk_b0)
v4_challenger_rows.append(base_row)

# P1: Frog in the Pan (Da, Gurun & Warachka 2014, RFS)
v4_challenger_rows.append(eval_v4_challenger(
    "P1a-FIP-Top5Tie. Pick Top-2 Most Continuous Daily Winners (%pos-%neg) Inside Sharpe Top-5",
    select_top2_within_sharpe_top5(NDX_E, "fip_cont", ascending_tie=False),
    select_top2_within_sharpe_top5(BSEC_E, "fip_cont", ascending_tie=False),
))
v4_challenger_rows.append(run_v4_col_challenger("P1b-FIP-Blend. 50/50 Rank Blend (12-1 Sharpe + Daily FIP Continuity)", "blend_fip"))
v4_challenger_rows.append(run_v4_col_challenger("P1c-SmoothSharpe. 12-1 Sharpe Excluding Top-5 Largest Daily Jump Spikes", "smooth_sh"))

# P2: 52-Week High Proximity (George & Hwang 2004, JF)
v4_challenger_rows.append(eval_v4_challenger(
    "P2a-52WHigh-Top5Tie. Pick Top-2 Closest to 52-Week High (P_t/High_252) Inside Sharpe Top-5",
    select_top2_within_sharpe_top5(NDX_E, "gh_52w", ascending_tie=False),
    select_top2_within_sharpe_top5(BSEC_E, "gh_52w", ascending_tie=False),
))
v4_challenger_rows.append(run_v4_col_challenger("P2b-52WHigh-Blend. 50/50 Rank Blend (12-1 Sharpe + 52-Week High Proximity)", "blend_gh52w"))
v4_challenger_rows.append(run_v4_col_challenger("P2c-52WHigh-Pure. Pure 52-Week High Proximity Ranking (George & Hwang 2004)", "gh_52w"))

# P3: Price Momentum & Trading Volume (Lee & Swaminathan 2000, JF)
v4_challenger_rows.append(eval_v4_challenger(
    "P3a-VolLow-Top5Tie. Pick Top-2 Lowest 3M/12M Volume Ratio (Early Underreaction) Inside Sharpe Top-5",
    select_top2_within_sharpe_top5(NDX_E, "vol_ratio_3_12", ascending_tie=True),
    select_top2_within_sharpe_top5(BSEC_E, "vol_ratio_3_12", ascending_tie=True),
))
v4_challenger_rows.append(eval_v4_challenger(
    "P3b-VolHigh-Top5Tie. Pick Top-2 Highest 3M/12M Volume Ratio (Breakout Volume) Inside Sharpe Top-5",
    select_top2_within_sharpe_top5(NDX_E, "vol_ratio_3_12", ascending_tie=False),
    select_top2_within_sharpe_top5(BSEC_E, "vol_ratio_3_12", ascending_tie=False),
))
v4_challenger_rows.append(run_v4_col_challenger("P3c-VolLow-Blend. 50/50 Rank Blend (12-1 Sharpe + Low 3M/12M Volume Ratio)", "blend_vol_low"))
v4_challenger_rows.append(run_v4_col_challenger("P3d-VolHigh-Blend. 50/50 Rank Blend (12-1 Sharpe + High 3M/12M Volume Ratio)", "blend_vol_high"))

# P4 (Remediated): True Dollar EPS SUE & Exact 3-Trading-Day EAR across Missing-Data Treatments
p4a_nan_last = eval_v4_challenger(
    "P4a-TrueSUE-NaNLast. True Dollar SUE Inside Sharpe Top-5 (Missing SUE = NaN Ranked Last)",
    select_top2_within_sharpe_top5(NDX_E, "sue_true", ascending_tie=False, na_position="last"),
    select_top2_within_sharpe_top5(BSEC_E, "sue_true", ascending_tie=False, na_position="last"),
)
p4a_cs_med = eval_v4_challenger(
    "P4a-TrueSUE-CSMedian. True Dollar SUE Inside Sharpe Top-5 (Missing SUE = Universe Median)",
    select_top2_within_sharpe_top5(NDX_E, "sue_cs_median", ascending_tie=False, na_position="last"),
    select_top2_within_sharpe_top5(BSEC_E, "sue_cs_median", ascending_tie=False, na_position="last"),
)
p4a_prefilter = eval_v4_challenger(
    "P4a-TrueSUE-PreFilter. True Dollar SUE Inside Sharpe Top-5 (Pre-Filter Eligible Pool to Valid SUE)",
    select_top2_within_sharpe_top5(NDX_E, "sue_true", ascending_tie=False, na_position="last", prefilter_valid=True),
    select_top2_within_sharpe_top5(BSEC_E, "sue_true", ascending_tie=False, na_position="last", prefilter_valid=True),
)
p4a_zero_fill = eval_v4_challenger(
    "P4a-TrueSUE-ZeroFill. True Dollar SUE Inside Sharpe Top-5 (Missing SUE = 0.0, Audit Comparison)",
    select_top2_within_sharpe_top5(NDX_E, "sue_zero_fill", ascending_tie=False, na_position="last"),
    select_top2_within_sharpe_top5(BSEC_E, "sue_zero_fill", ascending_tie=False, na_position="last"),
)
p4a_old_bug = eval_v4_challenger(
    "P4a-Old9f84929-BugRef. Old `filed_eps_diluted` Timestamp Bug + 0.0 Fill (Audit Reference Only)",
    select_top2_within_sharpe_top5(NDX_E, "sue_old_bug", ascending_tie=False, na_position="last"),
    select_top2_within_sharpe_top5(BSEC_E, "sue_old_bug", ascending_tie=False, na_position="last"),
)
p4b_3td_filing = eval_v4_challenger(
    "P4b-EAR-3TD-Filing. Exact 3-Trading-Day [tau-1..tau+1] Filing EAR Inside Sharpe Top-5 (NaN Last)",
    select_top2_within_sharpe_top5(NDX_E, "ear_3td", ascending_tie=False, na_position="last"),
    select_top2_within_sharpe_top5(BSEC_E, "ear_3td", ascending_tie=False, na_position="last"),
)
p4b_3td_peakvol = eval_v4_challenger(
    "P4b-EAR-3TD-PeakVol. Exact 3-Trading-Day Announcement Peak-Volume EAR Inside Sharpe Top-5 (NaN Last)",
    select_top2_within_sharpe_top5(NDX_E, "ear_3td_peakvol", ascending_tie=False, na_position="last"),
    select_top2_within_sharpe_top5(BSEC_E, "ear_3td_peakvol", ascending_tie=False, na_position="last"),
)
p4c_blend = run_v4_col_challenger("P4c-TrueSUE-Blend. 50/50 Rank Blend (12-1 Sharpe + True Dollar PIT SUE)", "blend_sue")
p4d_blend = run_v4_col_challenger("P4d-EAR3TD-Blend. 50/50 Rank Blend (12-1 Sharpe + Exact 3-Trading-Day EAR)", "blend_ear")

for r_p4 in [
    p4a_nan_last,
    p4a_cs_med,
    p4a_prefilter,
    p4a_zero_fill,
    p4a_old_bug,
    p4b_3td_filing,
    p4b_3td_peakvol,
    p4c_blend,
    p4d_blend,
]:
    v4_challenger_rows.append(r_p4)

df_v4_chal = pd.DataFrame(v4_challenger_rows)
df_v4_chal.to_csv(os.path.join(OUT_DIR, "v4_challengers_p1_p2_p3_p4_summary.csv"), index=False)

df_p4_audit = pd.DataFrame([
    base_row,
    p4a_nan_last,
    p4a_cs_med,
    p4a_prefilter,
    p4a_zero_fill,
    p4a_old_bug,
    p4b_3td_filing,
    p4b_3td_peakvol,
    p4c_blend,
    p4d_blend,
])
df_p4_audit.to_csv(os.path.join(OUT_DIR, "p4_sue_missing_data_and_ex202011_audit.csv"), index=False)


# ------------------------------------------------------------------------------
# 5. Run TQQQ SEP Challengers (P5 Post-2016-10 Live EBP + Unrevised HY OAS & P6 Index-Matched VRP)
# ------------------------------------------------------------------------------
idx_real = fv.idx_real
sep_exact = fv.sep_exact_fomc

# Load Official Federal Reserve EBP (`fed_official_ebp.csv`) with STRICT 1-Month Publication Lag:
# Per Fed documentation (Favara et al., April 2016 FEDS Notes), regular monthly EBP updates began in October 2016
# -> first live monthly EBP available in November 2016 (`2016-11-07`).
ebp_df = pd.read_csv(os.path.join(ROOT, "outputs", "four_paper_experiments_20261116", "fed_official_ebp.csv"))
ebp_df["ym_avail"] = (pd.to_datetime(ebp_df["date"]) + pd.DateOffset(months=1)).dt.strftime("%Y-%m")
ebp_map = dict(zip(ebp_df["ym_avail"], ebp_df["ebp"].astype(float)))

ebp_full_backfill = pd.Series(np.nan, index=idx_real)
ebp_live_post2016 = pd.Series(np.nan, index=idx_real)
cur_ebp = np.nan
for dt in idx_real:
    ym_s = dt.strftime("%Y-%m")
    if dt.day >= 7 and ym_s in ebp_map:
        cur_ebp = ebp_map[ym_s]
    ebp_full_backfill.loc[dt] = cur_ebp
    if dt >= pd.Timestamp("2016-11-01"):
        ebp_live_post2016.loc[dt] = cur_ebp

# Unrevised Real-Time Daily FRED ICE BofA US High-Yield OAS (`BAMLH0A0HYM2`, live since 1996)
hy_raw = json.load(open(os.path.join(ROOT, "data", "fred", "BAMLH0A0HYM2.json")))["values"]
hy_s = pd.Series({pd.Timestamp(d): float(v) for d, v in hy_raw if v is not None}).sort_index().reindex(idx_real).ffill().bfill()
hy_z = (hy_s - hy_s.rolling(252).mean()) / hy_s.rolling(252).std(ddof=1)

# Index-Matched & 21-Trading-Day Horizon-Matched Variance Risk Premia (Bollerslev, Tauchen & Zhou 2009):
#   (a) Nasdaq-100 Matched VRP: `VRP_NDX = (VXN/100)^2 - RV21_QQQ^2`
#   (b) S&P 500 Matched VRP:    `VRP_SPX = (VIX/100)^2 - RV21_SPY^2`
qqq_ret = fv.qqq["adjClose"].astype(float).pct_change()
rv21_qqq = (qqq_ret.rolling(21).std(ddof=1) * np.sqrt(252.0)) ** 2
rv21_spy = (spy_ret.rolling(21).std(ddof=1) * np.sqrt(252.0)) ** 2

vix_raw = json.load(open(os.path.join(ROOT, "data", "yahoo", "_VIX.json")))["values"]
vix_s = pd.Series({pd.Timestamp(d): float(v) for d, v in vix_raw if v is not None}).sort_index().reindex(idx_real).ffill().bfill()
iv_spx = (vix_s / 100.0) ** 2

vxn_df = pd.read_csv(os.path.join(OUT_DIR, "cboe_vxn_history.csv"))
vxn_df["DATE"] = pd.to_datetime(vxn_df["DATE"])
vxn_s = vxn_df.set_index("DATE")["CLOSE"].astype(float).sort_index().reindex(idx_real).ffill().bfill()
iv_ndx = (vxn_s / 100.0) ** 2

vrp_ndx = iv_ndx - rv21_qqq.reindex(idx_real).bfill()
vrp_spx = iv_spx - rv21_spy.reindex(idx_real).bfill()
vrp_ndx_z = (vrp_ndx - vrp_ndx.rolling(252).mean()) / vrp_ndx.rolling(252).std(ddof=1)
vrp_spx_z = (vrp_spx - vrp_spx.rolling(252).mean()) / vrp_spx.rolling(252).std(ddof=1)


def eval_tqqq_challenger(label, trig_fn, rec_fn):
    assets = {"3x": fv.tqqq.loc[idx_real], "1x": fv.qqq.loc[idx_real], "0x": fv.cash_bil_sgov.loc[idx_real]}
    eq = 1.0
    peak = 1.0
    max_dd = 0.0
    pos = "3x"
    entry_eq = 1.0
    cost_mult = 1.0 - 2.0 * 0.001
    eq_s = [1.0]
    sw = 0

    for i in range(1, len(idx_real)):
        prev_dt = idx_real[i - 1]
        s_on = bool(sep_exact.loc[prev_dt])
        r_on = assets[pos]["adjOpen"].iloc[i] / assets[pos]["adjClose"].iloc[i - 1] - 1.0
        eq_open_pre = eq * (1.0 + r_on)
        can_sell_nsl = (eq >= entry_eq and eq_open_pre * cost_mult >= entry_eq)

        if not s_on:
            target_pos = "0x"
        else:
            trig = bool(trig_fn(prev_dt))
            rec = bool(rec_fn(prev_dt))
            if pos == "0x":
                target_pos = "3x" if not trig else "1x"
            elif pos == "3x":
                target_pos = "1x" if (trig and can_sell_nsl) else "3x"
            else:
                target_pos = "3x" if rec else "1x"

        if target_pos == pos:
            eq *= (1.0 + (assets[pos]["adjClose"].iloc[i] / assets[pos]["adjClose"].iloc[i - 1] - 1.0))
        else:
            sw += 1
            eq = eq_open_pre * cost_mult
            if target_pos == "3x":
                entry_eq = eq
            eq *= (1.0 + (assets[target_pos]["adjClose"].iloc[i] / assets[target_pos]["adjOpen"].iloc[i] - 1.0))
            pos = target_pos
        if eq > peak:
            peak = eq
        dd = eq / peak - 1.0
        if dd < max_dd:
            max_dd = dd
        eq_s.append(eq)

    s_eq = pd.Series(eq_s, index=idx_real)
    yrs = (idx_real[-1] - idx_real[0]).days / 365.25
    cagr = (eq ** (1.0 / yrs) - 1.0) * 100.0
    dr = s_eq.pct_change().dropna()
    sh = float(dr.mean() / dr.std(ddof=1) * np.sqrt(252.0))
    s_25 = s_eq.loc[:"2025-12-31"]
    yrs25 = (s_25.index[-1] - s_25.index[0]).days / 365.25
    cagr25 = (float(s_25.iloc[-1]) ** (1.0 / yrs25) - 1.0) * 100.0

    # Exact Live EBP Subperiod (2016-11-01 .. 2026-11-03)
    s_16 = s_eq.loc["2016-11-01":]
    s_16 = s_16 / float(s_16.iloc[0])
    yrs16 = (s_16.index[-1] - s_16.index[0]).days / 365.25
    cagr16 = (float(s_16.iloc[-1]) ** (1.0 / yrs16) - 1.0) * 100.0
    mdd16 = float((s_16 / s_16.cummax() - 1.0).min()) * 100.0
    dr16 = s_16.pct_change().dropna()
    sh16 = float(dr16.mean() / dr16.std(ddof=1) * np.sqrt(252.0))

    m_nav = s_eq.resample("ME").last()
    m_mdd = float((m_nav / m_nav.cummax() - 1.0).min()) * 100.0
    return {
        "TQQQ_Challenger_Variant": label,
        "Full_10_26_CAGR_%": round(cagr, 2),
        "Ex2026_10_25_CAGR_%": round(cagr25, 2),
        "Daily_Sharpe_rf0": round(sh, 3),
        "Daily_MaxDD_%": round(max_dd * 100.0, 2),
        "LiveEra_16_26_CAGR_%": round(cagr16, 2),
        "LiveEra_16_26_Sharpe": round(sh16, 3),
        "LiveEra_16_26_MaxDD_%": round(mdd16, 2),
        "Monthly_MaxDD_%": round(m_mdd, 2),
        "Total_Switches": sw,
    }


tqqq_challenger_rows = [
    eval_tqqq_challenger(
        "0. Frozen V1-Daily Baseline (SEP + Vol_Z 1.2/0.3 + Open NSL)",
        lambda d: fv.vol_z.loc[d] > 1.2,
        lambda d: fv.vol_z.loc[d] < 0.3,
    ),
    eval_tqqq_challenger(
        "P5a-LiveEraOnly. Fed EBP > +0.50% Active ONLY in Live Publication Era (>= 2016-11)",
        lambda d: (fv.vol_z.loc[d] > 1.2) or (pd.notna(ebp_live_post2016.loc[d]) and ebp_live_post2016.loc[d] > 0.50),
        lambda d: (fv.vol_z.loc[d] < 0.3) and (pd.isna(ebp_live_post2016.loc[d]) or ebp_live_post2016.loc[d] <= 0.25),
    ),
    eval_tqqq_challenger(
        "P5b-BackfilledRef. Fed EBP > +0.50% Using Backfilled 2010-2016 Series (Audit Reference)",
        lambda d: (fv.vol_z.loc[d] > 1.2) or (pd.notna(ebp_full_backfill.loc[d]) and ebp_full_backfill.loc[d] > 0.50),
        lambda d: (fv.vol_z.loc[d] < 0.3) and (pd.isna(ebp_full_backfill.loc[d]) or ebp_full_backfill.loc[d] <= 0.25),
    ),
    eval_tqqq_challenger(
        "P5c-RealTime-HY-OAS. Unrevised Daily FRED High-Yield OAS Z-Score > 1.2 (2010-2026 Real-Time)",
        lambda d: (fv.vol_z.loc[d] > 1.2) or (pd.notna(hy_z.loc[d]) and hy_z.loc[d] > 1.2),
        lambda d: (fv.vol_z.loc[d] < 0.3) and (pd.isna(hy_z.loc[d]) or hy_z.loc[d] < 0.5),
    ),
    eval_tqqq_challenger(
        "P6a-VRP-NDX-Matched. Nasdaq-100 Matched VRP = (VXN/100)^2 - RV21_QQQ^2 < -0.015 (with NSL)",
        lambda d: vrp_ndx.loc[d] < -0.015,
        lambda d: (vrp_ndx.loc[d] > 0.005) and (fv.vol_z.loc[d] < 0.5),
    ),
    eval_tqqq_challenger(
        "P6b-VRP-NDX-ZScore. Nasdaq-100 Matched VRP_NDX_Z < -1.2 De-lever / > -0.3 Re-lever (with NSL)",
        lambda d: pd.notna(vrp_ndx_z.loc[d]) and vrp_ndx_z.loc[d] < -1.2,
        lambda d: pd.notna(vrp_ndx_z.loc[d]) and vrp_ndx_z.loc[d] > -0.3,
    ),
    eval_tqqq_challenger(
        "P6c-VRP-SPX-Matched. S&P 500 Matched VRP = (VIX/100)^2 - RV21_SPY^2 < -0.015 (with NSL)",
        lambda d: vrp_spx.loc[d] < -0.015,
        lambda d: (vrp_spx.loc[d] > 0.000) and (fv.vol_z.loc[d] < 0.5),
    ),
    eval_tqqq_challenger(
        "P6d-VRP-SPX-ZScore. S&P 500 Matched VRP_SPX_Z < -1.2 De-lever / > -0.3 Re-lever (with NSL)",
        lambda d: pd.notna(vrp_spx_z.loc[d]) and vrp_spx_z.loc[d] < -1.2,
        lambda d: pd.notna(vrp_spx_z.loc[d]) and vrp_spx_z.loc[d] > -0.3,
    ),
    eval_tqqq_challenger(
        "P6e-VRP-NDX-Reentry. Standard Vol_Z > 1.2 Exit + Faster Re-entry when VRP_NDX_Z > +1.0",
        lambda d: fv.vol_z.loc[d] > 1.2,
        lambda d: (fv.vol_z.loc[d] < 0.3) or (fv.vol_z.loc[d] < 0.8 and pd.notna(vrp_ndx_z.loc[d]) and vrp_ndx_z.loc[d] > 1.0),
    ),
]
df_tqqq_chal = pd.DataFrame(tqqq_challenger_rows)
df_tqqq_chal.to_csv(os.path.join(OUT_DIR, "tqqq_challengers_p5_ebp_p6_vrp_summary.csv"), index=False)

pd.set_option("display.max_columns", 20)
pd.set_option("display.width", 280)
print("\n=== PART 1: V4 CHALLENGERS (P1 FROG-IN-THE-PAN, P2 52-WEEK HIGH, P3 VOLUME, P4 REMEDIATED PIT SUE & 3-TD EAR) ===")
print(df_v4_chal.to_string(index=False))
print("\n=== PART 2: DEDICATED P4 AUDIT (TRUE DOLLAR EPS vs OLD TIMESTAMP BUG, MISSING-DATA RULES, EX-2020-11) ===")
print(df_p4_audit.to_string(index=False))
print("\n=== PART 3: TQQQ SEP CHALLENGERS (P5 LIVE-ERA EBP >=2016-11 & P6 INDEX-MATCHED VRP_NDX / VRP_SPX) ===")
print(df_tqqq_chal.to_string(index=False))
