#!/usr/bin/env python3
"""
audit_v4_from_scratch.py — Independent adversarial audit of Symmetric_Sharpe_Top2_V4 (+ built-in V3 Election Reset).

Shares no code with independent_v4_symmetric_sharpe_top2_audit.py or build_portable_inputs_from_raw.py.
What it reuses from the project (cannot be avoided): raw vendor price files, raw membership files,
the panel's (src, sym) identity choice per ticker, the panel's clean_sector, and the regime CSV.
Each of those reused inputs is audited separately below.

Parts
  A  Rebuild membership (NDX yaml, SPX csv) and compare with panel universe
  B  Recompute 12-1 mom / vol / Sharpe and open-to-open hold returns from raw daily files
  C  Re-run V4 selection on recomputed features with new code; reconcile picks and returns vs ledger
  D  Data integrity of every invested pick (flags, missing returns, cross-vendor check, extremes)
  E  Open-executed daily NAV -> daily MaxDD, 2026 MaxDD
  F  Benchmarks, alpha vs QQQ (Newey-West), block bootstrap, concentration, sub-periods
  G  Robustness grid (hold-k, top-N, metric, cost, regime overlay, election reset)
  H  Regime overlay sample size + Election Reset permutation test
Outputs: outputs/v4_from_scratch_audit_20261114/*.csv and stdout summary.
"""
import glob
import json
import os
import functools
import numpy as np
import pandas as pd
import yaml

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "research", "sector_stock_momentum", "data")
INP = os.path.join(ROOT, "outputs", "pure_momentum_1985_2026_audit", "inputs")
ETF = os.path.join(ROOT, "outputs", "remediation_full_audit_20261104", "tiingo_etfs")
LEDGER_V0 = os.path.join(ROOT, "outputs", "v4_symmetric_sharpe_top2_20261113", "v4_symmetric_sharpe_top2_h5_v0_214m_ledger.csv")
LEDGER_V3 = os.path.join(ROOT, "outputs", "v4_symmetric_sharpe_top2_20261113", "v4_symmetric_sharpe_top2_h5_v3_214m_ledger.csv")
OUT = os.path.join(ROOT, "outputs", "v4_from_scratch_audit_20261114")
os.makedirs(OUT, exist_ok=True)
TIINGO_ROWS_DIRS = [os.path.join(ROOT, "outputs", "qqq_mom_top3_claude_audit_20261103", "tiingo"),
                    os.path.join(ROOT, "outputs", "tech_top1_independent_audit_20261103", "tiingo")]
COST = 0.0010
LOG = []


def say(*a):
    s = " ".join(str(x) for x in a)
    print(s)
    LOG.append(s)


# ----------------------------------------------------------------------------- loaders (own implementation)
def _frame(dates, close, opn):
    idx = pd.to_datetime(pd.Series(list(dates)).astype(str).str[:10])
    df = pd.DataFrame({"c": pd.to_numeric(pd.Series(list(close)), errors="coerce").values,
                       "o": (pd.to_numeric(pd.Series(list(opn)), errors="coerce").values if opn is not None else np.nan)},
                      index=idx.values)
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df = df[df["c"] > 0]
    df.loc[~(df["o"] > 0), "o"] = np.nan
    return df if len(df) else None


@functools.lru_cache(maxsize=1)
def _wiki():
    w = pd.read_parquet(os.path.join(DATA, "wiki_bulk", "wiki_prices.parquet"), columns=["ticker", "date", "adj_close"])
    o = pd.read_parquet(os.path.join(DATA, "wiki_bulk", "wiki_open.parquet"))
    w = w.merge(o, on=["ticker", "date"], how="left")
    return {k: g for k, g in w.groupby("ticker")}


@functools.lru_cache(maxsize=None)
def load(src, sym):
    try:
        if src == "yahoo":
            for sub in ("raw_open", "raw"):
                p = os.path.join(DATA, sub, f"{sym}.json")
                if os.path.exists(p):
                    j = json.load(open(p))
                    return _frame(j["dates"], j["adjclose"], j.get("adj_open"))
        elif src == "tiingo":
            for d in TIINGO_ROWS_DIRS:
                p = os.path.join(d, f"{sym}.json")
                if os.path.exists(p):
                    r = pd.DataFrame(json.load(open(p))["rows"])
                    return _frame(r["date"], r["adjClose"], r.get("adjOpen"))
            p = os.path.join(DATA, "raw_tiingo", f"{sym}.json")
            if os.path.exists(p):
                j = json.load(open(p))
                return _frame(j["dates"], j["adjclose"], None)
        elif src in ("archive", "raw_ndx"):
            p = os.path.join(DATA, "raw_archive" if src == "archive" else "raw_ndx", f"{sym}.json")
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
    df = pd.DataFrame(json.load(open(os.path.join(ETF, f"{sym}.json"))))
    df["date"] = pd.to_datetime(df["date"].str[:10])
    df = df.set_index("date").sort_index()
    df = df[~df.index.duplicated(keep="last")]
    return pd.DataFrame({"c": df["adjClose"].astype(float), "o": df["adjOpen"].astype(float)})


ETFS = {s: load_etf(s) for s in ["SPY", "QQQ", "SGOV", "BIL"]}
CAL = ETFS["SPY"].index


def next_session(dt):
    i = CAL.searchsorted(pd.Timestamp(dt), side="right")
    return CAL[i] if i < len(CAL) else None


def last_close(df, dt, stale=7):
    s = df["c"].loc[:dt]
    if not len(s) or (pd.Timestamp(dt) - s.index[-1]).days > stale:
        return np.nan, None
    return float(s.iloc[-1]), s.index[-1]


