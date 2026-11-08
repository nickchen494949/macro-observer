#!/usr/bin/env python3
"""
run_election_duration_consistency_audit.py
==========================================
Comprehensive Clean-Room Audit of:
  1. Event-Study Consistency & Reliability around US Elections (Pre-Election vs Election vs Post-Election):
     - Monthly windows: Sep (M-2), Oct (M-1 Pre-Election), Nov (M0 Election Month), Dec (M+1 Post-Election), Jan (M+2), Feb (M+3)
     - Daily windows around Election Day (T_elec):
       [T-20d..T-10d], [T-10d..T-5d], [T-5d..T_elec], [Oct31..T_elec],
       [T_elec..T+1d], [T_elec..T+3d], [T_elec..T+5d], [T_elec..T+10d], [T_elec..Nov30]
     - Evaluated across:
       (a) 2009-2026 (214M) on `Current (A1-RS 1.35x)` and `Tech-Arena Challenger (TAC-1_A1Sec)`
       (b) 1985-2026 (42 Years, 21 Elections: 11 Midterms + 10 Presidentials) on S&P 500 Constituent Momentum
  2. Pre-Election Avoidance Duration & Timing Optimization:
     - Monthly avoidance durations: Oct only, Nov only, Oct+Nov, Nov+Dec, Oct+Nov+Dec, Oct+Dec vs Frozen V3 (Dec only)
     - Sub-monthly / Daily avoidance durations around T_elec:
       [Oct31..T+1d], [T-5d..T+1d], [T-5d..T+3d], [T-5d..T+5d], [T-10d..T+1d], [T-10d..T+5d], [T-15d..T+1d]
  3. Post-Election Rerank Lookback Duration Optimization:
     - When reranking after the election (at Dec 31 close, Nov 30 close, or T_elec + k days),
       which momentum lookback duration is best and most consistent?
       Tests: `12-1M (252-21d)`, `12-0M (252d)`, `9-1M (189-21d)`, `6-1M (126-21d)`, `6-0M (126d)`,
              `3-1M (63-21d)`, `3-0M (63d)`, `1-0M (21d)`, and `Post-Election Drift (T_elec -> Rerank Date)`.
"""
import os
import sys
import numpy as np
import pandas as pd
from scipy import stats as sst

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
IN_DIR = os.path.join(ROOT, "outputs", "pure_momentum_1985_2026_audit", "inputs")
OUT_DIR = HERE
os.makedirs(OUT_DIR, exist_ok=True)

sys.path.insert(0, os.path.join(ROOT, "outputs", "pure_momentum_1985_2026_audit"))
import build_portable_inputs_from_raw as bpi

# -------------------------------------------------------------------------
# 1. Load Canonical 214M and 502M (1985-2026) Datasets
# -------------------------------------------------------------------------
p_spx = pd.read_parquet(os.path.join(IN_DIR, "v3_spx_panel_214m.parquet"))
p_ndx = pd.read_parquet(os.path.join(IN_DIR, "v3_ndx_panel_214m.parquet"))
reg_df = pd.read_csv(os.path.join(IN_DIR, "v3_regime_and_cash_214m.csv"))
p_502 = pd.read_parquet(os.path.join(IN_DIR, "panel_1985_2026_monthly.parquet"))
macro_502 = pd.read_csv(os.path.join(IN_DIR, "macro_and_cash_indices_monthly_1983_2026.csv"))

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

# Map formation date t -> holding month YYYY-MM
t_to_ym = {t: (t + pd.offsets.MonthBegin(1)).strftime("%Y-%m") for t in months_214}
ym_to_t = {ym: t for t, ym in t_to_ym.items()}

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

all_keys = [(s, y) for s, y in (set(p_spx["key"]) | set(p_ndx["key"])) if pd.notna(s) and pd.notna(y)]
df_s_cache = {}
for src, sym in all_keys:
    df_s_cache[(src, sym)] = bpi.load_fixed(src, sym)
cal = bpi.trading_calendar()

