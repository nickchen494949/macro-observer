#!/usr/bin/env python3
"""
run_every_dec_reset_audit.py
============================
Tests the User's Occam's-Razor Hypothesis:
  "还是其实每个 dec reset is good?" (Is resetting EVERY December actually good?)

Evaluates all interpretations of "Every Dec Reset" on both `Current (A1-RS 1.35x)` and `Tech-Arena (TAC-1_A1Sec 1.35x)`:
  1. Year- by-Year Anatomy of all 17 Decembers (2009-12 .. 2025-12) and all 17 Januaries (2010-01 .. 2026-01):
     - What happens if you clear buffers (`held = []`) at EVERY Dec 31 close (entering Jan)?
     - Which specific Januaries change holdings when `held = []` is cleared at Dec 31 close, and what is the return delta in each year?
  2. Full Backtest Comparison across 10 Variants:
     - `00. V0 (No SGOV, No Buffer Reset ever)`
     - `01. Only Buffer Reset in Unified->Divided Dec 31 (3 times: 2010, 2018, 2022, no SGOV) [V1]`
     - `02. Only Buffer Reset in All Midterm Dec 31 (4 times: 2010, 2014, 2018, 2022, no SGOV)`
     - `03. Only Buffer Reset in All Election Dec 31 (8 times: 2010..2024 even years, no SGOV)`
     - `04. Buffer Reset EVERY Year Dec 31 (All 17 years 2009..2025, no SGOV) [Annual Year-End Buffer Cleanse]`
     - `05. Frozen V3: SGOV in Unified->Divided Dec (3 times) + Buffer Reset ONLY in Unified->Divided Dec 31 (3 times)`
     - `06. SGOV in Unified->Divided Dec (3 times) + Buffer Reset in ALL Election Dec 31 (8 even years)`
     - `07. SGOV in Unified->Divided Dec (3 times) + Buffer Reset EVERY Year Dec 31 (All 17 years)`
     - `08. SGOV in ALL Election Dec (8 even years) + Buffer Reset in ALL Election Dec 31`
     - `09. SGOV EVERY Year Dec (All 17 years) + Buffer Reset EVERY Year Dec 31`
  3. Calendar-Month Placebo Test (M1..M12):
     - If you do an Annual Buffer Reset (`held = []`) once a year at month M (Jan, Feb, ..., Dec), how does December compare to the other 11 months?
"""
import os
import sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run_election_duration_consistency_audit as base

OUT_DIR = HERE
MID_U2D_YRS = [2010, 2018, 2022]
ALL_MID_YRS = [2010, 2014, 2018, 2022]
ALL_ELEC_YRS = [2010, 2012, 2014, 2016, 2018, 2020, 2022, 2024]
ALL_YRS = list(range(2009, 2026))  # 2009..2025 have Dec (holding month YYYY-12) and Jan next year (YYYY+1-01)

# Helper to get formation dates t
def get_dec_sgov_t(years):
    # Holding month YYYY-12 is formed at YYYY-11 close
    return {base.ym_to_t[f"{y}-12"] for y in years if f"{y}-12" in base.ym_to_t}

def get_dec_end_reset_t(years):
    # Resetting at YYYY-12 close affects holding month (YYYY+1)-01
    return {base.ym_to_t[f"{y+1}-01"] for y in years if f"{y+1}-01" in base.ym_to_t}

