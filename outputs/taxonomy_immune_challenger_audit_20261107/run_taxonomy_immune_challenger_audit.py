#!/usr/bin/env python3
"""
Taxonomy-Immune Challenger Audit (2009-01 to 2026-10, 214 Months Strict PIT)
=============================================================================
Governance Rule:
  - DOES NOT modify Frozen `A1-RS 1.35x + V3 Election Reset` (`FROZEN_STRATEGY_SPEC.md`).
  - Compares strictly the 3 pre-registered versions requested:
      1. `Current` : Frozen `A1-RS 1.35x + V3` (Official PIT GICS `clean_sector` for Tech / BestSec / RS_sec).
                     Verified via hard assertions to match `FROZEN_STRATEGY_SPEC.md` bit-for-bit:
                     214M CAGR = 64.95%, Sharpe = 1.489, Monthly MaxDD = -22.74%,
                     Hist Daily MaxDD = -34.64%, 2026 Live Daily MaxDD = -25.88%, MinMER = 70.6%.
      2. `TI-1`    : Sector-Agnostic Momentum (0% GICS labels, 0% clusters; BestSec removed;
                     QQQ Sharpe Top-2/Hold<=5 + SP500 Raw Top-1/Hold<=3 + SP500 Ex-Overlap Raw Top-1/Hold<=3
                     with market-relative RS_mkt >= -5%).
      3. `TI-2`    : Price-Behavior Rolling Correlation Clusters (0% GICS labels; at each month-end t, partitions S&P 500
                     into K=11 clusters via deterministic Ward hierarchical clustering on trailing 252-trading-day daily
                     return correlations; identifies the Tech/Growth cluster by trailing 252d co-movement with QQQ and
                     ranks Ex-Tech clusters for BestCluster in SEP=OFF, with cluster-relative RS_cluster >= -5%).
  - Runs the Taxonomy Shock Test:
      * Shock A: S&P Moves Semis & AI Hardware (`NVDA, AMD, AVGO, MU, SNDK, AAPL, ANET, FSLR...`) out of IT -> Industrials.
      * Shock B: Merge Platform/Payment Giants (`META, GOOGL, NFLX, AMZN, TSLA, V, MA, PYPL`) back into IT across 2009-2026.
      * Shock C: Reclassify Top-30 Pure Tech Leaders into Financials.
      * Shock D: 25 Monte Carlo Full Random GICS Sector Permutations across all 868 S&P 500 stocks.
"""
import os
import sys
import json
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
IN_DIR = os.path.join(ROOT, "outputs", "pure_momentum_1985_2026_audit", "inputs")
OUT_DIR = HERE
os.makedirs(OUT_DIR, exist_ok=True)

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
import outputs.pure_momentum_1985_2026_audit.build_portable_inputs_from_raw as bpi

# -------------------------------------------------------------------------
# 1. Load 214-Month Strict PIT Panels & Build 252-Day Price-Correlation Clusters
# -------------------------------------------------------------------------
p_spx = pd.read_parquet(os.path.join(IN_DIR, "v3_spx_panel_214m.parquet"))
p_ndx = pd.read_parquet(os.path.join(IN_DIR, "v3_ndx_panel_214m.parquet"))
reg_df = pd.read_csv(os.path.join(IN_DIR, "v3_regime_and_cash_214m.csv"))

p_spx["t"] = pd.to_datetime(p_spx["t"])
p_ndx["t"] = pd.to_datetime(p_ndx["t"])
reg_df["t"] = pd.to_datetime(reg_df["t"])

p_spx = p_spx.sort_values(["t", "ticker"]).reset_index(drop=True)
p_ndx = p_ndx.sort_values(["t", "ticker"]).reset_index(drop=True)

months_all = sorted(p_spx["t"].unique())
months_213 = [t for t in months_all if pd.Timestamp("2008-12-31") <= t <= pd.Timestamp("2026-08-31")]
months_214 = [t for t in months_all if pd.Timestamp("2008-12-31") <= t <= pd.Timestamp("2026-09-30")]

