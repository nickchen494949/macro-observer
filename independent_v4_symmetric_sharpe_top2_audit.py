#!/usr/bin/env python3
"""
Zero-Shared-Code Clean-Room Audit Engine for Frozen Strategy V4 Latest (2026-11-13)
===================================================================================
Strategy Name: Symmetric_Sharpe_Top2_V4 (with optional V3 Election Reset insurance)

Core Rules (100% Symmetric Stock Selection Formula, Unlevered 1.0x):
1. Stock Selection Formula (Identical across all regimes):
   - Metric: 12-1 Sharpe (12-1 Raw Momentum divided by annualized 1-year daily volatility).
   - Position Count & Buffer: Buy Top-2 equal-weighted, keep existing holding if Rank <= 5 (Hold <= 5).
2. Macro Regime Switch (FOMC SEP via ALFRED point-in-time vintage):
   - SEP = ON  (180 historical months):
     * 50% QQQ #1 + 50% QQQ #2 (Nasdaq-100 constituent pool, 12-1 Sharpe, Buy Top-2 / Hold <= 5).
   - SEP = OFF (34 historical tightening months):
     * 50% SGOV (Tiingo open-to-open T-bill ETF return)
     * + 25% BestSec #1 + 25% BestSec #2, where BestSec is the #1 S&P 500 Non-IT GICS sector
       ranked by equal-weighted mean 12-1 Raw momentum, and the 2 stocks inside BestSec are
       selected by 12-1 Sharpe (Buy Top-2 / Hold <= 5, or Hold <= 3 high-win-rate variant).
3. Optional Midterm Election Regime Flip Insurance (V3 Election Reset):
   - Triggered ONLY when US Midterm Election flips Unified -> Divided Government (2010, 2018, 2022).
   - Election Year December (YYYY-12): 100% SGOV for 1 month.
   - Next Year January (YYYY+1-01): Reset Hold <= 5 buffer memory (held = []) at YYYY-12 close.
"""

import os
import json
import numpy as np
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IN_DIR = os.path.join(BASE_DIR, "inputs")
if not os.path.exists(IN_DIR):
    IN_DIR = os.path.join(BASE_DIR, "outputs", "pure_momentum_1985_2026_audit", "inputs")
OUT_DIR = os.path.join(BASE_DIR, "outputs", "v4_symmetric_sharpe_top2_20261113")
os.makedirs(OUT_DIR, exist_ok=True)

p_spx = pd.read_parquet(os.path.join(IN_DIR, "v3_spx_panel_214m.parquet"))
p_ndx = pd.read_parquet(os.path.join(IN_DIR, "v3_ndx_panel_214m.parquet"))
reg_df = pd.read_csv(os.path.join(IN_DIR, "v3_regime_and_cash_214m.csv"))

p_spx["t"] = pd.to_datetime(p_spx["t"])
p_ndx["t"] = pd.to_datetime(p_ndx["t"])
reg_df["t"] = pd.to_datetime(reg_df["t"])

months_all = sorted(p_spx["t"].unique())
months_213 = [t for t in months_all if pd.Timestamp("2008-12-31") <= t <= pd.Timestamp("2026-08-31")]
months_214 = [t for t in months_all if pd.Timestamp("2008-12-31") <= t <= pd.Timestamp("2026-09-30")]

reg_map = {r.t: r._asdict() for r in reg_df.itertuples(index=False)}
ret_lk = {}
for df_p in (p_spx, p_ndx):
    for r in df_p[["t", "ticker", "hold_ret"]].itertuples(index=False):
        ret_lk[(r.t, r.ticker)] = 0.0 if pd.isna(r.hold_ret) else float(r.hold_ret)

p_exit = p_spx[p_spx["clean_sector"] != "Information Technology"].copy()

ym_to_t = {(t + pd.offsets.MonthBegin(1)).strftime("%Y-%m"): t for t in months_all}
t_dec_u2d = {ym_to_t["2010-12"], ym_to_t["2018-12"], ym_to_t["2022-12"]}
t_jan_u2d = {ym_to_t["2011-01"], ym_to_t["2019-01"], ym_to_t["2023-01"]}


