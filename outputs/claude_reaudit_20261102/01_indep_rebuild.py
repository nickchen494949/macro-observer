#!/usr/bin/env python3
"""
01 — INDEPENDENT raw-data rebuild (imports NOTHING from Gemini's v2_cleanroom_lib / v2_06 / v2_07).

Inputs (all under research/sector_stock_momentum/data/):
  sp500_hist_components.csv            PIT membership (last snapshot <= t)
  raw/, raw_tiingo/, raw_wiki/ *.json  daily adjclose (first source found, NO alias stitching)
  raw_open/*.json                      daily adj_open
  identity_resolutions.csv             documented ticker-reuse evidence (e.g. Yahoo 'EP' = Empire
                                       Petroleum, not El Paso). Used ONLY to DROP contaminated
                                       spells; we do not stitch replacement histories.
Definitions:
  month-end close = last daily obs in calendar month (valid only if within 7 days of month-end)
  mom/RS windows  : a-b  = C[t-a]/C[t-b]-1  for 12-1, 6-1, 3-1, 12-0, 6-0, 3-0 (stock and SPY)
  SMA200          : mean of last 200 daily adjcloses up to t (>=160 obs)
  roo             : adj_open first session after t -> adj_open first session after t+1M
  ret_exec        : roo if available, else month-end close-to-close (flag fb=True)  [same
                    *policy* as the audited engine's close fallback, independently implemented]
Output: _work/claude_panel.parquet
"""
import json, os
import numpy as np, pandas as pd
from _paths import DATA, WORK


def load(path, field):
    with open(path) as fh:
        d = json.load(fh)
    dts, v = d.get("dates") or [], d.get(field) or []
    if not dts or len(dts) != len(v):
        return None
    s = pd.Series(v, index=pd.to_datetime(dts), dtype=float).dropna().sort_index()
    return s[~s.index.duplicated(keep="last")]


def norm(t):
    return str(t).strip().replace(".", "-")


def main():
    h = pd.read_csv(f"{DATA}/sp500_hist_components.csv", parse_dates=["date"]).sort_values("date")
    form = pd.date_range("2009-12-31", "2026-08-31", freq="ME")
    members = {t: sorted({norm(x) for x in str(h[h["date"] <= t].iloc[-1]["tickers"]).split(",")}) for t in form}
    universe = sorted(set().union(*members.values()) | {"SPY"})

    # documented identity contamination -> drop (no stitching)
    drop = {}
    idr = pd.read_csv(f"{DATA}/identity_resolutions.csv")
    for r in idr.itertuples():
        tk, d = norm(r.ticker), pd.Timestamp(r.date)
        if r.action in ("exclude_before", "use_wiki_before", "use_archive_before"):
            drop.setdefault(tk, []).append((pd.Timestamp("1900-01-01"), d))
        elif r.action == "exclude_spell":
            drop.setdefault(tk, []).append((d, pd.Timestamp(r.date_to)))

    close, opn, src = {}, {}, {}
    for tk in universe:
        for sub in ("raw", "raw_tiingo", "raw_wiki"):
            p = f"{DATA}/{sub}/{tk}.json"
            if os.path.exists(p):
                s = load(p, "adjclose")
                if s is not None and len(s):
                    close[tk], src[tk] = s, sub
                    break
        p = f"{DATA}/raw_open/{tk}.json"
        if os.path.exists(p):
            o = load(p, "adj_open")
            if o is not None and len(o):
                opn[tk] = o
    print(f"[01] universe={len(universe)} with_close={len(close)} with_open={len(opn)} "
          f"missing_close={len(universe) - len(close)}")

    sessions = close["SPY"].index
    def next_sess(d):
        i = sessions.searchsorted(d, side="right")
        return sessions[i] if i < len(sessions) else None

    all_me = pd.date_range("2008-01-31", "2026-10-31", freq="ME")
    def month_end_px(s):
        m = s.resample("ME").last().reindex(all_me)
        lastd = s.index.to_series().resample("ME").last().reindex(all_me)
        return m.where((all_me - lastd) <= pd.Timedelta(days=7))

    ME = {tk: month_end_px(s) for tk, s in close.items()}
    SMA = {tk: s.rolling(200, min_periods=160).mean() for tk, s in close.items()}
    W = {"121": (1, 12), "61": (1, 6), "31": (1, 3), "120": (0, 12), "60": (0, 6), "30": (0, 3)}

    rows = []
    for t in form:
        d0, d1 = next_sess(t), next_sess(t + pd.offsets.MonthEnd(1))
        i = all_me.get_loc(t)
        spy = ME["SPY"]
        spyw = {k: spy.iloc[i - a] / spy.iloc[i - b] - 1 for k, (a, b) in W.items()}
        for tk in members[t]:
            if tk not in ME:
                continue
            if any(a <= t <= b for a, b in drop.get(tk, [])):
                continue
            m = ME[tk]
            c0 = m.iloc[i]
            if not np.isfinite(c0):
                continue
            def r(a, b):
                x, y = m.iloc[i - a], m.iloc[i - b]
                return x / y - 1 if (np.isfinite(x) and np.isfinite(y) and y > 0) else np.nan
            row = dict(t=t, ticker=tk, src=src[tk])
            for k, (a, b) in W.items():
                row["r" + k] = r(a, b)
                row["spy" + k] = spyw[k]
            s = close[tk]
            sm = SMA[tk].loc[:t]
            row["dist"] = (s.loc[:t].iloc[-1] / sm.iloc[-1] - 1) if len(sm) and np.isfinite(sm.iloc[-1]) else np.nan
            roo = np.nan
            if tk in opn and d0 is not None and d1 is not None:
                o = opn[tk]
                if d0 in o.index and d1 in o.index:
                    roo = o[d1] / o[d0] - 1
                elif d0 in o.index:
                    after = s.loc[d0:d1]
                    if len(after) and after.index[-1] < d1:      # delisted inside the month
                        roo = after.iloc[-1] / o[d0] - 1
            c1 = m.iloc[i + 1] if i + 1 < len(m) else np.nan
            if not np.isfinite(c1):                               # delisted: last available close in month
                nxt = s.loc[t + pd.Timedelta(days=1): t + pd.offsets.MonthEnd(1)]
                c1 = nxt.iloc[-1] if len(nxt) else np.nan
            rcc = c1 / c0 - 1 if np.isfinite(c1) else np.nan
            row.update(roo=roo, rcc=rcc, fb=not np.isfinite(roo),
                       ret_exec=roo if np.isfinite(roo) else rcc)
            rows.append(row)
    panel = pd.DataFrame(rows)
    panel.to_parquet(f"{WORK}/claude_panel.parquet")
    elig = panel[panel["r121"].notna()]
    print(f"[01] panel rows={len(panel)} | 12-1 eligible={len(elig)} | exec-return fallback share "
          f"(eligible rows)={elig['fb'].mean()*100:.1f}%")


if __name__ == "__main__":
    main()