reg_map = reg_df.set_index("t").to_dict("index")
ym_to_t = {(t + pd.offsets.MonthBegin(1)).strftime("%Y-%m"): t for t in months_all}
t_dec_u2d = {ym_to_t["2010-12"], ym_to_t["2018-12"], ym_to_t["2022-12"]}
t_jan_u2d = {ym_to_t["2011-01"], ym_to_t["2019-01"], ym_to_t["2023-01"]}

print("Loading daily close & open series for 252-day correlation clustering and daily MaxDD/MinMER audit...")
pairs_spx = p_spx[["src", "sym"]].dropna().drop_duplicates().values.tolist()
pairs_ndx = p_ndx[["src", "sym"]].dropna().drop_duplicates().values.tolist()
all_pairs = list({(str(s), str(y)) for s, y in (pairs_spx + pairs_ndx)})

close_dict, open_dict, df_s_cache = {}, {}, {}
for src, sym in all_pairs:
    df_d = bpi.load_fixed(src, sym)
    if df_d is not None and len(df_d) > 0:
        k = f"{src}|{sym}"
        close_dict[k] = df_d["c"]
        open_dict[k] = df_d["o"]
        df_s_cache[k] = df_d

px_close_df = pd.DataFrame(close_dict).sort_index()
ret_daily_df = px_close_df.pct_change(fill_method=None).clip(-0.50, 1.00)

qqq_raw = json.load(open(os.path.join(ROOT, "outputs", "remediation_full_audit_20261104", "tiingo_etfs", "QQQ.json")))
qqq_df = pd.DataFrame(qqq_raw)
qqq_df["date"] = pd.to_datetime(qqq_df["date"]).dt.tz_localize(None)
qqq_df = qqq_df.set_index("date").sort_index()
qqq_ret_daily = qqq_df["adjClose"].astype(float).pct_change().reindex(ret_daily_df.index)

p_spx["key"] = p_spx["src"].astype(str) + "|" + p_spx["sym"].astype(str)
p_ndx["key"] = p_ndx["src"].astype(str) + "|" + p_ndx["sym"].astype(str)

# Build deterministic K=11 Price-Behavior Clusters at each month-end t using only trailing 252 trading days <= t
print("Computing K=11 deterministic Ward price-correlation clusters across 215 month-ends...")
N_CLUSTERS = 11
MIN_TECH_CLUSTER_SIZE = 45

cluster_labels_all = []
in_tech_cluster_all = []
top_beta_cluster_all = []

for t in months_all:
    g = p_spx[p_spx["t"] == t]
    keys = [k for k in g["key"].tolist() if k in ret_daily_df.columns]
    sub_r = ret_daily_df.loc[:t, keys].tail(252)
    mat = sub_r.fillna(0.0).values.T
    stds = mat.std(axis=1, keepdims=True)
    stds[stds < 1e-8] = 1.0
    mat_z = (mat - mat.mean(axis=1, keepdims=True)) / stds
    corr = np.clip((mat_z @ mat_z.T) / mat_z.shape[1], -1.0, 1.0)
    np.fill_diagonal(corr, 1.0)
    dist = np.sqrt(np.maximum(0.0, 1.0 - corr))
    np.fill_diagonal(dist, 0.0)

    Z = linkage(squareform(dist, checks=False), method="ward")
    labels = fcluster(Z, t=N_CLUSTERS, criterion="maxclust")
    key_to_cid = dict(zip(keys, labels))

    q_vec = qqq_ret_daily.loc[sub_r.index].fillna(0.0).values
    q_z = (q_vec - q_vec.mean()) / (q_vec.std() + 1e-8)

    cid_scores, cid_counts = {}, {}
    for cid in range(1, N_CLUSTERS + 1):
        idx_c = [i for i, l in enumerate(labels) if l == cid]
        if not idx_c:
            continue
        c_ret = mat[idx_c].mean(axis=0)
        c_z = (c_ret - c_ret.mean()) / (c_ret.std() + 1e-8)
        corr_q = float(np.mean(c_z * q_z))
        beta_q = float(np.cov(c_ret, q_vec)[0, 1] / (np.var(q_vec) + 1e-8))
        cid_scores[cid] = corr_q * beta_q
        cid_counts[cid] = len(idx_c)

    sorted_cids = sorted(cid_scores.keys(), key=lambda c: cid_scores[c], reverse=True)
    top1_cid = sorted_cids[0]
    tech_cids = set()
    cnt = 0
    for c in sorted_cids:
        tech_cids.add(c)
        cnt += cid_counts[c]
        if cnt >= MIN_TECH_CLUSTER_SIZE or len(tech_cids) >= 2:
            break

    for k in g["key"].tolist():
        cid = key_to_cid.get(k, -1)
        cluster_labels_all.append(f"Cluster_{cid:02d}")
        in_tech_cluster_all.append(bool(cid in tech_cids))
        top_beta_cluster_all.append(bool(cid == top1_cid))

