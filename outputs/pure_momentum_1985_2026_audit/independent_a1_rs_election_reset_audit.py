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

def select_ndx_stateful(panel, sig_col="sharpe", k=2, keep=5, reset_t_set=None):
    reset_t_set = reset_t_set or set()
    held, out = [], {}
    for t_val, g in panel[panel[sig_col].notna()].groupby("t", sort=True):
        if t_val in reset_t_set:
            held = []
        g = g.sort_values([sig_col, "ticker"], ascending=[False, True]).reset_index(drop=True)
        g["rk"] = g.index + 1
        rk_map = dict(zip(g["ticker"], g["rk"]))
        ranked = list(g["ticker"])
        kept = [x for x in held if rk_map.get(x, 999) <= keep][:k]
        for x in ranked:
            if len(kept) >= k:
                break
            if x not in kept:
                kept.append(x)
        held = list(kept)
        out[t_val] = list(kept)
    return out

def select_spx_stateful(panel, sig_col="mom", n_pick=1, hold_k=3, thresh=None, reset_t_set=None):
    reset_t_set = reset_t_set or set()
    held, out = [], {}
    for t_val, g in panel[panel[sig_col].notna()].groupby("t", sort=True):
        if t_val in reset_t_set:
            held = []
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
        out[t_val] = list(held)
    return out

def select_bestsec_stateful(df_exit_panel, thresh=None, reset_t_set=None):
    reset_t_set = reset_t_set or set()
    held_bs, out_bs = [], {}
    for t_val, g in df_exit_panel[df_exit_panel["mom"].notna()].groupby("t", sort=True):
        if t_val in reset_t_set:
            held_bs = []
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
        held_bs = list(kept)
        out_bs[t_val] = [kept[0], top_sec]
    return out_bs

p_tech = p_spx[p_spx["clean_sector"] == "Information Technology"].copy()
p_exit = p_spx[p_spx["clean_sector"] != "Information Technology"].copy()

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

sec_rk_raw, sec_rk_sh, soxx_top1 = {}, {}, {}
for (t_val, sec_val), g in p_spx.groupby(["t", "clean_sector"], sort=True):
    gv = g[g["mom"].notna()]
    sr_r = gv.sort_values(["mom", "ticker"], ascending=[False, True]).reset_index(drop=True)
    sr_s = gv[gv["sharpe"].notna()].sort_values(["sharpe", "ticker"], ascending=[False, True]).reset_index(drop=True)
    for idx, tk in enumerate(sr_r["ticker"]): sec_rk_raw[(t_val, tk)] = idx + 1
    for idx, tk in enumerate(sr_s["ticker"]): sec_rk_sh[(t_val, tk)] = idx + 1
    if sec_val == "Information Technology":
        g_semi = gv[gv["gics_4digit_group"] == "4530_Semiconductors_and_Equipment"].sort_values(["mom", "ticker"], ascending=[False, True])
        if len(g_semi): soxx_top1[t_val] = g_semi["ticker"].iloc[0]

ym_to_t = { (t + pd.offsets.MonthBegin(1)).strftime("%Y-%m"): t for t in months_all }
t_dec_u2d = { ym_to_t["2010-12"], ym_to_t["2018-12"], ym_to_t["2022-12"] }
t_jan_u2d = { ym_to_t["2011-01"], ym_to_t["2019-01"], ym_to_t["2023-01"] }
t_feb_u2d = { ym_to_t["2011-02"], ym_to_t["2019-02"], ym_to_t["2023-02"] }