def select_qqq_sharpe_top2(panel_ndx, hold_k=5, reset_t_set=None):
    picks = {}
    held = []
    for t, g in panel_ndx.groupby("t", sort=True):
        if reset_t_set and (t in reset_t_set):
            held = []
        gv = g[g["sharpe"].notna()].sort_values(["sharpe", "ticker"], ascending=[False, True]).reset_index(drop=True)
        rk = {tk: i + 1 for i, tk in enumerate(gv["ticker"])}
        kept = [tk for tk in held if rk.get(tk, 999) <= hold_k]
        for tk in gv["ticker"]:
            if len(kept) >= 2:
                break
            if tk not in kept:
                kept.append(tk)
        held = kept[:2]
        picks[t] = (held[0], held[1])
    return picks


def select_bestsec_sharpe_top2(panel_exit, hold_k=5, reset_t_set=None):
    picks = {}
    held = []
    for t, g in panel_exit.groupby("t", sort=True):
        if reset_t_set and (t in reset_t_set):
            held = []
        gv = g[g["mom"].notna() & g["sharpe"].notna()]
        best_sec = gv.groupby("clean_sector")["mom"].mean().sort_index().idxmax()
        gs = gv[gv["clean_sector"] == best_sec].sort_values(["sharpe", "ticker"], ascending=[False, True]).reset_index(drop=True)
        rk = {tk: i + 1 for i, tk in enumerate(gs["ticker"])}
        kept = [tk for tk in held if rk.get(tk, 999) <= hold_k]
        for tk in gs["ticker"]:
            if len(kept) >= 2:
                break
            if tk not in kept:
                kept.append(tk)
        held = kept[:2]
        picks[t] = (held[0], held[1], best_sec)
    return picks


def sim_v4(pk_q, pk_bs, use_election_v3=False, cost_bp=0.0010):
    prev_drifted_w = {}
    rows = []
    trades_q, trades_bs = [], []
    act_q, act_bs = {}, {}

    for t in months_214:
        ym = (t + pd.offsets.MonthBegin(1)).strftime("%Y-%m")
        rm = reg_map[t]
        sep_on = bool(rm["sep_on"])
        r_cash = float(rm["ret_sgov_actual"])
        q1, q2 = pk_q[t]
        bs1, bs2, bs_sec = pk_bs[t]
        is_dec = (t in t_dec_u2d)

        w_stocks = {}
        w_cash = 0.0
        cur_q, cur_bs = set(), set()

        if use_election_v3 and is_dec:
            w_cash = 1.00
        elif sep_on:
            w_stocks[q1] = w_stocks.get(q1, 0.0) + 0.50
            w_stocks[q2] = w_stocks.get(q2, 0.0) + 0.50
            cur_q = {q1, q2}
        else:
            w_stocks[bs1] = w_stocks.get(bs1, 0.0) + 0.25
            w_stocks[bs2] = w_stocks.get(bs2, 0.0) + 0.25
            w_cash = 0.50
            cur_bs = {bs1, bs2}

        for tk in list(act_q.keys()):
            if tk not in cur_q:
                trades_q.append(act_q.pop(tk))
        for tk in cur_q:
            r_tk = ret_lk[(t, tk)]
            if tk not in act_q:
                act_q[tk] = {"leg": "QQQ_ON", "tk": tk, "sec": "NDX", "start": ym, "end": ym, "months": 1, "cum_ret": (1.0 + r_tk) * (1.0 - 2 * cost_bp) - 1.0}
            else:
                act_q[tk]["end"] = ym
                act_q[tk]["months"] += 1
                act_q[tk]["cum_ret"] = (1.0 + act_q[tk]["cum_ret"]) * (1.0 + r_tk) - 1.0

        for tk in list(act_bs.keys()):
            if tk not in cur_bs:
                trades_bs.append(act_bs.pop(tk))
        for tk in cur_bs:
            r_tk = ret_lk[(t, tk)]
            if tk not in act_bs:
                act_bs[tk] = {"leg": "BestSec_OFF", "tk": tk, "sec": bs_sec, "start": ym, "end": ym, "months": 1, "cum_ret": (1.0 + r_tk) * (1.0 - 2 * cost_bp) - 1.0}
            else:
                act_bs[tk]["end"] = ym
                act_bs[tk]["months"] += 1
                act_bs[tk]["cum_ret"] = (1.0 + act_bs[tk]["cum_ret"]) * (1.0 + r_tk) - 1.0

        w_all = dict(w_stocks)
        if w_cash > 0:
            w_all["SGOV"] = w_cash

        gross = sum(wt * ret_lk[(t, tk)] for tk, wt in w_stocks.items()) + w_cash * r_cash
        if not prev_drifted_w:
            to = float(sum(abs(v) for v in w_all.values()))
        else:
            all_k = set(w_all.keys()) | set(prev_drifted_w.keys())
            to = float(sum(abs(w_all.get(k, 0.0) - prev_drifted_w.get(k, 0.0)) for k in all_k))

        net = (1.0 + gross) * ((1.0 - cost_bp) ** to) - 1.0 if to > 0 else gross
        end_eq = 1.0 + gross
        prev_drifted_w = {tk: wt * (1.0 + ret_lk[(t, tk)]) / end_eq for tk, wt in w_stocks.items() if wt > 0}
        if w_cash > 0:
            prev_drifted_w["SGOV"] = w_cash * (1.0 + r_cash) / end_eq

        rows.append({
            "t": t.strftime("%Y-%m-%d"),
            "ym": ym,
            "sep_on": sep_on,
            "q1": q1, "q2": q2,
            "bs1": bs1, "bs2": bs2, "bs_sec": bs_sec,
            "weights_json": json.dumps({k: round(v, 4) for k, v in sorted(w_all.items())}),
            "turnover_two_way": round(to, 6),
            "gross_ret": gross,
            "net_ret": net
        })

    for tk, tr in act_q.items():
        trades_q.append(tr)
    for tk, tr in act_bs.items():
        trades_bs.append(tr)
    return pd.DataFrame(rows).set_index("ym"), pd.DataFrame(trades_q + trades_bs)


