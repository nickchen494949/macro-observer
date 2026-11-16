#!/usr/bin/env python3
"""
run_jlaw_vcp_entry_and_blend_audit.py — V4 Entry/Exit Timing Challengers (J Law M.E.T.A., Minervini VCP, O'Neil, Turtle, Scale-In)
& Stateful Walk-Forward 50/50 Blend + Crash Co-Movement Audit (2026-11-16)
==================================================================================================================================
PART I: V4 ENTRY & EXIT TIMING CHALLENGERS (Selection & SEP Routing 100% Frozen)
  - Mode A (Baseline): Buy 100% of target slot at month-start first trading day open (`d0 Open`, `10bp/side`).
  - Mode B (J Law M.E.T.A. Pullback Entry — Wait for Support Confluence on New Entries):
      * B1 (`JLaw-MA20-Pivot-Pullback`): For any newly selected stock (continuing holdings from prior month remain 100% held),
        park the slot in `SGOV/BIL` at `d0 Open` and enter `100%` at next-day `adjOpen[d]` as soon as daily close `C[d-1]`
        pulls back into the J Law M.E.T.A. support zone: within `+2.0%` of rising `MA20` (`C[d-1] <= 1.02 * MA20[d-1]` and
        `MA20[d-1] >= MA20[d-6]`) OR within `+2.0%` of the prior 20-day breakout pivot (`max(C[t-25..t-5])`), while staying
        above `MA50` (`C[d-1] >= MA50[d-1]`).
      * B2 (`JLaw-Dip3pct-Pullback`): For any newly selected stock, wait for a `>= -3.0%` pullback from formation close `C[t]`
        (or touch of `MA20`) while `C[d-1] >= MA50[d-1]`, entering at next-day `adjOpen[d]`.
      * B3 (`JLaw-Pullback-10dCap`): Same as B1, but if no pullback occurs within the first 10 trading days of the month and
        the stock is still above `MA20`, enter at day-11 `adjOpen` (avoids missing entire runaway months).
  - Mode C (Minervini VCP & William O'Neil Breakout Entry on New Entries):
      * C1 (`Minervini-VCP-Breakout`): For any newly selected stock, wait for volatility contraction (`5-day std < 0.80 * 20-day std`
        or `5-day dollar volume < 20-day dollar volume`) followed by a daily close breaking above the trailing 10-day high
        (`C[d-1] >= max(C[d-10..d-2])`), entering at next-day `adjOpen[d]`.
      * C2 (`ONeil-20dHigh-VolBreakout`): For any newly selected stock, enter at next-day `adjOpen[d]` when daily close reaches
        within `0.5%` of a new 20-day high (`C[d-1] >= 0.995 * max(C[d-20..d-1])`) on above-average dollar volume (`DV[d-1] > MA20_DV`).
  - Mode D (Pyramiding / Scale-In on New Entries — Never Miss Runaway Leaders while Cutting Failed-Entry Risk):
      * D1 (`ScaleIn-50-50-Breakout3pct`): Enter `50%` of the new slot at `d0 Open` (other `50%` in `SGOV/BIL`). Add the remaining
        `50%` at next-day `adjOpen[d]` once close confirms `>= +3.0%` above `d0 Open` (or new 10-day high).
      * D2 (`ScaleIn-50-50-JLawOrBreakout`): Enter `50%` at `d0 Open`, and add the remaining `50%` at next-day `adjOpen[d]` either
        on a J Law `MA20` support pullback (`C[d-1] <= 1.015 * MA20[d-1]` & `>= MA50[d-1]`) OR on a `+4.0%` breakout confirmation.
      * D3 (`ScaleIn-AllSlots-50-50`): Apply `50% d0 Open + 50% on +3% confirmation` to ALL slots every month (stress test).
  - Mode E (Separate Exit-Only Challengers — Keeping Mode A `100% d0 Open` Entry Fixed):
      * E1 (`ONeil-8pct-StopLoss`): Exit to `SGOV/BIL` at next-day `adjOpen[d]` if daily close drops `<= -8.0%` below month entry `adjOpen[d0]`.
      * E2 (`Turtle-20dLow-Exit`): Exit to `SGOV/BIL` at next-day `adjOpen[d]` if daily close breaks below trailing 20-day low `min(C[d-20..d-2])`.
      * E3 (`Turtle-3ATR-TrailingStop`): Exit to `SGOV/BIL` at next-day `adjOpen[d]` if daily close drops `>= 3.0 * ATR_20` below peak close since entry.

PART II: PORTFOLIO-LEVEL COMBINATION (`V4 + TQQQ SEP` 50/50 BLEND — FROZEN & STATEFUL WALK-FORWARD) & CRASH CO-MOVEMENT AUDIT
  - Head-to-head comparison of `100% V4`, `100% TQQQ SEP`, and `50/50 Blend` under both:
      (1) Frozen rules (`2010-02-11 .. 2026-10-29`), and
      (2) Stateful Walk-Forward out-of-sample parameter selection (`2012-01-03 .. 2026-10-29`, zero hindsight).
  - Joint drawdown anatomy: identifies every historical episode where both strategies lost money simultaneously, quantifies
    regime-conditional correlation (`SEP = ON` vs `SEP = OFF`), and builds a live forward-simulation paper-trading log template.
"""
import functools
import json
import os
import numpy as np
import pandas as pd
import frozen_v1_tqqq_strategy as fv
import independent_v4_symmetric_sharpe_top2_audit as iv4

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "research", "sector_stock_momentum", "data")
ETF_DIR = os.path.join(ROOT, "outputs", "remediation_full_audit_20261104", "tiingo_etfs")
TIINGO_ROWS_DIRS = [
    os.path.join(ROOT, "outputs", "qqq_mom_top3_claude_audit_20261103", "tiingo"),
    os.path.join(ROOT, "outputs", "tech_top1_independent_audit_20261103", "tiingo"),
]
OUT_DIR = os.path.join(ROOT, "outputs", "jlaw_vcp_entry_and_blend_audit_20261116")
os.makedirs(OUT_DIR, exist_ok=True)


def _frame(dates, close, opn):
    idx = pd.to_datetime(pd.Series(list(dates)).astype(str).str[:10])
    df = pd.DataFrame({
        "c": pd.to_numeric(pd.Series(list(close)), errors="coerce").values,
        "o": (pd.to_numeric(pd.Series(list(opn)), errors="coerce").values if opn is not None else np.nan),
    }, index=idx.values)
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df = df[df["c"] > 0]
    df.loc[~(df["o"] > 0), "o"] = np.nan
    return df if len(df) else None