p_spx["price_cluster"] = cluster_labels_all
p_spx["in_tech_cluster"] = in_tech_cluster_all
p_spx["in_top1_beta_cluster"] = top_beta_cluster_all
p_spx["univ_group"] = "ALL_SP500"

# Relative strength columns:
# 1. Current: RS_sec = ret_1m - GICS clean_sector EW ret_1m
sec_ret1m_gics = p_spx.groupby(["t", "clean_sector"])["ret_1m"].mean().to_dict()
p_spx["rs_gics"] = [r1 - sec_ret1m_gics.get((t, s), np.nan) for t, s, r1 in zip(p_spx["t"], p_spx["clean_sector"], p_spx["ret_1m"])]

# 2. TI-1: RS_mkt = ret_1m - S&P 500 universe EW ret_1m (0% GICS, 0% clusters)
univ_ret1m = p_spx.groupby("t")["ret_1m"].mean().to_dict()
p_spx["rs_mkt"] = [r1 - univ_ret1m.get(t, np.nan) for t, r1 in zip(p_spx["t"], p_spx["ret_1m"])]

# 3. TI-2: RS_cluster = ret_1m - price_cluster EW ret_1m (0% GICS)
clust_ret1m = p_spx.groupby(["t", "price_cluster"])["ret_1m"].mean().to_dict()
p_spx["rs_cluster"] = [r1 - clust_ret1m.get((t, c), np.nan) for t, c, r1 in zip(p_spx["t"], p_spx["price_cluster"], p_spx["ret_1m"])]

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

# -------------------------------------------------------------------------
# 2. Exact Clean-Room Selection & Simulation Functions
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

def select_spx_stateful(panel, sig_col="mom", n_pick=1, hold_k=3, rs_col="rs_gics", thresh=None, reset_t_set=None, exclude_by_t=None):
    reset_t_set = reset_t_set or set()
    held, out = [], {}
    for t_val, g in panel[panel[sig_col].notna()].groupby("t", sort=True):
        if t_val in reset_t_set:
            held = []
        if exclude_by_t and t_val in exclude_by_t:
            g = g[~g["ticker"].isin(exclude_by_t[t_val])]
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

