#!/usr/bin/env python3
"""
audit_soxl_and_vol_estimators.py — Independent From-Scratch Audit of:
  1. High-Low / OHLC vs Close-to-Close Volatility Estimators on V1-Daily TQQQ SEP (T1, T1B)
  2. 1x Underlying (QQQ / SOXX) vs 3x ETF Own (TQQQ / SOXL) Vol_Z Source Comparison (T2)
  3. SOXL (3x Semiconductor ETF) V1-Daily Standalone Backtest & De-levering Target Matrix (1x SOXX vs 1x QQQ vs 3x TQQQ vs 0x Cash) (T3)
  4. SOXL Standalone 2D (Trig x Rec) Parameter Plateau & 2024-2025 Drawdown Anatomy (T4)
  5. TQQQ + SOXL Multi-Weight x Rebalance-Frequency 2D Plateau (Exact Open Execution, Overnight/Intraday Split + 10bp/side) (T5)
  6. 75% TQQQ + 25% SOXL (Annual Rebalance, Both De-levering to 1x QQQ) x SOXL (Trig, Rec) 64-Cell Plateau (T6)
  7. Complete Trade-by-Trade Ledgers & Daily NAV Series for External Audit Verification (T7)

Zero shared strategy code: rebuilds FOMC SEP, Vol_Z estimators, and exact next-day adjOpen execution from raw Tiingo JSON/CSV files.
"""
import json
import os
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
ETF_DIR = os.path.join(ROOT, "outputs", "remediation_full_audit_20261104", "tiingo_etfs")
SEP_CSV = os.path.join(ROOT, "outputs", "expabc_independent_audit_20261104", "02_sep_alfred_medians.csv")
OUT_DIR = os.path.join(ROOT, "outputs", "soxl_and_vol_estimators_audit_20261126")
os.makedirs(OUT_DIR, exist_ok=True)

FEE = 0.0010
LOG = []


def say(s=""):
    print(s)
    LOG.append(str(s))


def load_etf(sym):
    df = pd.DataFrame(json.load(open(os.path.join(ETF_DIR, f"{sym}.json"))))
    df["date"] = pd.to_datetime(df["date"].astype(str).str[:10])
    df = df.sort_values("date").drop_duplicates("date", keep="last").set_index("date")
    for col in ["open", "high", "low", "close", "adjOpen", "adjHigh", "adjLow", "adjClose"]:
        if col in df.columns:
            df[col] = df[col].astype(float)
    return df


QQQ = load_etf("QQQ")
TQQQ = load_etf("TQQQ")
SOXX = load_etf("SOXX")
SOXL = load_etf("SOXL")
BIL = load_etf("BIL")
SGOV = load_etf("SGOV")
HYG = load_etf("HYG")
IEF = load_etf("IEF")

CASH = BIL.copy()
CASH.loc[CASH.index.intersection(SGOV.index)] = SGOV.loc[CASH.index.intersection(SGOV.index)]

IDX_TQQQ = TQQQ.index.intersection(QQQ.index).intersection(CASH.index)
IDX_TQQQ = IDX_TQQQ[(IDX_TQQQ >= "2010-02-11") & (IDX_TQQQ <= "2026-11-03")]

IDX_COMMON = SOXL.index.intersection(SOXX.index).intersection(TQQQ.index).intersection(QQQ.index).intersection(CASH.index)
IDX_COMMON = IDX_COMMON[(IDX_COMMON >= "2010-03-11") & (IDX_COMMON <= "2026-11-03")]


def build_sep_series(idx):
    sep_raw = pd.read_csv(SEP_CSV)
    sep_raw = sep_raw[sep_raw["has_medians"] == True].reset_index(drop=True)  # noqa: E712
    state, prev_f, prev_p, flips = True, {}, {}, {}
    for _, r in sep_raw.iterrows():
        dt = pd.Timestamp(r["date"])
        ty = int(r["target_year"])
        f = {dt.year + k: float(v) for k, v in enumerate(json.loads(r["ffr_medians"]))}
        p = {dt.year + k: float(v) for k, v in enumerate(json.loads(r["pce_medians"]))}
        cr, cp, pr, pp = f.get(ty), p.get(ty), prev_f.get(ty), prev_p.get(ty)
        if None not in (cr, cp, pr, pp):
            if state and cr > pr and cp > pp and cp > 2.0:
                state = False
            elif (not state) and cr <= pr:
                state = True
        flips[dt] = state
        prev_f, prev_p = f, p
    out = pd.Series(True, index=idx)
    cur = True
    for d in idx:
        cur = flips.get(d, cur)
        out.loc[d] = cur
    return out


SEP_TQQQ = build_sep_series(IDX_TQQQ)
SEP_COMMON = build_sep_series(IDX_COMMON)


