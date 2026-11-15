#!/usr/bin/env python3
"""
proxy_sep_incorporation_test.py — Test incorporating the earlier Proxy SEP (2Y Treasury + Core PCE from sep_proxy_2y_test.py,
and break_signals_test.py signals) with our Dual Vol [min(RV21, VIX)] * Institutional CTA Baz Overextension Trim.
"""
import json
import os
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "outputs", "combined_macro_vrp_cta_20261115")
os.makedirs(OUT, exist_ok=True)

# Load base series and institutional CTA features
bsrc = open(os.path.join(ROOT, "break_signals_test.py")).read().split("# ----------------------------------------------------------------------------- A. index-level timing")[0]
bs = {"__file__": os.path.join(ROOT, "break_signals_test.py")}
exec(bsrc, bs)
fred, yahoo, sig, T = bs["fred"], bs["yahoo"], bs["sig"], bs["T"]

REG = pd.read_csv(os.path.join(ROOT, "outputs", "pure_momentum_1985_2026_audit", "inputs", "v3_regime_and_cash_214m.csv"))
real_sep = dict(zip(pd.to_datetime(REG["t"]), REG["sep_on"].astype(bool)))

csrc = open(os.path.join(ROOT, "cta_institutional_deep_test.py")).read().split("ixic = yahoo(\"_IXIC\")")[0]
cs = {"__file__": os.path.join(ROOT, "cta_institutional_deep_test.py"), "np": np, "pd": pd}
exec(csrc, cs)
build_institutional_cta_features = cs["build_institutional_cta_features"]

ETF_DIR = os.path.join(ROOT, "outputs", "remediation_full_audit_20261104", "tiingo_etfs")
def load_etf_close(sym):
    d = json.load(open(os.path.join(ETF_DIR, f"{sym}.json")))
    s = pd.Series({pd.Timestamp(r["date"][:10]): float(r["adjClose"]) for r in d}).sort_index()
    return s[~s.index.duplicated(keep="last")]

ixic = yahoo("_IXIC")
gspc = yahoo("_GSPC")
vix = fred("VIXCLS")
df_ixic = build_institutional_cta_features(ixic)
qqq_p = load_etf_close("QQQ")
tqqq_p = load_etf_close("TQQQ")
bil_p = load_etf_close("BIL")
sgov_p = load_etf_close("SGOV")
df_qqq = build_institutional_cta_features(qqq_p)

rv21_spx = gspc.pct_change().dropna().rolling(21).std(ddof=1) * np.sqrt(252) * 100.0
med_vix = vix.expanding(min_periods=252).median()

T90 = [t for t in T if t >= pd.Timestamp("1990-01-31")]
rf_d = (fred("DGS3MO") / 100.0).reindex(df_ixic.index).ffill().bfill() / 252.0
borrow_spread = 0.005 / 252.0
synth_m = {0: {}, 1: {}, 3: {}}
synth_d = {0: {}, 1: {}, 3: {}}
for t in T90:
    days = df_ixic.loc[(df_ixic.index > t) & (df_ixic.index <= t + pd.offsets.MonthEnd(1))].index
    synth_m[0][t] = float((1.0 + rf_d.loc[days]).prod() - 1.0)
    synth_d[0][t] = rf_d.loc[days]
    for L, er in ((1, 0.0020), (3, 0.0095)):
        d_lev = L * df_ixic["r"].loc[days] - (L - 1) * (rf_d.loc[days] + borrow_spread) - er / 252.0
        synth_m[L][t] = float((1.0 + d_lev).prod() - 1.0)
        synth_d[L][t] = d_lev

T_etf = [t for t in T90 if t >= pd.Timestamp("2010-03-31")]
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