def features(df, t):
    t1, t12 = t - pd.offsets.MonthEnd(1), t - pd.offsets.MonthEnd(12)
    p1, d1 = last_close(df, t1)
    p12, d12 = last_close(df, t12)
    p0, _ = last_close(df, t)
    if not (np.isfinite(p1) and np.isfinite(p12) and np.isfinite(p0)):
        return np.nan, np.nan
    seg = df["c"].loc[d12:d1]
    if len(seg) < 121 or np.diff(seg.index.values).astype("timedelta64[D]").astype(int).max() > 30:
        return np.nan, np.nan
    r = seg.pct_change().dropna().values
    return p1 / p12 - 1.0, float(np.std(r, ddof=1) * np.sqrt(252.0))


def hold_return(df, t, d1_override=None):
    d0 = next_session(t)
    d1 = d1_override or next_session(t + pd.offsets.MonthEnd(1))
    if d0 is None or d0 not in df.index:
        return np.nan, "no_entry"
    if d1 is not None and d1 in df.index:
        o0, o1 = df.at[d0, "o"], df.at[d1, "o"]
        if d1_override is not None and np.isfinite(o0):
            return df.at[d1, "c"] / o0 - 1.0, "sample_end_cutoff"
        if np.isfinite(o0) and np.isfinite(o1):
            return o1 / o0 - 1.0, "open_open"
        return df.at[d1, "c"] / df.at[d0, "c"] - 1.0, "close_close"
    seg = df["c"].loc[d0:]
    if len(seg) and (d1 is None or df.index.max() < d1):
        base = df.at[d0, "o"] if np.isfinite(df.at[d0, "o"]) else df.at[d0, "c"]
        if d1_override is not None:
            return seg.iloc[-1] / base - 1.0, "sample_end_cutoff"
        return seg.iloc[-1] / base - 1.0, "delist_mna_last_close"
    return np.nan, "unpriced"


# ----------------------------------------------------------------------------- inputs
P_SPX = pd.read_parquet(os.path.join(INP, "v3_spx_panel_214m.parquet"))
P_NDX = pd.read_parquet(os.path.join(INP, "v3_ndx_panel_214m.parquet"))
REG = pd.read_csv(os.path.join(INP, "v3_regime_and_cash_214m.csv"))
for p in (P_SPX, P_NDX):
    p["t"] = pd.to_datetime(p["t"])
REG["t"] = pd.to_datetime(REG["t"])
LED = pd.read_csv(LEDGER_V3)
MONTHS = [t for t in sorted(P_SPX["t"].unique()) if pd.Timestamp("2008-12-31") <= t <= pd.Timestamp("2026-09-30")]
LAST_T = pd.Timestamp("2026-09-30")
LAST_D1 = pd.Timestamp("2026-10-29")  # data end used by the project for the partial live month
YM = {t: (t + pd.offsets.MonthBegin(1)).strftime("%Y-%m") for t in MONTHS}
SEP = dict(zip(REG["t"], REG["sep_on"].astype(bool)))
CASH = dict(zip(REG["t"], REG["ret_sgov_actual"].astype(float)))
RF = dict(zip(REG["t"], REG["rf_tbill"].astype(float)))
DEC_RESET = {t for t in MONTHS if YM[t] in ("2010-12", "2018-12", "2022-12")}
JAN_RESET = {t for t in MONTHS if YM[t] in ("2011-01", "2019-01", "2023-01")}

# ============================================================================= PART A: membership
say("\n=== PART A: membership rebuild ===")
ndx_years = {}
for f in sorted(glob.glob(os.path.join(DATA, "nasdaq100_src", "n100-ticker-changes-*.yaml"))):
    d = yaml.load(open(f), Loader=yaml.BaseLoader)
    ch = [(pd.Timestamp(str(k)), set((v or {}).get("union") or []), set((v or {}).get("difference") or []))
          for k, v in (d.get("changes") or {}).items()]
    ndx_years[int(d["year"])] = (set(d["tickers_on_Jan_1"]), sorted(ch, key=lambda x: x[0]))
spx_hist = pd.read_csv(os.path.join(DATA, "sp500_hist_components.csv"), parse_dates=["date"]).sort_values("date")
mem_rows = []
for t in MONTHS + [pd.Timestamp("2026-10-31")]:
    y = min(t.year, max(ndx_years))
    s, ch = ndx_years[y]
    s = set(s)
    for dt, add, rem in ch:
        if dt <= t:
            s = (s - rem) | add
    pn = set(P_NDX.loc[P_NDX["t"] == t, "ticker"])
    sp = set(str(spx_hist[spx_hist["date"] <= t].iloc[-1]["tickers"]).split(","))
    ps = set(P_SPX.loc[P_SPX["t"] == t, "ticker"])
    mem_rows.append({"t": t, "ndx_n": len(s), "ndx_mismatch": len(s ^ pn), "spx_n": len(sp), "spx_mismatch": len(sp ^ ps),
                     "spx_last_snapshot": spx_hist[spx_hist["date"] <= t].iloc[-1]["date"].date()})
mem = pd.DataFrame(mem_rows)
mem.to_csv(os.path.join(OUT, "A_membership_rebuild.csv"), index=False)
say(f"NDX months with set mismatch: {(mem.ndx_mismatch > 0).sum()} / {len(mem)}; SPX: {(mem.spx_mismatch > 0).sum()} / {len(mem)}")
say(f"NDX size range {mem.ndx_n.min()}..{mem.ndx_n.max()}; latest SPX snapshot used: {mem.spx_last_snapshot.max()}")
say("Note: NDX 'year' file for t.year > last file reuses the last file's Jan-1 list + changes (check last year coverage):",
    max(ndx_years), "| SPX csv max date:", spx_hist["date"].max().date())

# ============================================================================= PART B: recompute features & returns
say("\n=== PART B: recompute 12-1 features and hold returns from raw daily files ===")


