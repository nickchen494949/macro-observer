#!/usr/bin/env python3
"""
cta_institutional_deep_test.py — Serious Institutional CTA Replication & Flow Cliff Study (1985-2026)

Why naive "Spot >= SMA(20/50/200)" is a retail toy, and how real Wall Street CTA models
(Man AHL / JPMorgan Baz-Granger-Harvey-Le Roux-Rattray 2015, Goldman Sachs FICC & Equities,
BofA Chintan Kotecha, Nomura Charlie McElligott) actually work:

1. Multi-Speed EWMA Crossovers (Baz et al. 2015):
   - Fast/Slow EWMA half-life pairs: (S_k, L_k) in {(8, 24), (16, 48), (32, 96)} trading days
   - Raw crossover: x_k(t) = EWMA(P, S_k) - EWMA(P, L_k)
   - 1st Vol Normalization: y_k(t) = x_k(t) / std_63(dP)
   - 2nd Signal Normalization: z_k(t) = y_k(t) / std_252(y_k)  (Continuous Trend Strength Z-score)
   - Non-linear Response Function (overextension dampener):
       psi(z) = (z * exp(-z^2 / 4)) / (sqrt(2) * exp(-0.5))  in [-1, +1]
     * Peaks at z = +/- sqrt(2) (~1.41 sigma)
     * Automatically trims/takes profit when trend is overextended (|z| > 2 sigma)!
     * Smoothly scales near 0 in choppy markets instead of binary 0/1 whipsaws.

2. BofA / Kotecha Trailing Stop-Out Layer:
   - Real CTAs include trailing drawdown stops (e.g. if price drops > 2.5x or 3.0x 21d daily vol
     from its 20-day rolling peak, fast/medium trend signals get stopped out until a new breakout).

3. Goldman Sachs "Asymmetric Cliff & Crowding" Flow Mechanics:
   - Total CTA Notional Exposure: E_t = Signal_t * (TargetVol / RealizedVol_t)
   - Why does breaking a level sometimes cause a crash and sometimes nothing?
     * Because Forced Selling Flow = dE_t = E_t - E_{t-1}!
     * A "CTA Cliff" ONLY happens when:
       (a) Crowding is high entering the break (E_{t-5} in top percentiles: strong trend + compressed vol), AND
       (b) Both Trend Signal drops AND Realized Volatility spikes simultaneously ("Double Whammy"), OR
       (c) Fast, Medium, and Slow triggers are tightly clustered (compression) and break together.
"""
import json
import os
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "outputs", "cta_triggers_20261115")
os.makedirs(OUT, exist_ok=True)

# Load base series
bsrc = open(os.path.join(ROOT, "break_signals_test.py")).read().split("# ----------------------------------------------------------------------------- A. index-level timing")[0]
bs = {"__file__": os.path.join(ROOT, "break_signals_test.py")}
exec(bsrc, bs)
fred, yahoo, sig, T = bs["fred"], bs["yahoo"], bs["sig"], bs["T"]

REG = pd.read_csv(os.path.join(ROOT, "outputs", "pure_momentum_1985_2026_audit", "inputs", "v3_regime_and_cash_214m.csv"))
real_sep = dict(zip(pd.to_datetime(REG["t"]), REG["sep_on"].astype(bool)))