# -------------------------------------------------------------------------
# 1. Compare All 10 "Dec Reset" Variants
# -------------------------------------------------------------------------
DEC_VARIANTS = [
    ("00_V0_NoSGOV_NoReset",                                  set(),                          set()),
    ("01_V1_NoSGOV_Reset_U2D_Midterm_Only (3 yrs)",           set(),                          get_dec_end_reset_t(MID_U2D_YRS)),
    ("02_NoSGOV_Reset_All_Midterms (4 yrs)",                  set(),                          get_dec_end_reset_t(ALL_MID_YRS)),
    ("03_NoSGOV_Reset_All_Elections_EvenYrs (8 yrs)",         set(),                          get_dec_end_reset_t(ALL_ELEC_YRS)),
    ("04_NoSGOV_Reset_EVERY_Dec31_AllYears (17 yrs)",         set(),                          get_dec_end_reset_t(ALL_YRS)),
    ("05_Frozen_V3_SGOV_U2D_And_Reset_U2D_Only (3 yrs)",      get_dec_sgov_t(MID_U2D_YRS),    get_dec_end_reset_t(MID_U2D_YRS)),
    ("06_SGOV_U2D_And_Reset_All_Midterms (4 yrs)",            get_dec_sgov_t(MID_U2D_YRS),    get_dec_end_reset_t(ALL_MID_YRS)),
    ("07_SGOV_U2D_And_Reset_All_Elections_EvenYrs (8 yrs)",   get_dec_sgov_t(MID_U2D_YRS),    get_dec_end_reset_t(ALL_ELEC_YRS)),
    ("08_SGOV_U2D_And_Reset_EVERY_Dec31_AllYears (17 yrs)",   get_dec_sgov_t(MID_U2D_YRS),    get_dec_end_reset_t(ALL_YRS)),
    ("09_SGOV_All_Elections_Dec_And_Reset_All_Elections (8y)",get_dec_sgov_t(ALL_ELEC_YRS),   get_dec_end_reset_t(ALL_ELEC_YRS)),
    ("10_SGOV_EVERY_Dec_AllYears_And_Reset_EVERY_Dec31 (17y)",get_dec_sgov_t(ALL_YRS),        get_dec_end_reset_t(ALL_YRS)),
]

var_rows = []
sim_cache = {}
for strat_name, is_tac in [("Current_A1RS", False), ("TechArena_TAC1_A1Sec", True)]:
    for v_name, sgov_set, rst_set in DEC_VARIANTS:
        rst_map_q = {t: "sharpe" for t in rst_set}
        rst_map_s = {t: "mom" for t in rst_set}

        pk_q = base.select_ndx_flex(base.p_ndx, "sharpe", 2, 5, rst_map_q)
        pk_t = base.select_tech_arena_flex("mom", rst_map_s) if is_tac else base.select_spx_flex(base.p_tech, "mom", 1, 1, None, None, rst_map_s)
        pk_s = base.select_spx_flex(base.p_spx, "mom", 1, 3, "rs_gics", -0.05, rst_map_s)
        pk_er = base.select_spx_flex(base.p_exit, "mom", 1, 3, "rs_gics", -0.05, rst_map_s)
        pk_eb = base.select_bestsec_flex(base.p_exit, "mom", "rs_gics", -0.05, rst_map_s)

        df_sim = base.simulate_monthly(
            pk_q, pk_t, pk_s, pk_er, pk_eb,
            sgov_t_set=sgov_set,
            a1_mode=("sector" if is_tac else "ticker")
        )
        sim_cache[(strat_name, v_name)] = df_sim
        m = base.calc_summary_metrics(df_sim)
        ym_ret = dict(zip(df_sim["ym"], df_sim["net_ret"]))
        jan_all = [ym_ret[f"{y+1}-01"] for y in ALL_YRS]
        dec_all = [ym_ret[f"{y}-12"] for y in ALL_YRS]
        var_rows.append({
            "strategy": strat_name,
            "variant": v_name,
            "n_sgov_decs": len(sgov_set),
            "n_reset_decs": len(rst_set),
            "cagr_213_pct": m["cagr_213_pct"],
            "cagr_214_pct": m["cagr_214_pct"],
            "sharpe_213": m["sharpe_213"],
            "sharpe_214": m["sharpe_214"],
            "mdd_monthly_pct": m["mdd_monthly_pct"],
            "turnover_2way_yr": m["turnover_2way_yr"],
            "mean_17_Dec_ret_pct": round(float(np.mean(dec_all)) * 100, 2),
            "mean_17_Jan_ret_pct": round(float(np.mean(jan_all)) * 100, 2),
        })