def recompute(panel, t_filter=None):
    rows = []
    for r in panel.itertuples(index=False):
        if t_filter is not None and r.t not in t_filter:
            continue
        if not isinstance(r.src, str):
            rows.append((r.t, r.ticker, np.nan, np.nan, np.nan, "no_series"))
            continue
        df = load(r.src, r.sym)
        if df is None:
            rows.append((r.t, r.ticker, np.nan, np.nan, np.nan, "load_fail"))
            continue
        m, v = features(df, r.t)
        hr, fl = hold_return(df, r.t, LAST_D1 if r.t == LAST_T else None)
        rows.append((r.t, r.ticker, m, v, hr, fl))
    out = pd.DataFrame(rows, columns=["t", "ticker", "mom_x", "vol_x", "hr_x", "flag_x"])
    out["sharpe_x"] = out["mom_x"] / out["vol_x"]
    return out


off_ts = {t for t in MONTHS if not SEP[t]}
RN = recompute(P_NDX[P_NDX["t"].isin(MONTHS)])
RS = recompute(P_SPX[P_SPX["t"].isin(MONTHS)], t_filter=off_ts | DEC_RESET | JAN_RESET)
NX = P_NDX.merge(RN, on=["t", "ticker"], how="left")
SX = P_SPX[P_SPX["t"].isin(off_ts | DEC_RESET | JAN_RESET)].merge(RS, on=["t", "ticker"], how="left")
for nm, X in (("NDX", NX), ("SPX(OFF months)", SX)):
    both = X["sharpe"].notna() & X["sharpe_x"].notna()
    only_panel = (X["sharpe"].notna() & X["sharpe_x"].isna()).sum()
    only_mine = (X["sharpe"].isna() & X["sharpe_x"].notna()).sum()
    dmom = (X.loc[both, "mom"] - X.loc[both, "mom_x"]).abs()
    hb = X["hold_ret"].notna() & X["hr_x"].notna()
    dhr = (X.loc[hb, "hold_ret"] - X.loc[hb, "hr_x"]).abs()
    say(f"{nm}: rows={len(X)} | both-valid={both.sum()} | panel-only={only_panel} | mine-only={only_mine} | "
        f"|dmom|>1e-6: {(dmom > 1e-6).sum()} | |dhold|>1e-6: {(dhr > 1e-6).sum()} (max {dhr.max():.4f})")
NX.to_csv(os.path.join(OUT, "B_ndx_feature_recompute.csv"), index=False)

# ============================================================================= PART C: independent selection + sim


def rank_pick(cands, held, k_hold, n_pick=2):
    """cands: list of tickers sorted best-first. Keep held names with rank<=k_hold, fill to n_pick by rank."""
    rk = {tk: i + 1 for i, tk in enumerate(cands)}
    keep = [tk for tk in held if rk.get(tk, 10 ** 9) <= k_hold]
    for tk in cands:
        if len(keep) >= n_pick:
            break
        if tk not in keep:
            keep.append(tk)
    return keep[:n_pick]


def run_v4(ndx, spx, *, metric="sharpe", k_on=5, k_off=5, n_on=2, n_off=2, w_off_stock=0.50, cost=COST,
           election=True, regime=True, sec_metric="mom", ret_col="hold_ret", nan_ret=None, start=None):
    """Monthly sim. ndx/spx: frames with t,ticker,<metric>,mom,<ret_col>,(clean_sector). Returns ledger DataFrame."""
    gq = {t: g for t, g in ndx.groupby("t")}
    gs = {t: g for t, g in spx.groupby("t")}
    held_q, held_b = [], []
    prev_w = {}
    rows = []
    for t in MONTHS:
        if election and t in JAN_RESET:
            held_q, held_b = [], []
        g = gq[t]
        g = g[g[metric].notna()].sort_values([metric, "ticker"], ascending=[False, True])
        held_q = rank_pick(list(g["ticker"]), held_q, k_on, n_on)
        s = gs.get(t)
        bsec, picks_b = None, []
        if s is not None:
            s = s[(s["clean_sector"] != "Information Technology") & s["mom"].notna() & s[metric].notna()]
            bsec = s.groupby("clean_sector")[sec_metric].mean().sort_index().idxmax()
            sb = s[s["clean_sector"] == bsec].sort_values([metric, "ticker"], ascending=[False, True])
            held_b = rank_pick(list(sb["ticker"]), held_b, k_off, n_off)
            picks_b = list(held_b)
        on = SEP[t] if regime else True
        w = {}
        if election and t in DEC_RESET:
            w["CASH"] = 1.0
        elif on:
            for tk in held_q:
                w[tk] = w.get(tk, 0) + 1.0 / n_on
        else:
            for tk in picks_b:
                w[tk] = w.get(tk, 0) + w_off_stock / n_off
            w["CASH"] = 1.0 - w_off_stock
        rl = {}
        for tk in w:
            if tk == "CASH":
                rl[tk] = CASH[t]
            else:
                v = np.nan
                for src in (g, s):
                    if src is not None:
                        hit = src.loc[src["ticker"] == tk, ret_col]
                        if len(hit):
                            v = hit.iloc[0]
                            break
                if pd.isna(v):
                    if nan_ret is None:
                        raise ValueError(f"Missing hold_ret for invested stock {tk} at {t}")
                    v = nan_ret
                rl[tk] = float(v)
        gross = sum(w[k] * rl[k] for k in w)
        keys = set(w) | set(prev_w)
        to = sum(abs(w.get(k, 0) - prev_w.get(k, 0)) for k in keys) if prev_w else sum(w.values())
        net = (1 + gross) * (1 - cost * to) - 1
        eq = 1 + gross
        prev_w = {k: w[k] * (1 + rl[k]) / eq for k in w}
        rows.append({"t": t, "ym": YM[t], "sep_on": on, "q": "|".join(held_q), "b": "|".join(picks_b), "bsec": bsec,
                     "w": json.dumps({k: round(v, 4) for k, v in sorted(w.items())}), "to": to, "gross": gross, "net": net})
    out = pd.DataFrame(rows)
    if start:
        out = out[out["ym"] >= start].reset_index(drop=True)
    return out


