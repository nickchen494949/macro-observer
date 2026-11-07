#!/usr/bin/env python3
"""
run_tech_arena_challenger_audit.py
==================================
Clean-Room One-Shot Challenger Audit for the User's Pre-Registered Next-Gen Concept:
  "Outer shell 100% untouched (QQQ Sharpe Top-2/Hold<=5 + SPY/Ex-IT BestSec + SEP + Gate V1 1.20x/1.35x + A1-RS + V3).
   Only upgrade the Tech attack leg: let Semi / Super-Tech / Official IT compete each month —
   first pick the strongest Tech pool by equal-weighted 12-1 momentum, then buy the #1 stock inside that pool."

Evaluates against `Current (Frozen A1-RS 1.35x + V3 = 64.95% CAGR)`:
  - `TAC-1 (Exact 3-Pool Nested Arena: Semi-4530 vs Official-IT vs Super-Tech)`:
      At each month-end t, compare the equal-weighted 12-1 momentum of:
        1) `Semi (GICS 4530)`
        2) `Official IT (GICS 4510 + 4520 + 4530)`
        3) `Super-Tech (Official IT + Platform/Fintech Giants: META, GOOGL, NFLX, AMZN, TSLA, V, MA, PYPL)`
      Pick the pool with the highest equal-weighted 12-1 momentum, then select `Hard Top-1` (12-1 Raw) inside that winning pool.
  - `TAC-2 (3-Pool Semi+Storage Arena: Semi&Storage [4530+452020] vs Official-IT vs Super-Tech)`:
      Includes `SNDK / WDC / STX / SMCI / AAPL` alongside `NVDA / AMD / AVGO / MU` in the Silicon & Storage pool (`4530 + 452020`),
      competing against `Official IT` and `Super-Tech`.
  - `TAC-3 (4-Subsector Disjoint Tech Arena: Semi [4530] vs Hardware/Storage [4520] vs Software [4510] vs Platform Giants)`:
      Directly implements the 4 cycle buckets in the prompt:
        1) Semiconductor Cycle (`GICS 4530`: `NVDA, AMD, AVGO, MU, FSLR...`)
        2) Hardware/Storage/Networking Cycle (`GICS 4520`: `AAPL, ANET, SNDK, SMCI, WDC, STX...`)
        3) Software Cycle (`GICS 4510`: `PLTR, NOW, CRM, ORCL, ADBE, PANW...`)
        4) Platform Cycle (`META, GOOGL, NFLX, AMZN, TSLA, V, MA, PYPL`)
      Rank the 4 sub-pools by equal-weighted 12-1 momentum at month-end t, then buy `Hard Top-1` inside the #1 sub-pool.
"""
import os
import sys
import json
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
IN_DIR = os.path.join(ROOT, "outputs", "pure_momentum_1985_2026_audit", "inputs")
OUT_DIR = HERE
os.makedirs(OUT_DIR, exist_ok=True)

sys.path.insert(0, os.path.join(ROOT, "outputs", "pure_momentum_1985_2026_audit"))
import build_portable_inputs_from_raw as bpi

# -------------------------------------------------------------------------
# 1. Load Canonical 214-Month Clean-Room Inputs
# -------------------------------------------------------------------------
p_spx = pd.read_parquet(os.path.join(IN_DIR, "v3_spx_panel_214m.parquet"))
p_ndx = pd.read_parquet(os.path.join(IN_DIR, "v3_ndx_panel_214m.parquet"))
reg_df = pd.read_csv(os.path.join(IN_DIR, "v3_regime_and_cash_214m.csv"))

p_spx["t"] = pd.to_datetime(p_spx["t"])
p_ndx["t"] = pd.to_datetime(p_ndx["t"])
reg_df["t"] = pd.to_datetime(reg_df["t"])

months_all = sorted(p_spx["t"].unique())
months_213 = [t for t in months_all if pd.Timestamp("2008-12-31") <= t <= pd.Timestamp("2026-08-31")]
months_214 = [t for t in months_all if pd.Timestamp("2008-12-31") <= t <= pd.Timestamp("2026-09-30")]

p_spx = p_spx[p_spx["t"].isin(months_214)].copy()
p_ndx = p_ndx[p_ndx["t"].isin(months_214)].copy()
reg_map = {r["t"]: r for _, r in reg_df.iterrows()}
rf_213 = np.array([float(reg_map[t]["rf_tbill"]) for t in months_213])
rf_214 = np.array([float(reg_map[t]["rf_tbill"]) for t in months_214])

