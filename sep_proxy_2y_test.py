#!/usr/bin/env python3
"""
sep_proxy_2y_test.py — Can a long-history market proxy reproduce the FOMC SEP switch? (2026-11-15)

PRE-REGISTERED (written before any output of this file was seen)
----------------------------------------------------------------
Signal evaluated at each month-end t (applies to the next month, like the SEP switch).
  rate_up   : DGS2(last <= t) - DGS2(last <= t - 3 months) > +0.25 pp     (market reprices >= 1 extra hike)
  rate_flat : same 3-month change <= 0                                    (expected path stopped rising)
  infl      : core PCE YoY of month (t - 2 months)  [2-month publication-lag buffer; latest vintage, see caveat]
  infl_hot  : infl > 2.0 and infl > core PCE YoY three months earlier
  State machine (starts ON): ON -> OFF if rate_up and infl_hot ; OFF -> ON if rate_flat.
Sensitivities (reported, never used to pick): S1 rate-only (drop infl_hot); S2 threshold 0bp; S3 6-month window;
  S4 core CPI instead of core PCE.
PASS criterion for using the proxy before 2012 (main proxy only):
  monthly agreement with the real SEP switch >= 85% over hold months 2015-12..2026-10, AND
  proxy OFF in >= 9 of the 12 hold months of 2022.
Caveat: PCE/CPI use today's vintage (revisions are usually small); DGS2 is never revised.
Descriptive history 1985-2026 uses ^GSPC / ^IXIC price indices (no dividends) — not a strategy backtest.
"""
import json
import os
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "outputs", "sep_proxy_2y_20261115")
os.makedirs(OUT, exist_ok=True)
LOG = []


def say(*a):
    s = " ".join(str(x) for x in a)
    print(s)
    LOG.append(s)


def fred(name):
    v = json.load(open(os.path.join(ROOT, "data", "fred", f"{name}.json")))["values"]
    s = pd.Series({pd.Timestamp(d): float(x) for d, x in v if x not in (None, ".")}).sort_index()
    return s


def yahoo(name):
    v = json.load(open(os.path.join(ROOT, "data", "yahoo", f"{name}.json")))
    v = v.get("values", v) if isinstance(v, dict) else v
    return pd.Series({pd.Timestamp(d): float(x) for d, x in v if x is not None}).sort_index()


dgs2 = fred("DGS2")
pce = fred("PCEPILFE")
cpi = fred("CPILFESL")
pce_yoy = (pce / pce.shift(12) - 1) * 100
cpi_yoy = (cpi / cpi.shift(12) - 1) * 100
REG = pd.read_csv(os.path.join(ROOT, "outputs", "pure_momentum_1985_2026_audit", "inputs", "v3_regime_and_cash_214m.csv"))
REG["t"] = pd.to_datetime(REG["t"])
SEP = dict(zip(REG["t"], REG["sep_on"].astype(bool)))

T = pd.date_range("1984-12-31", "2026-10-31", freq="ME")


def last_le(s, dt):
    x = s.loc[:dt]
    return float(x.iloc[-1]) if len(x) else np.nan


def proxy(thr=0.25, window=3, use_infl=True, infl_series=pce_yoy):
    state, out = True, {}
    for t in T:
        d_now = last_le(dgs2, t)
        d_then = last_le(dgs2, t - pd.offsets.MonthEnd(window))
        chg = d_now - d_then
        m = (t - pd.offsets.MonthEnd(2)).to_period("M").to_timestamp()
        m3 = (t - pd.offsets.MonthEnd(5)).to_period("M").to_timestamp()
        i_now = infl_series.get(m, np.nan)
        i_then = infl_series.get(m3, np.nan)
        hot = (i_now > 2.0) and (i_now > i_then) if use_infl else True
        if state and chg > thr and hot:
            state = False
        elif (not state) and chg <= 0:
            state = True
        out[t] = state
    return pd.Series(out)


VARIANTS = {
    "MAIN (3m>+25bp, corePCE>2 & rising)": proxy(),
    "S1 rate-only": proxy(use_infl=False),
    "S2 threshold 0bp": proxy(thr=0.0),
    "S3 6-month window": proxy(window=6),
    "S4 core CPI": proxy(infl_series=cpi_yoy),
}

# ---------------------------------------------------------------- agreement with real SEP switch
say("=== Agreement with real SEP switch, hold months 2015-12..2026-10 (formation 2015-11-30..2026-09-30) ===")
win = [t for t in T if pd.Timestamp("2015-11-30") <= t <= pd.Timestamp("2026-09-30")]
sep = pd.Series({t: SEP[t] for t in win})
rows = []
for name, p in VARIANTS.items():
    pw = p.loc[win]
    agree = (pw == sep).mean()
    off_sep = ~sep
    recall = ((~pw) & off_sep).sum() / off_sep.sum()
    prec = ((~pw) & off_sep).sum() / max((~pw).sum(), 1)
    m22 = [t for t in win if (t + pd.offsets.MonthBegin(1)).year == 2022]
    off22 = int((~pw.loc[m22]).sum())
    passed = (agree >= 0.85) and (off22 >= 9)
    rows.append({"variant": name, "agreement": agree, "SEP_OFF_caught": recall, "proxy_OFF_correct": prec,
                 "proxy_OFF_months": int((~pw).sum()), "SEP_OFF_months": int(off_sep.sum()), "OFF_in_2022(of12)": off22,
                 "PASS(main only)": passed if name.startswith("MAIN") else "-"})
