#!/usr/bin/env python3
import sys, os, json
import pandas as pd
import numpy as np
from scipy import stats as sst

sys.path.insert(0, "outputs/expabc_independent_audit_20261104")
import ind_engine as IE
import outputs.remediation_full_audit_20261104.run_full_8point_remediation_audit as ra

p_spx = pd.read_parquet("outputs/expabc_independent_audit_20261104/ind_panel_spx_with_sector.parquet")
p_ndx = pd.read_parquet("outputs/expabc_independent_audit_20261104/ind_panel_ndx.parquet")
p_spx["t"] = pd.to_datetime(p_spx["t"])
p_ndx["t"] = pd.to_datetime(p_ndx["t"])

get_pit_sector, get_pit_it_subindustry, map_to_gics_hierarchies = ra.build_repaired_pit_gics_tables()
p_spx["clean_sector"] = [get_pit_sector(t, tk, s) for t, tk, s in p_spx[["t", "ticker", "sector"]].itertuples(index=False)]

g4g_list, g4d_list = [], []
for t, tk, sec in p_spx[["t", "ticker", "clean_sector"]].itertuples(index=False):
    if sec == "Information Technology":
        raw_sub, _ = get_pit_it_subindustry(t, tk)
        g4d, g4g, _, _ = map_to_gics_hierarchies(raw_sub)
        g4g_list.append(g4g)
        g4d_list.append(g4d)
    else:
        g4g_list.append(sec)
        g4d_list.append("")
p_spx["gics_4grp_it"] = g4g_list
p_spx["gics_4digit_group"] = g4d_list

months_all = sorted(p_spx["t"].unique())
months_213 = [t for t in months_all if pd.Timestamp("2008-12-31") <= t <= pd.Timestamp("2026-08-31")]
months_214 = [t for t in months_all if pd.Timestamp("2008-12-31") <= t <= pd.Timestamp("2026-09-30")]
t_prev_map = {t: (months_all[i-1] if i > 0 else pd.Timestamp("2008-11-28")) for i, t in enumerate(months_all)}

p_row_lk = { (r.t, r.ticker): (r.src, r.sym, str(r.ret_flag)) for df_p in (p_spx, p_ndx) for r in df_p.itertuples(index=False) if pd.notna(r.src) }

def get_daily_df(t, tk):
    if (t, tk) in p_row_lk:
        src, sym, fl = p_row_lk[(t, tk)]
        if fl.startswith("open_open_via_"):
            src, sym = fl.replace("open_open_via_", "").split(":", 1)
        return IE.load_fixed(src, sym)
    for src, sym in IE.candidate_series(tk):
        df = IE.load_fixed(src, sym)
        if df is not None:
            return df
    return None

t_oct = pd.Timestamp("2026-09-30")
d0_oct = IE.first_session_after(t_oct)

for panel in (p_spx, p_ndx):
    ret1m_vals, hr_vals = [], []
    for t, tk, src, sym, hr in panel[["t", "ticker", "src", "sym", "hold_ret"]].itertuples(index=False):
        df_d = IE.load_fixed(src, sym) if pd.notna(src) else None
        t_prev = t_prev_map[t]
        if df_d is not None:
            s_t = df_d.loc[:t, "c"]
            s_p = df_d.loc[:t_prev, "c"]
            r1 = float(s_t.iloc[-1] / s_p.iloc[-1] - 1.0) if (len(s_t) > 0 and len(s_p) > 0) else np.nan
            if t == t_oct and pd.isna(hr) and d0_oct in df_d.index:
                hr = float(df_d["c"].iloc[-1] / df_d.at[d0_oct, "o"] - 1.0)
        else:
            r1 = np.nan
        ret1m_vals.append(r1)
        hr_vals.append(hr)
    panel["ret_1m"] = ret1m_vals
    panel["hold_ret"] = hr_vals

sec_ret1m = p_spx.groupby(["t", "clean_sector"])["ret_1m"].mean().to_dict()
p_spx["sec_ret_1m"] = [sec_ret1m.get((t, s), np.nan) for t, s in zip(p_spx["t"], p_spx["clean_sector"])]
p_spx["rs_sec"] = p_spx["ret_1m"] - p_spx["sec_ret_1m"]

ret_lk = { (r.t, r.ticker): float(r.hold_ret) for df_p in (p_spx, p_ndx) for r in df_p[["t", "ticker", "hold_ret"]].itertuples(index=False) if pd.notna(r.hold_ret) }
vol_lk = { (r.t, r.ticker): float(r.vol) for df_p in (p_spx, p_ndx) for r in df_p[["t", "ticker", "vol"]].itertuples(index=False) if pd.notna(r.vol) }