rf_214 = np.array([float(reg_map[t]["rf_tbill"]) for t in months_214])


def eval_summary(df, df_tr):
    r204 = df.iloc[:204]["net_ret"].values
    r214 = df.iloc[:214]["net_ret"].values
    c204 = float(np.prod(1.0 + r204) ** (12.0 / 204) - 1.0)
    c214 = float(np.prod(1.0 + r214) ** (12.0 / 214) - 1.0)
    sr214 = float(np.mean(r214 - rf_214) / np.std(r214, ddof=1) * np.sqrt(12.0))
    w = np.concatenate([[1.0], np.cumprod(1.0 + r214)])
    mdd = float((w / np.maximum.accumulate(w) - 1.0).min())
    tr = df_tr["cum_ret"].values
    wins = tr[tr > 0]
    losses = tr[tr <= 0]
    wr = float(len(wins) / len(tr))
    odds = float(np.mean(wins) / abs(np.mean(losses)))
    pf = float(np.sum(wins) / abs(np.sum(losses)))
    return c204, c214, sr214, mdd, wr, odds, pf, len(tr)


if __name__ == "__main__":
    pk_q_v0 = select_qqq_sharpe_top2(p_ndx, hold_k=5, reset_t_set=None)
    pk_bs_h5_v0 = select_bestsec_sharpe_top2(p_exit, hold_k=5, reset_t_set=None)
    pk_bs_h3_v0 = select_bestsec_sharpe_top2(p_exit, hold_k=3, reset_t_set=None)

    pk_q_v3 = select_qqq_sharpe_top2(p_ndx, hold_k=5, reset_t_set=t_jan_u2d)
    pk_bs_h5_v3 = select_bestsec_sharpe_top2(p_exit, hold_k=5, reset_t_set=t_jan_u2d)
    pk_bs_h3_v3 = select_bestsec_sharpe_top2(p_exit, hold_k=3, reset_t_set=t_jan_u2d)

    df_v4_h5_v0, tr_v4_h5_v0 = sim_v4(pk_q_v0, pk_bs_h5_v0, use_election_v3=False)
    df_v4_h3_v0, tr_v4_h3_v0 = sim_v4(pk_q_v0, pk_bs_h3_v0, use_election_v3=False)
    df_v4_h5_v3, tr_v4_h5_v3 = sim_v4(pk_q_v3, pk_bs_h5_v3, use_election_v3=True)
    df_v4_h3_v3, tr_v4_h3_v3 = sim_v4(pk_q_v3, pk_bs_h3_v3, use_election_v3=True)

    c204_1, c214_1, sr_1, mdd_1, wr_1, odds_1, pf_1, n_1 = eval_summary(df_v4_h5_v0, tr_v4_h5_v0)
    c204_2, c214_2, sr_2, mdd_2, wr_2, odds_2, pf_2, n_2 = eval_summary(df_v4_h3_v0, tr_v4_h3_v0)
    c204_3, c214_3, sr_3, mdd_3, wr_3, odds_3, pf_3, n_3 = eval_summary(df_v4_h5_v3, tr_v4_h5_v3)
    c204_4, c214_4, sr_4, mdd_4, wr_4, odds_4, pf_4, n_4 = eval_summary(df_v4_h3_v3, tr_v4_h3_v3)

    assert abs(c214_1 - 0.5965) < 1e-4, f"V4 H5 V0 214M CAGR mismatch: {c214_1:.6f}"
    assert abs(c214_2 - 0.5974) < 1e-4, f"V4 H3 V0 214M CAGR mismatch: {c214_2:.6f}"
    assert abs(c214_3 - 0.6078) < 1e-4, f"V4 H5 V3 214M CAGR mismatch: {c214_3:.6f}"
    assert abs(c214_4 - 0.6074) < 1e-4, f"V4 H3 V3 214M CAGR mismatch: {c214_4:.6f}"

    df_v4_h5_v0.to_csv(os.path.join(OUT_DIR, "v4_symmetric_sharpe_top2_h5_v0_214m_ledger.csv"))
    df_v4_h5_v3.to_csv(os.path.join(OUT_DIR, "v4_symmetric_sharpe_top2_h5_v3_214m_ledger.csv"))
    tr_v4_h5_v0.to_csv(os.path.join(OUT_DIR, "v4_symmetric_sharpe_top2_h5_v0_trades.csv"), index=False)

    t_nov26 = months_all[-1]
    print("PASS: independent_v4_symmetric_sharpe_top2_audit.py verified all assertions.")
    print(f"  1. V4 Symmetric Sharpe Top-2 (Hold<=5, V0 Core) : 09-25={c204_1*100:.2f}% | 214M={c214_1*100:.2f}% | SR={sr_1:.3f} | MonMDD={mdd_1*100:.2f}% | TradeWR={wr_1*100:.2f}% ({n_1} trades) | Odds={odds_1:.2f}:1 | PF={pf_1:.2f}")
    print(f"  2. V4 Symmetric Sharpe Top-2 (Hold<=3, V0 Core) : 09-25={c204_2*100:.2f}% | 214M={c214_2*100:.2f}% | SR={sr_2:.3f} | MonMDD={mdd_2*100:.2f}% | TradeWR={wr_2*100:.2f}% ({n_2} trades) | Odds={odds_2:.2f}:1 | PF={pf_2:.2f}")
    print(f"  3. V4 Symmetric Sharpe Top-2 (Hold<=5 + V3 Elec): 09-25={c204_3*100:.2f}% | 214M={c214_3*100:.2f}% | SR={sr_3:.3f} | MonMDD={mdd_3*100:.2f}%")
    print(f"  4. V4 Symmetric Sharpe Top-2 (Hold<=3 + V3 Elec): 09-25={c204_4*100:.2f}% | 214M={c214_4*100:.2f}% | SR={sr_4:.3f} | MonMDD={mdd_4*100:.2f}%")
    print(f"  2026-11 Live Holdings (SEP=OFF)                 : 25% {pk_bs_h5_v0[t_nov26][0]} + 25% {pk_bs_h5_v0[t_nov26][1]} ({pk_bs_h5_v0[t_nov26][2]}) + 50% SGOV")