def calc_vol_z(df, method="c2c", win=20, z_win=252, min_p=252):
    o = df["adjOpen"]
    h = df["adjHigh"] if "adjHigh" in df.columns else df["high"] * df["adjClose"] / df["close"]
    l = df["adjLow"] if "adjLow" in df.columns else df["low"] * df["adjClose"] / df["close"]
    c = df["adjClose"]
    c_prev = c.shift(1)
    if method == "c2c":
        rv = c.pct_change().rolling(win).std(ddof=1) * np.sqrt(252) * 100
    elif method == "o2c":
        rv = (c / o - 1.0).rolling(win).std(ddof=1) * np.sqrt(252) * 100
    elif method == "parkinson_hl":
        hl2 = np.log(h / l) ** 2
        rv = np.sqrt(hl2.rolling(win).mean() / (4.0 * np.log(2.0)) * 252) * 100
    elif method == "tr_rms":
        tr_hi = np.maximum(h, c_prev)
        tr_lo = np.minimum(l, c_prev)
        tr2 = np.log(tr_hi / tr_lo) ** 2
        rv = np.sqrt(tr2.rolling(win).mean() / (4.0 * np.log(2.0)) * 252) * 100
    elif method == "atr_pct":
        tr = np.maximum(h - l, np.maximum((h - c_prev).abs(), (l - c_prev).abs())) / c
        rv = tr.rolling(win).mean() * np.sqrt(252) * 100
    elif method == "garman_klass":
        hl2 = 0.5 * (np.log(h / l) ** 2)
        co2 = (2.0 * np.log(2.0) - 1.0) * (np.log(c / o) ** 2)
        gk = (hl2 - co2).clip(lower=0)
        rv = np.sqrt(gk.rolling(win).mean() * 252) * 100
    elif method == "yang_zhang":
        oj2 = np.log(o / c_prev) ** 2
        hl2 = 0.5 * (np.log(h / l) ** 2)
        co2 = (2.0 * np.log(2.0) - 1.0) * (np.log(c / o) ** 2)
        gkyz = (oj2 + hl2 - co2).clip(lower=0)
        rv = np.sqrt(gkyz.rolling(win).mean() * 252) * 100
    else:
        raise ValueError(f"Unknown method: {method}")
    vz = (rv - rv.rolling(z_win, min_periods=min_p).mean()) / rv.rolling(z_win, min_periods=min_p).std(ddof=1)
    return vz, rv


def calc_metrics(eq_ser, idx):
    yrs = (idx[-1] - idx[0]).days / 365.25
    cagr = round(float((eq_ser.iloc[-1] ** (1.0 / yrs) - 1.0) * 100), 2)
    mult = round(float(eq_ser.iloc[-1]), 1)
    dd_ser = (eq_ser / eq_ser.cummax() - 1.0) * 100
    max_dd = round(float(dd_ser.min()), 2)
    trough_dt = dd_ser.idxmin()
    peak_dt = eq_ser.loc[:trough_dt].idxmax()
    dr = eq_ser.pct_change().dropna()
    sharpe = round(float((dr.mean() / dr.std(ddof=1)) * np.sqrt(252)), 3)
    s19 = eq_ser.loc[:"2019-12-31"]
    yrs19 = (s19.index[-1] - s19.index[0]).days / 365.25
    cagr19 = round(float(((s19.iloc[-1] / s19.iloc[0]) ** (1.0 / yrs19) - 1.0) * 100), 2)
    s20 = eq_ser.loc["2019-12-31":]
    yrs20 = (s20.index[-1] - s20.index[0]).days / 365.25
    cagr20 = round(float(((s20.iloc[-1] / s20.iloc[0]) ** (1.0 / yrs20) - 1.0) * 100), 2)
    r2022 = round(float((eq_ser.loc["2022-12-30"] / eq_ser.loc["2021-12-31"] - 1.0) * 100), 2)
    s24 = eq_ser.loc["2024-01-01":]
    dd24 = round(float(((s24 / s24.cummax() - 1.0) * 100).min()), 2)
    return {
        "Full_CAGR_%": cagr,
        "Total_Mult_x": mult,
        "CAGR_2010_19_%": cagr19,
        "CAGR_2020_26_%": cagr20,
        "MaxDD_%": max_dd,
        "MaxDD_Window": f"{peak_dt.date()}->{trough_dt.date()}",
        "MaxDD_2024_26_%": dd24,
        "Ret_2022_%": r2022,
        "Daily_Sharpe": sharpe,
    }


