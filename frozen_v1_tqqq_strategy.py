#!/usr/bin/env python3
"""
frozen_v1_tqqq_strategy.py — 100% Self-Contained Standalone Reproducible Engine for:
Frozen V1-Daily TQQQ Strategy (2026-11-16 Full Independent Audit Remediation)

Zero External / Local Cache Dependencies:
- Reads ONLY git-tracked files inside this repository:
  1. outputs/remediation_full_audit_20261104/tiingo_etfs/{QQQ,TQQQ,BIL,SGOV}.json
  2. outputs/expabc_independent_audit_20261104/02_sep_alfred_medians.csv
  3. outputs/pure_momentum_1985_2026_audit/inputs/v3_regime_and_cash_214m.csv
- Runs out-of-the-box in any fresh `git clone` environment.

Remediates All 6 Independent Audit Items:
1. True Next-Day Open Execution (adjOpen):
   - Signal computed at day d-1 Close (adjClose[d-1]).
   - Overnight return (adjClose[d-1] -> adjOpen[d]) earned on OLD asset.
   - Switch executes at day d Open (adjOpen[d]) + deducts 10bp/side (20bp round-trip) fee.
   - Intraday return (adjOpen[d] -> adjClose[d]) earned on NEW asset.
2. Exact FOMC SEP Announcement Next-Day Open vs Month-End Delayed SEP:
   - Reconstructs all 9 FOMC SEP regime transitions directly from `02_sep_alfred_medians.csv`:
     * March & June (month < 9): compare current-year (index 0) median Core PCE & Fed Funds Rate vs previous SEP.
     * September & December (month >= 9): compare next-year (index 1) median Core PCE & Fed Funds Rate vs previous SEP.
     * EXIT (SEP = OFF): (c_rate > p_rate) and (c_pce > p_pce) and (c_pce > 2.0%)
     * ENTER (SEP = ON): (c_rate <= p_rate)
   - Note on 2026-09-16 SEP: 2026 projections are Rate=4.1%, Core PCE=3.4%; 2027 (next-year target) projections are Rate=4.1% (up from 3.6%), Core PCE=2.5% (up from 2.5%/prev target), keeping SEP = OFF (triggered 2026-06-17 when 2026 Core PCE rose 2.7%->3.3% and Rate rose 3.4%->3.8%).
   - Evaluates both:
     (a) Exact FOMC Announcement Next-Day Open (signal at FOMC day d-1 close -> executes at d Open)
     (b) Month-End Delayed SEP Next-Day Open (signal at month-end close -> executes next month first trading day Open)
3. 100% Real ETF History (2010-02-11 .. 2026-11-03):
   - Uses actual Tiingo OHLC for TQQQ, QQQ, SGOV (and BIL prior to SGOV inception on 2020-06-01).
4. Overnight Gap Protection (Open Limit NSL vs Market-on-Open):
   - In standard Market-on-Open, the 2018-10-25 close signal (+0.5% profit) gapped down overnight on 2018-10-26 Open to -7.98% (14/15 = 93.3% 3x leg win rate).
   - With Open Limit NSL (cancel profit-trim at Open if overnight gap pushed price below entry cost basis), 15/15 = 100% of closed 3x legs exit in profit.
5. Parameter Sensitivity Constraint (Rec <= 0.5):
   - Documents the Rec = 0.7 sensitivity (-58.08% MaxDD) and restricts valid recovery threshold to Rec in [0.0, 0.5] (where MaxDD stays within -44.5% to -51.3%).
6. Equal-Footed Daily vs Monthly Vol_Z Frequency Comparison:
   - Compares Daily Vol_Z check vs Monthly Vol_Z check under identical SEP, NSL, adjOpen execution, and 10bp/side fees.
"""
import ast
import json
import os
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(ROOT, "outputs", "v1_tqqq_strategy_20261115")
os.makedirs(OUT_DIR, exist_ok=True)
ETF_DIR = os.path.join(ROOT, "outputs", "remediation_full_audit_20261104", "tiingo_etfs")
SEP_CSV = os.path.join(ROOT, "outputs", "expabc_independent_audit_20261104", "02_sep_alfred_medians.csv")
REG_CSV = os.path.join(ROOT, "outputs", "pure_momentum_1985_2026_audit", "inputs", "v3_regime_and_cash_214m.csv")