# -------------------------------------------------------------------------
# 2. Compute Alternative Momentum Lookbacks & Sub-Month Signals at Each t
# -------------------------------------------------------------------------
print("Computing multi-duration momentum signals (12-1M, 12-0M, 9-1M, 6-1M, 6-0M, 3-1M, 3-0M, 1-0M)...")
for panel in (p_spx, p_ndx):
    m_12_0, m_9_1, m_6_1, m_6_0, m_3_1, m_3_0, m_1_0 = [], [], [], [], [], [], []
    sh_12_0, sh_9_1, sh_6_1, sh_6_0, sh_3_1, sh_3_0, sh_1_0 = [], [], [], [], [], [], []
    for r in panel[["t", "src", "sym", "vol"]].itertuples(index=False):
        t_val, src, sym, v_val = r.t, r.src, r.sym, r.vol
        df_d = df_s_cache.get((src, sym)) if (pd.notna(src) and pd.notna(sym)) else None
        if df_d is None or df_d.empty:
            for lst in (m_12_0, m_9_1, m_6_1, m_6_0, m_3_1, m_3_0, m_1_0,
                        sh_12_0, sh_9_1, sh_6_1, sh_6_0, sh_3_1, sh_3_0, sh_1_0):
                lst.append(np.nan)
            continue
        c_sub = df_d.loc[:t_val, "c"]
        n = len(c_sub)
        v_safe = float(v_val) if (pd.notna(v_val) and v_val > 1e-6) else np.nan

        def _get_ret(lb_start, lb_end):
            if n > lb_start and lb_start > lb_end:
                p_end = float(c_sub.iloc[-1 - lb_end])
                p_st = float(c_sub.iloc[-1 - lb_start])
                if p_st > 0:
                    return p_end / p_st - 1.0
            return np.nan

        r12_0 = _get_ret(252, 0)
        r9_1 = _get_ret(189, 21)
        r6_1 = _get_ret(126, 21)
        r6_0 = _get_ret(126, 0)
        r3_1 = _get_ret(63, 21)
        r3_0 = _get_ret(63, 0)
        r1_0 = _get_ret(21, 0)

        m_12_0.append(r12_0); sh_12_0.append(r12_0 / v_safe if pd.notna(r12_0) and pd.notna(v_safe) else np.nan)
        m_9_1.append(r9_1);   sh_9_1.append(r9_1 / v_safe if pd.notna(r9_1) and pd.notna(v_safe) else np.nan)
        m_6_1.append(r6_1);   sh_6_1.append(r6_1 / v_safe if pd.notna(r6_1) and pd.notna(v_safe) else np.nan)
        m_6_0.append(r6_0);   sh_6_0.append(r6_0 / v_safe if pd.notna(r6_0) and pd.notna(v_safe) else np.nan)
        m_3_1.append(r3_1);   sh_3_1.append(r3_1 / v_safe if pd.notna(r3_1) and pd.notna(v_safe) else np.nan)
        m_3_0.append(r3_0);   sh_3_0.append(r3_0 / v_safe if pd.notna(r3_0) and pd.notna(v_safe) else np.nan)
        m_1_0.append(r1_0);   sh_1_0.append(r1_0 / v_safe if pd.notna(r1_0) and pd.notna(v_safe) else np.nan)

    panel["mom_12_0"] = m_12_0; panel["sharpe_12_0"] = sh_12_0
    panel["mom_9_1"] = m_9_1;   panel["sharpe_9_1"] = sh_9_1
    panel["mom_6_1"] = m_6_1;   panel["sharpe_6_1"] = sh_6_1
    panel["mom_6_0"] = m_6_0;   panel["sharpe_6_0"] = sh_6_0
    panel["mom_3_1"] = m_3_1;   panel["sharpe_3_1"] = sh_3_1
    panel["mom_3_0"] = m_3_0;   panel["sharpe_3_0"] = sh_3_0
    panel["mom_1_0"] = m_1_0;   panel["sharpe_1_0"] = sh_1_0

# Also compute Post-Election Drift from Election Day (early Nov) to Nov 30 and Dec 31
ELECTION_DATES_2009_2026 = {
    2010: pd.Timestamp("2010-11-02"),
    2012: pd.Timestamp("2012-11-06"),
    2014: pd.Timestamp("2014-11-04"),
    2016: pd.Timestamp("2016-11-08"),
    2018: pd.Timestamp("2018-11-06"),
    2020: pd.Timestamp("2020-11-03"),
    2022: pd.Timestamp("2022-11-08"),
    2024: pd.Timestamp("2024-11-05"),
    2026: pd.Timestamp("2026-11-03"),
}

for panel in (p_spx, p_ndx):
    post_elec_m, post_elec_sh = [], []
    for r in panel[["t", "src", "sym", "vol", "mom", "sharpe"]].itertuples(index=False):
        t_val, src, sym, v_val = r.t, r.src, r.sym, r.vol
        yr = t_val.year
        if yr in ELECTION_DATES_2009_2026 and t_val.month in (11, 12):
            t_el = ELECTION_DATES_2009_2026[yr]
            df_d = df_s_cache.get((src, sym)) if (pd.notna(src) and pd.notna(sym)) else None
            if df_d is not None and not df_d.empty:
                c_el = df_d.loc[:t_el, "c"]
                c_t = df_d.loc[:t_val, "c"]
                if len(c_el) > 0 and len(c_t) > 0 and float(c_el.iloc[-1]) > 0:
                    rel = float(c_t.iloc[-1] / c_el.iloc[-1] - 1.0)
                    v_safe = float(v_val) if (pd.notna(v_val) and v_val > 1e-6) else np.nan
                    post_elec_m.append(rel)
                    post_elec_sh.append(rel / v_safe if pd.notna(v_safe) else np.nan)
                    continue
        post_elec_m.append(r.mom)
        post_elec_sh.append(r.sharpe)
    panel["mom_post_elec"] = post_elec_m
    panel["sharpe_post_elec"] = post_elec_sh

# -------------------------------------------------------------------------
# 3. Selection Functions Supporting Custom Rerank Dates & Custom Lookback Signals
# -------------------------------------------------------------------------
PLATFORM_FINTECH_GIANTS = {
    "META", "GOOGL", "GOOG", "NFLX", "AMZN", "TSLA",
    "V", "MA", "PYPL", "CRM", "ADBE", "NOW", "INTU", "ORCL"
}

p_tech = p_spx[p_spx["clean_sector"] == "Information Technology"].copy()
p_exit = p_spx[p_spx["clean_sector"] != "Information Technology"].copy()
p_semi = p_tech[p_tech["gics_4digit_group"] == "4530_Semiconductors_and_Equipment"].copy()
p_super_tech = p_spx[
    (p_spx["clean_sector"] == "Information Technology") |
    (p_spx["ticker"].isin(PLATFORM_FINTECH_GIANTS))
].copy()