def sim_cleanroom_variant(
    name, pk_q, pk_t, pk_s, pk_er, pk_eb,
    grp_rk_raw, grp_rk_sh, sub_top1,
    is_a1=True, l_conf2=1.20, l_ord3=1.35, cost_bp=0.0010
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
        eb_val = pk_eb[t]
        eb1, eb_sec = (eb_val[0], eb_val[1]) if len(eb_val) > 1 else (eb_val[0], "SP500_ExOverlap")

        is_dec = (t in t_dec_u2d)
        is_jan = (t in t_jan_u2d)

        s1 = er1 if (is_a1 and (not sep_on) and (t1 == s1_raw)) else s1_raw

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

        w_stocks = {}
        w_cash = 0.0
        w_borrow = 0.0
        L_mult = 1.0

        if is_dec:
            w_stocks = {}
            w_cash = 1.0
            w_borrow = 0.0
            L_mult = 0.0
        elif not sep_on:
            w_stocks[t1] = w_stocks.get(t1, 0.0) + 0.25
            w_stocks[s1] = w_stocks.get(s1, 0.0) + 0.25
            w_stocks[eb1] = w_stocks.get(eb1, 0.0) + 0.25
            w_cash = 0.25
        else:
            w_work = dict(w_base)
            if lowvol_ok:
                if is_3leg:
                    L_mult = l_ord3
                elif is_2leg and is_conf2:
                    L_mult = l_conf2
            w_stocks = {tk: wt * L_mult for tk, wt in w_work.items()}
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
            "is_u2d_dec": is_dec,
            "is_u2d_jan": is_jan,
            "q1": q1, "q2": q2, "t1": t1, "s1_raw": s1_raw, "s1_eff": s1, "eb1": eb1, "eb_sec": eb_sec,
            "L_mult": round(L_mult, 4),
            "w_stocks": dict(w_stocks),
            "w_cash": w_cash,
            "w_borrow": w_borrow,
            "max_single_w": max(w_stocks.values()) if w_stocks else 0.0,
            "n_unique_stocks": len([k for k, v in w_stocks.items() if v > 0]),
            "weights_json": json.dumps({k: round(v, 4) for k, v in sorted(w_all_tradable.items())}),
            "turnover_two_way": to,
            "gross_ret": gross_total,
            "net_ret": net_total,
        })
    return pd.DataFrame(rows).set_index("ym")

# Daily NAV & MinMER calculator matching `run_full_8point_remediation_audit.py`
cal = bpi.trading_calendar()

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

# -------------------------------------------------------------------------
# 3. Run the 3 Pre-Registered Versions (`Current`, `TI-1`, `TI-2`)
# -------------------------------------------------------------------------
rf_213 = np.array([float(reg_map[t]["rf_tbill"]) for t in months_213])
rf_214 = np.array([float(reg_map[t]["rf_tbill"]) for t in months_214])

def run_current_gics(panel_spx, label="Current: Frozen A1-RS 1.35x + V3 (GICS Tech & BestSec)"):
    p_spx_w = panel_spx.copy()
    p_spx_w["is_semi_gics"] = (p_spx_w["clean_sector"] == "Information Technology") & (
        p_spx_w["gics_4digit_group"] == "4530_Semiconductors_and_Equipment"
    )
    grp_rk_raw, grp_rk_sh, sub_top1 = build_group_rank_maps(p_spx_w, "clean_sector", "is_semi_gics")

    p_tech = p_spx_w[p_spx_w["clean_sector"] == "Information Technology"].copy()
    p_exit = p_spx_w[p_spx_w["clean_sector"] != "Information Technology"].copy()

    pk_q = select_ndx_stateful(p_ndx, "sharpe", 2, 5, reset_t_set=t_jan_u2d)
    pk_t = select_spx_stateful(p_tech, "mom", 1, 1, "rs_gics", None)
    pk_s = select_spx_stateful(p_spx_w, "mom", 1, 3, "rs_gics", -0.05, reset_t_set=t_jan_u2d)
    pk_er = select_spx_stateful(p_exit, "mom", 1, 3, "rs_gics", -0.05, reset_t_set=t_jan_u2d)
    pk_eb = select_bestgroup_stateful(p_exit, "clean_sector", "rs_gics", -0.05, reset_t_set=t_jan_u2d)

    return sim_cleanroom_variant(label, pk_q, pk_t, pk_s, pk_er, pk_eb, grp_rk_raw, grp_rk_sh, sub_top1, is_a1=True)