def build_institutional_cta_features(price_ser):
    """
    Build the exact Baz, Granger, Harvey, Le Roux & Rattray (2015) institutional CTA signal
    plus BofA-style trailing volatility stop and Goldman-style CTA exposure & forced flow.
    """
    p = price_ser.dropna().sort_index()
    r = p.pct_change()
    dp = p.diff()

    # 63-day EWMA std of daily price changes for 1st normalization (Baz et al. 2015)
    sig_dp_63 = dp.ewm(halflife=63, min_periods=21).std()

    # Three canonical CTA speeds: (8, 24) Short, (16, 48) Medium, (32, 96) Long
    z_dict = {}
    psi_dict = {}
    norm_const = np.sqrt(2.0) * np.exp(-0.5)  # ~0.85776, so max(|psi(z)|) == 1.0 at z = +/- sqrt(2)

    for label, (hl_s, hl_l) in [("st", (8, 24)), ("mt", (16, 48)), ("lt", (32, 96))]:
        ewm_s = p.ewm(halflife=hl_s, min_periods=hl_s).mean()
        ewm_l = p.ewm(halflife=hl_l, min_periods=hl_l).mean()
        x_k = ewm_s - ewm_l
        y_k = x_k / sig_dp_63.replace(0, np.nan)
        sig_y_252 = y_k.ewm(halflife=252, min_periods=63).std()
        z_k = (y_k / sig_y_252.replace(0, np.nan)).clip(-4.0, 4.0)
        psi_k = (z_k * np.exp(-(z_k ** 2) / 4.0)) / norm_const
        z_dict[label] = z_k
        psi_dict[label] = psi_k

    # Composite continuous CTA signal in [-1, +1] and long-only clipped version in [0, 1]
    z_comp = (z_dict["st"] + z_dict["mt"] + z_dict["lt"]) / 3.0
    psi_comp = (psi_dict["st"] + psi_dict["mt"] + psi_dict["lt"]) / 3.0
    psi_long = psi_comp.clip(lower=0.0, upper=1.0)
    # Also linear clipped version (without the Baz overextension dampener) to test whether the dampener helps
    lin_long = (z_comp / np.sqrt(2.0)).clip(lower=0.0, upper=1.0)

    # Realized volatility (dual-decay EWMA vol used by GS / CTAs: fast 10d + slow 30d blend, plus standard 21d)
    rv21 = r.rolling(21).std(ddof=1) * np.sqrt(252)
    rv_ewma_fast = r.ewm(halflife=10, min_periods=10).std() * np.sqrt(252)
    rv_ewma_slow = r.ewm(halflife=30, min_periods=21).std() * np.sqrt(252)
    rv_cta = 0.5 * rv_ewma_fast + 0.5 * rv_ewma_slow
    med_rv21 = rv21.expanding(min_periods=252).median()

    # Volatility scaling weights:
    # (1) CTA standard target-vol scaling: w_vol_cta = min(1, med_rv21 / rv_cta) (1/sigma scaling)
    # (2) Moreira-Muir variance scaling:   w_var_vm  = min(1, (med_rv21 / rv21)^2) (1/sigma^2 scaling)
    w_vol_1 = (med_rv21 / rv_cta).clip(upper=1.0)
    w_var_2 = ((med_rv21 / rv21) ** 2).clip(upper=1.0)

    # BofA-style Trailing Volatility Stop:
    # Drawdown from 20-day rolling peak measured in daily volatility units (rv21 / sqrt(252))
    dd_20d = p / p.rolling(20).max() - 1.0
    daily_sigma = (rv21 / np.sqrt(252)).replace(0, np.nan)
    dd_sigma_units = dd_20d / daily_sigma  # e.g. -3.0 means dropped 3 daily sigmas from 20d peak
    stop_triggered = (dd_sigma_units <= -3.0).astype(float)

    # Total Institutional CTA Equity Exposure (unclipped notional in [0, 2] for flow estimation)
    # In real CTAs, low vol allows leverage up to ~2x normal when psi_long is near 1.0
    cta_notional = psi_long * (med_rv21 / rv_cta).clip(upper=2.0)
    cta_flow_5d = cta_notional.diff(5)  # 5-day forced buying (+) or selling (-) flow

    # Trigger distance / clustering: how close are ST, MT, LT crossovers to 0 (in daily sigma units)?
    # For an EWMA pair, crossing 0 occurs when fast == slow. Distance in z-units is |z_k|.
    # "Clustered vulnerability" = all 3 speeds are currently positive (z_k > 0) AND at least 2 speeds are within 0.75 sigma of flipping!
    in_crowded_long = (cta_notional.shift(5) >= cta_notional.expanding(min_periods=252).quantile(0.70))

    return pd.DataFrame({
        "p": p,
        "r": r,
        "z_st": z_dict["st"],
        "z_mt": z_dict["mt"],
        "z_lt": z_dict["lt"],
        "z_comp": z_comp,
        "psi_st": psi_dict["st"],
        "psi_mt": psi_dict["mt"],
        "psi_lt": psi_dict["lt"],
        "psi_comp": psi_comp,
        "psi_long": psi_long,
        "lin_long": lin_long,
        "rv21": rv21,
        "rv_cta": rv_cta,
        "med_rv21": med_rv21,
        "w_vol_1": w_vol_1,
        "w_var_2": w_var_2,
        "dd_20d": dd_20d,
        "dd_sigma": dd_sigma_units,
        "stop_trig": stop_triggered,
        "cta_notional": cta_notional,
        "cta_flow_5d": cta_flow_5d,
        "crowded_long_5d_ago": in_crowded_long,
    })

