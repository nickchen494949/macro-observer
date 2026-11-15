#!/usr/bin/env python3
"""
dsr_signal_test.py — Debt service ratio as a warning signal for 2000/2008-type busts (2026-11-15)

PRE-REGISTERED before computing results in this file. Disclosure: before writing this I had already seen
(a) the raw BIS DSR levels and (b) an earlier project table (tqqq_expC) showing QQQ returns were lower when the BIS
private DSR was rising YoY. Rules below use that same textbook "rising YoY" form; no thresholds are tuned.

Signals (evaluated at month-end t, applied to month t+1; OFF = defensive):
  HH_DSR_UP : household debt service ratio (FRED TDSP), REAL-TIME vintage as of t (ALFRED; vintages from 1999-11-09;
              for t before the first vintage, the first vintage is used -> mild look-ahead, flagged). Take the latest
              quarter available in that vintage; OFF if DSR(q) - DSR(q-4) > 0 (same vintage for both points).
  BIS_DSR_UP: BIS private non-financial DSR (current vintage, 1999+), latest quarter ending >= 6 months before t;
              OFF if YoY change > 0.  (No BIS vintages available -> revision look-ahead possible.)
Evaluation identical to break_signals_test.py: A) NASDAQ-or-T-bills timing 1985-2026 (+ crash-window coverage,
false-alarm cost); B) extra OFF trigger inside V4 2009-01..2026-10.
Sources saved in outputs/dsr_signal_20261115/: TDSP_all_vintages_long.json (FRED/ALFRED API, output_type=1),
TDSP_first_release.json, TDSP_fred_full.json, TDSP_vintagedates.json; BIS from data/valuation/BIS_DSR_US.json.
"""
import json
import os
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "outputs", "dsr_signal_20261115")
LOG = []


def say(*a):
    s = " ".join(str(x) for x in a)
    print(s)
    LOG.append(s)


# reuse loaders, calendar and crash windows from break_signals_test.py (top section only)
bs_src = open(os.path.join(ROOT, "break_signals_test.py")).read().split("# ----------------------------------------------------------------------------- A. index-level timing")[0]
bs = {"__file__": os.path.join(ROOT, "break_signals_test.py")}
exec(bs_src, bs)
T, fred, yahoo = bs["T"], bs["fred"], bs["yahoo"]

# --- real-time household DSR
lv = pd.DataFrame(json.load(open(os.path.join(OUT, "TDSP_all_vintages_long.json")))["observations"])
lv = lv[lv.value != "."].copy()
lv["value"] = lv.value.astype(float)
lv["date"] = pd.to_datetime(lv.date)
lv["rs"] = pd.to_datetime(lv.realtime_start)
lv["re"] = pd.to_datetime(lv.realtime_end.replace("9999-12-31", "2262-01-01"))
first_v = lv.rs.min()
hh, hh_val = {}, {}
for t in T:
    asof = max(t, first_v)
    v = lv[(lv.rs <= asof) & (lv.re >= asof)].set_index("date").value.sort_index()
    q = v.index[-1]
    q4 = q - pd.DateOffset(years=1)
    chg = v.iloc[-1] - v.get(q4, np.nan)
    hh[t] = not (chg > 0)
    hh_val[t] = (q.strftime("%Y-%m"), round(v.iloc[-1], 2), round(chg, 2))
HH = pd.Series(hh)

# --- BIS private non-financial DSR (current vintage)
bis = json.load(open(os.path.join(ROOT, "data", "valuation", "BIS_DSR_US.json")))["data"]["Private_Nonfinancial"]
bis = pd.Series({pd.Period(q.replace("-", ""), "Q").end_time.normalize(): float(x) for q, x in bis})
bis_on = {}
for t in T:
    avail = bis.loc[:t - pd.DateOffset(months=6)]
    if len(avail) < 5:
        bis_on[t] = True  # no data before 2000 -> treated as ON (no signal)
        continue
    bis_on[t] = not (avail.iloc[-1] - avail.iloc[-5] > 0)
BIS = pd.Series(bis_on)

sigs = {"HH_DSR_UP": HH, "BIS_DSR_UP": BIS, "SEP_PROXY": bs["sig"]["SEP_PROXY"]}
sigs["SEP_PROXY+HH"] = sigs["SEP_PROXY"] & HH

# --- A. index-level timing
ndx = yahoo("_IXIC").resample("ME").last()
r_ndx = ndx.pct_change()
cash = fred("DGS3MO").resample("ME").last() / 100 / 12
H = [t + pd.offsets.MonthEnd(1) for t in T]
CRASH = {"1987": ("1987-08", "1987-11"), "1990": ("1990-07", "1990-10"), "2000-02": ("2000-03", "2002-09"),
         "2007-09": ("2007-11", "2009-02"), "2020": ("2020-02", "2020-03"), "2022": ("2022-01", "2022-12")}
