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

ym_to_t = { (t + pd.offsets.MonthBegin(1)).strftime("%Y-%m"): t for t in months_all }
t_dec_u2d = { ym_to_t["2010-12"], ym_to_t["2018-12"], ym_to_t["2022-12"] }
t_jan_u2d = { ym_to_t["2011-01"], ym_to_t["2019-01"], ym_to_t["2023-01"] }

pk_t = select_spx_stateful(p_tech, "mom", 1, 1, None)
pk_q_rst = select_ndx_stateful(p_ndx, "sharpe", 2, 5, reset_t_set=t_jan_u2d)
pk_s_rs5_rst = select_spx_stateful(p_spx, "mom", 1, 3, -0.05, reset_t_set=t_jan_u2d)
pk_er_rs5_rst = select_spx_stateful(p_exit, "mom", 1, 3, -0.05, reset_t_set=t_jan_u2d)
pk_eb_rs5_rst = select_bestsec_stateful(p_exit, -0.05, reset_t_set=t_jan_u2d)

pk_s_nors_rst = select_spx_stateful(p_spx, "mom", 1, 3, None, reset_t_set=t_jan_u2d)
pk_er_nors_rst = select_spx_stateful(p_exit, "mom", 1, 3, None, reset_t_set=t_jan_u2d)
pk_eb_nors_rst = select_bestsec_stateful(p_exit, None, reset_t_set=t_jan_u2d)

print("Verified V3 Election Reset picks at 2011-01, 2019-01, 2023-01:")
for ym in ["2011-01", "2019-01", "2023-01"]:
    t = ym_to_t[ym]
    print(f"  {ym}: QQQ={pk_q_rst[t]} | Tech={pk_t[t]} | SPY_RS5={pk_s_rs5_rst[t]} | ExIT_Raw_RS5={pk_er_rs5_rst[t]} | ExIT_BS_RS5={pk_eb_rs5_rst[t]}")
