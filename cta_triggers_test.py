#!/usr/bin/env python3
"""
cta_triggers_test.py — Empirical test of Goldman Sachs / Nomura-style CTA Trigger Levels
(Short-Term 20d MA, Medium-Term 50d/63d MA, Long-Term 200d MA) across 1985-2026 (41.5 years).

PRE-REGISTERED textbook CTA definitions (zero parameter tuning):
  - ST trigger : Price >= 20-trading-day SMA (~1 month)
  - MT trigger : Price >= 50-trading-day SMA (~2.5 months, standard GS "medium-term CTA threshold")
  - LT trigger : Price >= 200-trading-day SMA (~10 months, standard GS "long-term CTA threshold")
  - CTA_Count  : Number of triggers active in {0, 1, 2, 3} (ST + MT + LT)

Questions tested:
  1. When price breaks below ST (20d), MT (50d), or LT (200d), what actually happens NEXT month (and next 5/21 days)?
     Does "CTA selling" continue, or is it a whipsaw in bull markets (`SEP = ON`) vs bear markets (`SEP = OFF` / `2000-02` / `2008`)?
  2. If we use CTA triggers to scale TQQQ / 3x Nasdaq (either standalone or on top of B5 `SEP + Volatility Management`),
     does it help or hurt CAGR, Sharpe, and MaxDD across 1985-2026, 1985-2009, and 2010-2026?
"""
import json
import os
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "outputs", "cta_triggers_20261115")
os.makedirs(OUT, exist_ok=True)

# Load base series from break_signals_test.py
bsrc = open(os.path.join(ROOT, "break_signals_test.py")).read().split("# ----------------------------------------------------------------------------- A. index-level timing")[0]
bs = {"__file__": os.path.join(ROOT, "break_signals_test.py")}
exec(bsrc, bs)
fred, yahoo, sig, T = bs["fred"], bs["yahoo"], bs["sig"], bs["T"]

REG = pd.read_csv(os.path.join(ROOT, "outputs", "pure_momentum_1985_2026_audit", "inputs", "v3_regime_and_cash_214m.csv"))
real_sep = dict(zip(pd.to_datetime(REG["t"]), REG["sep_on"].astype(bool)))

ixic = yahoo("_IXIC")
r_ixic = ixic.pct_change().dropna()
rv21_ixic = r_ixic.rolling(21).std(ddof=1) * np.sqrt(252)
med_rv21_ixic = rv21_ixic.expanding(min_periods=252).median()

# Daily CTA triggers on Nasdaq Composite
ma20_ixic = ixic.rolling(20).mean()
ma50_ixic = ixic.rolling(50).mean()
ma200_ixic = ixic.rolling(200).mean()

st_d = (ixic >= ma20_ixic).astype(int)
mt_d = (ixic >= ma50_ixic).astype(int)
lt_d = (ixic >= ma200_ixic).astype(int)
cta_cnt_d = st_d + mt_d + lt_d  # 0, 1, 2, 3

# Synthetic monthly 1x / 3x / Cash returns (1985-05..2026-10)
rf_d = (fred("DGS3MO") / 100.0).reindex(r_ixic.index).ffill().bfill() / 252.0
borrow_spread = 0.005 / 252.0
synth_m = {0: {}, 1: {}, 3: {}}
for t in T:
    days = r_ixic.loc[(r_ixic.index > t) & (r_ixic.index <= t + pd.offsets.MonthEnd(1))].index
    synth_m[0][t] = float((1.0 + rf_d.loc[days]).prod() - 1.0)
    for L, er in ((1, 0.0020), (3, 0.0095)):
        d_lev = L * r_ixic.loc[days] - (L - 1) * (rf_d.loc[days] + borrow_spread) - er / 252.0
        synth_m[L][t] = float((1.0 + d_lev).prod() - 1.0)

# Actual ETFs (2010-04..2026-10)
ETF_DIR = os.path.join(ROOT, "outputs", "remediation_full_audit_20261104", "tiingo_etfs")
def load_etf_close(sym):
    d = json.load(open(os.path.join(ETF_DIR, f"{sym}.json")))
    s = pd.Series({pd.Timestamp(r["date"][:10]): float(r["adjClose"]) for r in d}).sort_index()
    return s[~s.index.duplicated(keep="last")]