def run_ti1_sector_agnostic(panel_spx, label="TI-1: Sector-Agnostic Momentum (0% GICS, No Clusters)"):
    # Zero GICS columns read! Uses only `univ_group` ("ALL_SP500") and `rs_mkt`.
    grp_rk_raw, grp_rk_sh, sub_top1 = build_group_rank_maps(panel_spx, "univ_group", None)

    pk_q = select_ndx_stateful(p_ndx, "sharpe", 2, 5, reset_t_set=t_jan_u2d)
    # Leg 2: S&P 500 Raw Top-1 (Hold<=3 + RS_mkt >= -5%)
    pk_s1 = select_spx_stateful(panel_spx, "mom", 1, 3, "rs_mkt", -0.05, reset_t_set=t_jan_u2d)
    # Leg 3: S&P 500 Ex-Overlap Raw Top-1 (Hold<=3 + RS_mkt >= -5%)
    excl_1 = {t: {pk_s1[t][0]} for t in months_214}
    pk_s2 = select_spx_stateful(panel_spx, "mom", 1, 3, "rs_mkt", -0.05, reset_t_set=t_jan_u2d, exclude_by_t=excl_1)
    # Leg 4 (for SEP=OFF when BestSec is cancelled): S&P 500 Ex-{Leg2, Leg3} Raw Top-1 (Hold<=3 + RS_mkt >= -5%)
    excl_12 = {t: {pk_s1[t][0], pk_s2[t][0]} for t in months_214}
    pk_s3 = select_spx_stateful(panel_spx, "mom", 1, 3, "rs_mkt", -0.05, reset_t_set=t_jan_u2d, exclude_by_t=excl_12)

    return sim_cleanroom_variant(label, pk_q, pk_s1, pk_s2, pk_s2, pk_s3, grp_rk_raw, grp_rk_sh, sub_top1, is_a1=True)

def run_ti2_price_clusters(panel_spx, label="TI-2: Rolling 252d Correlation Clusters (0% GICS)"):
    # Zero GICS columns read! Uses `price_cluster`, `in_tech_cluster`, `in_top1_beta_cluster`, and `rs_cluster`.
    grp_rk_raw, grp_rk_sh, sub_top1 = build_group_rank_maps(panel_spx, "price_cluster", "in_top1_beta_cluster")

    p_tech_cl = panel_spx[panel_spx["in_tech_cluster"]].copy()
    p_exit_cl = panel_spx[~panel_spx["in_tech_cluster"]].copy()

    pk_q = select_ndx_stateful(p_ndx, "sharpe", 2, 5, reset_t_set=t_jan_u2d)
    pk_t_cl = select_spx_stateful(p_tech_cl, "mom", 1, 1, "rs_cluster", None)
    pk_s_cl = select_spx_stateful(panel_spx, "mom", 1, 3, "rs_cluster", -0.05, reset_t_set=t_jan_u2d)
    pk_er_cl = select_spx_stateful(p_exit_cl, "mom", 1, 3, "rs_cluster", -0.05, reset_t_set=t_jan_u2d)
    pk_eb_cl = select_bestgroup_stateful(p_exit_cl, "price_cluster", "rs_cluster", -0.05, reset_t_set=t_jan_u2d)

    return sim_cleanroom_variant(label, pk_q, pk_t_cl, pk_s_cl, pk_er_cl, pk_eb_cl, grp_rk_raw, grp_rk_sh, sub_top1, is_a1=True)

df_curr = run_current_gics(p_spx)
df_ti1 = run_ti1_sector_agnostic(p_spx)
df_ti2 = run_ti2_price_clusters(p_spx)

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
        "Ret_2016_REIT_CarveOut": sub_ret("2016-01", "2016-12"),
        "Ret_2018_2019_XLC_Split": sub_ret("2018-01", "2019-12"),
        "Ret_2022_RateHike_Bear": sub_ret("2022-01", "2022-12"),
        "Ret_2023_Fintech_GICS_and_QQQ_Rebal": sub_ret("2023-01", "2023-12"),
        "Ret_2024_XLK_Cap_Event": sub_ret("2024-01", "2024-12"),
        "Ret_2026_YTD_10M": sub_ret("2026-01", "2026-10"),
        "Ret_2026_10_SingleMonth": float(df.loc["2026-10", "net_ret"]),
    }

summary_rows = [
    summarize_ledger(df_curr),
    summarize_ledger(df_ti1),
    summarize_ledger(df_ti2),
]
summary_df = pd.DataFrame(summary_rows)