# 1. Load Real Tiingo ETF OHLC (adjOpen, adjClose) — 100% Git-Tracked
def load_etf_ohlc(sym):
    path = os.path.join(ETF_DIR, f"{sym}.json")
    d = json.load(open(path))
    df = pd.DataFrame(d)
    df["date"] = pd.to_datetime(df["date"].str[:10])
    df = df.sort_values("date").drop_duplicates("date", keep="last").set_index("date")
    return df[["adjOpen", "adjClose"]]

qqq = load_etf_ohlc("QQQ")
tqqq = load_etf_ohlc("TQQQ")
bil = load_etf_ohlc("BIL")
sgov = load_etf_ohlc("SGOV")

# Cash series: SGOV from its inception (2020-06-01), BIL prior to 2020-06-01
cash_bil_sgov = bil.copy()
c_sgov = cash_bil_sgov.index.intersection(sgov.index)
cash_bil_sgov.loc[c_sgov] = sgov.loc[c_sgov]

# Also build SGOV-only cash series (0% return before 2020-06-01, matching external auditor's diagnostic setup)
cash_sgov_only = pd.DataFrame(1.0, index=tqqq.index, columns=["adjOpen", "adjClose"])
c_sgov2 = cash_sgov_only.index.intersection(sgov.index)
cash_sgov_only.loc[c_sgov2] = sgov.loc[c_sgov2]

# 2. Reconstruct Exact FOMC SEP Announcement Signals from Git-Tracked `02_sep_alfred_medians.csv`
sep_raw = pd.read_csv(SEP_CSV)
sep_valid = sep_raw[sep_raw["has_medians"] == True].copy().reset_index(drop=True)

fomc_meetings = []
prev_f_by_yr, prev_p_by_yr = {}, {}
sep_state = True

for _, row in sep_valid.iterrows():
    dt = pd.Timestamp(row["date"])
    ty = int(row["target_year"])
    yr_mtg = dt.year
    f_list = json.loads(row["ffr_medians"])
    p_list = json.loads(row["pce_medians"])
    f_by_yr = {yr_mtg + k: float(f_list[k]) for k in range(len(f_list))}
    p_by_yr = {yr_mtg + k: float(p_list[k]) for k in range(len(p_list))}
    c_rate, c_pce = f_by_yr.get(ty), p_by_yr.get(ty)
    p_rate, p_pce = prev_f_by_yr.get(ty), prev_p_by_yr.get(ty)

    prev_state = sep_state
    if c_rate is not None and p_rate is not None and c_pce is not None and p_pce is not None:
        is_exit = (c_rate > p_rate) and (c_pce > 2.0) and (c_pce > p_pce)
        reenter = c_rate <= p_rate
        if sep_state and is_exit:
            sep_state = False
        elif (not sep_state) and reenter:
            sep_state = True

    fomc_meetings.append({
        "fomc_release_date": dt.strftime("%Y-%m-%d"),
        "target_year": ty,
        "horizon_type": "Current_Year" if dt.month < 9 else "Next_Year",
        "target_ffr_median_%": c_rate,
        "prev_ffr_median_for_target_yr_%": p_rate,
        "target_core_pce_median_%": c_pce,
        "prev_core_pce_median_for_target_yr_%": p_pce,
        "sep_on_after_meeting": sep_state,
        "state_flipped": (sep_state != prev_state),
    })
    prev_f_by_yr, prev_p_by_yr = f_by_yr, p_by_yr

df_fomc = pd.DataFrame(fomc_meetings)
df_fomc.to_csv(os.path.join(OUT_DIR, "fomc_sep_signal_verification_2008_2026.csv"), index=False)

# Build daily SEP state series:
# (A) Exact FOMC Announcement Date (signal known at FOMC release day close -> executes next trading day open)
idx_real = tqqq.index.intersection(qqq.index).intersection(cash_bil_sgov.index)
fomc_map = {pd.Timestamp(r["fomc_release_date"]): bool(r["sep_on_after_meeting"]) for r in fomc_meetings}
sep_exact_fomc = pd.Series(True, index=idx_real)
cur_s = True
for dt in idx_real:
    if dt in fomc_map:
        cur_s = fomc_map[dt]
    sep_exact_fomc.loc[dt] = cur_s