# Fast monthly simulator with Election Reset options
def sim_monthly_fast(
    pk_q, pk_t, pk_s, pk_er, pk_eb,
    is_a1=False, conc_mode="none", l_conf2=1.20, l_ord3=1.35, l_grp3=1.35,
    use_actual_sgov=True, borrow_spread_ann=0.005, cost_bp=0.0010,
    dec_mode="normal",       # 'normal', 'sgov100', 'half50', 'force_sepoff', 'unlevered'
    jan_mode="normal",       # 'normal', 'sgov100'
    feb_mode="normal",       # 'normal', 'sgov100'
):
    prev_drifted_w = {}
    rows = []
    for t in months_214:
        ym = (t + pd.offsets.MonthBegin(1)).strftime("%Y-%m")
        rm = reg_map[t]
        sep_on = bool(rm["sep_on"])
        qqq_vol21 = float(rm["qqq_vol21"])
        dm_panic = bool(rm["dm_panic"])

        r_tbill = float(cash_map[t]["rf_tbill"])
        r_cash = float(cash_map[t]["ret_sgov_actual"]) if use_actual_sgov else r_tbill
        r_borrow = r_tbill + borrow_spread_ann / 12.0

        q1, q2 = pk_q[t]
        t1 = pk_t[t][0]
        s1_raw = pk_s[t][0]
        er1 = pk_er[t][0]
        eb1 = pk_eb[t][0]

        # Effective SEP-ON and Election Override
        is_dec = (t in t_dec_u2d)
        is_jan = (t in t_jan_u2d)
        is_feb = (t in t_feb_u2d)

        eff_sep_on = sep_on
        if is_dec and dec_mode == "force_sepoff":
            eff_sep_on = False

        s1 = er1 if (is_a1 and (not eff_sep_on) and (t1 == s1_raw)) else s1_raw

        w_base = {}
        for x in [q1, q2, t1, s1]:
            w_base[x] = w_base.get(x, 0.0) + 0.25

        port_vol_est = float(sum(wt * vol_lk.get((t, tk), 0.35) for tk, wt in w_base.items()))
        lowvol_ok = bool(eff_sep_on and (qqq_vol21 <= 0.30) and (port_vol_est <= 0.55) and (not dm_panic))

        is_3leg = (t1 == s1) and (t1 in (q1, q2))
        is_2leg = (not is_3leg) and ((t1 == s1) or (t1 in (q1, q2)) or (s1 in (q1, q2)))
        ov_tk = t1 if ((t1 == s1) or (t1 in (q1, q2))) else (s1 if (s1 in (q1, q2)) else "")
        is_subind_grp1 = (gics_grp_map.get((t, ov_tk), "") == top_gics_grp_by_t.get(t, "")) if ov_tk else False
        is_soxx1 = (ov_tk != "") and (soxx_top1.get(t, "") == ov_tk)
        sr_r = sec_rk_raw.get((t, ov_tk), 99)
        sr_s = sec_rk_sh.get((t, ov_tk), 99)
        t_in_q = (t1 in (q1, q2))
        s_in_q = (s1 in (q1, q2))
        is_conf2 = bool(is_2leg and ov_tk != "" and ((sr_r == 1 and sr_s == 1) or (s_in_q and not t_in_q and sr_r == 1) or (t_in_q and not s_in_q and is_soxx1)))

        w_stocks = {}
        w_cash = 0.0
        w_borrow = 0.0
        L_mult = 1.0

        if (is_dec and dec_mode == "sgov100") or (is_jan and jan_mode == "sgov100") or (is_feb and feb_mode == "sgov100"):
            w_stocks = {}
            w_cash = 1.0
            w_borrow = 0.0
            L_mult = 0.0
        elif not eff_sep_on:
            w_stocks[t1] = w_stocks.get(t1, 0.0) + 0.25
            w_stocks[s1] = w_stocks.get(s1, 0.0) + 0.25
            w_stocks[eb1] = w_stocks.get(eb1, 0.0) + 0.25
            w_cash = 0.25
            if is_dec and dec_mode == "half50":
                w_stocks = {tk: wt * 0.50 for tk, wt in w_stocks.items()}
                w_cash = 1.0 - sum(w_stocks.values())
        else:
            w_work = dict(w_base)
            if is_3leg and conc_mode == "grp1_100" and is_subind_grp1:
                w_work = {ov_tk: 1.00}
            if is_dec and dec_mode == "half50":
                w_stocks = {tk: wt * 0.50 for tk, wt in w_work.items()}
                w_cash = 0.50
                L_mult = 0.50
            elif is_dec and dec_mode == "unlevered":
                w_stocks = dict(w_work)
                L_mult = 1.0
            else:
                if lowvol_ok:
                    if is_3leg:
                        L_mult = l_grp3 if is_subind_grp1 else l_ord3
                    elif is_2leg and is_conf2:
                        L_mult = l_conf2
                w_stocks = {tk: wt * L_mult for tk, wt in w_work.items()}
                w_borrow = max(0.0, L_mult - 1.0)

        w_all_tradable = dict(w_stocks)
        if use_actual_sgov and w_cash > 0:
            w_all_tradable["SGOV"] = w_cash

        gross_stocks = sum(wt * ret_lk[(t, tk)] for tk, wt in w_stocks.items())
        gross_total = gross_stocks + w_cash * r_cash - w_borrow * r_borrow

        if not prev_drifted_w:
            to = float(sum(abs(v) for v in w_all_tradable.values()))
        else:
            all_k = set(w_all_tradable.keys()) | set(prev_drifted_w.keys())
            to = float(sum(abs(w_all_tradable.get(k, 0.0) - prev_drifted_w.get(k, 0.0)) for k in all_k))

        net_total = (1.0 + gross_total) * ((1.0 - cost_bp) ** to) - 1.0 if to > 0 else gross_total
        end_eq = 1.0 + gross_total
        if end_eq > 0:
            prev_drifted_w = {tk: wt * (1.0 + ret_lk[(t, tk)]) / end_eq for tk, wt in w_stocks.items() if wt > 0}
            if use_actual_sgov and w_cash > 0:
                prev_drifted_w["SGOV"] = w_cash * (1.0 + r_cash) / end_eq
        else:
            prev_drifted_w = {}

        rows.append({"t": t, "ym": ym, "net": net_total, "gross": gross_total, "to": to, "w_stocks": w_stocks, "w_cash": w_cash, "L_mult": L_mult})
    return pd.DataFrame(rows).set_index("t")

