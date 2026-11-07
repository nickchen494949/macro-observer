#!/usr/bin/env python3
"""
run_all_sectors_ranking_audit.py
================================
Comprehensive Ranking of All Sectors, Sub-Sectors, ETFs, and Within-Sector Stock Momentum:
  1. Official SPDR Sector ETFs (XLK, XLY, XLC, XLF, XLI, XLV, XLE, XLP, XLU, XLB, XLRE)
     + Benchmarks (QQQ, SPY, DIA) + Sector Rotation (12-1m Hold<=3 / Hard Top-1)
     + Extra Sub-Sector / Thematic ETFs (SOXX, IGV, IBB, KBE, KRE, XRT, GDX, ICLN, IWM, GLD, TLT, MAGS)
     across:
       - 2000-01 to 2026-10 (322m: Total Return adj_close vs Price Return raw_close)
       - 1999-01 to 2026-10 (334m: Full SPDR Sector ETF history since Dec 1998 launch)
       - 2009-01 to 2026-10 (214m: Post-GFC Modern Era)
       - 2018-07 to 2026-10 (100m: All 11 SPDR Sector ETFs incl. XLC & XLRE)
  2. All 11 S&P 500 GICS Sectors — Equal-Weight (EW) vs Within-Sector Stock Momentum
     (12-1m Top-1 Hard, 12-1m Top-1 Hold<=3, 12-1m Sharpe Top-2 Hold<=5, 10bp/side) across:
       - 2009-01 to 2026-10 (214m Strict PIT GICS & PIT S&P 500)
       - 2000-01 to 2026-10 (322m)
       - 1985-01 to 2026-10 (502m Full 41.8-Year History)
  3. High-Alpha Sub-Sectors & Super-Sectors Inside S&P 500 (2009-01 to 2026-10, 214m Strict PIT):
       - Semiconductors & Semi Equipment (GICS 4530: NVDA, AMD, AVGO, MU, LRCX, KLAC, AMAT, FSLR...)
       - Software & IT Services (GICS 4510: MSFT, ORCL, CRM, NOW, ADBE, PANW, PLTR, ANSS, SNPS...)
       - Tech Hardware, Storage & Networking (GICS 4520: AAPL, ANET, SNDK, WDC, STX, SMCI, DELL...)
       - True Tech + Platform Giants (IT + META, GOOGL, NFLX, AMZN, TSLA, V, MA, PYPL)
       - Biotech, Pharma & MedTech Growth (LLY, VRTX, REGN, MRNA, ISRG, DXCM, ALGN, GILD, AMGN...)
       - Aerospace & Defense (GE, RTX, LMT, NOC, GD, BA, HWM, TDG, AXON, LHX...)
       - Wall Street Capital Markets, Exchanges & FinTech (GS, MS, BLK, KKR, BX, SPGI, MCO, ICE, CME...)
       - Oil & Gas E&P + Refining (DVN, EQT, FANG, OXY, COP, EOG, MPC, VLO, PSX, HES, TPL...)
       - Consumer Retail, E-Commerce & Restaurants (AMZN, HD, LOW, ORLY, AZO, TJX, CMG, BKNG, MCD...)
"""
import os
import json
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
IN_DIR = os.path.join(ROOT, "outputs", "pure_momentum_1985_2026_audit", "inputs")
RAW_DIR = os.path.join(ROOT, "research", "sector_stock_momentum", "data", "raw")
YAHOO_DIR = os.path.join(ROOT, "data", "yahoo")
SEC_CSV = os.path.join(ROOT, "research", "sector_stock_momentum", "data", "sectors.csv")

COST_RATE = 0.0010  # 10 bp per one-way turnover


def eval_monthly(r_series, start_ym="1900-01", end_ym="2026-10"):
    sub = r_series[(r_series.index >= start_ym) & (r_series.index <= end_ym)].dropna()
    n = len(sub)
    if n == 0:
        return {
            "Months": 0,
            "Start": None,
            "End": None,
            "CAGR": np.nan,
            "Total_Multiple": np.nan,
            "Vol": np.nan,
            "Sharpe": np.nan,
            "MaxDD": np.nan,
            "WinRate": np.nan,
        }
    r_arr = sub.values.astype(float)
    eq = np.concatenate([[1.0], np.cumprod(1.0 + r_arr)])
    tot_mult = float(eq[-1])
    cagr = float(tot_mult ** (12.0 / n) - 1.0)
    vol = float(np.std(r_arr, ddof=1) * np.sqrt(12.0)) if n > 1 else np.nan
    sh = float((np.mean(r_arr) * 12.0) / vol) if (vol and vol > 0) else np.nan
    dd = float((eq / np.maximum.accumulate(eq) - 1.0).min())
    win = float(np.mean(r_arr > 0))
    return {
        "Months": n,
        "Start": sub.index[0],
        "End": sub.index[-1],
        "CAGR": cagr,
        "Total_Multiple": tot_mult,
        "Vol": vol,
        "Sharpe": sh,
        "MaxDD": dd,
        "WinRate": win,
    }


