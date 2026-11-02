#!/usr/bin/env python3
"""
03 — INDEPENDENT diagnosis of every month where Claude's naive rebuild and the Gemini ledger disagree.
For each stock Gemini holds that Claude does not, classify WHY, from raw files only.
Output: results/03_mismatch_reasons.csv  (+ printed tally per case)
"""
import os, json
import pandas as pd, numpy as np
from _paths import WORK, RESULTS, DATA

P = pd.read_parquet(f"{WORK}/claude_panel.parquet")
M = pd.read_csv(f"{RESULTS}/02_mismatch_months.csv", parse_dates=["month", "formation"])
idr = pd.read_csv(f"{DATA}/identity_resolutions.csv")
idr_t = set(idr["ticker"].str.replace(".", "-", regex=False))


def coverage(tk):
    out = []
    for sub in ("raw", "raw_tiingo", "raw_wiki", "raw_archive"):
        p = f"{DATA}/{sub}/{tk}.json"
        if os.path.exists(p):
            d = json.load(open(p)).get("dates") or []
            if d:
                out.append((sub, pd.Timestamp(d[0]), pd.Timestamp(d[-1])))
    return out


def has_open(tk, t):
    p = f"{DATA}/raw_open/{tk}.json"
    if not os.path.exists(p):
        return False
    d = json.load(open(p)).get("dates") or []
    return bool(d) and pd.Timestamp(d[0]) <= t <= pd.Timestamp(d[-1])


rows = []
for r in M.itertuples():
    t = r.formation
    g = set(str(r.gemini).split("|")) - {"CASH"}
    c = set(str(r.claude).split("|")) - {"CASH"}
    extra = sorted(g - c)
    if not extra:
        if g == c:
            fbm = P[(P.t == t) & P.ticker.isin(list(g))]["fb"].any()
            reason = ("same stocks; gross differs because the stock has NO raw open -> both engines fall back to a close "
                      "price (Gemini: next-session close; Claude: month-end close)" if fbm else
                      "same stocks; gross differs WITHOUT fallback -> UNEXPLAINED")
        else:
            reason = "Claude holds extra stock while Gemini holds CASH (gate outcome on different series)"
        rows.append(dict(case=r.case, month=r.month.date(), ticker="", reason=reason))
        continue
    for x in extra:
        cov = coverage(x)
        pt = P[(P.t == t) & (P.ticker == x)]
        if x in idr_t and pt.empty:
            reason = "documented ticker-reuse (identity_resolutions.csv): naive rebuild drops it; Gemini stitches clean archive/WIKI history"
        elif not cov:
            reason = "no file under this symbol: company later renamed (Gemini uses successor-ticker series)"
        elif pt.empty:
            if all(not (a <= t <= b) for _, a, b in cov):
                reason = "file exists but does not cover t (ticker re-used / data under different source)"
            else:
                first = next((s for s, a, b in cov if a <= t <= b), None)
                reason = f"covered only by {first}, not first-choice source in naive loader (ticker reuse in raw/)"
        elif not np.isfinite(pt["r121"].iloc[0]):
            reason = "naive 12-1 missing (history gap) while Gemini has continuous series"
        else:
            reason = "PRESENT in naive panel but ranked differently -> UNEXPLAINED"
        rows.append(dict(case=r.case, month=r.month.date(), ticker=x, reason=reason,
                         sources=";".join(f"{s}:{a.date()}..{b.date()}" for s, a, b in cov),
                         raw_open_covers_t=has_open(x, t)))
D = pd.DataFrame(rows)
D.to_csv(f"{RESULTS}/03_mismatch_reasons.csv", index=False)
for case, g in D.groupby("case"):
    print(f"[03] {case}: {g['month'].nunique()} mismatch months")
    for k, v in g["reason"].value_counts().items():
        print(f"       {v:4d}  {k}")
u = D[D.reason.str.contains("UNEXPLAINED")]
print(f"[03] UNEXPLAINED rows: {len(u)}")
if len(u):
    print(u.to_string(index=False))