def run_v1_engine(df_3x, df_1x, vz_ser, idx, sep_ser, trig=1.2, rec=0.3, use_nsl=True, gate_ser=None, pure_sep=False, delev_to="1x"):
    ac = {"3x": df_3x["adjClose"].reindex(idx).values, "1x": df_1x["adjClose"].reindex(idx).values, "0x": CASH["adjClose"].reindex(idx).values}
    ao = {"3x": df_3x["adjOpen"].reindex(idx).values, "1x": df_1x["adjOpen"].reindex(idx).values, "0x": CASH["adjOpen"].reindex(idx).values}
    sep_v = sep_ser.reindex(idx).values
    vz_v = vz_ser.reindex(idx).values if vz_ser is not None else np.zeros(len(idx))
    g_v = gate_ser.reindex(idx).values if gate_ser is not None else np.zeros(len(idx), dtype=bool)
    n = len(idx)
    pos = "3x" if sep_v[0] else "0x"
    nav = 1.0
    floor = 1.0 if pos == "3x" else None
    eq = np.empty(n)
    eq[0] = 1.0
    ov_mult = np.ones(n)
    in_mult = np.ones(n)
    sw_flags = [False] * n
    trades = []
    wins, tot_3x = 0, 0
    entry_dt = idx[0]

    for i in range(1, n):
        s_on = bool(sep_v[i - 1])
        v = vz_v[i - 1]
        g = bool(g_v[i - 1])
        ov = ao[pos][i] / ac[pos][i - 1]
        nav_open = nav * ov
        in_profit = True if (not use_nsl) else ((floor is not None) and (nav_open * (1.0 - FEE) > floor))
        tgt = pos
        if not s_on:
            tgt = "0x"
        elif pure_sep:
            tgt = "3x"
        elif pos == "0x":
            tgt = delev_to if (not np.isnan(v) and v > trig) else "3x"
        elif pos == "3x":
            if (not np.isnan(v)) and v > trig and (not g) and in_profit:
                tgt = delev_to
        elif pos == delev_to:
            if (not np.isnan(v)) and v < rec:
                tgt = "3x"

        if tgt != pos:
            fee_m = (1.0 - FEE) if (pos == "0x" or tgt == "0x") else (1.0 - FEE) ** 2
            ov_eff = ov * fee_m
            nav_after = nav * ov_eff
            leg_ret = None
            if pos == "3x" and floor is not None:
                tot_3x += 1
                if nav_after > floor:
                    wins += 1
                leg_ret = round((nav_after / floor - 1.0) * 100, 2)
            trades.append({
                "Signal_Close": str(idx[i - 1].date()),
                "Exec_Open": str(idx[i].date()),
                "From_State": pos,
                "To_State": tgt,
                "SEP_On": s_on,
                "Vol_Z": round(float(v), 3) if not np.isnan(v) else None,
                "3x_Entry_Date": str(entry_dt.date()) if pos == "3x" else None,
                "3x_Closed_Net_Ret_%": leg_ret,
            })
            if tgt == "3x":
                floor = nav_after
                entry_dt = idx[i]
            else:
                floor = None
            intra = ac[tgt][i] / ao[tgt][i]
            nav = nav_after * intra
            pos = tgt
            sw_flags[i] = True
        else:
            ov_eff = ov
            intra = ac[pos][i] / ao[pos][i]
            nav = nav * (ac[pos][i] / ac[pos][i - 1])

        ov_mult[i] = ov_eff
        in_mult[i] = intra
        eq[i] = nav

    eq_ser = pd.Series(eq, index=idx)
    return eq_ser, ov_mult, in_mult, sw_flags, trades, f"{wins}/{tot_3x}"


# =============================================================================
# T1. Volatility Estimators (Close-to-Close vs High-Low / OHLC) & Window Sweep
# =============================================================================
say("=== T1. Volatility Estimators on V1-Daily TQQQ SEP (2010-02-11 .. 2026-11-03) ===")
vol_methods = [
    ("1. Close-to-Close (Current Frozen Baseline)", "c2c"),
    ("2. Open-to-Close (Intraday Body Only)", "o2c"),
    ("3. Parkinson High-Low (Intraday H/L Range Only)", "parkinson_hl"),
    ("4. True Range RMS (High-Low + Overnight Gap)", "tr_rms"),
    ("5. Classic ATR% (Average True Range / Close)", "atr_pct"),
    ("6. Garman-Klass (Intraday OHLC)", "garman_klass"),
    ("7. Yang-Zhang / GK-YZ (Full OHLC + Overnight Gap)", "yang_zhang"),
]

t1_rows = []
for lbl, m in vol_methods:
    vz20, _ = calc_vol_z(QQQ, m, 20)
    eq20, _, _, _, tr20, wr20 = run_v1_engine(TQQQ, QQQ, vz20, IDX_TQQQ, SEP_TQQQ, 1.2, 0.3)
    mt20 = calc_metrics(eq20, IDX_TQQQ)
    # 15-cell plateau at win=20
    p_c, p_d = [], []
    for tr in [1.0, 1.1, 1.2, 1.3]:
        for rc in [0.0, 0.2, 0.3, 0.5, 0.7]:
            if tr == 1.3 and rc == 0.7:
                continue
            eq_i, _, _, _, _, _ = run_v1_engine(TQQQ, QQQ, vz20, IDX_TQQQ, SEP_TQQQ, tr, rc)
            mt_i = calc_metrics(eq_i, IDX_TQQQ)
            p_c.append(mt_i["Full_CAGR_%"])
            p_d.append(mt_i["MaxDD_%"])
    row = {
        "Estimator": lbl,
        "W20_CAGR_%": mt20["Full_CAGR_%"],
        "W20_MaxDD_%": mt20["MaxDD_%"],
        "W20_Sharpe": mt20["Daily_Sharpe"],
        "W20_Switches": len(tr20),
        "15Cell_Median_CAGR_%": round(float(np.median(p_c)), 2),
        "15Cell_Min_CAGR_%": min(p_c),
        "15Cell_Worst_MaxDD_%": min(p_d),
    }
    for w in [8, 10, 12, 15, 20, 25, 30]:
        vzw, _ = calc_vol_z(QQQ, m, w)
        eq_w, _, _, _, _, _ = run_v1_engine(TQQQ, QQQ, vzw, IDX_TQQQ, SEP_TQQQ, 1.2, 0.3)
        mt_w = calc_metrics(eq_w, IDX_TQQQ)
        row[f"W{w}_CAGR_%"] = mt_w["Full_CAGR_%"]
        row[f"W{w}_MaxDD_%"] = mt_w["MaxDD_%"]
    t1_rows.append(row)