def select_spx_buf_rs(panel, sig_col, n_pick, hold_k=3, thresh=None):
    held, out = [], {}
    for t_val, g in panel[panel[sig_col].notna()].groupby("t", sort=True):
        g = g.sort_values([sig_col, "ticker"], ascending=[False, True]).reset_index(drop=True)
        g["rk"] = g.index + 1
        rk_map = dict(zip(g["ticker"], g["rk"]))
        rs_map = dict(zip(g["ticker"], g["rs_sec"]))
        ranked = list(g["ticker"])
        kept, banned = [], set()
        for x in held:
            rk = rk_map.get(x, 999)
            if rk > hold_k:
                continue
            if thresh is None or rk == 1 or rs_map.get(x, 0.0) >= thresh:
                kept.append(x)
            else:
                banned.add(x)
        for x in ranked:
            if len(kept) >= n_pick:
                break
            if x not in kept and x not in banned:
                kept.append(x)
        held = kept[:n_pick]
        out[t_val] = held
    return out

def run_bestsec_buf_rs(df_exit_panel, thresh=None):
    held_bs, out_bs = [], {}
    for t_val, g in df_exit_panel[df_exit_panel["mom"].notna()].groupby("t", sort=True):
        sec_ew = g.groupby("clean_sector")["mom"].mean().sort_values(ascending=False)
        top_sec = str(sec_ew.index[0])
        sec_rk = {s: i + 1 for i, s in enumerate(sec_ew.index)}
        g = g.copy()
        g["sec_rk"] = g["clean_sector"].map(sec_rk)
        g_top = g[g["sec_rk"] == 1].sort_values(["mom", "ticker"], ascending=[False, True])
        g_rest = g[g["sec_rk"] > 1].sort_values(["sec_rk", "mom", "ticker"], ascending=[True, False, True])
        ranked = list(pd.concat([g_top, g_rest])["ticker"])
        rank = {x: i + 1 for i, x in enumerate(ranked)}
        rs_map = dict(zip(g["ticker"], g["rs_sec"]))
        kept = [x for x in held_bs if rank.get(x, 999) <= 3 and (thresh is None or rank.get(x, 999) == 1 or rs_map.get(x, 0.0) >= thresh)][:1]
        if not kept:
            kept = [ranked[0]]
        held_bs = kept
        out_bs[t_val] = [kept[0], top_sec]
    return out_bs

p_tech = p_spx[p_spx["clean_sector"] == "Information Technology"].copy()
p_exit = p_spx[p_spx["clean_sector"] != "Information Technology"].copy()

pk_q = IE.sleeve_picks(p_ndx, "sharpe", 2, 5)
pk_t = select_spx_buf_rs(p_tech, "mom", 1, 1, None)

cal = IE.calendar()
reg_df = pd.read_csv("outputs/expabc_independent_audit_20261104/02_ind_regime.csv")
reg_df["t"] = pd.to_datetime(reg_df["t"])
reg_map = reg_df.set_index("t").to_dict("index")
cash_map, df_sgov, df_bil, rf_s = ra.build_realistic_cash_etf_returns(months_all, cal)

gics_grp_map = {}
top_gics_grp_by_t = {}
for t_val, g in p_tech.groupby("t", sort=True):
    gv = g[g["mom"].notna()]
    for tk, grp_v in gv[["ticker", "gics_4grp_it"]].itertuples(index=False):
        gics_grp_map[(t_val, tk)] = grp_v
    grp_means = gv.groupby("gics_4grp_it")["mom"].mean().sort_values(ascending=False)
    if len(grp_means):
        top_gics_grp_by_t[t_val] = grp_means.index[0]

def make_routeA1_spy_picks(pk_s_in, pk_er_in):
    out = {}
    for t in months_all:
        if t in reg_map and (not bool(reg_map[t]["sep_on"])) and (pk_t[t][0] == pk_s_in[t][0]):
            out[t] = [pk_er_in[t][0]]
        else:
            out[t] = list(pk_s_in[t])
    return out

pk_s_0 = select_spx_buf_rs(p_spx, "mom", 1, 3, None)
pk_er_0 = select_spx_buf_rs(p_exit, "mom", 1, 3, None)
pk_eb_0 = run_bestsec_buf_rs(p_exit, None)