df_dec_vars = pd.DataFrame(var_rows)
df_dec_vars.to_csv(os.path.join(OUT_DIR, "12_every_dec_reset_variants_summary.csv"), index=False)

print("\n=== 1. Every Dec Reset Variants Summary ===")
print(df_dec_vars.to_string(index=False))

# -------------------------------------------------------------------------
# 2. Year-by-Year (2009-2025, 17 Years) Anatomy:
#    No Reset vs Every Dec 31 Buffer Reset (Which years change & why?)
# -------------------------------------------------------------------------
df_no_rst = sim_cache[("Current_A1RS", "00_V0_NoSGOV_NoReset")].set_index("ym")
df_all_rst = sim_cache[("Current_A1RS", "04_NoSGOV_Reset_EVERY_Dec31_AllYears (17 yrs)")].set_index("ym")
df_v3_u2d = sim_cache[("Current_A1RS", "05_Frozen_V3_SGOV_U2D_And_Reset_U2D_Only (3 yrs)")].set_index("ym")
df_v3_allrst = sim_cache[("Current_A1RS", "08_SGOV_U2D_And_Reset_EVERY_Dec31_AllYears (17 yrs)")].set_index("ym")

yby_rows = []
for y in ALL_YRS:
    ym_dec = f"{y}-12"
    ym_jan = f"{y+1}-01"
    if y in MID_U2D_YRS:
        y_type = "1_Midterm_U2D_Flip"
    elif y in ALL_MID_YRS:
        y_type = "2_Midterm_NoFlip"
    elif y in ALL_ELEC_YRS:
        y_type = "3_Presidential"
    else:
        y_type = "4_Odd_NonElection_Yr"

    r_dec_raw = float(df_no_rst.loc[ym_dec, "net_ret"]) * 100
    r_jan_no_rst = float(df_no_rst.loc[ym_jan, "net_ret"]) * 100
    r_jan_all_rst = float(df_all_rst.loc[ym_jan, "net_ret"]) * 100
    jan_diff = r_jan_all_rst - r_jan_no_rst

    # Also compute full next calendar year (y+1) cumulative return with vs without Dec 31 reset
    next_yr_months = [f"{y+1}-{m:02d}" for m in range(1, 13) if f"{y+1}-{m:02d}" in df_no_rst.index]
    ret_yr_no_rst = (float(np.prod(1.0 + df_no_rst.loc[next_yr_months, "net_ret"])) - 1.0) * 100
    ret_yr_all_rst = (float(np.prod(1.0 + df_all_rst.loc[next_yr_months, "net_ret"])) - 1.0) * 100
    yr_diff = ret_yr_all_rst - ret_yr_no_rst

    picks_no = f"Q:{df_no_rst.loc[ym_jan,'q1']}/{df_no_rst.loc[ym_jan,'q2']} | T:{df_no_rst.loc[ym_jan,'t1']} | S:{df_no_rst.loc[ym_jan,'s1']}"
    picks_rst = f"Q:{df_all_rst.loc[ym_jan,'q1']}/{df_all_rst.loc[ym_jan,'q2']} | T:{df_all_rst.loc[ym_jan,'t1']} | S:{df_all_rst.loc[ym_jan,'s1']}"
    changed = (picks_no != picks_rst)

    yby_rows.append({
        "dec_year": y,
        "year_type": y_type,
        "Dec_raw_ret_pct": round(r_dec_raw, 2),
        "Jan_ym": ym_jan,
        "picks_changed_on_reset": changed,
        "Jan_NoReset_pct": round(r_jan_no_rst, 2),
        "Jan_WithDecReset_pct": round(r_jan_all_rst, 2),
        "Jan_Reset_Delta_pp": round(jan_diff, 2),
        "FullNextYr_NoReset_pct": round(ret_yr_no_rst, 2),
        "FullNextYr_WithDecReset_pct": round(ret_yr_all_rst, 2),
        "FullNextYr_Delta_pp": round(yr_diff, 2),
        "picks_NoReset": picks_no,
        "picks_WithDecReset": picks_rst,
    })

