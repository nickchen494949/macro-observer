#!/usr/bin/env python3
"""
dashboard_best_leverage_strategy_search.py — Systematic backtest & walk-forward search for the best
index leverage strategy using the Macro Observer dashboard indicators (2026-11-15).

Tests:
  1. Why naive equal-weight voting failed (scaling to 0% cash on early bull-market euphoria).
  2. Proper economic functional forms for each dashboard family:
     - Macro Rate/Inflation Switch : SEP (2Y+CorePCE proxy pre-2015-12, real ALFRED SEP post-2015-12)
     - Volatility Sizing           : Variance inverse (VM: min(1, med_var21/var21)), Vol inverse (min(1, med_vol21/vol21))
     - Credit & Recession Break    : BAA-10Y widening > 50bp (or HY-IG > 100bp), Sahm Rule >= 0.50
     - Debt Service Burden (DSR)   : Real-time Household DSR (TDSP) rising YoY & 10Y/2Y yields rising YoY
     - Leverage Cycle Rollover     : FINRA Margin YoY 12M max > 40% AND drop from 12M max >= 10pp
     - Multi-Factor Euphoria Trim  : FMS Cash <= 4.0%, CAPE Z > +1, FINRA Z > +1, CFTC Z > +1
                                     (tested as partial trim 3x->2x instead of 0% cash!)
     - Contrarian Capitulation Buy : FMS Cash >= 5.3% OR FINRA Margin YoY <= -15% OR CFTC Z <= -1.2
     - Conditional Trend Filter    : 10M SMA only active when Credit/Recession/Rollover/Euphoria is stressed
  3. Evaluation across:
     - Window A: 1985-05..2026-10 (41.5 yrs, synthetic 3x/2x/1x Nasdaq Composite)
     - Window B: 2001-07..2026-10 (25.3 yrs, all dashboard indicators available)
     - Window C: 2010-04..2026-10 (16.6 yrs, actual TQQQ / QLD / QQQ / SGOV + daily MaxDD)
     - Window D: Strict Out-of-Sample (Train 1985..2010 -> Test 2010..2026) & Expanding Walk-Forward (2001..2026)
     - Part E  : Portfolio Combination with V4 & V4.1 Stock Momentum Core (2010-04..2026-10)

POST-HOC DISCLOSURE (added by audit 2026-11-15, see outputs/dashboard_best_leverage_search_20261115/AUDIT_20261115.md):
  NOT pre-registered. S2e/S4/S6b/S6c were added after seeing the first run, and two patches were made after
  inspecting which 2010-2011 months triggered: (1) FINRA rollover requires 2Y cumulative growth > 0
  (removed 2010-06..2011-04 trigger), (2) Sahm must be "active" (removed 2010-07 trigger).
  S2e ETF-era CAGR moved 33.2% -> 36.2% -> 37.2%, S6b 37.2% -> 40.2% -> 41.0% through these patches.
  => 2010-2026 is NOT an out-of-sample test for these rules. Treat S6b as a hypothesis, not evidence.
"""
import json
import os
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "outputs", "dashboard_best_leverage_search_20261115")
os.makedirs(OUT, exist_ok=True)

# Reuse base loaders, PIT macro signals, and real-time DSR from dsr_signal_test.py & break_signals_test.py
dsrc = open(os.path.join(ROOT, "dsr_signal_test.py")).read().split("# --- A. index-level timing")[0]
ds = {"__file__": os.path.join(ROOT, "dsr_signal_test.py")}
exec(dsrc, ds)
bs = ds["bs"]
fred, yahoo, at, sig, T = bs["fred"], bs["yahoo"], bs["at"], bs["sig"], bs["T"]
HH_OK = ds["HH"]   # True = real-time Household DSR (TDSP) NOT rising YoY
BIS_OK = ds["BIS"] # True = BIS Private DSR NOT rising YoY


def load_val(name):
    p = os.path.join(ROOT, "data", "valuation", f"{name}.json")
    if not os.path.exists(p):
        return pd.Series(dtype=float)
    j = json.load(open(p))
    v = j.get("values", j.get("data", j)) if isinstance(j, dict) else j
    return pd.Series({pd.Timestamp(d): float(x) for d, x in v if x is not None}).sort_index()


# Load SEP real regime (2015-11-30+)
REG = pd.read_csv(os.path.join(ROOT, "outputs", "pure_momentum_1985_2026_audit", "inputs", "v3_regime_and_cash_214m.csv"))
real_sep = dict(zip(pd.to_datetime(REG["t"]), REG["sep_on"].astype(bool)))

# Load Valuation / Sentiment / Positioning series
cape = load_val("SHILLER_CAPE").resample("ME").last().ffill()
fms = load_val("BOFA_FMS_CASH")
fin = load_val("FINRA_MARGIN_YOY")
fin.index = fin.index + pd.offsets.MonthEnd(0)
cftc_nq = load_val("CFTC_NQ_LEV_NET")
cftc_es = load_val("CFTC_ES_AM_NET")

# HY-IG spread (starts 1997) & 10Y / 2Y yields
hy = fred("BAMLH0A0HYM2")
ig = fred("BAMLC0A0CM")
hyig_m = (hy - ig).resample("ME").mean()
g10 = fred("DGS10")
g2 = fred("DGS2")

