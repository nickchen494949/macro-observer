#!/usr/bin/env python3
"""
run_rebalance_frequency_audit.py
================================
Comprehensive audit of Rebalance Frequency:
  - Monthly (1M: every month)
  - Quarterly (3M: every 3 months — testing all 3 calendar offsets:
      Q_JanAprJulOct [m%3==1], Q_FebMayAugNov [m%3==2], Q_MarJunSepDec [m%3==0], plus 3-offset average)
  - Bi-Annual / Semi-Annual (6M: every 6 months — testing all 6 calendar offsets:
      B_JanJul [m%6==1], B_FebAug [m%6==2], B_MarSep [m%6==3], B_AprOct [m%6==4], B_MayNov [m%6==5], B_JunDec [m%6==0], plus 6-offset average)
  - Annual (12M: every 12 months — Jan rebalance & 12-offset average for comparison)

Tested across 3 distinct panels (all with drifted 10 bp/side turnover cost & Initial NAV = 1.0 MaxDD):
  Panel A: 2009-01 to 2026-10 (214m Strict PIT Mainline Architecture):
    1. Frozen A1-RS 1.35x + V3 Election Reset:
       - Mode A1 (Hybrid): Stock sleeves rebalanced Quarterly/Bi-Annually, Macro SEP/V3 overlays active monthly
       - Mode A2 (Pure Frozen Weights): Entire portfolio frozen between Quarterly/Bi-Annual rebalance dates
    2. A1-RS 1.35x (V0 No Election Reset)
    3. Production Baseline 1.35x (BestSec_ModBurst_135_75_25_GateV1)
    4. Unlevered Pure 3-Leg Core 1.0x (50% QQQ Sharpe Top-2 H5 + 25% Tech Top-1 + 25% SPY Top-1 H3)
  Panel B: 1985-2026 (502m) & 2009-2026 (214m Strict PIT) Pure Stock & Sector Momentum Strategies:
    - Sec_12_1_Top1_Hard, Sec_12_1_Top1_H3, Stock_12_1_Top1_Hard, Stock_12_1_Top1_H3,
      Stock_12_1_Top2_H5, Stock_12_1_Top5, Tech_Top1_Hard, BestSec_Stock_Top1_H3, Pure_3Leg_Core_1x
  Panel C: 2000-2026 Total-Return ETFs (AdjClose, 10bp/side):
    - 9 SPDR Sector ETFs (12-1m Top-1 Hard, 12-1m Top-1 H3, 6-1m Top-2 EW)
    - Broad Index ETFs {SPY, DIA, QQQ} (12-0m Best-1, 6-1m Best-1)
"""
import os
import json
import numpy as np
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IN_DIR = os.path.join(BASE_DIR, "inputs")
COST_BP = 0.0010

# -------------------------------------------------------------------------
# Helper: Metrics with Initial NAV = 1.0
# -------------------------------------------------------------------------
def calc_metrics(rets, rf_arr, ann_turnover=np.nan):
    r = np.asarray(rets, dtype=float)
    rf = np.asarray(rf_arr, dtype=float)
    n = len(r)
    if n == 0:
        return {}
    nav = np.concatenate([[1.0], np.cumprod(1.0 + r)])
    cagr = float(nav[-1] ** (12.0 / n) - 1.0)
    vol = float(np.std(r, ddof=1) * np.sqrt(12.0))
    ex = r - rf
    sharpe = float(np.mean(ex) / np.std(r, ddof=1) * np.sqrt(12.0)) if np.std(r, ddof=1) > 0 else np.nan
    mdd = float((nav / np.maximum.accumulate(nav) - 1.0).min())
    win = float((r > 0).mean())
    return {
        "Months": n,
        "CAGR": cagr,
        "Vol": vol,
        "Sharpe": sharpe,
        "MaxDD": mdd,
        "WinRate": win,
        "Ann_TwoWay_Turnover": ann_turnover
    }

# -------------------------------------------------------------------------
# 1. Load 214M Mainline Cleanroom Inputs
# -------------------------------------------------------------------------
p_spx = pd.read_parquet(os.path.join(IN_DIR, "v3_spx_panel_214m.parquet"))
p_ndx = pd.read_parquet(os.path.join(IN_DIR, "v3_ndx_panel_214m.parquet"))
reg_df = pd.read_csv(os.path.join(IN_DIR, "v3_regime_and_cash_214m.csv"))

p_spx["t"] = pd.to_datetime(p_spx["t"])
p_ndx["t"] = pd.to_datetime(p_ndx["t"])
reg_df["t"] = pd.to_datetime(reg_df["t"])