sec_rk_raw_gics, sec_rk_sh_gics, soxx_top1_gics = {}, {}, {}
for (t_val, sec_val), g in p_spx.groupby(["t", "clean_sector"], sort=True):
    gv = g[g["mom"].notna()]
    sr_r = gv.sort_values(["mom", "ticker"], ascending=[False, True]).reset_index(drop=True)
    sr_s = gv[gv["sharpe"].notna()].sort_values(["sharpe", "ticker"], ascending=[False, True]).reset_index(drop=True)
    for idx, tk in enumerate(sr_r["ticker"]):
        sec_rk_raw_gics[(t_val, tk)] = idx + 1
    for idx, tk in enumerate(sr_s["ticker"]):
        sec_rk_sh_gics[(t_val, tk)] = idx + 1
    if sec_val == "Information Technology":
        g_semi = gv[gv["gics_4digit_group"] == "4530_Semiconductors_and_Equipment"].sort_values(
            ["mom", "ticker"], ascending=[False, True]
        )
        if len(g_semi):
            soxx_top1_gics[t_val] = g_semi["ticker"].iloc[0]


def select_ndx_flex(panel, base_sig="sharpe", k=2, keep=5, reset_t_map=None):
    """
    reset_t_map: dict {t_val: sig_col_to_use_at_reset}
    If t_val is in reset_t_map, clears held=[] and ranks by reset_t_map[t_val].
    """
    reset_t_map = reset_t_map or {}
    held, out = [], {}
    for t_val, g_all in panel.groupby("t", sort=True):
        sig_col = reset_t_map.get(t_val, base_sig)
        if t_val in reset_t_map:
            held = []
        g = g_all[g_all[sig_col].notna()].sort_values([sig_col, "ticker"], ascending=[False, True]).reset_index(drop=True)
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


def select_spx_flex(panel, base_sig="mom", n_pick=1, hold_k=3, rs_col="rs_gics", thresh=-0.05, reset_t_map=None):
    reset_t_map = reset_t_map or {}
    held, out = [], {}
    for t_val, g_all in panel.groupby("t", sort=True):
        sig_col = reset_t_map.get(t_val, base_sig)
        if t_val in reset_t_map:
            held = []
        g = g_all[g_all[sig_col].notna()].sort_values([sig_col, "ticker"], ascending=[False, True]).reset_index(drop=True)
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


def select_bestsec_flex(df_exit_panel, base_sig="mom", rs_col="rs_gics", thresh=-0.05, reset_t_map=None):
    reset_t_map = reset_t_map or {}
    held_bs, out_bs = [], {}
    for t_val, g_all in df_exit_panel.groupby("t", sort=True):
        sig_col = reset_t_map.get(t_val, base_sig)
        if t_val in reset_t_map:
            held_bs = []
        g = g_all[g_all[sig_col].notna()].copy()
        sec_ew = g.groupby("clean_sector")[sig_col].mean().sort_values(ascending=False)
        top_sec = str(sec_ew.index[0])
        sec_rk = {s: i + 1 for i, s in enumerate(sec_ew.index)}
        g["sec_rk"] = g["clean_sector"].map(sec_rk)
        g_top = g[g["sec_rk"] == 1].sort_values([sig_col, "ticker"], ascending=[False, True])
        g_rest = g[g["sec_rk"] > 1].sort_values(["sec_rk", sig_col, "ticker"], ascending=[True, False, True])
        ranked = list(pd.concat([g_top, g_rest])["ticker"])
        rank = {x: i + 1 for i, x in enumerate(ranked)}
        rs_map = dict(zip(g["ticker"], g[rs_col])) if (rs_col and rs_col in g.columns) else {}
        kept = [
            x for x in held_bs
            if rank.get(x, 999) <= 3
            and (thresh is None or rank.get(x, 999) == 1 or rs_map.get(x, 0.0) >= thresh)
        ][:1]
        if not kept:
            kept = [ranked[0]]
        held_bs = list(kept)
        out_bs[t_val] = [kept[0], top_sec]
    return out_bs


def select_tech_arena_flex(base_sig="mom", reset_t_map=None):
    reset_t_map = reset_t_map or {}
    pools = {
        "1_Semi_4530": p_semi,
        "2_Official_IT": p_tech,
        "3_Super_Tech": p_super_tech,
    }
    pool_order = ["1_Semi_4530", "2_Official_IT", "3_Super_Tech"]
    out = {}
    for t_val in months_214:
        sig_col = reset_t_map.get(t_val, base_sig)
        scores = {}
        top_stock_per_pool = {}
        for p_name in pool_order:
            df_p = pools[p_name]
            g = df_p[(df_p["t"] == t_val) & (df_p[sig_col].notna())]
            if len(g) == 0:
                scores[p_name] = -999.0
                top_stock_per_pool[p_name] = None
            else:
                scores[p_name] = float(g[sig_col].mean())
                g_sorted = g.sort_values([sig_col, "ticker"], ascending=[False, True])
                top_stock_per_pool[p_name] = str(g_sorted["ticker"].iloc[0])
        best_pool = max(scores.keys(), key=lambda k: (scores[k], k))
        out[t_val] = [top_stock_per_pool[best_pool], best_pool]
    return out


