#!/usr/bin/env python3
"""
Empirical Audit of Market Breadth Divergence ("Few Leaders Propping Up the Index While Many Constituents Break Below MAs")
===========================================================================================================================
Tests two core questions on 100% Point-in-Time (PIT) Nasdaq-100 (QQQ) daily constituents (2010-02-11 .. 2026-11-03):
1. Is the statement empirically true?
   - Construct exact daily PIT Nasdaq-100 constituent breadth:
     * Breadth_20  = % of active PIT NDX constituents with Close > SMA20
     * Breadth_50  = % of active PIT NDX constituents with Close > SMA50
     * Breadth_100 = % of active PIT NDX constituents with Close > SMA100
     * Breadth_200 = % of active PIT NDX constituents with Close > SMA200
     * EW_vs_CW_20d / 60d = PIT Equal-Weight NDX return minus Cap-Weight QQQ return over 20 / 60 trading days
   - Event study across all 9 major QQQ peaks (2010-2026) and regime conditional forward returns / drawdown probabilities
     when QQQ is near a high (within 3% of 60d high or > SMA50) while Breadth_50 < 50% / 45% / 40%.
   - False Positive vs True Positive analysis: how often does narrow leadership lead to a real top (>10% DD within 40d)
     vs a continued bull market rally?
2. Can it help our V1-Daily TQQQ SEP strategy (and 75/25 TQQQ+SOXL) escape tops and improve CAGR / MaxDD / Sharpe?
   - Evaluated on the fully remediated R3 engine (return-chained BIL->SGOV cash, 2-sided 20bp cash fees, next-day open execution).
"""

import os
import glob
import json
import yaml
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "research", "sector_stock_momentum", "data")
INP = os.path.join(ROOT, "outputs", "pure_momentum_1985_2026_audit", "inputs")
ETF_DIR = os.path.join(ROOT, "outputs", "remediation_full_audit_20261104", "tiingo_etfs")
TIINGO_ROWS_DIRS = [
    os.path.join(ROOT, "outputs", "qqq_mom_top3_claude_audit_20261103", "tiingo"),
    os.path.join(ROOT, "outputs", "tech_top1_independent_audit_20261103", "tiingo"),
]
OUT_DIR = os.path.join(ROOT, "outputs", "soxl_and_vol_estimators_audit_20261126")
os.makedirs(OUT_DIR, exist_ok=True)

FEE = 0.0010  # 10bp per side


def load_etf(sym):
    p = os.path.join(ETF_DIR, f"{sym}.json")
    df = pd.DataFrame(json.load(open(p)))
    df["date"] = pd.to_datetime(df["date"].str[:10])
    df = df.set_index("date").sort_index()
    df = df[~df.index.duplicated(keep="last")]
    return df[["adjOpen", "adjHigh", "adjLow", "adjClose"]].astype(float)


def _frame_close(dates, close):
    idx = pd.to_datetime(pd.Series(list(dates)).astype(str).str[:10])
    s = pd.Series(pd.to_numeric(pd.Series(list(close)), errors="coerce").values, index=idx.values)
    s = s[~s.index.duplicated(keep="last")].sort_index()
    s = s[s > 0]
    return s if len(s) else None


def load_stock_close(src, sym, wiki_dict):
    try:
        if src == "yahoo":
            for sub in ("raw_open", "raw"):
                p = os.path.join(DATA, sub, f"{sym}.json")
                if os.path.exists(p):
                    j = json.load(open(p))
                    return _frame_close(j["dates"], j["adjclose"])
        elif src == "tiingo":
            for d in TIINGO_ROWS_DIRS:
                p = os.path.join(d, f"{sym}.json")
                if os.path.exists(p):
                    r = pd.DataFrame(json.load(open(p))["rows"])
                    return _frame_close(r["date"], r["adjClose"])
            p = os.path.join(DATA, "raw_tiingo", f"{sym}.json")
            if os.path.exists(p):
                j = json.load(open(p))
                return _frame_close(j["dates"], j["adjclose"])
        elif src in ("archive", "raw_ndx"):
            p = os.path.join(DATA, "raw_archive" if src == "archive" else "raw_ndx", f"{sym}.json")
            if os.path.exists(p):
                j = json.load(open(p))
                return _frame_close(j["dates"], j["adjclose"])
        elif src == "wiki":
            g = wiki_dict.get(sym)
            if g is not None:
                return _frame_close(g["date"], g["adj_close"])
    except Exception:
        return None
    return None


print("1. Loading ETFs and Point-in-Time Nasdaq-100 constituent daily prices...")
qqq = load_etf("QQQ")
tqqq = load_etf("TQQQ")
bil = load_etf("BIL")
sgov = load_etf("SGOV")

# Build return-chained cash series (R2 remediated)
cal = qqq.index[(qqq.index >= pd.Timestamp("2008-01-02")) & (qqq.index <= pd.Timestamp("2026-11-03"))]
qqq = qqq.reindex(cal)

