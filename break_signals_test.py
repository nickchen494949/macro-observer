#!/usr/bin/env python3
"""
break_signals_test.py — Do bond/rate "something is breaking" signals warn of 2000-02 / 2007-09 style busts? (2026-11-15)

PRE-REGISTERED (written before any output of this file was seen; textbook thresholds, no tuning)
-------------------------------------------------------------------------------------------------
Each signal is evaluated at month-end t with data public by then and applies to month t+1 (OFF = defensive).
  CURVE : monthly average of T10Y3M (10y minus 3m Treasury) < 0                       [inversion]
  CREDIT: monthly avg of (DBAA - DGS10) minus its minimum over the prior 12 monthly avgs > 0.50 pp   [credit widening]
  SAHM  : SAHMREALTIME (real-time Sahm rule) of month t-1 >= 0.50                     [jobs report lag]
  CUTS  : monthly avg DFF(t) - monthly avg DFF(t-3 months) <= -0.50 pp                [Fed cut >= 50bp in 3 months]
  ANY   : OFF if any of the four is OFF
  PROXY+ANY : OFF if the 2Y/core-PCE SEP proxy (sep_proxy_2y_test.py MAIN) is OFF or ANY is OFF
Evaluation A (index level, 1985-01..2026-10, price indices, cash = DGS3MO/12):
  timing portfolio = NASDAQ Composite when ON, cash when OFF; report CAGR, MaxDD, months OFF, share of each crash
  window spent OFF, and cost in non-crash years. Sub-periods 1985-2008 and 2009-2026 reported separately.
Evaluation B (V4, 2009-01..2026-10): add each signal as an extra OFF trigger to V4 (OFF leg unchanged =
  BestSec top-2 + 50% SGOV). Post-2009 contains no 2000/2008-type bust, so B mostly measures false-alarm cost.
Crash windows (for reporting only): 1987-08..1987-11, 1990-07..1990-10, 2000-03..2002-09, 2007-11..2009-02,
  2020-02..2020-03, 2022-01..2022-12.
Caveat: only 3-4 real busts since 1985 -> any result is weak evidence; 5 signals tested -> multiple-testing risk.
"""
import json
import os
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "outputs", "break_signals_20261115")
os.makedirs(OUT, exist_ok=True)
LOG = []


def say(*a):
    s = " ".join(str(x) for x in a)
    print(s)
    LOG.append(s)


def fred(name):
    v = json.load(open(os.path.join(ROOT, "data", "fred", f"{name}.json")))["values"]
    return pd.Series({pd.Timestamp(d): float(x) for d, x in v if x not in (None, ".")}).sort_index()


def yahoo(name):
    v = json.load(open(os.path.join(ROOT, "data", "yahoo", f"{name}.json")))
    v = v.get("values", v) if isinstance(v, dict) else v
    return pd.Series({pd.Timestamp(d): float(x) for d, x in v if x is not None}).sort_index()


T = pd.date_range("1984-12-31", "2026-10-31", freq="ME")
mavg = lambda s: s.resample("ME").mean()
curve = mavg(fred("T10Y3M"))
baa, g10 = fred("DBAA"), fred("DGS10")
cs = mavg((baa - g10.reindex(baa.index)).dropna())
sahm = fred("SAHMREALTIME")
sahm.index = sahm.index.to_period("M").to_timestamp("M")
dff = mavg(fred("DFF"))
say(f"Data starts: T10Y3M {curve.index[0].date()}, BAA-10Y {cs.index[0].date()}, SAHM {sahm.index[0].date()}, DFF {dff.index[0].date()}")


def at(s, t):
    x = s.loc[:t]
    return float(x.iloc[-1]) if len(x) and (t - x.index[-1]).days < 40 else np.nan


sig = {}
sig["CURVE"] = pd.Series({t: not (at(curve, t) < 0) for t in T})
sig["CREDIT"] = pd.Series({t: not ((at(cs, t) - cs.loc[:t - pd.offsets.MonthEnd(1)].tail(12).min()) > 0.50) for t in T})
sig["SAHM"] = pd.Series({t: not (at(sahm, t - pd.offsets.MonthEnd(1)) >= 0.50) for t in T})
sig["CUTS"] = pd.Series({t: not ((at(dff, t) - at(dff, t - pd.offsets.MonthEnd(3))) <= -0.50) for t in T})
sig["ANY"] = sig["CURVE"] & sig["CREDIT"] & sig["SAHM"] & sig["CUTS"]

# SEP proxy (same definition as sep_proxy_2y_test.py MAIN)
dgs2 = fred("DGS2")
pce = fred("PCEPILFE")
pyoy = (pce / pce.shift(12) - 1) * 100
state, px = True, {}
for t in T:
    chg = at(dgs2, t) - float(dgs2.loc[:t - pd.offsets.MonthEnd(3)].iloc[-1])
    m = (t - pd.offsets.MonthEnd(2)).to_period("M").to_timestamp()
    m3 = (t - pd.offsets.MonthEnd(5)).to_period("M").to_timestamp()
    hot = pyoy.get(m, np.nan) > 2.0 and pyoy.get(m, np.nan) > pyoy.get(m3, np.nan)
    if state and chg > 0.25 and hot:
        state = False
    elif (not state) and chg <= 0:
        state = True
    px[t] = state
sig["SEP_PROXY"] = pd.Series(px)
sig["PROXY+ANY"] = sig["SEP_PROXY"] & sig["ANY"]