def simulate_monthly(pk_q, pk_t, pk_s, pk_er, pk_eb, sgov_t_set=None, a1_mode="ticker", cost_bp=0.0010):
    sgov_t_set = sgov_t_set or set()
    it_tickers_by_t = {}
    for t_val, g in p_tech.groupby("t"):
        it_tickers_by_t[t_val] = set(g["ticker"])

    prev_drifted_w = {}
    rows = []
    for t in months_214:
        ym = t_to_ym[t]
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
        eb1 = pk_eb[t][0]

        if not sep_on:
            if a1_mode == "sector":
                s1 = er1 if ((t1 == s1_raw) or (s1_raw in it_tickers_by_t.get(t, set()))) else s1_raw
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
        is_soxx1 = (ov_tk != "") and (soxx_top1_gics.get(t, "") == ov_tk)
        sr_r = sec_rk_raw_gics.get((t, ov_tk), 99)
        sr_s = sec_rk_sh_gics.get((t, ov_tk), 99)
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
        if t in sgov_t_set:
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
                    L_mult = 1.35
                elif is_2leg and is_conf2:
                    L_mult = 1.20
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

        net_ret = (1.0 + gross_total) * ((1.0 - cost_bp) ** to) - 1.0 if to > 0 else gross_total
        end_eq = 1.0 + gross_total
        if end_eq > 0:
            prev_drifted_w = {tk: wt * (1.0 + ret_lk.get((t, tk), 0.0)) / end_eq for tk, wt in w_stocks.items() if wt > 0}
            if w_cash > 0:
                prev_drifted_w["SGOV"] = w_cash * (1.0 + r_cash) / end_eq
        else:
            prev_drifted_w = {}

        rows.append({
            "t": t,
            "ym": ym,
            "sep_on": sep_on,
            "lev": L_mult,
            "q1": q1, "q2": q2, "t1": t1, "s1": s1_raw, "er1": er1, "eb1": eb1,
            "w_stocks": dict(w_stocks),
            "w_cash": w_cash,
            "w_borrow": w_borrow,
            "net_ret": net_ret,
            "one_way_to": 0.5 * to,
            "target_w": dict(w_all_tradable),
        })
    return pd.DataFrame(rows)


def calc_summary_metrics(df_res):
    r214 = df_res["net_ret"].to_numpy(float)
    r213 = r214[:213]
    cagr_213 = float(np.prod(1.0 + r213) ** (12.0 / 213.0) - 1.0)
    cagr_214 = float(np.prod(1.0 + r214) ** (12.0 / 214.0) - 1.0)
    vol_214 = float(np.std(r214, ddof=1) * np.sqrt(12.0))
    ex213 = r213 - rf_213
    ex214 = r214 - rf_214
    sh_213 = float(np.mean(ex213) / np.std(ex213, ddof=1) * np.sqrt(12.0))
    sh_214 = float(np.mean(ex214) / np.std(ex214, ddof=1) * np.sqrt(12.0))
    nav = np.cumprod(1.0 + r214)
    peak = np.maximum.accumulate(np.insert(nav, 0, 1.0))[1:]
    mdd = float(np.min(nav / peak - 1.0))
    to_yr = float(df_res["one_way_to"].mean() * 24.0)
    return {
        "cagr_213_pct": round(cagr_213 * 100, 2),
        "cagr_214_pct": round(cagr_214 * 100, 2),
        "vol_214_pct": round(vol_214 * 100, 2),
        "sharpe_213": round(sh_213, 3),
        "sharpe_214": round(sh_214, 3),
        "mdd_monthly_pct": round(mdd * 100, 2),
        "turnover_2way_yr": round(to_yr, 2),
    }


# -------------------------------------------------------------------------
# MODULE 1: Event-Study Anatomy Around Elections (Monthly & Daily)
# -------------------------------------------------------------------------
print("Running Module 1: Monthly & Daily Event-Study Anatomy around Elections...")
# First run V0 (no election rule) for both Current and Tech-Arena so we see raw unmasked returns in every month!
pk_q_v0 = select_ndx_flex(p_ndx, "sharpe", 2, 5)
pk_t_cur_v0 = select_spx_flex(p_tech, "mom", 1, 1, None, None)
pk_t_tac_v0 = select_tech_arena_flex("mom")
pk_s_v0 = select_spx_flex(p_spx, "mom", 1, 3, "rs_gics", -0.05)
pk_er_v0 = select_spx_flex(p_exit, "mom", 1, 3, "rs_gics", -0.05)
pk_eb_v0 = select_bestsec_flex(p_exit, "mom", "rs_gics", -0.05)

df_cur_v0 = simulate_monthly(pk_q_v0, pk_t_cur_v0, pk_s_v0, pk_er_v0, pk_eb_v0, sgov_t_set=set(), a1_mode="ticker")
df_tac_v0 = simulate_monthly(pk_q_v0, pk_t_tac_v0, pk_s_v0, pk_er_v0, pk_eb_v0, sgov_t_set=set(), a1_mode="sector")

ym_ret_cur = dict(zip(df_cur_v0["ym"], df_cur_v0["net_ret"]))
ym_ret_tac = dict(zip(df_tac_v0["ym"], df_tac_v0["net_ret"]))

ELECTION_META = [
    {"year": 2010, "type": "Midterm",      "pre_gov": "Unified", "post_gov": "Divided", "regime_shift": "Unified->Divided", "elec_date": "2010-11-02"},
    {"year": 2012, "type": "Presidential", "pre_gov": "Divided", "post_gov": "Divided", "regime_shift": "Divided->Divided", "elec_date": "2012-11-06"},
    {"year": 2014, "type": "Midterm",      "pre_gov": "Divided", "post_gov": "Divided", "regime_shift": "Divided->Divided", "elec_date": "2014-11-04"},
    {"year": 2016, "type": "Presidential", "pre_gov": "Divided", "post_gov": "Unified", "regime_shift": "Divided->Unified", "elec_date": "2016-11-08"},
    {"year": 2018, "type": "Midterm",      "pre_gov": "Unified", "post_gov": "Divided", "regime_shift": "Unified->Divided", "elec_date": "2018-11-06"},
    {"year": 2020, "type": "Presidential", "pre_gov": "Divided", "post_gov": "Unified", "regime_shift": "Divided->Unified", "elec_date": "2020-11-03"},
    {"year": 2022, "type": "Midterm",      "pre_gov": "Unified", "post_gov": "Divided", "regime_shift": "Unified->Divided", "elec_date": "2022-11-08"},
    {"year": 2024, "type": "Presidential", "pre_gov": "Divided", "post_gov": "Unified", "regime_shift": "Divided->Unified", "elec_date": "2024-11-05"},
    {"year": 2026, "type": "Midterm",      "pre_gov": "Unified", "post_gov": "TBD",     "regime_shift": "Unified->TBD",     "elec_date": "2026-11-03"},
]