# =============================================================================
# PART 1: ETF Total Return vs Price Return & Sector Rotation (1999-2026)
# =============================================================================
etf_daily = pd.read_parquet(os.path.join(IN_DIR, "etfs_daily_total_return_adjclose.parquet"))
etf_daily["ym"] = etf_daily["date"].astype(str).str.slice(0, 7)

# Add XLC and XLRE from research/sector_stock_momentum/data/raw/*.json (which have adjclose and close)
extra_raw_rows = []
for tk in ["XLC", "XLRE"]:
    p = os.path.join(RAW_DIR, f"{tk}.json")
    if os.path.exists(p):
        d = json.load(open(p))
        df_tk = pd.DataFrame({
            "ticker": tk,
            "date": pd.Series(d["dates"]).astype(str).str.slice(0, 10),
            "raw_close": pd.to_numeric(d["close"], errors="coerce"),
            "adj_close": pd.to_numeric(d["adjclose"], errors="coerce"),
        }).dropna()
        df_tk["ym"] = df_tk["date"].str.slice(0, 7)
        extra_raw_rows.append(df_tk)

# Also load thematic/sub-sector ETFs from data/yahoo/*.json (note: Yahoo dashboard JSON stores daily close)
THEMATIC_ETFS = {
    "SOXX": "Semiconductors ETF (iShares)",
    "IGV": "Expanded Tech-Software ETF (iShares)",
    "IBB": "Biotechnology ETF (iShares)",
    "KBE": "SPDR S&P Bank ETF",
    "KRE": "SPDR S&P Regional Banking ETF",
    "XRT": "SPDR S&P Retail ETF",
    "ICLN": "Global Clean Energy ETF (iShares)",
    "GDX": "Gold Miners ETF (VanEck)",
    "IWM": "Russell 2000 Small-Cap ETF (iShares)",
    "GLD": "SPDR Gold Trust",
    "TLT": "20+ Year Treasury Bond ETF (iShares)",
    "IEF": "7-10 Year Treasury Bond ETF (iShares)",
    "MAGS": "Roundhill Magnificent Seven ETF",
}
yahoo_rows = []
for tk in THEMATIC_ETFS:
    p = os.path.join(YAHOO_DIR, f"{tk}.json")
    if os.path.exists(p):
        d = json.load(open(p))
        vals = d.get("values", [])
        if vals:
            df_y = pd.DataFrame(vals, columns=["date", "close"])
            df_y["ticker"] = tk
            df_y["raw_close"] = pd.to_numeric(df_y["close"], errors="coerce")
            df_y["adj_close"] = df_y["raw_close"]  # price series in dashboard yahoo cache
            df_y["ym"] = df_y["date"].astype(str).str.slice(0, 7)
            yahoo_rows.append(df_y[["ticker", "date", "raw_close", "adj_close", "ym"]].dropna())

etf_all_daily = pd.concat(
    [etf_daily[["ticker", "date", "raw_close", "adj_close", "ym"]]] + extra_raw_rows + yahoo_rows,
    ignore_index=True,
)
etf_all_daily = etf_all_daily.sort_values(["ticker", "date"])
etf_m = etf_all_daily.groupby(["ticker", "ym"], as_index=False).last()

px_adj = etf_m.pivot(index="ym", columns="ticker", values="adj_close").sort_index()
px_raw = etf_m.pivot(index="ym", columns="ticker", values="raw_close").sort_index()

ret_adj = px_adj.pct_change(fill_method=None)
ret_raw = px_raw.pct_change(fill_method=None)

SPDR_9 = ["XLK", "XLY", "XLI", "XLV", "XLF", "XLE", "XLP", "XLU", "XLB"]
SPDR_11 = SPDR_9 + ["XLRE", "XLC"]
SECTOR_LABELS = {
    "XLK": "Information Technology (XLK)",
    "XLY": "Consumer Discretionary (XLY)",
    "XLC": "Communication Services (XLC, 2018+)",
    "XLI": "Industrials (XLI)",
    "XLV": "Health Care (XLV)",
    "XLF": "Financials (XLF)",
    "XLE": "Energy (XLE)",
    "XLP": "Consumer Staples (XLP)",
    "XLU": "Utilities (XLU)",
    "XLB": "Materials (XLB)",
    "XLRE": "Real Estate (XLRE, 2015+)",
    "QQQ": "Nasdaq-100 (QQQ)",
    "SPY": "S&P 500 (SPY)",
    "DIA": "Dow Jones 30 (DIA)",
}