qqq_p = load_etf_close("QQQ")
tqqq_p = load_etf_close("TQQQ")
bil_p = load_etf_close("BIL")
sgov_p = load_etf_close("SGOV")
rv21_qqq = qqq_p.pct_change().dropna().rolling(21).std(ddof=1) * np.sqrt(252)
med_rv21_qqq = rv21_qqq.expanding(min_periods=252).median()

ma20_qqq = qqq_p.rolling(20).mean()
ma50_qqq = qqq_p.rolling(50).mean()
ma200_qqq = qqq_p.rolling(200).mean()

T_etf = [t for t in T if t >= pd.Timestamp("2010-03-31")]
actual_m = {0: {}, 1: {}, 3: {}}
actual_d = {0: {}, 1: {}, 3: {}}
for t in T_etf:
    t1 = t + pd.offsets.MonthEnd(1)
    cp = sgov_p if t >= pd.Timestamp("2020-06-30") else bil_p
    actual_m[0][t] = float(cp.loc[:t1].iloc[-1] / cp.loc[:t].iloc[-1] - 1.0)
    days = qqq_p.loc[(qqq_p.index > t) & (qqq_p.index <= t1)].index
    actual_d[0][t] = cp.pct_change().reindex(days).fillna(0.0)
    for L, ser in ((1, qqq_p), (3, tqqq_p)):
        actual_m[L][t] = float(ser.loc[:t1].iloc[-1] / ser.loc[:t].iloc[-1] - 1.0)
        actual_d[L][t] = ser.pct_change().reindex(days).fillna(0.0)

# Build monthly panel at each month-end t
rows = []
for t in T:
    sep_on = bool(real_sep[t]) if t >= pd.Timestamp("2015-11-30") else bool(sig["SEP_PROXY"][t])
    st = int(st_d.loc[:t].iloc[-1])
    mt = int(mt_d.loc[:t].iloc[-1])
    lt = int(lt_d.loc[:t].iloc[-1])
    cnt = st + mt + lt
    rv = float(rv21_ixic.loc[:t].iloc[-1])
    m_rv = float(med_rv21_ixic.loc[:t].iloc[-1])
    w_vm = min(1.0, (m_rv / rv) ** 2)
    rows.append({
        "t": t,
        "sep_on": sep_on,
        "st_20d": st,
        "mt_50d": mt,
        "lt_200d": lt,
        "cta_cnt": cnt,
        "rv": rv,
        "w_vm": w_vm,
        "ret_1x": synth_m[1][t],
        "ret_3x": synth_m[3][t],
        "ret_cash": synth_m[0][t],
    })
P = pd.DataFrame(rows).set_index("t")

# =============================================================================
# PART 1: What happens NEXT month when CTA triggers are ON vs BROKEN? (1985-2026)
# =============================================================================
print("==========================================================================================")
print("PART 1: WHAT HAPPENS NEXT MONTH WHEN CTA TRIGGERS ARE BROKEN vs INTACT? (1985-05..2026-10)")
print("==========================================================================================")
for state_label, mask in [
    ("CTA 3/3 Bullish (Above 20d, 50d, 200d MA)", P["cta_cnt"] == 3),
    ("CTA 2/3 (Lost 20d short-term trigger only)", P["cta_cnt"] == 2),
    ("CTA 1/3 (Lost 20d & 50d medium-term triggers)", P["cta_cnt"] == 1),
    ("CTA 0/3 Max Bearish (Below 20d, 50d, 200d MA)", P["cta_cnt"] == 0),
    ("  -> CTA 0/3 when SEP = ON  (Fed not hawkish)", (P["cta_cnt"] == 0) & P["sep_on"]),
    ("  -> CTA 0/3 when SEP = OFF (Fed hawkish hike)", (P["cta_cnt"] == 0) & (~P["sep_on"])),
    ("Above 200d LT Trigger (LT = 1)", P["lt_200d"] == 1),
    ("Below 200d LT Trigger (LT = 0)", P["lt_200d"] == 0),
    ("Above 50d  MT Trigger (MT = 1)", P["mt_50d"] == 1),
    ("Below 50d  MT Trigger (MT = 0)", P["mt_50d"] == 0),
]:
    s = P[mask]
    r1_ann = (1.0 + s["ret_1x"]).prod() ** (12.0 / len(s)) - 1.0
    r3_ann = (1.0 + s["ret_3x"]).prod() ** (12.0 / len(s)) - 1.0
    avg_vm = s["w_vm"].mean()
    print(f"  {state_label:<48} | N={len(s):3d}m | Avg1M(1x): {s['ret_1x'].mean():+6.2%} | Ann(1x): {r1_ann:+6.1%} | Ann(3x): {r3_ann:+6.1%} | Avg w_vm: {avg_vm:.2f}")