t_dec_u2d = {pd.Timestamp("2010-11-30"), pd.Timestamp("2018-11-30"), pd.Timestamp("2022-11-30")}
t_jan_u2d = {pd.Timestamp("2010-12-31"), pd.Timestamp("2018-12-31"), pd.Timestamp("2022-12-31")}

p_spx["key"] = list(zip(p_spx["src"], p_spx["sym"]))
p_ndx["key"] = list(zip(p_ndx["src"], p_ndx["sym"]))

sec_ret1m_gics = p_spx.groupby(["t", "clean_sector"])["ret_1m"].mean().to_dict()
p_spx["rs_gics"] = [
    r1 - sec_ret1m_gics.get((t, s), np.nan)
    for t, s, r1 in zip(p_spx["t"], p_spx["clean_sector"], p_spx["ret_1m"])
]

ret_lk = {
    (r.t, r.ticker): float(r.hold_ret)
    for df_p in (p_spx, p_ndx)
    for r in df_p[["t", "ticker", "hold_ret"]].itertuples(index=False)
    if pd.notna(r.hold_ret)
}
vol_lk = {
    (r.t, r.ticker): float(r.vol)
    for df_p in (p_spx, p_ndx)
    for r in df_p[["t", "ticker", "vol"]].itertuples(index=False)
    if pd.notna(r.vol)
}
key_lk = {}
for df_p in (p_spx, p_ndx):
    for r in df_p[["t", "ticker", "key"]].itertuples(index=False):
        if (r.t, r.ticker) not in key_lk:
            key_lk[(r.t, r.ticker)] = r.key

# Load daily series for exact Daily MaxDD & MinMER calculation
all_keys = [(s, y) for s, y in (set(p_spx["key"]) | set(p_ndx["key"])) if pd.notna(s) and pd.notna(y)]
df_s_cache = {}
for src, sym in all_keys:
    df_s_cache[(src, sym)] = bpi.load_fixed(src, sym)
cal = bpi.trading_calendar()

# -------------------------------------------------------------------------
# 2. Selection & Simulation Helpers (100% Aligned with Frozen Spec)
# -------------------------------------------------------------------------
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


def select_spx_stateful(panel, sig_col="mom", n_pick=1, hold_k=3, rs_col="rs_gics", thresh=None, reset_t_set=None):
    reset_t_set = reset_t_set or set()
    held, out = [], {}
    for t_val, g in panel[panel[sig_col].notna()].groupby("t", sort=True):
        if t_val in reset_t_set:
            held = []
        g = g.sort_values([sig_col, "ticker"], ascending=[False, True]).reset_index(drop=True)
        g["rk"] = g.index + 1
        rk_map = dict(zip(g["ticker"], g["rk"]))
        rs_map = dict(zip(g["ticker"], g[rs_col])) if (rs_col and rs_col in g.columns) else {}
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


def select_bestgroup_stateful(df_exit_panel, group_col="clean_sector", rs_col="rs_gics", thresh=None, reset_t_set=None):
    reset_t_set = reset_t_set or set()
    held_bs, out_bs = [], {}
    for t_val, g in df_exit_panel[df_exit_panel["mom"].notna()].groupby("t", sort=True):
        if t_val in reset_t_set:
            held_bs = []
        sec_ew = g.groupby(group_col)["mom"].mean().sort_values(ascending=False)
        top_sec = str(sec_ew.index[0])
        sec_rk = {s: i + 1 for i, s in enumerate(sec_ew.index)}
        g = g.copy()
        g["sec_rk"] = g[group_col].map(sec_rk)
        g_top = g[g["sec_rk"] == 1].sort_values(["mom", "ticker"], ascending=[False, True])
        g_rest = g[g["sec_rk"] > 1].sort_values(["sec_rk", "mom", "ticker"], ascending=[True, False, True])
        ranked = list(pd.concat([g_top, g_rest])["ticker"])
        rank = {x: i + 1 for i, x in enumerate(ranked)}
        rs_map = dict(zip(g["ticker"], g[rs_col])) if (rs_col and rs_col in g.columns) else {}
        kept = [
            x for x in held_bs
            if rank.get(x, 999) <= 3 and (thresh is None or rank.get(x, 999) == 1 or rs_map.get(x, 0.0) >= thresh)
        ][:1]
        if not kept:
            kept = [ranked[0]]
        held_bs = list(kept)
        out_bs[t_val] = [kept[0], top_sec]
    return out_bs