# Build Sector ETF Equal-Weight & Sector ETF Momentum Rotation (12-1m) on SPDR_9 and SPDR_11
def sim_etf_rotation(ret_df, px_df, cols, lookback=12, skip=1, top_n=1, hold_b=3):
    yms = sorted(ret_df.index)
    out = {}
    held = []
    prev_w = {}
    for i in range(lookback + 1, len(yms)):
        ym_hold = yms[i]
        ym_form = yms[i - 1]
        ym_end_mom = yms[i - 1 - skip]
        ym_start_mom = yms[i - 1 - lookback]
        avail = [
            c for c in cols
            if pd.notna(px_df.loc[ym_end_mom, c])
            and pd.notna(px_df.loc[ym_start_mom, c])
            and pd.notna(ret_df.loc[ym_hold, c])
        ]
        if len(avail) < top_n:
            continue
        scores = {c: float(px_df.loc[ym_end_mom, c] / px_df.loc[ym_start_mom, c] - 1.0) for c in avail}
        ranked = sorted(avail, key=lambda c: (-scores[c], c))
        rank_map = {c: idx + 1 for idx, c in enumerate(ranked)}
        kept = [c for c in held if c in rank_map and rank_map[c] <= hold_b][:top_n]
        for c in ranked:
            if len(kept) >= top_n:
                break
            if c not in kept:
                kept.append(c)
        held = kept
        w = {c: 1.0 / len(held) for c in held}
        gross = sum(w[c] * float(ret_df.loc[ym_hold, c]) for c in held)
        all_k = set(prev_w) | set(w)
        to = 0.5 * sum(abs(w.get(k, 0.0) - prev_w.get(k, 0.0)) for k in all_k) if prev_w else 1.0
        out[ym_hold] = gross - to * 2.0 * COST_RATE
        prev_w = {c: w[c] * (1.0 + float(ret_df.loc[ym_hold, c])) / (1.0 + gross) for c in held}
    return pd.Series(out)


def sim_etf_ew(ret_df, cols):
    yms = sorted(ret_df.index)
    out = {}
    prev_w = {}
    for ym in yms:
        avail = [c for c in cols if pd.notna(ret_df.loc[ym, c])]
        if not avail:
            continue
        w = {c: 1.0 / len(avail) for c in avail}
        gross = sum(w[c] * float(ret_df.loc[ym, c]) for c in avail)
        all_k = set(prev_w) | set(w)
        to = 0.5 * sum(abs(w.get(k, 0.0) - prev_w.get(k, 0.0)) for k in all_k) if prev_w else 1.0
        out[ym] = gross - to * 2.0 * COST_RATE
        prev_w = {c: w[c] * (1.0 + float(ret_df.loc[ym, c])) / (1.0 + gross) for c in avail}
    return pd.Series(out)


rot_9_top1_h3 = sim_etf_rotation(ret_adj, px_adj, SPDR_9, 12, 1, 1, 3)
rot_9_top1_h1 = sim_etf_rotation(ret_adj, px_adj, SPDR_9, 12, 1, 1, 1)
rot_9_top2_h4 = sim_etf_rotation(ret_adj, px_adj, SPDR_9, 12, 1, 2, 4)
rot_11_top1_h3 = sim_etf_rotation(ret_adj, px_adj, SPDR_11, 12, 1, 1, 3)
ew_9_etf = sim_etf_ew(ret_adj, SPDR_9)
ew_11_etf = sim_etf_ew(ret_adj, SPDR_11)

etf_rows = []
# 1) All 9 SPDR Sector ETFs + 2 New SPDR Sector ETFs + 3 Index ETFs
for tk in SPDR_11 + ["QQQ", "SPY", "DIA"]:
    if tk not in ret_adj.columns:
        continue
    m_99 = eval_monthly(ret_adj[tk], "1999-01", "2026-10")
    m_00_tr = eval_monthly(ret_adj[tk], "2000-01", "2026-10")
    m_00_pr = eval_monthly(ret_raw[tk], "2000-01", "2026-10")
    m_09_tr = eval_monthly(ret_adj[tk], "2009-01", "2026-10")
    m_18_tr = eval_monthly(ret_adj[tk], "2018-07", "2026-10")
    etf_rows.append({
        "Category": "SPDR_Sector_ETF" if tk.startswith("XL") else "Market_Index_ETF",
        "Ticker": tk,
        "Name": SECTOR_LABELS.get(tk, tk),
        "Return_Type": "Total_Return_AdjClose",
        "Full_1999_2026_CAGR": m_99["CAGR"],
        "Full_1999_2026_Sharpe": m_99["Sharpe"],
        "W2000_2026_Months": m_00_tr["Months"],
        "W2000_2026_TR_CAGR": m_00_tr["CAGR"],
        "W2000_2026_TR_Multiple": m_00_tr["Total_Multiple"],
        "W2000_2026_Price_CAGR": m_00_pr["CAGR"],
        "Dividend_Boost_pp": (m_00_tr["CAGR"] - m_00_pr["CAGR"]) if pd.notna(m_00_tr["CAGR"]) else np.nan,
        "W2000_2026_Vol": m_00_tr["Vol"],
        "W2000_2026_Sharpe": m_00_tr["Sharpe"],
        "W2000_2026_MaxDD": m_00_tr["MaxDD"],
        "W2009_2026_TR_CAGR": m_09_tr["CAGR"],
        "W2009_2026_Sharpe": m_09_tr["Sharpe"],
        "W2009_2026_MaxDD": m_09_tr["MaxDD"],
        "W2018_2026_TR_CAGR": m_18_tr["CAGR"],
        "W2018_2026_Sharpe": m_18_tr["Sharpe"],
    })