L_ctrl, nav_ctrl, mer_ctrl = ra.simulate_zero_shared_code_strategy(
    "Ctrl_3S_G1_1k", months_213, months_214, p_ndx, p_spx, pk_q, pk_t, pk_s_0, pk_er_0, pk_eb_0,
    reg_map, cash_map, vol_lk, ret_lk, gics_grp_map, top_gics_grp_by_t,
    cal, get_daily_df, df_sgov, df_bil,
    sep_off_mode="none", conc_mode="none", l_conf2=1.0, l_ord3=1.0, l_grp3=1.0,
    gate_version="v1", use_actual_sgov=False, borrow_spread_ann=0.005
)

rf_213 = np.array([cash_map[t]["rf_tbill"] for t in months_213])
rf_214 = np.array([cash_map[t]["rf_tbill"] for t in months_214])
ex_ctrl_213 = L_ctrl.loc[months_213, "net"].values - rf_213
ex_ctrl_214 = L_ctrl.loc[months_214, "net"].values - rf_214
sk_bench_213 = float(sst.skew(ex_ctrl_213, bias=False))
ku_bench_213 = float(sst.kurtosis(ex_ctrl_213, fisher=False, bias=False))
sk_bench_214 = float(sst.skew(ex_ctrl_214, bias=False))
ku_bench_214 = float(sst.kurtosis(ex_ctrl_214, fisher=False, bias=False))

def calc_dsr(r_arr, rf_arr, sk_b, ku_b, n_trials=1112):
    ex = r_arr - rf_arr
    T = len(ex)
    sr_m = float(np.mean(ex) / np.std(r_arr, ddof=1))
    sr_ann = sr_m * np.sqrt(12.0)
    sk_own = float(sst.skew(ex, bias=False))
    ku_own = float(sst.kurtosis(ex, fisher=False, bias=False))
    sd_own = np.sqrt(max(1e-12, 1.0 - sk_own * sr_m + ((ku_own - 1.0) / 4.0) * (sr_m ** 2)))
    sd_ben = np.sqrt(max(1e-12, 1.0 - sk_b * sr_m + ((ku_b - 1.0) / 4.0) * (sr_m ** 2)))

    emc = 0.5772156649015329
    sd_sr_m = np.sqrt(0.0485 / 12.0)
    z1 = sst.norm.ppf(1.0 - 1.0 / n_trials)
    z2 = sst.norm.ppf(1.0 - 1.0 / (n_trials * np.e))
    sr0_m = sd_sr_m * ((1.0 - emc) * z1 + emc * z2)

    dsr_own = float(sst.norm.cdf((sr_m - sr0_m) * np.sqrt(T - 1.0) / sd_own))
    dsr_ben = float(sst.norm.cdf((sr_m - sr0_m) * np.sqrt(T - 1.0) / sd_ben))
    return sr_ann, dsr_own, dsr_ben

test_suites = [
    ("1. Official Mainline: BestSec_ModBurst_135_75_25_GateV1 (Route 1, No RS, 1.20/1.35x)",
     pk_s_0, pk_er_0, pk_eb_0, False, 1.20, 1.35, 1.35),
    ("2. Route A1 Baseline 1.35x: A1_ModBurst_135_75_25_GateV1 (Route A1, No RS, 1.20/1.35x)",
     pk_s_0, pk_er_0, pk_eb_0, True, 1.20, 1.35, 1.35),
    ("3a. A1-RS (0.0%) 1.35x: ModBurst_135_75_25_GateV1",
     select_spx_buf_rs(p_spx, "mom", 1, 3, 0.0), select_spx_buf_rs(p_exit, "mom", 1, 3, 0.0), run_bestsec_buf_rs(p_exit, 0.0), True, 1.20, 1.35, 1.35),
    ("3b. A1-RS (-2.5%) 1.35x: ModBurst_135_75_25_GateV1",
     select_spx_buf_rs(p_spx, "mom", 1, 3, -0.025), select_spx_buf_rs(p_exit, "mom", 1, 3, -0.025), run_bestsec_buf_rs(p_exit, -0.025), True, 1.20, 1.35, 1.35),
    ("3c. NEW SWEET SPOT: A1-RS (-5.0%) 1.35x: ModBurst_135_75_25_GateV1",
     select_spx_buf_rs(p_spx, "mom", 1, 3, -0.05), select_spx_buf_rs(p_exit, "mom", 1, 3, -0.05), run_bestsec_buf_rs(p_exit, -0.05), True, 1.20, 1.35, 1.35),
    ("3d. A1-RS (-7.5%) 1.35x: ModBurst_135_75_25_GateV1",
     select_spx_buf_rs(p_spx, "mom", 1, 3, -0.075), select_spx_buf_rs(p_exit, "mom", 1, 3, -0.075), run_bestsec_buf_rs(p_exit, -0.075), True, 1.20, 1.35, 1.35),
    ("3e. A1-RS (-10.0%) 1.35x: ModBurst_135_75_25_GateV1",
     select_spx_buf_rs(p_spx, "mom", 1, 3, -0.10), select_spx_buf_rs(p_exit, "mom", 1, 3, -0.10), run_bestsec_buf_rs(p_exit, -0.10), True, 1.20, 1.35, 1.35),
    ("4. Official Prudent 1.50x: BestSec_Prudent_150_75_25_GateV1 (Route 1, No RS, 1.25/1.50x)",
     pk_s_0, pk_er_0, pk_eb_0, False, 1.25, 1.50, 1.50),
    ("5. A1-RS (-5.0%) 1.50x: Prudent_150_75_25_GateV1 (Route A1, RS>=-5%, 1.25/1.50x)",
     select_spx_buf_rs(p_spx, "mom", 1, 3, -0.05), select_spx_buf_rs(p_exit, "mom", 1, 3, -0.05), run_bestsec_buf_rs(p_exit, -0.05), True, 1.25, 1.50, 1.50),
    ("6. A1-RS (-5.0%) 1.00x: Unlevered_1x (Route A1, RS>=-5%, 1.00x)",
     select_spx_buf_rs(p_spx, "mom", 1, 3, -0.05), select_spx_buf_rs(p_exit, "mom", 1, 3, -0.05), run_bestsec_buf_rs(p_exit, -0.05), True, 1.00, 1.00, 1.00),
]

