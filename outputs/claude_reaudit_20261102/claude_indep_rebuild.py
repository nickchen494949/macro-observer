#!/usr/bin/env python3
"""
Claude independent re-audit — rebuild 12-1 momentum strategies from raw JSON WITHOUT
importing anything from Gemini's v2_cleanroom_lib / v2_06 / v2_07.

Deliberately naive & transparent:
  * membership  : sp500_hist_components.csv (last snapshot <= t)
  * prices      : data/raw/{T}.json adjclose  (fallback raw_tiingo / raw_wiki) — no alias stitching
  * month-end   : last daily obs in calendar month, valid only if within 7 days of month-end
  * 12-1        : C[t-1]/C[t-12]-1 ; 6-1, 3-1 analog ; RS(6-0) = C[t]/C[t-6]-1
  * SMA200      : mean of last 200 daily adjcloses up to t (>=160 obs)
  * exec        : adj_open first session after t -> adj_open first session after t+1M
Outputs per-formation candidate panel to parquet for later comparison.
"""
import json, os, sys, glob
import numpy as np, pandas as pd

ROOT = "/Users/happygolucky/Desktop/宏观观察器/research/sector_stock_momentum/data"
OUT = os.path.dirname(os.path.abspath(__file__))

def load(path, field):
    with open(path) as fh:
        d = json.load(fh)
    dts, v = d.get("dates") or [], d.get(field) or []
    if not dts or len(dts) != len(v):
        return None
    s = pd.Series(v, index=pd.to_datetime(dts), dtype=float).dropna().sort_index()
    return s[~s.index.duplicated(keep="last")]

def norm(t): return str(t).strip().replace(".", "-")

h = pd.read_csv(f"{ROOT}/sp500_hist_components.csv", parse_dates=["date"]).sort_values("date")
form = pd.date_range("2009-12-31", "2026-08-31", freq="ME")
members = {}
for t in form:
    row = h[h["date"] <= t].iloc[-1]
    members[t] = sorted({norm(x) for x in str(row["tickers"]).split(",")})
universe = sorted(set().union(*members.values()) | {"SPY"})

close, opn, src = {}, {}, {}
for tk in universe:
    for d in ("raw", "raw_tiingo", "raw_wiki"):
        p = f"{ROOT}/{d}/{tk}.json"
        if os.path.exists(p):
            s = load(p, "adjclose")
            if s is not None and len(s):
                close[tk] = s; src[tk] = d; break
    p = f"{ROOT}/raw_open/{tk}.json"
    if os.path.exists(p):
        o = load(p, "adj_open")
        if o is not None and len(o):
            opn[tk] = o
missing = [t for t in universe if t not in close]
print(f"universe={len(universe)} with_close={len(close)} with_open={len(opn)} missing_close={len(missing)}")

sessions = close["SPY"].index
def next_sess(d):
    i = sessions.searchsorted(d, side="right")
    return sessions[i] if i < len(sessions) else None

all_me = pd.date_range("2008-01-31", "2026-10-31", freq="ME")
def month_end_px(s):
    m = s.resample("ME").last().reindex(all_me)
    lastd = s.index.to_series().resample("ME").last().reindex(all_me)
    ok = (all_me - lastd) <= pd.Timedelta(days=7)
    return m.where(ok)

ME = {tk: month_end_px(s) for tk, s in close.items()}
SMA = {tk: s.rolling(200, min_periods=160).mean() for tk, s in close.items()}

rows = []
for t in form:
    d0 = next_sess(t); d1 = next_sess(t + pd.offsets.MonthEnd(1))
    i = all_me.get_loc(t)
    spy = ME["SPY"]
    spy60 = spy.iloc[i] / spy.iloc[i - 6] - 1
    for tk in members[t]:
        if tk not in ME: continue
        m = ME[tk]
        c0 = m.iloc[i]
        if not np.isfinite(c0): continue
        def r(a, b):
            x, y = m.iloc[i - a], m.iloc[i - b]
            return x / y - 1 if (np.isfinite(x) and np.isfinite(y) and y > 0) else np.nan
        m121, m61, m31 = r(1, 12), r(1, 6), r(1, 3)
        rs60 = r(0, 6)
        s = close[tk]; sm = SMA[tk].loc[:t]
        dist = (s.loc[:t].iloc[-1] / sm.iloc[-1] - 1) if len(sm) and np.isfinite(sm.iloc[-1]) else np.nan
        # open-to-open
        roo, st = np.nan, "na"
        if tk in opn and d0 is not None and d1 is not None:
            o = opn[tk]
            if d0 in o.index and d1 in o.index:
                roo, st = o[d1] / o[d0] - 1, "ok"
            elif d0 in o.index:
                after = s.loc[d0:d1]
                if len(after) and after.index[-1] < d1:
                    roo, st = after.iloc[-1] / o[d0] - 1, "delisted"
        # close-to-close
        c1 = m.iloc[i + 1] if i + 1 < len(m) else np.nan
        rcc = c1 / c0 - 1 if np.isfinite(c1) else np.nan
        rows.append(dict(t=t, ticker=tk, src=src[tk], m121=m121, m61=m61, m31=m31, rs60=rs60,
                         spy60=spy60, dist=dist, roo=roo, st_oo=st, rcc=rcc))
panel = pd.DataFrame(rows)
panel.to_parquet(f"{OUT}/claude_panel.parquet")
print("panel rows", len(panel), "missing tickers sample:", missing[:40])