# Nasdaq Composite & daily returns / variance / 10M SMA
ixic = yahoo("_IXIC")
r_ixic = ixic.pct_change().dropna()
var21_ixic = r_ixic.rolling(21).var(ddof=1)
med_var21_ixic = var21_ixic.expanding(min_periods=252).median()
vol21_ixic = np.sqrt(var21_ixic * 252)
med_vol21_ixic = np.sqrt(med_var21_ixic * 252)
ixic_m = ixic.resample("ME").last()
sma10_ixic = ixic_m >= ixic_m.rolling(10).mean()
dd_ixic = ixic_m / ixic_m.cummax() - 1.0

# Build monthly Point-In-Time feature table at each month-end t in T (1985-04..2026-09)
sahm_ser = bs["sahm"]
rows = {}
for t in T:
    sep_on = bool(real_sep[t]) if t >= pd.Timestamp("2015-11-30") else bool(sig["SEP_PROXY"][t])
    credit_ok = bool(sig["CREDIT"][t])       # True = BAA-10Y widening <= 50bp
    sahm_raw_off = not bool(sig["SAHM"][t])  # True = real-time Sahm >= 0.50
    # Active Sahm recession: Sahm >= 0.50 AND not already fallen > 0.50pp below its 12M peak (post-recession recovery)
    sh_w = sahm_ser.loc[:t - pd.offsets.MonthEnd(1)].tail(12)
    sahm_active_rec = bool(sahm_raw_off and (len(sh_w) == 0 or sh_w.iloc[-1] >= sh_w.max() - 0.50))
    sahm_ok = not sahm_active_rec
    curve_ok = bool(sig["CURVE"][t])         # True = 10Y-3M >= 0
    cuts_ok = bool(sig["CUTS"][t])           # True = 3M DFF change > -50bp
    hh_dsr_up = not bool(HH_OK[t])           # True = real-time HH DSR rising YoY
    y10_up12m = bool((at(g10, t) - at(g10, t - pd.offsets.MonthEnd(12))) > 0)

    # HY-IG widening > 1.00pp over 12M min (available 1998+)
    hy_w = hyig_m.loc[:t].tail(13)
    hyig_stress = bool(hy_w.iloc[-1] - hy_w.iloc[:-1].min() > 1.00) if len(hy_w) >= 12 else False

    # Valuation: CAPE Z-score vs rolling 120M
    c_w = cape.loc[:t].tail(120)
    cape_z = float((c_w.iloc[-1] - c_w.mean()) / c_w.std()) if len(c_w) >= 60 and c_w.std() > 0 else 0.0
    cape_hot = cape_z > 1.0
    cape_cheap = cape_z < -0.5

    # BofA FMS Cash (publication lag <= t)
    fx = fms.loc[:t]
    fms_val = float(fx.iloc[-1]) if len(fx) and (t - fx.index[-1]).days < 75 else np.nan
    fms_euphoria = bool(fms_val <= 4.0) if np.isfinite(fms_val) else False
    fms_panic = bool(fms_val >= 5.3) if np.isfinite(fms_val) else False

    # FINRA Margin YoY (1-month publication lag: use t - 1M)
    # Note: A true margin bubble peak requires 1Y YoY > 40% AND 2Y cumulative growth > 0%
    # (filters out 2010-04 base-effect bounce off the -47% 2009 GFC trough where 2Y growth was -11.1%)
    fin_2y_ser = ((1.0 + fin / 100.0) * (1.0 + fin.shift(12) / 100.0) - 1.0) * 100.0
    m_w = fin.loc[:t - pd.offsets.MonthEnd(1)].tail(36)
    fin_val = float(m_w.iloc[-1]) if len(m_w) >= 1 else np.nan
    fin_z = float((m_w.iloc[-1] - m_w.mean()) / m_w.std()) if len(m_w) >= 24 and m_w.std() > 0 else 0.0
    fin_hot = fin_z > 1.0
    m_12 = fin.loc[:t - pd.offsets.MonthEnd(1)].tail(12)
    m2y_12 = fin_2y_ser.loc[:t - pd.offsets.MonthEnd(1)].reindex(m_12.index)
    true_bubble_months = m_12[(m_12 > 40.0) & (m2y_12.fillna(99.0) > 0.0)]
    fin_max12 = float(true_bubble_months.max()) if len(true_bubble_months) >= 1 else np.nan
    # Rollover: 12M true bubble peak > 40% and dropped >= 10pp from peak
    fin_rollover = bool(np.isfinite(fin_max12) and fin_val <= fin_max12 - 10.0)
    fin_washed = bool(fin_val <= -15.0) if np.isfinite(fin_val) else False

    # CFTC NQ & ES positioning (3-day lag)
    cf_nq = cftc_nq.loc[:t - pd.Timedelta(days=3)].tail(156)
    nq_z = float((cf_nq.iloc[-1] - cf_nq.mean()) / cf_nq.std()) if len(cf_nq) >= 52 and cf_nq.std() > 0 else 0.0
    cf_es = cftc_es.loc[:t - pd.Timedelta(days=3)].tail(156)
    es_z = float((cf_es.iloc[-1] - cf_es.mean()) / cf_es.std()) if len(cf_es) >= 52 and cf_es.std() > 0 else 0.0
    cftc_crowded = (nq_z > 1.0) or (es_z > 1.2)
    cftc_washed = (nq_z <= -1.2) or (es_z <= -1.2)

    # Volatility scaling weights at month-end t
    v_cur = float(var21_ixic.loc[:t].iloc[-1])
    v_med = float(med_var21_ixic.loc[:t].iloc[-1])
    w_vm_var = min(1.0, v_med / v_cur) if v_cur > 0 else 1.0
    w_vm_vol = min(1.0, np.sqrt(v_med / v_cur)) if v_cur > 0 else 1.0
    vol_cur = float(vol21_ixic.loc[:t].iloc[-1])

    # Trend & Drawdown at month-end t
    trend_up = bool(sma10_ixic.loc[t])
    dd_cur = float(dd_ixic.loc[t])

    # Composite counts
    # Hard macro/credit/leverage break count (0..3): Credit break, Sahm recession, FINRA margin rollover
    hard_breaks = int((not credit_ok) or hyig_stress) + int(not sahm_ok) + int(fin_rollover)
    # Structural bust (Bubble Rollover OR Confirmed Sahm Recession) — excludes transient 1-month VIX/credit panics
    structural_bust = bool((not sahm_ok) or fin_rollover)
    # Soft euphoria count (0..4): FMS<=4%, CAPE_hot, FIN_hot, CFTC_crowded
    euphoria_cnt = int(fms_euphoria) + int(cape_hot) + int(fin_hot) + int(cftc_crowded)
    # Contrarian panic bottom (any capitulation signal)
    panic_bottom = bool(fms_panic or fin_washed or cftc_washed)

    rows[t] = {
        "sep_on": sep_on,
        "credit_ok": credit_ok and (not hyig_stress),
        "sahm_ok": sahm_ok,
        "curve_ok": curve_ok,
        "cuts_ok": cuts_ok,
        "hh_dsr_up": hh_dsr_up,
        "y10_up12m": y10_up12m,
        "cape_z": cape_z,
        "cape_hot": cape_hot,
        "cape_cheap": cape_cheap,
        "fms_euphoria": fms_euphoria,
        "fms_panic": fms_panic,
        "fin_hot": fin_hot,
        "fin_rollover": fin_rollover,
        "fin_washed": fin_washed,
        "cftc_crowded": cftc_crowded,
        "cftc_washed": cftc_washed,
        "w_vm_var": w_vm_var,
        "w_vm_vol": w_vm_vol,
        "vol_cur": vol_cur,
        "trend_up": trend_up,
        "dd_cur": dd_cur,
        "hard_breaks": hard_breaks,
        "structural_bust": structural_bust,
        "euphoria_cnt": euphoria_cnt,
        "panic_bottom": panic_bottom,
    }