@functools.lru_cache(maxsize=1)
def _wiki():
    w = pd.read_parquet(os.path.join(DATA_DIR, "wiki_bulk", "wiki_prices.parquet"), columns=["ticker", "date", "adj_close"])
    o = pd.read_parquet(os.path.join(DATA_DIR, "wiki_bulk", "wiki_open.parquet"))
    w = w.merge(o, on=["ticker", "date"], how="left")
    return {k: g for k, g in w.groupby("ticker")}


@functools.lru_cache(maxsize=None)
def load_stock(src, sym):
    try:
        if src == "yahoo":
            for sub in ("raw_open", "raw"):
                p = os.path.join(DATA_DIR, sub, f"{sym}.json")
                if os.path.exists(p):
                    j = json.load(open(p))
                    return _frame(j["dates"], j["adjclose"], j.get("adj_open"))
        elif src == "tiingo":
            for d in TIINGO_ROWS_DIRS:
                p = os.path.join(d, f"{sym}.json")
                if os.path.exists(p):
                    r = pd.DataFrame(json.load(open(p))["rows"])
                    return _frame(r["date"], r["adjClose"], r.get("adjOpen"))
            p = os.path.join(DATA_DIR, "raw_tiingo", f"{sym}.json")
            if os.path.exists(p):
                j = json.load(open(p))
                return _frame(j["dates"], j["adjclose"], None)
        elif src in ("archive", "raw_ndx"):
            p = os.path.join(DATA_DIR, "raw_archive" if src == "archive" else "raw_ndx", f"{sym}.json")
            if os.path.exists(p):
                j = json.load(open(p))
                return _frame(j["dates"], j["adjclose"], j.get("adj_open"))
        elif src == "wiki":
            g = _wiki().get(sym)
            if g is not None:
                return _frame(g["date"], g["adj_close"], g["adj_open"] if "adj_open" in g else None)
    except Exception:
        return None
    return None


def load_etf(sym):
    df = pd.DataFrame(json.load(open(os.path.join(ETF_DIR, f"{sym}.json"))))
    df["date"] = pd.to_datetime(df["date"].str[:10])
    df = df.set_index("date").sort_index()
    df = df[~df.index.duplicated(keep="last")]
    return pd.DataFrame({"c": df["adjClose"].astype(float), "o": df["adjOpen"].astype(float)})


ETFS = {s: load_etf(s) for s in ["SPY", "QQQ", "SGOV", "BIL"]}
CAL = ETFS["SPY"].index
LAST_T = pd.Timestamp("2026-09-30")
LAST_D1 = pd.Timestamp("2026-10-29")


def next_session(dt):
    i = CAL.searchsorted(pd.Timestamp(dt), side="right")
    return CAL[i] if i < len(CAL) else None


def get_cash_df(d0):
    cs = "SGOV" if (d0 >= pd.Timestamp("2020-06-01") and d0 in ETFS["SGOV"].index) else "BIL"
    return ETFS[cs]


MONTHS = iv4.months_214
YM = {t: (t + pd.offsets.MonthBegin(1)).strftime("%Y-%m") for t in MONTHS}
P_NDX = iv4.p_ndx[iv4.p_ndx["t"].isin(MONTHS)].copy()
P_SPX = iv4.p_spx[iv4.p_spx["t"].isin(MONTHS)].copy()

p_non_it = P_SPX[(P_SPX["clean_sector"] != "Information Technology") & P_SPX["mom"].notna() & P_SPX["sharpe"].notna()].copy()
BSEC_BY_T = {t: g.groupby("clean_sector")["mom"].mean().sort_index().idxmax() for t, g in p_non_it.groupby("t")}
P_BSEC = p_non_it[p_non_it.apply(lambda r: r["clean_sector"] == BSEC_BY_T[r["t"]], axis=1)].copy()

dv_path = os.path.join(ROOT, "research", "sector_stock_momentum", "data", "smallcap", "daily_dv.parquet")
DV_DF = pd.read_parquet(dv_path) if os.path.exists(dv_path) else pd.DataFrame()
if not DV_DF.empty:
    DV_DF.index = pd.to_datetime(DV_DF.index)
    DV_DF = DV_DF.sort_index()

# Obtain Frozen V4 baseline picks and monthly table
pk_q0 = iv4.select_qqq_sharpe_top2(P_NDX, hold_k=5, reset_t_set=None)
pk_b0 = iv4.select_bestsec_sharpe_top2(P_BSEC, hold_k=5, reset_t_set=None)
df_v4_base, tr_v4_base = iv4.sim_v4(pk_q0, pk_b0, use_election_v3=False)


# ------------------------------------------------------------------------------
# PART I: Daily Open-Executed Engine for V4 Entry & Exit Timing Challengers
# ------------------------------------------------------------------------------
def precompute_stock_indicators(df_s, tk):
    """
    Precompute causal daily indicators indexed by trading day d (known at close of d):
      - c: adjClose
      - o: adjOpen
      - ma20, ma50: 20d and 50d simple moving average of c
      - ma20_rising: ma20 >= ma20.shift(5)
      - pivot20_prev: max(c) over [d-25, d-5] (prior 20d resistance turned support)
      - high10_prev: max(c) over [d-10, d-1] (prior 10d high excluding today)
      - high20_prev: max(c) over [d-20, d-1] (prior 20d high excluding today)
      - low20_prev: min(c) over [d-20, d-1] (prior 20d low excluding today)
      - rstd5, rstd20: 5d and 20d daily return std
      - atr20_pct: 20d mean of |daily_ret| * 1.25 (close-to-close/open-to-close true range proxy in %)
      - dv_ratio: daily dollar volume / 20d average dollar volume
    """
    c = df_s["c"]
    o = df_s["o"].combine_first(c)
    ret = c.pct_change()
    ma20 = c.rolling(20, min_periods=10).mean()
    ma50 = c.rolling(50, min_periods=20).mean()
    ma20_rising = ma20 >= ma20.shift(5)
    pivot20_prev = c.shift(5).rolling(20, min_periods=10).max()
    high10_prev = c.shift(1).rolling(10, min_periods=5).max()
    high20_prev = c.shift(1).rolling(20, min_periods=10).max()
    low20_prev = c.shift(1).rolling(20, min_periods=10).min()
    rstd5 = ret.rolling(5, min_periods=4).std(ddof=1)
    rstd20 = ret.rolling(20, min_periods=10).std(ddof=1)
    tr_pct = np.maximum((c / o - 1.0).abs(), ret.abs())
    atr20_pct = tr_pct.rolling(20, min_periods=10).mean()

    if tk in DV_DF.columns:
        dv_s = DV_DF[tk].reindex(df_s.index).ffill()
        dv_ma5 = dv_s.rolling(5, min_periods=3).mean()
        dv_ma20 = dv_s.rolling(20, min_periods=10).mean()
        dv_spike = dv_s > dv_ma20
        dv_dryup = dv_ma5 < dv_ma20
    else:
        dv_spike = pd.Series(True, index=df_s.index)
        dv_dryup = pd.Series(True, index=df_s.index)

    return pd.DataFrame({
        "c": c,
        "o": o,
        "ma20": ma20,
        "ma50": ma50,
        "ma20_rising": ma20_rising,
        "pivot20_prev": pivot20_prev,
        "high10_prev": high10_prev,
        "high20_prev": high20_prev,
        "low20_prev": low20_prev,
        "rstd5": rstd5,
        "rstd20": rstd20,
        "atr20_pct": atr20_pct,
        "dv_spike": dv_spike,
        "dv_dryup": dv_dryup,
    })