# =============================================================================
# PART 2: Backtest CTA Strategies (Standalone vs Combined with SEP & VM)
# =============================================================================
COST = 0.0010

def sim(weight_fn, t_list, ret_dict, is_etf=False, daily_dict=None):
    m_rets = {}
    d_rets = []
    prev_w = 0.0
    for t in t_list:
        row = P.loc[t]
        if is_etf:
            rv = float(rv21_qqq.loc[:t].iloc[-1])
            m_rv = float(med_rv21_qqq.loc[:t].iloc[-1])
            w_vm = min(1.0, (m_rv / rv) ** 2)
            st = int(qqq_p.loc[:t].iloc[-1] >= ma20_qqq.loc[:t].iloc[-1])
            mt = int(qqq_p.loc[:t].iloc[-1] >= ma50_qqq.loc[:t].iloc[-1])
            lt = int(qqq_p.loc[:t].iloc[-1] >= ma200_qqq.loc[:t].iloc[-1])
            cnt = st + mt + lt
        else:
            w_vm = float(row["w_vm"])
            st, mt, lt, cnt = int(row["st_20d"]), int(row["mt_50d"]), int(row["lt_200d"]), int(row["cta_cnt"])
        w = float(np.clip(weight_fn(row["sep_on"], w_vm, st, mt, lt, cnt), 0.0, 1.0))
        cost = abs(w - prev_w) * COST
        prev_w = w
        gross = w * ret_dict[3][t] + (1.0 - w) * ret_dict[0][t]
        m_rets[t + pd.offsets.MonthEnd(1)] = (1.0 + gross) * (1.0 - cost) - 1.0
        if daily_dict is not None:
            rd = w * daily_dict[3][t] + (1.0 - w) * daily_dict[0][t]
            if len(rd):
                rd = rd.copy()
                rd.iloc[0] = (1.0 + rd.iloc[0]) * (1.0 - cost) - 1.0
                d_rets.append(rd)
    return pd.Series(m_rets).sort_index(), (pd.concat(d_rets).sort_index() if d_rets else None)

def metrics(s_m, rf_ser, s_d=None):
    w = (1.0 + s_m).cumprod()
    w0 = pd.concat([pd.Series([1.0], index=[s_m.index[0] - pd.offsets.MonthEnd(1)]), w])
    cagr = float(w.iloc[-1] ** (12.0 / len(s_m)) - 1.0)
    mdd = float((w0 / w0.cummax() - 1.0).min())
    ex = s_m - rf_ser.reindex(s_m.index).fillna(0.0)
    sh = float(ex.mean() / s_m.std(ddof=1) * np.sqrt(12.0))
    mdd_d = np.nan
    if s_d is not None:
        wd = (1.0 + s_d).cumprod()
        wd0 = pd.concat([pd.Series([1.0], index=[s_d.index[0] - pd.Timedelta(days=1)]), wd])
        mdd_d = float((wd0 / wd0.cummax() - 1.0).min())
    return {"CAGR": cagr, "Sharpe": sh, "MaxDD_M": mdd, "MaxDD_D": mdd_d}

rf_synth_ser = pd.Series({t + pd.offsets.MonthEnd(1): synth_m[0][t] for t in T})
rf_etf_ser = pd.Series({t + pd.offsets.MonthEnd(1): actual_m[0][t] for t in T_etf})

