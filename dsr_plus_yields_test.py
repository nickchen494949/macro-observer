#!/usr/bin/env python3
"""
dsr_plus_yields_test.py — POST-HOC exploratory combos of debt service ratio + bond yields/spreads (2026-11-15).
Defined after seeing dsr_signal_test.py and break_signals_test.py results -> exploratory only, not evidence.
Combos fixed before running this file (all reported; OFF = defensive, evaluated at month-end t for month t+1):
  C1 HH_DSR_UP & 10Y yield higher than 12 months ago      C2 HH_DSR_UP & 2Y yield higher than 12 months ago
  C3 HH_DSR_UP & CREDIT widening (break_signals_test)     C4 BIS_DSR_UP & CREDIT widening
"""
import os, numpy as np, pandas as pd
ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "outputs", "dsr_signal_20261115")
src = open(os.path.join(ROOT, "dsr_signal_test.py")).read().split("# --- A. index-level timing")[0]
ns = {"__file__": os.path.join(ROOT, "dsr_signal_test.py")}
exec(src, ns)
T, fred, yahoo, bs = ns["T"], ns["fred"], ns["yahoo"], ns["bs"]
at = bs["at"]
g10, g2 = fred("DGS10"), fred("DGS2")
up = lambda s: pd.Series({t: (at(s, t) - at(s, t - pd.offsets.MonthEnd(12))) > 0 for t in T})
HHoff, BISoff, CRoff = ~ns["HH"], ~ns["BIS"], ~bs["sig"]["CREDIT"]
combos = {"HH_DSR_UP (alone)": ~HHoff, "C1 HH & 10Y up": ~(HHoff & up(g10)), "C2 HH & 2Y up": ~(HHoff & up(g2)),
          "C3 HH & credit widening": ~(HHoff & CRoff), "C4 BIS & credit widening": ~(BISoff & CRoff)}
ndx = yahoo("_IXIC").resample("ME").last(); r_ndx = ndx.pct_change()
cash = fred("DGS3MO").resample("ME").last() / 100 / 12
H = [t + pd.offsets.MonthEnd(1) for t in T]
CRASH = {"2000-02": ("2000-03", "2002-09"), "2007-09": ("2007-11", "2009-02"), "2020": ("2020-02", "2020-03"), "2022": ("2022-01", "2022-12")}
def cd(r):
    r = r.dropna(); w = (1 + r).cumprod(); return w.iloc[-1] ** (12 / len(r)) - 1, (w / w.cummax() - 1).min()
rows = []
for name, on in {"BUY&HOLD": pd.Series(True, index=T), **combos}.items():
    oh = pd.Series(on.values, index=H)
    r = pd.Series(np.where(oh.values, r_ndx.reindex(H).values, cash.reindex(T).values), index=H)
    row = {"signal": name, "OFF_m": int((~oh).sum())}
    for a, b, l in (("1985-01", "2026-10", "all"), ("1985-01", "2008-12", "85-08"), ("2009-01", "2026-10", "09-26")):
        row[f"CAGR_{l}"], row[f"MDD_{l}"] = cd(r.loc[a:b])
    for k, (a, b) in CRASH.items():
        row[f"OFF%_{k}"] = (~oh.loc[a:b]).mean()
    rows.append(row)
A = pd.DataFrame(rows)
pd.set_option("display.width", 250)
print(A.to_string(index=False, float_format=lambda v: f"{v:.0%}" if abs(v) >= 1 or v == 0 else f"{v:.1%}"))
v4src = open(os.path.join(ROOT, "v4_robust_upgrade_research.py")).read().split("# ---------------------------------------------------------------------------- 1. baselines")[0]
v = {"__file__": os.path.join(ROOT, "v4_robust_upgrade_research.py")}; exec(v4src, v)
brow = []
for name in ["none(SEP only)"] + list(combos):
    reg = v["SEP"] if name.startswith("none") else {t: bool(v["SEP"][t] and combos[name].get(t, True)) for t in v["MONTHS"]}
    L, _ = v["simulate"](v["sleeve_targets"]("sharpe", 2, 5, reg))
    c, s, d, _ = v["stats"](L.net, [v["YM"][t] for t in v["MONTHS"]])
    brow.append({"V4 + OFF trigger": name, "OFF_m": sum(not reg[t] for t in v["MONTHS"]), "CAGR": round(c, 3), "Sharpe": round(s, 3), "MDD": round(d, 3)})
B = pd.DataFrame(brow); print("\nInside V4 2009-2026:\n" + B.to_string(index=False))
A.to_csv(os.path.join(OUT, "posthoc_dsr_plus_yields_index.csv"), index=False); B.to_csv(os.path.join(OUT, "posthoc_dsr_plus_yields_v4.csv"), index=False)