print("=" * 155)
print("HEAD-TO-HEAD AUDIT: OFFICIAL 1.35x vs A1-RS 1.35x vs A1-RS 1.50x (True Daily MaxDD, Real SGOV, Updated DSR N=1,112)")
print("=" * 155)

for name, ps, per, peb, is_a1, lc2, lo3, lg3 in test_suites:
    ps_eff = make_routeA1_spy_picks(ps, per) if is_a1 else ps
    L_df, s_nav, s_mer = ra.simulate_zero_shared_code_strategy(
        name, months_213, months_214, p_ndx, p_spx, pk_q, pk_t, ps_eff, per, peb,
        reg_map, cash_map, vol_lk, ret_lk, gics_grp_map, top_gics_grp_by_t,
        cal, get_daily_df, df_sgov, df_bil,
        sep_off_mode="bestsec", conc_mode="none", l_conf2=lc2, l_ord3=lo3, l_grp3=lg3,
        gate_version="v1", use_actual_sgov=True, borrow_spread_ann=0.005
    )
    s_row = ra.summarize_strategy(name, "Audit", L_df, s_nav, s_mer, months_213, cash_map)
    r213 = L_df.loc[months_213, "net"].values
    r214 = L_df.loc[months_214, "net"].values
    sr213, dsr213_own, dsr213_ben = calc_dsr(r213, rf_213, sk_bench_213, ku_bench_213, n_trials=1112)
    sr214, dsr214_own, dsr214_ben = calc_dsr(r214, rf_214, sk_bench_214, ku_bench_214, n_trials=1112)

    max_single_wt = max(max(d.values()) for d in L_df["weights_dict"])
    max_tot_exp = float(L_df["long_exp"].max())
    r_2022 = float(s_row["Ret_2022"])
    r_26_off = float(np.prod(1.0 + r214[-4:]) - 1.0)
    r_oct26 = float(s_row["Ret_Oct2026_Live"])

    print(f"\n[{name}]")
    print(f"  213M (2009-01..2026-09): CAGR={s_row['CAGR_213 (09-26/09)']*100:6.2f}% | SR={sr213:5.3f} | DailyMaxDD={s_row['Daily_MaxDD_213']*100:6.2f}% ({s_row['Daily_DD_Trough']}) | DSR(N=1112): Own={dsr213_own:.4f} / Bench={dsr213_ben:.4f}")
    print(f"  214M (incl. Oct 2026)  : CAGR={s_row['CAGR_214 (incl Oct26)']*100:6.2f}% | SR={sr214:5.3f} | 2026_LiveDailyMDD={s_row['Live_2026_Worst_Daily_DD']*100:6.2f}% | DSR(N=1112): Own={dsr214_own:.4f} / Bench={dsr214_ben:.4f}")
    print(f"  Risk & Stress          : MonthlyMDD={s_row['Monthly_MaxDD_213']*100:6.2f}% | MinMER={s_row['Min_Daily_Margin_Equity_Ratio']*100:5.1f}% | MaxTotalExp={max_tot_exp:.2f}x | MaxSingleStock={max_single_wt*100:6.2f}% | 2022={r_2022*100:+5.1f}% | 26_JulOct={r_26_off*100:+5.1f}% | Oct26={r_oct26*100:+5.1f}%")