# ----------------------------------------------------------------------------- A. index-level timing
ndx = yahoo("_IXIC").resample("ME").last()
r_ndx = ndx.pct_change()
cash = fred("DGS3MO").resample("ME").last() / 100 / 12
H = [t + pd.offsets.MonthEnd(1) for t in T]  # hold months
CRASH = {"1987": ("1987-08", "1987-11"), "1990": ("1990-07", "1990-10"), "2000-02": ("2000-03", "2002-09"),
         "2007-09": ("2007-11", "2009-02"), "2020": ("2020-02", "2020-03"), "2022": ("2022-01", "2022-12")}


def timing(on):
    on_h = pd.Series(on.values, index=H)
    r = np.where(on_h.values, r_ndx.reindex(H).values, cash.reindex(T).values)
    return pd.Series(r, index=H), on_h


def cagr_dd(r):
    r = r.dropna()
    w = (1 + r).cumprod()
    return w.iloc[-1] ** (12 / len(r)) - 1, (w / w.cummax() - 1).min()


rows = []
variants = {"BUY&HOLD": pd.Series(True, index=T), **sig}
for name, on in variants.items():
    r, on_h = timing(on)
    row = {"signal": name, "months_OFF": int((~on_h).sum())}
    for a, b, lab in (("1985-01", "2026-10", "all"), ("1985-01", "2008-12", "85-08"), ("2009-01", "2026-10", "09-26")):
        c, d = cagr_dd(r.loc[a:b])
        row[f"CAGR_{lab}"] = c
        row[f"MDD_{lab}"] = d
    for k, (a, b) in CRASH.items():
        h = on_h.loc[a:b]
        row[f"OFF%_{k}"] = (~h).mean()
    rows.append(row)
A = pd.DataFrame(rows)
A.to_csv(os.path.join(OUT, "A_index_timing_1985_2026.csv"), index=False)
pd.set_option("display.width", 260)
say("\n=== A. NASDAQ when ON / T-bills when OFF (price index, 1985-2026) ===")
say(A[["signal", "months_OFF", "CAGR_all", "MDD_all", "CAGR_85-08", "MDD_85-08", "CAGR_09-26", "MDD_09-26"]]
    .to_string(index=False, float_format=lambda v: f"{v:.1%}"))
say("\nShare of each crash window spent OFF:")
say(A[["signal"] + [f"OFF%_{k}" for k in CRASH]].to_string(index=False, float_format=lambda v: f"{v:.0%}"))

# signal timelines around the two big busts
say("\nSignal state by hold month (X = OFF):")
for a, b in (("1999-06", "2003-03"), ("2006-01", "2009-06")):
    rng = [h for h in H if pd.Timestamp(a) <= h <= pd.Timestamp(b) + pd.offsets.MonthEnd(0)]
    say(f"  {a}..{b}")
    for name in ("CURVE", "CREDIT", "SAHM", "CUTS", "SEP_PROXY"):
        on_h = pd.Series(sig[name].values, index=H)
        say(f"    {name:9s} " + "".join("X" if not on_h[h] else "." for h in rng))
    say("    NASDAQ    " + "".join("v" if r_ndx.get(h, 0) < -0.05 else ("^" if r_ndx.get(h, 0) > 0.05 else "-") for h in rng)
        + "   (v = month < -5%, ^ = > +5%)")

# false alarms: OFF episodes outside crash windows and what NASDAQ did
say("\nOFF months outside crash windows: NASDAQ avg return in those months (annualized) — the cost of false alarms")
crash_months = set()
for a, b in CRASH.values():
    crash_months |= set(pd.date_range(a, pd.Timestamp(b) + pd.offsets.MonthEnd(0), freq="ME"))
for name in ("CURVE", "CREDIT", "SAHM", "CUTS", "ANY", "SEP_PROXY", "PROXY+ANY"):
    on_h = pd.Series(sig[name].values, index=H)
    fa = [h for h in H if (not on_h[h]) and h not in crash_months and h in r_ndx.index]
    say(f"  {name:9s}: {len(fa):3d} months, NASDAQ {np.nanmean([r_ndx[h] for h in fa]) * 12:+.1%}/yr in them; "
        f"years: {sorted(set(h.year for h in fa))}")

# ----------------------------------------------------------------------------- B. inside V4 (2009-2026)
say("\n=== B. Add each signal as an extra OFF trigger to V4 (2009-01..2026-10) ===")
src = open(os.path.join(ROOT, "v4_robust_upgrade_research.py")).read().split("# ---------------------------------------------------------------------------- 1. baselines")[0]
ns = {"__file__": os.path.join(ROOT, "v4_robust_upgrade_research.py")}
exec(src, ns)
MONTHS, RF = ns["MONTHS"], ns["RF"]
b_rows = []
for name in ("none(SEP only)", "CURVE", "CREDIT", "SAHM", "CUTS", "ANY"):
    if name.startswith("none"):
        reg = ns["SEP"]
    else:
        on = sig[name]
        reg = {t: bool(ns["SEP"][t] and on.get(t, True)) for t in MONTHS}
    L, _ = ns["simulate"](ns["sleeve_targets"]("sharpe", 2, 5, reg))
    c, s, d, _ = ns["stats"](L.net, [ns["YM"][t] for t in MONTHS])
    b_rows.append({"V4 + extra OFF trigger": name, "OFF_months": sum(not reg[t] for t in MONTHS), "CAGR": c, "Sharpe": s, "MonthlyMDD": d})
B = pd.DataFrame(b_rows)
B.to_csv(os.path.join(OUT, "B_v4_with_break_signals_2009_2026.csv"), index=False)
say(B.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
with open(os.path.join(OUT, "log.txt"), "w") as f:
    f.write("\n".join(LOG))
