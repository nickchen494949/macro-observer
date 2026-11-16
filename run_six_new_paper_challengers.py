#!/usr/bin/env python3
"""
run_six_new_paper_challengers.py — Clean-Room Challenger Evaluation of 6 Published Academic Papers (2026-11-16)
===============================================================================================================
STRICT CHALLENGER PROTOCOL:
- Frozen V4 (`Symmetric_Sharpe_Top2_V4`) and Frozen V1-Daily TQQQ (`1.2/0.3 + Open NSL`) are UNCHANGED.
- Every Challenger changes ONLY ONE ranking factor / signal at a time, keeping:
  * Identical constituent universe (`NDX_100` in SEP=ON, `#1 Non-IT BestSec` in SEP=OFF),
  * Identical `SEP` regime routing,
  * Identical `Top-2 / Hold <= 5` buffer structure,
  * Identical Next-Day Open (`adjOpen`) execution and `10bp/side` transaction cost,
  * Zero silent `0.0` return fallbacks (hard `ValueError` on any missing `hold_ret`),
  * Full evaluation across: Full 214M (2009-2026), Complete 213M (to 2026-09), Ex-2026 (2009-2025),
    Pre-2021 (2009-2020), Drop-Best-5M, Drop-Best-10M, Open-Executed Daily MaxDD, Monthly MaxDD,
    Annual Turnover, and Trade Win Rate.

Papers Tested:
  P1 (V4): Da, Gurun & Warachka (2014, RFS) — "Frog in the Pan: Continuous Information and Momentum"
           * `ID = sign(PRET) * (%neg - %pos)` over the 12-1 daily formation window (`FIP_continuity = %pos - %neg` for winners),
             plus `Smooth_Sharpe` (12-1 Sharpe after winsorizing/removing the 5 largest single-day jump spikes).
  P2 (V4): George & Hwang (2004, JF) — "The 52-Week High and Momentum Investing"
           * `GH_52w = P_t / max(P_{t-252..t})` (proximity to trailing 252-trading-day high at formation date t).
  P3 (V4): Lee & Swaminathan (2000, JF) — "Price Momentum and Trading Volume"
           * `Vol_Ratio = mean(DV_{t-63..t}) / mean(DV_{t-252..t})` and `Log_DV_Turn` from daily dollar volume (`daily_dv.parquet`),
             testing both Low-Volume ("early-stage underreaction") and High-Volume ("breakout confirmation") among Sharpe Top-5.
  P4 (V4): Chan, Jegadeesh & Lakonishok (1996, JF) — "Momentum Strategies" (Post-Earnings Announcement Drift / SUE & EAR)
           * Strictly Point-in-Time SEC EDGAR 10-Q/10-K filing dates (`available_date <= t` from `eps_quarterly_pit.parquet`):
             (a) `SUE_pit`: YoY quarterly diluted EPS surprise standardized by trailing 8-quarter EPS change std;
             (b) `EAR_3d`: 3-day abnormal return (`r_stock - r_SPY`) around the most recent quarterly SEC filing date `filed <= t`.
  P5 (TQQQ): Gilchrist & Zakrajsek (2012, AER) — "Credit Spreads and Business Cycle Fluctuations" (Official Fed EBP)
           * Official Federal Reserve `ebp_csv.csv` (`ebp` and `est_prob`) with strict 1-month publication lag (month M EBP used
             only after the 5th trading day of month M+1) to avoid backfill/publication look-ahead.
  P6 (TQQQ): Bollerslev, Tauchen & Zhou (2009, RFS) — "Expected Stock Returns and Variance Risk Premia"
           * True Variance Risk Premium `VRP_t = IV_var_t - RV_var_t` in variance units (`(VIX_t/100)^2 - rvol_21_t^2`).
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
# 1. Load Raw Daily Close, Daily Volume/Dollar-Volume, and PIT Quarterly EPS/Filing Dates
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
if eps_list:
    EPS_PIT = pd.concat(eps_list, ignore_index=True)
    EPS_PIT["filed"] = pd.to_datetime(EPS_PIT["filed"])
    EPS_PIT["available_date"] = pd.to_datetime(EPS_PIT["available_date"])
    EPS_PIT["period_end"] = pd.to_datetime(EPS_PIT["period_end"])
    e_dil = pd.to_numeric(EPS_PIT["filed_eps_diluted"], errors="coerce")
    e_bas = pd.to_numeric(EPS_PIT["filed_eps_basic"], errors="coerce")
    EPS_PIT["eps_val"] = e_dil.combine_first(e_bas).astype(float)
    EPS_PIT = EPS_PIT.dropna(subset=["ticker", "available_date", "eps_val"]).sort_values(["ticker", "period_end", "available_date"])
    EPS_PIT_FIRST = EPS_PIT.drop_duplicates(subset=["ticker", "period_end"], keep="first").copy().reset_index(drop=True)
    EPS_PIT_FIRST["eps_lag4"] = EPS_PIT_FIRST.groupby("ticker")["eps_val"].shift(4).astype(float)
    EPS_PIT_FIRST["eps_diff"] = (EPS_PIT_FIRST["eps_val"] - EPS_PIT_FIRST["eps_lag4"]).astype(float)
    EPS_PIT_FIRST["eps_diff_std"] = (
        EPS_PIT_FIRST.groupby("ticker")["eps_diff"]
        .rolling(8, min_periods=4)
        .std(ddof=1)
        .reset_index(level=0, drop=True)
        .astype(float)
    )
    EPS_PIT_FIRST["sue"] = (EPS_PIT_FIRST["eps_diff"] / EPS_PIT_FIRST["eps_diff_std"].replace(0.0, np.nan)).clip(-5.0, 5.0)
    eps_pct = (EPS_PIT_FIRST["eps_diff"] / EPS_PIT_FIRST["eps_lag4"].abs().clip(lower=0.10)).clip(-5.0, 5.0)
    EPS_PIT_FIRST["sue"] = EPS_PIT_FIRST["sue"].combine_first(eps_pct)
    EPS_BY_TK = {tk: g.sort_values("available_date") for tk, g in EPS_PIT_FIRST.groupby("ticker")}
else:
    EPS_BY_TK = {}

spy_ret = ETFS["SPY"]["c"].pct_change(fill_method=None).dropna()

# ------------------------------------------------------------------------------
# 2. Compute Paper Features (P1 FIP, P2 52W-High, P3 Volume, P4 PIT SUE & EAR)
# ------------------------------------------------------------------------------
def enrich_panel_with_paper_features(df_in):
    fip_cont = []       # P1: %pos - %neg over 12-1M window (Da, Gurun & Warachka 2014)
    smooth_sh = []      # P1b: 12-1 Sharpe after removing top 5 single-day jump spikes
    gh_52w = []         # P2: P_t / max(P_{t-252..t}) (George & Hwang 2004)
    vol_ratio_3_12 = [] # P3: 3M / 12M dollar volume ratio (Lee & Swaminathan 2000)
    vol_12m_log = []    # P3b: Log 12-1M average daily dollar volume
    sue_pit = []        # P4a: Point-in-time SEC quarterly SUE (available_date <= t)
    ear_3d_pit = []     # P4b: 3-day abnormal return around most recent SEC filing date <= t

    for row in df_in[["t", "ticker", "src", "sym", "mom", "vol", "sharpe"]].itertuples(index=False):
        s_c = close_cache.get((row.src, row.sym))
        r_s = ret_cache.get((row.src, row.sym))
        if s_c is None or r_s is None or pd.isna(row.sharpe):
            fip_cont.append(np.nan)
            smooth_sh.append(np.nan)
            gh_52w.append(np.nan)
            vol_ratio_3_12.append(np.nan)
            vol_12m_log.append(np.nan)
            sue_pit.append(np.nan)
            ear_3d_pit.append(np.nan)
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
            # Higher (pct_pos - pct_neg) = more continuous positive daily progression
            sign_p = 1.0 if row.mom >= 0 else -1.0
            fip_cont.append(sign_p * (pct_pos - pct_neg))
            # Smooth Sharpe: remove top 5 largest positive daily jump outliers
            rv_sorted = np.sort(rv)
            rv_ex5 = rv_sorted[:-5]
            comp_ex5 = float(np.prod(1.0 + rv_ex5) - 1.0)
            std_ex5 = float(np.std(rv_ex5, ddof=1) * np.sqrt(252.0))
            smooth_sh.append(comp_ex5 / std_ex5 if std_ex5 > 1e-8 else float(row.sharpe))
        else:
            fip_cont.append(0.0)
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
                vol_12m_log.append(float(np.log1p(s_dv.iloc[:-21].mean())))
            else:
                vol_ratio_3_12.append(1.0)
                vol_12m_log.append(np.nan)
        else:
            vol_ratio_3_12.append(1.0)
            vol_12m_log.append(np.nan)

        # P4: Point-in-Time Earnings Surprise (Chan, Jegadeesh & Lakonishok 1996: SUE & 3-Day EAR around filing date <= t)
        eg = EPS_BY_TK.get(row.ticker)
        if eg is not None:
            # Strict PIT filter: available_date <= t and within last 180 days (latest quarterly report)
            eg_avail = eg[(eg["available_date"] <= t) & (eg["available_date"] >= t - pd.Timedelta(days=180))]
            if len(eg_avail):
                last_rep = eg_avail.iloc[-1]
                sue_pit.append(float(last_rep["sue"]) if pd.notna(last_rep["sue"]) else 0.0)
                f_dt = last_rep["filed"]
                # 3-day abnormal return CAR[-1, +1] around SEC filing date (capped at t so zero look-ahead)
                end_ear = min(t, f_dt + pd.Timedelta(days=2))
                start_ear = f_dt - pd.Timedelta(days=2)
                r_win = r_s.loc[(r_s.index >= start_ear) & (r_s.index <= end_ear)]
                m_win = spy_ret.reindex(r_win.index).fillna(0.0)
                if len(r_win):
                    ear_3d_pit.append(float((1.0 + r_win).prod() - (1.0 + m_win).prod()))
                else:
                    ear_3d_pit.append(0.0)
            else:
                sue_pit.append(0.0)
                ear_3d_pit.append(0.0)
        else:
            sue_pit.append(0.0)
            ear_3d_pit.append(0.0)

    out = df_in.copy()
    out["fip_cont"] = fip_cont
    out["smooth_sh"] = smooth_sh
    out["gh_52w"] = gh_52w
    out["vol_ratio_3_12"] = vol_ratio_3_12
    out["vol_12m_log"] = vol_12m_log
    out["sue_pit"] = sue_pit
    out["ear_3d_pit"] = ear_3d_pit

    # Build Cross-Sectional Percentile Rank Composites per formation date t (parameter-free 50/50 rank blends)
    def add_cs_blends(df_p):
        df_p = df_p.copy()
        for col_new, name_blend in [
            ("fip_cont", "blend_fip"),
            ("gh_52w", "blend_gh52w"),
            ("vol_ratio_3_12", "blend_vol_high"),
            ("sue_pit", "blend_sue"),
            ("ear_3d_pit", "blend_ear"),
        ]:
            r_sh = df_p.groupby("t")["sharpe"].rank(pct=True)
            r_nf = df_p.groupby("t")[col_new].rank(pct=True)
            df_p[name_blend] = 0.5 * r_sh + 0.5 * r_nf.fillna(0.5)
        # Also Lee & Swaminathan (2000) Low-Volume Momentum ("early-stage underreaction": higher Sharpe + lower volume ratio)
        r_sh = df_p.groupby("t")["sharpe"].rank(pct=True)
        r_vlow = (-df_p["vol_ratio_3_12"]).groupby(df_p["t"]).rank(pct=True)
        df_p["blend_vol_low"] = 0.5 * r_sh + 0.5 * r_vlow.fillna(0.5)
        return df_p

    return add_cs_blends(out)


print("Computing P1 (FIP), P2 (52W High), P3 (Volume), P4 (PIT SUE & EAR) features from raw files...")
NDX_E = enrich_panel_with_paper_features(P_NDX)
BSEC_E = enrich_panel_with_paper_features(P_BSEC)


# ------------------------------------------------------------------------------
# 3. Selection & Simulation Helpers for V4 Challengers (Including Daily MaxDD!)
# ------------------------------------------------------------------------------
def select_top2_within_sharpe_top5(panel_df, tiebreaker_col, ascending_tie=False, hold_k=5):
    """
    User's exact protocol:
    - Candidate pool is restricted to current 12-1 Sharpe Top-5 (`rk_sharpe <= 5`).
    - Existing holdings are kept if they remain inside Sharpe Top-5 (`rk_sharpe <= hold_k`).
    - New entries are chosen from Sharpe Top-5 ranked by `tiebreaker_col`!
    """
    picks = {}
    held = []
    for t, g in panel_df.groupby("t", sort=True):
        gv = g[g["sharpe"].notna() & g["mom"].notna()].sort_values(["sharpe", "ticker"], ascending=[False, True]).reset_index(drop=True)
        rk_sh = {tk: i + 1 for i, tk in enumerate(gv["ticker"])}
        kept = [tk for tk in held if rk_sh.get(tk, 999) <= hold_k]
        top5 = gv.iloc[:5].copy()
        top5 = top5.sort_values([tiebreaker_col, "sharpe", "ticker"], ascending=[ascending_tie, False, True])
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
    s_213 = s_net.loc[:"2026-09"]
    c213 = float(np.prod(1.0 + s_213) ** (12.0 / len(s_213)) - 1.0)
    s_09_20 = s_net.loc[:"2020-12"]
    c_09_20 = float(np.prod(1.0 + s_09_20) ** (12.0 / len(s_09_20)) - 1.0)
    s_25 = s_net.loc[:"2025-12"]
    rf_25 = pd.Series([float(iv4.reg_map[t]["rf_tbill"]) for t in MONTHS if YM[t] <= "2025-12"], index=s_25.index)
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
        "Complete_213M_CAGR_%": round(c213 * 100, 2),
        "Ex2026_09_25_CAGR_%": round(c204 * 100, 2),
        "Pre2021_09_20_CAGR_%": round(c_09_20 * 100, 2),
        "Sharpe_214M": round(sr214, 3),
        "Sharpe_Ex2026": round(sh_25, 3),
        "Daily_MaxDD_%": round(daily_mdd * 100, 2),
        "Monthly_MaxDD_%": round(mdd_m * 100, 2),
        "DropBest5M_CAGR_%": round(c_drop5 * 100, 2),
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
# 4. Run All V4 Challengers (P1 FIP, P2 52W High, P3 Volume, P4 PIT SUE & EAR)
# ------------------------------------------------------------------------------
v4_challenger_rows = []

# Baseline
pk_q0 = iv4.select_qqq_sharpe_top2(NDX_E, hold_k=5, reset_t_set=None)
pk_b0 = iv4.select_bestsec_sharpe_top2(BSEC_E, hold_k=5, reset_t_set=None)
v4_challenger_rows.append(eval_v4_challenger("0. Frozen V4 Baseline (12-1 Sharpe, Top-2 / Hold<=5)", pk_q0, pk_b0))

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

# P4: Earnings Surprise SUE & 3-Day Filing EAR (Chan, Jegadeesh & Lakonishok 1996, JF — Strict SEC PIT `available_date <= t`)
v4_challenger_rows.append(eval_v4_challenger(
    "P4a-SUE-Top5Tie. Pick Top-2 Highest PIT Quarterly SUE Inside Sharpe Top-5",
    select_top2_within_sharpe_top5(NDX_E, "sue_pit", ascending_tie=False),
    select_top2_within_sharpe_top5(BSEC_E, "sue_pit", ascending_tie=False),
))
v4_challenger_rows.append(eval_v4_challenger(
    "P4b-EAR3d-Top5Tie. Pick Top-2 Highest 3-Day Filing Abnormal Return (EAR) Inside Sharpe Top-5",
    select_top2_within_sharpe_top5(NDX_E, "ear_3d_pit", ascending_tie=False),
    select_top2_within_sharpe_top5(BSEC_E, "ear_3d_pit", ascending_tie=False),
))
v4_challenger_rows.append(run_v4_col_challenger("P4c-SUE-Blend. 50/50 Rank Blend (12-1 Sharpe + PIT Quarterly SUE)", "blend_sue"))
v4_challenger_rows.append(run_v4_col_challenger("P4d-EAR3d-Blend. 50/50 Rank Blend (12-1 Sharpe + PIT 3-Day Filing EAR)", "blend_ear"))

df_v4_chal = pd.DataFrame(v4_challenger_rows)
df_v4_chal.to_csv(os.path.join(OUT_DIR, "v4_ challengers_p1_p2_p3_p4_summary.csv".replace(" ", "")), index=False)


# ------------------------------------------------------------------------------
# 5. Run TQQQ SEP Challengers (P5 Gilchrist-Zakrajsek EBP & P6 Bollerslev-Tauchen-Zhou VRP)
# ------------------------------------------------------------------------------
idx_real = fv.idx_real
sep_exact = fv.sep_exact_fomc

# Load Official Federal Reserve EBP (`fed_official_ebp.csv`) with STRICT 1-Month Publication Lag:
# Month M's EBP is published in early month M+1 -> available starting on the 5th trading day of month M+1!
ebp_df = pd.read_csv(os.path.join(ROOT, "outputs", "four_paper_experiments_20261116", "fed_official_ebp.csv"))
ebp_df["ym_avail"] = (pd.to_datetime(ebp_df["date"]) + pd.DateOffset(months=1)).dt.strftime("%Y-%m")
ebp_map = dict(zip(ebp_df["ym_avail"], ebp_df["ebp"].astype(float)))
prob_map = dict(zip(ebp_df["ym_avail"], ebp_df["est_prob"].astype(float)))

ebp_daily = pd.Series(0.0, index=idx_real)
prob_daily = pd.Series(0.0, index=idx_real)
cur_ebp, cur_prob = 0.0, 0.0
for dt in idx_real:
    ym_s = dt.strftime("%Y-%m")
    # Update on or after the 7th calendar day (~5th trading day) of month M+1
    if dt.day >= 7 and ym_s in ebp_map:
        cur_ebp = ebp_map[ym_s]
        cur_prob = prob_map[ym_s]
    ebp_daily.loc[dt] = cur_ebp
    prob_daily.loc[dt] = cur_prob

# Load CBOE VIX (`data/yahoo/_VIX.json`) and compute True Variance Risk Premium (Bollerslev, Tauchen & Zhou 2009):
# IV_var_t = (VIX_t / 100)^2 (annualized implied variance), RV_var_t = (rvol_20_t / 100)^2 (annualized 20d realized variance)
vix_raw = json.load(open(os.path.join(ROOT, "data", "yahoo", "_VIX.json")))["values"]
vix_s = pd.Series({pd.Timestamp(d): float(v) for d, v in vix_raw if v is not None}).sort_index().reindex(idx_real).ffill().bfill()
iv_var = (vix_s / 100.0) ** 2
rv_var = (fv.rvol_20.loc[idx_real].bfill() / 100.0) ** 2
vrp_var = iv_var - rv_var  # Positive = implied variance > realized variance; Negative = realized variance spike > implied variance
vrp_z = (vrp_var - vrp_var.rolling(252).mean()) / vrp_var.rolling(252).std(ddof=1)


def eval_tqqq_challenger(label, mode="baseline"):
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
        dt = idx_real[i]
        prev_dt = idx_real[i - 1]
        s_on = bool(sep_exact.loc[prev_dt])
        vz = float(fv.vol_z.loc[prev_dt])
        ebp_v = float(ebp_daily.loc[prev_dt])
        vrp_v = float(vrp_var.loc[prev_dt])
        vrp_zv = float(vrp_z.loc[prev_dt]) if pd.notna(vrp_z.loc[prev_dt]) else 0.0

        r_on = assets[pos]["adjOpen"].iloc[i] / assets[pos]["adjClose"].iloc[i - 1] - 1.0
        eq_open_pre = eq * (1.0 + r_on)
        can_sell_nsl = (eq >= entry_eq and eq_open_pre * cost_mult >= entry_eq)

        if not s_on:
            target_pos = "0x"
        else:
            if mode == "baseline":
                if pos == "0x":
                    target_pos = "3x" if vz <= 1.2 else "1x"
                elif pos == "3x":
                    target_pos = "1x" if (vz > 1.2 and can_sell_nsl) else "3x"
                else:
                    target_pos = "3x" if vz < 0.3 else "1x"
            elif mode == "p5a_ebp_delever_050":
                # P5a: De-lever 3x -> 1x (with NSL) if Vol_Z > 1.2 OR lagged Fed EBP > +0.50% (credit risk appetite contraction)
                trig_cond = (vz > 1.2) or (ebp_v > 0.50)
                rec_cond = (vz < 0.3) and (ebp_v <= 0.25)
                if pos == "0x":
                    target_pos = "3x" if not trig_cond else "1x"
                elif pos == "3x":
                    target_pos = "1x" if (trig_cond and can_sell_nsl) else "3x"
                else:
                    target_pos = "3x" if rec_cond else "1x"
            elif mode == "p5b_ebp_hard_cash_075":
                # P5b: Exit to 0x Cash if lagged Fed EBP > +0.75% (severe credit freeze, e.g., GFC / COVID), else V1-Daily
                if ebp_v > 0.75:
                    target_pos = "0x"
                elif pos == "0x":
                    target_pos = "3x" if vz <= 1.2 else "1x"
                elif pos == "3x":
                    target_pos = "1x" if (vz > 1.2 and can_sell_nsl) else "3x"
                else:
                    target_pos = "3x" if vz < 0.3 else "1x"
            elif mode == "p6a_vrp_negative_delever":
                # P6a: Bollerslev-Tauchen-Zhou (2009) VRP < -0.015 (realized variance exceeds implied variance by >150 var bps) triggers 3x -> 1x (with NSL)
                trig_cond = (vrp_v < -0.015)
                rec_cond = (vrp_v > 0.005) and (vz < 0.5)
                if pos == "0x":
                    target_pos = "3x" if not trig_cond else "1x"
                elif pos == "3x":
                    target_pos = "1x" if (trig_cond and can_sell_nsl) else "3x"
                else:
                    target_pos = "3x" if rec_cond else "1x"
            elif mode == "p6b_volz_plus_vrp_reentry":
                # P6b: Standard Vol_Z > 1.2 exit, but allow faster 1x -> 3x re-entry when VRP_Z > +1.0 (fear premium rich while realized vol subsides)
                if pos == "0x":
                    target_pos = "3x" if vz <= 1.2 else "1x"
                elif pos == "3x":
                    target_pos = "1x" if (vz > 1.2 and can_sell_nsl) else "3x"
                else:
                    target_pos = "3x" if (vz < 0.3 or (vz < 0.8 and vrp_zv > 1.0)) else "1x"

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
    m_nav = s_eq.resample("ME").last()
    m_mdd = float((m_nav / m_nav.cummax() - 1.0).min()) * 100.0
    return {
        "TQQQ_Challenger_Variant": label,
        "Full_10_26_CAGR_%": round(cagr, 2),
        "Ex2026_10_25_CAGR_%": round(cagr25, 2),
        "Daily_Sharpe_rf0": round(sh, 3),
        "Daily_MaxDD_%": round(max_dd * 100.0, 2),
        "Monthly_MaxDD_%": round(m_mdd, 2),
        "Total_Switches": sw,
    }


tqqq_challenger_rows = [
    eval_tqqq_challenger("0. Frozen V1-Daily Baseline (SEP + Vol_Z 1.2/0.3 + Open NSL)", "baseline"),
    eval_tqqq_challenger("P5a-EBP. De-lever 3x->1x (NSL) when Lagged Fed EBP > +0.50% or Vol_Z > 1.2", "p5a_ebp_delever_050"),
    eval_tqqq_challenger("P5b-EBP. Exit to Cash when Lagged Fed EBP > +0.75% (Severe Credit Freeze)", "p5b_ebp_hard_cash_075"),
    eval_tqqq_challenger("P6a-VRP. De-lever 3x->1x (NSL) when Bollerslev VRP = IV^2 - RV^2 < -0.015", "p6a_vrp_negative_delever"),
    eval_tqqq_challenger("P6b-VRP. Faster Re-entry 1x->3x when VRP_Z > +1.0 (High Implied Fear Premium)", "p6b_volz_plus_vrp_reentry"),
]
df_tqqq_chal = pd.DataFrame(tqqq_challenger_rows)
df_tqqq_chal.to_csv(os.path.join(OUT_DIR, "tqqq_challengers_p5_ebp_p6_vrp_summary.csv"), index=False)

pd.set_option("display.max_columns", 20)
pd.set_option("display.width", 260)
print("\n=== PART 1: V4 CHALLENGERS (P1 FROG-IN-THE-PAN, P2 52-WEEK HIGH, P3 VOLUME, P4 PIT EARNINGS SURPRISE) ===")
print(df_v4_chal.to_string(index=False))
print("\n=== PART 2: TQQQ SEP CHALLENGERS (P5 GILCHRIST-ZAKRAJSEK EBP & P6 BOLLERSLEV-TAUCHEN-ZHOU VRP) ===")
print(df_tqqq_chal.to_string(index=False))