df_t1 = pd.DataFrame(t1_rows)
say(df_t1.to_string(index=False))
df_t1.to_csv(os.path.join(OUT_DIR, "T1_volatility_estimators_and_window_sweep.csv"), index=False)

# T1B: Jan-Feb 2020 10-day Close-to-Close vs Parkinson High-Low vs True Range RMS Diagnostic
vz10_c2c, rv10_c2c = calc_vol_z(QQQ, "c2c", 10)
vz10_hl, rv10_hl = calc_vol_z(QQQ, "parkinson_hl", 10)
vz10_tr, rv10_tr = calc_vol_z(QQQ, "tr_rms", 10)
df_t1b = pd.DataFrame({
    "Date": QQQ.loc["2020-01-24":"2020-02-28"].index.strftime("%Y-%m-%d"),
    "QQQ_AdjClose": QQQ.loc["2020-01-24":"2020-02-28", "adjClose"].round(2).values,
    "QQQ_Daily_Ret_%": (QQQ["adjClose"].pct_change().loc["2020-01-24":"2020-02-28"] * 100).round(2).values,
    "RV10_C2C_%": rv10_c2c.loc["2020-01-24":"2020-02-28"].round(2).values,
    "VZ10_C2C": vz10_c2c.loc["2020-01-24":"2020-02-28"].round(2).values,
    "RV10_ParkinsonHL_%": rv10_hl.loc["2020-01-24":"2020-02-28"].round(2).values,
    "VZ10_ParkinsonHL": vz10_hl.loc["2020-01-24":"2020-02-28"].round(2).values,
    "RV10_TrueRange_%": rv10_tr.loc["2020-01-24":"2020-02-28"].round(2).values,
    "VZ10_TrueRange": vz10_tr.loc["2020-01-24":"2020-02-28"].round(2).values,
})
df_t1b.to_csv(os.path.join(OUT_DIR, "T1b_jan_feb_2020_c2c_vs_hl_tr_diagnostic.csv"), index=False)

# =============================================================================
# T2. 1x Underlying Vol_Z vs 3x ETF Own Vol_Z Source Comparison
# =============================================================================
say("\n=== T2. 1x Underlying Vol_Z (QQQ/SOXX) vs 3x ETF Own Vol_Z (TQQQ/SOXL) ===")
r_qqq = QQQ["adjClose"].pct_change()
r_tqqq_raw = TQQQ["adjClose"].pct_change()
r_tqqq_warm = pd.concat([r_qqq.loc[r_qqq.index < "2010-02-12"] * 3.0, r_tqqq_raw.loc["2010-02-12":]]).sort_index()

r_soxx = SOXX["adjClose"].pct_change()
r_soxl_raw = SOXL["adjClose"].pct_change()
r_soxl_warm = pd.concat([r_soxx.loc[r_soxx.index < "2010-03-12"] * 3.0, r_soxl_raw.loc["2010-03-12":]]).sort_index()


def vz_from_ret(r_ser, min_p=252):
    rv = r_ser.rolling(20).std(ddof=1) * np.sqrt(252) * 100
    return (rv - rv.rolling(252, min_periods=min_p).mean()) / rv.rolling(252, min_periods=min_p).std(ddof=1)


vz_qqq_1x = vz_from_ret(r_qqq, 252)
vz_tqqq_3x_warm = vz_from_ret(r_tqqq_warm, 252)
vz_tqqq_3x_raw = vz_from_ret(r_tqqq_raw, 60)

vz_soxx_1x = vz_from_ret(r_soxx, 252)
vz_soxl_3x_warm = vz_from_ret(r_soxl_warm, 252)
vz_soxl_3x_raw = vz_from_ret(r_soxl_raw, 60)

corr_tqqq = round(float(vz_qqq_1x.reindex(IDX_TQQQ).corr(vz_tqqq_3x_warm.reindex(IDX_TQQQ))), 5)
corr_soxl = round(float(vz_soxx_1x.reindex(IDX_COMMON).corr(vz_soxl_3x_warm.reindex(IDX_COMMON))), 5)
say(f"Correlation Vol_Z(1x QQQ) vs Vol_Z(3x TQQQ): {corr_tqqq}")
say(f"Correlation Vol_Z(1x SOXX) vs Vol_Z(3x SOXL): {corr_soxl}")