def build_group_rank_maps(panel_spx, group_col, sub_leader_mask_col=None):
    grp_rk_raw, grp_rk_sh, sub_top1 = {}, {}, {}
    for (t_val, grp_val), g in panel_spx.groupby(["t", group_col], sort=True):
        gv = g[g["mom"].notna()]
        sr_r = gv.sort_values(["mom", "ticker"], ascending=[False, True]).reset_index(drop=True)
        sr_s = gv[gv["sharpe"].notna()].sort_values(["sharpe", "ticker"], ascending=[False, True]).reset_index(drop=True)
        for idx, tk in enumerate(sr_r["ticker"]):
            grp_rk_raw[(t_val, tk)] = idx + 1
        for idx, tk in enumerate(sr_s["ticker"]):
            grp_rk_sh[(t_val, tk)] = idx + 1
    if sub_leader_mask_col:
        for t_val, g in panel_spx[panel_spx[sub_leader_mask_col] & panel_spx["mom"].notna()].groupby("t", sort=True):
            gs = g.sort_values(["mom", "ticker"], ascending=[False, True])
            if len(gs):
                sub_top1[t_val] = gs["ticker"].iloc[0]
    return grp_rk_raw, grp_rk_sh, sub_top1


# -------------------------------------------------------------------------
# 3. Tech-Arena Pool Competition Selector
# -------------------------------------------------------------------------
PLATFORM_GIANTS = {"META", "FB", "GOOGL", "GOOG", "NFLX", "AMZN", "TSLA", "V", "MA", "PYPL"}


def select_tech_arena(panel_spx, pool_defs_dict, sep_on_only_for_subpools=False, fallback_pool_name="Official_IT"):
    """
    At each formation date t:
      - Compute the equal-weighted 12-1 momentum (`mean(mom)`) of each candidate Tech pool in `pool_defs_dict`.
      - Select the pool with the highest equal-weighted 12-1 momentum (`winning_pool`).
      - Pick the `Hard Top-1` (`12-1 Raw`, `Hold<=1`) stock inside `winning_pool`.
    Returns:
      - `pk_t`: dict `t -> [top1_ticker]`
      - `win_pool_map`: dict `t -> winning_pool_name`
      - `pool_scores_map`: dict `t -> {pool_name: ew_mom}`
    """
    pk_t, win_pool_map, pool_scores_map = {}, {}, {}
    for t_val, g in panel_spx[panel_spx["mom"].notna()].groupby("t", sort=True):
        sep_on = bool(reg_map[t_val]["sep_on"])
        scores = {}
        top_stock_per_pool = {}
        for p_name, mask_fn in pool_defs_dict.items():
            sub = g[mask_fn(g)].sort_values(["mom", "ticker"], ascending=[False, True])
            if len(sub) > 0:
                scores[p_name] = float(sub["mom"].mean())
                top_stock_per_pool[p_name] = str(sub["ticker"].iloc[0])
        if sep_on_only_for_subpools and (not sep_on) and (fallback_pool_name in top_stock_per_pool):
            best_pool = fallback_pool_name
        else:
            best_pool = max(scores.keys(), key=lambda k: (scores[k], k))
        pk_t[t_val] = [top_stock_per_pool[best_pool]]
        win_pool_map[t_val] = best_pool
        pool_scores_map[t_val] = scores
    return pk_t, win_pool_map, pool_scores_map


tech_tk_set_by_t = {
    t_val: set(g[g["clean_sector"] == "Information Technology"]["ticker"])
    for t_val, g in p_spx.groupby("t")
}