months_214 = sorted([t for t in p_spx["t"].unique() if pd.Timestamp("2008-12-31") <= t <= pd.Timestamp("2026-09-30")])
sec_ret1m = p_spx.groupby(["t", "clean_sector"])["ret_1m"].mean().to_dict()
p_spx["sec_ret_1m"] = [sec_ret1m.get((t, s), np.nan) for t, s in zip(p_spx["t"], p_spx["clean_sector"])]
p_spx["rs_sec"] = p_spx["ret_1m"] - p_spx["sec_ret_1m"]

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

p_tech = p_spx[p_spx["clean_sector"] == "Information Technology"].copy()
p_exit = p_spx[p_spx["clean_sector"] != "Information Technology"].copy()
reg_map = reg_df.set_index("t").to_dict("index")
rf_214 = np.array([float(reg_map[t]["rf_tbill"]) for t in months_214])

gics_grp_map, top_gics_grp_by_t = {}, {}
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
    for idx, tk in enumerate(sr_r["ticker"]):
        sec_rk_raw[(t_val, tk)] = idx + 1
    for idx, tk in enumerate(sr_s["ticker"]):
        sec_rk_sh[(t_val, tk)] = idx + 1
    if sec_val == "Information Technology":
        g_semi = gv[gv["gics_4digit_group"] == "4530_Semiconductors_and_Equipment"].sort_values(["mom", "ticker"], ascending=[False, True])
        if len(g_semi):
            soxx_top1[t_val] = g_semi["ticker"].iloc[0]

ym_to_t = {(t + pd.offsets.MonthBegin(1)).strftime("%Y-%m"): t for t in months_214}
t_dec_u2d = {ym_to_t["2010-12"], ym_to_t["2018-12"], ym_to_t["2022-12"]}
t_jan_u2d = {ym_to_t["2011-01"], ym_to_t["2019-01"], ym_to_t["2023-01"]}

def is_rebal_month(idx, hold_ym, freq, offset=0):
    if idx == 0:
        return True
    m = int(hold_ym.split("-")[1])
    if freq == "1M":
        return True
    elif freq == "3M":
        return (m - 1) % 3 == offset
    elif freq == "6M":
        return (m - 1) % 6 == offset
    elif freq == "12M":
        return (m - 1) % 12 == offset
    raise ValueError(freq)