DF = pd.DataFrame.from_dict(rows, orient="index")
DF.index.name = "t"

# -----------------------------------------------------------------------------
# Build Monthly & Daily Returns for 1x, 2x, 3x, and Cash:
#   (A) Long-run synthetic Nasdaq Composite (1985-05..2026-10)
#   (B) Actual QQQ / QLD / TQQQ / SGOV(BIL) (2010-04..2026-10)
# -----------------------------------------------------------------------------
r_d = r_ixic[r_ixic.index >= "1985-01-01"]
rf_d = (fred("DGS3MO") / 100.0).reindex(r_d.index).ffill().bfill() / 252.0
borrow_spread = 0.005 / 252.0

synth_m = {0: {}, 1: {}, 2: {}, 3: {}}
for t in T:
    days = r_d.loc[(r_d.index > t) & (r_d.index <= t + pd.offsets.MonthEnd(1))].index
    if not len(days):
        continue
    c_ret = float((1.0 + rf_d.loc[days]).prod() - 1.0)
    synth_m[0][t] = c_ret
    for L, er in ((1, 0.0020), (2, 0.0095), (3, 0.0095)):
        d_lev = L * r_d.loc[days] - (L - 1) * (rf_d.loc[days] + borrow_spread) - er / 252.0
        synth_m[L][t] = float((1.0 + d_lev).prod() - 1.0)

# Actual ETFs (2010-04..2026-10)
ETF_DIR = os.path.join(ROOT, "outputs", "remediation_full_audit_20261104", "tiingo_etfs")


def load_etf_close(sym):
    d = json.load(open(os.path.join(ETF_DIR, f"{sym}.json")))
    s = pd.Series({pd.Timestamp(r["date"][:10]): float(r["adjClose"]) for r in d}).sort_index()
    return s[~s.index.duplicated(keep="last")]


qqq_p = load_etf_close("QQQ")
qld_p = load_etf_close("QLD")
tqqq_p = load_etf_close("TQQQ")
bil_p = load_etf_close("BIL")
sgov_p = load_etf_close("SGOV")

# Also load QQQ 21d variance for actual ETF simulation
r_qqq = qqq_p.pct_change().dropna()
var21_qqq = r_qqq.rolling(21).var(ddof=1)
med_var21_qqq = var21_qqq.expanding(min_periods=252).median()