strats = {
    # A. Standalone CTA trend rules on 3x (without SEP or VM)
    "A1. Pure 3x Buy & Hold (No CTA, No SEP, No VM)":
        lambda sep, w_vm, st, mt, lt, cnt: 1.0,
    "A2. Pure CTA 200d LT Trigger Only (100% 3x if >=MA200 else Cash)":
        lambda sep, w_vm, st, mt, lt, cnt: float(lt),
    "A3. Pure CTA 50d MT Trigger Only (100% 3x if >=MA50 else Cash)":
        lambda sep, w_vm, st, mt, lt, cnt: float(mt),
    "A4. Pure CTA 3-Speed (cnt/3 of 20d+50d+200d, No SEP, No VM)":
        lambda sep, w_vm, st, mt, lt, cnt: cnt / 3.0,
    "A5. Pure CTA 3-Speed + Volatility Management ((cnt/3) * w_vm, No SEP)":
        lambda sep, w_vm, st, mt, lt, cnt: (cnt / 3.0) * w_vm,

    # B. Our Baseline vs Adding CTA triggers on top of SEP + VM
    "B0. Baseline B5: SEP + Volatility Management (w_vm)":
        lambda sep, w_vm, st, mt, lt, cnt: w_vm if sep else 0.0,
    "B1. SEP + VM + Exit when 200d LT Trigger broken (lt == 0)":
        lambda sep, w_vm, st, mt, lt, cnt: (w_vm if lt == 1 else 0.0) if sep else 0.0,
    "B2. SEP + VM + Exit when 50d MT Trigger broken (mt == 0)":
        lambda sep, w_vm, st, mt, lt, cnt: (w_vm if mt == 1 else 0.0) if sep else 0.0,
    "B3. SEP + VM * CTA 3-Speed ((cnt/3) * w_vm)":
        lambda sep, w_vm, st, mt, lt, cnt: (cnt / 3.0) * w_vm if sep else 0.0,
    "B4. SEP + VM, Halve weight only when ALL 3 CTA lines broken (cnt == 0)":
        lambda sep, w_vm, st, mt, lt, cnt: (0.5 * w_vm if cnt == 0 else w_vm) if sep else 0.0,
}

b5_all, _ = sim(strats["B0. Baseline B5: SEP + Volatility Management (w_vm)"], T, synth_m, is_etf=False)
b5_etf, _ = sim(strats["B0. Baseline B5: SEP + Volatility Management (w_vm)"], T_etf, actual_m, is_etf=True)

out_rows = []
for name, fn in strats.items():
    sm_all, _ = sim(fn, T, synth_m, is_etf=False)
    sm_85_09 = sm_all.loc[:"2009-12-31"]
    sm_etf, sd_etf = sim(fn, T_etf, actual_m, is_etf=True, daily_dict=actual_d)

    m_all = metrics(sm_all, rf_synth_ser)
    m_85 = metrics(sm_85_09, rf_synth_ser)
    m_etf = metrics(sm_etf, rf_etf_ser, s_d=sd_etf)

    if name.startswith("B0."):
        t_all, t_etf = 0.0, 0.0
    else:
        da = (sm_all - b5_all).dropna()
        t_all = float(da.mean() / da.std(ddof=1) * np.sqrt(len(da))) if da.std(ddof=1) > 0 else 0.0
        de = (sm_etf - b5_etf).dropna()
        t_etf = float(de.mean() / de.std(ddof=1) * np.sqrt(len(de))) if de.std(ddof=1) > 0 else 0.0

    out_rows.append({
        "Strategy": name,
        "85_26_CAGR": f"{m_all['CAGR']:.1%}",
        "85_26_Sh": f"{m_all['Sharpe']:.2f}",
        "85_26_MDD": f"{m_all['MaxDD_M']:.1%}",
        "85_09_CAGR": f"{m_85['CAGR']:.1%}",
        "85_09_Sh": f"{m_85['Sharpe']:.2f}",
        "85_09_MDD": f"{m_85['MaxDD_M']:.1%}",
        "ETF_10_26_CAGR": f"{m_etf['CAGR']:.1%}",
        "ETF_10_26_Sh": f"{m_etf['Sharpe']:.2f}",
        "ETF_MDD_M": f"{m_etf['MaxDD_M']:.1%}",
        "ETF_MDD_D": f"{m_etf['MaxDD_D']:.1%}",
        "t_vs_B5(ETF)": f"{t_etf:+.2f}",
    })

res_df = pd.DataFrame(out_rows)
res_df.to_csv(os.path.join(OUT, "cta_triggers_1985_2026_summary.csv"), index=False)
pd.set_option("display.width", 260)
pd.set_option("display.max_columns", 20)
print("\n==========================================================================================")
print("PART 2: CTA TRIGGER BACKTEST (1985-2026 FULL 41.5Y, 1985-2009 PRE-ETF, 2010-2026 ETF)")
print("==========================================================================================")
print(res_df.to_string(index=False))