t2_rows = []
for lbl, d3, d1, vz_s, idx_u, sep_u, cr in [
    ("TQQQ Strategy — Vol_Z from 1x QQQ (Frozen Standard)", TQQQ, QQQ, vz_qqq_1x, IDX_TQQQ, SEP_TQQQ, 1.0),
    ("TQQQ Strategy — Vol_Z from 3x TQQQ (with 2009 3x Warm-up)", TQQQ, QQQ, vz_tqqq_3x_warm, IDX_TQQQ, SEP_TQQQ, corr_tqqq),
    ("TQQQ Strategy — Vol_Z from 3x TQQQ (Raw Post-Inception Only)", TQQQ, QQQ, vz_tqqq_3x_raw, IDX_TQQQ, SEP_TQQQ, corr_tqqq),
    ("SOXL Strategy — Vol_Z from 1x SOXX (Standard, -> 1x SOXX)", SOXL, SOXX, vz_soxx_1x, IDX_COMMON, SEP_COMMON, 1.0),
    ("SOXL Strategy — Vol_Z from 3x SOXL (with 2009 3x Warm-up, -> 1x SOXX)", SOXL, SOXX, vz_soxl_3x_warm, IDX_COMMON, SEP_COMMON, corr_soxl),
    ("SOXL Strategy — Vol_Z from 3x SOXL (Raw Post-Inception Only, -> 1x SOXX)", SOXL, SOXX, vz_soxl_3x_raw, IDX_COMMON, SEP_COMMON, corr_soxl),
]:
    eq_u, _, _, _, tr_u, wr_u = run_v1_engine(d3, d1, vz_s, idx_u, sep_u, 1.2, 0.3)
    mt_u = calc_metrics(eq_u, idx_u)
    t2_rows.append({"Variant": lbl, "Corr_vs_1x_VolZ": cr, **mt_u, "Switches": len(tr_u), "Closed_3x_Wins": wr_u})

df_t2 = pd.DataFrame(t2_rows)
say(df_t2.to_string(index=False))
df_t2.to_csv(os.path.join(OUT_DIR, "T2_1x_vs_3x_vol_z_source_comparison.csv"), index=False)

# =============================================================================
# T3. SOXL Standalone V1-Daily Variants & De-levering Target Matrix (2010-03-11 .. 2026-11-03)
# =============================================================================
say("\n=== T3. SOXL Standalone V1-Daily Variants & De-levering Target Matrix (2010-03-11 .. 2026-11-03) ===")
cal_hi = HYG.index.intersection(IEF.index)
rat_hi = HYG["adjClose"].reindex(cal_hi) / IEF["adjClose"].reindex(cal_hi)
sma200_hi = rat_hi.rolling(200, min_periods=200).mean()
g_hi = (rat_hi > sma200_hi).astype(float)
g_hi[sma200_hi.isna()] = np.nan
GATE_HYG_IEF = g_hi.reindex(IDX_COMMON).ffill().fillna(0.0).astype(bool)

bh_soxx = SOXX["adjClose"].reindex(IDX_COMMON) / SOXX["adjClose"].reindex(IDX_COMMON).iloc[0]
bh_soxl = SOXL["adjClose"].reindex(IDX_COMMON) / SOXL["adjClose"].reindex(IDX_COMMON).iloc[0]
bh_qqq = QQQ["adjClose"].reindex(IDX_COMMON) / QQQ["adjClose"].reindex(IDX_COMMON).iloc[0]
bh_tqqq = TQQQ["adjClose"].reindex(IDX_COMMON) / TQQQ["adjClose"].reindex(IDX_COMMON).iloc[0]

# Also simulate SOXL -> TQQQ (if QQQ calm) -> QQQ ladder
def run_soxl_tqqq_qqq_ladder():
    ac = {
        "SOXL": SOXL["adjClose"].reindex(IDX_COMMON).values,
        "TQQQ": TQQQ["adjClose"].reindex(IDX_COMMON).values,
        "QQQ": QQQ["adjClose"].reindex(IDX_COMMON).values,
        "CASH": CASH["adjClose"].reindex(IDX_COMMON).values,
    }
    ao = {
        "SOXL": SOXL["adjOpen"].reindex(IDX_COMMON).values,
        "TQQQ": TQQQ["adjOpen"].reindex(IDX_COMMON).values,
        "QQQ": QQQ["adjOpen"].reindex(IDX_COMMON).values,
        "CASH": CASH["adjOpen"].reindex(IDX_COMMON).values,
    }
    sep_v = SEP_COMMON.values
    vs_v = vz_soxx_1x.reindex(IDX_COMMON).values
    vq_v = vz_qqq_1x.reindex(IDX_COMMON).values
    n = len(IDX_COMMON)
    pos, nav, floor = "SOXL", 1.0, 1.0
    eq = np.empty(n)
    eq[0] = 1.0
    sw = 0
    for i in range(1, n):
        s_on = bool(sep_v[i - 1])
        vs, vq = vs_v[i - 1], vq_v[i - 1]
        nav_open = nav * (ao[pos][i] / ac[pos][i - 1])
        in_profit = (floor is not None) and (nav_open * (1.0 - FEE) > floor)
        tgt = pos
        if not s_on:
            tgt = "CASH"
        else:
            if pos == "CASH":
                tgt = "SOXL" if (np.isnan(vs) or vs <= 1.2) else ("TQQQ" if (np.isnan(vq) or vq <= 1.2) else "QQQ")
            elif pos == "SOXL":
                if (not np.isnan(vs)) and vs > 1.2 and in_profit:
                    tgt = "TQQQ" if (np.isnan(vq) or vq <= 1.2) else "QQQ"
            elif pos == "TQQQ":
                if (not np.isnan(vs)) and vs < 0.3:
                    tgt = "SOXL"
                elif (not np.isnan(vq)) and vq > 1.2 and in_profit:
                    tgt = "QQQ"
            elif pos == "QQQ":
                if (not np.isnan(vs)) and vs < 0.3:
                    tgt = "SOXL"
                elif (not np.isnan(vq)) and vq < 0.3:
                    tgt = "TQQQ"
        if tgt != pos:
            fee_m = (1.0 - FEE) if (pos == "CASH" or tgt == "CASH") else (1.0 - FEE) ** 2
            nav_after = nav_open * fee_m
            if tgt in ("SOXL", "TQQQ") and pos in ("QQQ", "CASH"):
                floor = nav_after
            elif tgt in ("QQQ", "CASH"):
                floor = None
            nav = nav_after * (ac[tgt][i] / ao[tgt][i])
            pos = tgt
            sw += 1
        else:
            nav = nav * (ac[pos][i] / ac[pos][i - 1])
        eq[i] = nav
    return pd.Series(eq, index=IDX_COMMON), sw


