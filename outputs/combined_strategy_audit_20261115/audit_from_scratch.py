#!/usr/bin/env python3
"""
audit_from_scratch.py — Independent, zero-shared-code audit of the "COMBO A" index-leverage rule
    TQQQ weight = SEP x min(w_RV21, w_VIX) x CTA_Baz_trim      (rest in BIL/SGOV)
claimed (combined_macro_vrp_cta_test.py, 2026-11-15): 2010-2026 TQQQ CAGR 32.4%, Sharpe 1.08,
monthly MDD -28.1%, daily MDD -35.5% vs B5 (SEP x w_RV21) 37.2% / 1.02 / -34.0% / -45.2%.

Nothing is imported from the audited scripts. Everything is rebuilt from raw files:
  data/yahoo/_IXIC.json, data/fred/{VIXCLS,DGS3MO,DGS2,PCEPILFE}.json,
  outputs/remediation_full_audit_20261104/tiingo_etfs/{QQQ,TQQQ,BIL,SGOV}.json,
  outputs/pure_momentum_1985_2026_audit/inputs/v3_regime_and_cash_214m.csv (real SEP switch).

Daily simulation with drifting weights inside the month (the audited code mixed monthly buy-and-hold for
CAGR with daily-rebalanced weights for daily MDD).
"""
import json
import os
import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
OUT = os.path.dirname(os.path.abspath(__file__))
LOG = []


def say(*a):
    s = " ".join(str(x) for x in a)
    print(s)
    LOG.append(s)


# ----------------------------------------------------------------------------- raw data
def fred(n):
    v = json.load(open(os.path.join(ROOT, "data", "fred", f"{n}.json")))["values"]
    return pd.Series({pd.Timestamp(d): float(x) for d, x in v if x not in (None, ".")}).sort_index()


def yahoo(n):
    v = json.load(open(os.path.join(ROOT, "data", "yahoo", f"{n}.json")))
    v = v.get("values", v) if isinstance(v, dict) else v
    return pd.Series({pd.Timestamp(d): float(x) for d, x in v if x is not None}).sort_index()


def tiingo(sym):
    d = json.load(open(os.path.join(ROOT, "outputs", "remediation_full_audit_20261104", "tiingo_etfs", f"{sym}.json")))
    df = pd.DataFrame({"c": [r["adjClose"] for r in d], "o": [r["adjOpen"] for r in d]},
                      index=pd.to_datetime([r["date"][:10] for r in d]))
    return df[~df.index.duplicated(keep="last")].sort_index()


ixic = yahoo("_IXIC")
vix = fred("VIXCLS")
dgs3 = fred("DGS3MO")
dgs2 = fred("DGS2")
pce = fred("PCEPILFE")
QQQ, TQQQ, BIL, SGOV = tiingo("QQQ"), tiingo("TQQQ"), tiingo("BIL"), tiingo("SGOV")
REG = pd.read_csv(os.path.join(ROOT, "outputs", "pure_momentum_1985_2026_audit", "inputs", "v3_regime_and_cash_214m.csv"))
REAL_SEP = dict(zip(pd.to_datetime(REG["t"]), REG["sep_on"].astype(bool)))

say(f"Data: IXIC {ixic.index[0].date()}..{ixic.index[-1].date()} | VIX {vix.index[0].date()}..{vix.index[-1].date()} | "
    f"TQQQ {TQQQ.index[0].date()}..{TQQQ.index[-1].date()} | SGOV {SGOV.index[0].date()}..{SGOV.index[-1].date()}")
say(f"Real SEP switch rows: {len(REAL_SEP)}, OFF formation months: "
    f"{sorted(t.strftime('%Y-%m') for t, v in REAL_SEP.items() if not v)}")

# ----------------------------------------------------------------------------- SEP proxy (re-derived from its written spec)
pyoy = (pce / pce.shift(12) - 1) * 100
ME_ALL = pd.date_range("1984-12-31", "2026-10-31", freq="ME")


def last_le(s, t, max_age=40):
    x = s.loc[:t]
    if not len(x) or (t - x.index[-1]).days > max_age:
        return np.nan
    return float(x.iloc[-1])


state, PROXY = True, {}
for t in ME_ALL:
    chg = last_le(dgs2, t) - last_le(dgs2, t - pd.offsets.MonthEnd(3), max_age=10_000)
    m = (t - pd.offsets.MonthEnd(2)).to_period("M").to_timestamp()
    m3 = (t - pd.offsets.MonthEnd(5)).to_period("M").to_timestamp()
    hot = pyoy.get(m, np.nan) > 2.0 and pyoy.get(m, np.nan) > pyoy.get(m3, np.nan)
    if state and chg > 0.25 and hot:
        state = False
    elif (not state) and chg <= 0:
        state = True
    PROXY[t] = state