def select_sleeves_with_freq(freq="1M", offset=0, use_rs=True, use_v3_reset=False):
    rs_th = -0.05 if use_rs else None
    rst_set = t_jan_u2d if use_v3_reset else set()

    # Group panels by t
    ndx_by_t = {t: g for t, g in p_ndx[p_ndx["sharpe"].notna()].groupby("t")}
    tech_by_t = {t: g for t, g in p_tech[p_tech["mom"].notna()].groupby("t")}
    spx_by_t = {t: g for t, g in p_spx[p_spx["mom"].notna()].groupby("t")}
    exit_by_t = {t: g for t, g in p_exit[p_exit["mom"].notna()].groupby("t")}

    held_q, held_t, held_s, held_er, held_eb = [], [], [], [], []
    last_eb_sec = ""
    out_q, out_t, out_s, out_er, out_eb = {}, {}, {}, {}, {}

    for idx, t_val in enumerate(months_214):
        hold_ym = (t_val + pd.offsets.MonthBegin(1)).strftime("%Y-%m")
        do_rebal = is_rebal_month(idx, hold_ym, freq, offset)
        if t_val in rst_set:
            held_q, held_t, held_s, held_er, held_eb = [], [], [], [], []
            do_rebal = True

        if not do_rebal:
            # Keep previous picks if still valid/priced in return lookup; if delisted mid-quarter, replace at month-end
            out_q[t_val] = list(held_q)
            out_t[t_val] = list(held_t)
            out_s[t_val] = list(held_s)
            out_er[t_val] = list(held_er)
            out_eb[t_val] = [held_eb[0], last_eb_sec]
            continue

        # 1. QQQ (Buy 2, Hold <= 5)
        gq = ndx_by_t[t_val].sort_values(["sharpe", "ticker"], ascending=[False, True]).reset_index(drop=True)
        rk_q = {tk: i + 1 for i, tk in enumerate(gq["ticker"])}
        kept_q = [x for x in held_q if rk_q.get(x, 999) <= 5][:2]
        for x in gq["ticker"]:
            if len(kept_q) >= 2: break
            if x not in kept_q: kept_q.append(x)
        held_q = list(kept_q)
        out_q[t_val] = list(held_q)

        # 2. Tech (Hard Top-1)
        gt = tech_by_t[t_val].sort_values(["mom", "ticker"], ascending=[False, True]).reset_index(drop=True)
        held_t = [gt["ticker"].iloc[0]]
        out_t[t_val] = list(held_t)

        # 3. SPY (Buy 1, Hold <= 3 + RS)
        gs = spx_by_t[t_val].sort_values(["mom", "ticker"], ascending=[False, True]).reset_index(drop=True)
        rk_s = {tk: i + 1 for i, tk in enumerate(gs["ticker"])}
        rs_s = dict(zip(gs["ticker"], gs["rs_sec"]))
        kept_s, ban_s = [], set()
        for x in held_s:
            rk = rk_s.get(x, 999)
            if rk <= 3 and (rs_th is None or rk == 1 or rs_s.get(x, 0.0) >= rs_th):
                kept_s.append(x)
            elif rk <= 3:
                ban_s.add(x)
        for x in gs["ticker"]:
            if len(kept_s) >= 1: break
            if x not in kept_s and x not in ban_s: kept_s.append(x)
        held_s = kept_s[:1]
        out_s[t_val] = list(held_s)

        # 4. Ex-IT Raw (Buy 1, Hold <= 3 + RS)
        ge = exit_by_t[t_val].sort_values(["mom", "ticker"], ascending=[False, True]).reset_index(drop=True)
        rk_e = {tk: i + 1 for i, tk in enumerate(ge["ticker"])}
        rs_e = dict(zip(ge["ticker"], ge["rs_sec"]))
        kept_e, ban_e = [], set()
        for x in held_er:
            rk = rk_e.get(x, 999)
            if rk <= 3 and (rs_th is None or rk == 1 or rs_e.get(x, 0.0) >= rs_th):
                kept_e.append(x)
            elif rk <= 3:
                ban_e.add(x)
        for x in ge["ticker"]:
            if len(kept_e) >= 1: break
            if x not in kept_e and x not in ban_e: kept_e.append(x)
        held_er = kept_e[:1]
        out_er[t_val] = list(held_er)

        # 5. Ex-IT BestSec (Buy 1, Hold <= 3 + RS)
        g_bs = exit_by_t[t_val].copy()
        sec_ew = g_bs.groupby("clean_sector")["mom"].mean().sort_values(ascending=False)
        top_sec = str(sec_ew.index[0])
        sec_rk = {s: i + 1 for i, s in enumerate(sec_ew.index)}
        g_bs["sec_rk"] = g_bs["clean_sector"].map(sec_rk)
        g_top = g_bs[g_bs["sec_rk"] == 1].sort_values(["mom", "ticker"], ascending=[False, True])
        g_rest = g_bs[g_bs["sec_rk"] > 1].sort_values(["sec_rk", "mom", "ticker"], ascending=[True, False, True])
        ranked_bs = list(pd.concat([g_top, g_rest])["ticker"])
        rk_bs = {x: i + 1 for i, x in enumerate(ranked_bs)}
        rs_bs = dict(zip(g_bs["ticker"], g_bs["rs_sec"]))
        kept_bs = [
            x for x in held_eb
            if rk_bs.get(x, 999) <= 3 and (rs_th is None or rk_bs.get(x, 999) == 1 or rs_bs.get(x, 0.0) >= rs_th)
        ][:1]
        if not kept_bs:
            kept_bs = [ranked_bs[0]]
        held_eb = list(kept_bs)
        last_eb_sec = top_sec
        out_eb[t_val] = [held_eb[0], top_sec]

    return out_q, out_t, out_s, out_er, out_eb