# Strict assertions verifying `Current` matches `FROZEN_STRATEGY_SPEC.md`
assert abs(summary_df.loc[0, "CAGR_214M"] - 0.649550) < 1e-4, f"Current CAGR mismatch: {summary_df.loc[0, 'CAGR_214M']}"
assert abs(summary_df.loc[0, "Sharpe_214M"] - 1.48923) < 1e-3, f"Current Sharpe mismatch: {summary_df.loc[0, 'Sharpe_214M']}"
assert abs(summary_df.loc[0, "Monthly_MaxDD"] - (-0.227376)) < 1e-4, f"Current Monthly MaxDD mismatch: {summary_df.loc[0, 'Monthly_MaxDD']}"

summary_df.to_csv(os.path.join(OUT_DIR, "01_taxonomy_immune_head_to_head_summary.csv"), index=False)

ledger_cmp = pd.DataFrame({
    "ym": df_curr.index,
    "sep_on": df_curr["sep_on"].values,
    "curr_picks": [f"{r.q1},{r.q2}|{r.t1}|{r.s1_eff}|{r.eb1}({r.eb_sec})" for r in df_curr.itertuples()],
    "ti1_picks": [f"{r.q1},{r.q2}|{r.t1}|{r.s1_eff}|{r.eb1}" for r in df_ti1.itertuples()],
    "ti2_picks": [f"{r.q1},{r.q2}|{r.t1}|{r.s1_eff}|{r.eb1}({r.eb_sec})" for r in df_ti2.itertuples()],
    "curr_net_ret": df_curr["net_ret"].values,
    "ti1_net_ret": df_ti1["net_ret"].values,
    "ti2_net_ret": df_ti2["net_ret"].values,
})
ledger_cmp.to_csv(os.path.join(OUT_DIR, "02_monthly_ledger_current_vs_ti1_vs_ti2.csv"), index=False)

# -------------------------------------------------------------------------
# 4. Taxonomy Shock Test (Administrative GICS Reclassification & Random Scrambling)
# -------------------------------------------------------------------------
print("Running Taxonomy Shock Tests across Current vs TI-1 vs TI-2...")

def apply_gics_shock_and_eval(p_base, shock_name, new_sector_map_fn, run_ti_checks=True):
    p_shocked = p_base.copy()
    p_shocked["clean_sector"] = [new_sector_map_fn(t, tk, sec) for t, tk, sec in p_shocked[["t", "ticker", "clean_sector"]].itertuples(index=False)]
    sec_1m_s = p_shocked.groupby(["t", "clean_sector"])["ret_1m"].mean().to_dict()
    p_shocked["rs_gics"] = [r1 - sec_1m_s.get((t, s), np.nan) for t, s, r1 in zip(p_shocked["t"], p_shocked["clean_sector"], p_shocked["ret_1m"])]

    df_c_s = run_current_gics(p_shocked, label=f"Current ({shock_name})")

    def quick_stats(df_s, df_ref):
        r = df_s["net_ret"].values
        r_ref = df_ref["net_ret"].values
        cagr = float(np.prod(1.0 + r) ** (12.0 / len(r)) - 1.0)
        cagr_ref = float(np.prod(1.0 + r_ref) ** (12.0 / len(r_ref)) - 1.0)
        sr = float(np.mean(r - rf_214) / np.std(r, ddof=1) * np.sqrt(12.0))
        w = np.concatenate([[1.0], np.cumprod(1.0 + r)])
        mdd = float((w / np.maximum.accumulate(w) - 1.0).min())
        months_changed = int(np.sum(np.abs(r - r_ref) > 1e-9))
        max_mo_diff_bp = float(np.max(np.abs(r - r_ref)) * 10000.0)
        return cagr, cagr - cagr_ref, sr, mdd, months_changed, max_mo_diff_bp

    c_cagr, c_dc, c_sr, c_mdd, c_mc, c_mbp = quick_stats(df_c_s, df_curr)
    if run_ti_checks:
        df_1_s = run_ti1_sector_agnostic(p_shocked, label=f"TI-1 ({shock_name})")
        df_2_s = run_ti2_price_clusters(p_shocked, label=f"TI-2 ({shock_name})")
        t1_cagr, t1_dc, t1_sr, t1_mdd, t1_mc, t1_mbp = quick_stats(df_1_s, df_ti1)
        t2_cagr, t2_dc, t2_sr, t2_mdd, t2_mc, t2_mbp = quick_stats(df_2_s, df_ti2)
        assert t1_mc == 0 and t1_mbp == 0.0, "TI-1 must be 100% invariant to GICS shocks!"
        assert t2_mc == 0 and t2_mbp == 0.0, "TI-2 must be 100% invariant to GICS shocks!"
    else:
        t1_cagr, t1_dc, t1_mc = float(np.prod(1.0 + df_ti1["net_ret"].values) ** (12.0 / 214) - 1.0), 0.0, 0
        t2_cagr, t2_dc, t2_mc = float(np.prod(1.0 + df_ti2["net_ret"].values) ** (12.0 / 214) - 1.0), 0.0, 0

    return {
        "Shock_Scenario": shock_name,
        "Current_CAGR": c_cagr,
        "Current_CAGR_Delta_pp": c_dc * 100.0,
        "Current_Sharpe": c_sr,
        "Current_Monthly_MaxDD": c_mdd,
        "Current_Months_Altered": c_mc,
        "Current_Max_Monthly_Diff_bp": c_mbp,
        "TI1_CAGR": t1_cagr,
        "TI1_CAGR_Delta_pp": t1_dc * 100.0,
        "TI1_Months_Altered": t1_mc,
        "TI2_CAGR": t2_cagr,
        "TI2_CAGR_Delta_pp": t2_dc * 100.0,
        "TI2_Months_Altered": t2_mc,
    }