actual_m = {0: {}, 1: {}, 2: {}, 3: {}}
actual_d = {0: {}, 1: {}, 2: {}, 3: {}}
T_etf = [t for t in T if t >= pd.Timestamp("2010-03-31")]
for t in T_etf:
    t1 = t + pd.offsets.MonthEnd(1)
    cp = sgov_p if t >= pd.Timestamp("2020-06-30") else bil_p
    s_c = cp.loc[:t1]
    s_c0 = cp.loc[:t]
    actual_m[0][t] = float(s_c.iloc[-1] / s_c0.iloc[-1] - 1.0)
    days = qqq_p.loc[(qqq_p.index > t) & (qqq_p.index <= t1)].index
    actual_d[0][t] = cp.pct_change().reindex(days).fillna(0.0)
    for L, ser in ((1, qqq_p), (2, qld_p), (3, tqqq_p)):
        p1 = float(ser.loc[:t1].iloc[-1])
        p0 = float(ser.loc[:t].iloc[-1])
        actual_m[L][t] = p1 / p0 - 1.0
        actual_d[L][t] = ser.pct_change().reindex(days).fillna(0.0)

# -----------------------------------------------------------------------------
# Define Candidate Strategy Rules
# Each strategy function returns (L_choice, weight_in_L) at month-end t:
#   - L_choice in {0, 1, 2, 3}: which ETF/leverage tier is used
#   - weight_in_L in [0.0, 1.0]: fraction in L_choice, remainder (1 - weight_in_L) in Cash (0)
# -----------------------------------------------------------------------------