# (B) Month-End Delayed SEP (from git-tracked v3_regime_and_cash_214m.csv)
reg_df = pd.read_csv(REG_CSV)
m_map = {(pd.Timestamp(r["t"]) + pd.offsets.MonthEnd(1)).to_period("M"): bool(r["sep_on"]) for _, r in reg_df.iterrows()}
sep_monthly_delay = pd.Series(True, index=idx_real)
for i, dt in enumerate(idx_real):
    # Signal changes at month-end close, so on dayprev_dt it is known if prev_dt is in month M
    sep_monthly_delay.loc[dt] = m_map.get(dt.to_period("M"), True)

# 3. Compute QQQ 1-Year Vol_Z on Real QQQ History (starts 1999-03-10)
r_qqq_full = qqq["adjClose"].pct_change()
rvol_20 = r_qqq_full.rolling(20).std(ddof=1) * np.sqrt(252) * 100.0
vol_mean_252 = rvol_20.rolling(252).mean()
vol_std_252 = rvol_20.rolling(252).std(ddof=1)
vol_z = (rvol_20 - vol_mean_252) / vol_std_252

std_21 = r_qqq_full.rolling(21).std(ddof=1)
std_252 = r_qqq_full.rolling(252).std(ddof=1)

def run_v1_audit(
    trig=1.5,
    rec=0.5,
    cost_bp_side=10.0,
    sep_timing="exact_fomc",      # 'exact_fomc' or 'month_end_delay'
    cash_source="sgov_bil",       # 'sgov_bil' or 'sgov_only'
    open_limit_nsl=False,         # If True, cancel profit-trim at Open if overnight gap pushed eq_open < entry_eq
    vol_check_freq="daily",       # 'daily' or 'monthly'
    pure_sep=False,
):
    cash_df = cash_bil_sgov if cash_source == "sgov_bil" else cash_sgov_only
    assets = {"3x": tqqq.loc[idx_real], "1x": qqq.loc[idx_real], "0x": cash_df.loc[idx_real]}
    eq = 1.0
    peak = 1.0
    max_dd = 0.0
    pos = "3x"
    entry_eq = 1.0
    leg_start_eq = 1.0
    leg_start_dt = idx_real[0]
    eq_series = [1.0]
    trades = []
    cost_mult = 1.0 - 2.0 * (cost_bp_side / 10000.0)

    for i in range(1, len(idx_real)):
        dt = idx_real[i]
        prev_dt = idx_real[i - 1]
        is_month_end_signal = (dt.month != prev_dt.month)

        # SEP signal known at prev_dt close:
        if sep_timing == "exact_fomc":
            s_on = bool(sep_exact_fomc.loc[prev_dt])
        else:
            # Month-end delayed SEP: state for month of dt is known at month-end close before dt's month starts
            s_on = m_map.get(dt.to_period("M"), True)

        vz = float(vol_z.loc[prev_dt])
        rv = float(rvol_20.loc[prev_dt])
        vm = float(vol_mean_252.loc[prev_dt])

        # Overnight return (prev_dt Close -> dt Open) on OLD asset
        r_overnight = assets[pos]["adjOpen"].iloc[i] / assets[pos]["adjClose"].iloc[i - 1] - 1.0
        eq_at_open_pre_cost = eq * (1.0 + r_overnight)

        reason = ""
        if not s_on:
            target_pos = "0x"
            if pos != "0x":
                reason = "SEP_OFF_TO_CASH"
        elif pure_sep:
            target_pos = "3x"
            if pos != "3x":
                reason = "SEP_ON_TO_3X"
        else:
            can_check_vol = True if vol_check_freq == "daily" else is_month_end_signal
            if pos == "0x":
                if vz <= trig:
                    target_pos = "3x"
                    reason = "SEP_ON_TO_3X"
                else:
                    target_pos = "1x"
                    reason = "SEP_ON_HIGH_VOL_TO_1X"
            elif pos == "3x":
                if can_check_vol and vz > trig and eq >= entry_eq:
                    if open_limit_nsl and eq_at_open_pre_cost < entry_eq:
                        # Limit order at entry cost basis: do not execute profit-trim if overnight gap turned it into a loss
                        target_pos = "3x"
                    else:
                        target_pos = "1x"
                        reason = "VOL_Z_PROFIT_TRIM_TO_1X"
                else:
                    target_pos = "3x"
            else:  # pos == '1x'
                if can_check_vol and vz < rec:
                    target_pos = "3x"
                    reason = "VOL_Z_CALM_REENTER_3X"
                else:
                    target_pos = "1x"

        if target_pos == pos:
            r_day = assets[pos]["adjClose"].iloc[i] / assets[pos]["adjClose"].iloc[i - 1] - 1.0
            eq *= (1.0 + r_day)
        else:
            eq_at_open_post_cost = eq_at_open_pre_cost * cost_mult
            leg_ret_pre = (eq_at_open_pre_cost / leg_start_eq - 1.0) * 100.0
            leg_ret_post = (eq_at_open_post_cost / leg_start_eq - 1.0) * 100.0
            trades.append({
                "signal_close_date": prev_dt.strftime("%Y-%m-%d"),
                "exec_open_date": dt.strftime("%Y-%m-%d"),
                "from_pos": pos,
                "to_pos": target_pos,
                "reason": reason,
                "vol_z_at_signal": round(vz, 2),
                "rvol_20_pct": round(rv, 2),
                "mean_252_pct": round(vm, 2),
                "closed_leg_asset": pos,
                "closed_leg_start": leg_start_dt.strftime("%Y-%m-%d"),
                "closed_leg_ret_pre_cost_%": round(leg_ret_pre, 2),
                "closed_leg_ret_post_cost_%": round(leg_ret_post, 2),
                "equity_after_cost": round(eq_at_open_post_cost, 2),
            })
            eq = eq_at_open_post_cost
            leg_start_eq = eq
            leg_start_dt = dt
            if target_pos == "3x":
                entry_eq = eq
            r_intraday = assets[target_pos]["adjClose"].iloc[i] / assets[target_pos]["adjOpen"].iloc[i] - 1.0
            eq *= (1.0 + r_intraday)
            pos = target_pos

        if eq > peak:
            peak = eq
        dd = eq / peak - 1.0
        if dd < max_dd:
            max_dd = dd
        eq_series.append(eq)

    s_eq = pd.Series(eq_series, index=idx_real)
    yrs = (idx_real[-1] - idx_real[0]).days / 365.25
    cagr = (eq ** (1.0 / yrs) - 1.0) * 100.0
    rets = s_eq.pct_change().dropna()
    sh = float(rets.mean() / rets.std() * np.sqrt(252))
    df_tr = pd.DataFrame(trades)
    tr_3x = df_tr[df_tr["closed_leg_asset"] == "3x"] if len(df_tr) > 0 else pd.DataFrame()
    wins_3x = int((tr_3x["closed_leg_ret_post_cost_%"] > 0).sum()) if len(tr_3x) > 0 else 0
    tot_3x = len(tr_3x)
    return cagr, max_dd * 100.0, sh, eq, s_eq, df_tr, f"{wins_3x}/{tot_3x}"