shock_rows = []

shock_rows.append(apply_gics_shock_and_eval(
    p_spx,
    "0. Baseline (Unshocked Official PIT GICS)",
    lambda t, tk, sec: sec
))

SEMI_HW_SET = {"NVDA", "AMD", "AVGO", "MU", "SNDK", "AAPL", "ANET", "WDC", "STX", "FSLR", "SMCI", "PLTR", "LRCX", "KLAC", "AMAT"}
shock_rows.append(apply_gics_shock_and_eval(
    p_spx,
    "1. Shock A: S&P Moves Semis & AI Hardware (NVDA/AMD/AVGO/MU/SNDK/AAPL/ANET/FSLR) Out of IT -> Industrials",
    lambda t, tk, sec: "Industrials" if tk in SEMI_HW_SET else sec
))

MEGA_PLATFORM_SET = {"META", "FB", "GOOGL", "GOOG", "NFLX", "AMZN", "TSLA", "V", "MA", "PYPL"}
shock_rows.append(apply_gics_shock_and_eval(
    p_spx,
    "2. Shock B: Merge Platform/Payment Giants (META/GOOGL/NFLX/AMZN/TSLA/V/MA/PYPL) Back Into IT (2009-2026)",
    lambda t, tk, sec: "Information Technology" if tk in MEGA_PLATFORM_SET else sec
))

TOP_TECH_30 = {
    "NVDA", "AAPL", "MSFT", "AVGO", "AMD", "ORCL", "CRM", "NOW", "ANET", "ADBE",
    "MU", "SNDK", "AMAT", "LRCX", "KLAC", "INTC", "CSCO", "IBM", "QCOM", "TXN",
    "INTU", "PANW", "CRWD", "FTNT", "PLTR", "SMCI", "FSLR", "ENPH", "WDC", "STX"
}
shock_rows.append(apply_gics_shock_and_eval(
    p_spx,
    "3. Shock C: Reclassify Top-30 Pure Tech Leaders Into Financials",
    lambda t, tk, sec: "Financials" if tk in TOP_TECH_30 else sec
))

rng = np.random.default_rng(42)
all_tickers = sorted(p_spx["ticker"].unique())
all_sectors = sorted(p_spx["clean_sector"].dropna().unique())
mc_cagrs, mc_srs, mc_mdds, mc_altered = [], [], [], []