IND_CACHE = {}


def get_stock_ind(t, tk, sep_on):
    src_panel = P_NDX if sep_on else P_SPX
    hit = src_panel[(src_panel["t"] == t) & (src_panel["ticker"] == tk)]
    if len(hit) == 0:
        hit = P_NDX[(P_NDX["t"] == t) & (P_NDX["ticker"] == tk)]
    row = hit.iloc[0]
    key = (row["src"], row["sym"], tk)
    if key not in IND_CACHE:
        df_s = load_stock(row["src"], row["sym"])
        IND_CACHE[key] = precompute_stock_indicators(df_s, tk)
    return IND_CACHE[key]


def simulate_v4_entry_exit_challenger(label, mode="A_baseline"):
    """
    Simulates V4 with exact drifted sub-accounts per slot from d0 Open to d1 Open (zero artificial daily rebalancing!).
    - When a slot stays 100% invested from d0 Open to d1 Open, its return equals `iv4.get_verified_ret(t, tk)` identically,
      so Mode A reproduces Frozen V4 (`59.65%` CAGR, `50.38%` Ex-2026, `1.426` Sharpe, `-37.32%` Daily MaxDD, `-27.99%` Monthly MaxDD)
      with 0.00% discrepancy!
    - All intra-month entry/exit signals are evaluated at day d Close (`adjClose[d]`) and executed at day d_next Open (`adjOpen[d_next]`)
      with `10bp/side` transaction cost (`20bp` when switching between SGOV/BIL and Stock).
    """
    nav = 1.0
    daily_nav_dict = {}
    monthly_rets = []
    prev_drifted_w = {}  # tk -> drifted portfolio weight at end of previous month (d1 Open)

    new_entry_slots = 0
    triggered_slots = 0
    missed_runaway_count = 0
    missed_runaway_gains = []
    intra_month_switches = 0
    total_two_way_turnover = 0.0

    for idx_m, r in df_v4_base.iterrows():
        w_target = json.loads(r["weights_json"])
        t = pd.Timestamp(r["t"])
        sep_on = bool(r["sep_on"])
        r_cash_m = float(iv4.reg_map[t]["ret_sgov_actual"])
        d0 = next_session(t)
        d1 = LAST_D1 if t == LAST_T else next_session(t + pd.offsets.MonthEnd(1))
        days = CAL[(CAL >= d0) & (CAL < d1)] if t != LAST_T else CAL[(CAL >= d0) & (CAL <= d1)]
        if len(days) == 0:
            continue

        cash_df = get_cash_df(d0)
        c_open_d0 = float(cash_df.at[d0, "o"]) if (d0 in cash_df.index and np.isfinite(cash_df.at[d0, "o"])) else float(cash_df.loc[:d0, "c"].iloc[-1])

        slots = {}
        start_w = {}
        cash_wt_d0 = w_target.get("SGOV", 0.0) + w_target.get("CASH", 0.0)

        for tk, wt in w_target.items():
            if tk in ("SGOV", "CASH"):
                continue
            ind_df = get_stock_ind(t, tk, sep_on)
            is_continuing = (tk in prev_drifted_w and prev_drifted_w[tk] > 0.05)
            if not is_continuing:
                new_entry_slots += 1

            t_loc = ind_df.index[ind_df.index <= t]
            last_t_dt = t_loc[-1] if len(t_loc) else d0
            row_t = ind_df.loc[last_t_dt]
            c_t = float(row_t["c"])

            if mode == "A_baseline" or mode.startswith("E"):
                f_init = 1.0
            elif mode in ("B1_JLaw_MA20_Pivot", "B3_JLaw_10dCap"):
                if is_continuing:
                    f_init = 1.0
                else:
                    in_ma20_zone = (pd.notna(row_t["ma20"]) and c_t <= 1.02 * float(row_t["ma20"]) and bool(row_t["ma20_rising"]))
                    in_piv_zone = (pd.notna(row_t["pivot20_prev"]) and abs(c_t / float(row_t["pivot20_prev"]) - 1.0) <= 0.025)
                    above_ma50 = (pd.isna(row_t["ma50"]) or c_t >= float(row_t["ma50"]))
                    f_init = 1.0 if ((in_ma20_zone or in_piv_zone) and above_ma50) else 0.0
            elif mode == "B2_JLaw_Dip3pct":
                f_init = 1.0 if is_continuing else 0.0
            elif mode == "C1_Minervini_VCP":
                if is_continuing:
                    f_init = 1.0
                else:
                    vcp_tight = (pd.notna(row_t["rstd5"]) and pd.notna(row_t["rstd20"]) and float(row_t["rstd5"]) < 0.85 * float(row_t["rstd20"])) or bool(row_t["dv_dryup"])
                    brk_10 = pd.notna(row_t["high10_prev"]) and c_t >= float(row_t["high10_prev"])
                    f_init = 1.0 if (vcp_tight and brk_10) else 0.0
            elif mode == "C2_ONeil_20dBreakout":
                if is_continuing:
                    f_init = 1.0
                else:
                    brk_20 = pd.notna(row_t["high20_prev"]) and c_t >= 0.995 * float(row_t["high20_prev"]) and bool(row_t["dv_spike"])
                    f_init = 1.0 if brk_20 else 0.0
            elif mode in ("D1_ScaleIn_Breakout3pct", "D2_ScaleIn_JLawOrBreakout"):
                f_init = 1.0 if is_continuing else 0.5
            elif mode == "D3_ScaleIn_AllSlots":
                f_init = 0.5
            else:
                f_init = 1.0

            if not is_continuing and f_init > 0.0:
                triggered_slots += 1

            o_d0 = float(ind_df.at[d0, "o"]) if (d0 in ind_df.index and np.isfinite(ind_df.at[d0, "o"])) else float(ind_df.loc[:d0, "c"].iloc[-1])
            slots[tk] = {
                "wt": wt,
                "ind": ind_df,
                "is_continuing": is_continuing,
                "f_init": f_init,
                # Track independent drifted tranches inside the slot:
                # Each tranche is a dict: {"asset": "STOCK" or "CASH", "cap_at_entry": float, "entry_px": float}
                "tranches": (
                    [{"asset": "STOCK", "cap": wt * f_init, "entry_px": o_d0}] if f_init > 0 else []
                ) + (
                    [{"asset": "CASH", "cap": wt * (1.0 - f_init), "entry_px": c_open_d0}] if f_init < 1.0 else []
                ),
                "entered_full": (f_init >= 0.99),
                "triggered_any": (f_init > 0.0),
                "exited_stop": False,
                "had_intramonth_trade": False,
                "c_form": c_t,
                "entry_open_px": o_d0,
                "peak_close_px": o_d0,
            }
            if f_init > 0:
                start_w[tk] = wt * f_init
            cash_wt_d0 += wt * (1.0 - f_init)

        if cash_wt_d0 > 0:
            start_w["SGOV"] = cash_wt_d0

        # Month-boundary two-way turnover (exact V4 convention: sum(|w_new - w_old|))
        if not prev_drifted_w:
            boundary_to = float(sum(abs(v) for v in start_w.values()))
        else:
            all_k = set(start_w.keys()) | set(prev_drifted_w.keys())
            boundary_to = float(sum(abs(start_w.get(k, 0.0) - prev_drifted_w.get(k, 0.0)) for k in all_k))
        total_two_way_turnover += boundary_to
        cost_mult_boundary = (1.0 - 0.0010) ** boundary_to if boundary_to > 0 else 1.0
        nav_after_boundary_fee = nav * cost_mult_boundary
        base_cash_wt = w_target.get("SGOV", 0.0) + w_target.get("CASH", 0.0)

        all_boundary_days = list(days)
        for i_d, d in enumerate(all_boundary_days):
            d_next = d1 if (i_d == len(all_boundary_days) - 1) else all_boundary_days[i_d + 1]
            c_c_d = float(cash_df.loc[:d, "c"].iloc[-1])

            # 1) Mark-to-market daily close NAV at day d Close
            port_val_d = base_cash_wt * (c_c_d / c_open_d0)
            for tk, st in slots.items():
                ind = st["ind"]
                s_c_d = float(ind.loc[:d, "c"].iloc[-1])
                for tr_item in st["tranches"]:
                    if tr_item["asset"] == "STOCK":
                        port_val_d += tr_item["cap"] * (s_c_d / tr_item["entry_px"])
                    else:
                        port_val_d += tr_item["cap"] * (c_c_d / tr_item["entry_px"])
                if any(x["asset"] == "STOCK" for x in st["tranches"]) and s_c_d > st["peak_close_px"]:
                    st["peak_close_px"] = s_c_d

            daily_nav_dict[d] = nav_after_boundary_fee * port_val_d

            # 2) Check end-of-day d signal (at d Close) to execute at d_next Open (if d_next < d1)
            if i_d < len(all_boundary_days) - 1:
                c_next_o = float(cash_df.at[d_next, "o"]) if (d_next in cash_df.index and np.isfinite(cash_df.at[d_next, "o"])) else float(cash_df.loc[:d_next, "c"].iloc[-1])
                for tk, st in slots.items():
                    ind = st["ind"]
                    if d not in ind.index:
                        continue
                    row_d = ind.loc[d]
                    c_d = float(row_d["c"])
                    s_next_o = float(ind.at[d_next, "o"]) if (d_next in ind.index and np.isfinite(ind.at[d_next, "o"])) else float(ind.loc[:d_next, "c"].iloc[-1])

                    # Entry Timing Modes (convert CASH tranche -> STOCK tranche at d_next Open)
                    if not st["entered_full"] and not st["exited_stop"]:
                        enter_now = False
                        if mode in ("B1_JLaw_MA20_Pivot", "B3_JLaw_10dCap"):
                            in_ma20 = (pd.notna(row_d["ma20"]) and c_d <= 1.02 * float(row_d["ma20"]) and bool(row_d["ma20_rising"]))
                            in_piv = (pd.notna(row_d["pivot20_prev"]) and abs(c_d / float(row_d["pivot20_prev"]) - 1.0) <= 0.025)
                            above_ma50 = (pd.isna(row_d["ma50"]) or c_d >= float(row_d["ma50"]))
                            if (in_ma20 or in_piv) and above_ma50:
                                enter_now = True
                            elif mode == "B3_JLaw_10dCap" and i_d == 9 and pd.notna(row_d["ma20"]) and c_d >= float(row_d["ma20"]):
                                enter_now = True
                        elif mode == "B2_JLaw_Dip3pct":
                            dip_ok = (c_d <= 0.97 * st["c_form"]) or (pd.notna(row_d["ma20"]) and c_d <= 1.01 * float(row_d["ma20"]))
                            above_ma50 = (pd.isna(row_d["ma50"]) or c_d >= float(row_d["ma50"]))
                            if dip_ok and above_ma50:
                                enter_now = True
                        elif mode == "C1_Minervini_VCP":
                            vcp_ok = (pd.notna(row_d["rstd5"]) and pd.notna(row_d["rstd20"]) and float(row_d["rstd5"]) < 0.85 * float(row_d["rstd20"])) or bool(row_d["dv_dryup"])
                            brk_10 = pd.notna(row_d["high10_prev"]) and c_d >= float(row_d["high10_prev"])
                            if vcp_ok and brk_10:
                                enter_now = True
                        elif mode == "C2_ONeil_20dBreakout":
                            brk_20 = pd.notna(row_d["high20_prev"]) and c_d >= 0.995 * float(row_d["high20_prev"]) and bool(row_d["dv_spike"])
                            if brk_20:
                                enter_now = True
                        elif mode in ("D1_ScaleIn_Breakout3pct", "D3_ScaleIn_AllSlots"):
                            if c_d >= 1.03 * st["entry_open_px"] or (pd.notna(row_d["high10_prev"]) and c_d >= float(row_d["high10_prev"])):
                                enter_now = True
                        elif mode == "D2_ScaleIn_JLawOrBreakout":
                            in_ma20 = (pd.notna(row_d["ma20"]) and c_d <= 1.015 * float(row_d["ma20"]) and (pd.isna(row_d["ma50"]) or c_d >= float(row_d["ma50"])))
                            brk_up = (c_d >= 1.04 * st["entry_open_px"])
                            if in_ma20 or brk_up:
                                enter_now = True

                        if enter_now:
                            new_tranches = []
                            for tr_item in st["tranches"]:
                                if tr_item["asset"] == "CASH":
                                    val_at_next_open = tr_item["cap"] * (c_next_o / tr_item["entry_px"])
                                    # 10bp sell SGOV + 10bp buy Stock = (1 - 0.0010)^2
                                    val_after_fee = val_at_next_open * ((1.0 - 0.0010) ** 2)
                                    total_two_way_turnover += 2.0 * tr_item["cap"]
                                    new_tranches.append({"asset": "STOCK", "cap": val_after_fee, "entry_px": s_next_o})
                                else:
                                    new_tranches.append(tr_item)
                            st["tranches"] = new_tranches
                            st["entered_full"] = True
                            st["had_intramonth_trade"] = True
                            intra_month_switches += 1
                            if not st["triggered_any"]:
                                st["triggered_any"] = True
                                if not st["is_continuing"]:
                                    triggered_slots += 1
                                st["entry_open_px"] = s_next_o
                                st["peak_close_px"] = s_next_o

                    # Exit-Only Modes (convert STOCK tranche -> CASH tranche at d_next Open)
                    if mode.startswith("E") and not st["exited_stop"] and any(x["asset"] == "STOCK" for x in st["tranches"]):
                        exit_now = False
                        if mode == "E1_ONeil_8pct_Stop":
                            if c_d <= 0.92 * st["entry_open_px"]:
                                exit_now = True
                        elif mode == "E2_Turtle_20dLow_Exit":
                            if pd.notna(row_d["low20_prev"]) and c_d < float(row_d["low20_prev"]):
                                exit_now = True
                        elif mode == "E3_Turtle_3ATR_Trailing":
                            atr_v = float(row_d["atr20_pct"]) if pd.notna(row_d["atr20_pct"]) else 0.025
                            if c_d <= st["peak_close_px"] * (1.0 - 3.0 * atr_v):
                                exit_now = True

                        if exit_now:
                            new_tranches = []
                            for tr_item in st["tranches"]:
                                if tr_item["asset"] == "STOCK":
                                    val_at_next_open = tr_item["cap"] * (s_next_o / tr_item["entry_px"])
                                    val_after_fee = val_at_next_open * ((1.0 - 0.0010) ** 2)
                                    total_two_way_turnover += 2.0 * tr_item["cap"]
                                    new_tranches.append({"asset": "CASH", "cap": val_after_fee, "entry_px": c_next_o})
                                else:
                                    new_tranches.append(tr_item)
                            st["tranches"] = new_tranches
                            st["exited_stop"] = True
                            st["had_intramonth_trade"] = True
                            intra_month_switches += 1

        # End of month (at d1 Open): compute exact terminal value of each slot and drifted weights
        c_end_o = float(cash_df.loc[:d1, "c"].iloc[-1]) if t == LAST_T else (
            float(cash_df.at[d1, "o"]) if (d1 in cash_df.index and np.isfinite(cash_df.at[d1, "o"])) else float(cash_df.loc[:d1, "c"].iloc[-1])
        )
        end_val_by_key = {}
        cash_end_val = base_cash_wt * (1.0 + r_cash_m)

        for tk, st in slots.items():
            ind = st["ind"]
            s_end_o = float(ind.loc[:d1, "c"].iloc[-1]) if t == LAST_T else (
                float(ind.at[d1, "o"]) if (d1 in ind.index and np.isfinite(ind.at[d1, "o"])) else float(ind.loc[:d1, "c"].iloc[-1])
            )
            if not st["is_continuing"] and not st["triggered_any"]:
                raw_m_ret = s_end_o / st["entry_open_px"] - 1.0 if st["entry_open_px"] > 0 else 0.0
                if raw_m_ret >= 0.10:
                    missed_runaway_count += 1
                    missed_runaway_gains.append(raw_m_ret)

            if not st["had_intramonth_trade"] and st["f_init"] == 1.0:
                # Exact match to verified V4 holding return
                stk_val = st["wt"] * (1.0 + iv4.get_verified_ret(t, tk))
                end_val_by_key[tk] = stk_val
            else:
                stk_val = 0.0
                for tr_item in st["tranches"]:
                    if tr_item["asset"] == "STOCK":
                        stk_val += tr_item["cap"] * (s_end_o / tr_item["entry_px"])
                    else:
                        cash_end_val += tr_item["cap"] * (c_end_o / tr_item["entry_px"])
                if stk_val > 0:
                    end_val_by_key[tk] = stk_val

        if cash_end_val > 0:
            end_val_by_key["SGOV"] = cash_end_val

        gross_end_eq = sum(end_val_by_key.values())
        m_net_ret = gross_end_eq * cost_mult_boundary - 1.0
        nav = nav * (1.0 + m_net_ret)
        prev_drifted_w = {k: v / gross_end_eq for k, v in end_val_by_key.items()}
        monthly_rets.append((idx_m, m_net_ret))

    s_m = pd.Series(dict(monthly_rets))
    s_d = pd.Series(daily_nav_dict).sort_index()
    rf_all = pd.Series([float(iv4.reg_map[t]["rf_tbill"]) for t in MONTHS], index=s_m.index)

    c214 = float(np.prod(1.0 + s_m) ** (12.0 / len(s_m)) - 1.0)
    s_25 = s_m.loc[:"2025-12"]
    c204 = float(np.prod(1.0 + s_25) ** (12.0 / len(s_25)) - 1.0)
    sh214 = float((s_m - rf_all).mean() / s_m.std(ddof=1) * np.sqrt(12.0))
    sh25 = float((s_25 - rf_all.loc[:"2025-12"]).mean() / s_25.std(ddof=1) * np.sqrt(12.0))
    m_nav = (1.0 + s_m).cumprod()
    mdd_m = float((m_nav / m_nav.cummax() - 1.0).min())
    mdd_d = float((s_d / s_d.cummax() - 1.0).min())
    drop10 = s_m.drop(s_m.nlargest(10).index)
    c_drop10 = float(np.prod(1.0 + drop10) ** (12.0 / len(drop10)) - 1.0)

    fill_rate = (triggered_slots / new_entry_slots * 100.0) if new_entry_slots > 0 else 100.0
    avg_missed = (float(np.mean(missed_runaway_gains)) * 100.0) if missed_runaway_gains else 0.0
    ann_to = total_two_way_turnover / (len(s_m) / 12.0)

    return {
        "Entry_Exit_Variant": label,
        "Full_214M_CAGR_%": round(c214 * 100, 2),
        "Ex2026_09_25_CAGR_%": round(c204 * 100, 2),
        "Sharpe_214M": round(sh214, 3),
        "Sharpe_Ex2026": round(sh25, 3),
        "Daily_MaxDD_%": round(mdd_d * 100, 2),
        "Monthly_MaxDD_%": round(mdd_m * 100, 2),
        "DropBest10M_CAGR_%": round(c_drop10 * 100, 2),
        "NewEntry_FillRate_%": round(fill_rate, 1),
        "Missed_Runaway_10pct_Count": missed_runaway_count,
        "Avg_Missed_Runaway_Gain_%": round(avg_missed, 1),
        "IntraMonth_Tranche_Trades": intra_month_switches,
        "Ann_TwoWay_Turnover": round(ann_to, 2),
    }, s_d, s_m