ixic = yahoo("_IXIC")
df_ixic_full = build_institutional_cta_features(ixic)
df_ixic = df_ixic_full.loc["1985-04-01":"2026-10-31"].copy()

# =============================================================================
# PART 1: WHY GOLDMAN'S "CTA CLIFF" IS REAL — CROWDED vs UNCROWDED BREAKDOWNS
# =============================================================================
print("=====================================================================================================")
print("PART 1: TESTING GOLDMAN SACHS'S 'ASYMMETRIC CTA CLIFF' HYPOTHESIS (1985-2026, 41.5 YEARS DAILY)")
print("=====================================================================================================")
# Compare what happens when medium-term trend breaks (z_mt drops by >0.5 sigma over 5 days or crosses below +0.5):
# Case A: CTAs were CROWDED LONG 5 days ago (cta_notional in top 30%) AND vol spikes -> Forced Selling Cliff!
# Case B: CTAs were NOT crowded (already light position) -> Nothing happens / quick bounce!

p_arr = df_ixic["p"]
fwd_5d = p_arr.shift(-5) / p_arr - 1.0
fwd_10d = p_arr.shift(-10) / p_arr - 1.0
fwd_21d = p_arr.shift(-21) / p_arr - 1.0
df_ixic["fwd_5d"] = fwd_5d
df_ixic["fwd_10d"] = fwd_10d
df_ixic["fwd_21d"] = fwd_21d

# Define a 5-day price pullback of -3% to -6% (typical trigger breach window Goldman writes about)
dip_mask = (df_ixic["p"] / df_ixic["p"].shift(5) - 1.0).between(-0.06, -0.025)

# Sub-cases during a -2.5% to -6% weekly pullback:
# 1. Crowded CTA Long + Trend breaking + Vol spiking (CTA forced liquidation in progress, but NOT washed out yet: z_comp still > 0)
cliff_start = dip_mask & df_ixic["crowded_long_5d_ago"] & (df_ixic["z_comp"] > 0.0) & (df_ixic["rv_cta"] > df_ixic["rv_cta"].shift(5) * 1.15)
# 2. Uncrowded pullback (CTAs were already light 5 days ago)
uncrowded_dip = dip_mask & (~df_ixic["crowded_long_5d_ago"])
# 3. CTA Complete Washout / Capitulation (z_comp <= -1.0 and dd_sigma <= -3.0: CTAs have already puked everything!)
cta_washout = (df_ixic["z_comp"] <= -1.0) & (df_ixic["dd_sigma"] <= -3.0)

for label, m in [
    ("All -2.5%..-6% 5d pullbacks (unconditional)", dip_mask),
    ("  A. Pullback from CROWDED CTA Long + Vol Spike (CTA Cliff starting, still long)", cliff_start),
    ("  B. Pullback when CTAs UNCROWDED (already light position)", uncrowded_dip),
    ("  C. After CTA CAPITULATION / WASHOUT (z_comp <= -1.0 & -3sigma stop hit)", cta_washout),
]:
    sub = df_ixic[m].dropna(subset=["fwd_5d", "fwd_10d", "fwd_21d"])
    # Ann vol during next 10 days
    print(
        f"  {label:<78} | Days={len(sub):4d} | "
        f"Next 5d: {sub['fwd_5d'].mean():+6.2%} | "
        f"Next 10d: {sub['fwd_10d'].mean():+6.2%} | "
        f"Next 21d: {sub['fwd_21d'].mean():+6.2%} (WR {(sub['fwd_21d']>0).mean():.0%})"
    )