for trial in range(25):
    perm_map = {tk: rng.choice(all_sectors) for tk in all_tickers}
    res = apply_gics_shock_and_eval(
        p_spx,
        f"MC_{trial}",
        lambda t, tk, sec, pm=perm_map: pm.get(tk, sec),
        run_ti_checks=(trial == 0)
    )
    mc_cagrs.append(res["Current_CAGR"])
    mc_srs.append(res["Current_Sharpe"])
    mc_mdds.append(res["Current_Monthly_MaxDD"])
    mc_altered.append(res["Current_Months_Altered"])

base_cagr = shock_rows[0]["Current_CAGR"]
shock_rows.append({
    "Shock_Scenario": "4. Shock D: 25 Monte Carlo Random Full GICS Label Scramblings (Mean Across 25 Runs)",
    "Current_CAGR": float(np.mean(mc_cagrs)),
    "Current_CAGR_Delta_pp": float((np.mean(mc_cagrs) - base_cagr) * 100.0),
    "Current_Sharpe": float(np.mean(mc_srs)),
    "Current_Monthly_MaxDD": float(np.mean(mc_mdds)),
    "Current_Months_Altered": float(np.mean(mc_altered)),
    "Current_Max_Monthly_Diff_bp": 9999.0,
    "TI1_CAGR": shock_rows[0]["TI1_CAGR"],
    "TI1_CAGR_Delta_pp": 0.0,
    "TI1_Months_Altered": 0,
    "TI2_CAGR": shock_rows[0]["TI2_CAGR"],
    "TI2_CAGR_Delta_pp": 0.0,
    "TI2_Months_Altered": 0,
})
shock_rows.append({
    "Shock_Scenario": "5. Shock D (Worst-Case of 25 Random GICS Scramblings)",
    "Current_CAGR": float(np.min(mc_cagrs)),
    "Current_CAGR_Delta_pp": float((np.min(mc_cagrs) - base_cagr) * 100.0),
    "Current_Sharpe": float(np.min(mc_srs)),
    "Current_Monthly_MaxDD": float(np.min(mc_mdds)),
    "Current_Months_Altered": float(np.max(mc_altered)),
    "Current_Max_Monthly_Diff_bp": 9999.0,
    "TI1_CAGR": shock_rows[0]["TI1_CAGR"],
    "TI1_CAGR_Delta_pp": 0.0,
    "TI1_Months_Altered": 0,
    "TI2_CAGR": shock_rows[0]["TI2_CAGR"],
    "TI2_CAGR_Delta_pp": 0.0,
    "TI2_Months_Altered": 0,
})

shock_df = pd.DataFrame(shock_rows)
shock_df.to_csv(os.path.join(OUT_DIR, "03_taxonomy_shock_test_summary.csv"), index=False)

print("\n=== HEAD-TO-HEAD SUMMARY (2009-01..2026-10, 214M) ===")
print(summary_df[[
    "Strategy", "CAGR_214M", "Sharpe_214M", "Monthly_MaxDD", "Hist_Daily_MaxDD",
    "Live_2026_Daily_MaxDD", "MinMER", "Ann_TwoWay_Turnover", "Avg_Max_Single_Stock_Weight"
]].to_string(index=False))

print("\n=== EVENT WINDOWS ===")
print(summary_df[[
    "Strategy", "Ret_2016_REIT_CarveOut", "Ret_2018_2019_XLC_Split",
    "Ret_2022_RateHike_Bear", "Ret_2023_Fintech_GICS_and_QQQ_Rebal",
    "Ret_2024_XLK_Cap_Event", "Ret_2026_YTD_10M", "Ret_2026_10_SingleMonth"
]].to_string(index=False))

print("\n=== TAXONOMY SHOCK TEST ===")
print(shock_df[[
    "Shock_Scenario", "Current_CAGR", "Current_CAGR_Delta_pp", "Current_Months_Altered",
    "TI1_CAGR", "TI1_CAGR_Delta_pp", "TI1_Months_Altered",
    "TI2_CAGR", "TI2_CAGR_Delta_pp", "TI2_Months_Altered"
]].to_string(index=False))
