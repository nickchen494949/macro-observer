import io, contextlib, sys, os, json
import numpy as np, pandas as pd
os.chdir("/Users/happygolucky/Desktop/宏观观察器")
sys.path.insert(0, ".")
with contextlib.redirect_stdout(io.StringIO()):
    import dashboard_best_leverage_strategy_search as d
DF = d.DF.infer_objects()
B5 = "B5_3x_SEP_VM (Current Primary)"
S2e = "S2e_SEP_VM + StructuralBust_SMA (Sahm/Rollover & <SMA10)"
S6b = "S6b_Golden_TrafficLight (SEP+VM+StructBustSMA+SafePanic)"

# 1. FMS coverage
fms = d.fms
print("1) FMS points", len(fms), "first", fms.index[0].date())
yrs = fms.groupby(fms.index.year).size()
print("   FMS points per year:", yrs.to_dict())
cov = DF.loc["2001-01-31":]
fms_avail = [(t - d.fms.loc[:t].index[-1]).days < 75 if len(d.fms.loc[:t]) else False for t in cov.index]
print("   months with usable FMS 2001+: %d / %d" % (sum(fms_avail), len(cov)))

# 2. Which months differ between B5 and S6b (ETF era) and contribution
def weights(name, tl, etf):
    fn = d.strats[name]; out = {}
    for t in tl:
        r = d.DF.loc[t]
        if etf:
            vc = float(d.var21_qqq.loc[:t].iloc[-1]); vm = float(d.med_var21_qqq.loc[:t].iloc[-1]); w_vm = min(1.0, vm / vc)
        else:
            w_vm = float(r["w_vm_var"])
        L, w = fn(r, w_vm); out[t] = (L, 0.0 if L == 0 else w)
    return out
wb, ws = weights(B5, d.T_etf, True), weights(S6b, d.T_etf, True)
rows = []
for t in d.T_etf:
    if abs(wb[t][1] - ws[t][1]) > 1e-9 or wb[t][0] != ws[t][0]:
        r3 = d.actual_m[3][t]; c = d.actual_m[0][t]
        rows.append({"t": t.strftime("%Y-%m"), "w_B5": round(wb[t][1], 2), "w_S6b": round(ws[t][1], 2),
                     "TQQQ_next": round(r3, 3), "excess_gain": round((ws[t][1] - wb[t][1]) * (r3 - c), 4),
                     "panic": bool(DF.loc[t, "panic_bottom"]), "bust": bool(DF.loc[t, "structural_bust"])})
X = pd.DataFrame(rows)
print("\n2) ETF-era months where S6b != B5:", len(X))
print(X.to_string(index=False))
print("   sum excess gain (arith):", round(X.excess_gain.sum(), 3), " months positive:", int((X.excess_gain > 0).sum()))
print("   top-3 months share of total gain:", round(X.excess_gain.nlargest(3).sum() / X.excess_gain.sum(), 2))

# 3. average exposure + exposure-matched B5 (uniformly scale-up via floor)
avg_b = np.mean([wb[t][1] for t in d.T_etf]); avg_s = np.mean([ws[t][1] for t in d.T_etf])
print("\n3) avg TQQQ weight ETF era: B5 %.3f  S6b %.3f" % (avg_b, avg_s))

def variant(floor_fn):
    def f(r, w_vm):
        if not r["sep_on"]: return (0, 0.0)
        if r["structural_bust"] and not r["trend_up"]: return (0, 0.0)
        return (3, floor_fn(r, w_vm))
    return f
tests = {
  "S2e (no panic boost)": variant(lambda r, w: w),
  "S6b floor0.80 (as published)": variant(lambda r, w: max(w, 0.8) if (r["panic_bottom"] and not r["structural_bust"]) else w),
  "PLACEBO: floor0.80 in RANDOM-ish months? -> uniform floor 0.35 always": variant(lambda r, w: max(w, 0.35)),
  "uniform floor 0.50 always": variant(lambda r, w: max(w, 0.50)),
  "VM sqrt (less aggressive cut)": variant(lambda r, w: np.sqrt(w)),
  "panic floor 0.60": variant(lambda r, w: max(w, 0.6) if (r["panic_bottom"] and not r["structural_bust"]) else w),
  "panic floor 1.00": variant(lambda r, w: 1.0 if (r["panic_bottom"] and not r["structural_bust"]) else w),
  "panic = FMS only": variant(lambda r, w: max(w, 0.8) if (r["fms_panic"] and not r["structural_bust"]) else w),
  "panic = FINRA<=-15 only": variant(lambda r, w: max(w, 0.8) if (r["fin_washed"] and not r["structural_bust"]) else w),
  "panic = CFTC only": variant(lambda r, w: max(w, 0.8) if (r["cftc_washed"] and not r["structural_bust"]) else w),
  "panic = INVERTED (boost when NOT panic)": variant(lambda r, w: max(w, 0.8) if (not r["panic_bottom"] and not r["structural_bust"]) else w),
}
out = []
for k, fn in tests.items():
    sa, _ = d.run_strategy(fn, d.T, d.synth_m)
    sc, sd = d.run_strategy(fn, d.T_etf, d.actual_m, use_qqq_vm=True, daily_dict=d.actual_d)
    ma = d.calc_metrics(sa.loc["2001-07-01":], d.rf_m_synth); mc = d.calc_metrics(sc, d.rf_m_actual, s_d=sd)
    m85 = d.calc_metrics(sa.loc[:"2000-12-31"], d.rf_m_synth)
    out.append({"variant": k, "85-00 CAGR": m85["CAGR"], "01-26 CAGR": ma["CAGR"], "01-26 Sh": ma["Sharpe"], "01-26 MDD": ma["MaxDD_M"],
                "ETF CAGR": mc["CAGR"], "ETF Sh": mc["Sharpe"], "ETF MDD_D": mc["MaxDD_D"]})