def stats(r, rf=None):
    r = np.asarray(r, float)
    n = len(r)
    wealth = np.cumprod(1 + r)
    cagr = wealth[-1] ** (12 / n) - 1
    ex = r - (np.asarray(rf) if rf is not None else 0)
    sh = ex.mean() / r.std(ddof=1) * np.sqrt(12)
    w = np.concatenate([[1], wealth])
    mdd = (w / np.maximum.accumulate(w) - 1).min()
    return cagr, sh, mdd


say("\n=== PART C: independent re-implementation (Default V4 No-ER and V4 + ER) ===")
spx_off_cols = P_SPX[["t", "ticker", "mom", "sharpe", "hold_ret", "clean_sector"]]
ndx_cols = P_NDX[["t", "ticker", "mom", "sharpe", "hold_ret"]]
LED0 = pd.read_csv(LEDGER_V0)
L_panel_v0 = run_v4(ndx_cols, spx_off_cols, election=False)  # Default V4 (No Election Reset)
L_panel = run_v4(ndx_cols, spx_off_cols, election=True)      # V4 + Election Reset
LED["q"] = LED["q1"] + "|" + LED["q2"]
m0 = L_panel_v0.merge(LED0[["ym", "net_ret", "q1", "q2", "bs1", "bs2", "sep_on"]], on="ym")
c0, s0, d0_mdd = stats(L_panel_v0["net"], [RF[t] for t in MONTHS])
c0_213, s0_213, d0_213 = stats(L_panel_v0["net"].iloc[:213], [RF[t] for t in MONTHS[:213]])
c0_204, s0_204, d0_204 = stats(L_panel_v0["net"].iloc[:204], [RF[t] for t in MONTHS[:204]])
say(f"My code on panel features vs official Default V4 (No ER) ledger: max |net diff|={(m0['net'] - m0['net_ret']).abs().max():.2e} | "
    f"214M CAGR={c0:.4%} Sharpe={s0:.3f} MDD={d0_mdd:.2%} | Complete 213M (to 2026-09) CAGR={c0_213:.4%} Sh={s0_213:.3f} | Ex-2026 204M CAGR={c0_204:.4%} Sh={s0_204:.3f}")
m = L_panel.merge(LED[["ym", "net_ret", "q1", "q2", "bs1", "bs2", "sep_on"]], on="ym")
used_q = m["sep_on_x"] & ~m["ym"].isin(["2010-12", "2018-12", "2022-12"])
pick_mismatch = (used_q & (m["q"] != m["q1"] + "|" + m["q2"])).sum()
off_m = ~m["sep_on_x"] & ~m["ym"].isin(["2010-12", "2018-12", "2022-12"])
pick_mismatch_b = (off_m & (m["b"] != m["bs1"] + "|" + m["bs2"])).sum()
ret_gap = (m["net"] - m["net_ret"]).abs()
say(f"My code on panel features vs official V4+ER ledger: QQQ pick mismatches={pick_mismatch}, BestSec pick mismatches={pick_mismatch_b}, "
    f"max |net diff|={ret_gap.max():.2e} (months > 1bp: {(ret_gap > 1e-4).sum()})")
c, s_, d = stats(L_panel["net"], [RF[t] for t in MONTHS])
say(f"  My code V4+ER 214M: CAGR={c:.4%} Sharpe={s_:.3f} MonthlyMDD={d:.2%}  (official V4+ER: 60.78% / 1.444 / -27.99%)")
if (ret_gap > 1e-4).any():
    say("  Months with >1bp net diff:\n" + m.loc[ret_gap > 1e-4, ["ym", "net", "net_ret"]].to_string(index=False))

# Selection on MY recomputed features (both Default No-ER and +ER)
ndx_x = NX[["t", "ticker", "mom_x", "sharpe_x", "hr_x"]].rename(columns={"mom_x": "mom", "sharpe_x": "sharpe", "hr_x": "hold_ret"})
spx_x = SX[["t", "ticker", "mom_x", "sharpe_x", "hr_x", "clean_sector"]].rename(columns={"mom_x": "mom", "sharpe_x": "sharpe", "hr_x": "hold_ret"})
spx_x = pd.concat([spx_x, spx_off_cols[~spx_off_cols["t"].isin(set(spx_x["t"]))]], ignore_index=True)
L_raw_v0 = run_v4(ndx_x, spx_x, election=False)
c0_raw, s0_raw, d0_raw = stats(L_raw_v0["net"], [RF[t] for t in MONTHS])
c0_raw_213, s0_raw_213, _ = stats(L_raw_v0["net"].iloc[:213], [RF[t] for t in MONTHS[:213]])
c0_raw_204, s0_raw_204, _ = stats(L_raw_v0["net"].iloc[:204], [RF[t] for t in MONTHS[:204]])
say(f"Default V4 (No ER) on features recomputed from raw files: 214M CAGR={c0_raw:.4%} Sh={s0_raw:.3f} MDD={d0_raw:.2%} | "
    f"Complete 213M CAGR={c0_raw_213:.4%} Sh={s0_raw_213:.3f} | Ex-2026 204M CAGR={c0_raw_204:.4%} Sh={s0_raw_204:.3f}")
L_raw = run_v4(ndx_x, spx_x, election=True)
c2, s2, d2 = stats(L_raw["net"], [RF[t] for t in MONTHS])
diff_q = (L_raw["q"] != L_panel["q"]) & L_panel["sep_on"]
say(f"V4+ER on features recomputed from raw files (no flat-price filter): CAGR={c2:.4%} Sharpe={s2:.3f} MDD={d2:.2%} | "
    f"ON-month QQQ pick-set differences vs panel: {diff_q.sum()}")
if diff_q.any():
    say(pd.DataFrame({"ym": L_raw["ym"], "panel": L_panel["q"], "raw": L_raw["q"]})[diff_q].to_string(index=False))