# Add Sector Rotation & Equal Weight rows
for tk, label, ser in [
    ("Rot9_12_1_Top1_H3", "9-Sector Rotation (12-1m Top-1, Hold<=3, 10bp)", rot_9_top1_h3),
    ("Rot9_12_1_Top1_Hard", "9-Sector Rotation (12-1m Top-1 Hard, 10bp)", rot_9_top1_h1),
    ("Rot9_12_1_Top2_H4", "9-Sector Rotation (12-1m Top-2, Hold<=4, 10bp)", rot_9_top2_h4),
    ("Rot11_12_1_Top1_H3", "11-Sector Rotation incl. XLRE/XLC (12-1m Top-1, Hold<=3, 10bp)", rot_11_top1_h3),
    ("EW_9_SPDR_ETFs", "Equal-Weight 9 SPDR Sector ETFs (10bp)", ew_9_etf),
    ("EW_11_SPDR_ETFs", "Equal-Weight 11 SPDR Sector ETFs (10bp)", ew_11_etf),
]:
    m_99 = eval_monthly(ser, "1999-01", "2026-10")
    m_00 = eval_monthly(ser, "2000-01", "2026-10")
    m_09 = eval_monthly(ser, "2009-01", "2026-10")
    m_18 = eval_monthly(ser, "2018-07", "2026-10")
    etf_rows.append({
        "Category": "Sector_ETF_Strategy",
        "Ticker": tk,
        "Name": label,
        "Return_Type": "Total_Return_Net_10bp",
        "Full_1999_2026_CAGR": m_99["CAGR"],
        "Full_1999_2026_Sharpe": m_99["Sharpe"],
        "W2000_2026_Months": m_00["Months"],
        "W2000_2026_TR_CAGR": m_00["CAGR"],
        "W2000_2026_TR_Multiple": m_00["Total_Multiple"],
        "W2000_2026_Price_CAGR": np.nan,
        "Dividend_Boost_pp": np.nan,
        "W2000_2026_Vol": m_00["Vol"],
        "W2000_2026_Sharpe": m_00["Sharpe"],
        "W2000_2026_MaxDD": m_00["MaxDD"],
        "W2009_2026_TR_CAGR": m_09["CAGR"],
        "W2009_2026_Sharpe": m_09["Sharpe"],
        "W2018_2026_TR_CAGR": m_18["CAGR"],
        "W2018_2026_Sharpe": m_18["Sharpe"],
        "W2009_2026_MaxDD": m_09["MaxDD"],
    })

# Add Thematic / Sub-Sector ETFs
for tk, desc in THEMATIC_ETFS.items():
    if tk not in ret_adj.columns:
        continue
    m_all = eval_monthly(ret_adj[tk], "1999-01", "2026-10")
    m_09 = eval_monthly(ret_adj[tk], "2009-01", "2026-10")
    m_18 = eval_monthly(ret_adj[tk], "2018-07", "2026-10")
    etf_rows.append({
        "Category": "SubSector_Thematic_ETF",
        "Ticker": tk,
        "Name": f"{desc} (since {m_all['Start']})",
        "Return_Type": "Price_Close_Yahoo",
        "Full_1999_2026_CAGR": m_all["CAGR"],
        "Full_1999_2026_Sharpe": m_all["Sharpe"],
        "W2000_2026_Months": m_all["Months"],
        "W2000_2026_TR_CAGR": m_all["CAGR"],
        "W2000_2026_TR_Multiple": m_all["Total_Multiple"],
        "W2000_2026_Price_CAGR": m_all["CAGR"],
        "Dividend_Boost_pp": 0.0,
        "W2000_2026_Vol": m_all["Vol"],
        "W2000_2026_Sharpe": m_all["Sharpe"],
        "W2000_2026_MaxDD": m_all["MaxDD"],
        "W2009_2026_TR_CAGR": m_09["CAGR"],
        "W2009_2026_Sharpe": m_09["Sharpe"],
        "W2009_2026_MaxDD": m_09["MaxDD"],
        "W2018_2026_TR_CAGR": m_18["CAGR"],
        "W2018_2026_Sharpe": m_18["Sharpe"],
    })