def sim_cleanroom_variant(
    name, pk_q, pk_t, pk_s, pk_er, pk_eb,
    grp_rk_raw, grp_rk_sh, sub_top1,
    win_pool_map=None, is_a1=True, a1_dedup_it_sector=False, l_conf2=1.20, l_ord3=1.35, cost_bp=0.0010
):
    prev_drifted_w = {}
    rows = []
    for t in months_214:
        ym = (t + pd.offsets.MonthBegin(1)).strftime("%Y-%m")
        rm = reg_map[t]
        sep_on = bool(rm["sep_on"])
        qqq_vol21 = float(rm["qqq_vol21"])
        dm_panic = bool(rm["dm_panic"])

        r_tbill = float(rm["rf_tbill"])
        r_cash = float(rm["ret_sgov_actual"])
        r_borrow = r_tbill + 0.005 / 12.0

        q1, q2 = pk_q[t]
        t1 = pk_t[t][0]
        s1_raw = pk_s[t][0]
        er1 = pk_er[t][0]
        eb1, eb_sec = pk_eb[t][0], pk_eb[t][1]
        w_pool = win_pool_map.get(t, "Official_IT") if win_pool_map else "Official_IT"

        is_dec = (t in t_dec_u2d)
        is_jan = (t in t_jan_u2d)

        # Route A1 De-duplication in SEP = OFF:
        #   - Standard (`t1 == s1_raw`): rotate SPY to Ex-IT Raw if exact ticker match
        #   - Sector-level (`a1_dedup_it_sector=True`): in SEP=OFF, Tech leg already holds 25% Tech;
        #     if SPY leg (`s1_raw`) also picks an IT stock (or matches `t1`), rotate SPY to Ex-IT Raw (`er1`) so SEP=OFF never holds 50% Tech.
        if is_a1 and (not sep_on):
            if a1_dedup_it_sector:
                s1 = er1 if ((t1 == s1_raw) or (s1_raw in tech_tk_set_by_t.get(t, set()))) else s1_raw
            else:
                s1 = er1 if (t1 == s1_raw) else s1_raw
        else:
            s1 = s1_raw

        w_base = {}
        for x in [q1, q2, t1, s1]:
            w_base[x] = w_base.get(x, 0.0) + 0.25

        port_vol_est = float(sum(wt * vol_lk.get((t, tk), 0.35) for tk, wt in w_base.items()))
        lowvol_ok = bool(sep_on and (qqq_vol21 <= 0.30) and (port_vol_est <= 0.55) and (not dm_panic))

        is_3leg = (t1 == s1) and (t1 in (q1, q2))
        is_2leg = (not is_3leg) and ((t1 == s1) or (t1 in (q1, q2)) or (s1 in (q1, q2)))
        ov_tk = t1 if ((t1 == s1) or (t1 in (q1, q2))) else (s1 if (s1 in (q1, q2)) else "")
        is_soxx1 = (ov_tk != "") and (sub_top1.get(t, "") == ov_tk)
        sr_r = grp_rk_raw.get((t, ov_tk), 99)
        sr_s = grp_rk_sh.get((t, ov_tk), 99)
        t_in_q = (t1 in (q1, q2))
        s_in_q = (s1 in (q1, q2))
        is_conf2 = bool(
            is_2leg and ov_tk != "" and (
                (sr_r == 1 and sr_s == 1) or
                (s_in_q and not t_in_q and sr_r == 1) or
                (t_in_q and not s_in_q and is_soxx1)
            )
        )

        w_stocks, w_cash, w_borrow, L_mult = {}, 0.0, 0.0, 1.0
        if is_dec:
            w_cash = 1.0
            L_mult = 0.0
        elif not sep_on:
            w_stocks[t1] = w_stocks.get(t1, 0.0) + 0.25
            w_stocks[s1] = w_stocks.get(s1, 0.0) + 0.25
            w_stocks[eb1] = w_stocks.get(eb1, 0.0) + 0.25
            w_cash = 0.25
        else:
            if lowvol_ok:
                if is_3leg:
                    L_mult = l_ord3
                elif is_2leg and is_conf2:
                    L_mult = l_conf2
            w_stocks = {tk: wt * L_mult for tk, wt in w_base.items()}
            w_borrow = max(0.0, L_mult - 1.0)

        w_all_tradable = dict(w_stocks)
        if w_cash > 0:
            w_all_tradable["SGOV"] = w_cash

        gross_stocks = sum(wt * ret_lk.get((t, tk), 0.0) for tk, wt in w_stocks.items())
        gross_total = gross_stocks + w_cash * r_cash - w_borrow * r_borrow

        if not prev_drifted_w:
            to = float(sum(abs(v) for v in w_all_tradable.values()))
        else:
            all_k = set(w_all_tradable.keys()) | set(prev_drifted_w.keys())
            to = float(sum(abs(w_all_tradable.get(k, 0.0) - prev_drifted_w.get(k, 0.0)) for k in all_k))

        net_total = (1.0 + gross_total) * ((1.0 - cost_bp) ** to) - 1.0 if to > 0 else gross_total
        end_eq = 1.0 + gross_total
        if end_eq > 0:
            prev_drifted_w = {tk: wt * (1.0 + ret_lk.get((t, tk), 0.0)) / end_eq for tk, wt in w_stocks.items() if wt > 0}
            if w_cash > 0:
                prev_drifted_w["SGOV"] = w_cash * (1.0 + r_cash) / end_eq
        else:
            prev_drifted_w = {}

        rows.append({
            "strategy": name,
            "t": t,
            "ym": ym,
            "sep_on": sep_on,
            "win_tech_pool": w_pool,
            "q1": q1, "q2": q2, "t1": t1, "s1_raw": s1_raw, "s1_eff": s1, "eb1": eb1, "eb_sec": eb_sec,
            "L_mult": round(L_mult, 4),
            "w_stocks": dict(w_stocks),
            "w_cash": w_cash,
            "w_borrow": w_borrow,
            "max_single_w": max(w_stocks.values()) if w_stocks else 0.0,
            "n_unique_stocks": len([k for k, v in w_stocks.items() if v > 0]),
            "turnover_two_way": to,
            "gross_ret": gross_total,
            "net_ret": net_total,
        })
    return pd.DataFrame(rows).set_index("ym")