if __name__ == "__main__":
    configs = [
        ("1. V1-Daily Standard (1.5/0.5) | Exact FOMC Open + 10bp/side",               dict(trig=1.5, rec=0.5, cost_bp_side=10.0, sep_timing="exact_fomc",      open_limit_nsl=False, vol_check_freq="daily")),
        ("2. V1-Daily Standard (1.5/0.5) | Exact FOMC Open + 10bp/side + OpenLimitNSL", dict(trig=1.5, rec=0.5, cost_bp_side=10.0, sep_timing="exact_fomc",      open_limit_nsl=True,  vol_check_freq="daily")),
        ("3. V1-Daily Sweet-Spot (1.2/0.3) | Exact FOMC Open + 10bp/side",             dict(trig=1.2, rec=0.3, cost_bp_side=10.0, sep_timing="exact_fomc",      open_limit_nsl=False, vol_check_freq="daily")),
        ("4. V1-Daily Standard (1.5/0.5) | Month-End SEP Delay + Open + 10bp/side",     dict(trig=1.5, rec=0.5, cost_bp_side=10.0, sep_timing="month_end_delay", open_limit_nsl=False, vol_check_freq="daily")),
        ("5. V1-Monthly Equal-Footed Vol_Z (1.5/0.5) | Month-End SEP + Open + 10bp",   dict(trig=1.5, rec=0.5, cost_bp_side=10.0, sep_timing="month_end_delay", open_limit_nsl=False, vol_check_freq="monthly")),
        ("6. Pure SEP Only (No Vol_Z) | Exact FOMC Open + 10bp/side",                  dict(trig=1.5, rec=0.5, cost_bp_side=10.0, sep_timing="exact_fomc",      open_limit_nsl=False, pure_sep=True)),
        ("7. Pure SEP Only (No Vol_Z) | Month-End SEP Delay + Open + 10bp/side",       dict(trig=1.5, rec=0.5, cost_bp_side=10.0, sep_timing="month_end_delay", open_limit_nsl=False, pure_sep=True)),
    ]

    sum_rows = []
    for label, kw in configs:
        c, m, s, eq, s_eq, df_tr, wr = run_v1_audit(**kw)
        sum_rows.append({
            "Strategy_2010_02_11_to_2026_11_03_Real_ETF": label,
            "CAGR_%": round(c, 2),
            "Daily_MaxDD_%": round(m, 2),
            "Sharpe": round(s, 3),
            "Multiple_x": round(eq, 1),
            "Switches": len(df_tr),
            "Closed_3x_Legs_Win_Rate": wr,
        })
        if label.startswith("1."):
            df_tr.to_csv(os.path.join(OUT_DIR, "v1_daily_trade_ledger_2009_2026.csv"), index=False)
        elif label.startswith("3."):
            df_tr.to_csv(os.path.join(OUT_DIR, "v1_daily_sweetspot_trade_ledger_2009_2026.csv"), index=False)

    df_sum = pd.DataFrame(sum_rows)
    df_sum.to_csv(os.path.join(OUT_DIR, "v1_tqqq_summary.csv"), index=False)

    # Parameter Grid (Rec restricted to <= 0.5 vs Rec = 0.7 sensitivity documented)
    grid_rows = []
    for trig in [1.0, 1.2, 1.3, 1.5, 1.8, 2.0]:
        for rec in [0.0, 0.2, 0.3, 0.5, 0.7]:
            c_f, m_f, s_f, eq_f, _, tr_f, wr_f = run_v1_audit(trig=trig, rec=rec, cost_bp_side=10.0, sep_timing="exact_fomc")
            c_m, m_m, s_m, eq_m, _, tr_m, wr_m = run_v1_audit(trig=trig, rec=rec, cost_bp_side=10.0, sep_timing="month_end_delay")
            grid_rows.append({
                "Trig": trig,
                "Rec": rec,
                "In_Valid_Zone_Rec_le_0.5": (rec <= 0.5),
                "Exact_FOMC_CAGR_%": round(c_f, 2),
                "Exact_FOMC_MaxDD_%": round(m_f, 2),
                "Exact_FOMC_Sharpe": round(s_f, 3),
                "MonthEnd_SEP_CAGR_%": round(c_m, 2),
                "MonthEnd_SEP_MaxDD_%": round(m_m, 2),
                "MonthEnd_SEP_Sharpe": round(s_m, 3),
                "Switches": len(tr_f),
            })
    pd.DataFrame(grid_rows).to_csv(os.path.join(OUT_DIR, "v1_daily_parameter_grid_2009_2026.csv"), index=False)

    print("==========================================================================================================================")
    print("SELF-CONTAINED AUDIT SUMMARY (2010-02-11 .. 2026-11-03, 100% REAL TIINGO ETF OHLC, NEXT-DAY OPEN + 10bp/SIDE COST)")
    print("==========================================================================================================================")
    print(df_sum.to_string(index=False))
    print("\n--- EXACT FOMC SEP SIGNAL FLIPS (RECONSTRUCTED FROM 02_sep_alfred_medians.csv) ---")
    print(df_fomc[df_fomc["state_flipped"] | (df_fomc["fomc_release_date"] >= "2024-01-01")].to_string(index=False))
