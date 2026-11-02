import os
import sys, pandas as pd, numpy as np
sys.path.insert(0, "/Users/happygolucky/Desktop/宏观观察器/outputs/gemini_full_data_audit_20261031/v2_standalone")
import v2_07_mece_24_grid_cleanroom_auditor as G
from v2_cleanroom_lib import CleanRoomEquityStore
REPO = G.REPO_ROOT; ssm = REPO + "/" + G.ORIG_SSM_REL; dd = ssm + "/data"
store = CleanRoomEquityStore(REPO, ssm_rel=G.ORIG_SSM_REL, include_ndx=False)
cmap, aliases = G.cleanroom_reconstruct_cik_map_and_aliases(ssm, store)
print("alias evidence types:", aliases["evidence"].map(lambda s: s.split("_")[0] + "_" + s.split("_")[1] if "sec_same" in s else s).value_counts().to_dict())
bad = G.cleanroom_untrusted_and_excluded_spells(dd, store)
me = store.P.index
mem = G.cleanroom_load_pit_membership(dd, me, bad)
sec = G.cleanroom_build_pit_sector_panel(dd, store, aliases, cmap, me)
fd = me[(me >= "2009-12-31") & (me <= "2026-08-31")]
panel = G.build_mece_panel(store, mem, sec, fd)

# coverage: raw membership snapshot vs usable panel
h = pd.read_csv(dd + "/sp500_hist_components.csv", parse_dates=["date"]).sort_values("date")
raw_n = sum(len(str(h[h.date <= t].iloc[-1].tickers).split(",")) for t in fd)
elig = panel[panel.has_12_1].groupby("t").size()
print(f"member-months raw={raw_n}  after trust filter={sum(len(mem[t]) for t in fd)}  usable w/ 12-1={elig.sum()}  ({100*elig.sum()/raw_n:.1f}%)")
print("ret_oo NaN among 12-1-eligible:", int(panel[panel.has_12_1].ret_oo.isna().sum()))

def run(**kw):
    return G.simulate_mece_cell(panel, store, fd, exec_mode="open", weight_mode="drifted", **kw)
S = {
 "T3_base": run(rank_col="mom_12_1", k=3),
 "T3_rs":   run(rank_col="mom_12_1", k=3, rs_col="rs_6_0", bench_col="spy_6_0"),
 "T1_base": run(rank_col="mom_12_1", k=1),
 "T1_rs":   run(rank_col="mom_12_1", k=1, rs_col="rs_6_0", bench_col="spy_6_0"),
 "T1_sma":  run(rank_col="mom_12_1", k=1, sma200_mode="pass_down"),
}
pd.to_pickle(S, os.path.join(os.path.dirname(os.path.abspath(__file__)), "gemini_engine_series.pkl"))
spy = store.P["SPY"]; spy_m = (spy.shift(-1) / spy - 1)  # close-close monthly SPY, holding month index shift
rng = np.random.default_rng(1)
def block_boot(x, B=20000, L=6):
    n = len(x); out = np.empty(B)
    for b in range(B):
        idx = np.concatenate([np.arange(s, s + L) % n for s in rng.integers(0, n, n // L + 1)])[:n]
        out[b] = x[idx].sum()
    return out
for a, b in [("T3_rs", "T3_base"), ("T1_rs", "T1_base"), ("T1_sma", "T1_base")]:
    for start in ["2010", "2015"]:
        A = S[a].loc[start:"2026-09", "net"]; Bs = S[b].loc[start:"2026-09", "net"]
        lr = (np.log1p(A) - np.log1p(Bs)).values
        n = len(lr); ann = np.exp(lr.sum() * 12 / n) - 1
        srt = np.sort(lr)[::-1]
        ex2 = np.exp((lr.sum() - srt[:2].sum()) * 12 / n) - 1
        ex3 = np.exp((lr.sum() - srt[:3].sum()) * 12 / n) - 1
        diff = (np.abs(lr) > 1e-9).sum()
        bs = block_boot(lr)
        t = lr.mean() / (lr.std(ddof=1) / np.sqrt(n))
        print(f"{a} vs {b} {start}-2026: ann gain {ann*100:+.2f}%/yr | excl best 2 mo {ex2*100:+.2f} | excl best 3 {ex3*100:+.2f} | months differ {diff} | t={t:.2f} | block-boot P(gain<=0)={np.mean(bs<=0):.3f}")