# =============================================================================
# PART 3: Daily CTA Breakdown Event Study (What happens 1d / 5d / 21d AFTER breaking 20d/50d/200d?)
# =============================================================================
print("\n==========================================================================================")
print("PART 3: DAILY EVENT STUDY — WHAT HAPPENS THE DAY PRICE BREAKS BELOW A CTA TRIGGER LINE?")
print("==========================================================================================")
ixic_clean = ixic.loc["1985-05-01":"2026-10-31"]
for name, ma_ser in [("ST 20d MA", ma20_ixic), ("MT 50d MA", ma50_ixic), ("LT 200d MA", ma200_ixic)]:
    above = (ixic_clean >= ma_ser.reindex(ixic_clean.index)).astype(int)
    cross_down = ixic_clean.index[(above == 0) & (above.shift(1) == 1)]
    r1d, r5d, r21d = [], [], []
    for d in cross_down:
        loc = ixic_clean.index.get_loc(d)
        if loc + 21 < len(ixic_clean):
            r1d.append(ixic_clean.iloc[loc + 1] / ixic_clean.iloc[loc] - 1.0)
            r5d.append(ixic_clean.iloc[loc + 5] / ixic_clean.iloc[loc] - 1.0)
            r21d.append(ixic_clean.iloc[loc + 21] / ixic_clean.iloc[loc] - 1.0)
    r1d, r5d, r21d = np.array(r1d), np.array(r5d), np.array(r21d)
    print(
        f"  Break BELOW {name:<10} | Events={len(r21d):3d} | "
        f"Next 1d: {r1d.mean():+6.2%} (WR {(r1d>0).mean():.0%}) | "
        f"Next 5d: {r5d.mean():+6.2%} (WR {(r5d>0).mean():.0%}) | "
        f"Next 21d: {r21d.mean():+6.2%} (WR {(r21d>0).mean():.0%})"
    )

# Also check daily CTA execution on Actual TQQQ (2010-04..2026-10)
print("\n==========================================================================================")
print("PART 4: WHAT IF YOU TRADE CTA TRIGGERS DAILY INSTEAD OF MONTHLY? (2010-04..2026-10 TQQQ)")
print("==========================================================================================")
days_etf = qqq_p.loc["2010-04-01":"2026-10-30"].index
r_tqqq_d = tqqq_p.pct_change().reindex(days_etf).fillna(0.0)
r_cash_d = sgov_p.pct_change().reindex(days_etf).fillna(bil_p.pct_change().reindex(days_etf)).fillna(0.0)
st_qqq_d = (qqq_p >= ma20_qqq).astype(float).shift(1).reindex(days_etf).fillna(1.0)
mt_qqq_d = (qqq_p >= ma50_qqq).astype(float).shift(1).reindex(days_etf).fillna(1.0)
lt_qqq_d = (qqq_p >= ma200_qqq).astype(float).shift(1).reindex(days_etf).fillna(1.0)
cnt_qqq_d = (st_qqq_d + mt_qqq_d + lt_qqq_d) / 3.0

for label, w_ser in [
    ("Daily CTA 200d MA (100% TQQQ above MA200 else Cash, 10bp/trade)", lt_qqq_d),
    ("Daily CTA 50d  MA (100% TQQQ above MA50  else Cash, 10bp/trade)", mt_qqq_d),
    ("Daily CTA 3-Speed (1/3 each 20d/50d/200d, 10bp/trade)", cnt_qqq_d),
]:
    turns = w_ser.diff().abs().fillna(0.0)
    rd = w_ser * r_tqqq_d + (1.0 - w_ser) * r_cash_d - turns * COST
    wd = (1.0 + rd).cumprod()
    n_yrs = len(rd) / 252.0
    cagr = float(wd.iloc[-1] ** (1.0 / n_yrs) - 1.0)
    mdd = float((wd / wd.cummax() - 1.0).min())
    sh = float((rd - r_cash_d).mean() / rd.std(ddof=1) * np.sqrt(252.0))
    n_trades = int((turns > 0).sum())
    print(f"  {label:<65} | CAGR: {cagr:5.1%} | Sharpe: {sh:.2f} | Daily MaxDD: {mdd:6.1%} | Trades: {n_trades}")