P_NDX = pd.read_parquet(os.path.join(INP, "v3_ndx_panel_214m.parquet"))
P_NDX["t"] = pd.to_datetime(P_NDX["t"])

# Map each ticker -> (src, sym) by month t, plus fallback latest valid (src, sym)
tk_src_map = {}
for r in P_NDX.itertuples(index=False):
    if isinstance(r.src, str) and isinstance(r.sym, str):
        tk_src_map[(r.t.year, r.t.month, r.ticker)] = (r.src, r.sym)
        if r.ticker not in tk_src_map:
            tk_src_map[r.ticker] = (r.src, r.sym)

unique_pairs = set(v for k, v in tk_src_map.items() if isinstance(k, tuple))
need_wiki = any(src == "wiki" for src, _ in unique_pairs)
wiki_dict = {}
if need_wiki:
    w = pd.read_parquet(os.path.join(DATA, "wiki_bulk", "wiki_prices.parquet"), columns=["ticker", "date", "adj_close"])
    wiki_dict = {k: g for k, g in w.groupby("ticker")}

pair_series = {}
for src, sym in sorted(unique_pairs):
    s = load_stock_close(src, sym, wiki_dict)
    if s is not None:
        pair_series[(src, sym)] = s.reindex(cal).ffill(limit=5)

# Precompute SMA20, SMA50, SMA100, SMA200 and daily return for every pair_series
pair_above20 = {}
pair_above50 = {}
pair_above100 = {}
pair_above200 = {}
pair_ret1d = {}

for pair, s in pair_series.items():
    sma20 = s.rolling(20, min_periods=20).mean()
    sma50 = s.rolling(50, min_periods=50).mean()
    sma100 = s.rolling(100, min_periods=100).mean()
    sma200 = s.rolling(200, min_periods=200).mean()
    pair_above20[pair] = (s > sma20).where(sma20.notna())
    pair_above50[pair] = (s > sma50).where(sma50.notna())
    pair_above100[pair] = (s > sma100).where(sma100.notna())
    pair_above200[pair] = (s > sma200).where(sma200.notna())
    pair_ret1d[pair] = s.pct_change()

# Build daily PIT Nasdaq-100 membership from n100-ticker-changes-*.yaml
ndx_years = {}
for f in sorted(glob.glob(os.path.join(DATA, "nasdaq100_src", "n100-ticker-changes-*.yaml"))):
    d = yaml.load(open(f), Loader=yaml.BaseLoader)
    ch = [
        (pd.Timestamp(str(k)), set((v or {}).get("union") or []), set((v or {}).get("difference") or []))
        for k, v in (d.get("changes") or {}).items()
    ]
    ndx_years[int(d["year"])] = (set(d["tickers_on_Jan_1"]), sorted(ch, key=lambda x: x[0]))

print("2. Computing exact daily PIT Nasdaq-100 Breadth (% > SMA20/50/100/200) and Equal-Weight NDX...")
b20_list, b50_list, b100_list, b200_list, ew_ret_list, n_valid_list = [], [], [], [], [], []

for dt in cal:
    y = min(dt.year, max(ndx_years))
    s_mem, ch = ndx_years[y]
    s_mem = set(s_mem)
    for c_dt, add, rem in ch:
        if c_dt <= dt:
            s_mem = (s_mem - rem) | add

    v20, v50, v100, v200, vret = [], [], [], [], []
    for tk in s_mem:
        pair = tk_src_map.get((dt.year, dt.month, tk), tk_src_map.get(tk))
        if pair is None or pair not in pair_series:
            continue
        a20 = pair_above20[pair].at[dt]
        a50 = pair_above50[pair].at[dt]
        a100 = pair_above100[pair].at[dt]
        a200 = pair_above200[pair].at[dt]
        r1 = pair_ret1d[pair].at[dt]
        if pd.notna(a20):
            v20.append(float(a20))
        if pd.notna(a50):
            v50.append(float(a50))
        if pd.notna(a100):
            v100.append(float(a100))
        if pd.notna(a200):
            v200.append(float(a200))
        if pd.notna(r1) and abs(r1) < 0.8:
            vret.append(float(r1))

    b20_list.append(np.mean(v20) if v20 else np.nan)
    b50_list.append(np.mean(v50) if v50 else np.nan)
    b100_list.append(np.mean(v100) if v100 else np.nan)
    b200_list.append(np.mean(v200) if v200 else np.nan)
    ew_ret_list.append(np.mean(vret) if vret else 0.0)
    n_valid_list.append(len(v50))

bdf = pd.DataFrame({
    "qqq_close": qqq["adjClose"],
    "qqq_open": qqq["adjOpen"],
    "qqq_ret": qqq["adjClose"].pct_change(),
    "ew_ret": ew_ret_list,
    "b20": b20_list,
    "b50": b50_list,
    "b100": b100_list,
    "b200": b200_list,
    "n_valid": n_valid_list,
}, index=cal)