rf_213 = np.array([cash_map[t]["rf_tbill"] for t in months_213])
rf_214 = np.array([cash_map[t]["rf_tbill"] for t in months_214])

def eval_df(df):
    r213 = df.loc[months_213, "net"].values
    r214 = df.loc[months_214, "net"].values
    c213 = float(np.prod(1.0 + r213) ** (12.0 / len(r213)) - 1.0)
    c214 = float(np.prod(1.0 + r214) ** (12.0 / len(r214)) - 1.0)
    sr213 = float(np.mean(r213 - rf_213) / np.std(r213, ddof=1) * np.sqrt(12.0))
    sr214 = float(np.mean(r214 - rf_214) / np.std(r214, ddof=1) * np.sqrt(12.0))
    w = np.concatenate([[1.0], np.cumprod(1.0 + r214)])
    mdd = float((w / np.maximum.accumulate(w) - 1.0).min())
    # Returns in Dec, Jan, Feb across the 3 U->D midterms
    r_decs = [float(df[df["ym"] == ym]["net"].iloc[0]) for ym in ["2010-12", "2018-12", "2022-12"]]
    r_jans = [float(df[df["ym"] == ym]["net"].iloc[0]) for ym in ["2011-01", "2019-01", "2023-01"]]
    r_febs = [float(df[df["ym"] == ym]["net"].iloc[0]) for ym in ["2011-02", "2019-02", "2023-02"]]
    return c213, c214, sr213, sr214, mdd, r_decs, r_jans, r_febs

# Pre-build sleeve pick sets:
# 1. Normal (no buffer reset)
pk_t = select_spx_stateful(p_tech, "mom", 1, 1, None)
pk_q_norm = select_ndx_stateful(p_ndx, "sharpe", 2, 5)
pk_s_nors_norm = select_spx_stateful(p_spx, "mom", 1, 3, None)
pk_er_nors_norm = select_spx_stateful(p_exit, "mom", 1, 3, None)
pk_eb_nors_norm = select_bestsec_stateful(p_exit, None)

