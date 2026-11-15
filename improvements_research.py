#!/usr/bin/env python3
"""
improvements_research.py — Literature-motivated improvement tests for TQQQ+SEP and V4 (2026-11-15)

PRE-REGISTERED (written before any output of this file was seen). Ideas come from published research, not from
mining our data: Moreira & Muir (2017) volatility-managed portfolios; Barroso & Santa-Clara (2015) risk-managed
momentum; Daniel & Moskowitz (2016) momentum crashes / panic states; leveraged-ETF optimal-leverage math
(g = L*mu - 0.5*L^2*sigma^2). Caveat from Cederburg et al. (2020): vol management often fails out of sample, so the
pre-2009 window is the real test where available.

PART 1 — TQQQ+SEP on a synthetic daily-reset leveraged Nasdaq, 1985-2026
  Underlying: ^IXIC Nasdaq Composite daily (price index; NDX is not available before ETF data -> lower vol than NDX,
  no dividends). Leveraged daily return = L*r - (L-1)*(rf+0.50%)/252 - 0.95%/252. Cash = DGS3MO.
  Regime: 2Y-yield + core-PCE SEP proxy (sep_proxy_2y_test.py MAIN) for formation months before 2015-11-30, the real
  ALFRED SEP switch afterwards. Decision at month-end t applies to month t+1 (month-end close to close).
  Variants: T0 3x buy&hold | T1 3x + SEP | T2 T1 + vol-managed: exposure w = min(1, median(var21 to date)/var21_t)
  | T3 T1 + panic state: OFF if Nasdaq 24m return < 0 and vol21 > expanding median | T4 = T1 with 2x | T5 = T2 with 2x.
  Reported for 1985-2008 (out-of-sample for the SEP idea and overlays), 2009-2026, full. Validation: correlation of
  synthetic 3x vs actual TQQQ monthly returns 2010-2026.
PART 2 — V4 (QQQ top-2 Sharpe, hold<=5, SEP, BestSec+50% SGOV, no ER), 2009-2026 only (no pre-2009 NDX data)
  V-RM (Barroso-Santa-Clara): stock exposure scaled by w = min(1, median(sigma126 to date)/sigma126_t), sigma126 =
       realized vol of the strategy's own daily NAV over the prior 126 trading days (audit daily NAV; that NAV
       includes the 3 Election-Reset Decembers -> negligible difference); unscaled until 252 days of history.
  V-DM (Daniel-Moskowitz panic): if QQQ 24m return < 0 and qqq_vol21 > expanding median -> stock exposure halved.
  Residual weight -> SGOV. Costs 10bp/side netted.
"""
import json
import os
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "outputs", "improvements_research_20261115")
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


def perf(r, rf=None):
    r = pd.Series(r).dropna()
    w = (1 + r).cumprod()
    cagr = w.iloc[-1] ** (12 / len(r)) - 1
    ex = r - (rf.reindex(r.index).fillna(0) if rf is not None else 0)
    sh = ex.mean() / r.std(ddof=1) * np.sqrt(12)
    mdd = (w / w.cummax() - 1).min()
    return cagr, sh, mdd


# ============================================================================ PART 1: synthetic leveraged Nasdaq
ixic = yahoo("_IXIC")
ixic = ixic[ixic.index >= "1983-01-01"]
r_d = ixic.pct_change().dropna()
rf_d = (fred("DGS3MO") / 100).reindex(r_d.index).ffill()
lev = {L: L * r_d - (L - 1) * (rf_d + 0.005) / 252 - 0.0095 / 252 for L in (2, 3)}
cash_d = rf_d / 252
var21 = r_d.rolling(21).var()
med_var = var21.expanding(min_periods=252).median()
vol21 = np.sqrt(var21 * 252)
med_vol = vol21.expanding(min_periods=252).median()
me = ixic.resample("ME").last()
ret24 = me / me.shift(24) - 1