def sim_mainline_with_freq(
    freq="1M", offset=0, is_a1=True, use_rs=True, use_v3=True,
    freeze_all_between_rebals=False, unlevered_pure_3leg=False
):
    pk_q, pk_t, pk_s, pk_er, pk_eb = select_sleeves_with_freq(freq, offset, use_rs, use_v3)
    prev_drifted_w = {}
    prev_borrow = 0.0
    net_rets = []
    tot_to = 0.0

    for idx, t in enumerate(months_214):
        ym = (t + pd.offsets.MonthBegin(1)).strftime("%Y-%m")
        do_rebal = is_rebal_month(idx, ym, freq, offset)
        if use_v3 and (t in t_dec_u2d or t in t_jan_u2d):
            do_rebal = True

        rm = reg_map[t]
        r_tbill = float(rm["rf_tbill"])
        r_cash = float(rm["ret_sgov_actual"])
        r_borrow = r_tbill + 0.005 / 12.0

        if freeze_all_between_rebals and (not do_rebal) and prev_drifted_w:
            # Pure buy-and-hold drift between rebalance months (zero trading except if delisted)
            w_stocks = {}
            w_cash = float(prev_drifted_w.get("SGOV", 0.0))
            freed_cash = 0.0
            for tk, wt in prev_drifted_w.items():
                if tk == "SGOV":
                    continue
                if (t, tk) in ret_lk:
                    w_stocks[tk] = wt
                else:
                    freed_cash += wt
            w_cash += freed_cash
            w_borrow = prev_borrow
            w_all_tradable = dict(w_stocks)
            if w_cash > 0:
                w_all_tradable["SGOV"] = w_cash
        else:
            sep_on = True if unlevered_pure_3leg else bool(rm["sep_on"])
            qqq_vol21 = float(rm["qqq_vol21"])
            dm_panic = bool(rm["dm_panic"])

            q1, q2 = pk_q[t]
            t1 = pk_t[t][0]
            s1_raw = pk_s[t][0]
            er1 = pk_er[t][0]
            eb1 = pk_eb[t][0]

            # Ensure held ticker has valid return in non-rebalance month; if exited, fallback to current top-1
            if (t, q1) not in ret_lk or (t, q2) not in ret_lk:
                gq = p_ndx[(p_ndx["t"] == t) & p_ndx["sharpe"].notna()].sort_values(["sharpe", "ticker"], ascending=[False, True])
                q_cands = [x for x in gq["ticker"] if (t, x) in ret_lk]
                if (t, q1) not in ret_lk: q1 = q_cands[0]
                if (t, q2) not in ret_lk or q2 == q1: q2 = [x for x in q_cands if x != q1][0]
            if (t, t1) not in ret_lk:
                gt = p_tech[(p_tech["t"] == t) & p_tech["mom"].notna()].sort_values(["mom", "ticker"], ascending=[False, True])
                t1 = [x for x in gt["ticker"] if (t, x) in ret_lk][0]
            if (t, s1_raw) not in ret_lk:
                gs = p_spx[(p_spx["t"] == t) & p_spx["mom"].notna()].sort_values(["mom", "ticker"], ascending=[False, True])
                s1_raw = [x for x in gs["ticker"] if (t, x) in ret_lk][0]
            if (t, er1) not in ret_lk:
                ge = p_exit[(p_exit["t"] == t) & p_exit["mom"].notna()].sort_values(["mom", "ticker"], ascending=[False, True])
                er1 = [x for x in ge["ticker"] if (t, x) in ret_lk][0]
            if (t, eb1) not in ret_lk:
                ge = p_exit[(p_exit["t"] == t) & p_exit["mom"].notna()].sort_values(["mom", "ticker"], ascending=[False, True])
                eb1 = [x for x in ge["ticker"] if (t, x) in ret_lk][0]

            is_dec = use_v3 and (t in t_dec_u2d)
            s1 = er1 if (is_a1 and (not sep_on) and (t1 == s1_raw)) else s1_raw

            w_base = {}
            for x in [q1, q2, t1, s1]:
                w_base[x] = w_base.get(x, 0.0) + 0.25

            port_vol_est = float(sum(wt * vol_lk.get((t, tk), 0.35) for tk, wt in w_base.items()))
            lowvol_ok = bool((not unlevered_pure_3leg) and sep_on and (qqq_vol21 <= 0.30) and (port_vol_est <= 0.55) and (not dm_panic))

            is_3leg = (t1 == s1) and (t1 in (q1, q2))
            is_2leg = (not is_3leg) and ((t1 == s1) or (t1 in (q1, q2)) or (s1 in (q1, q2)))
            ov_tk = t1 if ((t1 == s1) or (t1 in (q1, q2))) else (s1 if (s1 in (q1, q2)) else "")
            is_soxx1 = (ov_tk != "") and (soxx_top1.get(t, "") == ov_tk)
            sr_r = sec_rk_raw.get((t, ov_tk), 99)
            sr_s = sec_rk_sh.get((t, ov_tk), 99)
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

        gross_stocks = sum(wt * ret_lk[(t, tk)] for tk, wt in w_stocks.items())
        gross_total = gross_stocks + w_cash * r_cash - w_borrow * r_borrow

        if not prev_drifted_w:
            to = float(sum(abs(v) for v in w_all_tradable.values()))
        else:
            all_k = set(w_all_tradable.keys()) | set(prev_drifted_w.keys())
            to = float(sum(abs(w_all_tradable.get(k, 0.0) - prev_drifted_w.get(k, 0.0)) for k in all_k))
        tot_to += to

        net_total = (1.0 + gross_total) * ((1.0 - COST_BP) ** to) - 1.0 if to > 0 else gross_total
        end_eq = 1.0 + gross_total
        if end_eq > 0:
            prev_drifted_w = {tk: wt * (1.0 + ret_lk[(t, tk)]) / end_eq for tk, wt in w_stocks.items() if wt > 0}
            if w_cash > 0:
                prev_drifted_w["SGOV"] = w_cash * (1.0 + r_cash) / end_eq
            prev_borrow = w_borrow / end_eq
        else:
            prev_drifted_w = {}
            prev_borrow = 0.0
        net_rets.append(net_total)

    ann_to = tot_to * (12.0 / len(months_214))
    return calc_metrics(net_rets, rf_214, ann_to)