def compute_daily_risk_metrics(df_ledger):
    W = 1.0
    pts_nav = {pd.Timestamp("2009-01-02"): 1.0}
    pts_mer = {pd.Timestamp("2009-01-02"): 1.0}

    for row in df_ledger.itertuples():
        t_ts = pd.Timestamp(row.t)
        d0_idx = cal.searchsorted(t_ts, side="right")
        d0 = cal[d0_idx]
        if t_ts == pd.Timestamp("2026-09-30"):
            d1 = pd.Timestamp("2026-10-29")
            m_days = cal[(cal >= d0) & (cal <= d1)]
        else:
            t_next = t_ts + pd.offsets.MonthEnd(1)
            d1_idx = cal.searchsorted(t_next, side="right")
            d1 = cal[d1_idx]
            m_days = cal[(cal >= d0) & (cal < d1)]

        h_dict = row.w_stocks
        w_cash = float(row.w_cash)
        w_borrow = float(row.w_borrow)
        r_cash_m = float(reg_map[t_ts]["ret_sgov_actual"])
        r_borrow_m = float(reg_map[t_ts]["borrow_m"])
        fin_drag_m = w_borrow * r_borrow_m - w_cash * r_cash_m

        s_map, p_e_map, v_rel_0 = {}, {}, {}
        for tk in h_dict:
            k = key_lk.get((t_ts, tk))
            df_s = df_s_cache.get(k)
            s_map[tk] = df_s
            if df_s is not None and len(df_s.loc[:d0]):
                o_val = df_s.loc[:d0, "o"].iloc[-1]
                c_val = df_s.loc[:d0, "c"].iloc[-1]
                p_e_map[tk] = float(o_val) if (pd.notna(o_val) and o_val > 0) else float(c_val)
            else:
                p_e_map[tk] = 1.0

        n_m = len(m_days)
        for d_i, d in enumerate(m_days):
            frac = (d_i + 1) / max(n_m, 1)
            pnl_c = -fin_drag_m * frac
            mv_long_rel = 0.0
            for tk, wv in h_dict.items():
                df_s = s_map[tk]
                c_d = float(df_s.loc[:d, "c"].iloc[-1]) if (df_s is not None and len(df_s.loc[:d])) else p_e_map[tk]
                rel = c_d / p_e_map[tk] if p_e_map[tk] > 0 else 1.0
                if d_i == 0:
                    v_rel_0[tk] = rel if rel > 0 else 1.0
                stock_mult = rel / v_rel_0[tk]
                pnl_c += wv * (stock_mult - 1.0)
                mv_long_rel += wv * stock_mult

            eq_rel = 1.0 + pnl_c
            pts_nav[d] = W * eq_rel
            pts_mer[d] = float(eq_rel / mv_long_rel) if mv_long_rel > 0 else 1.0

        W = W * (1.0 + float(row.net_ret))
        pts_nav[d1] = W

    s_nav = pd.Series(pts_nav).sort_index()
    s_nav = s_nav[~s_nav.index.duplicated(keep="last")]
    s_mer = pd.Series(pts_mer).sort_index()
    s_mer = s_mer[~s_mer.index.duplicated(keep="last")]

    dd_all = (s_nav / s_nav.cummax() - 1.0)
    d_dd_all = float(dd_all.min())
    s_2026 = s_nav.loc["2026-01-01":]
    dd_2026 = float((s_2026 / s_2026.cummax() - 1.0).min())
    min_mer = float(s_mer.loc[:pd.Timestamp("2026-10-01")].min())
    return d_dd_all, dd_2026, min_mer