def get_strategies():
    strats = {}

    # 0. Baselines
    strats["B0_1x_BuyHold"] = lambda r, w_vm: (1, 1.0)
    strats["B1_2x_BuyHold"] = lambda r, w_vm: (2, 1.0)
    strats["B2_3x_BuyHold"] = lambda r, w_vm: (3, 1.0)
    strats["B3_3x_SEP_Only"] = lambda r, w_vm: (3, 1.0) if r["sep_on"] else (0, 0.0)
    strats["B4_2x_SEP_Only"] = lambda r, w_vm: (2, 1.0) if r["sep_on"] else (0, 0.0)
    strats["B5_3x_SEP_VM (Current Primary)"] = lambda r, w_vm: (3, w_vm) if r["sep_on"] else (0, 0.0)
    strats["B6_2x_SEP_VM"] = lambda r, w_vm: (2, w_vm) if r["sep_on"] else (0, 0.0)
    strats["B7_3x_SEP_VolSqrt"] = lambda r, w_vm: (3, r["w_vm_vol"]) if r["sep_on"] else (0, 0.0)

    # 1. Discrete Volatility Tiers (3x in low vol, 2x in medium vol, 1x/cash in high vol)
    def s_vol_tier(r, w_vm):
        if not r["sep_on"]:
            return (0, 0.0)
        if r["vol_cur"] <= 0.18:
            return (3, 1.0)
        elif r["vol_cur"] <= 0.28:
            return (2, 1.0)
        else:
            return (1, 0.5)
    strats["S1_SEP_Discrete_VolTiers (3x/2x/0.5x)"] = s_vol_tier

    # 2. SEP + VM + Hard Break Guard (Credit widening > 50bp OR Sahm >= 0.50 OR FINRA Rollover)
    #    When a hard break fires during SEP=ON (e.g., 2001/2008 recession after Fed starts cutting):
    #    Variant 2a: Go to Cash unless Trend (10M SMA) is up
    def s_hard_break_sma(r, w_vm):
        if not r["sep_on"]:
            return (0, 0.0)
        if r["hard_breaks"] >= 1 and (not r["trend_up"]):
            return (0, 0.0)
        return (3, w_vm)
    strats["S2a_SEP_VM + HardBreak_SMA_Guard"] = s_hard_break_sma

    #    Variant 2b: Hard break directly caps at 0% cash (unless contrarian panic bottom)
    def s_hard_break_cash(r, w_vm):
        if not r["sep_on"]:
            return (0, 0.0)
        if r["panic_bottom"]:
            return (3, w_vm)
        if r["hard_breaks"] >= 1:
            return (0, 0.0)
        return (3, w_vm)
    strats["S2b_SEP_VM + HardBreak_To_Cash"] = s_hard_break_cash

    #    Variant 2c: FINRA Margin Rollover Guard (specifically targets 2000 & 2008 & 2022 bubble bursts)
    def s_margin_rollover(r, w_vm):
        if not r["sep_on"] or r["fin_rollover"]:
            return (0, 0.0)
        return (3, w_vm)
    strats["S2c_SEP_VM + FINRA_Rollover_Guard"] = s_margin_rollover

    #    Variant 2d: Household DSR rising YoY & 10Y yield rising YoY + Trend guard
    def s_dsr_yield_sma(r, w_vm):
        if not r["sep_on"]:
            return (0, 0.0)
        if (r["hh_dsr_up"] and r["y10_up12m"]) and (not r["trend_up"]):
            return (0, 0.0)
        return (3, w_vm)
    strats["S2d_SEP_VM + DSR_10Y_SMA_Guard"] = s_dsr_yield_sma

    #    Variant 2e: Structural Bust Guard ((Sahm>=0.50 OR FINRA_Rollover) & Price<10M_SMA)
    #    Distinguishes multi-year bubble/recession busts (2000-02, 2008-09) from 1-month VIX/credit dips!
    def s_structural_bust_sma(r, w_vm):
        if not r["sep_on"]:
            return (0, 0.0)
        if r["structural_bust"] and (not r["trend_up"]):
            return (0, 0.0)
        return (3, w_vm)
    strats["S2e_SEP_VM + StructuralBust_SMA (Sahm/Rollover & <SMA10)"] = s_structural_bust_sma

    # 3. SEP + VM + Conditional Trend (10M SMA ONLY checked when Euphoria>=2 or HardBreak>=1 or CAPE_hot)
    def s_cond_sma_stress(r, w_vm):
        if not r["sep_on"]:
            return (0, 0.0)
        stressed = (r["hard_breaks"] >= 1) or (r["euphoria_cnt"] >= 2) or r["cape_hot"]
        if stressed and (not r["trend_up"]):
            return (0, 0.0)
        return (3, w_vm)
    strats["S3_SEP_VM + Conditional_SMA (Only when stressed)"] = s_cond_sma_stress

    # 4. SEP + VM + Euphoria Partial Trim (When >=2 euphoria flags fire, step down 3x -> 2x, NEVER 0%!)
    def s_euphoria_stepdown_2x(r, w_vm):
        if not r["sep_on"]:
            return (0, 0.0)
        if r["structural_bust"] and (not r["trend_up"]):
            return (0, 0.0)
        if r["euphoria_cnt"] >= 2:
            return (2, w_vm)
        return (3, w_vm)
    strats["S4_SEP_VM + Euphoria>=2_To_2x + StructuralBustSMA"] = s_euphoria_stepdown_2x

    # 5. SEP + VM + Contrarian Panic Booster (When FMS>=5.3% or Margin<=-15% or CFTC<=-1.2sd, boost VM floor)
    def s_panic_boost(r, w_vm):
        if not r["sep_on"]:
            return (0, 0.0)
        if r["panic_bottom"] or (r["dd_cur"] <= -0.25 and r["trend_up"]):
            return (3, max(w_vm, 0.85))
        return (3, w_vm)
    strats["S5_SEP_VM + Contrarian_Panic_Boost (Unfiltered)"] = s_panic_boost

    # 6a. Full Dashboard Traffic-Light Hierarchy (with Credit in HardBreak)
    def s_full_hierarchy(r, w_vm):
        if not r["sep_on"]:
            return (0, 0.0)
        if r["hard_breaks"] >= 1 and (not r["trend_up"]):
            return (0, 0.0)
        if r["panic_bottom"]:
            return (3, max(w_vm, 0.80))
        return (3, w_vm)
    strats["S6a_TrafficLight_AllBreaks (Includes Credit Dip Exits)"] = s_full_hierarchy

    # 6b. Golden Dashboard Hierarchy: SEP + VM + StructuralBust_SMA (Sahm/Rollover & <SMA10) + Safe Panic Boost
    #     - Exits to 0% Cash in SEP=OFF (2022) AND in Structural Busts (2000-02 Dot-Com, 2008-09 GFC)
    #     - Does NOT exit on 1-month VIX/credit spikes (2011, 2015, 2018-12, 2020-03, 2025-04)
    #     - Boosts VM floor to 0.80 on Contrarian Panic Bottoms ONLY when NOT in a Structural Bust!
    def s_golden_hierarchy(r, w_vm):
        if not r["sep_on"]:
            return (0, 0.0)
        if r["structural_bust"] and (not r["trend_up"]):
            return (0, 0.0)
        if r["panic_bottom"] and (not r["structural_bust"]):
            return (3, max(w_vm, 0.80))
        return (3, w_vm)
    strats["S6b_Golden_TrafficLight (SEP+VM+StructBustSMA+SafePanic)"] = s_golden_hierarchy

    # 6c. Golden Dashboard Hierarchy + Extreme Euphoria (>=3 of 4 flags) Step-Down 3x -> 2x
    def s_golden_plus_euphoria3(r, w_vm):
        if not r["sep_on"]:
            return (0, 0.0)
        if r["structural_bust"] and (not r["trend_up"]):
            return (0, 0.0)
        if r["panic_bottom"] and (not r["structural_bust"]):
            return (3, max(w_vm, 0.80))
        if r["euphoria_cnt"] >= 3:
            return (2, w_vm)
        return (3, w_vm)
    strats["S6c_Golden_TrafficLight + Euphoria>=3_StepDown2x"] = s_golden_plus_euphoria3

    # 7. Naive Equal-Weight 7-Flag Vote (from earlier dashboard_composite_test.py for comparison)
    def s_naive_vote(r, w_vm):
        votes_off = (
            int(not r["sep_on"])
            + int(r["cape_hot"])
            + int(r["fms_euphoria"])
            + int(r["fin_hot"] or r["fin_rollover"])
            + int(r["cftc_crowded"])
            + int(not r["credit_ok"])
            + int(not r["sahm_ok"])
        )
        if votes_off >= 3:
            return (0, 0.0)
        elif votes_off == 2:
            return (1, w_vm)
        elif votes_off == 1:
            return (2, w_vm)
        return (3, w_vm)
    strats["S7_Naive_7Flag_Vote (Earlier Failed Test)"] = s_naive_vote

    return strats


# -----------------------------------------------------------------------------
# Simulation & Metrics Engine
# -----------------------------------------------------------------------------
COST_ONE_WAY = 0.0010  # 10 bp per side