event_rows = []
for em in ELECTION_META:
    yr = em["year"]
    for strat_label, ym_map in [("Current_A1RS_V0", ym_ret_cur), ("TechArena_TAC1_V0", ym_ret_tac)]:
        r_sep = ym_map.get(f"{yr}-09", np.nan)
        r_oct = ym_map.get(f"{yr}-10", np.nan)
        r_nov = ym_map.get(f"{yr}-11", np.nan)
        r_dec = ym_map.get(f"{yr}-12", np.nan)
        r_jan = ym_map.get(f"{yr+1}-01", np.nan)
        r_feb = ym_map.get(f"{yr+1}-02", np.nan)
        event_rows.append({
            "strategy": strat_label,
            "election_year": yr,
            "type": em["type"],
            "pre_gov": em["pre_gov"],
            "regime_shift": em["regime_shift"],
            "Sep_M_minus_2_pct": round(r_sep * 100, 2) if pd.notna(r_sep) else np.nan,
            "Oct_M_minus_1_PreElec_pct": round(r_oct * 100, 2) if pd.notna(r_oct) else np.nan,
            "Nov_M0_ElecMonth_pct": round(r_nov * 100, 2) if pd.notna(r_nov) else np.nan,
            "Dec_M_plus_1_PostElec_pct": round(r_dec * 100, 2) if pd.notna(r_dec) else np.nan,
            "Jan_M_plus_2_NewYear_pct": round(r_jan * 100, 2) if pd.notna(r_jan) else np.nan,
            "Feb_M_plus_3_pct": round(r_feb * 100, 2) if pd.notna(r_feb) else np.nan,
        })

df_event_monthly = pd.DataFrame(event_rows)
df_event_monthly.to_csv(os.path.join(OUT_DIR, "01_election_monthly_event_study_2009_2026.csv"), index=False)

# Also build daily portfolio price path for Current_V0 so we can inspect exact daily windows around Election Day!
def build_daily_portfolio_series(df_res):
    W = 1.0
    pts_nav = {pd.Timestamp("2009-01-02"): 1.0}
    for row in df_res.itertuples():
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
            for tk, wv in h_dict.items():
                df_s = s_map[tk]
                c_d = float(df_s.loc[:d, "c"].iloc[-1]) if (df_s is not None and len(df_s.loc[:d])) else p_e_map[tk]
                rel = c_d / p_e_map[tk] if p_e_map[tk] > 0 else 1.0
                if d_i == 0:
                    v_rel_0[tk] = rel if rel > 0 else 1.0
                stock_mult = rel / v_rel_0[tk]
                pnl_c += wv * (stock_mult - 1.0)
            eq_rel = 1.0 + pnl_c
            pts_nav[d] = W * eq_rel

        W = W * (1.0 + float(row.net_ret))
        pts_nav[d1] = W

    s_nav = pd.Series(pts_nav).sort_index()
    s_nav = s_nav[~s_nav.index.duplicated(keep="last")]
    s_ret = s_nav.pct_change().fillna(0.0)
    return s_ret, s_nav

s_ret_cur_v0, s_nav_cur_v0 = build_daily_portfolio_series(df_cur_v0)
s_ret_tac_v0, s_nav_tac_v0 = build_daily_portfolio_series(df_tac_v0)

daily_win_rows = []
for em in ELECTION_META:
    yr = em["year"]
    if yr == 2026:
        continue
    t_el = pd.Timestamp(em["elec_date"])
    idx_el = s_nav_cur_v0.index.get_indexer([t_el], method="nearest")[0]
    for strat_label, s_nav in [("Current_A1RS_V0", s_nav_cur_v0), ("TechArena_TAC1_V0", s_nav_tac_v0)]:
        def _wret(off_start, off_end):
            i0 = max(0, min(len(s_nav) - 1, idx_el + off_start))
            i1 = max(0, min(len(s_nav) - 1, idx_el + off_end))
            return round((float(s_nav.iloc[i1] / s_nav.iloc[i0]) - 1.0) * 100, 2)

        # Also get Oct 31 to Election Day, and Election Day to Nov 30
        oct_end = s_nav.loc[:pd.Timestamp(f"{yr}-10-31")].index[-1]
        nov_end = s_nav.loc[:pd.Timestamp(f"{yr}-11-30")].index[-1]
        dec_end = s_nav.loc[:pd.Timestamp(f"{yr}-12-31")].index[-1]
        r_oct31_to_el = round((float(s_nav.loc[t_el] / s_nav.loc[oct_end]) - 1.0) * 100, 2)
        r_el_to_nov30 = round((float(s_nav.loc[nov_end] / s_nav.loc[t_el]) - 1.0) * 100, 2)
        r_nov30_to_dec31 = round((float(s_nav.loc[dec_end] / s_nav.loc[nov_end]) - 1.0) * 100, 2)

        daily_win_rows.append({
            "strategy": strat_label,
            "election_year": yr,
            "type": em["type"],
            "regime_shift": em["regime_shift"],
            "T_minus_20_to_T_minus_10_pct": _wret(-20, -10),
            "T_minus_10_to_T_minus_5_pct": _wret(-10, -5),
            "T_minus_5_to_T_elec_pct": _wret(-5, 0),
            "T_minus_10_to_T_elec_pct": _wret(-10, 0),
            "T_minus_20_to_T_elec_pct": _wret(-20, 0),
            "Oct31_to_T_elec_pct": r_oct31_to_el,
            "T_elec_to_T_plus_1_pct": _wret(0, 1),
            "T_elec_to_T_plus_3_pct": _wret(0, 3),
            "T_elec_to_T_plus_5_pct": _wret(0, 5),
            "T_elec_to_T_plus_10_pct": _wret(0, 10),
            "T_elec_to_Nov30_pct": r_el_to_nov30,
            "Nov30_to_Dec31_pct": r_nov30_to_dec31,
        })