bdf["ew_nav"] = (1.0 + bdf["ew_ret"]).cumprod()
bdf["qqq_sma50"] = bdf["qqq_close"].rolling(50).mean()
bdf["qqq_sma200"] = bdf["qqq_close"].rolling(200).mean()
bdf["qqq_high60"] = bdf["qqq_close"].rolling(60).max()
bdf["qqq_high252"] = bdf["qqq_close"].rolling(252).max()
bdf["qqq_dd60"] = bdf["qqq_close"] / bdf["qqq_high60"] - 1.0
bdf["qqq_dd252"] = bdf["qqq_close"] / bdf["qqq_high252"] - 1.0

# 20d and 60d Equal-Weight vs Cap-Weight return spread
bdf["ew_minus_cw_20d"] = bdf["ew_nav"].pct_change(20) - bdf["qqq_close"].pct_change(20)
bdf["ew_minus_cw_60d"] = bdf["ew_nav"].pct_change(60) - bdf["qqq_close"].pct_change(60)
bdf["b50_chg20"] = bdf["b50"] - bdf["b50"].shift(20)
bdf["b50_max60"] = bdf["b50"].rolling(60).max()
bdf["b50_drop_from_60d_max"] = bdf["b50"] - bdf["b50_max60"]

# Forward QQQ returns and forward max drawdowns (over next 20, 40, 60 trading days)
close_arr = bdf["qqq_close"].values
n_days = len(bdf)
fwd_ret_20 = np.full(n_days, np.nan)
fwd_ret_40 = np.full(n_days, np.nan)
fwd_ret_60 = np.full(n_days, np.nan)
fwd_mdd_20 = np.full(n_days, np.nan)
fwd_mdd_40 = np.full(n_days, np.nan)
fwd_mdd_60 = np.full(n_days, np.nan)

for i in range(n_days):
    p0 = close_arr[i]
    if i + 20 < n_days:
        fwd_ret_20[i] = close_arr[i + 20] / p0 - 1.0
        fwd_mdd_20[i] = np.min(close_arr[i + 1 : i + 21]) / p0 - 1.0
    if i + 40 < n_days:
        fwd_ret_40[i] = close_arr[i + 40] / p0 - 1.0
        fwd_mdd_40[i] = np.min(close_arr[i + 1 : i + 41]) / p0 - 1.0
    if i + 60 < n_days:
        fwd_ret_60[i] = close_arr[i + 60] / p0 - 1.0
        fwd_mdd_60[i] = np.min(close_arr[i + 1 : i + 61]) / p0 - 1.0

bdf["fwd_ret_20"] = fwd_ret_20
bdf["fwd_ret_40"] = fwd_ret_40
bdf["fwd_ret_60"] = fwd_ret_60
bdf["fwd_mdd_20"] = fwd_mdd_20
bdf["fwd_mdd_40"] = fwd_mdd_40
bdf["fwd_mdd_60"] = fwd_mdd_60

# Filter to TQQQ era: 2010-02-11 .. 2026-11-03
sub = bdf.loc["2010-02-11":"2026-11-03"].copy()
print(f"   Done. Active NDX constituents per day: min={sub['n_valid'].min()}, median={int(sub['n_valid'].median())}, max={sub['n_valid'].max()}")

# =================================================================================================
# PART 1: IS THE STATEMENT EMPIRICALLY TRUE?
# =================================================================================================
print("\n" + "=" * 95)
print("PART 1: EMPIRICAL TEST OF THE STATEMENT ON PIT NASDAQ-100 (2010-02-11 .. 2026-11-03)")
print("=" * 95)

# Check conditional forward QQQ statistics when QQQ is at a high (within 2% of 60d high AND QQQ > SMA50)
at_high = (sub["qqq_dd60"] >= -0.02) & (sub["qqq_close"] > sub["qqq_sma50"])