df_yby = pd.DataFrame(yby_rows)
df_yby.to_csv(os.path.join(OUT_DIR, "13_year_by_year_17decs_reset_anatomy.csv"), index=False)

print("\n=== 2. Year-by-Year (2009-2025) Dec Return & Jan Reset Impact ===")
print(df_yby[["dec_year", "year_type", "Dec_raw_ret_pct", "Jan_ym", "picks_changed_on_reset", "Jan_NoReset_pct", "Jan_WithDecReset_pct", "Jan_Reset_Delta_pp", "FullNextYr_Delta_pp", "picks_NoReset", "picks_WithDecReset"]].to_string(index=False))

print("\n=== 2B. Group Averages by Year Type ===")
for yt, g in df_yby.groupby("year_type"):
    print(f"  {yt:22s} (N={len(g):2d}): Dec_Mean={g['Dec_raw_ret_pct'].mean():+6.2f}% (Win={(g['Dec_raw_ret_pct']>0).mean()*100:5.1f}%) | Jan_Reset_Delta_Mean={g['Jan_Reset_Delta_pp'].mean():+6.2f}pp | FullNextYr_Delta_Mean={g['FullNextYr_Delta_pp'].mean():+6.2f}pp")

# -------------------------------------------------------------------------
# 3. Calendar Month Placebo Test: What if we reset buffers EVERY year at Month M (M=1..12)?
# -------------------------------------------------------------------------
cal_m_rows = []
for m_num in range(1, 13):
    # Resetting before holding month m_num (so m_num=1 means resetting at Dec 31 close before Jan!)
    rst_set_m = {t for t in base.months_214 if (t + pd.offsets.MonthBegin(1)).month == m_num}
    for strat_name, is_tac in [("Current_A1RS", False), ("TechArena_TAC1_A1Sec", True)]:
        rst_map_q = {t: "sharpe" for t in rst_set_m}
        rst_map_s = {t: "mom" for t in rst_set_m}
        pk_q = base.select_ndx_flex(base.p_ndx, "sharpe", 2, 5, rst_map_q)
        pk_t = base.select_tech_arena_flex("mom", rst_map_s) if is_tac else base.select_spx_flex(base.p_tech, "mom", 1, 1, None, None, rst_map_s)
        pk_s = base.select_spx_flex(base.p_spx, "mom", 1, 3, "rs_gics", -0.05, rst_map_s)
        pk_er = base.select_spx_flex(base.p_exit, "mom", 1, 3, "rs_gics", -0.05, rst_map_s)
        pk_eb = base.select_bestsec_flex(base.p_exit, "mom", "rs_gics", -0.05, rst_map_s)

        df_sim = base.simulate_monthly(
            pk_q, pk_t, pk_s, pk_er, pk_eb,
            sgov_t_set=get_dec_sgov_t(MID_U2D_YRS),
            a1_mode=("sector" if is_tac else "ticker")
        )
        m = base.calc_summary_metrics(df_sim)
        cal_m_rows.append({
            "strategy": strat_name,
            "annual_reset_before_month": f"M{m_num:02d} (Reset at M{(m_num-2)%12+1:02d}-end)",
            "cagr_214_pct": m["cagr_214_pct"],
            "sharpe_214": m["sharpe_214"],
            "mdd_monthly_pct": m["mdd_monthly_pct"],
        })

df_cal_m = pd.DataFrame(cal_m_rows)
df_cal_m.to_csv(os.path.join(OUT_DIR, "14_annual_buffer_reset_by_calendar_month_placebo.csv"), index=False)

print("\n=== 3. Annual Buffer Reset by Calendar Month (with U2D Dec SGOV) ===")
print(df_cal_m[df_cal_m["strategy"] == "Current_A1RS"].to_string(index=False))