def summarize_ledger(df):
    r213 = df.iloc[:213]["net_ret"].values
    r214 = df.iloc[:214]["net_ret"].values
    c213 = float(np.prod(1.0 + r213) ** (12.0 / len(r213)) - 1.0)
    c214 = float(np.prod(1.0 + r214) ** (12.0 / len(r214)) - 1.0)
    vol214 = float(np.std(r214, ddof=1) * np.sqrt(12.0))
    sr213 = float(np.mean(r213 - rf_213) / np.std(r213, ddof=1) * np.sqrt(12.0))
    sr214 = float(np.mean(r214 - rf_214) / np.std(r214, ddof=1) * np.sqrt(12.0))
    w = np.concatenate([[1.0], np.cumprod(1.0 + r214)])
    m_mdd = float((w / np.maximum.accumulate(w) - 1.0).min())
    wr = float(np.mean(r214 > 0))
    ann_to = float(df["turnover_two_way"].mean() * 12.0)
    avg_max_w = float(df["max_single_w"].mean())
    max_single_w = float(df["max_single_w"].max())
    avg_n_stocks = float(df["n_unique_stocks"].mean())
    d_mdd, d_mdd_2026, min_mer = compute_daily_risk_metrics(df)

    def sub_ret(start_ym, end_ym):
        sub = df.loc[(df.index >= start_ym) & (df.index <= end_ym), "net_ret"].values
        return float(np.prod(1.0 + sub) - 1.0) if len(sub) > 0 else 0.0

    pool_counts = df["win_tech_pool"].value_counts().to_dict()
    pool_str = "; ".join([f"{k}:{v}" for k, v in sorted(pool_counts.items(), key=lambda x: -x[1])])

    return {
        "Strategy": df["strategy"].iloc[0],
        "CAGR_213M": c213,
        "CAGR_214M": c214,
        "Ann_Vol": vol214,
        "Sharpe_213M": sr213,
        "Sharpe_214M": sr214,
        "Monthly_MaxDD": m_mdd,
        "Hist_Daily_MaxDD": d_mdd,
        "Live_2026_Daily_MaxDD": d_mdd_2026,
        "MinMER": min_mer,
        "Win_Rate": wr,
        "Ann_TwoWay_Turnover": ann_to,
        "Avg_Max_Single_Stock_Weight": avg_max_w,
        "Peak_Single_Stock_Weight": max_single_w,
        "Avg_Unique_Stocks_Held": avg_n_stocks,
        "Ret_2018_2019_XLC_Split": sub_ret("2018-01", "2019-12"),
        "Ret_2022_RateHike_Bear": sub_ret("2022-01", "2022-12"),
        "Ret_2023_Fintech_QQQ": sub_ret("2023-01", "2023-12"),
        "Ret_2024_XLK_Cap": sub_ret("2024-01", "2024-12"),
        "Ret_2026_YTD_10M": sub_ret("2026-01", "2026-10"),
        "Ret_2026_10_SingleMonth": float(df.loc["2026-10", "net_ret"]),
        "Winning_Pool_Months": pool_str,
    }


# -------------------------------------------------------------------------
# 4. Build Shared Outer Shell & Run Current vs Tech-Arena Challengers
# -------------------------------------------------------------------------
p_spx["is_semi_gics"] = (p_spx["clean_sector"] == "Information Technology") & (
    p_spx["gics_4digit_group"] == "4530_Semiconductors_and_Equipment"
)
grp_rk_raw, grp_rk_sh, sub_top1 = build_group_rank_maps(p_spx, "clean_sector", "is_semi_gics")

p_tech_it = p_spx[p_spx["clean_sector"] == "Information Technology"].copy()
p_exit_it = p_spx[p_spx["clean_sector"] != "Information Technology"].copy()

# Outer shell legs (100% identical across all variants!)
pk_q = select_ndx_stateful(p_ndx, "sharpe", 2, 5, reset_t_set=t_jan_u2d)
pk_s = select_spx_stateful(p_spx, "mom", 1, 3, "rs_gics", -0.05, reset_t_set=t_jan_u2d)
pk_er = select_spx_stateful(p_exit_it, "mom", 1, 3, "rs_gics", -0.05, reset_t_set=t_jan_u2d)
pk_eb = select_bestgroup_stateful(p_exit_it, "clean_sector", "rs_gics", -0.05, reset_t_set=t_jan_u2d)

