#!/usr/bin/env python3
"""
run_presidential_election_deep_audit.py
=======================================
Dedicated Clean-Room Audit of US Presidential Elections (总统大选):
  - 2009-2026 Modern Era (4 Presidential Elections: 2012, 2016, 2020, 2024)
  - 1985-2026 Full 42-Year History (10 Presidential Elections: 1988, 1992, 1996, 2000, 2004, 2008, 2012, 2016, 2020, 2024)

Tests:
  1. Monthly & Daily Event Study exclusively on Presidential Elections:
     - Monthly: Sep (M-2), Oct (M-1 Pre-Elec), Nov (M0 Election), Dec (M+1), Jan (M+2 Inauguration), Feb (M+3)
     - Daily around Presidential Election Day (T_elec):
       [T-20d..T_elec], [T-15d..T_elec], [T-10d..T_elec], [T-5d..T_elec], [Oct31..T_elec],
       [T_elec..T+1d], [T_elec..T+3d], [T_elec..T+5d], [T_elec..T+10d], [T_elec..Nov30]
  2. Monthly Pre/Post Avoidance & Rerank Timing in Presidential Years (on top of Frozen V3 Midterm rule):
     - Avoid Oct + Rerank Nov (Pre-1M)
     - Avoid Nov + Rerank Dec (Elec-1M)
     - Avoid Dec + Rerank Jan (Post-1M)
     - No Avoid + Rerank Only at Nov / Dec / Jan
  3. Daily Pre-Election Avoidance Windows `[T_elec - k .. T_elec]` (k = 5, 8, 10, 12, 15, 20 trading days before Presidential Election Day)
     + Post-Election Re-entry & Rerank at `T_elec + d` (d = 0 close / +1d open, +2d, +3d, +5d)
  4. Best Rerank Lookback Duration (`12-1M`, `12-0M`, `9-1M`, `6-1M`, `3-1M`, `1-0M`) after Presidential Elections.
"""
import os
import sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
import run_election_duration_consistency_audit as base

OUT_DIR = HERE
PRES_YEARS_214 = [2012, 2016, 2020, 2024]
MID_U2D_YEARS = [2010, 2018, 2022]

# -------------------------------------------------------------------------
# 1. Extract Presidential Election Monthly & Daily Event Tables
# -------------------------------------------------------------------------
df_m_all = pd.read_csv(os.path.join(OUT_DIR, "01_election_monthly_event_study_2009_2026.csv"))
df_d_all = pd.read_csv(os.path.join(OUT_DIR, "02_election_daily_subwindows_2010_2024.csv"))
df_lt_all = pd.read_csv(os.path.join(OUT_DIR, "03_long_term_1985_2026_21_elections_consistency.csv"))

df_m_pres = df_m_all[df_m_all["type"] == "Presidential"].copy()
df_d_pres = df_d_all[df_d_all["type"] == "Presidential"].copy()
df_lt_pres = df_lt_all[df_lt_all["type"] == "Presidential"].copy()

print("\n=== 1A. 2009-2026 Presidential Elections Monthly Event Study ===")
print(df_m_pres[df_m_pres["strategy"] == "Current_A1RS_V0"].to_string(index=False))

print("\n=== 1B. 2012-2024 Presidential Elections Daily Windows Around Election Day ===")
print(df_d_pres[df_d_pres["strategy"] == "Current_A1RS_V0"].to_string(index=False))

print("\n=== 1C. 1985-2026 (10 Presidential Elections) Long-Term Monthly Consistency ===")
print(df_lt_pres.to_string(index=False))
for col in ["Sep_pct", "Oct_PreElec_pct", "Nov_Elec_pct", "Dec_PostElec_pct", "Jan_NextYr_pct"]:
    s = df_lt_pres[col].dropna()
    print(f"  10-Presidential {col:18s}: WinRate={(s > 0).mean()*100:5.1f}% ({int((s>0).sum())}/{len(s)}) | Mean={s.mean():+6.2f}% | Median={s.median():+6.2f}%")