conds = [
    ("All Trading Days (2010-2026)", sub.index == sub.index),
    ("QQQ At High (within 2% of 60d High & > SMA50) — ALL", at_high),
    ("  1. Broad Rally at High: Breadth_50 >= 65%", at_high & (sub["b50"] >= 0.65)),
    ("  2. Moderate Breadth at High: 50% <= Breadth_50 < 65%", at_high & (sub["b50"] >= 0.50) & (sub["b50"] < 0.65)),
    ("  3. Narrow Divergence at High: Breadth_50 < 50% (>50% stocks < SMA50)", at_high & (sub["b50"] < 0.50)),
    ("  4. Severe Divergence at High: Breadth_50 < 45% (>55% stocks < SMA50)", at_high & (sub["b50"] < 0.45)),
    ("  5. Extreme Divergence at High: Breadth_50 < 40% (>60% stocks < SMA50)", at_high & (sub["b50"] < 0.40)),
    ("  6. High + EW lags CW by > 3% over 20d (ew_minus_cw_20d < -3%)", at_high & (sub["ew_minus_cw_20d"] < -0.03)),
    ("  7. High + EW lags CW by > 5% over 60d (ew_minus_cw_60d < -5%)", at_high & (sub["ew_minus_cw_60d"] < -0.05)),
    ("  8. High + Breadth_200 < 55% (Long-term breadth weak while QQQ at 60d high)", at_high & (sub["b200"] < 0.55)),
    ("  9. 52W-High (dd252 >= -2%) + Breadth_50 Drops >= 14pp from 40d Max", (sub["qqq_dd252"] >= -0.02) & (sub["b50_drop_from_60d_max"] <= -0.14)),
    (" 10. 52W-High (dd252 >= -2%) + Breadth_50 < 60%", (sub["qqq_dd252"] >= -0.02) & (sub["b50"] < 0.60)),
    (" 11. 52W-High (dd252 >= -2%) + EW lags CW by > 5% over 60d", (sub["qqq_dd252"] >= -0.02) & (sub["ew_minus_cw_60d"] < -0.05)),
    (" 12. 52W-High (dd252 >= -2%) + Breadth_200 < 65%", (sub["qqq_dd252"] >= -0.02) & (sub["b200"] < 0.65)),
]

part1_rows = []
for label, mask in conds:
    df_c = sub[mask & sub["fwd_ret_40"].notna()]
    n_c = len(df_c)
    if n_c == 0:
        continue
    row = {
        "Regime_Condition": label,
        "Days_Count": n_c,
        "Pct_of_Days": round(100.0 * n_c / len(sub), 2),
        "Avg_Breadth50_pct": round(100.0 * df_c["b50"].mean(), 1),
        "Fwd_20d_Mean_Ret_pct": round(100.0 * df_c["fwd_ret_20"].mean(), 2),
        "Fwd_40d_Mean_Ret_pct": round(100.0 * df_c["fwd_ret_40"].mean(), 2),
        "Fwd_60d_Mean_Ret_pct": round(100.0 * df_c["fwd_ret_60"].dropna().mean(), 2),
        "Fwd_40d_WinRate_pct": round(100.0 * (df_c["fwd_ret_40"] > 0).mean(), 1),
        "Fwd_40d_Avg_MaxDD_pct": round(100.0 * df_c["fwd_mdd_40"].mean(), 2),
        "Prob_40d_DD_gt_5pct": round(100.0 * (df_c["fwd_mdd_40"] <= -0.05).mean(), 1),
        "Prob_40d_DD_gt_10pct": round(100.0 * (df_c["fwd_mdd_40"] <= -0.10).mean(), 1),
    }
    part1_rows.append(row)

p1_df = pd.DataFrame(part1_rows)
p1_df.to_csv(os.path.join(OUT_DIR, "B1_breadth_divergence_conditional_outcomes.csv"), index=False)
print(p1_df.to_string(index=False))

# Check what Breadth looked like at the exact 10 major QQQ peaks before >=10% drawdowns (2010-2026)
print("\n" + "=" * 95)
print("PART 1B: ANATOMY OF THE 10 MAJOR QQQ MARKET TOPS (2010-2026) — DID BREADTH DIVERGE AT THE TOP?")
print("=" * 95)

major_peaks = [
    ("2011 Euro Debt Peak", "2011-07-22", "2011-08-19"),
    ("2015 China/Biotech Peak", "2015-07-20", "2015-08-25"),
    ("2018 Q4 Rate Hike Peak", "2018-08-29", "2018-12-24"),
    ("2018 Oct Secondary Peak", "2018-10-01", "2018-12-24"),
    ("2020 COVID Crash Peak", "2020-02-19", "2020-03-20"),
    ("2021 Nov All-Time Peak", "2021-11-19", "2022-10-14"),
    ("2021 Dec Double Top", "2021-12-27", "2022-10-14"),
    ("2023 Summer Peak", "2023-07-18", "2023-10-26"),
    ("2024 July Mag-7 Peak", "2024-07-10", "2024-08-07"),
    ("2025 Feb Tariff Peak", "2025-02-19", "2025-04-08"),
]