def get_state(t, is_etf=False):
    # 1. Pure Proxy SEP (2Y DGS2 3m > +25bp & Core PCE > 2% & rising; OFF until 3m DGS2 <= 0)
    proxy_sep = bool(sig["SEP_PROXY"][t])
    # 2. Real SEP (available from 2015-11-30; True before 2015-11-30 if unproxied)
    has_real = (t >= pd.Timestamp("2015-11-30"))
    r_sep = bool(real_sep[t]) if has_real else True
    # 3. Spliced SEP (Proxy pre-2015, Real SEP 2015+)
    spliced_sep = r_sep if has_real else proxy_sep
    # 4. Consensus OFF (only OFF when BOTH Real SEP and Proxy SEP say OFF; i.e. ON if either is ON)
    either_on = (r_sep or proxy_sep) if has_real else proxy_sep
    # 5. Strict ON (OFF if EITHER Real SEP or Proxy SEP says OFF)
    both_on = (r_sep and proxy_sep) if has_real else proxy_sep
    # 6. Proxy SEP + Break Signals (CURVE / CREDIT / SAHM / CUTS)
    proxy_plus_any = bool(sig["PROXY+ANY"][t])
    proxy_plus_credit = proxy_sep and bool(sig["CREDIT"][t])

    row = (df_qqq if is_etf else df_ixic).loc[:t].iloc[-1]
    w_rv = float(row["w_var_2"])
    vix_t = float(vix.loc[:t].iloc[-1])
    mvix_t = float(med_vix.loc[:t].iloc[-1]) if pd.notna(med_vix.loc[:t].iloc[-1]) else 19.0
    w_vix = min(1.0, (mvix_t / vix_t) ** 2)
    w_dual_vol = min(w_rv, w_vix)
    z_comp = float(row["z_comp"])
    psi_long = float(row["psi_long"])
    baz_trim = psi_long if z_comp > np.sqrt(2.0) else 1.0
    w_combo = w_dual_vol * baz_trim

    return {
        "proxy_sep": proxy_sep,
        "real_sep_only": r_sep,
        "spliced_sep": spliced_sep,
        "either_on": either_on,
        "both_on": both_on,
        "proxy_plus_any": proxy_plus_any,
        "proxy_plus_credit": proxy_plus_credit,
        "w_rv": w_rv,
        "w_dual_vol": w_dual_vol,
        "baz_trim": baz_trim,
        "w_combo": w_combo,
    }

COST = 0.0010

def sim(weight_fn, t_list, ret_dict, daily_dict, L=3, is_etf=False):
    m_rets = {}
    d_rets = []
    prev_w = 0.0
    off_cnt = 0
    for t in t_list:
        s = get_state(t, is_etf=is_etf)
        w = float(np.clip(weight_fn(s), 0.0, 1.0))
        if w == 0.0:
            off_cnt += 1
        cost = abs(w - prev_w) * COST
        prev_w = w
        gross = w * ret_dict[L][t] + (1.0 - w) * ret_dict[0][t]
        m_rets[t + pd.offsets.MonthEnd(1)] = (1.0 + gross) * (1.0 - cost) - 1.0
        rd = w * daily_dict[L][t] + (1.0 - w) * daily_dict[0][t]
        if len(rd):
            rd = rd.copy()
            rd.iloc[0] = (1.0 + rd.iloc[0]) * (1.0 - cost) - 1.0
            d_rets.append(rd)
    return pd.Series(m_rets).sort_index(), pd.concat(d_rets).sort_index(), off_cnt

def metrics(s_m, rf_ser, s_d):
    w = (1.0 + s_m).cumprod()
    w0 = pd.concat([pd.Series([1.0], index=[s_m.index[0] - pd.offsets.MonthEnd(1)]), w])
    cagr = float(w.iloc[-1] ** (12.0 / len(s_m)) - 1.0)
    mdd_m = float((w0 / w0.cummax() - 1.0).min())
    ex = s_m - rf_ser.reindex(s_m.index).fillna(0.0)
    sh = float(ex.mean() / s_m.std(ddof=1) * np.sqrt(12.0))
    wd = (1.0 + s_d).cumprod()
    wd0 = pd.concat([pd.Series([1.0], index=[s_d.index[0] - pd.Timedelta(days=1)]), wd])
    mdd_d = float((wd0 / wd0.cummax() - 1.0).min())
    calmar = cagr / abs(mdd_d) if mdd_d < 0 else np.nan
    return {"CAGR": cagr, "Sharpe": sh, "MaxDD_M": mdd_m, "MaxDD_D": mdd_d, "Calmar_D": calmar}

rf_synth_ser = pd.Series({t + pd.offsets.MonthEnd(1): synth_m[0][t] for t in T90})
rf_etf_ser = pd.Series({t + pd.offsets.MonthEnd(1): actual_m[0][t] for t in T_etf})