df_event_daily = pd.DataFrame(daily_win_rows)
df_event_daily.to_csv(os.path.join(OUT_DIR, "02_election_daily_subwindows_2010_2024.csv"), index=False)

# -------------------------------------------------------------------------
# MODULE 1C: 42-Year (1985-2026, 21 Elections) Long-Term Consistency Check
# -------------------------------------------------------------------------
print("Running Module 1C: 42-Year (1985-2026, 21 Elections) Long-Term Consistency Check...")

def sim_pool_502(df_pool, col_score="mom_12_1", top_n=1, hold_b=1, ret_col="fwd_ret_stress"):
    out = {}
    held = []
    for ym, g in df_pool.groupby("hold_ym", sort=True):
        g_valid = g[g[col_score].notna() & g[ret_col].notna()].sort_values(
            [col_score, "ticker"], ascending=[False, True]
        ).reset_index(drop=True)
        if len(g_valid) == 0:
            continue
        rk_map = {tk: i + 1 for i, tk in enumerate(g_valid["ticker"])}
        ret_map = dict(zip(g_valid["ticker"], g_valid[ret_col]))
        kept = [tk for tk in held if rk_map.get(tk, 9999) <= hold_b][:top_n]
        for tk in g_valid["ticker"]:
            if len(kept) >= top_n:
                break
            if tk not in kept:
                kept.append(tk)
        held = list(kept)
        out[ym] = float(np.mean([ret_map[tk] for tk in held]))
    return out

p502_tech = p_502[p_502["clean_sector"] == "Information Technology"].copy()
ym_502_tech = sim_pool_502(p502_tech, "mom_12_1", 1, 1, "fwd_ret_stress")
ym_502_spy = sim_pool_502(p_502, "mom_12_1", 1, 3, "fwd_ret_stress")
ym_502_comp = {
    ym: 0.5 * ym_502_tech.get(ym, 0.0) + 0.5 * ym_502_spy.get(ym, 0.0)
    for ym in sorted(set(ym_502_tech.keys()) | set(ym_502_spy.keys()))
}

ELECTIONS_1985_2026 = [
    (1986, "Midterm",      "Divided", "Divided->Divided"),
    (1988, "Presidential", "Divided", "Divided->Divided"),
    (1990, "Midterm",      "Divided", "Divided->Divided"),
    (1992, "Presidential", "Divided", "Divided->Unified"),
    (1994, "Midterm",      "Unified", "Unified->Divided"),
    (1996, "Presidential", "Divided", "Divided->Divided"),
    (1998, "Midterm",      "Divided", "Divided->Divided"),
    (2000, "Presidential", "Divided", "Divided->Unified"),
    (2002, "Midterm",      "Divided", "Divided->Unified"),
    (2004, "Presidential", "Unified", "Unified->Unified"),
    (2006, "Midterm",      "Unified", "Unified->Divided"),
    (2008, "Presidential", "Divided", "Divided->Unified"),
    (2010, "Midterm",      "Unified", "Unified->Divided"),
    (2012, "Presidential", "Divided", "Divided->Divided"),
    (2014, "Midterm",      "Divided", "Divided->Divided"),
    (2016, "Presidential", "Divided", "Divided->Unified"),
    (2018, "Midterm",      "Unified", "Unified->Divided"),
    (2020, "Presidential", "Divided", "Divided->Unified"),
    (2022, "Midterm",      "Unified", "Unified->Divided"),
    (2024, "Presidential", "Divided", "Divided->Unified"),
    (2026, "Midterm",      "Unified", "Unified->TBD"),
]

lt_rows = []
for yr, etype, pre_g, shift in ELECTIONS_1985_2026:
    lt_rows.append({
        "year": yr,
        "type": etype,
        "pre_gov": pre_g,
        "regime_shift": shift,
        "Sep_pct": round(ym_502_comp.get(f"{yr}-09", np.nan) * 100, 2),
        "Oct_PreElec_pct": round(ym_502_comp.get(f"{yr}-10", np.nan) * 100, 2),
        "Nov_Elec_pct": round(ym_502_comp.get(f"{yr}-11", np.nan) * 100, 2) if f"{yr}-11" in ym_502_comp else np.nan,
        "Dec_PostElec_pct": round(ym_502_comp.get(f"{yr}-12", np.nan) * 100, 2) if f"{yr}-12" in ym_502_comp else np.nan,
        "Jan_NextYr_pct": round(ym_502_comp.get(f"{yr+1}-01", np.nan) * 100, 2) if f"{yr+1}-01" in ym_502_comp else np.nan,
    })