def sep_at(t):
    return REAL_SEP[t] if t >= pd.Timestamp("2015-11-30") else PROXY[t]


# ----------------------------------------------------------------------------- signal features
def features(p, baz_mode="audited"):
    """baz_mode: 'audited' = halflife=n EWMAs + EWM std (what the audited code did);
                 'paper'   = Baz et al. (2015): lambda=(n-1)/n EWMAs, rolling 63d price-change std, rolling 252d std."""
    p = p.dropna()
    r = p.pct_change()
    rv21 = r.rolling(21).std() * np.sqrt(252)
    med = rv21.expanding(min_periods=252).median()
    w_rv = ((med / rv21) ** 2).clip(upper=1.0)
    dp = p.diff()
    s63 = dp.ewm(halflife=63, min_periods=21).std() if baz_mode == "audited" else dp.rolling(63).std()
    zs, ps = [], []
    k = np.sqrt(2) * np.exp(-0.5)
    for S, L in ((8, 24), (16, 48), (32, 96)):
        if baz_mode == "audited":
            x = p.ewm(halflife=S, min_periods=S).mean() - p.ewm(halflife=L, min_periods=L).mean()
        else:
            x = p.ewm(com=S - 1, min_periods=S).mean() - p.ewm(com=L - 1, min_periods=L).mean()
        y = x / s63
        sy = y.ewm(halflife=252, min_periods=63).std() if baz_mode == "audited" else y.rolling(252).std()
        z = (y / sy).clip(-4, 4)
        zs.append(z)
        ps.append(z * np.exp(-z ** 2 / 4) / k)
    z_comp = sum(zs) / 3
    psi_long = (sum(ps) / 3).clip(0, 1)
    return pd.DataFrame({"r": r, "rv21": rv21, "w_rv": w_rv, "z": z_comp, "psi": psi_long})


med_vix = vix.expanding(min_periods=252).median()


def w_vix_at(t, fallback=19.0):
    v = last_le(vix, t)
    m = med_vix.loc[:t]
    m = float(m.iloc[-1]) if len(m) and pd.notna(m.iloc[-1]) else fallback
    return min(1.0, (m / v) ** 2)


# ----------------------------------------------------------------------------- daily return bases
# A) Actual ETFs 2010-2026: risky = TQQQ, cash = BIL until 2020-06-30 then SGOV (same splice as audited code)
cash_c = pd.concat([BIL["c"].loc[:"2020-06-30"].pct_change(), SGOV["c"].loc["2020-07-01":].pct_change()])
cash_o = pd.concat([BIL["o"].loc[:"2020-06-30"].pct_change(), SGOV["o"].loc["2020-07-01":].pct_change()])
# first SGOV day return vs last BIL day is not defined -> 0 (one day of T-bill carry, negligible)
ETF_DAYS = TQQQ.index
ETF = {
    "close": pd.DataFrame({"risk": TQQQ["c"].pct_change(), "cash": cash_c}).reindex(ETF_DAYS).fillna(0.0),
    "open": pd.DataFrame({"risk": TQQQ["o"].pct_change(), "cash": cash_o}).reindex(ETF_DAYS).fillna(0.0),
}
# B) Synthetic 3x daily-reset Nasdaq Composite 1990-2026 (price index, no dividends), financing = 3M bill + 50bp, ER 0.95%
r_ix = ixic.pct_change().dropna()
rf_d = (dgs3 / 100).reindex(r_ix.index).ffill().bfill() / 252
SYN = {"close": pd.DataFrame({"risk": 3 * r_ix - 2 * (rf_d + 0.005 / 252) - 0.0095 / 252, "cash": rf_d})}


