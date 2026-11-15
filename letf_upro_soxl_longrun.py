#!/usr/bin/env python3
"""
letf_upro_soxl_longrun.py — UPRO-like (3x S&P 500) and SOXL-like (3x semiconductors) long-run tests (2026-11-15)

PRE-SPECIFIED before running; same engine as improvements_research.py PART 1:
  Leveraged daily return = 3r - 2(rf+0.5%)/252 - 0.95%/252, monthly decisions at month-end, cash = DGS3MO.
  Underlyings: S&P 500 = ^GSPC daily price + dividend yield/252 (1985-2026); Semis = SMH daily adjClose (Tiingo,
  2000-06-05 onward; starts ~3 months after the March-2000 SOX peak, so the dot-com semis crash is slightly
  understated). ^SOX daily history is not available locally (Yahoo 'max' returns monthly only; one fetch saved as
  SOX_yahoo_max.json for reference) -> no semis test before 2000-06.
  Variants per underlying: 1x buy&hold | 3x buy&hold | 3x + SEP | 3x + SEP + vol-managed
  (w = min(1, expanding median var21 / var21_t) of the underlying) | (Nasdaq 3x + SEP + VM from earlier, for reference).
  Validation: synthetic vs actual UPRO / SOXL monthly returns in the overlap.
"""
import json
import os
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "outputs", "improvements_research_20261115")
src = open(os.path.join(ROOT, "improvements_research.py")).read().split("rf_m = (1 + cash_d)")[0]
ns = {"__file__": os.path.join(ROOT, "improvements_research.py")}
exec(src, ns)
yahoo, rf_all, sep_on, perf, fred = ns["yahoo"], ns["rf_d"], ns["sep_on"], ns["perf"], ns["fred"]
rf_full = (fred("DGS3MO") / 100)


def etf(sym):
    d = pd.DataFrame(json.load(open(os.path.join(ROOT, "outputs", "remediation_full_audit_20261104", "tiingo_etfs", f"{sym}.json"))))
    d["date"] = pd.to_datetime(d["date"].str[:10])
    return d.set_index("date")["adjClose"].astype(float).sort_index()


gspc = yahoo("_GSPC")
dy = json.load(open(os.path.join(ROOT, "data", "valuation", "SP500_DIV_YIELD.json")))
dy = pd.Series({pd.Timestamp(d): float(x) for d, x in (dy.get("values", dy) if isinstance(dy, dict) else dy)}).sort_index()
spx_r = gspc.pct_change().dropna()
spx_r = spx_r[spx_r.index >= "1983-01-01"]
spx_r = spx_r + dy.reindex(spx_r.index, method="ffill") / 100 / 252
smh_r = etf("SMH").pct_change().dropna()
UNDER = {"S&P 500 (UPRO-like)": spx_r, "Semis SMH (SOXL-like)": smh_r, "Nasdaq Comp (TQQQ-like)": ns["r_d"]}


def run(r_d, L, use_sep, vm):
    rf_d = rf_full.reindex(r_d.index).ffill()
    lev = L * r_d - (L - 1) * (rf_d + 0.005) / 252 - (0.0095 / 252 if L > 1 else 0)
    cash = rf_d / 252
    var21 = r_d.rolling(21).var()
    medv = var21.expanding(min_periods=252).median()
    out = {}
    me = r_d.index.to_series().groupby(r_d.index.to_period("M")).max()
    for t in me.values[:-1]:
        t = pd.Timestamp(t)
        tm = t + pd.offsets.MonthEnd(0)
        nxt = tm + pd.offsets.MonthEnd(1)
        days = r_d.loc[(r_d.index > t) & (r_d.index <= nxt)].index
        if not len(days) or tm > pd.Timestamp("2026-09-30"):
            continue
        on = sep_on.get(tm, True) if use_sep else True
        w = 1.0 if on else 0.0
        if vm and on and np.isfinite(medv.loc[:t].iloc[-1]):
            w = min(1.0, medv.loc[:t].iloc[-1] / var21.loc[:t].iloc[-1])
        out[nxt] = w * ((1 + lev.loc[days]).prod() - 1) + (1 - w) * ((1 + cash.loc[days]).prod() - 1)
    return pd.Series(out)


rows = []
for uname, r in UNDER.items():
    for vname, (L, s, vm) in {"1x buy&hold": (1, False, False), "3x buy&hold": (3, False, False), "3x + SEP": (3, True, False),
                              "3x + SEP + vol-managed": (3, True, True)}.items():
        m = run(r, L, s, vm)
        row = {"underlying": uname, "variant": vname, "start": m.index[0].strftime("%Y-%m")}
        for a, b, lab in (("1985-01", "2026-10", "full"), ("1985-01", "2008-12", "to08"), ("2009-01", "2026-10", "09-26"),
                          ("2000-06", "2002-12", "00-02"), ("2007-01", "2009-12", "07-09")):
            c, sh, d = perf(m.loc[a:b])
            row[f"CAGR_{lab}"], row[f"MDD_{lab}"] = c, d
            if lab == "full":
                row["Sharpe_full"] = sh
        rows.append(row)
D = pd.DataFrame(rows)
D.to_csv(os.path.join(OUT, "upro_soxl_tqqq_longrun.csv"), index=False)
pd.set_option("display.width", 260)
print(D.to_string(index=False, float_format=lambda v: f"{v:.2f}" if abs(v) > 5 else f"{v:.1%}"))
for uname, sym in (("S&P 500 (UPRO-like)", "UPRO"), ("Semis SMH (SOXL-like)", "SOXL")):
    act = etf(sym).resample("ME").last().pct_change().dropna()
    syn = run(UNDER[uname], 3, False, False).reindex(act.index).dropna()
    a = act.reindex(syn.index)
    print(f"Validation {sym}: corr={syn.corr(a):.3f}, CAGR synthetic {perf(syn)[0]:.1%} vs actual {perf(a)[0]:.1%} ({syn.index[0]:%Y-%m}..{syn.index[-1]:%Y-%m})")