L_panel_v0.to_csv(os.path.join(OUT, "C_my_ledger_v0_panel_features.csv"), index=False)
L_raw_v0.to_csv(os.path.join(OUT, "C_my_ledger_v0_raw_features.csv"), index=False)
L_panel.to_csv(os.path.join(OUT, "C_my_ledger_panel_features.csv"), index=False)
L_raw.to_csv(os.path.join(OUT, "C_my_ledger_raw_features.csv"), index=False)

# ============================================================================= PART D: pick-level integrity
say("\n=== PART D: integrity of every invested position ===")
MNA_NOTES = {
    ("2013-06", "VMED"): "Virgin Media acquired by Liberty Global (completed 2013-06-07: $17.50 cash + 0.2582 LBTYA + 0.1928 LBTYK = ~$51.00/sh deal value; entered 2013-06-03 open $49.65, exited 2013-06-07 close $51.00 = +2.72%)",
    ("2019-03", "FOX"): "21st Century Fox (TFCF) Disney merger + Fox Corp spin-off (completed 2019-03-19/20: 1/3 sh new FOX ~$12.92 + $38.00 Disney consideration = ~$50.92/sh [+1.11% vs $50.36 open]; ledger conservatively uses last pre-close $49.61 = -1.49%)",
    ("2019-03", "FOXA"): "21st Century Fox Class A (TFCFA) Disney merger + Fox Corp spin-off (completed 2019-03-19/20: 1/3 sh new FOXA ~$12.92 + $38.00 Disney consideration = ~$50.92/sh [+0.57% vs $50.63 open]; ledger conservatively uses last pre-close $49.69 = -1.86%)",
}
pos = []
for r in L_panel.itertuples(index=False):
    for tk, wt in json.loads(r.w).items():
        if tk == "CASH":
            continue
        src_panel = P_NDX if r.sep_on else P_SPX
        row = src_panel[(src_panel["t"] == r.t) & (src_panel["ticker"] == tk)].iloc[0]
        raw_flag = row["ret_flag"]
        if r.t == LAST_T:
            audit_flag = "sample_end_cutoff_20261029"
            corp_note = "Active S&P 500 constituent; holding period truncated at 2026-10-29 sample cutoff date (NOT delisted)"
        elif raw_flag == "delist_last_close":
            audit_flag = "delist_mna_last_close"
            corp_note = MNA_NOTES.get((r.ym, tk), "Corporate action / delisting exit at last traded close")
        else:
            audit_flag = raw_flag
            corp_note = ""
        pos.append({"ym": r.ym, "t": r.t, "ticker": tk, "w": wt, "leg": "QQQ" if r.sep_on else "BestSec",
                    "src": row["src"], "sym": row["sym"], "flag": audit_flag, "panel_raw_flag": raw_flag,
                    "corp_action_note": corp_note, "hold_ret": row["hold_ret"],
                    "mom": row["mom"], "vol": row["vol"]})
POS = pd.DataFrame(pos)
say(f"Invested stock-months: {len(POS)} | unique tickers: {POS.ticker.nunique()}")
say("Audited return flag breakdown (separating true M&A delistings from 2026-10-29 sample-end cutoff):\n" + POS["flag"].value_counts().to_string())
say("True M&A / corporate reorganization exits (3 positions) + sample-end cutoff positions (2 positions):\n" +
    POS[POS["flag"] != "open_open"][["ym", "ticker", "leg", "flag", "hold_ret", "corp_action_note"]].to_string(index=False))
say(f"Missing hold_ret: {POS['hold_ret'].isna().sum()}")
say("Price source of invested positions:\n" + POS["src"].value_counts().to_string())

# cross-vendor check for every invested position: compare BOTH open_open and close_close against ALL available alternative vendors
VENDORS = [("yahoo", None), ("tiingo", None), ("wiki", None), ("raw_ndx", None), ("archive", None)]
xv = []
for p in POS.itertuples(index=False):
    d0 = next_session(p.t)
    d1 = LAST_D1 if p.t == LAST_T else next_session(p.t + pd.offsets.MonthEnd(1))
    alts_cc = {}
    alts_oo = {}
    for src, _ in VENDORS:
        for sym in dict.fromkeys([p.ticker, p.ticker.replace(".", "-"), p.sym]):
            if src == p.src and sym == p.sym:
                continue
            df = load(src, sym)
            if df is None or d0 not in df.index or d1 not in df.index:
                continue
            alts_cc[f"{src}:{sym}"] = float(df.at[d1, "c"] / df.at[d0, "c"] - 1)
            if p.t == LAST_T and np.isfinite(df.at[d0, "o"]):
                alts_oo[f"{src}:{sym}"] = float(df.at[d1, "c"] / df.at[d0, "o"] - 1)
            elif np.isfinite(df.at[d0, "o"]) and np.isfinite(df.at[d1, "o"]):
                alts_oo[f"{src}:{sym}"] = float(df.at[d1, "o"] / df.at[d0, "o"] - 1)
    own = load(p.src, p.sym)
    own_cc = float(own.at[d1, "c"] / own.at[d0, "c"] - 1) if (own is not None and d0 in own.index and d1 in own.index) else np.nan
    own_oo = float(p.hold_ret)
    best_cc = min(alts_cc.items(), key=lambda kv: abs(kv[1] - own_cc)) if alts_cc and np.isfinite(own_cc) else (None, np.nan)
    worst_cc = max(alts_cc.items(), key=lambda kv: abs(kv[1] - own_cc)) if alts_cc and np.isfinite(own_cc) else (None, np.nan)
    best_oo = min(alts_oo.items(), key=lambda kv: abs(kv[1] - own_oo)) if alts_oo and np.isfinite(own_oo) else (None, np.nan)
    worst_oo = max(alts_oo.items(), key=lambda kv: abs(kv[1] - own_oo)) if alts_oo and np.isfinite(own_oo) else (None, np.nan)
    xv.append({
        "ym": p.ym, "ticker": p.ticker, "src": f"{p.src}:{p.sym}",
        "hold_ret_open_open": own_oo,
        "n_alt_oo": len(alts_oo),
        "closest_alt_oo": best_oo[0], "closest_alt_open_open": best_oo[1],
        "min_absdiff_oo": abs(own_oo - best_oo[1]) if np.isfinite(best_oo[1]) else np.nan,
        "worst_alt_oo": worst_oo[0], "worst_alt_open_open": worst_oo[1],
        "max_absdiff_oo": abs(own_oo - worst_oo[1]) if np.isfinite(worst_oo[1]) else np.nan,
        "own_close_close": own_cc,
        "n_alt": len(alts_cc),
        "alt": best_cc[0], "alt_close_close": best_cc[1],
        "absdiff": abs(own_cc - best_cc[1]) if np.isfinite(best_cc[1]) else np.nan,
        "worst_alt_cc": worst_cc[0], "worst_alt_close_close": worst_cc[1],
        "max_absdiff_cc": abs(own_cc - worst_cc[1]) if np.isfinite(worst_cc[1]) else np.nan,
    })