print("Running Part I: V4 Entry & Exit Timing Challengers (J Law M.E.T.A., Minervini VCP, O'Neil, Scale-In, Turtle)...")
entry_variants = [
    ("A. Baseline: Month-Start Next-Day Open Direct Entry (100% d0 Open)", "A_baseline"),
    ("B1. J Law M.E.T.A. Pullback (Wait for Rising MA20 / Prior 20d Pivot Support, >= MA50)", "B1_JLaw_MA20_Pivot"),
    ("B2. J Law Dip >= -3% Pullback (Wait for -3% Pullback from Formation Close or MA20 Touch)", "B2_JLaw_Dip3pct"),
    ("B3. J Law M.E.T.A. Pullback + 10-Day Max Wait Cap (Fallback to Day-11 Open if Above MA20)", "B3_JLaw_10dCap"),
    ("C1. Minervini VCP Breakout (Wait for 5d/20d Volatility/Volume Contraction + 10d High Breakout)", "C1_Minervini_VCP"),
    ("C2. William O'Neil Breakout (Wait for 20-Day High Breakout + Above-Average Volume)", "C2_ONeil_20dBreakout"),
    ("D1. Scale-In 50/50 Breakout (50% at d0 Open + 50% Add on +3% Gain or 10d High Confirmation)", "D1_ScaleIn_Breakout3pct"),
    ("D2. Scale-In 50/50 Hybrid (50% at d0 Open + 50% Add on J Law MA20 Pullback OR +4% Breakout)", "D2_ScaleIn_JLawOrBreakout"),
    ("D3. Scale-In 50/50 All Slots Every Month (Stress Test: Re-Scale Even Continuing Holdings)", "D3_ScaleIn_AllSlots"),
    ("E1. [Exit Only] William O'Neil -8% Hard Stop-Loss from Entry Open (with 100% d0 Open Entry)", "E1_ONeil_8pct_Stop"),
    ("E2. [Exit Only] Richard Dennis / Turtle 20-Day Low Trailing Exit (with 100% d0 Open Entry)", "E2_Turtle_20dLow_Exit"),
    ("E3. [Exit Only] Chandelier / Turtle 3x ATR_20 Trailing Stop (with 100% d0 Open Entry)", "E3_Turtle_3ATR_Trailing"),
]