peak_rows = []
for name, pk_str, tr_str in major_peaks:
    pk_dt = sub.index[sub.index.searchsorted(pd.Timestamp(pk_str))]
    tr_dt = sub.index[min(sub.index.searchsorted(pd.Timestamp(tr_str)), len(sub) - 1)]
    r_pk = sub.loc[pk_dt]
    # Also check max Breadth_50 in the 40 days prior to peak
    w40 = sub.loc[:pk_dt].iloc[-40:]
    dd_actual = sub.loc[pk_dt:tr_dt, "qqq_close"].min() / r_pk["qqq_close"] - 1.0
    peak_rows.append({
        "Peak_Event": name,
        "Peak_Date": pk_dt.strftime("%Y-%m-%d"),
        "Subsequent_QQQ_DD_pct": round(100.0 * dd_actual, 2),
        "Breadth50_at_Peak_pct": round(100.0 * r_pk["b50"], 1),
        "Breadth50_40d_Prior_Max_pct": round(100.0 * w40["b50"].max(), 1),
        "Breadth50_Drop_Before_Peak_pp": round(100.0 * (r_pk["b50"] - w40["b50"].max()), 1),
        "Breadth200_at_Peak_pct": round(100.0 * r_pk["b200"], 1),
        "EW_minus_CW_20d_pct": round(100.0 * r_pk["ew_minus_cw_20d"], 2),
        "EW_minus_CW_60d_pct": round(100.0 * r_pk["ew_minus_cw_60d"], 2),
        "Divergence_Present_at_Peak": "YES" if (r_pk["b50"] < 0.55 or r_pk["ew_minus_cw_20d"] < -0.025) else "NO",
    })

pk_df = pd.DataFrame(peak_rows)
pk_df.to_csv(os.path.join(OUT_DIR, "B2_major_qqq_peaks_breadth_anatomy.csv"), index=False)
print(pk_df.to_string(index=False))

# =================================================================================================
# PART 2: CAN BREADTH DIVERGENCE IMPROVE OUR V1-DAILY TQQQ SEP STRATEGY?
# =================================================================================================
print("\n" + "=" * 95)
print("PART 2: STRATEGY INTEGRATION TEST — CAN BREADTH DIVERGENCE IMPROVE V1-DAILY TQQQ SEP?")
print("=" * 95)

# Load remediated R1 SEP signal and Vol_Z on QQQ
sep_df = pd.read_csv(os.path.join(OUT_DIR, "R1_complete_2012_2026_fomc_sep_core_vs_headline_pce.csv"))
sep_df["meeting_date"] = pd.to_datetime(sep_df["FOMC_Date"])
sep_df = sep_df.sort_values("meeting_date").reset_index(drop=True)

sep_on = pd.Series(True, index=cal)
for i, r in sep_df.iterrows():
    m_dt = r["meeting_date"]
    nxt_m = sep_df.loc[i + 1, "meeting_date"] if i + 1 < len(sep_df) else pd.Timestamp("2030-01-01")
    mask = (cal >= m_dt) & (cal < nxt_m)
    sep_on.loc[mask] = bool(r["SEP_ON_Core_PCE_(Official_Spec)"])

# Vol_Z(QQQ)
ret_q = qqq["adjClose"].pct_change()
rv20 = ret_q.rolling(20).std() * np.sqrt(252) * 100.0
vz_q = (rv20 - rv20.rolling(252).mean()) / rv20.rolling(252).std()

# Return-chained cash open-to-open and close-to-close
cash_o = pd.Series(index=cal, dtype=float)
cash_c = pd.Series(index=cal, dtype=float)
bil_o = bil["adjOpen"].reindex(cal).ffill()
bil_c = bil["adjClose"].reindex(cal).ffill()
sgov_o = sgov["adjOpen"].reindex(cal).ffill()
sgov_c = sgov["adjClose"].reindex(cal).ffill()
splice_dt = pd.Timestamp("2020-06-01")

cash_o.iloc[0] = 100.0
cash_c.iloc[0] = 100.0 * (bil_c.iloc[0] / bil_o.iloc[0])
for i in range(1, len(cal)):
    dt = cal[i]
    prev_dt = cal[i - 1]
    if dt <= splice_dt or pd.isna(sgov_o.loc[prev_dt]) or pd.isna(sgov_o.loc[dt]):
        ro = bil_o.loc[dt] / bil_o.loc[prev_dt] - 1.0
        rc = bil_c.loc[dt] / bil_o.loc[dt] - 1.0
    else:
        ro = sgov_o.loc[dt] / sgov_o.loc[prev_dt] - 1.0
        rc = sgov_c.loc[dt] / sgov_o.loc[dt] - 1.0
    cash_o.iloc[i] = cash_o.iloc[i - 1] * (1.0 + (ro if np.isfinite(ro) else 0.0))
    cash_c.iloc[i] = cash_o.iloc[i] * (1.0 + (rc if np.isfinite(rc) else 0.0))

sim_dates = cal[(cal >= pd.Timestamp("2010-03-11")) & (cal <= pd.Timestamp("2026-11-03"))]