O = pd.DataFrame(out)
for c in O.columns[1:]:
    O[c] = O[c].map(lambda v: f"{v:.2f}" if "Sh" in c else f"{v:.1%}")
print("\n3b) sensitivity / placebo:")
print(O.to_string(index=False))

# 4. significance of S6b - B5 (ETF era & 2001-26 synthetic)
for lab, sa, sb, rf in (("ETF 2010-26", d.m_series_C[S6b], d.m_series_C[B5], d.rf_m_actual),
                        ("Synth 2001-26", d.m_series_A[S6b].loc["2001-07-01":], d.m_series_A[B5].loc["2001-07-01":], d.rf_m_synth)):
    diff = (sa - sb).dropna(); tstat = diff.mean() / diff.std(ddof=1) * np.sqrt(len(diff))
    rng = np.random.default_rng(0); n = len(diff); bs = []
    for _ in range(5000):
        idx = rng.integers(0, n - 5, n // 6); ii = np.concatenate([np.arange(i, i + 6) for i in idx])[:n]
        a, b = sa.values[ii], sb.values[ii]
        bs.append((np.prod(1 + a) ** (12 / n) - 1) - (np.prod(1 + b) ** (12 / n) - 1))
    bs = np.array(bs)
    print(f"\n4) {lab}: mean monthly diff {diff.mean():.4f}, t={tstat:.2f}, nonzero months={int((diff.abs()>1e-9).sum())}; block-bootstrap CAGR diff 5/50/95%: {np.percentile(bs,5):.3f}/{np.percentile(bs,50):.3f}/{np.percentile(bs,95):.3f}, P(diff<=0)={np.mean(bs<=0):.2f}")

# 5. 1985-2000 where FMS/CFTC/FINRA don't exist
pre = (d.m_series_A[S6b].loc[:"1997-12-31"] - d.m_series_A[B5].loc[:"1997-12-31"]).abs()
print("\n5) 1985-1997 months S6b != B5:", int((pre > 1e-9).sum()))

# 6. 41y MaxDD location for S6b
s = d.m_series_A[S6b]; w = (1 + s).cumprod(); dd = w / w.cummax() - 1
trough = dd.idxmin(); peak = w.loc[:trough].idxmax()
print("\n6) S6b 41y MaxDD %.1f%% peak %s trough %s" % (dd.min() * 100, peak.date(), trough.date()))

# 7. Execution lag: signal at close t, trade at close t+1 (ETF era, daily)
def run_lag(name):
    fn = d.strats[name]; rets = []
    allw = weights(name, d.T_etf, True)
    for t in d.T_etf:
        L, w = allw[t]
        days = d.qqq_p.loc[(d.qqq_p.index > t) & (d.qqq_p.index <= t + pd.offsets.MonthEnd(1))].index
        if not len(days): continue
        rets.append((t, L, w, days))
    out = []; prev = (0, 0.0)
    for i, (t, L, w, days) in enumerate(rets):
        for j, day in enumerate(days):
            Lc, wc = (prev if j == 0 else (L, w))   # first day still old position
            r3 = d.actual_d[Lc][t].get(day, 0.0) if Lc > 0 else 0.0
            r0 = d.actual_d[0][t].get(day, 0.0)
            out.append(wc * r3 + (1 - wc) * r0)
        prev = (L, w)
    r = pd.Series(out); W = (1 + r).cumprod()
    return W.iloc[-1] ** (252 / len(r)) - 1, (W / W.cummax() - 1).min()
for nm in (B5, S6b):
    c, m = run_lag(nm); print(f"7) 1-day execution lag {nm[:4]}: CAGR {c:.1%} dailyMDD {m:.1%}")
