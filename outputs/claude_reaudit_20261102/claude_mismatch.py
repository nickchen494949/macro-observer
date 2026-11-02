import pandas as pd, numpy as np, json, os
S = os.path.dirname(os.path.abspath(__file__)) + "/"
R = "/Users/happygolucky/Desktop/宏观观察器/research/sector_stock_momentum/data/"
P = pd.read_parquet(S + "claude_panel.parquet")
cases = [("2009-12-31", "XL", "EP"), ("2010-06-30", "TGNA", "GNW"), ("2010-08-31", "AIG", "EP"), ("2010-09-30", "TIE", "EP"),
         ("2011-08-31", "COG", "CMG"), ("2013-01-31", "S", "PHM"), ("2014-03-31", "FB", "FRX"), ("2015-08-31", "EA", "MNST"),
         ("2018-06-30", "HFC", "ABMD"), ("2019-07-31", "BLL", "CMG"), ("2021-06-30", "LB", "FCX"), ("2010-06-30", "SNDK", "WYNN")]
for t, g, c in cases:
    t = pd.Timestamp(t)
    x = P[(P.t == t) & (P.ticker.isin([g, c]))][["ticker", "src", "m121", "dist", "roo", "rcc"]]
    top = P[(P.t == t) & P.m121.notna() & (P.dist > 0)].sort_values("m121", ascending=False).head(3)[["ticker", "m121"]]
    print(t.date(), "gemini", g, "| claude", c); print(x.round(3).to_string(index=False)); print("  claude top3(>SMA):", list(zip(top.ticker, top.m121.round(3))))
    for sub in ("raw", "raw_tiingo", "raw_wiki", "raw_archive"):
        p = f"{R}{sub}/{g}.json"
        if os.path.exists(p):
            j = json.load(open(p)); print(f"   file {sub}/{g}.json {j['dates'][0]}..{j['dates'][-1]}")
# EP sanity
j = json.load(open(R + "raw/EP.json")); s = pd.Series(j["adjclose"], index=pd.to_datetime(j["dates"]))
print("EP raw adjclose around 2009-2010:", s["2009-11-25":"2010-01-05"].iloc[[0, -1]].round(2).to_dict(), s.index[0].date(), s.index[-1].date())
print(pd.read_csv(R + "identity_resolutions.csv").to_string())
# MRNA Aug-2026 gap
j = json.load(open(R + "raw_open/MRNA.json")); m = pd.DataFrame({k: j[k] for k in ["open", "close", "adj_open", "adjclose"]}, index=pd.to_datetime(j["dates"]))
print(m["2026-08-14":"2026-08-24"].round(2).to_string())