pk_s_rs5_norm = select_spx_stateful(p_spx, "mom", 1, 3, -0.05)
pk_er_rs5_norm = select_spx_stateful(p_exit, "mom", 1, 3, -0.05)
pk_eb_rs5_norm = select_bestsec_stateful(p_exit, -0.05)

# 2. Reset at end of Dec (entering Jan: 2011-01, 2019-01, 2023-01)
pk_q_rst_jan = select_ndx_stateful(p_ndx, "sharpe", 2, 5, reset_t_set=t_jan_u2d)
pk_s_nors_rst_jan = select_spx_stateful(p_spx, "mom", 1, 3, None, reset_t_set=t_jan_u2d)
pk_er_nors_rst_jan = select_spx_stateful(p_exit, "mom", 1, 3, None, reset_t_set=t_jan_u2d)
pk_eb_nors_rst_jan = select_bestsec_stateful(p_exit, None, reset_t_set=t_jan_u2d)

pk_s_rs5_rst_jan = select_spx_stateful(p_spx, "mom", 1, 3, -0.05, reset_t_set=t_jan_u2d)
pk_er_rs5_rst_jan = select_spx_stateful(p_exit, "mom", 1, 3, -0.05, reset_t_set=t_jan_u2d)
pk_eb_rs5_rst_jan = select_bestsec_stateful(p_exit, -0.05, reset_t_set=t_jan_u2d)

# 3. Reset at end of Jan (entering Feb, for 2M dodge)
pk_q_rst_feb = select_ndx_stateful(p_ndx, "sharpe", 2, 5, reset_t_set=t_feb_u2d)
pk_s_nors_rst_feb = select_spx_stateful(p_spx, "mom", 1, 3, None, reset_t_set=t_feb_u2d)
pk_er_nors_rst_feb = select_spx_stateful(p_exit, "mom", 1, 3, None, reset_t_set=t_feb_u2d)
pk_eb_nors_rst_feb = select_bestsec_stateful(p_exit, None, reset_t_set=t_feb_u2d)

pk_s_rs5_rst_feb = select_spx_stateful(p_spx, "mom", 1, 3, -0.05, reset_t_set=t_feb_u2d)
pk_er_rs5_rst_feb = select_spx_stateful(p_exit, "mom", 1, 3, -0.05, reset_t_set=t_feb_u2d)
pk_eb_rs5_rst_feb = select_bestsec_stateful(p_exit, -0.05, reset_t_set=t_feb_u2d)