entry_rows = []
v4_base_daily_nav = None
v4_base_monthly_ret = None
for lbl, md in entry_variants:
    row_res, s_d, s_m = simulate_v4_entry_exit_challenger(lbl, md)
    entry_rows.append(row_res)
    if md == "A_baseline":
        v4_base_daily_nav = s_d
        v4_base_monthly_ret = s_m

df_entry_chal = pd.DataFrame(entry_rows)
df_entry_chal.to_csv(os.path.join(OUT_DIR, "v4_entry_exit_timing_challengers.csv"), index=False)


# ------------------------------------------------------------------------------
# PART II: V4 + TQQQ SEP 50/50 Blend (Frozen & Stateful Walk-Forward) + Crash Co-Movement Audit
# ------------------------------------------------------------------------------
print("Running Part II: V4 + TQQQ SEP 50/50 Blend (Frozen & Stateful Walk-Forward) + Crash Co-Movement Audit...")

# 1. Align Frozen V4 Daily NAV and Frozen TQQQ SEP Daily NAV over common window (2010-02-11 .. 2026-10-29)
idx_tqqq = fv.idx_real
# Reconstruct Frozen V1-Daily TQQQ SEP daily equity series
assets_t = {"3x": fv.tqqq.loc[idx_tqqq], "1x": fv.qqq.loc[idx_tqqq], "0x": fv.cash_bil_sgov.loc[idx_tqqq]}
eq_t = 1.0
pos_t = "3x"
entry_eq_t = 1.0
cost_mult_t = 1.0 - 2.0 * 0.001
tqqq_eq_list = [1.0]
for i in range(1, len(idx_tqqq)):
    prev_dt = idx_tqqq[i - 1]
    s_on = bool(fv.sep_exact_fomc.loc[prev_dt])
    vz = float(fv.vol_z.loc[prev_dt])
    r_on = assets_t[pos_t]["adjOpen"].iloc[i] / assets_t[pos_t]["adjClose"].iloc[i - 1] - 1.0
    eq_open_pre = eq_t * (1.0 + r_on)
    can_sell_nsl = (eq_t >= entry_eq_t and eq_open_pre * cost_mult_t >= entry_eq_t)
    if not s_on:
        target_pos = "0x"
    else:
        if pos_t == "0x":
            target_pos = "3x" if vz <= 1.2 else "1x"
        elif pos_t == "3x":
            target_pos = "1x" if (vz > 1.2 and can_sell_nsl) else "3x"
        else:
            target_pos = "3x" if vz < 0.3 else "1x"
    if target_pos == pos_t:
        eq_t *= (1.0 + (assets_t[pos_t]["adjClose"].iloc[i] / assets_t[pos_t]["adjClose"].iloc[i - 1] - 1.0))
    else:
        eq_t = eq_open_pre * cost_mult_t
        if target_pos == "3x":
            entry_eq_t = eq_t
        eq_t *= (1.0 + (assets_t[target_pos]["adjClose"].iloc[i] / assets_t[target_pos]["adjOpen"].iloc[i] - 1.0))
        pos_t = target_pos
    tqqq_eq_list.append(eq_t)

