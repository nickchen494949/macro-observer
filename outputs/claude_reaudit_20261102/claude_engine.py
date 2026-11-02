"""
Claude's independent portfolio simulator (imports nothing from Gemini code).

Rules (identical *specification* to the audited strategies, independently implemented):
  rank stocks by `rank` desc (ties by ticker); optional SMA200 'pass' (drop dist<=0 before ranking)
  or 'gate' (slot -> cash if dist<=0); optional RS gate (slot -> cash if rs <= bench);
  equal 1/k slot targets; cash earns raw-FRED T-bill rf; cost 10bp x equity turnover vs drifted
  previous weights (additive).
"""
import numpy as np, pandas as pd
from _paths import raw_rf_monthly

RF = raw_rf_monthly()


def simulate(panel, k, rank="r121", sma=None, rs=None, bench=None, ret="ret_exec", cost=0.001,
             drift=True, require_121=True):
    out, wprev = [], {}
    P = panel
    if require_121:
        P = P[P["r121"].notna()]
    for t, g in P.groupby("t", sort=True):
        m = t + pd.offsets.MonthEnd(1)
        g = g[g[rank].notna() & g[ret].notna()]
        if sma == "pass":
            g = g[g["dist"] > 0]
        g = g.sort_values([rank, "ticker"], ascending=[False, True]).head(k)
        tgt, rets, slots, fbs = {}, {}, [], 0
        for r in g.itertuples(index=False):
            ok = True
            if sma == "gate":
                ok &= bool(r.dist > 0)
            if rs is not None:
                ok &= bool(getattr(r, rs) > getattr(r, bench))
            if ok:
                tgt[r.ticker] = tgt.get(r.ticker, 0) + 1 / k
                rets[r.ticker] = getattr(r, ret)
                slots.append(r.ticker)
                fbs += int(bool(getattr(r, "fb", False)))
            else:
                slots.append("CASH")
        slots += ["CASH"] * (k - len(slots))
        rfm = float(RF.get(m, 0.0))
        cw = 1 - sum(tgt.values())
        gross = sum(tgt[s] * rets[s] for s in tgt) + cw * rfm
        turn = sum(abs(tgt.get(s, 0) - wprev.get(s, 0)) for s in set(tgt) | set(wprev))
        net = gross - cost * turn
        wprev = ({s: tgt[s] * (1 + rets[s]) / (1 + gross) for s in tgt} if (drift and 1 + gross > 0)
                 else dict(tgt))
        out.append(dict(month=m, picks="|".join(slots), gross=gross, net=net, cash=cw, rf=rfm,
                        turn=turn, fb_slots=fbs))
    return pd.DataFrame(out).set_index("month")


def cagr(r):
    return (1 + r).prod() ** (12 / len(r)) - 1


def mdd(r):
    e = (1 + r).cumprod()
    return (e / e.cummax() - 1).min()