rows_out = []

# Test Mainline Strategies across 1M, 3M (all 3 offsets + avg), 6M (all 6 offsets + avg), 12M (all 12 offsets + avg)
mainline_configs = [
    ("Frozen Challenger: A1-RS 1.35x + V3 (Stock Rebal Only, Monthly Macro/V3 Active)", True, True, True, False, False),
    ("Frozen Challenger: A1-RS 1.35x + V3 (Full Portfolio Frozen Between Rebals)", True, True, True, True, False),
    ("A1-RS 1.35x (V0 No Election Reset, Full Frozen Between Rebals)", True, True, False, True, False),
    ("Production Baseline 1.35x (Route 1 No RS, Full Frozen Between Rebals)", False, False, False, True, False),
    ("Unlevered Pure 3-Leg Core 1.0x (50% QQQ + 25% Tech + 25% SPY, Full Frozen)", False, False, False, True, True),
]

for strat_label, is_a1, use_rs, use_v3, freeze_all, unlev in mainline_configs:
    # 1M
    m_1m = sim_mainline_with_freq("1M", 0, is_a1, use_rs, use_v3, freeze_all, unlev)
    rows_out.append({"Panel": "Panel A: 2009-2026 Strict PIT Mainline (214m, Next-Open, 10bp/side)", "Strategy": strat_label, "Rebal_Freq": "1M (Monthly)", **m_1m})

    # 3M offsets: 0=Jan/Apr/Jul/Oct, 1=Feb/May/Aug/Nov, 2=Mar/Jun/Sep/Dec
    q_names = {0: "3M_JanAprJulOct", 1: "3M_FebMayAugNov", 2: "3M_MarJunSepDec"}
    q_list = []
    for off in range(3):
        mq = sim_mainline_with_freq("3M", off, is_a1, use_rs, use_v3, freeze_all, unlev)
        q_list.append(mq)
        rows_out.append({"Panel": "Panel A: 2009-2026 Strict PIT Mainline (214m, Next-Open, 10bp/side)", "Strategy": strat_label, "Rebal_Freq": q_names[off], **mq})
    rows_out.append({
        "Panel": "Panel A: 2009-2026 Strict PIT Mainline (214m, Next-Open, 10bp/side)", "Strategy": strat_label, "Rebal_Freq": "3M (Quarterly Mean of 3 Offsets)",
        "Months": 214,
        "CAGR": float(np.mean([x["CAGR"] for x in q_list])),
        "Vol": float(np.mean([x["Vol"] for x in q_list])),
        "Sharpe": float(np.mean([x["Sharpe"] for x in q_list])),
        "MaxDD": float(np.mean([x["MaxDD"] for x in q_list])),
        "WinRate": float(np.mean([x["WinRate"] for x in q_list])),
        "Ann_TwoWay_Turnover": float(np.mean([x["Ann_TwoWay_Turnover"] for x in q_list])),
    })

    # 6M offsets: 0=Jan/Jul .. 5=Jun/Dec
    b_names = {0: "6M_JanJul", 3: "6M_AprOct", 5: "6M_JunDec"}
    b_list = []
    for off in range(6):
        mb = sim_mainline_with_freq("6M", off, is_a1, use_rs, use_v3, freeze_all, unlev)
        b_list.append(mb)
        if off in b_names:
            rows_out.append({"Panel": "Panel A: 2009-2026 Strict PIT Mainline (214m, Next-Open, 10bp/side)", "Strategy": strat_label, "Rebal_Freq": b_names[off], **mb})
    rows_out.append({
        "Panel": "Panel A: 2009-2026 Strict PIT Mainline (214m, Next-Open, 10bp/side)", "Strategy": strat_label, "Rebal_Freq": "6M (Bi-Annual Mean of 6 Offsets)",
        "Months": 214,
        "CAGR": float(np.mean([x["CAGR"] for x in b_list])),
        "Vol": float(np.mean([x["Vol"] for x in b_list])),
        "Sharpe": float(np.mean([x["Sharpe"] for x in b_list])),
        "MaxDD": float(np.mean([x["MaxDD"] for x in b_list])),
        "WinRate": float(np.mean([x["WinRate"] for x in b_list])),
        "Ann_TwoWay_Turnover": float(np.mean([x["Ann_TwoWay_Turnover"] for x in b_list])),
    })

# -------------------------------------------------------------------------
# 2. Panel B: 1985-2026 (502m) & 2009-2026 (214m) Long-Term Stock & Sector Momentum
# -------------------------------------------------------------------------
panel_lt = pd.read_parquet(os.path.join(IN_DIR, "panel_1985_2026_monthly.parquet"))
macro_m = pd.read_csv(os.path.join(IN_DIR, "macro_and_cash_indices_monthly_1983_2026.csv"))
macro_m["rf_m"] = (macro_m["DGS3MO"].ffill().fillna(4.0) / 100.0) / 12.0
rf_map = dict(zip(macro_m["ym"], macro_m["rf_m"]))