eq_ladder, sw_ladder = run_soxl_tqqq_qqq_ladder()
vz_soxx_hl20, _ = calc_vol_z(SOXX, "parkinson_hl", 20)
vz_soxx_hl10, _ = calc_vol_z(SOXX, "parkinson_hl", 10)

t3_specs = [
    ("0a. SOXX (1x Semiconductor) Buy & Hold", bh_soxx, 0, "-"),
    ("0b. SOXL (3x Semiconductor) Buy & Hold", bh_soxl, 0, "-"),
    ("1. SOXL Pure FOMC SEP Only (SEP=ON -> 3x SOXL, OFF -> Cash)", *run_v1_engine(SOXL, SOXX, None, IDX_COMMON, SEP_COMMON, pure_sep=True)[::4], "-"),
]

t3_rows = [
    {"Strategy": "0a. SOXX (1x Semiconductor) Buy & Hold", **calc_metrics(bh_soxx, IDX_COMMON), "Switches": 0, "Closed_3x_Wins": "-"},
    {"Strategy": "0b. SOXL (3x Semiconductor) Buy & Hold", **calc_metrics(bh_soxl, IDX_COMMON), "Switches": 0, "Closed_3x_Wins": "-"},
]

for name, kwargs in [
    ("1. SOXL Pure FOMC SEP Only (SEP=ON -> SOXL, OFF -> Cash)", dict(df_3x=SOXL, df_1x=SOXX, vz_ser=None, pure_sep=True)),
    ("2. SOXL + SEP + SOXX Vol_Z(1.2/0.3) NO NSL (Accept Loss -> 1x SOXX)", dict(df_3x=SOXL, df_1x=SOXX, vz_ser=vz_soxx_1x, use_nsl=False)),
    ("3a. SOXL V1-Daily (Vol_Z on SOXX -> De-lever to 1x SOXX)", dict(df_3x=SOXL, df_1x=SOXX, vz_ser=vz_soxx_1x, use_nsl=True)),
    ("3b. SOXL V1-Daily (Vol_Z on SOXX -> De-lever to 1x QQQ)", dict(df_3x=SOXL, df_1x=QQQ, vz_ser=vz_soxx_1x, use_nsl=True)),
    ("3c. SOXL V1-Daily (Vol_Z on QQQ  -> De-lever to 1x SOXX)", dict(df_3x=SOXL, df_1x=SOXX, vz_ser=vz_qqq_1x, use_nsl=True)),
    ("3d. SOXL V1-Daily (Vol_Z on QQQ  -> De-lever to 1x QQQ)", dict(df_3x=SOXL, df_1x=QQQ, vz_ser=vz_qqq_1x, use_nsl=True)),
    ("3e. SOXL V1-Daily (Vol_Z on SOXX -> De-lever to 0x Cash)", dict(df_3x=SOXL, df_1x=SOXX, vz_ser=vz_soxx_1x, use_nsl=True, delev_to="0x")),
]:
    eq_s, _, _, _, tr_s, wr_s = run_v1_engine(idx=IDX_COMMON, sep_ser=SEP_COMMON, **kwargs)
    t3_rows.append({"Strategy": name, **calc_metrics(eq_s, IDX_COMMON), "Switches": len(tr_s), "Closed_3x_Wins": wr_s})
    if name.startswith("3b."):
        pd.DataFrame(tr_s).to_csv(os.path.join(OUT_DIR, "T7_soxl_v1_to_qqq_trade_ledger.csv"), index=False)

t3_rows.append({"Strategy": "3f. SOXL -> 3x TQQQ (if QQQ calm) -> 1x QQQ Ladder", **calc_metrics(eq_ladder, IDX_COMMON), "Switches": sw_ladder, "Closed_3x_Wins": "-"})