for panel_title, is_a1, use_rs, conc_m, lc2, lo3, lg3, use_sgov in [
    ("PANEL A: 原版 1.35x 正式主线 (BestSec_ModBurst_135_75_25_GateV1: Route 1, No RS)", False, False, "none", 1.20, 1.35, 1.35, True),
    ("PANEL B: A1-RS (-5.0%) 1.35x 新甜蜜点 (A1-RS_ModBurst_135_75_25_GateV1: Route A1 + RS>=-5%)", True, True, "none", 1.20, 1.35, 1.35, True),
    ("PANEL C: A1-RS (-5.0%) 1.50x 稳健版 (A1-RS_Prudent_150_75_25_GateV1: Route A1 + RS>=-5%)", True, True, "none", 1.25, 1.50, 1.50, True),
    ("PANEL D: ExpABC_3b_BestSec 1.75x (对照用户 76.46% 账本口径)", False, False, "grp1_100", 1.25, 1.50, 1.75, False),
]:
    print("\n" + "=" * 150)
    print(panel_title)
    print("=" * 150)
    ps_n = pk_s_rs5_norm if use_rs else pk_s_nors_norm
    per_n = pk_er_rs5_norm if use_rs else pk_er_nors_norm
    peb_n = pk_eb_rs5_norm if use_rs else pk_eb_nors_norm

    ps_rj = pk_s_rs5_rst_jan if use_rs else pk_s_nors_rst_jan
    per_rj = pk_er_rs5_rst_jan if use_rs else pk_er_nors_rst_jan
    peb_rj = pk_eb_rs5_rst_jan if use_rs else pk_eb_nors_rst_jan

    ps_rf = pk_s_rs5_rst_feb if use_rs else pk_s_nors_rst_feb
    per_rf = pk_er_rs5_rst_feb if use_rs else pk_er_nors_rst_feb
    peb_rf = pk_eb_rs5_rst_feb if use_rs else pk_eb_nors_rst_feb

    configs = [
        ("V0. 不躲、不重置 (Baseline)", pk_q_norm, ps_n, per_n, peb_n, "normal", "normal", "normal"),
        ("V1. 仅 12月底 Reset Hold-Buffer (12月不躲，1月从零选)", pk_q_rst_jan, ps_rj, per_rj, peb_rj, "normal", "normal", "normal"),
        ("V2. 只躲 12月 SGOV (不重置 Hold-Buffer，1月沿用旧记忆)", pk_q_norm, ps_n, per_n, peb_n, "sgov100", "normal", "normal"),
        ("V3. Election Reset 标准版 (12月 100% SGOV + 12月底 Reset Hold-Buffer)", pk_q_rst_jan, ps_rj, per_rj, peb_rj, "sgov100", "normal", "normal"),
        ("V4. Election Reset 半仓版 (12月 50%仓位+50%SGOV + 12月底 Reset)", pk_q_rst_jan, ps_rj, per_rj, peb_rj, "half50", "normal", "normal"),
        ("V5. Election Reset 强制SEP=OFF防守版 (12月 25/25/25/25 + 12月底 Reset)", pk_q_rst_jan, ps_rj, per_rj, peb_rj, "force_sepoff", "normal", "normal"),
        ("V6. Election Reset 12月仅去杠杆版 (12月 1.0x + 12月底 Reset)", pk_q_rst_jan, ps_rj, per_rj, peb_rj, "unlevered", "normal", "normal"),
        ("V7. 躲 12月+1月 SGOV (2个月现金 + 1月底 Reset)", pk_q_rst_feb, ps_rf, per_rf, peb_rf, "sgov100", "sgov100", "normal"),
        ("V8. 躲 12月+1月+2月 SGOV (3个月现金)", pk_q_norm, ps_n, per_n, peb_n, "sgov100", "sgov100", "sgov100"),
    ]

    base_c213, base_c214 = None, None
    for vname, pq, ps, per, peb, dm, jm, fm in configs:
        df_sim = sim_monthly_fast(
            pq, pk_t, ps, per, peb,
            is_a1=is_a1, conc_mode=conc_m, l_conf2=lc2, l_ord3=lo3, l_grp3=lg3,
            use_actual_sgov=use_sgov, dec_mode=dm, jan_mode=jm, feb_mode=fm
        )
        c213, c214, sr213, sr214, mdd, r_decs, r_jans, r_febs = eval_df(df_sim)
        if base_c213 is None:
            base_c213, base_c214 = c213, c214
        d213 = (c213 - base_c213) * 100
        d214 = (c214 - base_c214) * 100
        print(f"  {vname:66s} | CAGR213={c213*100:6.2f}% ({d213:+5.2f}pp) | CAGR214={c214*100:6.2f}% ({d214:+5.2f}pp) | SR213={sr213:5.3f} | SR214={sr214:5.3f} | MDD={mdd*100:6.2f}% | Dec[10/18/22]=[{r_decs[0]*100:+5.1f}%,{r_decs[1]*100:+5.1f}%,{r_decs[2]*100:+5.1f}%] | Jan[11/19/23]=[{r_jans[0]*100:+5.1f}%,{r_jans[1]*100:+5.1f}%,{r_jans[2]*100:+5.1f}%]")