XV = pd.DataFrame(xv)
XV.to_csv(os.path.join(OUT, "D_cross_vendor_check.csv"), index=False)
say(f"Cross-vendor Open-to-Open: positions with >=1 alt vendor with open prices: {(XV.n_alt_oo > 0).sum()}/{len(XV)}; "
    f"min_diff > 1%: {(XV.min_absdiff_oo > 0.01).sum()}; max_diff (across ALL alt vendors) > 1%: {(XV.max_absdiff_oo > 0.01).sum()}; "
    f"max_diff > 5%: {(XV.max_absdiff_oo > 0.05).sum()}")
say(f"Cross-vendor Close-to-Close: positions with >=1 alt vendor: {(XV.n_alt > 0).sum()}/{len(XV)}; "
    f"min_diff > 1%: {(XV.absdiff > 0.01).sum()}; max_diff (across ALL alt vendors) > 1%: {(XV.max_absdiff_cc > 0.01).sum()}; "
    f"max_diff > 5%: {(XV.max_absdiff_cc > 0.05).sum()}")
single_oo = XV[XV.n_alt_oo == 0]
say(f"Breakdown of the {len(single_oo)} positions without a 2nd open-price vendor: "
    f"{(single_oo.n_alt > 0).sum()} have a verified 2nd close-price vendor (max_diff_cc <= {single_oo.loc[single_oo.n_alt > 0, 'max_absdiff_cc'].max():.4%}); "
    f"of the remaining {(single_oo.n_alt == 0).sum()} single-vendor positions, {(single_oo.loc[single_oo.n_alt == 0, 'ym'] >= '2018-04').sum()} are in 2018-04..2026-10 (after Quandl WIKI ended in 2018-03).")
if (XV.max_absdiff_oo > 0.01).any():
    say("Positions with Open-to-Open max vendor diff > 1%:\n" +
        XV[XV.max_absdiff_oo > 0.01][["ym", "ticker", "src", "hold_ret_open_open", "worst_alt_oo", "worst_alt_open_open", "max_absdiff_oo"]].sort_values("max_absdiff_oo", ascending=False).head(15).to_string(index=False))
ext = POS[POS["hold_ret"].abs() > 0.30].sort_values("hold_ret")
say(f"Extreme position-months |r|>30%: {len(ext)}")
say(ext[["ym", "ticker", "leg", "src", "flag", "hold_ret"]].to_string(index=False))
POS.to_csv(os.path.join(OUT, "D_invested_positions.csv"), index=False)

# ============================================================================= PART E: open-executed daily NAV
say("\n=== PART E: open-executed daily NAV (weights set at d0 open, drift daily, exit at next d0 open) ===")
nav, dates, navs = 1.0, [], []
prev_w = {}
for r in L_panel.itertuples(index=False):
    w = json.loads(r.w)
    t = r.t
    d0 = next_session(t)
    d1 = LAST_D1 if t == LAST_T else next_session(t + pd.offsets.MonthEnd(1))
    nav *= (1 - COST * r.to)
    series = {}
    for tk in w:
        if tk == "CASH":
            cs = "SGOV" if (d0 >= pd.Timestamp("2020-06-01") and d0 in ETFS["SGOV"].index) else "BIL"
            series[tk] = ETFS[cs]
        else:
            pr = POS[(POS.ym == r.ym) & (POS.ticker == tk)].iloc[0]
            series[tk] = load(pr.src, pr.sym)
    days = CAL[(CAL >= d0) & (CAL < d1)] if t != LAST_T else CAL[(CAL >= d0) & (CAL <= d1)]
    base = {}
    for tk, df in series.items():
        o = df.at[d0, "o"] if (d0 in df.index and np.isfinite(df.at[d0, "o"])) else (df.at[d0, "c"] if d0 in df.index else np.nan)
        base[tk] = o
    for d in days:
        v = 0.0
        for tk, wt in w.items():
            df = series[tk]
            px = df["c"].loc[:d]
            v += wt * (float(px.iloc[-1]) / base[tk] if len(px) else 1.0)
        dates.append(d)
        navs.append(nav * v)
    # month end value at next open (consistent with monthly ledger)
    v_end = 0.0
    for tk, wt in w.items():
        df = series[tk]
        if t == LAST_T:
            v_end += wt * float(df["c"].loc[:d1].iloc[-1]) / base[tk]
        elif d1 in df.index and np.isfinite(df.at[d1, "o"]):
            v_end += wt * df.at[d1, "o"] / base[tk]
        else:
            v_end += wt * float(df["c"].loc[:d1].iloc[-1]) / base[tk]
    nav *= v_end