def simulate(weights, base, exec_lag=0, cost=0.0010):
    """weights: dict formation month-end t -> risky weight. exec_lag: trading days after t's last session.
    Drifting weights inside the month; turnover cost on |w_target - w_drifted|."""
    days = base.index
    ts = sorted(weights)
    V, w_prev, eq, mret, mcash = 1.0, 0.0, [], {}, {}
    for i, t in enumerate(ts):
        i0 = days.searchsorted(t, side="right") - 1 + exec_lag          # execution session index
        t_next = ts[i + 1] if i + 1 < len(ts) else t + pd.offsets.MonthEnd(1)
        i1 = days.searchsorted(t_next, side="right") - 1 + exec_lag
        i1 = min(i1, len(days) - 1)
        if i0 < 0 or i1 <= i0:
            continue
        seg = base.iloc[i0 + 1:i1 + 1]
        w = float(np.clip(weights[t], 0, 1))
        V0 = V * (1 - abs(w - w_prev) * cost)
        gr = (1 + seg["risk"]).cumprod()
        gc = (1 + seg["cash"]).cumprod()
        path = V0 * (w * gr + (1 - w) * gc)
        eq.append(path)
        mret[t] = path.iloc[-1] / V - 1
        mcash[t] = gc.iloc[-1] - 1
        end_r, end_c = w * gr.iloc[-1], (1 - w) * gc.iloc[-1]
        w_prev = end_r / (end_r + end_c) if (end_r + end_c) > 0 else 0.0
        V = path.iloc[-1]
    return pd.Series(mret), pd.Series(mcash), pd.concat(eq)


def stats(mret, mcash, eq):
    n = len(mret)
    cagr = (1 + mret).prod() ** (12 / n) - 1
    ex = mret - mcash
    sh = ex.mean() / mret.std(ddof=1) * np.sqrt(12)
    wm = (1 + mret).cumprod()
    mdd_m = (wm / np.maximum(wm.cummax(), 1.0) - 1).min()
    e = pd.concat([pd.Series([1.0]), eq.reset_index(drop=True)])
    mdd_d = (e / e.cummax() - 1).min()
    return {"CAGR": cagr, "Sharpe": sh, "MDD_M": mdd_m, "MDD_D": mdd_d, "Calmar": cagr / abs(mdd_d), "Vol": mret.std() * np.sqrt(12)}


def fmt(d):
    return (f"CAGR {d['CAGR']:6.1%} | Sharpe {d['Sharpe']:.2f} | Vol {d['Vol']:5.1%} | MDD_M {d['MDD_M']:6.1%} | "
            f"MDD_D {d['MDD_D']:6.1%} | Calmar {d['Calmar']:.2f}")


# ----------------------------------------------------------------------------- weights per strategy
T_ETF = [t for t in ME_ALL if pd.Timestamp("2010-03-31") <= t <= pd.Timestamp("2026-09-30")]
T_SYN = [t for t in ME_ALL if pd.Timestamp("1990-01-31") <= t <= pd.Timestamp("2026-09-30")]

FEAT = {("ETF", m): features(QQQ["c"], m) for m in ("audited", "paper")}
FEAT.update({("SYN", m): features(ixic, m) for m in ("audited", "paper")})


def comp(t, F, thr=np.sqrt(2)):
    row = F.loc[:t].iloc[-1]
    wr, wv = float(row["w_rv"]), w_vix_at(t)
    trim = float(row["psi"]) if row["z"] > thr else 1.0
    return {"sep": sep_at(t), "proxy": PROXY[t], "w_rv": wr, "w_vix": wv, "trim": trim, "z": float(row["z"])}


def build(T, F, rule, thr=np.sqrt(2)):
    out = {}
    for t in T:
        c = comp(t, F, thr)
        out[t] = rule(c)
    return out


RULES = {
    "PureSEP (100%/0%)": lambda c: 1.0 if c["sep"] else 0.0,
    "B5  = SEP x w_RV": lambda c: c["w_rv"] if c["sep"] else 0.0,
    "DualVol = SEP x min(RV,VIX)": lambda c: min(c["w_rv"], c["w_vix"]) if c["sep"] else 0.0,
    "B0  = min(RV,VIX) x trim (no SEP)": lambda c: min(c["w_rv"], c["w_vix"]) * c["trim"],
    "COMBO_A = SEP x min(RV,VIX) x trim": lambda c: min(c["w_rv"], c["w_vix"]) * c["trim"] if c["sep"] else 0.0,
}

results = {}
say("\n=== 1. REPRODUCTION (audited Baz implementation, execution at signal close like the audited code) ===")
for per, T, base in (("ETF 2010-04..2026-10 (TQQQ)", T_ETF, ETF["close"]), ("SYN 1990-02..2026-10 (3x IXIC)", T_SYN, SYN["close"])):
    say(f"-- {per}")
    F = FEAT[("ETF" if per.startswith("ETF") else "SYN", "audited")]
    for name, rule in RULES.items():
        W = build(T, F, rule)
        m, c, e = simulate(W, base)
        s = stats(m, c, e)
        s["avgW"] = np.mean(list(W.values()))
        results[(per[:3], name)] = (W, m, c, e, s)
        say(f"  {name:<38} {fmt(s)} | avg TQQQ {s['avgW']:.0%}")