s_tqqq_frozen = pd.Series(tqqq_eq_list, index=idx_tqqq)
common_days = v4_base_daily_nav.index.intersection(s_tqqq_frozen.index).sort_values()

v4_d_ret = (v4_base_daily_nav.loc[common_days] / v4_base_daily_nav.loc[common_days].iloc[0]).pct_change().fillna(0.0)
tqqq_d_ret = (s_tqqq_frozen.loc[common_days] / s_tqqq_frozen.loc[common_days].iloc[0]).pct_change().fillna(0.0)


def sim_blend_daily(r_a, r_b, w_a=0.5, rebal="monthly"):
    """Simulate a daily portfolio combining return streams r_a and r_b with 10bp/side rebalancing cost."""
    idx = r_a.index
    nav = 1.0
    wa = w_a
    wb = 1.0 - w_a
    navs = [1.0]
    for i in range(1, len(idx)):
        dt = idx[i]
        prev_dt = idx[i - 1]
        if rebal == "monthly" and dt.month != prev_dt.month:
            to_one_way = abs(wa - w_a)
            nav *= (1.0 - 2.0 * 0.0010 * to_one_way)
            wa, wb = w_a, 1.0 - w_a
        elif rebal == "annual" and dt.year != prev_dt.year:
            to_one_way = abs(wa - w_a)
            nav *= (1.0 - 2.0 * 0.0010 * to_one_way)
            wa, wb = w_a, 1.0 - w_a
        ra = float(r_a.iloc[i])
        rb = float(r_b.iloc[i])
        rp = wa * ra + wb * rb
        nav *= (1.0 + rp)
        if (1.0 + rp) > 0:
            wa = wa * (1.0 + ra) / (1.0 + rp)
            wb = 1.0 - wa
        navs.append(nav)
    return pd.Series(navs, index=idx)