# regime: SEP proxy (pre-2015-11-30) + real SEP afterwards
pxsrc = open(os.path.join(ROOT, "break_signals_test.py")).read().split("# ----------------------------------------------------------------------------- A. index-level timing")[0]
bns = {"__file__": os.path.join(ROOT, "break_signals_test.py")}
exec(pxsrc, bns)
proxy = bns["sig"]["SEP_PROXY"]
REG = pd.read_csv(os.path.join(ROOT, "outputs", "pure_momentum_1985_2026_audit", "inputs", "v3_regime_and_cash_214m.csv"))
REG["t"] = pd.to_datetime(REG["t"])
real_sep = dict(zip(REG["t"], REG["sep_on"].astype(bool)))
T = [t for t in proxy.index if t <= pd.Timestamp("2026-09-30")]
sep_on = {t: (real_sep[t] if t >= pd.Timestamp("2015-11-30") else bool(proxy[t])) for t in T}


def monthly_sim(L, use_sep, vm=False, panic=False):
    out = {}
    for t in T:
        nxt = t + pd.offsets.MonthEnd(1)
        days = r_d.loc[(r_d.index > t) & (r_d.index <= nxt)].index
        if not len(days):
            continue
        on = sep_on[t] if use_sep else True
        if panic and (ret24.get(t, 0) < 0) and (vol21.loc[:t].iloc[-1] > med_vol.loc[:t].iloc[-1]):
            on = False
        w = 1.0
        if vm and on:
            mv, v = med_var.loc[:t].iloc[-1], var21.loc[:t].iloc[-1]
            w = min(1.0, mv / v) if np.isfinite(mv) else 1.0
        if not on:
            w = 0.0
        # daily rebalance to w within the month is NOT assumed; buy-and-hold w of the LETF for the month
        lv = (1 + lev[L].loc[days]).prod() - 1
        cs = (1 + cash_d.loc[days]).prod() - 1
        out[nxt] = w * lv + (1 - w) * cs
    return pd.Series(out)


rf_m = (1 + cash_d).resample("ME").prod() - 1
V1 = {"T0 3x buy&hold": monthly_sim(3, False), "T1 3x + SEP": monthly_sim(3, True),
      "T2 3x + SEP + vol-managed": monthly_sim(3, True, vm=True), "T3 3x + SEP + panic-off": monthly_sim(3, True, panic=True),
      "T4 2x + SEP": monthly_sim(2, True), "T5 2x + SEP + vol-managed": monthly_sim(2, True, vm=True),
      "Nasdaq 1x buy&hold": None}
nas1 = ((1 + r_d).resample("ME").prod() - 1).loc[V1["T0 3x buy&hold"].index]
V1["Nasdaq 1x buy&hold"] = nas1
rows = []
for name, r in V1.items():
    row = {"variant": name}
    for a, b, lab in (("1985-01", "2026-10", "all"), ("1985-01", "2008-12", "85-08"), ("2009-01", "2026-10", "09-26"),
                      ("2000-01", "2002-12", "00-02"), ("2007-01", "2009-12", "07-09")):
        c, s, d = perf(r.loc[a:b], rf_m)
        row[f"CAGR_{lab}"], row[f"Sh_{lab}"], row[f"MDD_{lab}"] = c, s, d
    rows.append(row)
P1 = pd.DataFrame(rows)
P1.to_csv(os.path.join(OUT, "part1_synthetic_leveraged_nasdaq.csv"), index=False)
pd.set_option("display.width", 260)
say("=== PART 1: synthetic daily-reset leveraged Nasdaq Composite, month-end decisions ===")
say(P1[["variant", "CAGR_all", "Sh_all", "MDD_all", "CAGR_85-08", "MDD_85-08", "CAGR_09-26", "MDD_09-26"]]
    .to_string(index=False, float_format=lambda v: f"{v:.2f}" if abs(v) > 3 else f"{v:.1%}"))
say("\nCrash windows (cumulative-period CAGR / MDD):")
say(P1[["variant", "CAGR_00-02", "MDD_00-02", "CAGR_07-09", "MDD_07-09"]].to_string(index=False, float_format=lambda v: f"{v:.1%}"))
# validation vs actual TQQQ
tq = pd.DataFrame(json.load(open(os.path.join(ROOT, "outputs", "remediation_full_audit_20261104", "tiingo_etfs", "TQQQ.json"))))
tq["date"] = pd.to_datetime(tq["date"].str[:10])
tqm = tq.set_index("date")["adjClose"].astype(float).resample("ME").last().pct_change().dropna()
syn = V1["T0 3x buy&hold"].reindex(tqm.index).dropna()
say(f"\nValidation 2010-2026: corr(synthetic 3x Composite, actual TQQQ) monthly = {syn.corr(tqm.reindex(syn.index)):.3f}; "
    f"CAGR synthetic {perf(syn)[0]:.1%} vs actual TQQQ {perf(tqm.reindex(syn.index))[0]:.1%} (Composite is less volatile than NDX)")