# -------------------------------------------------------------------------
# 2. Monthly Presidential Avoidance & Rerank Timing (Standalone vs Combined with Midterm V3)
# -------------------------------------------------------------------------
PRES_MONTHLY_SPECS = [
    ("00_Baseline_MidtermV3_Only (No Pres Rule)",      [],       []),
    ("01_Pres_Pre1M_AvoidOct_RerankNov",               [10],     [11]),
    ("02_Pres_Pre1M_AvoidOct_NoRerank",                [10],     []),
    ("03_Pres_Elec1M_AvoidNov_RerankDec",              [11],     [12]),
    ("04_Pres_Post1M_AvoidDec_RerankJan",              [12],     [13]),
    ("05_Pres_AvoidOctAndDec_KeepNov_RerankNovJan",    [10, 12], [11, 13]),
    ("06_Pres_OnlyRerankNov_NoAvoid",                  [],       [11]),
    ("07_Pres_OnlyRerankDec_NoAvoid",                  [],       [12]),
    ("08_Pres_OnlyRerankJan_NoAvoid (Inauguration)",   [],       [13]),
    ("09_Pres_Div2Uni_AvoidDec_RerankJan (2016/20/24)", "div2uni_dec", "div2uni_jan"),
]

base_sgov_mid = base.get_t_set(MID_U2D_YEARS, [12])
base_rst_mid = base.get_t_set(MID_U2D_YEARS, [13])

pres_m_rows = []
for strat_name, is_tac in [("Current_A1RS_V3", False), ("TechArena_TAC1_A1Sec_V3", True)]:
    for spec_name, p_avoid, p_rst in PRES_MONTHLY_SPECS:
        if p_avoid == "div2uni_dec":
            sgov_p = base.get_t_set([2016, 2020, 2024], [12])
            rst_p = base.get_t_set([2016, 2020, 2024], [13])
        else:
            sgov_p = base.get_t_set(PRES_YEARS_214, p_avoid)
            rst_p = base.get_t_set(PRES_YEARS_214, p_rst)

        sgov_tot = base_sgov_mid | sgov_p
        rst_tot = base_rst_mid | rst_p
        rst_map_q = {t: "sharpe" for t in rst_tot}
        rst_map_s = {t: "mom" for t in rst_tot}

        pk_q = base.select_ndx_flex(base.p_ndx, "sharpe", 2, 5, rst_map_q)
        pk_t = base.select_tech_arena_flex("mom", rst_map_s) if is_tac else base.select_spx_flex(base.p_tech, "mom", 1, 1, None, None, rst_map_s)
        pk_s = base.select_spx_flex(base.p_spx, "mom", 1, 3, "rs_gics", -0.05, rst_map_s)
        pk_er = base.select_spx_flex(base.p_exit, "mom", 1, 3, "rs_gics", -0.05, rst_map_s)
        pk_eb = base.select_bestsec_flex(base.p_exit, "mom", "rs_gics", -0.05, rst_map_s)

        df_sim = base.simulate_monthly(
            pk_q, pk_t, pk_s, pk_er, pk_eb,
            sgov_t_set=sgov_tot,
            a1_mode=("sector" if is_tac else "ticker")
        )
        m = base.calc_summary_metrics(df_sim)
        ym_ret = dict(zip(df_sim["ym"], df_sim["net_ret"]))
        pres_m_rows.append({
            "strategy": strat_name,
            "presidential_rule": spec_name,
            "cagr_213_pct": m["cagr_213_pct"],
            "cagr_214_pct": m["cagr_214_pct"],
            "sharpe_213": m["sharpe_213"],
            "sharpe_214": m["sharpe_214"],
            "mdd_monthly_pct": m["mdd_monthly_pct"],
            "turnover_2way_yr": m["turnover_2way_yr"],
            "Oct_mean_4pres_pct": round(np.mean([ym_ret[f"{y}-10"] for y in PRES_YEARS_214]) * 100, 2),
            "Nov_mean_4pres_pct": round(np.mean([ym_ret[f"{y}-11"] for y in PRES_YEARS_214]) * 100, 2),
            "Dec_mean_4pres_pct": round(np.mean([ym_ret[f"{y}-12"] for y in PRES_YEARS_214]) * 100, 2),
            "Jan_mean_4pres_pct": round(np.mean([ym_ret[f"{y+1}-01"] for y in PRES_YEARS_214]) * 100, 2),
        })

df_pres_monthly = pd.DataFrame(pres_m_rows)
df_pres_monthly.to_csv(os.path.join(OUT_DIR, "06_presidential_monthly_avoid_and_rerank_matrix.csv"), index=False)