df_lt_42y = pd.DataFrame(lt_rows)
df_lt_42y.to_csv(os.path.join(OUT_DIR, "03_long_term_1985_2026_21_elections_consistency.csv"), index=False)

# -------------------------------------------------------------------------
# MODULE 2: Pre-Election vs Post-Election Avoidance Duration Matrix
# -------------------------------------------------------------------------
print("Running Module 2: Pre-Election & Post-Election Avoidance Duration Matrix...")

# Define election year sets for 3 Trigger Scopes:
# Scope 1: Unified_Pre_Midterm (2010, 2018, 2022, and 2026 for Oct) -> 100% ex-ante known before the election!
# Scope 2: All_Midterms (2010, 2014, 2018, 2022, 2026)
# Scope 3: All_Elections (2010, 2012, 2014, 2016, 2018, 2020, 2022, 2024, 2026)
SCOPES = {
    "Scope1_UnifiedMidterm": [2010, 2018, 2022, 2026],
    "Scope2_AllMidterms":    [2010, 2014, 2018, 2022, 2026],
    "Scope3_AllElections":   [2010, 2012, 2014, 2016, 2018, 2020, 2022, 2024, 2026],
}

def get_t_set(years, months_list):
    out = set()
    for y in years:
        for m in months_list:
            ym_str = f"{y+1}-01" if m == 13 else (f"{y+1}-02" if m == 14 else f"{y}-{m:02d}")
            if ym_str in ym_to_t:
                out.add(ym_to_t[ym_str])
    return out

AVOID_SPECS = [
    ("00_V0_NoAvoid_NoReset",        [],           []),
    ("01_Pre1M_AvoidOct_RerankNov",  [10],         [11]),
    ("02_Elec1M_AvoidNov_RerankDec", [11],         [12]),
    ("03_Post1M_V3_AvoidDec_RerankJan (Frozen V3)", [12], [13]),
    ("04_Pre2M_AvoidOctNov_RerankDec", [10, 11],   [12]),
    ("05_ElecPost2M_AvoidNovDec_RerankJan", [11, 12], [13]),
    ("06_All3M_AvoidOctNovDec_RerankJan", [10, 11, 12], [13]),
    ("07_Split_AvoidOctAndDec_KeepNov_RerankNovJan", [10, 12], [11, 13]),
    ("08_Post2M_V7_AvoidDecJan_RerankFeb", [12, 13], [14]),
    ("09_OnlyRerankNov_NoAvoid",     [],           [11]),
    ("10_OnlyRerankDec_NoAvoid",     [],           [12]),
    ("11_OnlyRerankJan_NoAvoid (V1)", [],          [13]),
]

avoid_rows = []
for strat_name, is_tac in [("Current_A1RS", False), ("TechArena_TAC1_A1Sec", True)]:
    for scope_name, yrs in SCOPES.items():
        for spec_name, avoid_m, reset_m in AVOID_SPECS:
            if spec_name == "00_V0_NoAvoid_NoReset" and scope_name != "Scope1_UnifiedMidterm":
                continue
            sgov_set = get_t_set(yrs, avoid_m)
            rst_set = get_t_set(yrs, reset_m)
            rst_map_q = {t: "sharpe" for t in rst_set}
            rst_map_s = {t: "mom" for t in rst_set}

            pk_q = select_ndx_flex(p_ndx, "sharpe", 2, 5, rst_map_q)
            pk_t = select_tech_arena_flex("mom", rst_map_s) if is_tac else select_spx_flex(p_tech, "mom", 1, 1, None, None, rst_map_s)
            pk_s = select_spx_flex(p_spx, "mom", 1, 3, "rs_gics", -0.05, rst_map_s)
            pk_er = select_spx_flex(p_exit, "mom", 1, 3, "rs_gics", -0.05, rst_map_s)
            pk_eb = select_bestsec_flex(p_exit, "mom", "rs_gics", -0.05, rst_map_s)

            df_sim = simulate_monthly(
                pk_q, pk_t, pk_s, pk_er, pk_eb,
                sgov_t_set=sgov_set,
                a1_mode=("sector" if is_tac else "ticker")
            )
            m = calc_summary_metrics(df_sim)
            m["strategy"] = strat_name
            m["trigger_scope"] = scope_name
            m["avoid_duration_spec"] = spec_name
            m["n_months_avoided"] = len(sgov_set)
            avoid_rows.append(m)

df_avoid_matrix = pd.DataFrame(avoid_rows)
cols_front = ["strategy", "trigger_scope", "avoid_duration_spec", "n_months_avoided", "cagr_213_pct", "cagr_214_pct", "sharpe_213", "sharpe_214", "mdd_monthly_pct", "turnover_2way_yr"]
df_avoid_matrix = df_avoid_matrix[cols_front]
df_avoid_matrix.to_csv(os.path.join(OUT_DIR, "04_avoidance_duration_and_timing_matrix.csv"), index=False)