# ============================================================================ PART 2: V4 overlays
say("\n=== PART 2: V4 overlays (2009-01..2026-10) ===")
src = open(os.path.join(ROOT, "v4_robust_upgrade_research.py")).read().split("# ---------------------------------------------------------------------------- 1. baselines")[0]
v = {"__file__": os.path.join(ROOT, "v4_robust_upgrade_research.py")}
exec(src, v)
MONTHS, SEPv, YM = v["MONTHS"], v["SEP"], v["YM"]
base = v["sleeve_targets"]("sharpe", 2, 5, SEPv)
dn = pd.read_csv(os.path.join(ROOT, "outputs", "v4_from_scratch_audit_20261114", "E_daily_nav.csv"), index_col=0, parse_dates=True).iloc[:, 0]
dr = dn.pct_change().dropna()
sig126 = dr.rolling(126).std() * np.sqrt(252)
med126 = sig126.expanding(min_periods=126).median()
qd = pd.DataFrame(json.load(open(os.path.join(ROOT, "outputs", "remediation_full_audit_20261104", "tiingo_etfs", "QQQ.json"))))
qd["date"] = pd.to_datetime(qd["date"].str[:10])
qm = qd.set_index("date")["adjClose"].astype(float).resample("ME").last()
q24 = qm / qm.shift(24) - 1
qv = dict(zip(v["REG"]["t"], v["REG"]["qqq_vol21"]))
qv_med = pd.Series(qv).expanding().median()


def scaled(targets, scale_fn):
    out = {}
    for t in MONTHS:
        w = dict(targets[t])
        s = scale_fn(t)
        if s < 1:
            stocks = {k: x * s for k, x in w.items() if k != "CASH"}
            cash = w.get("CASH", 0) + sum(x for k, x in w.items() if k != "CASH") * (1 - s)
            w = {**stocks, "CASH": cash}
        out[t] = w
    return out


def rm_scale(t):
    hist = sig126.loc[:t]
    if len(dr.loc[:t]) < 252 or not len(hist) or not np.isfinite(hist.iloc[-1]):
        return 1.0
    return float(min(1.0, med126.loc[:t].iloc[-1] / hist.iloc[-1]))


def dm_scale(t):
    return 0.5 if (q24.get(t, 0) < 0 and qv[t] > qv_med.loc[t]) else 1.0


rows2 = []
for name, tg in (("V4", base), ("V-RM (Barroso-Santa-Clara)", scaled(base, rm_scale)), ("V-DM (Daniel-Moskowitz panic)", scaled(base, dm_scale))):
    L, _ = v["simulate"](tg)
    ym = [YM[t] for t in MONTHS]
    c, s, d, top10 = v["stats"](L.net, ym)
    avg_exp = np.mean([sum(x for k, x in tg[t].items() if k != "CASH") for t in MONTHS])
    rows2.append({"variant": name, "CAGR": c, "Sharpe": s, "MonthlyMDD": d, "worst_month": L.net.min(), "avg_stock_exposure": avg_exp,
                  "CAGR_09-14": v["stats"](L.net, ym, "2009-01", "2014-12")[0], "CAGR_15-20": v["stats"](L.net, ym, "2015-01", "2020-12")[0],
                  "CAGR_21-26": v["stats"](L.net, ym, "2021-01", "2026-10")[0]})
P2 = pd.DataFrame(rows2)
P2.to_csv(os.path.join(OUT, "part2_v4_overlays.csv"), index=False)
say(P2.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
dm_months = [YM[t] for t in MONTHS if dm_scale(t) < 1]
say(f"V-DM panic months: {len(dm_months)} {dm_months}")
with open(os.path.join(OUT, "log.txt"), "w") as f:
    f.write("\n".join(LOG))