crash_months = set()
for a, b in CRASH.values():
    crash_months |= set(pd.date_range(a, pd.Timestamp(b) + pd.offsets.MonthEnd(0), freq="ME"))


def cagr_dd(r):
    r = r.dropna()
    w = (1 + r).cumprod()
    return w.iloc[-1] ** (12 / len(r)) - 1, (w / w.cummax() - 1).min()


rows = []
for name, on in {"BUY&HOLD": pd.Series(True, index=T), **sigs}.items():
    on_h = pd.Series(on.values, index=H)
    r = pd.Series(np.where(on_h.values, r_ndx.reindex(H).values, cash.reindex(T).values), index=H)
    row = {"signal": name, "months_OFF": int((~on_h).sum())}
    for a, b, lab in (("1985-01", "2026-10", "all"), ("1985-01", "2008-12", "85-08"), ("2009-01", "2026-10", "09-26")):
        c, d = cagr_dd(r.loc[a:b])
        row[f"CAGR_{lab}"], row[f"MDD_{lab}"] = c, d
    for k, (a, b) in CRASH.items():
        row[f"OFF%_{k}"] = (~on_h.loc[a:b]).mean()
    fa = [h for h in H if (not on_h[h]) and h not in crash_months and h in r_ndx.index]
    row["false_alarm_months"] = len(fa)
    row["NASDAQ_ann_in_false_alarms"] = np.nanmean([r_ndx[h] for h in fa]) * 12 if fa else np.nan
    rows.append(row)
A = pd.DataFrame(rows)
A.to_csv(os.path.join(OUT, "A_index_timing_1985_2026.csv"), index=False)
pd.set_option("display.width", 260)
say("=== A. NASDAQ when ON / T-bills when OFF (price index) ===")
say(A[["signal", "months_OFF", "CAGR_all", "MDD_all", "CAGR_85-08", "MDD_85-08", "CAGR_09-26", "MDD_09-26",
       "false_alarm_months", "NASDAQ_ann_in_false_alarms"]].to_string(index=False, float_format=lambda v: f"{v:.1%}"))
say("\nShare of each crash window spent OFF:")
say(A[["signal"] + [f"OFF%_{k}" for k in CRASH]].to_string(index=False, float_format=lambda v: f"{v:.0%}"))

say("\nState by hold month (X = OFF):")
for a, b in (("1998-01", "2003-06"), ("2004-01", "2009-06"), ("2019-01", "2026-10")):
    rng = [h for h in H if pd.Timestamp(a) <= h <= pd.Timestamp(b) + pd.offsets.MonthEnd(0)]
    say(f"  {a}..{b}")
    for name in ("HH_DSR_UP", "BIS_DSR_UP", "SEP_PROXY"):
        on_h = pd.Series(sigs[name].values, index=H)
        say(f"    {name:10s} " + "".join("X" if not on_h[h] else "." for h in rng))
    say("    NASDAQ     " + "".join("v" if r_ndx.get(h, 0) < -0.05 else ("^" if r_ndx.get(h, 0) > 0.05 else "-") for h in rng))
say("\nLatest real-time household DSR reading (quarter, level, YoY change): " + str(hh_val[T[-1]]))

# --- B. inside V4
say("\n=== B. Extra OFF trigger inside V4 (2009-01..2026-10) ===")
src = open(os.path.join(ROOT, "v4_robust_upgrade_research.py")).read().split("# ---------------------------------------------------------------------------- 1. baselines")[0]
ns = {"__file__": os.path.join(ROOT, "v4_robust_upgrade_research.py")}
exec(src, ns)
MONTHS = ns["MONTHS"]
b_rows = []
for name in ("none(SEP only)", "HH_DSR_UP", "BIS_DSR_UP"):
    reg = ns["SEP"] if name.startswith("none") else {t: bool(ns["SEP"][t] and sigs[name].get(t, True)) for t in MONTHS}
    L, _ = ns["simulate"](ns["sleeve_targets"]("sharpe", 2, 5, reg))
    c, s, d, _ = ns["stats"](L.net, [ns["YM"][t] for t in MONTHS])
    b_rows.append({"V4 + extra OFF trigger": name, "OFF_months": sum(not reg[t] for t in MONTHS), "CAGR": c, "Sharpe": s, "MonthlyMDD": d})
B = pd.DataFrame(b_rows)
B.to_csv(os.path.join(OUT, "B_v4_with_dsr_2009_2026.csv"), index=False)
say(B.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
with open(os.path.join(OUT, "log.txt"), "w") as f:
    f.write("\n".join(LOG))