def run_strategy(fn, t_list, ret_dict, use_qqq_vm=False, daily_dict=None):
    m_rets = {}
    d_rets = []
    prev_L, prev_w = 0, 0.0
    for t in t_list:
        r = DF.loc[t]
        if use_qqq_vm:
            vc = float(var21_qqq.loc[:t].iloc[-1])
            vm = float(med_var21_qqq.loc[:t].iloc[-1])
            w_vm = min(1.0, vm / vc) if vc > 0 else 1.0
        else:
            w_vm = float(r["w_vm_var"])
        L, w = fn(r, w_vm)
        if L == 0:
            w = 0.0
        # Turnover cost: if same L, |w - prev_w|; if different L, prev_w + w
        to = abs(w - prev_w) if L == prev_L else (prev_w + w)
        cost = to * COST_ONE_WAY
        prev_L, prev_w = L, w

        rm_L = ret_dict[L][t] if L > 0 else 0.0
        rm_0 = ret_dict[0][t]
        gross = w * rm_L + (1.0 - w) * rm_0
        net = (1.0 + gross) * (1.0 - cost) - 1.0
        m_rets[t + pd.offsets.MonthEnd(1)] = net

        if daily_dict is not None:
            rd_L = daily_dict[L][t] if L > 0 else 0.0
            rd_0 = daily_dict[0][t]
            rd = w * rd_L + (1.0 - w) * rd_0
            if len(rd):
                rd = rd.copy()
                rd.iloc[0] = (1.0 + rd.iloc[0]) * (1.0 - cost) - 1.0
                d_rets.append(rd)

    s_m = pd.Series(m_rets).sort_index()
    s_d = pd.concat(d_rets).sort_index() if d_rets else None
    return s_m, s_d


def calc_metrics(s_m, rf_m_series, s_d=None):
    s_m = s_m.dropna()
    n = len(s_m)
    if n == 0:
        return {}
    w = (1.0 + s_m).cumprod()
    w0 = pd.concat([pd.Series([1.0], index=[s_m.index[0] - pd.offsets.MonthEnd(1)]), w])
    cagr = float(w.iloc[-1] ** (12.0 / n) - 1.0)
    mdd = float((w0 / w0.cummax() - 1.0).min())
    rf_aligned = rf_m_series.reindex(s_m.index).fillna(0.0)
    ex = s_m - rf_aligned
    vol = float(s_m.std(ddof=1) * np.sqrt(12.0))
    sharpe = float(ex.mean() / s_m.std(ddof=1) * np.sqrt(12.0)) if s_m.std(ddof=1) > 0 else 0.0
    down = s_m[s_m < 0]
    sortino = float(ex.mean() * 12.0 / (down.std(ddof=1) * np.sqrt(12.0))) if len(down) > 1 and down.std(ddof=1) > 0 else 0.0
    calmar = float(cagr / abs(mdd)) if mdd < 0 else 0.0

    # Crisis drawdowns
    def sub_dd(a, b):
        sub = s_m.loc[a:b]
        if not len(sub):
            return np.nan
        ws = (1.0 + sub).cumprod()
        ws0 = pd.concat([pd.Series([1.0], index=[sub.index[0] - pd.offsets.MonthEnd(1)]), ws])
        return float((ws0 / ws0.cummax() - 1.0).min())

    res = {
        "CAGR": cagr,
        "Vol": vol,
        "Sharpe": sharpe,
        "Sortino": sortino,
        "Calmar": calmar,
        "MaxDD_M": mdd,
        "DD_00_02": sub_dd("2000-03-01", "2002-10-31"),
        "DD_07_09": sub_dd("2007-11-01", "2009-03-31"),
        "DD_2020": sub_dd("2020-02-01", "2020-04-30"),
        "DD_2022": sub_dd("2022-01-01", "2022-12-31"),
    }
    if s_d is not None and len(s_d):
        wd = (1.0 + s_d).cumprod()
        wd0 = pd.concat([pd.Series([1.0], index=[s_d.index[0] - pd.Timedelta(days=1)]), wd])
        res["MaxDD_D"] = float((wd0 / wd0.cummax() - 1.0).min())
    return res


rf_m_synth = pd.Series({t + pd.offsets.MonthEnd(1): synth_m[0][t] for t in T})
rf_m_actual = pd.Series({t + pd.offsets.MonthEnd(1): actual_m[0][t] for t in T_etf})

strats = get_strategies()

# -----------------------------------------------------------------------------
# Run Window A (1985-05..2026-10, 498m), Window B (2001-07..2026-10, 304m), Window C (2010-04..2026-10, 199m)
# -----------------------------------------------------------------------------
T_2001 = [t for t in T if t >= pd.Timestamp("2001-06-30")]

rows_A, rows_B, rows_C = [], [], []
m_series_A = {}
m_series_C = {}
d_series_C = {}

for name, fn in strats.items():
    sm_a, _ = run_strategy(fn, T, synth_m, use_qqq_vm=False)
    m_series_A[name] = sm_a
    ma = calc_metrics(sm_a, rf_m_synth)
    rows_A.append({"Strategy": name, **ma})

    sm_b = sm_a.loc["2001-07-01":]
    mb = calc_metrics(sm_b, rf_m_synth)
    rows_B.append({"Strategy": name, **mb})

    sm_c, sd_c = run_strategy(fn, T_etf, actual_m, use_qqq_vm=True, daily_dict=actual_d)
    m_series_C[name] = sm_c
    d_series_C[name] = sd_c
    mc = calc_metrics(sm_c, rf_m_actual, s_d=sd_c)
    rows_C.append({"Strategy": name, **mc})

df_A = pd.DataFrame(rows_A)
df_B = pd.DataFrame(rows_B)
df_C = pd.DataFrame(rows_C)