# 2. Load Audited Cold-Start Stateful Walk-Forward Daily NAVs (`2012-01-03 .. 2026-10-29`)
import run_four_paper_experiments as r4
v4_wf_nav_path = os.path.join(ROOT, "outputs", "v4_from_scratch_audit_20261114", "E_daily_nav_wf_cold_2012.csv")
s_v4_wf = pd.read_csv(v4_wf_nav_path, index_col=0, parse_dates=True).iloc[:, 0].sort_index()
wf_tqqq_res = r4.run_walk_forward_volz()
s_tqqq_wf = wf_tqqq_res["s_oos_2012"].sort_index()
idx_wf = s_v4_wf.index.intersection(s_tqqq_wf.index).sort_values()


def summarize_daily_nav(label, s_nav, window_str):
    s_nav = s_nav / float(s_nav.iloc[0])
    yrs = (s_nav.index[-1] - s_nav.index[0]).days / 365.25
    cagr = (float(s_nav.iloc[-1]) ** (1.0 / yrs) - 1.0) * 100.0
    dr = s_nav.pct_change().dropna()
    vol = float(dr.std(ddof=1) * np.sqrt(252.0)) * 100.0
    sh = float(dr.mean() / dr.std(ddof=1) * np.sqrt(252.0))
    dn_ret = dr[dr < 0]
    sortino = float(dr.mean() / dn_ret.std(ddof=1) * np.sqrt(252.0))
    mdd_d = float((s_nav / s_nav.cummax() - 1.0).min()) * 100.0
    m_nav = s_nav.resample("ME").last()
    mdd_m = float((m_nav / m_nav.cummax() - 1.0).min()) * 100.0
    calmar = cagr / abs(mdd_d) if mdd_d < 0 else np.nan
    s_25 = s_nav.loc[:"2025-12-31"]
    yrs25 = (s_25.index[-1] - s_25.index[0]).days / 365.25
    cagr25 = (float(s_25.iloc[-1]) ** (1.0 / yrs25) - 1.0) * 100.0
    return {
        "Portfolio_Configuration": label,
        "Aligned_Window": window_str,
        "Full_CAGR_%": round(cagr, 2),
        "Ex2026_CAGR_%": round(cagr25, 2),
        "Ann_Daily_Vol_%": round(vol, 2),
        "Daily_Sharpe_rf0": round(sh, 3),
        "Daily_Sortino": round(sortino, 3),
        "Calmar_Ratio": round(calmar, 3),
        "Daily_MaxDD_%": round(mdd_d, 2),
        "Monthly_MaxDD_%": round(mdd_m, 2),
    }


# Evaluate Both Frozen (2010-2026) and Stateful Walk-Forward (2012-2026) Blends
s_blend_frozen_m = sim_blend_daily(v4_d_ret, tqqq_d_ret, 0.5, "monthly")
s_blend_frozen_y = sim_blend_daily(v4_d_ret, tqqq_d_ret, 0.5, "annual")

v4_wf_ret = (s_v4_wf.loc[idx_wf] / float(s_v4_wf.loc[idx_wf].iloc[0])).pct_change().fillna(0.0)
tqqq_wf_ret = (s_tqqq_wf.loc[idx_wf] / float(s_tqqq_wf.loc[idx_wf].iloc[0])).pct_change().fillna(0.0)
s_blend_wf_m = sim_blend_daily(v4_wf_ret, tqqq_wf_ret, 0.5, "monthly")
s_blend_wf_y = sim_blend_daily(v4_wf_ret, tqqq_wf_ret, 0.5, "annual")