def run_v1_with_breadth_rule(mode_name, rule_type, param=None):
    """
    Runs remediated R3 Share-Lot V1-Daily TQQQ SEP with optional Breadth Divergence rules.
    States: 3 = TQQQ, 1 = QQQ, 0 = Cash (SGOV/BIL)
    """
    p_3o = tqqq["adjOpen"].reindex(sim_dates).values
    p_3c = tqqq["adjClose"].reindex(sim_dates).values
    p_1o = qqq["adjOpen"].reindex(sim_dates).values
    p_1c = qqq["adjClose"].reindex(sim_dates).values
    p_0o = cash_o.reindex(sim_dates).values
    p_0c = cash_c.reindex(sim_dates).values

    s_sep = sep_on.reindex(sim_dates).values
    s_vz = vz_q.reindex(sim_dates).values
    s_b50 = bdf["b50"].reindex(sim_dates).values
    s_b200 = bdf["b200"].reindex(sim_dates).values
    s_dd60 = bdf["qqq_dd60"].reindex(sim_dates).values
    s_qsma50 = (bdf["qqq_close"] > bdf["qqq_sma50"]).reindex(sim_dates).values
    s_ewcw20 = bdf["ew_minus_cw_20d"].reindex(sim_dates).values
    s_ewcw60 = bdf["ew_minus_cw_60d"].reindex(sim_dates).values
    s_b50_drop = bdf["b50_drop_from_60d_max"].reindex(sim_dates).values

    n = len(sim_dates)
    nav = np.zeros(n)

    state = 3 if s_sep[0] else 0
    px0 = p_3o[0] if state == 3 else p_0o[0]
    shares = (1.0 * (1.0 - FEE)) / px0
    cost_basis = 1.0  # total dollar cost basis of current 3x position
    nav[0] = shares * (p_3c[0] if state == 3 else p_0c[0])

    switches = 0
    breadth_triggers = 0

    for i in range(1, n):
        # Signal evaluated at yesterday's close (i-1), executed at today's open (i)
        sep_prev = s_sep[i - 1]
        vz_prev = s_vz[i - 1]
        b50_prev = s_b50[i - 1]
        b200_prev = s_b200[i - 1]
        dd60_prev = s_dd60[i - 1]
        qsma50_prev = s_qsma50[i - 1]
        ewcw20_prev = s_ewcw20[i - 1]
        ewcw60_prev = s_ewcw60[i - 1]
        b50_drop_prev = s_b50_drop[i - 1]

        # Open value of current holding before any switch
        if state == 3:
            open_val = shares * p_3o[i]
        elif state == 1:
            open_val = shares * p_1o[i]
        else:
            open_val = shares * p_0o[i]

        in_profit_at_open = (open_val * (1.0 - FEE)) > cost_basis

        target = state
        trig_by_breadth = False

        if not sep_prev:
            target = 0
        else:
            if state == 0:
                target = 3
            elif state == 3:
                # Baseline trigger
                base_delever = (vz_prev > 1.2) and in_profit_at_open

                if rule_type == "baseline":
                    if base_delever:
                        target = 1

                elif rule_type == "direct_high_b50_nsl":
                    # Escape 3x -> 1x when QQQ at high (dd60 >= -2% & > SMA50) and Breadth_50 < threshold (with NSL)
                    b_div = qsma50_prev and (dd60_prev >= -0.02) and (b50_prev < param)
                    if base_delever or (b_div and in_profit_at_open):
                        target = 1
                        if not base_delever:
                            trig_by_breadth = True

                elif rule_type == "direct_high_b50_no_nsl":
                    # Escape 3x -> 1x when QQQ at high and Breadth_50 < threshold (override NSL)
                    b_div = qsma50_prev and (dd60_prev >= -0.02) and (b50_prev < param)
                    if base_delever or b_div:
                        target = 1
                        if not base_delever:
                            trig_by_breadth = True

                elif rule_type == "direct_b50_collapse_nsl":
                    # De-lever whenever Breadth_50 < threshold (regardless of QQQ near high) with NSL
                    if base_delever or ((b50_prev < param) and in_profit_at_open):
                        target = 1
                        if not base_delever:
                            trig_by_breadth = True

                elif rule_type == "adaptive_volz_when_narrow_b50":
                    # Lower Vol_Z trigger from 1.2 to param[1] when Breadth_50 < param[0]
                    b_thresh, vz_low = param
                    eff_trig = vz_low if (b50_prev < b_thresh) else 1.2
                    if (vz_prev > eff_trig) and in_profit_at_open:
                        target = 1
                        if not base_delever:
                            trig_by_breadth = True

                elif rule_type == "adaptive_volz_when_ew_lags":
                    # Lower Vol_Z trigger from 1.2 to param[1] when EW lags CW by > param[0] over 20d
                    lag_thresh, vz_low = param
                    eff_trig = vz_low if (ewcw20_prev < lag_thresh) else 1.2
                    if (vz_prev > eff_trig) and in_profit_at_open:
                        target = 1
                        if not base_delever:
                            trig_by_breadth = True

                elif rule_type == "adaptive_volz_when_b50_drops":
                    # Lower Vol_Z trigger from 1.2 to param[1] when Breadth_50 dropped > param[0] from 60d max
                    drop_thresh, vz_low = param
                    eff_trig = vz_low if (b50_drop_prev < drop_thresh) else 1.2
                    if (vz_prev > eff_trig) and in_profit_at_open:
                        target = 1
                        if not base_delever:
                            trig_by_breadth = True

                elif rule_type == "gate_volz_only_when_narrow":
                    # Only allow Vol_Z > 1.2 to de-lever if Breadth_50 < param (if Breadth is strong >= param, ignore Vol_Z spike!)
                    if base_delever and (b50_prev < param):
                        target = 1

                elif rule_type == "direct_high_b200_nsl":
                    b_div = qsma50_prev and (dd60_prev >= -0.02) and (b200_prev < param)
                    if base_delever or (b_div and in_profit_at_open):
                        target = 1
                        if not base_delever:
                            trig_by_breadth = True

                elif rule_type == "direct_high_b50drop_nsl":
                    # Escape when QQQ at high (dd60 >= -2%) and Breadth_50 dropped >= param from 60d max
                    b_div = qsma50_prev and (dd60_prev >= -0.02) and (b50_drop_prev <= param)
                    if base_delever or (b_div and in_profit_at_open):
                        target = 1
                        if not base_delever:
                            trig_by_breadth = True

                elif rule_type == "direct_high_ewcw60_nsl":
                    # Escape when QQQ at high (dd60 >= -2%) and EW lags CW by >= param over 60d
                    b_div = qsma50_prev and (dd60_prev >= -0.02) and (ewcw60_prev <= param)
                    if base_delever or (b_div and in_profit_at_open):
                        target = 1
                        if not base_delever:
                            trig_by_breadth = True

                elif rule_type == "gate_relever_b50":
                    if base_delever:
                        target = 1

            elif state == 1:
                # Re-leveraging 1x -> 3x
                if rule_type == "gate_relever_b50":
                    if (vz_prev < 0.3) and (b50_prev >= param):
                        target = 3
                elif rule_type in ("direct_high_b50_nsl", "direct_high_b50_no_nsl"):
                    b_div = qsma50_prev and (dd60_prev >= -0.02) and (b50_prev < param)
                    if (vz_prev < 0.3) and (not b_div):
                        target = 3
                elif rule_type == "direct_b50_collapse_nsl":
                    if (vz_prev < 0.3) and (b50_prev >= param):
                        target = 3
                else:
                    if vz_prev < 0.3:
                        target = 3

        if target != state:
            # Execute 2-sided trade at today's open (sell old, buy new -> (1 - FEE)^2)
            net_cap = open_val * (1.0 - FEE) * (1.0 - FEE)
            new_px = p_3o[i] if target == 3 else (p_1o[i] if target == 1 else p_0o[i])
            shares = net_cap / new_px
            if target == 3:
                cost_basis = net_cap
            state = target
            switches += 1
            if trig_by_breadth:
                breadth_triggers += 1

        # End of day close NAV
        close_px = p_3c[i] if state == 3 else (p_1c[i] if state == 1 else p_0c[i])
        nav[i] = shares * close_px

    s_nav = pd.Series(nav, index=sim_dates)
    yrs = (sim_dates[-1] - sim_dates[0]).days / 365.25
    cagr = (s_nav.iloc[-1] / 1.0) ** (1.0 / yrs) - 1.0
    mdd = (s_nav / s_nav.cummax() - 1.0).min()
    dr = s_nav.pct_change().dropna()
    sh = (dr.mean() / dr.std()) * np.sqrt(252)

    # Pre-AI (2010-2022) vs AI (2023-2026)
    s_pre = s_nav.loc[:"2022-12-31"]
    yrs_pre = (s_pre.index[-1] - s_pre.index[0]).days / 365.25
    cagr_pre = (s_pre.iloc[-1] / 1.0) ** (1.0 / yrs_pre) - 1.0

    s_ai = s_nav.loc["2022-12-30":]
    yrs_ai = (s_ai.index[-1] - s_ai.index[0]).days / 365.25
    cagr_ai = (s_ai.iloc[-1] / s_ai.iloc[0]) ** (1.0 / yrs_ai) - 1.0

    return {
        "Strategy_Variant": mode_name,
        "Full_CAGR_pct": round(100.0 * cagr, 2),
        "MaxDD_pct": round(100.0 * mdd, 2),
        "Sharpe": round(sh, 3),
        "Calmar": round(cagr / abs(mdd), 3),
        "PreAI_2010_2022_CAGR_pct": round(100.0 * cagr_pre, 2),
        "AI_2023_2026_CAGR_pct": round(100.0 * cagr_ai, 2),
        "Total_Switches": switches,
        "Extra_Breadth_Triggers": breadth_triggers,
    }