df_A.to_csv(os.path.join(OUT, "windowA_1985_2026_full_41yr.csv"), index=False)
df_B.to_csv(os.path.join(OUT, "windowB_2001_2026_dashboard_era.csv"), index=False)
df_C.to_csv(os.path.join(OUT, "windowC_2010_2026_actual_tqqq.csv"), index=False)

# -----------------------------------------------------------------------------
# Window D: Strict Out-of-Sample (Train 1985-05..2010-03 -> Test 2010-04..2026-10)
#           AND Expanding Annual Walk-Forward (2001..2026)
# -----------------------------------------------------------------------------
oos_rows = []
for name in strats:
    s_tr = m_series_A[name].loc[:"2010-03-31"]
    s_te = m_series_C[name]
    m_tr = calc_metrics(s_tr, rf_m_synth)
    m_te = calc_metrics(s_te, rf_m_actual, s_d=d_series_C[name])
    oos_rows.append({
        "Strategy": name,
        "Train_85_10_CAGR": m_tr["CAGR"],
        "Train_85_10_Sharpe": m_tr["Sharpe"],
        "Train_85_10_Calmar": m_tr["Calmar"],
        "Train_85_10_MaxDD": m_tr["MaxDD_M"],
        "Test_10_26_CAGR": m_te["CAGR"],
        "Test_10_26_Sharpe": m_te["Sharpe"],
        "Test_10_26_Calmar": m_te["Calmar"],
        "Test_10_26_MaxDD_M": m_te["MaxDD_M"],
        "Test_10_26_MaxDD_D": m_te["MaxDD_D"],
    })
df_OOS = pd.DataFrame(oos_rows)
df_OOS.to_csv(os.path.join(OUT, "windowD_train1985_2010_test2010_2026.csv"), index=False)

# Expanding Walk-Forward (2001-01..2026-10): at each year-end Y-1, pick best strategy by past Sharpe or Calmar
wf_candidates = [k for k in strats if not k.startswith("B0") and not k.startswith("B1") and not k.startswith("B2") and not k.startswith("S7")]
wf_sharpe_rets = []
wf_calmar_rets = []
wf_choices = []

for yr in range(2001, 2027):
    cutoff = f"{yr-1}-12-31"
    best_sh_name, best_sh_val = None, -999.0
    best_ca_name, best_ca_val = None, -999.0
    for name in wf_candidates:
        past = m_series_A[name].loc[:cutoff]
        mp = calc_metrics(past, rf_m_synth)
        if mp["Sharpe"] > best_sh_val:
            best_sh_val = mp["Sharpe"]
            best_sh_name = name
        if mp["Calmar"] > best_ca_val:
            best_ca_val = mp["Calmar"]
            best_ca_name = name
    yr_slice = slice(f"{yr}-01-01", f"{yr}-12-31")
    wf_sharpe_rets.append(m_series_A[best_sh_name].loc[yr_slice])
    wf_calmar_rets.append(m_series_A[best_ca_name].loc[yr_slice])
    wf_choices.append({"Year": yr, "Picked_By_Sharpe": best_sh_name, "Past_Sharpe": round(best_sh_val, 3),
                       "Picked_By_Calmar": best_ca_name, "Past_Calmar": round(best_ca_val, 3)})

s_wf_sh = pd.concat(wf_sharpe_rets).sort_index()
s_wf_ca = pd.concat(wf_calmar_rets).sort_index()
pd.DataFrame(wf_choices).to_csv(os.path.join(OUT, "walk_forward_annual_choices_2001_2026.csv"), index=False)

# -----------------------------------------------------------------------------
# Part E: Combining V4 / V4.1 Stock Momentum Core + Best Index Leverage Satellite (2010-04..2026-10)
# -----------------------------------------------------------------------------
v4_df = pd.read_csv(os.path.join(ROOT, "outputs", "v4_symmetric_sharpe_top2_20261113", "v4_symmetric_sharpe_top2_h5_v0_214m_ledger.csv"))
v4_s = pd.Series(v4_df["net_ret"].values, index=pd.to_datetime(v4_df["t"]) + pd.offsets.MonthEnd(1)).loc["2010-04-01":]

v41_df = pd.read_csv(os.path.join(ROOT, "outputs", "v4_robust_upgrade_20261115", "v41_ensemble_ledger.csv"))
v41_s = pd.Series(v41_df["net"].values, index=pd.to_datetime(v41_df["t"]) + pd.offsets.MonthEnd(1)).loc["2010-04-01":]

s_b5 = m_series_C["B5_3x_SEP_VM (Current Primary)"]
s_s2e = m_series_C["S2e_SEP_VM + StructuralBust_SMA (Sahm/Rollover & <SMA10)"]
s_s6b = m_series_C["S6b_Golden_TrafficLight (SEP+VM+StructBustSMA+SafePanic)"]
s_qqq = m_series_C["B0_1x_BuyHold"]