# Also check the Baz et al. (2015) Overextension Zone (z_comp > +2.0 vs normal +0.5..+1.5):
print("\n-----------------------------------------------------------------------------------------------------")
print("PART 1B: BAZ / MAN AHL OVEREXTENSION CURVE — WHAT HAPPENS WHEN TREND Z-SCORE IS EXTREME?")
print("-----------------------------------------------------------------------------------------------------")
for z_label, z_mask in [
    ("Moderate Uptrend (0.5 <= z_comp < 1.5, Peak of Baz Curve)", (df_ixic["z_comp"] >= 0.5) & (df_ixic["z_comp"] < 1.5)),
    ("Overextended Uptrend (z_comp >= 2.0, Baz Curve auto-trims position!)", df_ixic["z_comp"] >= 2.0),
    ("Mild Downtrend (-1.5 < z_comp < 0.0)", (df_ixic["z_comp"] < 0.0) & (df_ixic["z_comp"] > -1.5)),
    ("Deep Oversold / Capitulation (z_comp <= -1.5)", df_ixic["z_comp"] <= -1.5),
]:
    sub = df_ixic[z_mask].dropna(subset=["fwd_21d"])
    # Compute annualized 1x and 3x daily return on days in this regime
    # Wait: use next-day return r.shift(-1) so strictly no look-ahead!
    r_next = df_ixic["r"].shift(-1).loc[z_mask].dropna()
    r1_ann = (1.0 + r_next).prod() ** (252.0 / len(r_next)) - 1.0
    r3_ann = (1.0 + 3.0 * r_next - 0.03 / 252.0).prod() ** (252.0 / len(r_next)) - 1.0
    vol_ann = r_next.std(ddof=1) * np.sqrt(252)
    print(
        f"  {z_label:<68} | Days={len(r_next):4d} | "
        f"Next-Day Ann(1x): {r1_ann:+6.1%} | Ann(3x): {r3_ann:+6.1%} | Future Vol: {vol_ann:5.1%}"
    )

# =============================================================================
# PART 2: BACKTEST INSTITUTIONAL CTA MODELS vs TOY SMA vs B5 (1985-2026 & 2010-2026 TQQQ)
# =============================================================================
ETF_DIR = os.path.join(ROOT, "outputs", "remediation_full_audit_20261104", "tiingo_etfs")
def load_etf_close(sym):
    d = json.load(open(os.path.join(ETF_DIR, f"{sym}.json")))
    s = pd.Series({pd.Timestamp(r["date"][:10]): float(r["adjClose"]) for r in d}).sort_index()
    return s[~s.index.duplicated(keep="last")]

qqq_p = load_etf_close("QQQ")
tqqq_p = load_etf_close("TQQQ")
bil_p = load_etf_close("BIL")
sgov_p = load_etf_close("SGOV")
df_qqq = build_institutional_cta_features(qqq_p)

rf_d = (fred("DGS3MO") / 100.0).reindex(df_ixic.index).ffill().bfill() / 252.0
borrow_spread = 0.005 / 252.0
synth_m = {0: {}, 1: {}, 3: {}}
for t in T:
    days = df_ixic.loc[(df_ixic.index > t) & (df_ixic.index <= t + pd.offsets.MonthEnd(1))].index
    synth_m[0][t] = float((1.0 + rf_d.loc[days]).prod() - 1.0)
    for L, er in ((1, 0.0020), (3, 0.0095)):
        d_lev = L * df_ixic["r"].loc[days] - (L - 1) * (rf_d.loc[days] + borrow_spread) - er / 252.0
        synth_m[L][t] = float((1.0 + d_lev).prod() - 1.0)

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

COST = 0.0010

def sim_inst(weight_fn, t_list, ret_dict, feat_df, daily_dict=None):
    m_rets = {}
    d_rets = []
    prev_w = 0.0
    for t in t_list:
        sep_on = bool(real_sep[t]) if t >= pd.Timestamp("2015-11-30") else bool(sig["SEP_PROXY"][t])
        row = feat_df.loc[:t].iloc[-1]
        w = float(np.clip(weight_fn(sep_on, row), 0.0, 1.0))
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