variants = [
    ("0. Baseline: V1-Daily TQQQ (SEP + Vol_Z 1.2/0.3 + NSL)", "baseline", None),
    # A. Direct Top-Escape on Breadth Divergence at High (QQQ within 2% of 60d high & >SMA50, Breadth_50 < X)
    ("A1. Direct Escape at High: Breadth_50 < 50% (with NSL)", "direct_high_b50_nsl", 0.50),
    ("A2. Direct Escape at High: Breadth_50 < 45% (with NSL)", "direct_high_b50_nsl", 0.45),
    ("A3. Direct Escape at High: Breadth_50 < 40% (with NSL)", "direct_high_b50_nsl", 0.40),
    ("A4. Direct Escape at High: Breadth_50 < 45% (Override NSL)", "direct_high_b50_no_nsl", 0.45),
    ("A5. Direct Escape at High: Breadth_200 < 55% (with NSL)", "direct_high_b200_nsl", 0.55),
    ("A6. Direct Escape at High: Breadth_200 < 65% (with NSL)", "direct_high_b200_nsl", 0.65),
    ("A7. Direct Escape at High: Breadth_50 Drops >=14pp from 60d Max (NSL)", "direct_high_b50drop_nsl", -0.14),
    ("A8. Direct Escape at High: EW lags CW by >=5% over 60d (NSL)", "direct_high_ewcw60_nsl", -0.05),
    # B. Direct De-lever on Any Breadth Collapse (Breadth_50 < X)
    ("B1. Direct De-lever: Breadth_50 < 40% (with NSL)", "direct_b50_collapse_nsl", 0.40),
    ("B2. Direct De-lever: Breadth_50 < 35% (with NSL)", "direct_b50_collapse_nsl", 0.35),
    ("B3. Direct De-lever: Breadth_50 < 30% (with NSL)", "direct_b50_collapse_nsl", 0.30),
    # C. Adaptive Vol_Z Tightening When Breadth is Narrow (Lower Vol_Z trigger from 1.2 to Y when Breadth_50 < X)
    ("C1. Adaptive Vol_Z: Breadth_50 < 50% -> Vol_Z > 0.8 (else 1.2)", "adaptive_volz_when_narrow_b50", (0.50, 0.80)),
    ("C2. Adaptive Vol_Z: Breadth_50 < 50% -> Vol_Z > 0.9 (else 1.2)", "adaptive_volz_when_narrow_b50", (0.50, 0.90)),
    ("C3. Adaptive Vol_Z: Breadth_50 < 45% -> Vol_Z > 0.8 (else 1.2)", "adaptive_volz_when_narrow_b50", (0.45, 0.80)),
    ("C4. Adaptive Vol_Z: Breadth_50 < 45% -> Vol_Z > 1.0 (else 1.2)", "adaptive_volz_when_narrow_b50", (0.45, 1.00)),
    ("C5. Adaptive Vol_Z: EW-CW 20d < -3% -> Vol_Z > 0.8 (else 1.2)", "adaptive_volz_when_ew_lags", (-0.03, 0.80)),
    ("C6. Adaptive Vol_Z: Breadth_50 drops >15pp -> Vol_Z > 0.8", "adaptive_volz_when_b50_drops", (-0.15, 0.80)),
    # D. Breadth Confirmation Gate on Vol_Z De-leveraging (Only de-lever on Vol_Z > 1.2 if Breadth_50 < X)
    ("D1. Breadth Confirm De-lever: Vol_Z > 1.2 AND Breadth_50 < 55%", "gate_volz_only_when_narrow", 0.55),
    ("D2. Breadth Confirm De-lever: Vol_Z > 1.2 AND Breadth_50 < 50%", "gate_volz_only_when_narrow", 0.50),
    ("D3. Breadth Confirm De-lever: Vol_Z > 1.2 AND Breadth_50 < 45%", "gate_volz_only_when_narrow", 0.45),
    # E. Breadth Confirmation Gate on Re-leveraging (1x -> 3x requires Vol_Z < 0.3 AND Breadth_50 >= X)
    ("E1. Re-lever Gate: Vol_Z < 0.3 AND Breadth_50 >= 45%", "gate_relever_b50", 0.45),
    ("E2. Re-lever Gate: Vol_Z < 0.3 AND Breadth_50 >= 50%", "gate_relever_b50", 0.50),
    ("E3. Re-lever Gate: Vol_Z < 0.3 AND Breadth_50 >= 55%", "gate_relever_b50", 0.55),
]

res_rows = [run_v1_with_breadth_rule(name, rtype, p) for name, rtype, p in variants]
res_df = pd.DataFrame(res_rows)
res_df.to_csv(os.path.join(OUT_DIR, "B3_v1_tqqq_breadth_divergence_strategy_tests.csv"), index=False)
print(res_df.to_string(index=False))
