#!/usr/bin/env python3
"""
run_turnover_presidential_audit.py
==================================
Surgical Audit of "Party Turnover / Regime Alternation Presidential Elections" (政党轮换大选):
  - Contrasts:
    A) Party Turnover Presidential Elections (白宫政党轮替 / 易主):
       - Modern 214M (2009-2026): 2016 (Dem->GOP), 2020 (GOP->Dem), 2024 (Dem->GOP) [N=3]
       - Full 42Y (1985-2026): 1992 (GOP->Dem), 2000 (Dem->GOP), 2008 (GOP->Dem), 2016, 2020, 2024 [N=6]
    B) Incumbent Party Re-elected (白宫连任 / 不轮替):
       - Modern 214M (2009-2026): 2012 (Dem->Dem) [N=1]
       - Full 42Y (1985-2026): 1988 (GOP->GOP), 1996 (Dem->Dem), 2004 (GOP->GOP), 2012 (Dem->Dem) [N=4]
    C) Midterm Regime Flip (中期选举 Unified -> Divided: 2010, 2018, 2022) [N=3]

Evaluates:
  1. Full Monthly Path from Aug (M-3) to Apr (M+5) for Turnover vs Non-Turnover Presidential Elections
  2. Daily Path around Election Day (T_elec) for Turnover (2016, 2020, 2024) vs Non-Turnover (2012)
  3. Avoid & Rerank Strategies specifically targeting Party Turnover Presidential Elections (post-election Nov/Dec/Jan/Feb/Mar)
     and Pre-Election when Poll/Incumbent Turnover is tested.
"""
import os
import sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run_election_duration_consistency_audit as base

OUT_DIR = HERE
TURNOVER_PRES_214 = [2016, 2020, 2024]
REELECT_PRES_214 = [2012]
ALL_PRES_214 = [2012, 2016, 2020, 2024]
MID_U2D_214 = [2010, 2018, 2022]

# -------------------------------------------------------------------------
# 1. Full Monthly Trajectory (Aug M-3 to May M+6) for 2009-2026 Elections
# -------------------------------------------------------------------------
ym_cur = base.ym_ret_cur
ym_tac = base.ym_ret_tac

PRES_DETAIL_META = [
    (2012, "Re-election (No Turnover)", "Dem (Obama) -> Dem (Obama)",       "Divided -> Divided"),
    (2016, "Party Turnover (轮换)",     "Dem (Obama) -> GOP (Trump)",       "Divided -> Unified"),
    (2020, "Party Turnover (轮换)",     "GOP (Trump) -> Dem (Biden)",       "Divided -> Unified"),
    (2024, "Party Turnover (轮换)",     "Dem (Biden) -> GOP (Trump)",       "Divided -> Unified"),
]

traj_rows = []
for strat_label, ym_map in [("Current_A1RS_V0", ym_cur), ("TechArena_TAC1_V0", ym_tac)]:
    for yr, ptype, transition, gov_shift in PRES_DETAIL_META:
        row = {
            "strategy": strat_label,
            "year": yr,
            "turnover_type": ptype,
            "party_transition": transition,
            "gov_shift": gov_shift,
        }
        month_specs = [
            ("Aug_M-3", yr, 8),
            ("Sep_M-2", yr, 9),
            ("Oct_M-1_PreElec", yr, 10),
            ("Nov_M0_Election", yr, 11),
            ("Dec_M+1_PostElec", yr, 12),
            ("Jan_M+2_Inauguration", yr + 1, 1),
            ("Feb_M+3_PostInaug", yr + 1, 2),
            ("Mar_M+4", yr + 1, 3),
            ("Apr_M+5", yr + 1, 4),
        ]
        for col_lbl, y_m, m_num in month_specs:
            v = ym_map.get(f"{y_m}-{m_num:02d}", np.nan)
            row[col_lbl] = round(v * 100, 2) if pd.notna(v) else np.nan
        traj_rows.append(row)

df_traj_214 = pd.DataFrame(traj_rows)
df_traj_214.to_csv(os.path.join(OUT_DIR, "09_presidential_turnover_vs_reelection_monthly_trajectory.csv"), index=False)

print("\n=== 1. 2009-2026 Presidential Elections: Party Turnover (2016/2020/2024) vs Re-election (2012) Monthly Trajectory ===")
print(df_traj_214[df_traj_214["strategy"] == "Current_A1RS_V0"].to_string(index=False))