df_etf_rank = pd.DataFrame(etf_rows)
df_etf_rank.to_csv(os.path.join(HERE, "01_etf_sectors_and_thematics_buy_and_hold_ranking.csv"), index=False)


# =============================================================================
# PART 2: All 11 S&P 500 GICS Sectors — EW vs Within-Sector Stock Momentum
#         Across 1985-2026 (502m), 2000-2026 (322m), and 2009-2026 (214m Strict PIT)
# =============================================================================
panel_all = pd.read_parquet(os.path.join(IN_DIR, "panel_1985_2026_monthly.parquet"))
# Unify "Telecommunication Services" (pre-2018-09) and "Communication Services" (2018-09+)
panel_all["gics_11"] = panel_all["clean_sector"].replace({
    "Telecommunication Services": "Communication Services (incl. pre-2018 Telecom)"
})
panel_all["gics_11"] = panel_all["gics_11"].replace({
    "Communication Services": "Communication Services (incl. pre-2018 Telecom)"
})

GICS_11_LIST = [
    "Information Technology",
    "Consumer Discretionary",
    "Communication Services (incl. pre-2018 Telecom)",
    "Health Care",
    "Industrials",
    "Financials",
    "Energy",
    "Materials",
    "Consumer Staples",
    "Utilities",
    "Real Estate",
]


def sim_pool_momentum(df_pool, col_score="mom_12_1", top_n=1, hold_b=1, ret_col="fwd_ret_stress"):
    out = {}
    held = []
    prev_w = {}
    for ym, g in df_pool.groupby("hold_ym", sort=True):
        g_valid = g[g[col_score].notna() & g[ret_col].notna()].sort_values(
            [col_score, "ticker"], ascending=[False, True]
        )
        if len(g_valid) == 0:
            continue
        ranked = g_valid["ticker"].tolist()
        ret_map = dict(zip(g_valid["ticker"], g_valid[ret_col].astype(float)))
        rank_map = {tk: i + 1 for i, tk in enumerate(ranked)}
        kept = [tk for tk in held if tk in rank_map and rank_map[tk] <= hold_b][:top_n]
        for tk in ranked:
            if len(kept) >= top_n:
                break
            if tk not in kept:
                kept.append(tk)
        held = kept
        w = {tk: 1.0 / len(held) for tk in held}
        gross = sum(w[tk] * ret_map[tk] for tk in held)
        all_k = set(prev_w) | set(w)
        to = 0.5 * sum(abs(w.get(k, 0.0) - prev_w.get(k, 0.0)) for k in all_k) if prev_w else 1.0
        out[ym] = gross - to * 2.0 * COST_RATE
        prev_w = {tk: w[tk] * (1.0 + ret_map[tk]) / max(1.0 + gross, 1e-6) for tk in held}
    return pd.Series(out)


def sim_pool_ew(df_pool, ret_col="fwd_ret_stress"):
    out = {}
    prev_w = {}
    for ym, g in df_pool.groupby("hold_ym", sort=True):
        g_valid = g[g[ret_col].notna()]
        if len(g_valid) == 0:
            continue
        tks = g_valid["ticker"].tolist()
        ret_map = dict(zip(tks, g_valid[ret_col].astype(float)))
        w = {tk: 1.0 / len(tks) for tk in tks}
        gross = sum(w[tk] * ret_map[tk] for tk in tks)
        all_k = set(prev_w) | set(w)
        to = 0.5 * sum(abs(w.get(k, 0.0) - prev_w.get(k, 0.0)) for k in all_k) if prev_w else 1.0
        out[ym] = gross - to * 2.0 * COST_RATE
        prev_w = {tk: w[tk] * (1.0 + ret_map[tk]) / max(1.0 + gross, 1e-6) for tk in tks}
    return pd.Series(out)