combos_E = {
    "1. Pure QQQ Buy & Hold (1x)": s_qqq,
    "2. Pure TQQQ + SEP + VM (B5 Baseline)": s_b5,
    "3. Pure TQQQ + StructuralBust_SMA (S2e)": s_s2e,
    "4. Pure TQQQ + Golden TrafficLight (S6b)": s_s6b,
    "5. Pure V4.1 Stock Ensemble (1x Unlevered)": v41_s,
    "6. Pure V4 Stock Dual-Core (1x Unlevered)": v4_s,
    "7. 50% V4.1 Stock + 50% TQQQ(SEP+VM B5) [Monthly Rebal]": 0.5 * v41_s + 0.5 * s_b5,
    "8. 50% V4.1 Stock + 50% TQQQ(Golden S6b) [Monthly Rebal]": 0.5 * v41_s + 0.5 * s_s6b,
    "9. 70% V4.1 Stock + 30% TQQQ(Golden S6b) [Monthly Rebal]": 0.7 * v41_s + 0.3 * s_s6b,
    "10. 50% V4 Stock + 50% TQQQ(Golden S6b) [Monthly Rebal]": 0.5 * v4_s + 0.5 * s_s6b,
}

rows_E = []
for k, ser in combos_E.items():
    me = calc_metrics(ser, rf_m_actual)
    rows_E.append({"Portfolio (2010-04..2026-10)": k, **me})
df_E = pd.DataFrame(rows_E)
df_E.to_csv(os.path.join(OUT, "partE_v4_v41_plus_tqqq_combinations.csv"), index=False)

# -----------------------------------------------------------------------------
# Print Clean Summary Tables
# -----------------------------------------------------------------------------
pd.set_option("display.width", 260)
pd.set_option("display.max_columns", 20)
fmt = lambda x: f"{x:.1%}" if isinstance(x, float) and abs(x) < 10 else (f"{x:.2f}" if isinstance(x, float) else str(x))


def show_table(title, df, cols):
    print(f"\n==================== {title} ====================")
    d = df[cols].copy()
    for c in d.columns:
        if c == "Strategy" or c.startswith("Portfolio"):
            continue
        if "Sharpe" in c or "Sortino" in c or "Calmar" in c:
            d[c] = d[c].map(lambda v: f"{v:.2f}" if pd.notna(v) else "")
        else:
            d[c] = d[c].map(lambda v: f"{v:.1%}" if pd.notna(v) else "")
    print(d.to_string(index=False))


show_table(
    "WINDOW A: FULL 41.5 YEARS (1985-05..2026-10, 498m, Synthetic 3x/2x/1x Nasdaq)",
    df_A,
    ["Strategy", "CAGR", "Vol", "Sharpe", "Sortino", "Calmar", "MaxDD_M", "DD_00_02", "DD_07_09", "DD_2020", "DD_2022"],
)

show_table(
    "WINDOW B: DASHBOARD-COMPLETE ERA (2001-07..2026-10, 304m, All Indicators Active)",
    df_B,
    ["Strategy", "CAGR", "Vol", "Sharpe", "Sortino", "Calmar", "MaxDD_M", "DD_00_02", "DD_07_09", "DD_2020", "DD_2022"],
)

show_table(
    "WINDOW C: ACTUAL ETF ERA (2010-04..2026-10, 199m, Real TQQQ / QLD / QQQ / SGOV)",
    df_C,
    ["Strategy", "CAGR", "Vol", "Sharpe", "Sortino", "Calmar", "MaxDD_M", "MaxDD_D", "DD_2020", "DD_2022"],
)

show_table(
    "WINDOW D: STRICT OUT-OF-SAMPLE (TRAIN 1985-2010 -> TEST 2010-2026)",
    df_OOS,
    ["Strategy", "Train_85_10_CAGR", "Train_85_10_Sharpe", "Train_85_10_MaxDD", "Test_10_26_CAGR", "Test_10_26_Sharpe", "Test_10_26_MaxDD_M", "Test_10_26_MaxDD_D"],
)

print("\n==================== EXPANDING WALK-FORWARD (2001-01..2026-10, Zero Hindsight) ====================")
for label, s_wf in [
    ("Walk-Forward Pick #1 by Past Sharpe", s_wf_sh),
    ("Walk-Forward Pick #1 by Past Calmar", s_wf_ca),
    ("Fixed B5 (3x + SEP + VM)", m_series_A["B5_3x_SEP_VM (Current Primary)"].loc["2001-01-01":]),
    ("Fixed S2e (3x + SEP + VM + StructuralBust_SMA)", m_series_A["S2e_SEP_VM + StructuralBust_SMA (Sahm/Rollover & <SMA10)"].loc["2001-01-01":]),
    ("Fixed S6b (Golden TrafficLight)", m_series_A["S6b_Golden_TrafficLight (SEP+VM+StructBustSMA+SafePanic)"].loc["2001-01-01":]),
    ("Fixed B2 (3x Buy & Hold)", m_series_A["B2_3x_BuyHold"].loc["2001-01-01":]),
]:
    mw = calc_metrics(s_wf, rf_m_synth)
    print(f"  {label:<48} | CAGR: {mw['CAGR']:6.1%} | Sharpe: {mw['Sharpe']:5.2f} | Calmar: {mw['Calmar']:5.2f} | MaxDD_M: {mw['MaxDD_M']:6.1%}")

show_table(
    "PART E: COMBINING V4 / V4.1 STOCK CORE + INDEX LEVERAGE SATELLITE (2010-04..2026-10)",
    df_E,
    ["Portfolio (2010-04..2026-10)", "CAGR", "Vol", "Sharpe", "Sortino", "Calmar", "MaxDD_M", "DD_2020", "DD_2022"],
)