# 0. Current Frozen (Fixed Official IT Tech Leg)
pk_t_curr = select_spx_stateful(p_tech_it, "mom", 1, 1, "rs_gics", None)
df_curr = sim_cleanroom_variant(
    "0. Current Frozen: Fixed Official IT (A1-RS 1.35x + V3)",
    pk_q, pk_t_curr, pk_s, pk_er, pk_eb, grp_rk_raw, grp_rk_sh, sub_top1
)

# 1. TAC-1: Exact 3-Pool Arena (`Semi 4530` vs `Official IT` vs `Super-Tech`, Exact-Ticker A1 `t1 == s1_raw`)
POOLS_TAC1 = {
    "1_Semi_4530": lambda d: d["gics_4digit_group"] == "4530_Semiconductors_and_Equipment",
    "2_Official_IT": lambda d: d["clean_sector"] == "Information Technology",
    "3_Super_Tech": lambda d: (d["clean_sector"] == "Information Technology") | d["ticker"].isin(PLATFORM_GIANTS),
}
pk_t_tac1, wp_tac1, sc_tac1 = select_tech_arena(p_spx, POOLS_TAC1, sep_on_only_for_subpools=False)
df_tac1 = sim_cleanroom_variant(
    "1. TAC-1 (3-Pool Arena: Semi-4530 vs Official-IT vs Super-Tech, Ticker A1, 1.35x + V3)",
    pk_q, pk_t_tac1, pk_s, pk_er, pk_eb, grp_rk_raw, grp_rk_sh, sub_top1, win_pool_map=wp_tac1, a1_dedup_it_sector=False
)

# 2. TAC-1_A1Sec: Exact 3-Pool Arena + Sector-Level Route A1 in SEP=OFF (prevents holding 25% Semi + 25% IT in SEP=OFF)
df_tac1b = sim_cleanroom_variant(
    "2. TAC-1_A1Sec (3-Pool Arena: Semi-4530 vs Official-IT vs Super-Tech + Sector-A1, 1.35x + V3)",
    pk_q, pk_t_tac1, pk_s, pk_er, pk_eb, grp_rk_raw, grp_rk_sh, sub_top1, win_pool_map=wp_tac1, a1_dedup_it_sector=True
)

# 3. TAC-2: 3-Pool Arena where Semi pool includes AI Storage/Hardware (`4530 + 452020`: NVDA/AMD/AVGO/MU + SNDK/WDC/STX/AAPL/SMCI)
POOLS_TAC2 = {
    "1_Semi_And_Storage_4530_452020": lambda d: (d["clean_sector"] == "Information Technology") & (
        d["gics_4grp_it"].isin(["453010_Semiconductors_and_Equipment", "452020_Tech_Hardware_Storage_Peripherals"])
    ),
    "2_Official_IT": lambda d: d["clean_sector"] == "Information Technology",
    "3_Super_Tech": lambda d: (d["clean_sector"] == "Information Technology") | d["ticker"].isin(PLATFORM_GIANTS),
}
pk_t_tac2, wp_tac2, _ = select_tech_arena(p_spx, POOLS_TAC2, sep_on_only_for_subpools=False)
df_tac2 = sim_cleanroom_variant(
    "3. TAC-2 (3-Pool Arena: Semi+Storage [incl. SNDK] vs Official-IT vs Super-Tech + Sector-A1, 1.35x + V3)",
    pk_q, pk_t_tac2, pk_s, pk_er, pk_eb, grp_rk_raw, grp_rk_sh, sub_top1, win_pool_map=wp_tac2, a1_dedup_it_sector=True
)

pk_t_tac2b, wp_tac2b, _ = select_tech_arena(p_spx, POOLS_TAC1, sep_on_only_for_subpools=True, fallback_pool_name="2_Official_IT")
df_tac2b = sim_cleanroom_variant(
    "4. TAC-1_SEP_ON (SEP=ON 3-Pool Arena: Semi-4530 vs Official-IT vs Super-Tech, SEP=OFF Official-IT, 1.35x + V3)",
    pk_q, pk_t_tac2b, pk_s, pk_er, pk_eb, grp_rk_raw, grp_rk_sh, sub_top1, win_pool_map=wp_tac2b, a1_dedup_it_sector=True
)