hold_months_all = sorted(panel_lt["hold_ym"].unique())
by_ym = {ym: g for ym, g in panel_lt.groupby("hold_ym")}
ret_col = "fwd_ret_stress"

def eval_lt_weights_with_freq(weights_by_ym_1m, freq="1M", offset=0):
    prev_drifted = {}
    out_r = []
    tot_to = 0.0
    for idx, ym in enumerate(hold_months_all):
        g = by_ym[ym]
        r_map = dict(zip(g["ticker"], g[ret_col]))
        do_rebal = is_rebal_month(idx, ym, freq, offset)

        if do_rebal or not prev_drifted:
            w_tgt = weights_by_ym_1m.get(ym, {})
        else:
            # Keep drifted holdings; if a stock exited/delisted prior to this month, redistribute proportionally or to current target
            valid_prev = {k: v for k, v in prev_drifted.items() if k in r_map}
            s_val = sum(valid_prev.values())
            if s_val > 1e-9:
                w_tgt = {k: v / s_val for k, v in valid_prev.items()}
            else:
                w_tgt = weights_by_ym_1m.get(ym, {})

        all_k = set(w_tgt.keys()) | set(prev_drifted.keys())
        to = sum(abs(w_tgt.get(k, 0.0) - prev_drifted.get(k, 0.0)) for k in all_k) if prev_drifted else sum(abs(v) for v in w_tgt.values())
        tot_to += to
        gross = sum(w * r_map.get(k, 0.0) for k, w in w_tgt.items())
        net = (1.0 + gross) * ((1.0 - COST_BP) ** to) - 1.0
        out_r.append((ym, net))
        denom = 1.0 + gross
        if denom > 0:
            prev_drifted = {k: w * (1.0 + r_map.get(k, 0.0)) / denom for k, w in w_tgt.items() if k in r_map}
        else:
            prev_drifted = {}
    df_r = pd.DataFrame(out_r, columns=["ym", "r"]).set_index("ym")
    return df_r, tot_to

# Build 1M target weights for key strategies
w_sec_top1, w_stock_top1_hard, w_stock_top1_h3, w_stock_top5, w_tech_top1, w_3leg = {}, {}, {}, {}, {}, {}
held_s1_h3, held_sh2_h5 = [], []

for ym in hold_months_all:
    g = by_ym[ym]
    g_sec = g.dropna(subset=["clean_sector"])
    sec_mom = g_sec.groupby("clean_sector")["mom_12_1"].mean().sort_values(ascending=False)
    top_sec = sec_mom.index[0]
    s_tks = list(g_sec[g_sec["clean_sector"] == top_sec]["ticker"])
    w_sec_top1[ym] = {k: 1.0 / len(s_tks) for k in s_tks}

    gs = g.sort_values(["mom_12_1", "ticker"], ascending=[False, True]).reset_index(drop=True)
    rk_s = {tk: i + 1 for i, tk in enumerate(gs["ticker"])}
    w_stock_top1_hard[ym] = {gs["ticker"].iloc[0]: 1.0}

    kept_h3 = [x for x in held_s1_h3 if rk_s.get(x, 999) <= 3][:1]
    if not kept_h3:
        kept_h3 = [gs["ticker"].iloc[0]]
    held_s1_h3 = list(kept_h3)
    w_stock_top1_h3[ym] = {held_s1_h3[0]: 1.0}

    top5 = list(gs["ticker"].iloc[:5])
    w_stock_top5[ym] = {k: 1.0 / len(top5) for k in top5}

    gt = g_sec[g_sec["clean_sector"] == "Information Technology"].sort_values(["mom_12_1", "ticker"], ascending=[False, True])
    t_pick = gt["ticker"].iloc[0] if len(gt) > 0 else gs["ticker"].iloc[0]
    w_tech_top1[ym] = {t_pick: 1.0}

    gsh = g.dropna(subset=["sharpe_12_1"]).sort_values(["sharpe_12_1", "ticker"], ascending=[False, True]).reset_index(drop=True)
    rk_sh = {tk: i + 1 for i, tk in enumerate(gsh["ticker"])}
    kept_sh = [x for x in held_sh2_h5 if rk_sh.get(x, 999) <= 5][:2]
    for x in gsh["ticker"]:
        if len(kept_sh) >= 2: break
        if x not in kept_sh: kept_sh.append(x)
    held_sh2_h5 = list(kept_sh)

    w3 = {}
    for k in held_sh2_h5:
        w3[k] = w3.get(k, 0.0) + 0.50 / len(held_sh2_h5)
    w3[t_pick] = w3.get(t_pick, 0.0) + 0.25
    w3[held_s1_h3[0]] = w3.get(held_s1_h3[0], 0.0) + 0.25
    w_3leg[ym] = w3