# -------------------------------------------------------------------------
# MODULE 3: Post-Election Rerank Lookback Duration Optimization
# -------------------------------------------------------------------------
print("Running Module 3: Post-Election Rerank Lookback Duration Optimization...")
LOOKBACK_SPECS = [
    ("12-1M (252d ex 21d, Standard)", "mom",           "sharpe"),
    ("12-0M (252d inc last 1M)",      "mom_12_0",      "sharpe_12_0"),
    ("9-1M (189d ex 21d)",            "mom_9_1",       "sharpe_9_1"),
    ("6-1M (126d ex 21d)",            "mom_6_1",       "sharpe_6_1"),
    ("6-0M (126d inc last 1M)",       "mom_6_0",       "sharpe_6_0"),
    ("3-1M (63d ex 21d)",             "mom_3_1",       "sharpe_3_1"),
    ("3-0M (63d inc last 1M)",        "mom_3_0",       "sharpe_3_0"),
    ("1-0M (21d Post-Elec 1M)",       "mom_1_0",       "sharpe_1_0"),
    ("Post-Elec Drift (T_elec->t)",   "mom_post_elec", "sharpe_post_elec"),
]

# Test lookback durations at two rerank timings:
#   Timing A: V3 Standard (Avoid Dec, Rerank at Dec 31 for Jan)
#   Timing B: Avoid Nov, Rerank at Nov 30 for Dec
#   Timing C: Split Avoid Oct+Dec, Rerank at Nov & Jan
RERANK_TIMINGS = [
    ("TimingA_V3_AvoidDec_RerankJan",      [2010, 2018, 2022], [12], [13]),
    ("TimingB_AvoidNov_RerankDec",         [2010, 2018, 2022], [11], [12]),
    ("TimingC_AllElections_RerankDec",     [2010, 2012, 2014, 2016, 2018, 2020, 2022, 2024], [], [12]),
    ("TimingD_AllElections_RerankJan",     [2010, 2012, 2014, 2016, 2018, 2020, 2022, 2024], [], [13]),
]

lb_rows = []
for strat_name, is_tac in [("Current_A1RS", False), ("TechArena_TAC1_A1Sec", True)]:
    for timing_name, yrs, avoid_m, reset_m in RERANK_TIMINGS:
        sgov_set = get_t_set(yrs, avoid_m)
        rst_set = get_t_set(yrs, reset_m)
        for lb_label, m_col, sh_col in LOOKBACK_SPECS:
            rst_map_q = {t: sh_col for t in rst_set}
            rst_map_s = {t: m_col for t in rst_set}

            pk_q = select_ndx_flex(p_ndx, "sharpe", 2, 5, rst_map_q)
            pk_t = select_tech_arena_flex("mom", rst_map_s) if is_tac else select_spx_flex(p_tech, "mom", 1, 1, None, None, rst_map_s)
            pk_s = select_spx_flex(p_spx, "mom", 1, 3, "rs_gics", -0.05, rst_map_s)
            pk_er = select_spx_flex(p_exit, "mom", 1, 3, "rs_gics", -0.05, rst_map_s)
            pk_eb = select_bestsec_flex(p_exit, "mom", "rs_gics", -0.05, rst_map_s)

            df_sim = simulate_monthly(
                pk_q, pk_t, pk_s, pk_er, pk_eb,
                sgov_t_set=sgov_set,
                a1_mode=("sector" if is_tac else "ticker")
            )
            m = calc_summary_metrics(df_sim)
            ym_ret = dict(zip(df_sim["ym"], df_sim["net_ret"]))
            # Record post-rerank month returns for the 3 Unified->Divided cycles
            if 13 in reset_m:
                r_p1, r_p2, r_p3 = ym_ret["2011-01"], ym_ret["2019-01"], ym_ret["2023-01"]
            else:
                r_p1, r_p2, r_p3 = ym_ret["2010-12"], ym_ret["2018-12"], ym_ret["2022-12"]

            lb_rows.append({
                "strategy": strat_name,
                "rerank_timing": timing_name,
                "rerank_lookback_duration": lb_label,
                "cagr_213_pct": m["cagr_213_pct"],
                "cagr_214_pct": m["cagr_214_pct"],
                "sharpe_213": m["sharpe_213"],
                "sharpe_214": m["sharpe_214"],
                "mdd_monthly_pct": m["mdd_monthly_pct"],
                "cycle_2010_post_rerank_pct": round(r_p1 * 100, 2),
                "cycle_2018_post_rerank_pct": round(r_p2 * 100, 2),
                "cycle_2022_post_rerank_pct": round(r_p3 * 100, 2),
                "mean_3cycle_post_rerank_pct": round(np.mean([r_p1, r_p2, r_p3]) * 100, 2),
            })

df_lb_matrix = pd.DataFrame(lb_rows)
df_lb_matrix.to_csv(os.path.join(OUT_DIR, "05_post_election_rerank_lookback_duration_matrix.csv"), index=False)

print("\n=== MODULE 1A: 2009-2026 Monthly Event Study (Current_A1RS_V0) ===")
print(df_event_monthly[df_event_monthly["strategy"] == "Current_A1RS_V0"].to_string(index=False))

print("\n=== MODULE 1B: 2010-2024 Daily Sub-Windows Around Election Day (Current_A1RS_V0) ===")
print(df_event_daily[df_event_daily["strategy"] == "Current_A1RS_V0"].to_string(index=False))

print("\n=== MODULE 2: Avoidance Duration & Timing Matrix (Scope1_UnifiedMidterm & Scope2_AllMidterms) ===")
print(df_avoid_matrix[df_avoid_matrix["trigger_scope"].isin(["Scope1_UnifiedMidterm", "Scope2_AllMidterms"])].to_string(index=False))

print("\n=== MODULE 3: Post-Election Rerank Lookback Duration Matrix (TimingA & TimingB) ===")
print(df_lb_matrix[df_lb_matrix["rerank_timing"].isin(["TimingA_V3_AvoidDec_RerankJan", "TimingB_AvoidNov_RerankDec"])].to_string(index=False))