inst_strats = {
    # 1. Pure Institutional CTA (No SEP macro filter) — compare against Toy SMA CTA!
    "I1. Institutional CTA Continuous Signal Only (Baz psi_long, No Vol Scale, No SEP)":
        lambda sep, r: float(r["psi_long"]),
    "I2. Institutional CTA + Target-Vol 1/sigma (psi_long * w_vol_1, No SEP)":
        lambda sep, r: float(r["psi_long"] * r["w_vol_1"]),
    "I3. Institutional CTA + Variance 1/sigma^2 (psi_long * w_var_2, No SEP)":
        lambda sep, r: float(r["psi_long"] * r["w_var_2"]),

    # 2. Baseline B5 vs Combining Institutional CTA with SEP + VM
    "B5. Baseline: SEP + Variance Scaling (w_var_2, No CTA trend filter)":
        lambda sep, r: float(r["w_var_2"]) if sep else 0.0,
    "I4. SEP + Dual-EWMA CTA Vol Scaling (w_vol_1: 10d/30d EWMA 1/sigma)":
        lambda sep, r: float(r["w_vol_1"]) if sep else 0.0,
    "I5. SEP + Fast/Slow Variance Scaling (min of 21d var & 10d/30d CTA EWMA var)":
        lambda sep, r: float(min(r["w_var_2"], (r["med_rv21"] / r["rv_cta"]) ** 2)) if sep else 0.0,
    "I6. SEP + VM * Institutional CTA Continuous Signal (w_var_2 * psi_long)":
        lambda sep, r: float(r["w_var_2"] * r["psi_long"]) if sep else 0.0,
    "I7. SEP + VM + Baz Overextension Trim Only (trim when z_comp > sqrt(2))":
        lambda sep, r: float(r["w_var_2"] * (r["psi_long"] if r["z_comp"] > np.sqrt(2.0) else 1.0)) if sep else 0.0,
    "I8. SEP + VM + BofA -3sigma Trailing Vol Stop (halve weight on -3sigma drop)":
        lambda sep, r: float(r["w_var_2"] * (0.5 if r["stop_trig"] > 0 else 1.0)) if sep else 0.0,
    "I9. SEP + VM, but when SEP=OFF allow Institutional CTA Uptrend (0.5*psi_long*w_var_2)":
        lambda sep, r: float(r["w_var_2"]) if sep else float(0.5 * r["psi_long"] * r["w_var_2"]),
}

b5_all, _ = sim_inst(inst_strats["B5. Baseline: SEP + Variance Scaling (w_var_2, No CTA trend filter)"], T, synth_m, df_ixic_full)
b5_etf, _ = sim_inst(inst_strats["B5. Baseline: SEP + Variance Scaling (w_var_2, No CTA trend filter)"], T_etf, actual_m, df_qqq)

rows_out = []
for name, fn in inst_strats.items():
    sm_all, _ = sim_inst(fn, T, synth_m, df_ixic_full)
    sm_85_09 = sm_all.loc[:"2009-12-31"]
    sm_etf, sd_etf = sim_inst(fn, T_etf, actual_m, df_qqq, daily_dict=actual_d)

    m_all = metrics(sm_all, rf_synth_ser)
    m_85 = metrics(sm_85_09, rf_synth_ser)
    m_etf = metrics(sm_etf, rf_etf_ser, s_d=sd_etf)

    if name.startswith("B5."):
        t_etf = 0.0
    else:
        de = (sm_etf - b5_etf).dropna()
        t_etf = float(de.mean() / de.std(ddof=1) * np.sqrt(len(de))) if de.std(ddof=1) > 0 else 0.0

    rows_out.append({
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

res_inst = pd.DataFrame(rows_out)
res_inst.to_csv(os.path.join(OUT, "cta_institutional_1985_2026_summary.csv"), index=False)
pd.set_option("display.width", 260)
pd.set_option("display.max_columns", 20)
print("\n=====================================================================================================")
print("PART 2: INSTITUTIONAL CTA MODEL (BAZ/AHL EWMA + VOL + RESPONSE CURVE) vs B5 (1985-2026 & 2010-2026)")
print("=====================================================================================================")
print(res_inst.to_string(index=False))