for name, kwargs in [
    ("4a. SOXL V1-Daily + Parkinson High-Low Vol_Z (20d, -> 1x SOXX)", dict(df_3x=SOXL, df_1x=SOXX, vz_ser=vz_soxx_hl20, use_nsl=True)),
    ("4b. SOXL V1-Daily + Parkinson High-Low Vol_Z (10d, -> 1x SOXX)", dict(df_3x=SOXL, df_1x=SOXX, vz_ser=vz_soxx_hl10, use_nsl=True)),
    ("5. SOXL V1-Daily + HYG/IEF SMA200 Gate (-> 1x SOXX)", dict(df_3x=SOXL, df_1x=SOXX, vz_ser=vz_soxx_1x, use_nsl=True, gate_ser=GATE_HYG_IEF)),
    ("Ref-1. QQQ (1x Nasdaq-100) Buy & Hold (Same Dates)", None),
    ("Ref-2. TQQQ (3x Nasdaq-100) Buy & Hold (Same Dates)", None),
    ("Ref-3. TQQQ Pure FOMC SEP Only (Same Dates)", dict(df_3x=TQQQ, df_1x=QQQ, vz_ser=None, pure_sep=True)),
    ("Ref-4. TQQQ Frozen V1-Daily (SEP + QQQ Vol_Z 1.2/0.3 + NSL, Same Dates)", dict(df_3x=TQQQ, df_1x=QQQ, vz_ser=vz_qqq_1x, use_nsl=True)),
]:
    if name.startswith("Ref-1"):
        t3_rows.append({"Strategy": name, **calc_metrics(bh_qqq, IDX_COMMON), "Switches": 0, "Closed_3x_Wins": "-"})
    elif name.startswith("Ref-2"):
        t3_rows.append({"Strategy": name, **calc_metrics(bh_tqqq, IDX_COMMON), "Switches": 0, "Closed_3x_Wins": "-"})
    else:
        eq_s, _, _, _, tr_s, wr_s = run_v1_engine(idx=IDX_COMMON, sep_ser=SEP_COMMON, **kwargs)
        t3_rows.append({"Strategy": name, **calc_metrics(eq_s, IDX_COMMON), "Switches": len(tr_s), "Closed_3x_Wins": wr_s})

df_t3 = pd.DataFrame(t3_rows)
say(df_t3.to_string(index=False))
df_t3.to_csv(os.path.join(OUT_DIR, "T3_soxl_standalone_variants_vs_tqqq.csv"), index=False)

# =============================================================================
# T4. SOXL Standalone 2D (Trig x Rec) Parameter Plateau (De-levering to 1x QQQ)
# =============================================================================
say("\n=== T4. SOXL Standalone 2D (Trig x Rec) Parameter Plateau (Vol_Z on SOXX -> 1x QQQ) ===")
trigs_t4 = [0.6, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6]
recs_t4 = [-0.4, -0.2, -0.1, 0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.7]
t4_rows = []
for tr in trigs_t4:
    for rc in recs_t4:
        if rc >= tr:
            continue
        eq_cell, _, _, _, tr_cell, wr_cell = run_v1_engine(SOXL, QQQ, vz_soxx_1x, IDX_COMMON, SEP_COMMON, tr, rc)
        mt_cell = calc_metrics(eq_cell, IDX_COMMON)
        t4_rows.append({"Trig": tr, "Rec": rc, **mt_cell, "Switches": len(tr_cell), "Closed_3x_Wins": wr_cell})

df_t4 = pd.DataFrame(t4_rows)
df_t4.to_csv(os.path.join(OUT_DIR, "T4_soxl_standalone_2d_trig_rec_plateau.csv"), index=False)
piv_t4 = df_t4.pivot(index="Trig", columns="Rec", values="Full_CAGR_%")
say("SOXL Standalone 2D CAGR% Plateau:")
say(piv_t4.to_string())

# =============================================================================
# T5. TQQQ + SOXL Rebalanced Blend: Weight x Rebalance Frequency Matrix (Exact Open Execution)
# =============================================================================
say("\n=== T5. TQQQ + SOXL Rebalanced Blend: Weight x Rebalance Frequency Matrix (Both De-lever to 1x QQQ) ===")
eq_t_base, ov_t, in_t, sw_t, _, _ = run_v1_engine(TQQQ, QQQ, vz_qqq_1x, IDX_COMMON, SEP_COMMON, 1.2, 0.3)
eq_s_base, ov_s, in_s, sw_s, _, _ = run_v1_engine(SOXL, QQQ, vz_soxx_1x, IDX_COMMON, SEP_COMMON, 1.2, 0.3)


