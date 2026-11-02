import os
import pandas as pd, numpy as np
S = os.path.dirname(os.path.abspath(__file__)) + "/"
D = "/Users/happygolucky/Desktop/宏观观察器/outputs/gemini_full_data_audit_20261031/v2_standalone/"
P = pd.read_parquet(S + "claude_panel.parquet")
P = P[P["m121"].notna()]
rf = pd.read_csv(D + "v2_06_ledger_sp500_top3_oo_rs60.csv", parse_dates=["month"]).set_index("month")["rf"]

def cagr(r): return (1 + r).prod() ** (12 / len(r)) - 1
def mdd(r):
    e = (1 + r).cumprod(); return (e / e.cummax() - 1).min()

def sim(k, rank="m121", sma=None, rs=False, ret="roo", drift=True):
    out, wprev = [], {}
    for t, g in P.groupby("t"):
        m = t + pd.offsets.MonthEnd(1)
        g = g[g[rank].notna()]
        if ret == "roo": g = g[g["roo"].notna()]
        if sma == "pass": g = g[g["dist"] > 0]
        g = g.sort_values([rank, "ticker"], ascending=[False, True]).head(k)
        tgt, rets, slots = {}, {}, []
        for _, r in g.iterrows():
            ok = True
            if sma == "gate": ok &= bool(r["dist"] > 0)
            if rs: ok &= bool(r["rs60"] > r["spy60"])
            if ok:
                tgt[r.ticker] = 1 / k; rets[r.ticker] = r[ret]; slots.append(r.ticker)
            else:
                slots.append("CASH")
        rfm = rf.get(m, 0.0)
        cw = 1 - sum(tgt.values())
        gross = sum(tgt[s] * rets[s] for s in tgt) + cw * rfm
        turn = sum(abs(tgt.get(s, 0) - wprev.get(s, 0)) for s in set(tgt) | set(wprev))
        net = gross - 0.001 * turn
        if drift:
            wprev = {s: tgt[s] * (1 + rets[s]) / (1 + gross) for s in tgt}
        else:
            wprev = dict(tgt)
        out.append(dict(month=m, picks="|".join(slots), gross=gross, net=net, cash=cw))
    return pd.DataFrame(out).set_index("month")

def compare(name, mine, ledger_file, setwise):
    L = pd.read_csv(D + ledger_file, parse_dates=["month"]).set_index("month")
    idx = L.index.intersection(mine.index)
    if setwise:
        eq = [set(mine.at[i, "picks"].split("|")) == set(L.at[i, "picks"].split("|")) for i in idx]
    else:
        eq = [mine.at[i, "picks"] == L.at[i, "picks"] for i in idx]
    eq = pd.Series(eq, index=idx)
    gd = (mine.loc[idx, "gross"] - L.loc[idx, "gross"]).abs()
    print(f"\n== {name}: pick match {eq.sum()}/{len(idx)} | gross |diff|>0.5%: {(gd>0.005).sum()} months")
    for a in ["2010", "2015"]:
        print(f"   {a}-2026 CAGR  Claude={cagr(mine.loc[a:'2026-09','net'])*100:6.2f}%  Gemini={cagr(L.loc[a:'2026-09','net'])*100:6.2f}%"
              f" | MDD Claude={mdd(mine.loc[a:'2026-09','net'])*100:6.2f}% Gemini={mdd(L.loc[a:'2026-09','net'])*100:6.2f}%")
    bad = idx[(~eq.values) | (gd.values > 0.005)]
    if len(bad):
        x = pd.DataFrame({"claude": mine.loc[bad, "picks"], "gemini": L.loc[bad, "picks"],
                          "g_claude": mine.loc[bad, "gross"].round(4), "g_gemini": L.loc[bad, "gross"].round(4)})
        print(x.to_string())
    return mine

a = compare("Top-1 + SMA200 pass-down, next-day open", sim(1, sma="pass"), "v2_06_ledger_sp500_top1_sma200_oo.csv", False)
b = compare("Top-3 + RS(6-0)>SPY, next-day open", sim(3, rs=True), "v2_06_ledger_sp500_top3_oo_rs60.csv", True)
c = compare("Top-1 + SMA200 pass-down, close-close", sim(1, sma="pass", ret="rcc", drift=False), "v2_06_ledger_sp500_top1_sma200_cc.csv", False)
pd.to_pickle({"top1sma": a, "top3rs": b}, S + "claude_sims.pkl")