lt_strats = [
    ("Sec_12_1_Top1_Hard", w_sec_top1),
    ("Stock_12_1_Top1_Hard", w_stock_top1_hard),
    ("Stock_12_1_Top1_H3", w_stock_top1_h3),
    ("Stock_12_1_Top5", w_stock_top5),
    ("Tech_Top1_Hard", w_tech_top1),
    ("Pure_3Leg_Core_1x", w_3leg),
]

for era_label, start_ym in [
    ("Panel B1: 2009-2026 Strict PIT Stocks & Sectors (214m, 10bp/side)", "2009-01"),
    ("Panel B2: 1985-2026 Long-Term Stocks & Sectors (502m, 10bp/side)", "1985-01"),
]:
    for sname, w_dict in lt_strats:
        # 1M
        df_1m, _ = eval_lt_weights_with_freq(w_dict, "1M", 0)
        sub_1m = df_1m.loc[start_ym:]
        rf_sub = [rf_map.get(ym, 0.003) for ym in sub_1m.index]
        rows_out.append({"Panel": era_label, "Strategy": sname, "Rebal_Freq": "1M (Monthly)", **calc_metrics(sub_1m["r"].values, rf_sub)})

        # 3M mean of 3 offsets
        q_mets = []
        for off in range(3):
            df_q, _ = eval_lt_weights_with_freq(w_dict, "3M", off)
            sub_q = df_q.loc[start_ym:]
            q_mets.append(calc_metrics(sub_q["r"].values, rf_sub))
        rows_out.append({
            "Panel": era_label, "Strategy": sname, "Rebal_Freq": "3M (Quarterly Mean of 3 Offsets)",
            "Months": len(sub_1m),
            "CAGR": float(np.mean([x["CAGR"] for x in q_mets])),
            "Vol": float(np.mean([x["Vol"] for x in q_mets])),
            "Sharpe": float(np.mean([x["Sharpe"] for x in q_mets])),
            "MaxDD": float(np.mean([x["MaxDD"] for x in q_mets])),
            "WinRate": float(np.mean([x["WinRate"] for x in q_mets])),
            "Ann_TwoWay_Turnover": np.nan
        })

        # 6M mean of 6 offsets
        b_mets = []
        for off in range(6):
            df_b, _ = eval_lt_weights_with_freq(w_dict, "6M", off)
            sub_b = df_b.loc[start_ym:]
            b_mets.append(calc_metrics(sub_b["r"].values, rf_sub))
        rows_out.append({
            "Panel": era_label, "Strategy": sname, "Rebal_Freq": "6M (Bi-Annual Mean of 6 Offsets)",
            "Months": len(sub_1m),
            "CAGR": float(np.mean([x["CAGR"] for x in b_mets])),
            "Vol": float(np.mean([x["Vol"] for x in b_mets])),
            "Sharpe": float(np.mean([x["Sharpe"] for x in b_mets])),
            "MaxDD": float(np.mean([x["MaxDD"] for x in b_mets])),
            "WinRate": float(np.mean([x["WinRate"] for x in b_mets])),
            "Ann_TwoWay_Turnover": np.nan
        })

# -------------------------------------------------------------------------
# 3. Panel C: 2000-2026 Total-Return ETFs (9 SPDR Sectors & {SPY, DIA, QQQ})
# -------------------------------------------------------------------------
etf_d = pd.read_parquet(os.path.join(IN_DIR, "etfs_daily_total_return_adjclose.parquet"))
etf_d["ym"] = etf_d["date"].str.slice(0, 7)
etf_m = etf_d.sort_values(["ticker", "date"]).groupby(["ticker", "ym"], as_index=False).last()
sec_etfs = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]
spdr_p = etf_m[etf_m["ticker"].isin(sec_etfs)].pivot(index="ym", columns="ticker", values="adj_close").dropna()
spdr_p = spdr_p[spdr_p.index <= "2026-10"]
spdr_ret = spdr_p.pct_change()
spdr_sig_12_1 = (spdr_p.shift(1) / spdr_p.shift(12) - 1.0).shift(1)
spdr_sig_6_1 = (spdr_p.shift(1) / spdr_p.shift(6) - 1.0).shift(1)
valid_spdr_yms = list(spdr_p.index[13:])
rf_spdr = [rf_map.get(ym, 0.002) for ym in valid_spdr_yms]