gics_rows = []
for sec in GICS_11_LIST:
    sub_df = panel_all[panel_all["gics_11"] == sec]
    s_ew = sim_pool_ew(sub_df)
    s_top1_h1 = sim_pool_momentum(sub_df, "mom_12_1", 1, 1)
    s_top1_h3 = sim_pool_momentum(sub_df, "mom_12_1", 1, 3)
    s_sh_top2_h5 = sim_pool_momentum(sub_df, "sharpe_12_1", 2, 5)

    for w_label, start_ym in [
        ("2009_2026_Strict_PIT_214m", "2009-01"),
        ("2000_2026_322m", "2000-01"),
        ("1985_2026_Full_502m", "1985-01"),
    ]:
        m_ew = eval_monthly(s_ew, start_ym, "2026-10")
        m_h1 = eval_monthly(s_top1_h1, start_ym, "2026-10")
        m_h3 = eval_monthly(s_top1_h3, start_ym, "2026-10")
        m_sh = eval_monthly(s_sh_top2_h5, start_ym, "2026-10")
        avg_n = float(sub_df[sub_df["hold_ym"] >= start_ym].groupby("hold_ym")["ticker"].count().mean())
        gics_rows.append({
            "Window": w_label,
            "GICS_Sector": sec,
            "Months": m_ew["Months"],
            "Avg_Stocks_Per_Month": avg_n,
            "Sector_EW_CAGR": m_ew["CAGR"],
            "Sector_EW_Sharpe": m_ew["Sharpe"],
            "Sector_EW_MaxDD": m_ew["MaxDD"],
            "Top1_Hard_CAGR": m_h1["CAGR"],
            "Top1_Hard_Sharpe": m_h1["Sharpe"],
            "Top1_Hard_MaxDD": m_h1["MaxDD"],
            "Top1_Hold3_CAGR": m_h3["CAGR"],
            "Top1_Hold3_Sharpe": m_h3["Sharpe"],
            "Top1_Hold3_MaxDD": m_h3["MaxDD"],
            "Sharpe_Top2_Hold5_CAGR": m_sh["CAGR"],
            "Sharpe_Top2_Hold5_Sharpe": m_sh["Sharpe"],
            "Sharpe_Top2_Hold5_MaxDD": m_sh["MaxDD"],
        })

df_gics_rank = pd.DataFrame(gics_rows)
df_gics_rank.to_csv(os.path.join(HERE, "02_sp500_11_gics_sectors_ew_and_top1_stock_momentum.csv"), index=False)


# =============================================================================
# PART 3: High-Alpha Sub-Sectors & Super-Sectors Inside S&P 500 (2009-2026 Strict PIT)
# =============================================================================
p_spx = pd.read_parquet(os.path.join(IN_DIR, "v3_spx_panel_214m.parquet"))
p_spx["t"] = pd.to_datetime(p_spx["t"])
p_spx = p_spx[p_spx["t"] <= pd.Timestamp("2026-09-30")].copy()
p_spx["hold_ym"] = (p_spx["t"] + pd.DateOffset(months=1)).dt.strftime("%Y-%m")
p_spx["mom_12_1"] = p_spx["mom"]
p_spx["sharpe_12_1"] = p_spx["sharpe"]
p_spx["fwd_ret_stress"] = np.where(
    p_spx["hold_ret"].notna(),
    p_spx["hold_ret"],
    np.where(p_spx["ret_flag"].astype(str).str.contains("delist|missing", case=False), -0.30, 0.0),
)

sec_csv_df = pd.read_csv(SEC_CSV)
ind_map = dict(zip(sec_csv_df["ticker"], sec_csv_df["industry"].fillna("")))
p_spx["sub_industry"] = p_spx["ticker"].map(ind_map).fillna("")

PLATFORM_GIANTS = {"META", "FB", "GOOGL", "GOOG", "NFLX", "AMZN", "TSLA", "V", "MA", "PYPL", "SQ", "XYZ", "UBER", "ABNB", "DASH", "EBAY", "BKNG", "PCLN", "EXPE", "TRIP", "EA", "ATVI", "TTWO"}