# -------------------------------------------------------------------------
# 2. 42-Year (1985-2026, 10 Presidential Elections) Party Turnover (6) vs Re-election (4)
# -------------------------------------------------------------------------
PRES_42Y_META = [
    (1988, "Re-election (No Turnover)", "GOP (Reagan) -> GOP (Bush Sr.)"),
    (1992, "Party Turnover (轮换)",     "GOP (Bush Sr.) -> Dem (Clinton)"),
    (1996, "Re-election (No Turnover)", "Dem (Clinton) -> Dem (Clinton)"),
    (2000, "Party Turnover (轮换)",     "Dem (Clinton) -> GOP (Bush Jr.)"),
    (2004, "Re-election (No Turnover)", "GOP (Bush Jr.) -> GOP (Bush Jr.)"),
    (2008, "Party Turnover (轮换)",     "GOP (Bush Jr.) -> Dem (Obama)"),
    (2012, "Re-election (No Turnover)", "Dem (Obama) -> Dem (Obama)"),
    (2016, "Party Turnover (轮换)",     "Dem (Obama) -> GOP (Trump)"),
    (2020, "Party Turnover (轮换)",     "GOP (Trump) -> Dem (Biden)"),
    (2024, "Party Turnover (轮换)",     "Dem (Biden) -> GOP (Trump)"),
]

lt_pres_rows = []
for yr, ptype, trans in PRES_42Y_META:
    r = {
        "year": yr,
        "turnover_type": ptype,
        "transition": trans,
    }
    for col_lbl, y_m, m_num in [
        ("Sep_M-2", yr, 9),
        ("Oct_M-1_PreElec", yr, 10),
        ("Nov_M0_Election", yr, 11),
        ("Dec_M+1_PostElec", yr, 12),
        ("Jan_M+2_Inaug", yr + 1, 1),
        ("Feb_M+3_PostInaug", yr + 1, 2),
        ("Mar_M+4", yr + 1, 3),
    ]:
        v = base.ym_502_comp.get(f"{y_m}-{m_num:02d}", np.nan)
        r[col_lbl] = round(v * 100, 2) if pd.notna(v) else np.nan
    lt_pres_rows.append(r)

df_lt_turnover = pd.DataFrame(lt_pres_rows)
df_lt_turnover.to_csv(os.path.join(OUT_DIR, "10_1985_2026_10pres_turnover_vs_reelection.csv"), index=False)

print("\n=== 2. 1985-2026 (10 Presidential Elections): Party Turnover (N=6) vs Re-election (N=4) ===")
print(df_lt_turnover.to_string(index=False))
for grp_name, g_df in df_lt_turnover.groupby("turnover_type"):
    print(f"\n--- Group Summary: {grp_name} (N={len(g_df)}) ---")
    for c in ["Sep_M-2", "Oct_M-1_PreElec", "Nov_M0_Election", "Dec_M+1_PostElec", "Jan_M+2_Inaug", "Feb_M+3_PostInaug", "Mar_M+4"]:
        s = g_df[c].dropna()
        print(f"  {c:20s}: WinRate={(s>0).mean()*100:5.1f}% ({int((s>0).sum())}/{len(s)}) | Mean={s.mean():+6.2f}% | Median={s.median():+6.2f}%")

# -------------------------------------------------------------------------
# 3. Post-Election Rules Exclusively on Party-Turnover Presidential Elections (2016, 2020, 2024)
#    (Note: Once Election Day passes in early Nov, whether Party Turnover occurred is 100% KNOWN ex-ante!)
# -------------------------------------------------------------------------
# Notice a critical PIT fact:
#   - BEFORE Election Day (in Oct), you don't know for sure whether the White House will flip parties.
#   - AFTER Election Day (at Nov 30 close for Dec, Dec 31 close for Jan, Jan 31 close for Feb),
#     whether the Presidential Election resulted in PARTY TURNOVER (2016, 2020, 2024 vs 2012 re-election)
#     is 100% KNOWN with ZERO look-ahead bias!
base_sgov_mid = base.get_t_set(MID_U2D_214, [12])
base_rst_mid = base.get_t_set(MID_U2D_214, [13])

