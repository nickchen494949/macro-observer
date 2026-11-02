import json, os, pandas as pd, numpy as np
S = os.path.dirname(os.path.abspath(__file__)) + "/"
D = "/Users/happygolucky/Desktop/宏观观察器/outputs/gemini_full_data_audit_20261031/v2_standalone/"
R = "/Users/happygolucky/Desktop/宏观观察器/research/sector_stock_momentum/data/"
P = pd.read_parquet(S + "claude_panel.parquet").set_index(["t", "ticker"])

def rawpx(tk, field, d):
    for sub in ("raw_open", "raw", "raw_tiingo", "raw_wiki"):
        p = f"{R}{sub}/{tk}.json"
        if os.path.exists(p):
            j = json.load(open(p))
            if field in j and j[field]:
                s = pd.Series(j[field], index=pd.to_datetime(j["dates"])).dropna()
                return s, sub
    return None, None

for f in ["v2_06_ledger_sp500_top1_sma200_oo.csv"]:
    L = pd.read_csv(D + f, parse_dates=["month"]).set_index("month")
    big = L.reindex(L["gross"].abs().sort_values(ascending=False).index).head(15)
    print(f"\nTop-15 |gross| months in {f}")
    for m, r in big.iterrows():
        t = pd.Timestamp(r["formation"]); tk = r["picks"]
        mine = P["roo"].get((t, tk), np.nan); mcc = P["rcc"].get((t, tk), np.nan)
        s, sub = rawpx(tk, "close", None)
        # raw unadjusted close move as split sanity
        print(f"  {m.date()} {tk:6s} gemini={r['gross']*100:8.2f}%  claude_open={mine*100 if np.isfinite(mine) else float('nan'):8.2f}%  claude_cc={mcc*100 if np.isfinite(mcc) else float('nan'):8.2f}%")