def sim_etf_rebal(sig_df, ret_df, yms, top_k=1, hold_k=1, freq="1M", offset=0):
    held = []
    prev_drifted = {}
    rets = []
    for idx, ym in enumerate(yms):
        r_row = ret_df.loc[ym].to_dict()
        do_rebal = is_rebal_month(idx, ym, freq, offset)
        if do_rebal or not prev_drifted:
            s_row = sig_df.loc[ym].sort_values(ascending=False)
            ranked = list(s_row.index)
            rk_map = {k: i + 1 for i, k in enumerate(ranked)}
            kept = [x for x in held if rk_map.get(x, 999) <= hold_k][:top_k]
            for x in ranked:
                if len(kept) >= top_k: break
                if x not in kept: kept.append(x)
            held = list(kept)
            w_tgt = {k: 1.0 / len(held) for k in held}
        else:
            w_tgt = dict(prev_drifted)

        all_k = set(w_tgt.keys()) | set(prev_drifted.keys())
        to = sum(abs(w_tgt.get(k, 0.0) - prev_drifted.get(k, 0.0)) for k in all_k) if prev_drifted else sum(abs(v) for v in w_tgt.values())
        gross = sum(w * float(r_row[k]) for k, w in w_tgt.items())
        net = (1.0 + gross) * ((1.0 - COST_BP) ** to) - 1.0
        rets.append(net)
        denom = 1.0 + gross
        prev_drifted = {k: w * (1.0 + float(r_row[k])) / denom for k, w in w_tgt.items()} if denom > 0 else {}
    return calc_metrics(rets, rf_spdr)

for s_label, s_df, tk, hk in [
    ("9-SPDR Sector ETFs: 12-1m Top-1 Hard", spdr_sig_12_1, 1, 1),
    ("9-SPDR Sector ETFs: 12-1m Top-1 (Hold<=3)", spdr_sig_12_1, 1, 3),
    ("9-SPDR Sector ETFs: 6-1m Top-2 EW", spdr_sig_6_1, 2, 2),
]:
    m1 = sim_etf_rebal(s_df, spdr_ret, valid_spdr_yms, tk, hk, "1M", 0)
    rows_out.append({"Panel": "Panel C: 2000-2026 Total-Return SPDR Sector ETFs (322m, 10bp/side)", "Strategy": s_label, "Rebal_Freq": "1M (Monthly)", **m1})
    q_m = [sim_etf_rebal(s_df, spdr_ret, valid_spdr_yms, tk, hk, "3M", off) for off in range(3)]
    rows_out.append({
        "Panel": "Panel C: 2000-2026 Total-Return SPDR Sector ETFs (322m, 10bp/side)", "Strategy": s_label, "Rebal_Freq": "3M (Quarterly Mean of 3 Offsets)",
        "Months": len(valid_spdr_yms),
        "CAGR": float(np.mean([x["CAGR"] for x in q_m])),
        "Vol": float(np.mean([x["Vol"] for x in q_m])),
        "Sharpe": float(np.mean([x["Sharpe"] for x in q_m])),
        "MaxDD": float(np.mean([x["MaxDD"] for x in q_m])),
        "WinRate": float(np.mean([x["WinRate"] for x in q_m])),
        "Ann_TwoWay_Turnover": np.nan
    })
    b_m = [sim_etf_rebal(s_df, spdr_ret, valid_spdr_yms, tk, hk, "6M", off) for off in range(6)]
    rows_out.append({
        "Panel": "Panel C: 2000-2026 Total-Return SPDR Sector ETFs (322m, 10bp/side)", "Strategy": s_label, "Rebal_Freq": "6M (Bi-Annual Mean of 6 Offsets)",
        "Months": len(valid_spdr_yms),
        "CAGR": float(np.mean([x["CAGR"] for x in b_m])),
        "Vol": float(np.mean([x["Vol"] for x in b_m])),
        "Sharpe": float(np.mean([x["Sharpe"] for x in b_m])),
        "MaxDD": float(np.mean([x["MaxDD"] for x in b_m])),
        "WinRate": float(np.mean([x["WinRate"] for x in b_m])),
        "Ann_TwoWay_Turnover": np.nan
    })

df_out = pd.DataFrame(rows_out)
df_out.to_csv(os.path.join(BASE_DIR, "08_rebalance_frequency_monthly_quarterly_biannual_audit.csv"), index=False)

for p_name, grp in df_out.groupby("Panel", sort=False):
    print("\n" + "=" * 120)
    print(p_name)
    print("=" * 120)
    for _, r in grp.iterrows():
        to_str = f"{r['Ann_TwoWay_Turnover']:.2f}x/yr" if pd.notna(r["Ann_TwoWay_Turnover"]) else "  N/A "
        print(f"{r['Strategy']:<72s} | {r['Rebal_Freq']:<32s} | CAGR: {r['CAGR']:6.2%} | SR: {r['Sharpe']:5.3f} | MaxDD: {r['MaxDD']:7.2%} | Turn: {to_str}")