TURNOVER_RULES = [
    ("00_Baseline_MidtermV3_Only",                                 [],   [],   "mom",      "sharpe"),
    # Post-election rules on Party-Turnover Presidential Elections (2016, 2020, 2024) — 100% known after Nov Election!
    ("01_TurnoverPres_RerankDec_12_1M (Nov 30 close)",             [],   [12], "mom",      "sharpe"),
    ("02_TurnoverPres_RerankJan_12_1M (Dec 31 Inauguration)",      [],   [13], "mom",      "sharpe"),
    ("03_TurnoverPres_RerankJan_3_1M (Dec 31 Inauguration)",       [],   [13], "mom_3_1",  "sharpe_3_1"),
    ("04_TurnoverPres_AvoidDec_RerankJan_12_1M (Same as Midterm)", [12], [13], "mom",      "sharpe"),
    ("05_TurnoverPres_AvoidFeb_RerankMar_12_1M (Post-Inaug Dip)",  [14], [15], "mom",      "sharpe"),
    ("06_TurnoverPres_RerankJan_And_AvoidFeb_RerankMar",           [14], [13, 15], "mom",  "sharpe"),
    # Pre-election Oct avoid on Turnover years vs All Presidential years
    ("07_TurnoverPres_PreAvoidOct_RerankNov_12_1M",                [10], [11], "mom",      "sharpe"),
    ("08_AllPres_AvoidFeb_RerankMar_12_1M (2012/16/20/24 Feb)",    "all_feb", "all_mar", "mom", "sharpe"),
    ("09_AllPres_RerankJan_And_AvoidFeb_RerankMar",                "all_feb", "all_jan_mar", "mom", "sharpe"),
]

def get_t_set_ext(years, months_list):
    out = set()
    for y in years:
        for m in months_list:
            if m <= 12:
                ym_str = f"{y}-{m:02d}"
            else:
                ym_str = f"{y+1}-{m-12:02d}"
            if ym_str in base.ym_to_t:
                out.add(base.ym_to_t[ym_str])
    return out

to_rule_rows = []
for strat_name, is_tac in [("Current_A1RS_V3", False), ("TechArena_TAC1_A1Sec_V3", True)]:
    for rule_name, p_avoid, p_rst, m_col, sh_col in TURNOVER_RULES:
        if p_avoid == "all_feb":
            sgov_p = get_t_set_ext(ALL_PRES_214, [14])
            rst_p = get_t_set_ext(ALL_PRES_214, [15] if p_rst == "all_mar" else [13, 15])
        else:
            sgov_p = get_t_set_ext(TURNOVER_PRES_214, p_avoid)
            rst_p = get_t_set_ext(TURNOVER_PRES_214, p_rst)

        sgov_tot = base_sgov_mid | sgov_p
        rst_map_q = {t: "sharpe" for t in base_rst_mid}
        rst_map_s = {t: "mom" for t in base_rst_mid}
        for t in rst_p:
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
        to_rule_rows.append({
            "strategy": strat_name,
            "turnover_pres_rule": rule_name,
            "cagr_213_pct": m["cagr_213_pct"],
            "cagr_214_pct": m["cagr_214_pct"],
            "sharpe_213": m["sharpe_213"],
            "sharpe_214": m["sharpe_214"],
            "mdd_monthly_pct": m["mdd_monthly_pct"],
            "turnover_2way_yr": m["turnover_2way_yr"],
            "Nov_turnover_mean_pct": round(np.mean([ym_ret[f"{y}-11"] for y in TURNOVER_PRES_214]) * 100, 2),
            "Dec_turnover_mean_pct": round(np.mean([ym_ret[f"{y}-12"] for y in TURNOVER_PRES_214]) * 100, 2),
            "Jan_turnover_mean_pct": round(np.mean([ym_ret[f"{y+1}-01"] for y in TURNOVER_PRES_214]) * 100, 2),
            "Feb_turnover_mean_pct": round(np.mean([ym_ret[f"{y+1}-02"] for y in TURNOVER_PRES_214]) * 100, 2),
        })

df_to_rules = pd.DataFrame(to_rule_rows)
df_to_rules.to_csv(os.path.join(OUT_DIR, "11_turnover_presidential_rules_backtest.csv"), index=False)

print("\n=== 3. Party-Turnover Presidential Election Rules Backtest ===")
print(df_to_rules.to_string(index=False))