say("  Audited claims (ETF): B5 37.2%/1.02/-34.0%/-45.2%; DualVol 35.0%/1.05/-34.0%/-39.7%; B0 30.0%/0.94/-31.5%/-40.0%;"
    " COMBO_A 32.4%/1.08/-28.1%/-35.5%; PureSEP 49.1%/1.06/-49.1%/-69.9%")

# ----------------------------------------------------------------------------- 2. execution timing
say("\n=== 2. EXECUTION TIMING (ETF). Audited code trades at the SAME close used for the signal (VIX closes 15 min later) ===")
for lab, base, lag in (("same close t", ETF["close"], 0), ("next close t+1", ETF["close"], 1), ("next open t+1", ETF["open"], 1)):
    row = []
    for name in ("B5  = SEP x w_RV", "COMBO_A = SEP x min(RV,VIX) x trim"):
        W = results[("ETF", name)][0]
        m, c, e = simulate(W, base, exec_lag=lag)
        s = stats(m, c, e)
        row.append(f"{name.split('=')[0].strip()}: {s['CAGR']:.1%}/{s['Sharpe']:.2f}/MDD_D {s['MDD_D']:.1%}")
    say(f"  {lab:<15} " + " || ".join(row))

# ----------------------------------------------------------------------------- 3. matched risk
say("\n=== 3. MATCHED RISK: is COMBO_A better than simply holding LESS B5? (ETF, same close) ===")
WA = results[("ETF", "COMBO_A = SEP x min(RV,VIX) x trim")][0]
WB = results[("ETF", "B5  = SEP x w_RV")][0]
sA = results[("ETF", "COMBO_A = SEP x min(RV,VIX) x trim")][4]
for lab, k in (("B5 x k (match avg weight)", np.mean(list(WA.values())) / np.mean(list(WB.values()))),):
    m, c, e = simulate({t: k * w for t, w in WB.items()}, ETF["close"])
    say(f"  {lab}, k={k:.3f}: {fmt(stats(m, c, e))}")
# match monthly vol by bisection
lo, hi = 0.3, 1.0
for _ in range(30):
    k = (lo + hi) / 2
    m, c, e = simulate({t: k * w for t, w in WB.items()}, ETF["close"])
    (lo, hi) = (k, hi) if stats(m, c, e)["Vol"] < sA["Vol"] else (lo, k)
m, c, e = simulate({t: k * w for t, w in WB.items()}, ETF["close"])
say(f"  B5 x k (match monthly vol), k={k:.3f}: {fmt(stats(m, c, e))}")
say(f"  COMBO_A                         : {fmt(sA)}")

# ----------------------------------------------------------------------------- 4. bootstrap
say("\n=== 4. STATIONARY BLOCK BOOTSTRAP (mean block 12m, 5000 draws) on paired monthly returns ===")
rng = np.random.default_rng(20261115)


def boot(ma, ca, mb, cb, n=5000, blk=12):
    idx = ma.index.intersection(mb.index)
    A, B, C = ma[idx].values, mb[idx].values, ca[idx].values
    N = len(idx)
    dS, dC = [], []
    for _ in range(n):
        ii, i = [], rng.integers(N)
        while len(ii) < N:
            ii.append(i)
            i = rng.integers(N) if rng.random() < 1 / blk else (i + 1) % N
        ii = np.array(ii)
        a, b, c = A[ii], B[ii], C[ii]
        dS.append((a - c).mean() / a.std(ddof=1) * np.sqrt(12) - (b - c).mean() / b.std(ddof=1) * np.sqrt(12))
        dC.append(np.prod(1 + a) ** (12 / N) - np.prod(1 + b) ** (12 / N))
    dS, dC = np.array(dS), np.array(dC)
    return dS, dC


pairs = [("ETF", "COMBO_A = SEP x min(RV,VIX) x trim", "B5  = SEP x w_RV", "CTA trim + VIX vs B5"),
         ("ETF", "COMBO_A = SEP x min(RV,VIX) x trim", "B0  = min(RV,VIX) x trim (no SEP)", "SEP contribution"),
         ("SYN", "COMBO_A = SEP x min(RV,VIX) x trim", "B5  = SEP x w_RV", "CTA trim + VIX vs B5 (1990-2026 synth)")]
