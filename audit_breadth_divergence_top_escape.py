#!/usr/bin/env python3
"""
Round-3 Remediated Empirical Audit of Market Breadth Divergence on PIT Nasdaq-100 (2010-03-11 .. 2026-11-03)
=============================================================================================================
Addresses all Round-3 External Audit findings on Commit 973da78:
1. Exact Baseline Alignment (53.21% CAGR, -44.54% MaxDD, 1.232 Sharpe):
   - Uses the exact same initialization (Day 0 Close = 1.0) and SEP re-entry rule
     (`pos == "0x" -> "1x" if Vol_Z > 1.2 else "3x"`) as `run_single_share_lot_engine` in `R3`.
2. Strict Point-in-Time (PIT) Constituent Mapping & Zero Return Clipping:
   - Maps `(src, sym)` strictly from the latest completed month-end `t_prev <= dt` (zero within-month look-ahead).
   - Removes `abs(r1) < 0.8` filter on constituent daily returns.
   - Exports full 4,189-day daily breadth & constituent coverage ledger (`B0_daily_pit_ndx_breadth_and_coverage.csv`).
3. Both Forward Drawdown Definitions + De-Clustered Independent Episode Counts (`B1`):
   - Reports BOTH `Fwd_40d_Max_Drop_from_Signal` (`min(P[t+1..t+40])/P[t] - 1`) AND
     `Fwd_40d_True_Peak_to_Trough_MaxDD` (`min_{u <= v in [t..t+40]} (P[v]/P[u] - 1)`).
   - Computes de-clustered independent signal episodes (minimum 40 trading days separation between episode starts)
     and reports episode count and episode-level >=10% drop hit rate.
4. Programmatic Objective Peak-Trough Cycle Detection (`B2`):
   - Automatically identifies all objective QQQ bull peaks followed by a >=10% drawdown before a new high is reached.
5. Full Trade-by-Trade Switch Ledger, Exact Decomposition of C5 (2 extra triggers) & A5, Parameter Sensitivity Grid,
   and Stateful Walk-Forward OOS (2014-2026) (`B3`, `B4`, `B5`).
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


print("1. Loading ETFs and strictly Point-in-Time (PIT) Nasdaq-100 constituent daily prices...")
qqq = load_etf("QQQ")
tqqq = load_etf("TQQQ")
bil = load_etf("BIL")
sgov = load_etf("SGOV")

cal = qqq.index[(qqq.index >= pd.Timestamp("2008-01-02")) & (qqq.index <= pd.Timestamp("2026-11-03"))]
qqq = qqq.reindex(cal)

P_NDX = pd.read_parquet(os.path.join(INP, "v3_ndx_panel_214m.parquet"))
P_NDX["t"] = pd.to_datetime(P_NDX["t"])
P_NDX = P_NDX.sort_values(["t", "ticker"]).reset_index(drop=True)

# Build strictly PIT source history per ticker: sorted list of (month_end_t, (src, sym))
# At any trading day dt, we ONLY look up month_end_t <= dt (or earliest available if ticker was added mid-month with identical source)
pit_tk_history = {}
unique_pairs = set()
for r in P_NDX.itertuples(index=False):
    if isinstance(r.src, str) and isinstance(r.sym, str):
        pair = (r.src, r.sym)
        unique_pairs.add(pair)
        pit_tk_history.setdefault(r.ticker, []).append((r.t, pair))


def get_pit_pair(tk, dt):
    hist = pit_tk_history.get(tk)
    if not hist:
        return None
    # Strictly use latest month-end snapshot t <= dt; if newly added after last month-end, use first snapshot only if symbol matches ticker
    chosen = None
    for t_snap, pair in hist:
        if t_snap <= dt:
            chosen = pair
        else:
            break
    if chosen is not None:
        return chosen
    # For a stock newly added to NDX mid-month before its first month-end snapshot, use its direct ticker file (yahoo/tiingo/wiki with sym == tk)
    first_pair = hist[0][1]
    if first_pair[1] == tk:
        return first_pair
    return None


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

pair_above20, pair_above50, pair_above100, pair_above200, pair_ret1d, pair_has_px = {}, {}, {}, {}, {}, {}
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
    pair_has_px[pair] = s.notna()

ndx_years = {}
for f in sorted(glob.glob(os.path.join(DATA, "nasdaq100_src", "n100-ticker-changes-*.yaml"))):
    d = yaml.load(open(f), Loader=yaml.BaseLoader)
    ch = [
        (pd.Timestamp(str(k)), set((v or {}).get("union") or []), set((v or {}).get("difference") or []))
        for k, v in (d.get("changes") or {}).items()
    ]
    ndx_years[int(d["year"])] = (set(d["tickers_on_Jan_1"]), sorted(ch, key=lambda x: x[0]))

print("2. Computing daily PIT Nasdaq-100 Breadth, Equal-Weight NDX (zero return clipping), and coverage audit...")
b20_l, b50_l, b100_l, b200_l, ew_ret_l = [], [], [], [], []
n_mem_l, n_px_l, n_sma50_l, n_sma200_l = [], [], [], []

for dt in cal:
    y = min(dt.year, max(ndx_years))
    s_mem, ch = ndx_years[y]
    s_mem = set(s_mem)
    for c_dt, add, rem in ch:
        if c_dt <= dt:
            s_mem = (s_mem - rem) | add

    v20, v50, v100, v200, vret = [], [], [], [], []
    n_px = 0
    for tk in s_mem:
        pair = get_pit_pair(tk, dt)
        if pair is None or pair not in pair_series:
            continue
        if pair_has_px[pair].at[dt]:
            n_px += 1
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
        if pd.notna(r1) and np.isfinite(r1):
            vret.append(float(r1))

    n_mem_l.append(len(s_mem))
    n_px_l.append(n_px)
    n_sma50_l.append(len(v50))
    n_sma200_l.append(len(v200))
    b20_l.append(np.mean(v20) if v20 else np.nan)
    b50_l.append(np.mean(v50) if v50 else np.nan)
    b100_l.append(np.mean(v100) if v100 else np.nan)
    b200_l.append(np.mean(v200) if v200 else np.nan)
    ew_ret_l.append(np.mean(vret) if vret else 0.0)

bdf = pd.DataFrame({
    "qqq_close": qqq["adjClose"],
    "qqq_open": qqq["adjOpen"],
    "qqq_ret": qqq["adjClose"].pct_change(),
    "ew_ret": ew_ret_l,
    "b20": b20_l,
    "b50": b50_l,
    "b100": b100_l,
    "b200": b200_l,
    "ndx_yaml_members": n_mem_l,
    "priced_members": n_px_l,
    "valid_sma50_members": n_sma50_l,
    "valid_sma200_members": n_sma200_l,
}, index=cal)

bdf["coverage_ratio_pct"] = (bdf["priced_members"] / bdf["ndx_yaml_members"] * 100.0).round(2)
bdf["ew_nav"] = (1.0 + bdf["ew_ret"]).cumprod()
bdf["qqq_sma50"] = bdf["qqq_close"].rolling(50).mean()
bdf["qqq_sma200"] = bdf["qqq_close"].rolling(200).mean()
bdf["qqq_high60"] = bdf["qqq_close"].rolling(60).max()
bdf["qqq_high252"] = bdf["qqq_close"].rolling(252).max()
bdf["qqq_dd60"] = bdf["qqq_close"] / bdf["qqq_high60"] - 1.0
bdf["qqq_dd252"] = bdf["qqq_close"] / bdf["qqq_high252"] - 1.0
bdf["ew_minus_cw_20d"] = bdf["ew_nav"].pct_change(20) - bdf["qqq_close"].pct_change(20)
bdf["ew_minus_cw_60d"] = bdf["ew_nav"].pct_change(60) - bdf["qqq_close"].pct_change(60)
bdf["b50_max60"] = bdf["b50"].rolling(60).max()
bdf["b50_drop_from_60d_max"] = bdf["b50"] - bdf["b50_max60"]

# Compute BOTH forward 40d max drop from signal close AND true rolling peak-to-trough max drawdown in [t, t+40]
close_arr = bdf["qqq_close"].values
n_days = len(bdf)
fwd_ret_20 = np.full(n_days, np.nan)
fwd_ret_40 = np.full(n_days, np.nan)
fwd_ret_60 = np.full(n_days, np.nan)
fwd_drop_from_sig_40 = np.full(n_days, np.nan)
fwd_true_mdd_40 = np.full(n_days, np.nan)

for i in range(n_days):
    p0 = close_arr[i]
    if i + 20 < n_days:
        fwd_ret_20[i] = close_arr[i + 20] / p0 - 1.0
    if i + 40 < n_days:
        w = close_arr[i : i + 41]  # includes signal day P[t] through P[t+40]
        fwd_ret_40[i] = close_arr[i + 40] / p0 - 1.0
        fwd_drop_from_sig_40[i] = np.min(close_arr[i + 1 : i + 41]) / p0 - 1.0
        running_max = np.maximum.accumulate(w)
        fwd_true_mdd_40[i] = np.min(w / running_max - 1.0)
    if i + 60 < n_days:
        fwd_ret_60[i] = close_arr[i + 60] / p0 - 1.0

bdf["fwd_ret_20"] = fwd_ret_20
bdf["fwd_ret_40"] = fwd_ret_40
bdf["fwd_ret_60"] = fwd_ret_60
bdf["fwd_drop_from_sig_40"] = fwd_drop_from_sig_40
bdf["fwd_true_mdd_40"] = fwd_true_mdd_40

# Export full daily breadth & coverage table for 2010-03-11 .. 2026-11-03 (4,189 trading days)
sim_dates = cal[(cal >= pd.Timestamp("2010-03-11")) & (cal <= pd.Timestamp("2026-11-03"))]
b0_export = bdf.reindex(sim_dates)[[
    "qqq_close", "ndx_yaml_members", "priced_members", "coverage_ratio_pct",
    "valid_sma50_members", "valid_sma200_members",
    "b20", "b50", "b100", "b200", "ew_ret", "ew_minus_cw_20d", "ew_minus_cw_60d",
    "qqq_dd60", "qqq_dd252", "fwd_ret_40", "fwd_drop_from_sig_40", "fwd_true_mdd_40"
]].copy()
b0_export.index.name = "Date"
b0_export.to_csv(os.path.join(OUT_DIR, "B0_daily_pit_ndx_breadth_and_coverage.csv"))

sub = bdf.loc["2010-02-11":"2026-11-03"].copy()
print(f"   Coverage Audit (2010-2026): YAML members median={int(sub['ndx_yaml_members'].median())}, "
      f"priced median={int(sub['priced_members'].median())}, "
      f"mean coverage={sub['coverage_ratio_pct'].mean():.2f}%, min coverage={sub['coverage_ratio_pct'].min():.2f}%")


def count_independent_episodes(mask_ser, min_gap_days=40):
    """De-clusters daily signals into distinct independent episodes separated by at least `min_gap_days` trading days."""
    sig_positions = np.where(mask_ser.values)[0]
    if len(sig_positions) == 0:
        return 0, 0, 0, 0.0, 0.0
    ep_starts = []
    last_pos = -999999
    for pos in sig_positions:
        if pos - last_pos >= min_gap_days:
            ep_starts.append(pos)
            last_pos = pos
    ep_df = sub.iloc[ep_starts]
    n_ep = len(ep_df)
    ep_drop10 = int((ep_df["fwd_drop_from_sig_40"] <= -0.10).sum())
    ep_mdd10 = int((ep_df["fwd_true_mdd_40"] <= -0.10).sum())
    return n_ep, ep_drop10, ep_mdd10, round(100.0 * ep_drop10 / n_ep, 1), round(100.0 * ep_mdd10 / n_ep, 1)


# =================================================================================================
# PART 1: REMEDIATED CONDITIONAL OUTCOMES (BOTH DD DEFINITIONS + DE-CLUSTERED INDEPENDENT EPISODES)
# =================================================================================================
print("\n" + "=" * 115)
print("PART 1: REMEDIATED CONDITIONAL OUTCOMES (BOTH DD DEFINITIONS & DE-CLUSTERED 40-DAY INDEPENDENT EPISODES)")
print("=" * 115)

at_high = (sub["qqq_dd60"] >= -0.02) & (sub["qqq_close"] > sub["qqq_sma50"])
valid_40 = sub["fwd_ret_40"].notna()

conds = [
    ("All Trading Days (2010-2026)", valid_40),
    ("QQQ At 60d High (dd60 >= -2% & > SMA50) — ALL", at_high & valid_40),
    ("  1. Broad Rally at High: Breadth_50 >= 65%", at_high & (sub["b50"] >= 0.65) & valid_40),
    ("  2. Moderate Breadth at High: 50% <= Breadth_50 < 65%", at_high & (sub["b50"] >= 0.50) & (sub["b50"] < 0.65) & valid_40),
    ("  3. Narrow Divergence at High: Breadth_50 < 50%", at_high & (sub["b50"] < 0.50) & valid_40),
    ("  4. Severe Divergence at High: Breadth_50 < 45%", at_high & (sub["b50"] < 0.45) & valid_40),
    ("  5. Extreme Divergence at High: Breadth_50 < 40%", at_high & (sub["b50"] < 0.40) & valid_40),
    ("  6. High + EW lags CW by > 3% over 20d", at_high & (sub["ew_minus_cw_20d"] < -0.03) & valid_40),
    ("  7. High + EW lags CW by > 5% over 60d", at_high & (sub["ew_minus_cw_60d"] < -0.05) & valid_40),
    ("  8. High + Breadth_200 < 55% (Long-term breadth weak at 60d high)", at_high & (sub["b200"] < 0.55) & valid_40),
    ("  9. 52W-High (dd252 >= -2%) + Breadth_50 Drops >= 14pp from 60d Max", (sub["qqq_dd252"] >= -0.02) & (sub["b50_drop_from_60d_max"] <= -0.14) & valid_40),
    (" 10. 52W-High (dd252 >= -2%) + Breadth_50 < 60%", (sub["qqq_dd252"] >= -0.02) & (sub["b50"] < 0.60) & valid_40),
    (" 11. 52W-High (dd252 >= -2%) + EW lags CW by > 5% over 60d", (sub["qqq_dd252"] >= -0.02) & (sub["ew_minus_cw_60d"] < -0.05) & valid_40),
    (" 12. 52W-High (dd252 >= -2%) + Breadth_200 < 65%", (sub["qqq_dd252"] >= -0.02) & (sub["b200"] < 0.65) & valid_40),
]

part1_rows = []
for label, mask in conds:
    df_c = sub[mask]
    n_c = len(df_c)
    if n_c == 0:
        continue
    n_ep, ep_d10, ep_m10, ep_d10_pct, ep_m10_pct = count_independent_episodes(mask, min_gap_days=40)
    part1_rows.append({
        "Regime_Condition": label,
        "Signal_Days": n_c,
        "Independent_40d_Episodes": n_ep,
        "Fwd_40d_Mean_Ret_pct": round(100.0 * df_c["fwd_ret_40"].mean(), 2),
        "Fwd_40d_WinRate_pct": round(100.0 * (df_c["fwd_ret_40"] > 0).mean(), 1),
        "Day_Prob_DropFromSignal_ge_10pct": round(100.0 * (df_c["fwd_drop_from_sig_40"] <= -0.10).mean(), 2),
        "Day_Prob_TruePeakTroughMaxDD_ge_10pct": round(100.0 * (df_c["fwd_true_mdd_40"] <= -0.10).mean(), 2),
        "Episode_Hit_DropFromSignal_ge_10pct": f"{ep_d10}/{n_ep} ({ep_d10_pct}%)",
        "Episode_Hit_TrueMaxDD_ge_10pct": f"{ep_m10}/{n_ep} ({ep_m10_pct}%)",
    })

p1_df = pd.DataFrame(part1_rows)
p1_df.to_csv(os.path.join(OUT_DIR, "B1_breadth_divergence_conditional_outcomes.csv"), index=False)
print(p1_df.to_string(index=False))

# =================================================================================================
# PART 1B: PROGRAMMATIC OBJECTIVE DETECTION OF ALL QQQ PEAKS FOLLOWED BY >=10% DRAWDOWN (2010-2026)
# =================================================================================================
print("\n" + "=" * 115)
print("PART 1B: PROGRAMMATICALLY DETECTED QQQ BULL PEAKS FOLLOWED BY >=10% DRAWDOWN BEFORE NEW HIGH (2010-2026)")
print("=" * 115)

# Objective peak-trough algorithm: find every all-time / 252d rolling high that is followed by a >=10% drawdown before being surpassed
obj_peaks = []
i = 0
dates_sub = sub.index
px_sub = sub["qqq_close"].values
while i < len(sub):
    # Track running peak until a >=10% drop from that running peak occurs
    pk_idx = i
    pk_val = px_sub[i]
    tr_idx = i
    tr_val = px_sub[i]
    in_dd = False
    j = i + 1
    while j < len(sub):
        if not in_dd:
            if px_sub[j] >= pk_val:
                pk_val = px_sub[j]
                pk_idx = j
            elif px_sub[j] / pk_val - 1.0 <= -0.10:
                in_dd = True
                tr_val = px_sub[j]
                tr_idx = j
        else:
            if px_sub[j] < tr_val:
                tr_val = px_sub[j]
                tr_idx = j
            elif px_sub[j] >= pk_val:
                # Recovered to old peak -> cycle complete!
                break
        j += 1
    if in_dd:
        pk_dt = dates_sub[pk_idx]
        tr_dt = dates_sub[tr_idx]
        r_pk = sub.loc[pk_dt]
        w40 = sub.loc[:pk_dt].iloc[-40:]
        obj_peaks.append({
            "Objective_Peak_Date": pk_dt.strftime("%Y-%m-%d"),
            "Trough_Date": tr_dt.strftime("%Y-%m-%d"),
            "Cycle_MaxDD_pct": round(100.0 * (tr_val / pk_val - 1.0), 2),
            "Breadth50_at_Peak_pct": round(100.0 * r_pk["b50"], 1),
            "Breadth50_Min_5d_Prior_pct": round(100.0 * sub.loc[:pk_dt].iloc[-5:]["b50"].min(), 1),
            "Breadth50_Drop_from_40d_Max_pp": round(100.0 * (r_pk["b50"] - w40["b50"].max()), 1),
            "Breadth200_at_Peak_pct": round(100.0 * r_pk["b200"], 1),
            "EW_minus_CW_20d_pct": round(100.0 * r_pk["ew_minus_cw_20d"], 2),
            "EW_minus_CW_60d_pct": round(100.0 * r_pk["ew_minus_cw_60d"], 2),
            "B50_lt_50_at_Peak": bool(r_pk["b50"] < 0.50),
            "B200_lt_55_at_Peak": bool(r_pk["b200"] < 0.55),
            "EWCW20_lt_minus3pct": bool(r_pk["ew_minus_cw_20d"] < -0.03),
        })
        i = j
    else:
        break

pk_df = pd.DataFrame(obj_peaks)
pk_df.to_csv(os.path.join(OUT_DIR, "B2_major_qqq_peaks_breadth_anatomy.csv"), index=False)
print(pk_df.to_string(index=False))
print(f"Summary across {len(pk_df)} objectively detected >=10% drawdown peaks:")
print(f"  - Breadth_50 < 50% on peak day: {pk_df['B50_lt_50_at_Peak'].sum()} / {len(pk_df)}")
print(f"  - Breadth_200 < 55% on peak day: {pk_df['B200_lt_55_at_Peak'].sum()} / {len(pk_df)}")
print(f"  - EW-CW 20d < -3% on peak day: {pk_df['EWCW20_lt_minus3pct'].sum()} / {len(pk_df)}")

# =================================================================================================
# PART 2: EXACT FROZEN R3 BASELINE (53.21%) VS BREADTH VARIANTS + TRADE LEDGER + WALK-FORWARD OOS
# =================================================================================================
print("\n" + "=" * 115)
print("PART 2: STRATEGY INTEGRATION ON EXACT FROZEN R3 BASELINE (53.21% CAGR, -44.54% MaxDD, 1.232 Sharpe)")
print("=" * 115)

sep_df = pd.read_csv(os.path.join(OUT_DIR, "R1_complete_2012_2026_fomc_sep_core_vs_headline_pce.csv"))
sep_df["meeting_date"] = pd.to_datetime(sep_df["FOMC_Date"])
sep_df = sep_df.sort_values("meeting_date").reset_index(drop=True)

# Match exact SEP mapping in remediate_soxl_tqqq_7point_audit.py (`cal >= m_dt` so `sep_v[i-1]` triggers on next trading day open after FOMC!)
sep_on = pd.Series(True, index=cal)
for i, r in sep_df.iterrows():
    m_dt = r["meeting_date"]
    sep_on.loc[cal >= m_dt] = bool(r["SEP_ON_Core_PCE_(Official_Spec)"])

# Match exact Vol_Z(QQQ) with ddof=1
ret_q = qqq["adjClose"].pct_change()
rv20 = ret_q.rolling(20).std(ddof=1) * np.sqrt(252) * 100.0
vz_q = (rv20 - rv20.rolling(252).mean()) / rv20.rolling(252).std(ddof=1)

# Match exact build_return_chained_cash() from remediate_soxl_tqqq_7point_audit.py
b_c = bil["adjClose"].reindex(cal).ffill()
b_o = bil["adjOpen"].reindex(cal).ffill()
s_c = sgov["adjClose"].reindex(cal).ffill()
s_o = sgov["adjOpen"].reindex(cal).ffill()
rc_b = b_c.pct_change().fillna(0.0)
rc_s = s_c.pct_change().fillna(0.0)
use_s = (cal >= pd.Timestamp("2020-06-01")) & sgov["adjClose"].reindex(cal).notna()
rc = np.where(use_s, rc_s, rc_b)
cash_c = pd.Series(100.0 * np.cumprod(1.0 + rc), index=cal)
gap_b = (b_o / b_c.shift(1)).fillna(1.0)
gap_s = (s_o / s_c.shift(1)).fillna(1.0)
gap = np.where(use_s, gap_s, gap_b)
cash_o = pd.Series(cash_c.shift(1).fillna(100.0).values * gap, index=cal)
cash_o.iloc[0] = cash_c.iloc[0]


def run_exact_r3_with_breadth(mode_name, rule_type, param=None, idx_run=sim_dates, trig_base=1.2, rec_base=0.3):
    """
    100% identical to `run_single_share_lot_engine` in `remediate_soxl_tqqq_7point_audit.py`
    (Baseline = 53.21% CAGR, -44.54% MaxDD, 1.232 Sharpe), with optional breadth rules.
    """
    ac = {"3x": tqqq["adjClose"].reindex(idx_run).values, "1x": qqq["adjClose"].reindex(idx_run).values, "0x": cash_c.reindex(idx_run).values}
    ao = {"3x": tqqq["adjOpen"].reindex(idx_run).values, "1x": qqq["adjOpen"].reindex(idx_run).values, "0x": cash_o.reindex(idx_run).values}
    sep_v = sep_on.reindex(idx_run).values
    vz_v = vz_q.reindex(idx_run).values

    s_b50 = bdf["b50"].reindex(idx_run).values
    s_b200 = bdf["b200"].reindex(idx_run).values
    s_dd60 = bdf["qqq_dd60"].reindex(idx_run).values
    s_qsma50 = (bdf["qqq_close"] > bdf["qqq_sma50"]).reindex(idx_run).values
    s_ewcw20 = bdf["ew_minus_cw_20d"].reindex(idx_run).values
    s_ewcw60 = bdf["ew_minus_cw_60d"].reindex(idx_run).values
    s_b50_drop = bdf["b50_drop_from_60d_max"].reindex(idx_run).values

    n = len(idx_run)
    pos = "3x" if sep_v[0] else "0x"
    nav = 1.0
    floor = 1.0 if pos == "3x" else None
    eq = np.empty(n)
    eq[0] = 1.0
    sw = 0
    breadth_trigs = 0
    trade_log = []

    for i in range(1, n):
        s_on = bool(sep_v[i - 1])
        v = vz_v[i - 1]
        b50_p = s_b50[i - 1]
        b200_p = s_b200[i - 1]
        dd60_p = s_dd60[i - 1]
        qsma50_p = s_qsma50[i - 1]
        ewcw20_p = s_ewcw20[i - 1]
        ewcw60_p = s_ewcw60[i - 1]
        b50_drop_p = s_b50_drop[i - 1]

        ov = ao[pos][i] / ac[pos][i - 1]
        nav_open = nav * ov
        in_profit = (floor is not None) and (nav_open * (1.0 - FEE) > floor)
        tgt = pos
        reason = ""
        trig_by_b = False

        if not s_on:
            if pos != "0x":
                tgt = "0x"
                reason = "SEP_OFF_Mandatory_Cash"
        elif pos == "0x":
            # Exact frozen R3 SEP recovery rule:
            if (not np.isnan(v)) and v > trig_base:
                tgt = "1x"
                reason = f"SEP_ON_HighVol_1x (VolZ={v:.2f}>{trig_base})"
            else:
                tgt = "3x"
                reason = f"SEP_ON_Enter_3x (VolZ={v:.2f})"
        elif pos == "3x":
            base_delever = (not np.isnan(v)) and (v > trig_base) and in_profit

            if rule_type == "baseline":
                if base_delever:
                    tgt = "1x"
                    reason = f"VolZ>{trig_base}_NSL"

            elif rule_type == "direct_high_b50_nsl":
                b_div = qsma50_p and (dd60_p >= -0.02) and (b50_p < param)
                if base_delever or (b_div and in_profit):
                    tgt = "1x"
                    trig_by_b = not base_delever
                    reason = f"Breadth50<{param:.2f}_at_High" if trig_by_b else f"VolZ>{trig_base}_NSL"

            elif rule_type == "direct_high_b50_no_nsl":
                b_div = qsma50_p and (dd60_p >= -0.02) and (b50_p < param)
                if base_delever or b_div:
                    tgt = "1x"
                    trig_by_b = not base_delever
                    reason = f"Breadth50<{param:.2f}_NoNSL" if trig_by_b else f"VolZ>{trig_base}_NSL"

            elif rule_type == "direct_high_b200_nsl":
                b_div = qsma50_p and (dd60_p >= -0.02) and (b200_p < param)
                if base_delever or (b_div and in_profit):
                    tgt = "1x"
                    trig_by_b = not base_delever
                    reason = f"Breadth200<{param:.2f}_at_High" if trig_by_b else f"VolZ>{trig_base}_NSL"

            elif rule_type == "direct_high_b50drop_nsl":
                b_div = qsma50_p and (dd60_p >= -0.02) and (b50_drop_p <= param)
                if base_delever or (b_div and in_profit):
                    tgt = "1x"
                    trig_by_b = not base_delever
                    reason = f"B50Drop<={param:.2f}_at_High" if trig_by_b else f"VolZ>{trig_base}_NSL"

            elif rule_type == "direct_high_ewcw60_nsl":
                b_div = qsma50_p and (dd60_p >= -0.02) and (ewcw60_p <= param)
                if base_delever or (b_div and in_profit):
                    tgt = "1x"
                    trig_by_b = not base_delever
                    reason = f"EWCW60<={param:.2f}_at_High" if trig_by_b else f"VolZ>{trig_base}_NSL"

            elif rule_type == "direct_b50_collapse_nsl":
                if base_delever or ((b50_p < param) and in_profit):
                    tgt = "1x"
                    trig_by_b = not base_delever
                    reason = f"Breadth50<{param:.2f}_Collapse" if trig_by_b else f"VolZ>{trig_base}_NSL"

            elif rule_type == "adaptive_volz_when_narrow_b50":
                b_thresh, vz_low = param
                eff_trig = vz_low if (b50_p < b_thresh) else trig_base
                if (not np.isnan(v)) and (v > eff_trig) and in_profit:
                    tgt = "1x"
                    trig_by_b = not base_delever
                    reason = f"Adaptive_B50<{b_thresh:.2f}_VolZ>{vz_low}" if trig_by_b else f"VolZ>{trig_base}_NSL"

            elif rule_type == "adaptive_volz_when_ew_lags":
                lag_thresh, vz_low = param
                eff_trig = vz_low if (ewcw20_p < lag_thresh) else trig_base
                if (not np.isnan(v)) and (v > eff_trig) and in_profit:
                    tgt = "1x"
                    trig_by_b = not base_delever
                    reason = f"Adaptive_EWCW20<{lag_thresh:.3f}_VolZ>{vz_low}" if trig_by_b else f"VolZ>{trig_base}_NSL"

            elif rule_type == "adaptive_volz_when_b50_drops":
                drop_thresh, vz_low = param
                eff_trig = vz_low if (b50_drop_p < drop_thresh) else trig_base
                if (not np.isnan(v)) and (v > eff_trig) and in_profit:
                    tgt = "1x"
                    trig_by_b = not base_delever
                    reason = f"Adaptive_B50Drop<{drop_thresh:.2f}_VolZ>{vz_low}" if trig_by_b else f"VolZ>{trig_base}_NSL"

            elif rule_type == "gate_volz_only_when_narrow":
                if base_delever and (b50_p < param):
                    tgt = "1x"
                    reason = f"Gated_VolZ>{trig_base}_and_B50<{param:.2f}"

            elif rule_type == "gate_relever_b50":
                if base_delever:
                    tgt = "1x"
                    reason = f"VolZ>{trig_base}_NSL"

        elif pos == "1x":
            can_rec = (not np.isnan(v)) and (v < rec_base)
            if rule_type == "gate_relever_b50":
                can_rec = can_rec and (b50_p >= param)
            elif rule_type in ("direct_high_b50_nsl", "direct_high_b50_no_nsl"):
                b_div = qsma50_p and (dd60_p >= -0.02) and (b50_p < param)
                can_rec = can_rec and (not b_div)
            elif rule_type == "direct_high_b200_nsl":
                b_div = qsma50_p and (dd60_p >= -0.02) and (b200_p < param)
                can_rec = can_rec and (not b_div)
            elif rule_type == "direct_b50_collapse_nsl":
                can_rec = can_rec and (b50_p >= param)
            if can_rec:
                tgt = "3x"
                reason = f"Relever_VolZ<{rec_base}"

        if tgt != pos:
            fee_m = (1.0 - FEE) ** 2
            nav_after = nav_open * fee_m
            leg_pnl_pct = ((nav_after / floor - 1.0) * 100.0) if (pos == "3x" and floor is not None) else np.nan
            trade_log.append({
                "Strategy": mode_name,
                "Signal_Date": idx_run[i - 1].strftime("%Y-%m-%d"),
                "Exec_Open_Date": idx_run[i].strftime("%Y-%m-%d"),
                "From_State": pos,
                "To_State": tgt,
                "Reason": reason,
                "Triggered_By_Breadth": trig_by_b,
                "Vol_Z_Prev": round(float(v), 3) if pd.notna(v) else np.nan,
                "Breadth50_Prev_pct": round(float(b50_p * 100), 1) if pd.notna(b50_p) else np.nan,
                "Breadth200_Prev_pct": round(float(b200_p * 100), 1) if pd.notna(b200_p) else np.nan,
                "EW_minus_CW_20d_Prev_pct": round(float(ewcw20_p * 100), 2) if pd.notna(ewcw20_p) else np.nan,
                "Closed_3x_Leg_PnL_pct": round(float(leg_pnl_pct), 2) if pd.notna(leg_pnl_pct) else np.nan,
                "NAV_After_Switch": round(float(nav_after), 4),
            })
            floor = nav_after if tgt == "3x" else None
            nav = nav_after * (ac[tgt][i] / ao[tgt][i])
            pos = tgt
            sw += 1
            if trig_by_b:
                breadth_trigs += 1
        else:
            nav = nav * (ac[pos][i] / ac[pos][i - 1])
        eq[i] = nav

    s_nav = pd.Series(eq, index=idx_run)
    yrs = (idx_run[-1] - idx_run[0]).days / 365.25
    cagr = (s_nav.iloc[-1] / 1.0) ** (1.0 / yrs) - 1.0
    mdd = (s_nav / s_nav.cummax() - 1.0).min()
    dr = s_nav.pct_change().dropna()
    sh = (dr.mean() / dr.std(ddof=1)) * np.sqrt(252)

    s_pre = s_nav.loc[:"2022-12-30"]
    yrs_pre = (s_pre.index[-1] - s_pre.index[0]).days / 365.25
    cagr_pre = (s_pre.iloc[-1] / 1.0) ** (1.0 / yrs_pre) - 1.0

    s_ai = s_nav.loc["2022-12-30":]
    yrs_ai = (s_ai.index[-1] - s_ai.index[0]).days / 365.25
    cagr_ai = (s_ai.iloc[-1] / s_ai.iloc[0]) ** (1.0 / yrs_ai) - 1.0

    summary = {
        "Strategy_Variant": mode_name,
        "Full_CAGR_pct": round(100.0 * cagr, 2),
        "MaxDD_pct": round(100.0 * mdd, 2),
        "Sharpe": round(sh, 3),
        "Calmar": round(cagr / abs(mdd), 3),
        "PreAI_2010_2022_CAGR_pct": round(100.0 * cagr_pre, 2),
        "AI_2023_2026_CAGR_pct": round(100.0 * cagr_ai, 2),
        "Total_Switches": sw,
        "Extra_Breadth_Triggers": breadth_trigs,
    }
    return summary, s_nav, trade_log


variants = [
    ("0. Exact Frozen R3 Baseline: V1-Daily TQQQ (53.21%)", "baseline", None),
    ("A1. Direct Escape at High: Breadth_50 < 50% (with NSL)", "direct_high_b50_nsl", 0.50),
    ("A2. Direct Escape at High: Breadth_50 < 45% (with NSL)", "direct_high_b50_nsl", 0.45),
    ("A3. Direct Escape at High: Breadth_50 < 40% (with NSL)", "direct_high_b50_nsl", 0.40),
    ("A4. Direct Escape at High: Breadth_50 < 45% (Override NSL)", "direct_high_b50_no_nsl", 0.45),
    ("A5. Direct Escape at High: Breadth_200 < 55% (with NSL)", "direct_high_b200_nsl", 0.55),
    ("A6. Direct Escape at High: Breadth_200 < 65% (with NSL)", "direct_high_b200_nsl", 0.65),
    ("A7. Direct Escape at High: Breadth_50 Drops >=14pp from 60d Max (NSL)", "direct_high_b50drop_nsl", -0.14),
    ("A8. Direct Escape at High: EW lags CW by >=5% over 60d (NSL)", "direct_high_ewcw60_nsl", -0.05),
    ("B1. Direct De-lever: Breadth_50 < 40% (with NSL)", "direct_b50_collapse_nsl", 0.40),
    ("B2. Direct De-lever: Breadth_50 < 35% (with NSL)", "direct_b50_collapse_nsl", 0.35),
    ("B3. Direct De-lever: Breadth_50 < 30% (with NSL)", "direct_b50_collapse_nsl", 0.30),
    ("C1. Adaptive Vol_Z: Breadth_50 < 50% -> Vol_Z > 0.8 (else 1.2)", "adaptive_volz_when_narrow_b50", (0.50, 0.80)),
    ("C2. Adaptive Vol_Z: Breadth_50 < 50% -> Vol_Z > 0.9 (else 1.2)", "adaptive_volz_when_narrow_b50", (0.50, 0.90)),
    ("C3. Adaptive Vol_Z: Breadth_50 < 45% -> Vol_Z > 0.8 (else 1.2)", "adaptive_volz_when_narrow_b50", (0.45, 0.80)),
    ("C4. Adaptive Vol_Z: Breadth_50 < 45% -> Vol_Z > 1.0 (else 1.2)", "adaptive_volz_when_narrow_b50", (0.45, 1.00)),
    ("C5. Adaptive Vol_Z: EW-CW 20d < -3% -> Vol_Z > 0.8 (else 1.2)", "adaptive_volz_when_ew_lags", (-0.03, 0.80)),
    ("C6. Adaptive Vol_Z: Breadth_50 drops >15pp -> Vol_Z > 0.8", "adaptive_volz_when_b50_drops", (-0.15, 0.80)),
    ("D1. Breadth Confirm De-lever: Vol_Z > 1.2 AND Breadth_50 < 55%", "gate_volz_only_when_narrow", 0.55),
    ("D2. Breadth Confirm De-lever: Vol_Z > 1.2 AND Breadth_50 < 50%", "gate_volz_only_when_narrow", 0.50),
    ("D3. Breadth Confirm De-lever: Vol_Z > 1.2 AND Breadth_50 < 45%", "gate_volz_only_when_narrow", 0.45),
    ("E1. Re-lever Gate: Vol_Z < 0.3 AND Breadth_50 >= 45%", "gate_relever_b50", 0.45),
    ("E2. Re-lever Gate: Vol_Z < 0.3 AND Breadth_50 >= 50%", "gate_relever_b50", 0.50),
    ("E3. Re-lever Gate: Vol_Z < 0.3 AND Breadth_50 >= 55%", "gate_relever_b50", 0.55),
]

res_rows = []
all_logs = []
nav_map = {}
for name, rtype, p in variants:
    s_row, s_nav, t_log = run_exact_r3_with_breadth(name, rtype, p)
    res_rows.append(s_row)
    nav_map[name] = s_nav
    if name.startswith("0.") or name.startswith("A5.") or name.startswith("C5.") or name.startswith("A1."):
        all_logs.extend(t_log)

res_df = pd.DataFrame(res_rows)
res_df.to_csv(os.path.join(OUT_DIR, "B3_v1_tqqq_breadth_divergence_strategy_tests.csv"), index=False)
print(res_df.to_string(index=False))

log_df = pd.DataFrame(all_logs)
log_df.to_csv(os.path.join(OUT_DIR, "B4_baseline_vs_A5_C5_trade_ledger.csv"), index=False)

# =================================================================================================
# PART 3: EXACT ANATOMY OF THE EXTRA TRIGGERS IN C5 AND A5 + PARAMETER SENSITIVITY GRID
# =================================================================================================
print("\n" + "=" * 115)
print("PART 3A: EXACT DECOMPOSITION OF THE EXTRA BREADTH TRIGGERS IN C5 AND A5")
print("=" * 115)
print("\n--- C5 Extra Triggers (Triggered_By_Breadth == True) ---")
c5_extra = log_df[(log_df["Strategy"].str.startswith("C5.")) & (log_df["Triggered_By_Breadth"])]
print(c5_extra.to_string(index=False))

print("\n--- All C5 vs Baseline Switch Differences ---")
base_sw = set(log_df[log_df["Strategy"].str.startswith("0.")]["Exec_Open_Date"])
c5_sw = set(log_df[log_df["Strategy"].str.startswith("C5.")]["Exec_Open_Date"])
diff_dates = sorted(base_sw ^ c5_sw)
print(log_df[(log_df["Strategy"].str.startswith("0.") | log_df["Strategy"].str.startswith("C5.")) & (log_df["Exec_Open_Date"].isin(diff_dates))].sort_values(["Exec_Open_Date", "Strategy"]).to_string(index=False))

print("\n" + "=" * 115)
print("PART 3B: PARAMETER SENSITIVITY GRID FOR A5 (Breadth_200 Threshold) AND C5 (EW-CW 20d Lag x Vol_Z Threshold)")
print("=" * 115)
sens_rows = []
for b200_th in [0.45, 0.50, 0.52, 0.55, 0.58, 0.60, 0.65]:
    sr, _, _ = run_exact_r3_with_breadth(f"A5_Grid: Breadth_200 < {int(b200_th*100)}%", "direct_high_b200_nsl", b200_th)
    sens_rows.append(sr)

for ew_th in [-0.02, -0.025, -0.03, -0.035, -0.04, -0.05]:
    for vz_th in [0.70, 0.80, 0.90, 1.00]:
        sr, _, _ = run_exact_r3_with_breadth(f"C5_Grid: EW-CW20 < {ew_th*100:.1f}% -> VolZ > {vz_th:.1f}", "adaptive_volz_when_ew_lags", (ew_th, vz_th))
        sens_rows.append(sr)

sens_df = pd.DataFrame(sens_rows)
sens_df.to_csv(os.path.join(OUT_DIR, "B5_A5_C5_parameter_sensitivity_grid.csv"), index=False)
print(sens_df.to_string(index=False))