DN = pd.Series(navs, index=pd.DatetimeIndex(dates))
DN.to_csv(os.path.join(OUT, "E_daily_nav.csv"))
dd = DN / DN.cummax() - 1
dret = DN.pct_change().dropna()
say(f"Daily NAV end={DN.iloc[-1]:.1f} (monthly ledger wealth={np.prod(1 + L_panel['net']):.1f})")
say(f"Daily MaxDD (full)={dd.min():.2%} at {dd.idxmin().date()} (peak {DN.loc[:dd.idxmin()].idxmax().date()})")
d26 = DN.loc["2026-01-01":]
dd26 = (d26 / d26.cummax() - 1).min()
dd26b = (d26 / DN.loc[:"2026-12-31"].cummax().loc["2026-01-01":] - 1).min()
say(f"2026 MaxDD (peak reset 2026-01-01)={dd26:.2%}; 2026 drawdown vs all-time peak={dd26b:.2%}")
say(f"Daily Sharpe (rf=0)={dret.mean() / dret.std() * np.sqrt(252):.3f}; daily ann. vol={dret.std() * np.sqrt(252):.2%}")
worst = dd.groupby(dd.index.year).min()
say("Worst daily drawdown by year:\n" + worst.map(lambda x: f"{x:.1%}").to_string())

# ============================================================================= PART F: benchmarks & statistics
say("\n=== PART F: benchmarks, alpha, bootstrap, concentration ===")


def etf_month(sym, t):
    df = ETFS[sym]
    d0 = next_session(t)
    if t == LAST_T:
        return df.at[LAST_D1, "c"] / df.at[d0, "o"] - 1
    d1 = next_session(t + pd.offsets.MonthEnd(1))
    return df.at[d1, "o"] / df.at[d0, "o"] - 1


R = pd.DataFrame({"ym": [YM[t] for t in MONTHS], "v4": L_panel["net"].values,
                  "qqq": [etf_month("QQQ", t) for t in MONTHS], "spy": [etf_month("SPY", t) for t in MONTHS],
                  "rf": [RF[t] for t in MONTHS], "sep_on": [SEP[t] for t in MONTHS]})
for col in ("v4", "qqq", "spy"):
    c, s_, d = stats(R[col], R["rf"])
    say(f"{col:4s}: CAGR={c:.2%} Sharpe={s_:.3f} MonthlyMDD={d:.2%}")
# alpha vs QQQ with Newey-West(6)
y = (R["v4"] - R["rf"]).values
x = (R["qqq"] - R["rf"]).values
X = np.column_stack([np.ones_like(x), x])
b = np.linalg.lstsq(X, y, rcond=None)[0]
e = y - X @ b
L_ = 6
S = (X * e[:, None]).T @ (X * e[:, None])
for l in range(1, L_ + 1):
    wl = 1 - l / (L_ + 1)
    G = (X[l:] * e[l:, None]).T @ (X[:-l] * e[:-l, None])
    S += wl * (G + G.T)
XtXi = np.linalg.inv(X.T @ X)
V = XtXi @ S @ XtXi
say(f"Alpha vs QQQ: {b[0] * 12:.2%}/yr (NW t={b[0] / np.sqrt(V[0, 0]):.2f}), beta={b[1]:.2f} (t={b[1] / np.sqrt(V[1, 1]):.2f})")

# stationary block bootstrap on monthly returns (mean block 6), paired with QQQ
rng = np.random.default_rng(20261114)
n = len(R)
B = 5000
res = []
arr = R[["v4", "qqq", "rf"]].values
for _ in range(B):
    idx = []
    i = rng.integers(n)
    while len(idx) < n:
        idx.append(i)
        i = rng.integers(n) if rng.random() < 1 / 6 else (i + 1) % n
    a = arr[idx]
    cv = np.prod(1 + a[:, 0]) ** (12 / n) - 1
    cq = np.prod(1 + a[:, 1]) ** (12 / n) - 1
    sv = (a[:, 0] - a[:, 2]).mean() / a[:, 0].std(ddof=1) * np.sqrt(12)
    sq = (a[:, 1] - a[:, 2]).mean() / a[:, 1].std(ddof=1) * np.sqrt(12)
    res.append((cv, sv, cv - cq, sv - sq))
res = np.array(res)
q = lambda k: np.percentile(res[:, k], [2.5, 50, 97.5])
say(f"Bootstrap 95% CI  CAGR {q(0)[0]:.1%}..{q(0)[2]:.1%} | Sharpe {q(1)[0]:.2f}..{q(1)[2]:.2f} | "
    f"CAGR-QQQ {q(2)[0]:.1%}..{q(2)[2]:.1%} | Sharpe-QQQ {q(3)[0]:.2f}..{q(3)[2]:.2f}")

# concentration
lw = np.log1p(R["v4"].values)
order = np.argsort(-lw)
tot = lw.sum()
for k in (5, 10, 20):
    rest = np.delete(R["v4"].values, order[:k])
    say(f"Drop best {k:2d} months -> CAGR of remaining {len(rest)} months = {np.prod(1 + rest) ** (12 / len(rest)) - 1:.2%} "
        f"(best {k} months = {lw[order[:k]].sum() / tot:.0%} of total log-wealth)")