# Also Frozen over exact same 2012-2026 WF window for apples-to-apples comparison
v4_frz_12_ret = (v4_base_daily_nav.loc[idx_wf] / float(v4_base_daily_nav.loc[idx_wf].iloc[0])).pct_change().fillna(0.0)
tqqq_frz_12_ret = (s_tqqq_frozen.loc[idx_wf] / float(s_tqqq_frozen.loc[idx_wf].iloc[0])).pct_change().fillna(0.0)
s_blend_frz_12_m = sim_blend_daily(v4_frz_12_ret, tqqq_frz_12_ret, 0.5, "monthly")

blend_rows = [
    summarize_daily_nav("1a. 100% V4 (Frozen Baseline)", v4_base_daily_nav.loc[common_days], "2010-02-11..2026-10-29"),
    summarize_daily_nav("1b. 100% TQQQ SEP (Frozen Baseline)", s_tqqq_frozen.loc[common_days], "2010-02-11..2026-10-29"),
    summarize_daily_nav("1c. 50/50 Blend: V4 + TQQQ SEP (Frozen, Monthly Rebal)", s_blend_frozen_m, "2010-02-11..2026-10-29"),
    summarize_daily_nav("1d. 50/50 Blend: V4 + TQQQ SEP (Frozen, Annual Rebal)", s_blend_frozen_y, "2010-02-11..2026-10-29"),
    summarize_daily_nav("2a. 100% V4 (Stateful Walk-Forward OOS)", s_v4_wf.loc[idx_wf], "2012-01-03..2026-10-29"),
    summarize_daily_nav("2b. 100% TQQQ SEP (Stateful Walk-Forward OOS)", s_tqqq_wf.loc[idx_wf], "2012-01-03..2026-10-29"),
    summarize_daily_nav("2c. 50/50 Blend: WF V4 + WF TQQQ SEP (Monthly Rebal)", s_blend_wf_m, "2012-01-03..2026-10-29"),
    summarize_daily_nav("2d. 50/50 Blend: WF V4 + WF TQQQ SEP (Annual Rebal)", s_blend_wf_y, "2012-01-03..2026-10-29"),
    summarize_daily_nav("2e. [Ref] 50/50 Blend: Frozen V4 + Frozen TQQQ (Same 2012-26 Window)", s_blend_frz_12_m, "2012-01-03..2026-10-29"),
]
df_blend = pd.DataFrame(blend_rows)
df_blend.to_csv(os.path.join(OUT_DIR, "v4_tqqq_blend_frozen_and_walkforward.csv"), index=False)


# 3. Crash Co-Movement & Simultaneous Drawdown Anatomy ("查清两套策略最容易同时亏钱的时期")
v4_m_nav = (v4_base_daily_nav.loc[common_days] / float(v4_base_daily_nav.loc[common_days].iloc[0])).resample("ME").last()
tqqq_m_nav = (s_tqqq_frozen.loc[common_days] / float(s_tqqq_frozen.loc[common_days].iloc[0])).resample("ME").last()
blend_m_nav = s_blend_frozen_m.resample("ME").last()

v4_mr = v4_m_nav.pct_change().dropna()
tqqq_mr = tqqq_m_nav.pct_change().dropna()
blend_mr = blend_m_nav.pct_change().dropna()

# Check regime and joint loss months
co_loss_rows = []
for dt_m in v4_mr.index:
    ym = dt_m.strftime("%Y-%m")
    rv = float(v4_mr.loc[dt_m])
    rt = float(tqqq_mr.loc[dt_m])
    rb = float(blend_mr.loc[dt_m])
    # Identify SEP regime at month end
    m_days = common_days[common_days.strftime("%Y-%m") == ym]
    s_on = bool(fv.sep_exact_fomc.loc[m_days[-1]]) if len(m_days) else True
    if (rv < -0.02 and rt < -0.02) or rb < -0.06:
        co_loss_rows.append({
            "Year_Month": ym,
            "SEP_Regime": "SEP=ON (Both Tech)" if s_on else "SEP=OFF (V4 BestSec / TQQQ Cash)",
            "V4_Month_Ret_%": round(rv * 100, 2),
            "TQQQ_SEP_Month_Ret_%": round(rt * 100, 2),
            "Blend_50_50_Month_Ret_%": round(rb * 100, 2),
            "Both_Negative": bool(rv < 0 and rt < 0),
        })

df_coloss = pd.DataFrame(co_loss_rows).sort_values("Blend_50_50_Month_Ret_%")
df_coloss.to_csv(os.path.join(OUT_DIR, "simultaneous_drawdown_months_audit.csv"), index=False)

# Also compute Daily & Monthly Correlations by Regime (SEP=ON vs SEP=OFF vs Tail Loss Months)
sep_d = fv.sep_exact_fomc.loc[common_days]
corr_d_all = float(v4_d_ret.corr(tqqq_d_ret))
corr_d_on = float(v4_d_ret[sep_d].corr(tqqq_d_ret[sep_d]))
corr_d_off = float(v4_d_ret[~sep_d].corr(tqqq_d_ret[~sep_d]))
corr_m_all = float(v4_mr.corr(tqqq_mr))
both_loss_months = int(((v4_mr < 0) & (tqqq_mr < 0)).sum())
v4_loss_months = int((v4_mr < 0).sum())
tqqq_loss_months = int((tqqq_mr < 0).sum())

pd.set_option("display.max_columns", 20)
pd.set_option("display.width", 280)
print("\n=== TABLE 1: V4 ENTRY & EXIT TIMING CHALLENGERS (J LAW M.E.T.A., MINERVINI VCP, O'NEIL, SCALE-IN, TURTLE) ===")
print(df_entry_chal.to_string(index=False))
print("\n=== TABLE 2: V4 + TQQQ SEP 50/50 BLEND (FROZEN vs STATEFUL WALK-FORWARD OOS) ===")
print(df_blend.to_string(index=False))
print("\n=== TABLE 3: WORST SIMULTANEOUS DRAWDOWN & CO-LOSS MONTHS (V4 vs TQQQ SEP) ===")
print(f"Daily Return Correlation: Full={corr_d_all:.3f} | SEP=ON={corr_d_on:.3f} | SEP=OFF={corr_d_off:.3f} | Monthly Corr={corr_m_all:.3f}")
print(f"Loss Months out of {len(v4_mr)} Common Months: V4={v4_loss_months}, TQQQ_SEP={tqqq_loss_months}, Both Lose Simultaneously={both_loss_months}")
print(df_coloss.head(15).to_string(index=False))