for per, a, b, lab in pairs:
    _, ma, ca, _, sa = results[(per, a)]
    _, mb, cb, _, sb = results[(per, b)]
    dS, dC = boot(ma, ca, mb, cb)
    say(f"  {lab:<42} dSharpe {sa['Sharpe'] - sb['Sharpe']:+.3f} (90% CI {np.percentile(dS, 5):+.2f}..{np.percentile(dS, 95):+.2f}, "
        f"P(dSharpe<=0)={np.mean(dS <= 0):.2f}) | dCAGR {sa['CAGR'] - sb['CAGR']:+.1%} (P<=0 {np.mean(dC <= 0):.2f})")

# ----------------------------------------------------------------------------- 5. where do the differences come from
say("\n=== 5. CALENDAR-YEAR RETURNS (ETF, same close) ===")
yr = {}
for name in ("B5  = SEP x w_RV", "B0  = min(RV,VIX) x trim (no SEP)", "COMBO_A = SEP x min(RV,VIX) x trim"):
    m = results[("ETF", name)][1]
    m.index = [t + pd.offsets.MonthEnd(1) for t in m.index]
    yr[name.split("=")[0].strip()] = (1 + m).groupby(m.index.year).prod() - 1
Y = pd.DataFrame(yr)
Y["A-B5"] = Y["COMBO_A"] - Y["B5"]
Y["A-B0 (SEP)"] = Y["COMBO_A"] - Y["B0"]
say(Y.to_string(float_format=lambda v: f"{v:+.1%}"))
lw = np.log1p(Y["COMBO_A"]) - np.log1p(Y["B0"])
say(f"  SEP log-wealth contribution total {lw.sum():+.3f}; of which 2022 {lw.get(2022, 0):+.3f}; ex-2022 {lw.drop(2022, errors='ignore').sum():+.3f}")


def dd_window(eq):
    e = eq / eq.cummax() - 1
    trough = e.idxmin()
    peak = eq.loc[:trough].idxmax()
    return peak.date(), trough.date(), e.min()


for name in ("B5  = SEP x w_RV", "COMBO_A = SEP x min(RV,VIX) x trim", "B0  = min(RV,VIX) x trim (no SEP)"):
    say(f"  max daily DD window {name:<38}: peak {dd_window(results[('ETF', name)][3])}")

# ----------------------------------------------------------------------------- 6. parameter / implementation fragility
say("\n=== 6. FRAGILITY: Baz threshold and implementation (ETF same close | SYN 1990-2026) ===")
for mode in ("audited", "paper"):
    for thr in (1.0, 1.25, np.sqrt(2), 1.75, 2.0, 99):
        out = []
        for per, T, base in (("ETF", T_ETF, ETF["close"]), ("SYN", T_SYN, SYN["close"])):
            W = build(T, FEAT[(per, mode)], RULES["COMBO_A = SEP x min(RV,VIX) x trim"], thr=thr)
            m, c, e = simulate(W, base)
            s = stats(m, c, e)
            out.append(f"{per}: {s['CAGR']:.1%}/{s['Sharpe']:.2f}/MDD_D {s['MDD_D']:.1%}")
        tl = "no trim" if thr == 99 else f"z>{thr:.2f}"
        say(f"  Baz={mode:<7} {tl:<8} " + " || ".join(out))

# ----------------------------------------------------------------------------- 7. the 'z>=2 => 3x loses -9.9%/yr' claim
say("\n=== 7. CLAIM CHECK: 'when trend z >= 2, next-day 3x Nasdaq returns -9.9%/yr' (IXIC daily, 1985-2026) ===")
import statsmodels.api as sm  # noqa: E402

for mode in ("audited", "paper"):
    F = features(ixic, mode).loc["1985-05-01":"2026-10-31"]
    nxt = F["r"].shift(-1)
    for a, b in (("1985", "1999"), ("2000", "2009"), ("2010", "2026"), ("1985", "2026")):
        f = F.loc[a:b]
        n = nxt.loc[a:b]
        hi = f["z"] >= 2.0
        mid = (f["z"] >= 0.5) & (f["z"] < 1.5)
        X = sm.add_constant(pd.DataFrame({"hi": hi.astype(float), "mid": mid.astype(float)}))
        ok = n.notna()
        res = sm.OLS(n[ok], X[ok]).fit(cov_type="HAC", cov_kwds={"maxlags": 21})
        d = (res.params["hi"] - res.params["mid"]) * 252
        se = np.sqrt(res.cov_params().loc["hi", "hi"] + res.cov_params().loc["mid", "mid"] - 2 * res.cov_params().loc["hi", "mid"]) * 252
        say(f"  Baz={mode:<7} {a}-{b}: days z>=2 {int(hi.sum()):5d} mean {n[hi].mean() * 252:+6.1%}/yr | "
            f"0.5<=z<1.5 {int(mid.sum()):5d} mean {n[mid].mean() * 252:+6.1%}/yr | diff {d:+6.1%}/yr, HAC t={d / se:+.2f}")