SUBSECTOR_DEFS = [
    (
        "1. Semiconductors & Semi Equipment (GICS 4530)",
        lambda d: d["gics_4digit_group"] == "4530_Semiconductors_and_Equipment",
    ),
    (
        "2. Software & IT Services (GICS 4510)",
        lambda d: d["gics_4digit_group"] == "4510_Software_and_Services",
    ),
    (
        "3. Tech Hardware, Storage & Networking (GICS 4520)",
        lambda d: d["gics_4digit_group"] == "4520_Tech_Hardware_and_Equipment",
    ),
    (
        "4. Official GICS Information Technology (4510+4520+4530)",
        lambda d: d["clean_sector"] == "Information Technology",
    ),
    (
        "5. Super-Tech: IT + Platform/Fintech Giants (META/GOOGL/NFLX/AMZN/TSLA/V/MA/PYPL...)",
        lambda d: (d["clean_sector"] == "Information Technology") | d["ticker"].isin(PLATFORM_GIANTS),
    ),
    (
        "6. Semi + Storage/Networking Hardware Only (4530 + 4520, Ex-Software)",
        lambda d: d["gics_4digit_group"].isin(["4530_Semiconductors_and_Equipment", "4520_Tech_Hardware_and_Equipment"]),
    ),
    (
        "7. Biotech, Pharma & MedTech Growth (Health Care Innovation)",
        lambda d: (d["clean_sector"] == "Health Care") & d["sub_industry"].str.contains(
            "Biotechnology|Pharmaceuticals|Life Sciences|Health Care Equipment|Health Care Supplies", case=False, na=False
        ),
    ),
    (
        "8. Aerospace & Defense (Industrials Defense Core)",
        lambda d: (d["clean_sector"] == "Industrials") & d["sub_industry"].str.contains(
            "Aerospace & Defense", case=False, na=False
        ),
    ),
    (
        "9. Capital Markets, Exchanges & FinTech (Financials High-Beta)",
        lambda d: (d["clean_sector"] == "Financials") & d["sub_industry"].str.contains(
            "Asset Management|Investment Banking|Financial Exchanges|Transaction & Payment|Consumer Finance", case=False, na=False
        ),
    ),
    (
        "10. Oil & Gas E&P + Refining (Energy Cyclical Core)",
        lambda d: (d["clean_sector"] == "Energy") & d["sub_industry"].str.contains(
            "Exploration & Production|Refining & Marketing|Integrated Oil & Gas|Drilling|Equipment & Services", case=False, na=False
        ),
    ),
    (
        "11. Consumer Retail, E-Commerce, Homebuilders & Restaurants",
        lambda d: (d["clean_sector"] == "Consumer Discretionary") & d["sub_industry"].str.contains(
            "Retail|Restaurants|Homebuilding|Home Improvement|Hotels, Resorts|Internet & Direct Marketing|Broadline", case=False, na=False
        ),
    ),
]

sub_rows = []
for name, cond_fn in SUBSECTOR_DEFS:
    sub_d = p_spx[cond_fn(p_spx)]
    s_ew = sim_pool_ew(sub_d)
    s_h1 = sim_pool_momentum(sub_d, "mom_12_1", 1, 1)
    s_h3 = sim_pool_momentum(sub_d, "mom_12_1", 1, 3)
    s_sh = sim_pool_momentum(sub_d, "sharpe_12_1", 2, 5)

    m_ew = eval_monthly(s_ew, "2009-01", "2026-10")
    m_h1 = eval_monthly(s_h1, "2009-01", "2026-10")
    m_h3 = eval_monthly(s_h3, "2009-01", "2026-10")
    m_sh = eval_monthly(s_sh, "2009-01", "2026-10")
    avg_n = float(sub_d.groupby("hold_ym")["ticker"].count().mean())

    sub_rows.append({
        "SubSector_Pool": name,
        "Months": m_ew["Months"],
        "Avg_Stocks": avg_n,
        "Pool_EW_CAGR": m_ew["CAGR"],
        "Pool_EW_Sharpe": m_ew["Sharpe"],
        "Pool_EW_MaxDD": m_ew["MaxDD"],
        "Top1_Hard_CAGR": m_h1["CAGR"],
        "Top1_Hard_Sharpe": m_h1["Sharpe"],
        "Top1_Hard_MaxDD": m_h1["MaxDD"],
        "Top1_Hold3_CAGR": m_h3["CAGR"],
        "Top1_Hold3_Sharpe": m_h3["Sharpe"],
        "Top1_Hold3_MaxDD": m_h3["MaxDD"],
        "Sharpe_Top2_Hold5_CAGR": m_sh["CAGR"],
        "Sharpe_Top2_Hold5_Sharpe": m_sh["Sharpe"],
        "Sharpe_Top2_Hold5_MaxDD": m_sh["MaxDD"],
    })

df_sub_rank = pd.DataFrame(sub_rows)
df_sub_rank.to_csv(os.path.join(HERE, "03_subsectors_and_super_sectors_constituent_momentum_2009_2026.csv"), index=False)

print("=== 1. SPDR SECTOR ETFs & BENCHMARKS (2000-01 to 2026-10 Total Return Ranked) ===")
spdr_sub = df_etf_rank[df_etf_rank["Category"].isin(["SPDR_Sector_ETF", "Market_Index_ETF", "Sector_ETF_Strategy"])].sort_values(
    "W2000_2026_TR_CAGR", ascending=False
)
for _, r in spdr_sub.iterrows():
    print(
        f"  {r['Ticker']:20s} | 2000-26 TR: {r['W2000_2026_TR_CAGR']*100:6.2f}% (Sh {r['W2000_2026_Sharpe']:5.3f}, DD {r['W2000_2026_MaxDD']*100:6.2f}%) "
        f"| 1999-26 TR: {(r['Full_1999_2026_CAGR']*100 if pd.notna(r['Full_1999_2026_CAGR']) else 0):6.2f}% "
        f"| 2009-26 TR: {r['W2009_2026_TR_CAGR']*100:6.2f}% (Sh {r['W2009_2026_Sharpe']:5.3f}) "
        f"| 2018-26 TR: {r['W2018_2026_TR_CAGR']*100:6.2f}%"
    )