top = R.iloc[order[:10]][["ym", "v4", "qqq"]].copy()
top["picks"] = [L_panel.set_index("ym").loc[y_, "w"] for y_ in top["ym"]]
say("Best 10 months:\n" + top.to_string(index=False))
# trade-level contribution (position-level log contribution)
POS["contrib"] = np.log1p(POS["w"] * POS["hold_ret"].fillna(0))
tc = POS.groupby("ticker")["contrib"].sum().sort_values(ascending=False)
say("Top 10 tickers by summed log-contribution (approx):\n" + tc.head(10).map(lambda v: f"{v:+.2f}").to_string())
say(f"Top 5 tickers share of summed log-contribution: {tc.head(5).sum() / tc.sum():.0%}")
# yearly
R["year"] = R["ym"].str[:4]
yr = R.groupby("year").apply(lambda g: pd.Series({"v4": np.prod(1 + g.v4) - 1, "qqq": np.prod(1 + g.qqq) - 1, "n": len(g)}))
say("Calendar-year returns:\n" + yr.to_string(float_format=lambda v: f"{v:+.1%}"))
for a, b_ in (("2009-01", "2014-12"), ("2015-01", "2020-12"), ("2021-01", "2026-10"), ("2009-01", "2019-12"), ("2020-01", "2026-10")):
    sub = R[(R.ym >= a) & (R.ym <= b_)]
    c, s_, d = stats(sub["v4"], sub["rf"])
    cq, sq, dq = stats(sub["qqq"], sub["rf"])
    say(f"{a}..{b_}: V4 CAGR={c:.1%} Sh={s_:.2f} MDD={d:.1%} | QQQ CAGR={cq:.1%} Sh={sq:.2f}")
R.to_csv(os.path.join(OUT, "F_monthly_returns_vs_benchmarks.csv"), index=False)

# ============================================================================= PART G: robustness grid
say("\n=== PART G: robustness grid (panel features, my engine) ===")
grid = []


def add(label, **kw):
    L = run_v4(ndx_cols, spx_off_cols, **kw)
    c, s_, d = stats(L["net"], [RF[t] for t in MONTHS])
    sub = L[L.ym >= "2015-01"]
    c15, s15, _ = stats(sub["net"], [RF[t] for t in MONTHS if YM[t] >= "2015-01"])
    grid.append({"variant": label, "CAGR": c, "Sharpe": s_, "MDD": d, "CAGR_2015+": c15, "Sharpe_2015+": s15})


add("V4 default (Sharpe, top2, hold5, ER on)")
add("No Election Reset (V0)", election=False)
add("No regime overlay (always QQQ top2) + ER", regime=False)
add("No regime, no ER (pure QQQ Sharpe top2/hold5)", regime=False, election=False)
for k in (2, 3, 4, 6, 8, 10):
    add(f"hold<= {k} (both legs)", k_on=k, k_off=k)
for nn in (1, 3, 4, 5):
    add(f"top-{nn} / hold<= {max(5, nn + 3)}", n_on=nn, n_off=nn, k_on=max(5, nn + 3), k_off=max(5, nn + 3))
add("metric = raw 12-1 momentum", metric="mom")
for cbp in (0.0025, 0.0050, 0.0100):
    add(f"cost {cbp * 1e4:.0f}bp/side", cost=cbp)
add("OFF leg 100% stocks (no 50% cash)", w_off_stock=1.0)
add("OFF leg 0% stocks (100% cash)", w_off_stock=0.0)
add("missing returns = -100% (worst case)", nan_ret=-1.0)
G = pd.DataFrame(grid)
G.to_csv(os.path.join(OUT, "G_robustness_grid.csv"), index=False)
say(G.to_string(index=False, float_format=lambda v: f"{v:.3f}"))

# ============================================================================= PART H: regime + election evidence
say("\n=== PART H: regime overlay sample size and Election Reset permutation ===")
off = R[~R.sep_on]
say(f"SEP=OFF months: {len(off)}; first={off.ym.min()} last={off.ym.max()}; years with any OFF: {sorted(off.ym.str[:4].unique())}")
say("Official FOMC SEP medians start 2015-09-17 (ALFRED archival series 2015-12) => 2009-01..2015-08 regime is ON by construction (no median published).")
L_noreg = run_v4(ndx_cols, spx_off_cols, regime=False)
Rm = R.copy()
Rm["noreg"] = L_noreg["net"].values
o = Rm[~Rm.sep_on]
say(f"Within the {len(o)} OFF months: V4 cumulative={np.prod(1 + o.v4) - 1:+.1%} vs staying in QQQ-top2={np.prod(1 + o.noreg) - 1:+.1%} "
    f"vs QQQ ETF={np.prod(1 + o.qqq) - 1:+.1%}")
# split OFF episodes
o = o.assign(ep=(o.ym.apply(lambda s: pd.Period(s, 'M')).diff().apply(lambda x: x.n if pd.notna(x) else 1) != 1).cumsum())
for ep, g in o.groupby("ep"):
    say(f"  OFF episode {g.ym.min()}..{g.ym.max()} ({len(g)}m): V4 {np.prod(1 + g.v4) - 1:+.1%} | stay-QQQtop2 {np.prod(1 + g.noreg) - 1:+.1%} | QQQ {np.prod(1 + g.qqq) - 1:+.1%}")

# Election reset: compare gain from 3 chosen Decembers vs random 3-December sets
L0 = run_v4(ndx_cols, spx_off_cols, election=False)
dec_rows = L0[L0.ym.str.endswith("-12")].copy()
dec_rows["cash"] = [CASH[t] for t in dec_rows.t]
dec_rows["gain"] = np.log1p(dec_rows["cash"]) - np.log1p(dec_rows["net"])
chosen = dec_rows[dec_rows.ym.isin(["2010-12", "2018-12", "2022-12"])]["gain"].sum()
from itertools import combinations
gains = [dec_rows.iloc[list(c)]["gain"].sum() for c in combinations(range(len(dec_rows)), 3)]
say("V0 December returns: " + ", ".join(f"{a[:4]}:{b:+.1%}" for a, b in zip(dec_rows.ym, dec_rows.net)))
say(f"Cash-in-December log gain, chosen 3 = {chosen:+.3f}; rank among all C({len(dec_rows)},3)={len(gains)} sets: "
    f"top {np.mean(np.array(gains) >= chosen - 1e-12):.2%}  (in-sample: the trigger years were chosen after seeing these months)")
say("Midterm flip U->D events in sample: 3. Any rule fitted to 3 events has ~zero statistical power.")

with open(os.path.join(OUT, "audit_log.txt"), "w") as f:
    f.write("\n".join(LOG))
say(f"\nWrote outputs to {OUT}")