print("\n=== 2. Presidential Monthly Avoidance & Rerank Matrix (Combined with Midterm V3) ===")
print(df_pres_monthly.to_string(index=False))

# -------------------------------------------------------------------------
# 3. Daily Sub-Monthly Pre-Election Avoidance Windows Around Presidential Election Day
# -------------------------------------------------------------------------
# Check exact daily return in [T_elec - k_pre .. T_elec + k_post] across the 4 Presidential Elections (2012, 2016, 2020, 2024)
# and simulate stepping aside into SGOV during [T_elec - k_pre .. T_elec + k_post]!
s_ret_cur, s_nav_cur = base.s_ret_cur_v0, base.s_nav_cur_v0
s_ret_tac, s_nav_tac = base.s_ret_tac_v0, base.s_nav_tac_v0

DAILY_PRE_POST_SPECS = [
    ("D0_No_Daily_Avoid",             0,  0),
    ("D1_Avoid_T_minus_3_to_T_elec", -3,  0),
    ("D2_Avoid_T_minus_5_to_T_elec", -5,  0),
    ("D3_Avoid_T_minus_8_to_T_elec", -8,  0),
    ("D4_Avoid_T_minus_10_to_T_elec",-10, 0),
    ("D5_Avoid_T_minus_15_to_T_elec",-15, 0),
    ("D6_Avoid_T_minus_20_to_T_elec",-20, 0),
    ("D7_Avoid_T_minus_5_to_T_plus_1",-5, 1),
    ("D8_Avoid_T_minus_10_to_T_plus_1",-10, 1),
    ("D9_Avoid_T_minus_10_to_T_plus_3",-10, 3),
    ("D10_Avoid_T_minus_10_to_T_plus_5",-10, 5),
]

daily_pres_rows = []
for strat_label, s_nav in [("Current_A1RS_V3", s_nav_cur), ("TechArena_TAC1_A1Sec_V3", s_nav_tac)]:
    for spec_label, k_pre, k_post in DAILY_PRE_POST_SPECS:
        cyc_rets = {}
        for yr in PRES_YEARS_214:
            t_el = base.ELECTION_DATES_2009_2026[yr]
            idx_el = s_nav.index.get_indexer([t_el], method="nearest")[0]
            i0 = idx_el + k_pre
            i1 = idx_el + k_post
            r_w = float(s_nav.iloc[i1] / s_nav.iloc[i0] - 1.0) if i1 > i0 else 0.0
            cyc_rets[yr] = r_w

        # If we avoid this window (replace r_w with ~0% SGOV minus 20bp round-trip cost),
        # net multiplier per cycle is (1 - 0.0020) / (1 + r_w)
        mult_tot = 1.0
        if k_pre != 0 or k_post != 0:
            for yr in PRES_YEARS_214:
                mult_tot *= (1.0 - 0.0020) / (1.0 + cyc_rets[yr])

        base_cagr = 0.6495 if "Current" in strat_label else 0.6716
        adj_cagr = (1.0 + base_cagr) * (mult_tot ** (12.0 / 214.0)) - 1.0

        vals = [cyc_rets[y] * 100 for y in PRES_YEARS_214]
        n_neg = sum(1 for v in vals if v < 0)
        daily_pres_rows.append({
            "strategy": strat_label,
            "daily_avoid_window": spec_label,
            "2012_window_ret_pct": round(vals[0], 2),
            "2016_window_ret_pct": round(vals[1], 2),
            "2020_window_ret_pct": round(vals[2], 2),
            "2024_window_ret_pct": round(vals[3], 2),
            "mean_window_ret_pct": round(float(np.mean(vals)), 2),
            "loss_freq_out_of_4": f"{n_neg}/4",
            "resulting_214m_cagr_pct": round(adj_cagr * 100, 2),
            "cagr_delta_vs_base_pp": round((adj_cagr - base_cagr) * 100, 2),
        })

df_daily_pres = pd.DataFrame(daily_pres_rows)
df_daily_pres.to_csv(os.path.join(OUT_DIR, "07_presidential_daily_pre_election_avoid_windows.csv"), index=False)