print("\n=== 2. THEMATIC / SUB-SECTOR ETFs ===")
th_sub = df_etf_rank[df_etf_rank["Category"] == "SubSector_Thematic_ETF"].sort_values("W2009_2026_TR_CAGR", ascending=False)
for _, r in th_sub.iterrows():
    print(
        f"  {r['Ticker']:6s} ({r['Name']:45s}) | Full: {r['W2000_2026_TR_CAGR']*100:6.2f}% ({int(r['W2000_2026_Months'])}m) "
        f"| 2009-26: {(r['W2009_2026_TR_CAGR']*100 if pd.notna(r['W2009_2026_TR_CAGR']) else 0):6.2f}% (Sh {(r['W2009_2026_Sharpe'] if pd.notna(r['W2009_2026_Sharpe']) else 0):5.3f}) "
        f"| 2018-26: {r['W2018_2026_TR_CAGR']*100:6.2f}%"
    )

print("\n=== 3. ALL 11 GICS SECTORS (2009-2026 Strict PIT: EW vs Within-Sector Top-1) ===")
g09 = df_gics_rank[df_gics_rank["Window"] == "2009_2026_Strict_PIT_214m"].sort_values("Top1_Hard_CAGR", ascending=False)
for _, r in g09.iterrows():
    print(
        f"  {r['GICS_Sector']:48s} | EW: {r['Sector_EW_CAGR']*100:6.2f}% (Sh {r['Sector_EW_Sharpe']:5.3f}) "
        f"| Top1 Hard: {r['Top1_Hard_CAGR']*100:6.2f}% (Sh {r['Top1_Hard_Sharpe']:5.3f}) "
        f"| Top1 H3: {r['Top1_Hold3_CAGR']*100:6.2f}% (Sh {r['Top1_Hold3_Sharpe']:5.3f}) "
        f"| Sharpe Top2 H5: {r['Sharpe_Top2_Hold5_CAGR']*100:6.2f}% (Sh {r['Sharpe_Top2_Hold5_Sharpe']:5.3f})"
    )

print("\n=== 4. ALL 11 GICS SECTORS (1985-2026 Full 502m: EW vs Within-Sector Top-1) ===")
g85 = df_gics_rank[df_gics_rank["Window"] == "1985_2026_Full_502m"].sort_values("Top1_Hold3_CAGR", ascending=False)
for _, r in g85.iterrows():
    print(
        f"  {r['GICS_Sector']:48s} | EW: {r['Sector_EW_CAGR']*100:6.2f}% (Sh {r['Sector_EW_Sharpe']:5.3f}) "
        f"| Top1 Hard: {r['Top1_Hard_CAGR']*100:6.2f}% (Sh {r['Top1_Hard_Sharpe']:5.3f}) "
        f"| Top1 H3: {r['Top1_Hold3_CAGR']*100:6.2f}% (Sh {r['Top1_Hold3_Sharpe']:5.3f}) "
        f"| Sharpe Top2 H5: {r['Sharpe_Top2_Hold5_CAGR']*100:6.2f}% (Sh {r['Sharpe_Top2_Hold5_Sharpe']:5.3f})"
    )

print("\n=== 5. HIGH-ALPHA SUB-SECTORS & SUPER-SECTORS (2009-2026 Strict PIT) ===")
for _, r in df_sub_rank.sort_values("Top1_Hard_CAGR", ascending=False).iterrows():
    print(
        f"  {r['SubSector_Pool']:78s} | AvgN: {r['Avg_Stocks']:4.1f} | EW: {r['Pool_EW_CAGR']*100:6.2f}% (Sh {r['Pool_EW_Sharpe']:5.3f}) "
        f"| Top1 Hard: {r['Top1_Hard_CAGR']*100:6.2f}% (Sh {r['Top1_Hard_Sharpe']:5.3f}) "
        f"| Top1 H3: {r['Top1_Hold3_CAGR']*100:6.2f}% (Sh {r['Top1_Hold3_Sharpe']:5.3f}) "
        f"| Sharpe Top2 H5: {r['Sharpe_Top2_Hold5_CAGR']*100:6.2f}% (Sh {r['Sharpe_Top2_Hold5_Sharpe']:5.3f})"
    )