# 5. TAC-3: 4-Subsector Disjoint Tech Arena (Semi [4530] vs Hardware/Storage [4520] vs Software [4510] vs Platform Giants)
POOLS_TAC3 = {
    "1_Semi_4530": lambda d: d["gics_4digit_group"] == "4530_Semiconductors_and_Equipment",
    "2_Hardware_Storage_4520": lambda d: d["gics_4digit_group"] == "4520_Tech_Hardware_and_Equipment",
    "3_Software_4510": lambda d: d["gics_4digit_group"] == "4510_Software_and_Services",
    "4_Platform_Giants": lambda d: d["ticker"].isin(PLATFORM_GIANTS),
}
pk_t_tac3, wp_tac3, _ = select_tech_arena(p_spx, POOLS_TAC3, sep_on_only_for_subpools=False)
df_tac3 = sim_cleanroom_variant(
    "5. TAC-3 (4-Cycle Disjoint Arena: Semi vs Hardware/Storage vs Software vs Platforms + Sector-A1, 1.35x + V3)",
    pk_q, pk_t_tac3, pk_s, pk_er, pk_eb, grp_rk_raw, grp_rk_sh, sub_top1, win_pool_map=wp_tac3, a1_dedup_it_sector=True
)

summary_df = pd.DataFrame([
    summarize_ledger(df_curr),
    summarize_ledger(df_tac1),
    summarize_ledger(df_tac1b),
    summarize_ledger(df_tac2),
    summarize_ledger(df_tac2b),
    summarize_ledger(df_tac3),
])

assert abs(summary_df.loc[0, "CAGR_214M"] - 0.649550) < 1e-4
assert abs(summary_df.loc[0, "Sharpe_214M"] - 1.48923) < 1e-3

summary_df.to_csv(os.path.join(OUT_DIR, "01_tech_arena_challenger_summary.csv"), index=False)

# Save month-by-month ledger comparison
ledger_cmp = pd.DataFrame({
    "ym": df_curr.index,
    "sep_on": df_curr["sep_on"].values,
    "curr_tech_pick": df_curr["t1"].values,
    "tac1_win_pool": df_tac1["win_tech_pool"].values,
    "tac1_tech_pick": df_tac1["t1"].values,
    "tac2_win_pool": df_tac2["win_tech_pool"].values,
    "tac2_tech_pick": df_tac2["t1"].values,
    "tac3_win_pool": df_tac3["win_tech_pool"].values,
    "tac3_tech_pick": df_tac3["t1"].values,
    "curr_net_ret": df_curr["net_ret"].values,
    "tac1_net_ret": df_tac1["net_ret"].values,
    "tac1b_net_ret": df_tac1b["net_ret"].values,
    "tac2_net_ret": df_tac2["net_ret"].values,
    "tac2b_net_ret": df_tac2b["net_ret"].values,
    "tac3_net_ret": df_tac3["net_ret"].values,
})
ledger_cmp.to_csv(os.path.join(OUT_DIR, "02_tech_arena_monthly_ledger.csv"), index=False)

print("=== TECH-ARENA CHALLENGER CLEAN-ROOM SUMMARY (2009-01..2026-10, 214M) ===")
for _, r in summary_df.iterrows():
    print(
        f"{r['Strategy']:95s}\n"
        f"  -> 214M CAGR: {r['CAGR_214M']*100:6.2f}% (213M: {r['CAGR_213M']*100:6.2f}%) | Sharpe: {r['Sharpe_214M']:5.3f} (213M: {r['Sharpe_213M']:5.3f}) | Vol: {r['Ann_Vol']*100:5.2f}%\n"
        f"  -> Monthly MaxDD: {r['Monthly_MaxDD']*100:6.2f}% | Hist Daily MaxDD: {r['Hist_Daily_MaxDD']*100:6.2f}% | 2026 Live Daily MaxDD: {r['Live_2026_Daily_MaxDD']*100:6.2f}% | MinMER: {r['MinMER']*100:5.2f}%\n"
        f"  -> Turnover: {r['Ann_TwoWay_Turnover']:5.2f}x/yr | 2018-19: {r['Ret_2018_2019_XLC_Split']*100:6.2f}% | 2022: {r['Ret_2022_RateHike_Bear']*100:6.2f}% | 2026 YTD: {r['Ret_2026_YTD_10M']*100:6.2f}% | 2026-10: {r['Ret_2026_10_SingleMonth']*100:6.2f}%\n"
        f"  -> Winning Pool Months: {r['Winning_Pool_Months']}\n"
    )