print("\n=== 3. Presidential Daily Pre-Election Avoidance Windows (2012, 2016, 2020, 2024) ===")
print(df_daily_pres[df_daily_pres["strategy"] == "Current_A1RS_V3"].to_string(index=False))

# -------------------------------------------------------------------------
# 4. Presidential Post-Election Rerank Lookback Duration Matrix
#    (Testing Rerank at Nov 1 [for Nov], Dec 1 [for Dec], and Jan 1 [for Jan Inauguration] in Presidential Years)
# -------------------------------------------------------------------------
PRES_RERANK_TIMINGS = [
    ("Pres_RerankNov_ForNovRally (Oct 31 close)", PRES_YEARS_214, [],   [11]),
    ("Pres_RerankDec_ForDec (Nov 30 close)",      PRES_YEARS_214, [],   [12]),
    ("Pres_RerankJan_ForInauguration (Dec 31)",   PRES_YEARS_214, [],   [13]),
    ("Pres_AvoidOct_RerankNov (Oct SGOV + Rerank)", PRES_YEARS_214, [10], [11]),
]

pres_lb_rows = []
for strat_name, is_tac in [("Current_A1RS_V3", False), ("TechArena_TAC1_A1Sec_V3", True)]:
    for timing_name, yrs, p_avoid, p_rst in PRES_RERANK_TIMINGS:
        sgov_tot = base_sgov_mid | base.get_t_set(yrs, p_avoid)
        rst_pres = base.get_t_set(yrs, p_rst)
        for lb_label, m_col, sh_col in base.LOOKBACK_SPECS:
            # Keep Midterm V3 reset at standard 12-1M, and test custom lookback on Presidential reset dates!
            rst_map_q = {t: "sharpe" for t in base_rst_mid}
            rst_map_s = {t: "mom" for t in base_rst_mid}
            for t in rst_pres:
                rst_map_q[t] = sh_col
                rst_map_s[t] = m_col

            pk_q = base.select_ndx_flex(base.p_ndx, "sharpe", 2, 5, rst_map_q)
            pk_t = base.select_tech_arena_flex("mom", rst_map_s) if is_tac else base.select_spx_flex(base.p_tech, "mom", 1, 1, None, None, rst_map_s)
            pk_s = base.select_spx_flex(base.p_spx, "mom", 1, 3, "rs_gics", -0.05, rst_map_s)
            pk_er = base.select_spx_flex(base.p_exit, "mom", 1, 3, "rs_gics", -0.05, rst_map_s)
            pk_eb = base.select_bestsec_flex(base.p_exit, "mom", "rs_gics", -0.05, rst_map_s)

            df_sim = base.simulate_monthly(
                pk_q, pk_t, pk_s, pk_er, pk_eb,
                sgov_t_set=sgov_tot,
                a1_mode=("sector" if is_tac else "ticker")
            )
            m = base.calc_summary_metrics(df_sim)
            ym_ret = dict(zip(df_sim["ym"], df_sim["net_ret"]))
            target_m = p_rst[0]
            r_4 = [ym_ret[f"{y+1}-01" if target_m == 13 else f"{y}-{target_m:02d}"] for y in PRES_YEARS_214]
            pres_lb_rows.append({
                "strategy": strat_name,
                "pres_rerank_timing": timing_name,
                "rerank_lookback_duration": lb_label,
                "cagr_214_pct": m["cagr_214_pct"],
                "sharpe_214": m["sharpe_214"],
                "mdd_monthly_pct": m["mdd_monthly_pct"],
                "2012_post_rerank_pct": round(r_4[0] * 100, 2),
                "2016_post_rerank_pct": round(r_4[1] * 100, 2),
                "2020_post_rerank_pct": round(r_4[2] * 100, 2),
                "2024_post_rerank_pct": round(r_4[3] * 100, 2),
                "mean_4pres_post_rerank_pct": round(float(np.mean(r_4)) * 100, 2),
            })

df_pres_lb = pd.DataFrame(pres_lb_rows)
df_pres_lb.to_csv(os.path.join(OUT_DIR, "08_presidential_rerank_lookback_duration_matrix.csv"), index=False)

print("\n=== 4. Presidential Post-Election Rerank Lookback Duration Matrix (Current_A1RS_V3) ===")
print(df_pres_lb[df_pres_lb["strategy"] == "Current_A1RS_V3"].to_string(index=False))