AG = pd.DataFrame(rows)
say(AG.to_string(index=False, float_format=lambda v: f"{v:.2f}"))
AG.to_csv(os.path.join(OUT, "agreement_2015_2026.csv"), index=False)

cmp_ = pd.DataFrame({"hold_month": [(t + pd.offsets.MonthBegin(1)).strftime("%Y-%m") for t in win],
                     "SEP": ["ON" if sep[t] else "OFF" for t in win],
                     "proxy": ["ON" if VARIANTS["MAIN (3m>+25bp, corePCE>2 & rising)"][t] else "OFF" for t in win]})
dis = cmp_[cmp_.SEP != cmp_.proxy]
say(f"\nMAIN disagreement months ({len(dis)}):\n" + dis.to_string(index=False))
cmp_.to_csv(os.path.join(OUT, "monthly_sep_vs_proxy.csv"), index=False)

# ---------------------------------------------------------------- descriptive history 1985-2026
say("\n=== MAIN proxy OFF episodes 1985-2026 (descriptive; price indices) ===")
spx = yahoo("_GSPC").resample("ME").last()
ndx = yahoo("_IXIC").resample("ME").last()
p = VARIANTS["MAIN (3m>+25bp, corePCE>2 & rising)"]
hold = pd.Series(p.values, index=[t + pd.offsets.MonthEnd(1) for t in p.index])  # state applied to next month
eps = []
cur = None
for t, on in hold.items():
    if not on and cur is None:
        cur = t
    if on and cur is not None:
        eps.append((cur, t - pd.offsets.MonthEnd(1)))
        cur = None
if cur is not None:
    eps.append((cur, hold.index[-1]))


def ret(s, a, b):
    try:
        return s.loc[b] / s.loc[a - pd.offsets.MonthEnd(1)] - 1
    except KeyError:
        return np.nan


ep_rows = []
for a, b in eps:
    nxt = b + pd.offsets.MonthEnd(12)
    ep_rows.append({"OFF_from": a.strftime("%Y-%m"), "OFF_to": b.strftime("%Y-%m"), "months": (b.to_period("M") - a.to_period("M")).n + 1,
                    "SPX_during_OFF": ret(spx, a, b), "NASDAQ_during_OFF": ret(ndx, a, b),
                    "SPX_12m_after_reentry": ret(spx, b + pd.offsets.MonthEnd(1), min(nxt, spx.index[-1])),
                    "NASDAQ_12m_after_reentry": ret(ndx, b + pd.offsets.MonthEnd(1), min(nxt, ndx.index[-1]))})
EP = pd.DataFrame(ep_rows)
say(EP.to_string(index=False, float_format=lambda v: f"{v:+.1%}"))
EP.to_csv(os.path.join(OUT, "main_proxy_off_episodes_1985_2026.csv"), index=False)

say("\n=== Where was the MAIN proxy during the big busts? (state for each hold month) ===")
for a, b, lab in (("2000-03", "2002-10", "Dot-com bust"), ("2007-10", "2009-03", "GFC"), ("1987-08", "1987-12", "1987 crash"),
                  ("1990-07", "1990-10", "1990 bear"), ("2022-01", "2022-12", "2022 bear")):
    h = hold.loc[a:b]
    say(f"{lab:13s} {a}..{b}: OFF {int((~h).sum())}/{len(h)} months; "
        f"SPX {ret(spx, pd.Timestamp(a) + pd.offsets.MonthEnd(0), pd.Timestamp(b) + pd.offsets.MonthEnd(0)):+.1%}, "
        f"NASDAQ {ret(ndx, pd.Timestamp(a) + pd.offsets.MonthEnd(0), pd.Timestamp(b) + pd.offsets.MonthEnd(0)):+.1%}")

# monthly returns by state (1985-2026, and 1985-2014 = pre-SEP-data period)
m_spx = spx.pct_change()
m_ndx = ndx.pct_change()
df = pd.DataFrame({"on": hold, "spx": m_spx.reindex(hold.index), "ndx": m_ndx.reindex(hold.index)}).dropna()
for a, b in (("1985-01", "2026-10"), ("1985-01", "2015-11"), ("2015-12", "2026-10")):
    d = df.loc[a:b]
    say(f"{a}..{b}: ON {int(d.on.sum())}m  NASDAQ avg {d[d.on].ndx.mean() * 12:+.1%}/yr, SPX {d[d.on].spx.mean() * 12:+.1%}/yr | "
        f"OFF {int((~d.on).sum())}m  NASDAQ avg {d[~d.on].ndx.mean() * 12:+.1%}/yr, SPX {d[~d.on].spx.mean() * 12:+.1%}/yr")

with open(os.path.join(OUT, "log.txt"), "w") as f:
    f.write("\n".join(LOG))