# ----------------------------------------------------------------------------- 8. 'CTA washout => +2.77% next 21d' claim, de-clustered
say("\n=== 8. CLAIM CHECK: 'after CTA washout (z<=-1 & 20d DD <= -3 daily sigma) Nasdaq +2.77% next 21d' — de-clustered ===")
F = features(ixic, "audited").loc["1985-05-01":"2026-10-31"]
p = ixic.loc[F.index]
dds = (p / p.rolling(20).max() - 1) / (F["rv21"] / np.sqrt(252))
wash = (F["z"] <= -1.0) & (dds <= -3.0)
f21 = p.shift(-21) / p - 1
days = list(F.index[wash & f21.notna()])
eps, last = [], None
for d in days:
    if last is None or F.index.get_loc(d) - F.index.get_loc(last) > 21:
        eps.append(d)
    last = d
e21 = f21.loc[eps]
uncond = f21.dropna()
say(f"  raw (overlapping) washout days: {len(days)}, mean fwd21 {f21.loc[days].mean():+.2%} | "
    f"independent episodes: {len(eps)}, mean fwd21 {e21.mean():+.2%}, median {e21.median():+.2%}, "
    f"win {(e21 > 0).mean():.0%}, t={e21.mean() / (e21.std(ddof=1) / np.sqrt(len(e21))):+.2f} | unconditional 21d mean {uncond.mean():+.2%}")
say("  episodes by decade: " + str(pd.Series([d.year // 10 * 10 for d in eps]).value_counts().sort_index().to_dict()))

# ----------------------------------------------------------------------------- 9. small data issues
say("\n=== 9. SMALL ISSUES ===")
nfb = sum(1 for t in T_SYN if pd.isna(med_vix.loc[:t].iloc[-1]))
say(f"  months where VIX median is undefined and the hard-coded 19.0 fallback is used: {nfb} (1990)")
dis = [(t + pd.offsets.MonthEnd(1)).strftime("%Y-%m") for t in T_ETF if t >= pd.Timestamp("2015-11-30") and REAL_SEP[t] != PROXY[t]]
say(f"  real SEP vs proxy disagreement hold-months 2015-12..2026-10: {len(dis)} -> {dis}")
# C4 claim: ON if real SEP OR proxy ON
c4 = {}
for t in T_ETF:
    c = comp(t, FEAT[("ETF", "audited")])
    on = (REAL_SEP[t] or PROXY[t]) if t >= pd.Timestamp("2015-11-30") else PROXY[t]
    c4[t] = min(c["w_rv"], c["w_vix"]) * c["trim"] if on else 0.0
m, c, e = simulate(c4, ETF["close"])
say(f"  C4 (ON if real SEP OR proxy ON) x combo, ETF: {fmt(stats(m, c, e))}  vs COMBO_A {fmt(sA)}")

# ----------------------------------------------------------------------------- 10. live readout
say("\n=== 10. LIVE READOUT RECOMPUTED ===")
Fq = FEAT[("ETF", "audited")]
Fi = features(ixic, "audited")
t_live = pd.Timestamp("2026-10-31")
c = comp(t_live, Fq)
say(f"  formation 2026-10-31 (QQQ features): SEP={'ON' if c['sep'] else 'OFF'}, w_RV {c['w_rv']:.0%}, w_VIX {c['w_vix']:.0%}, z {c['z']:+.2f}, trim {c['trim']:.0%} "
    f"-> COMBO_A TQQQ weight {RULES['COMBO_A = SEP x min(RV,VIX) x trim'](c):.0%}")
li = Fi.iloc[-1]
say(f"  latest IXIC day {Fi.index[-1].date()}: z {li['z']:+.2f}, w_RV {li['w_rv']:.0%}, VIX {vix.iloc[-1]:.1f} ({vix.index[-1].date()})")

with open(os.path.join(OUT, "audit_log.txt"), "w") as f:
    f.write("\n".join(LOG))