def sim_open_blend(ov_a, in_a, ov_b, in_b, sw_a, sw_b, w_a=0.75, freq="annual"):
    w_b = round(1.0 - w_a, 4)
    va, vb = w_a, w_b
    n = len(IDX_COMMON)
    eq = np.empty(n)
    eq[0] = 1.0
    w_b_series = np.empty(n)
    w_b_series[0] = w_b
    reb_cnt = 0
    for i in range(1, n):
        d0, d = IDX_COMMON[i - 1], IDX_COMMON[i]
        va *= ov_a[i]
        vb *= ov_b[i]
        tot_open = va + vb
        wa_cur = va / tot_open
        do_reb = False
        if freq == "never":
            do_reb = False
        elif freq == "monthly":
            do_reb = (d.month != d0.month)
        elif freq == "quarterly":
            do_reb = (d.month in (1, 4, 7, 10) and d.month != d0.month)
        elif freq == "semiannual":
            do_reb = (d.month in (1, 7) and d.month != d0.month)
        elif freq == "annual":
            do_reb = (d.year != d0.year)
        elif freq == "on_switch":
            do_reb = (sw_a[i] or sw_b[i])
        elif freq == "band5":
            do_reb = (abs(wa_cur - w_a) >= 0.05)
        elif freq == "band10":
            do_reb = (abs(wa_cur - w_a) >= 0.10)
        elif freq == "band15":
            do_reb = (abs(wa_cur - w_a) >= 0.15)

        if do_reb and abs(wa_cur - w_a) > 1e-4 and (0.0 < w_a < 1.0):
            move = abs(va - w_a * tot_open)
            tot_after = tot_open - move * 2.0 * FEE
            va, vb = w_a * tot_after, w_b * tot_after
            reb_cnt += 1

        va *= in_a[i]
        vb *= in_b[i]
        eq[i] = va + vb
        w_b_series[i] = vb / eq[i]

    eq_ser = pd.Series(eq, index=IDX_COMMON)
    wb_ser = pd.Series(w_b_series, index=IDX_COMMON)
    return eq_ser, wb_ser, reb_cnt


weights_t5 = [1.00, 0.90, 0.85, 0.80, 0.75, 0.70, 0.65, 0.60, 0.50, 0.00]
freqs_t5 = ["never", "monthly", "quarterly", "semiannual", "annual", "on_switch", "band5", "band10", "band15"]
t5_rows = []
for wa in weights_t5:
    wb = round(1.0 - wa, 2)
    w_lbl = f"{int(round(wa*100))}/{int(round(wb*100))}"
    for fr in freqs_t5:
        if (wa in (1.0, 0.0)) and fr != "never":
            continue
        eq_b, wb_s, r_cnt = sim_open_blend(ov_t, in_t, ov_s, in_s, sw_t, sw_s, wa, fr)
        mt_b = calc_metrics(eq_b, IDX_COMMON)
        t5_rows.append({
            "TQQQ_SOXL_Weight": w_lbl,
            "Rebalance_Method": fr,
            **mt_b,
            "Rebalance_Count": r_cnt,
            "Max_SOXL_Weight_%": round(float(wb_s.max() * 100), 1),
            "End_SOXL_Weight_%": round(float(wb_s.iloc[-1] * 100), 1),
        })
        if w_lbl == "75/25" and fr == "annual":
            pd.DataFrame({
                "Date": IDX_COMMON.strftime("%Y-%m-%d"),
                "Blend_75_25_Annual_NAV": eq_b.round(6).values,
                "TQQQ_V1_NAV": eq_t_base.round(6).values,
                "SOXL_V1_to_QQQ_NAV": eq_s_base.round(6).values,
                "SOXL_Sleeve_Weight_%": (wb_s * 100).round(2).values,
            }).to_csv(os.path.join(OUT_DIR, "T7_blend_75_25_daily_nav_and_weights.csv"), index=False)

df_t5 = pd.DataFrame(t5_rows)
say(df_t5[df_t5["TQQQ_SOXL_Weight"].isin(["100/0", "80/20", "75/25", "50/50", "0/100"])].to_string(index=False))
df_t5.to_csv(os.path.join(OUT_DIR, "T5_blend_weight_x_rebalance_frequency_plateau.csv"), index=False)

# =============================================================================
# T6. 75% TQQQ + 25% SOXL (Annual Rebalance) x SOXL (Trig, Rec) 64-Cell Plateau
# =============================================================================
say("\n=== T6. 75% TQQQ + 25% SOXL (Annual Rebalance, Both De-lever to 1x QQQ) x SOXL (Trig, Rec) 64-Cell Plateau ===")
trigs_t6 = [0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5]
recs_t6 = [-0.2, 0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.7]
t6_rows = []
for tr in trigs_t6:
    for rc in recs_t6:
        _, ov_s_cell, in_s_cell, sw_s_cell, _, _ = run_v1_engine(SOXL, QQQ, vz_soxx_1x, IDX_COMMON, SEP_COMMON, tr, rc)
        eq_c, _, r_cnt = sim_open_blend(ov_t, in_t, ov_s_cell, in_s_cell, sw_t, sw_s_cell, 0.75, "annual")
        mt_c = calc_metrics(eq_c, IDX_COMMON)
        t6_rows.append({"SOXL_Trig": tr, "SOXL_Rec": rc, **mt_c, "Rebalance_Count": r_cnt})

df_t6 = pd.DataFrame(t6_rows)
df_t6.to_csv(os.path.join(OUT_DIR, "T6_blend_75_25_annual_x_soxl_trig_rec_64cell_plateau.csv"), index=False)
say("64-Cell CAGR range: " + f"{df_t6['Full_CAGR_%'].min():.2f}% .. {df_t6['Full_CAGR_%'].max():.2f}% | MaxDD range: {df_t6['MaxDD_%'].min():.2f}% .. {df_t6['MaxDD_%'].max():.2f}%")

open(os.path.join(OUT_DIR, "audit_log.txt"), "w").write("\n".join(LOG))