variants = {
    # A. Without Vol/CTA (Pure Macro Switches on 3x)
    "A1. Pure Real SEP Only (No pre-2015 Proxy, No Vol/CTA)":
        lambda s: 1.0 if s["real_sep_only"] else 0.0,
    "A2. Pure Proxy SEP Only (2Y+CorePCE 1990-2026, No Vol/CTA)":
        lambda s: 1.0 if s["proxy_sep"] else 0.0,
    "A3. Spliced SEP Only (Proxy pre-2015 + Real SEP 2015+, No Vol/CTA)":
        lambda s: 1.0 if s["spliced_sep"] else 0.0,

    # B. Market Signal Only (No SEP / No Proxy SEP)
    "B0. NO SEP at all: min(RV21, VIX) * CTA Baz Trim":
        lambda s: s["w_combo"],

    # C. Incorporating Proxy SEP variants into min(RV21, VIX) * CTA Baz Trim
    "C1. Real SEP Only (2015+) + min(RV21, VIX) * CTA Baz Trim (No pre-2015 Proxy)":
        lambda s: s["w_combo"] if s["real_sep_only"] else 0.0,
    "C2. Pure Proxy SEP (2Y+CorePCE all years) + min(RV21, VIX) * CTA Baz Trim":
        lambda s: s["w_combo"] if s["proxy_sep"] else 0.0,
    "C3. Spliced (Proxy pre-2015 + Real SEP 2015+) + min(RV21, VIX) * CTA Baz Trim":
        lambda s: s["w_combo"] if s["spliced_sep"] else 0.0,
    "C4. Consensus OFF (OFF only if BOTH Real SEP & Proxy SEP are OFF) + Combo":
        lambda s: s["w_combo"] if s["either_on"] else 0.0,
    "C5. Either OFF (OFF if EITHER Real SEP or Proxy SEP is OFF) + Combo":
        lambda s: s["w_combo"] if s["both_on"] else 0.0,
    "C6. Proxy SEP + Credit Filter (CREDIT) + min(RV21, VIX) * CTA Baz Trim":
        lambda s: s["w_combo"] if s["proxy_plus_credit"] else 0.0,
    "C7. Proxy SEP + All Break Signals (PROXY+ANY) + min(RV21, VIX) * CTA Baz Trim":
        lambda s: s["w_combo"] if s["proxy_plus_any"] else 0.0,
}

out = []
for name, fn in variants.items():
    sm_90, sd_90, off_90 = sim(fn, T90, synth_m, synth_d, L=3, is_etf=False)
    sm_pre = sm_90.loc[:"2009-12-31"]
    sd_pre = sd_90.loc[:"2009-12-31"]
    sm_etf, sd_etf, off_etf = sim(fn, T_etf, actual_m, actual_d, L=3, is_etf=True)

    m_90 = metrics(sm_90, rf_synth_ser, sd_90)
    m_pre = metrics(sm_pre, rf_synth_ser, sd_pre)
    m_etf = metrics(sm_etf, rf_etf_ser, sd_etf)

    out.append({
        "Strategy": name,
        "OFF_m(90-26)": off_90,
        "90_09_CAGR": f"{m_pre['CAGR']:.1%}",
        "90_09_MDD_M": f"{m_pre['MaxDD_M']:.1%}",
        "90_26_CAGR": f"{m_90['CAGR']:.1%}",
        "90_26_Sh": f"{m_90['Sharpe']:.2f}",
        "90_26_MDD_M": f"{m_90['MaxDD_M']:.1%}",
        "ETF_10_26_CAGR": f"{m_etf['CAGR']:.1%}",
        "ETF_10_26_Sh": f"{m_etf['Sharpe']:.2f}",
        "ETF_MDD_M": f"{m_etf['MaxDD_M']:.1%}",
        "ETF_MDD_D": f"{m_etf['MaxDD_D']:.1%}",
        "ETF_Calmar": f"{m_etf['Calmar_D']:.2f}",
    })

df_out = pd.DataFrame(out)
df_out.to_csv(os.path.join(OUT, "proxy_sep_incorporation_summary.csv"), index=False)
pd.set_option("display.width", 280)
pd.set_option("display.max_columns", 20)
print("==========================================================================================================================")
print("INCORPORATING PROXY SEP (2Y+CorePCE) WITH DUAL VOL [min(RV21, VIX)] * INSTITUTIONAL CTA BAZ TRIM (1990-2026 & 2010-2026)")
print("==========================================================================================================================")
print(df_out.to_string(index=False))
