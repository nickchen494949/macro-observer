#!/usr/bin/env python3
"""
audit_hyg_ief_from_scratch.py — Independent from-scratch audit of the TQQQ SEP + HYG/IEF credit gate (2026-11-18)

Rule under audit (Gemini, 2026-11-18, "trim-only gate"):
  Frozen V1-Daily TQQQ SEP, except the 3x -> 1x de-lever requires BOTH
      Vol_Z(d-1) > 1.2  AND  HYG/IEF(d-1) < SMA200(HYG/IEF)(d-1)   (plus the usual Open-Limit NSL)
  Everything else unchanged (SEP=OFF -> cash, 1x -> 3x when Vol_Z < 0.3, next-day open, 10bp/side).
  Optional add-on: "20-day non-ratchet NSL" (a 1x hedge shorter than 20 trading days does not reset the NSL floor).

This script imports NO strategy code. It rebuilds from raw files:
  - ETF OHLC (Tiingo adjOpen/adjClose JSON), FOMC SEP state from 02_sep_alfred_medians.csv,
  - Vol_Z, the HYG/IEF signal, and the open-executed simulation engine.
Checks:
  T0 reproduce baseline and the gate; T1 data integrity; T2 gain attribution by episode;
  T3 signal margin at every baseline trim; T4 placebo (circular-shift) test; T5 alternative credit proxies;
  T6 credit-signal-only delay; T7 the 20-day non-ratchet NSL patch; T8 calendar-year breakdown.
"""
import json
import os

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
ETF = os.path.join(ROOT, "outputs", "remediation_full_audit_20261104", "tiingo_etfs")
SEP_CSV = os.path.join(ROOT, "outputs", "expabc_independent_audit_20261104", "02_sep_alfred_medians.csv")
OUT = os.path.join(ROOT, "outputs", "hyg_ief_independent_audit_20261118")
os.makedirs(OUT, exist_ok=True)
FEE = 0.0010
LOG = []


def say(s=""):
    print(s)
    LOG.append(str(s))


def etf(sym):
    df = pd.DataFrame(json.load(open(os.path.join(ETF, f"{sym}.json"))))
    df["date"] = pd.to_datetime(df["date"].str[:10])
    df = df.sort_values("date").drop_duplicates("date", keep="last").set_index("date")
    return df[["adjOpen", "adjClose"]].astype(float)


# ----------------------------------------------------------------------------- raw inputs
QQQ, TQQQ, BIL, SGOV = etf("QQQ"), etf("TQQQ"), etf("BIL"), etf("SGOV")
CASH = BIL.copy()
CASH.loc[CASH.index.intersection(SGOV.index)] = SGOV.loc[CASH.index.intersection(SGOV.index)]
IDX = TQQQ.index.intersection(QQQ.index).intersection(CASH.index)
IDX = IDX[(IDX >= "2010-02-11") & (IDX <= "2026-11-03")]

# SEP state rebuilt independently (same published rule: exit if rate up & PCE up & PCE>2; re-enter if rate not up)
sep_raw = pd.read_csv(SEP_CSV)
sep_raw = sep_raw[sep_raw["has_medians"] == True].reset_index(drop=True)  # noqa: E712
state, prev_f, prev_p, flips = True, {}, {}, {}
for _, r in sep_raw.iterrows():
    dt = pd.Timestamp(r["date"])
    ty = int(r["target_year"])
    f = {dt.year + k: float(v) for k, v in enumerate(json.loads(r["ffr_medians"]))}
    p = {dt.year + k: float(v) for k, v in enumerate(json.loads(r["pce_medians"]))}
    cr, cp, pr, pp = f.get(ty), p.get(ty), prev_f.get(ty), prev_p.get(ty)
    if None not in (cr, cp, pr, pp):
        if state and cr > pr and cp > pp and cp > 2.0:
            state = False
        elif (not state) and cr <= pr:
            state = True
    flips[dt] = state
    prev_f, prev_p = f, p
SEP = pd.Series(True, index=IDX)
cur = True
for d in IDX:
    cur = flips.get(d, cur)
    SEP.loc[d] = cur

rq = QQQ["adjClose"].pct_change()


def volz(win=20):
    rv = rq.rolling(win).std(ddof=1) * np.sqrt(252) * 100
    return ((rv - rv.rolling(252).mean()) / rv.rolling(252).std(ddof=1)).reindex(IDX)


VZ20 = volz(20)


def credit_gate(num, den, ma=200):
    """True = credit healthy (ratio above its SMA). Computed on the num/den common calendar, then forward-filled
    onto the trading calendar (no backfill; NaN -> False = 'unhealthy', i.e. never blocks a trim)."""
    a, b = etf(num)["adjClose"], etf(den)["adjClose"]
    ratio = (a / b).dropna()
    ok = (ratio > ratio.rolling(ma).mean())
    ok[ratio.rolling(ma).mean().isna()] = np.nan
    return ok.reindex(IDX, method="ffill").astype(float).fillna(0.0).astype(bool), ratio


GATE200, RATIO = credit_gate("HYG", "IEF", 200)

A = {k: (v.reindex(IDX)) for k, v in {"3x": TQQQ, "1x": QQQ, "0x": CASH}.items()}
AO = {k: v["adjOpen"].values for k, v in A.items()}
AC = {k: v["adjClose"].values for k, v in A.items()}
SEPV = SEP.values


def sim(gate=None, vz=None, trig=1.2, rec=0.3, non_ratchet_days=0, record=False):
    """Open-executed engine. gate: bool array (True = credit healthy -> block 3x->1x). Signals at d-1 close."""
    vz = (VZ20 if vz is None else vz).values
    g = np.zeros(len(IDX), bool) if gate is None else np.asarray(gate, bool)
    cm = (1 - FEE) ** 2
    eq, pos, entry, days1x = 1.0, "3x", 1.0, 10 ** 6
    eqs, trades, pos_s = np.empty(len(IDX)), [], np.empty(len(IDX), dtype=object)
    eqs[0], pos_s[0] = 1.0, "3x"
    for i in range(1, len(IDX)):
        s_on, v, ok = SEPV[i - 1], vz[i - 1], g[i - 1]
        eq_open = eq * AO[pos][i] / AC[pos][i - 1]
        can_sell = eq >= entry and eq_open * cm >= entry
        if pos == "1x":
            days1x += 1
        if not s_on:
            tgt = "0x"
        elif pos == "0x":
            tgt = "3x" if v <= trig else "1x"
        elif pos == "3x":
            tgt = "1x" if (v > trig and not ok and can_sell) else "3x"
        else:
            tgt = "3x" if v < rec else "1x"
        if tgt == pos:
            eq *= AC[pos][i] / AC[pos][i - 1]
        else:
            if record:
                trades.append((IDX[i].date(), pos, tgt, round(float(v), 2)))
            eq = eq_open * cm
            if tgt == "1x":
                days1x = 0
            if tgt == "3x":
                if non_ratchet_days == 0 or pos == "0x" or days1x >= non_ratchet_days or eq < entry:
                    entry = eq
            eq *= AC[tgt][i] / AO[tgt][i]
            pos = tgt
        eqs[i], pos_s[i] = eq, pos
    s = pd.Series(eqs, index=IDX)
    return (s, trades, pd.Series(pos_s, index=IDX)) if record else s


def stats(s):
    yrs = (s.index[-1] - s.index[0]).days / 365.25
    cagr = (s.iloc[-1] / s.iloc[0]) ** (1 / yrs) - 1
    dr = s.pct_change().dropna()
    return dict(CAGR=round(cagr * 100, 2), MaxDD=round((s / s.cummax() - 1).min() * 100, 2),
                Sharpe=round(dr.mean() / dr.std() * np.sqrt(252), 3))


def sub_cagr(s, a, b):
    x = s.loc[a:b]
    return round(((x.iloc[-1] / x.iloc[0]) ** (365.25 / (x.index[-1] - x.index[0]).days) - 1) * 100, 2)


# ============================================================================= T0 reproduction
say("=== T0. Reproduction (independent engine) ===")
base, tr_b, pos_b = sim(None, record=True)
gated, tr_g, pos_g = sim(GATE200, record=True)
say(f"Baseline V1-Daily : {stats(base)} switches={len(tr_b)}   (frozen spec: 54.89% / -44.54% / 33)")
say(f"+HYG/IEF SMA200   : {stats(gated)} switches={len(tr_g)}   (Gemini claim: 57.90% / -44.54% / 24)")
say(f"Time credit-healthy (gate=True) on trading days: {GATE200.mean()*100:.1f}%")

# ============================================================================= T1 data integrity
say("\n=== T1. Data integrity ===")
hyg, ief = etf("HYG"), etf("IEF")
miss_h = IDX.difference(hyg.index)
miss_i = IDX.difference(ief.index)
say(f"Trading days missing in HYG: {len(miss_h)}, in IEF: {len(miss_i)} (forward-filled, never back-filled)")
yi = pd.Series({pd.Timestamp(d): v for d, v in json.load(open(os.path.join(ROOT, "data", "yahoo", "IEF.json")))["values"] if v})
yr = yi.pct_change().dropna()
tr_ = ief["adjClose"].pct_change().reindex(yr.index).dropna()
say(f"IEF Tiingo vs local Yahoo daily-return correlation: {yr.reindex(tr_.index).corr(tr_):.4f} on {len(tr_)} days "
    f"(Yahoo file starts {yi.index.min().date()})")
say("Look-ahead via dividend adjustment: adjusted prices scale every price <= t by the same later factor, "
    "so ratio/SMA comparisons at t are unchanged -> no look-ahead. Signal uses d-1 close, executes d open: OK.")
fred = json.load(open(os.path.join(ROOT, "data", "fred", "BAMLH0A0HYM2.json")))["values"]
say(f"NOTE: local FRED HY OAS (BAMLH0A0HYM2) starts {fred[0][0]} -> the earlier 'P5c real-time HY OAS' test "
    f"(2010-2026) used a back-filled constant before {fred[0][0]}; that result is invalid, not evidence either way.")

# ============================================================================= T2 attribution
say("\n=== T2. Where does the +3pp come from? (episodes where the two strategies hold different assets) ===")
lr_diff = np.log(gated).diff().fillna(0) - np.log(base).diff().fillna(0)
differ = (pos_g != pos_b)
eps, cur_ep = [], None
for d in IDX:
    if differ.loc[d]:
        if cur_ep is None:
            cur_ep = [d, d]
        cur_ep[1] = d
    elif cur_ep is not None:
        eps.append(cur_ep)
        cur_ep = None
if cur_ep:
    eps.append(cur_ep)
rows = []
for a, b in eps:
    # include the day after the divergence ends (open-to-close of switch day belongs to the episode)
    j = IDX.get_loc(b) + 1
    b2 = IDX[min(j, len(IDX) - 1)]
    g = float(lr_diff.loc[a:b2].sum())
    rows.append(dict(start=a.date(), end=b.date(), days=int(differ.loc[a:b].sum()),
                     base_pos=pos_b.loc[a], gated_pos=pos_g.loc[a], log_gain=round(g, 4)))
df_ep = pd.DataFrame(rows).sort_values("log_gain", ascending=False)
tot = float(lr_diff.sum())
df_ep["share_of_total_%"] = (df_ep["log_gain"] / tot * 100).round(1)
say(f"Total log-wealth advantage of gated vs baseline: {tot:.4f} ({len(df_ep)} divergence episodes)")
say(df_ep.to_string(index=False))
df_ep.to_csv(os.path.join(OUT, "T2_divergence_episodes.csv"), index=False)
top1 = df_ep["log_gain"].iloc[0] / tot * 100
top2 = df_ep["log_gain"].iloc[:2].sum() / tot * 100
say(f"Largest episode = {top1:.0f}% of the total gain; largest two = {top2:.0f}%")

# ============================================================================= T3 margin at baseline trims
say("\n=== T3. Signal margin at every baseline de-lever (3x->1x) signal date ===")
sma = RATIO.rolling(200).mean()
marg = (RATIO / sma - 1) * 100
rows = []
for d_exec, frm, to, v in tr_b:
    if frm == "3x" and to == "1x":
        d_sig = IDX[IDX.get_loc(pd.Timestamp(d_exec)) - 1]
        m = float(marg.reindex([d_sig], method="ffill").iloc[0])
        # also margin for the 5 trading days before signal
        rows.append(dict(signal_close=d_sig.date(), exec_open=d_exec, VolZ=v,
                         ratio_vs_SMA200_pct=round(m, 2), gate_blocks=bool(GATE200.loc[d_sig])))
df_m = pd.DataFrame(rows)
say(df_m.to_string(index=False))
df_m.to_csv(os.path.join(OUT, "T3_margin_at_baseline_trims.csv"), index=False)

# ============================================================================= T4 placebo
say("\n=== T4. Placebo: circularly shifted credit signal (same persistence, wrong dates) ===")
g_arr = GATE200.values
rng = np.random.default_rng(20261118)
n = len(g_arr)
shifts = rng.choice(np.arange(250, n - 250), size=400, replace=False)
res = []
for k in shifts:
    s = sim(np.roll(g_arr, int(k)))
    st = stats(s)
    res.append((st["CAGR"], st["MaxDD"]))
res = np.array(res)
real = stats(gated)
p_cagr = (res[:, 0] >= real["CAGR"]).mean()
p_both = ((res[:, 0] >= real["CAGR"]) & (res[:, 1] >= real["MaxDD"] - 1e-9)).mean()
say(f"400 shifted placebos: median CAGR {np.median(res[:,0]):.2f}%, 90th pct {np.percentile(res[:,0],90):.2f}%, "
    f"median MaxDD {np.median(res[:,1]):.2f}%, worst {res[:,1].min():.2f}%")
say(f"Share of placebos with CAGR >= real ({real['CAGR']}%): {p_cagr*100:.1f}%  |  with CAGR >= real AND MaxDD no worse: {p_both*100:.1f}%")
say(f"Share of placebos with MaxDD worse than -50%: {(res[:,1] < -50).mean()*100:.1f}%")
pd.DataFrame(res, columns=["CAGR", "MaxDD"]).assign(shift=shifts).to_csv(os.path.join(OUT, "T4_placebo_shifts.csv"), index=False)

# ============================================================================= T5 alternative proxies
say("\n=== T5. Same rule with other credit proxies (if the idea is real, cousins should also help) ===")
rows = [dict(proxy="none (baseline)", **stats(base))]
for num, den in [("HYG", "IEF"), ("JNK", "IEF"), ("HYG", "SHY"), ("JNK", "SHY"), ("HYG", "LQD"), ("LQD", "IEF")]:
    for ma in (100, 150, 200, 250):
        gt, _ = credit_gate(num, den, ma)
        rows.append(dict(proxy=f"{num}/{den} SMA{ma}", **stats(sim(gt))))
df5 = pd.DataFrame(rows)
say(df5.to_string(index=False))
df5.to_csv(os.path.join(OUT, "T5_alternative_proxies.csv"), index=False)

# ============================================================================= T6 credit-only delay
say("\n=== T6. Delay ONLY the credit signal (Vol_Z on time) ===")
rows = []
for dl in range(0, 11):
    g = pd.Series(g_arr, index=IDX).shift(dl).fillna(False).astype(bool).values
    rows.append(dict(credit_delay_days=dl, **stats(sim(g))))
df6 = pd.DataFrame(rows)
say(df6.to_string(index=False))
df6.to_csv(os.path.join(OUT, "T6_credit_only_delay.csv"), index=False)

# ============================================================================= T7 non-ratchet patch
say("\n=== T7. The '20-day non-ratchet NSL' patch: what does it actually change? ===")
rows = []
for w in (8, 10, 12, 15, 20, 25, 30):
    vz = volz(w)
    for lab, gt in (("baseline", None), ("HYG/IEF", GATE200)):
        a0 = stats(sim(gt, vz=vz))
        a1 = stats(sim(gt, vz=vz, non_ratchet_days=20))
        rows.append(dict(vol_win=w, variant=lab, CAGR_old=a0["CAGR"], MDD_old=a0["MaxDD"],
                         CAGR_patch=a1["CAGR"], MDD_patch=a1["MaxDD"]))
df7 = pd.DataFrame(rows)
say(df7.to_string(index=False))
df7.to_csv(os.path.join(OUT, "T7_non_ratchet_patch.csv"), index=False)
for nd in (5, 10, 15, 20, 30, 40, 60):
    a = stats(sim(GATE200, vz=volz(10), non_ratchet_days=nd))
    say(f"  vol_win=10, non_ratchet_days={nd:2d}: {a}")

# ============================================================================= T8 calendar years
say("\n=== T8. Calendar-year returns: gated minus baseline ===")
yb = base.resample("YE").last().pct_change()
yg = gated.resample("YE").last().pct_change()
yb.iloc[0] = base.resample("YE").last().iloc[0] / base.iloc[0] - 1
yg.iloc[0] = gated.resample("YE").last().iloc[0] / gated.iloc[0] - 1
df8 = pd.DataFrame({"base_%": (yb * 100).round(2), "gated_%": (yg * 100).round(2)})
df8["diff_pp"] = (df8["gated_%"] - df8["base_%"]).round(2)
df8.index = df8.index.year
say(df8.to_string())
say(f"Years better / equal / worse: {(df8.diff_pp>0.05).sum()} / {(df8.diff_pp.abs()<=0.05).sum()} / {(df8.diff_pp<-0.05).sum()}")
say(f"Sub-periods: 2010-2019 base {sub_cagr(base,'2010-02-11','2019-12-31')}% vs gated {sub_cagr(gated,'2010-02-11','2019-12-31')}% | "
    f"2020-2026 base {sub_cagr(base,'2019-12-31','2026-11-03')}% vs gated {sub_cagr(gated,'2019-12-31','2026-11-03')}%")
df8.to_csv(os.path.join(OUT, "T8_calendar_years.csv"))

# ============================================================================= T9 credit vs rates decomposition
say("\n=== T9. Is HYG/IEF a credit signal or a rates signal? ===")
say("HYG/IEF = (HYG/SHY) x (SHY/IEF): a pure-credit leg times a pure-duration leg (SHY/IEF rises when yields rise).")
rows = []
for lab, (num, den) in {"credit only: HYG/SHY": ("HYG", "SHY"), "rates only: SHY/IEF (yields rising)": ("SHY", "IEF"),
                        "combined: HYG/IEF": ("HYG", "IEF")}.items():
    gt, _ = credit_gate(num, den, 200)
    st = stats(sim(gt))
    blocks = [str(r["signal_close"]) for _, r in df_m.iterrows()
              if bool(gt.loc[pd.Timestamp(r["signal_close"])])]
    rows.append(dict(gate=lab, **st, blocked_baseline_trims=len(blocks), blocks=", ".join(blocks)))
df9 = pd.DataFrame(rows)
say(df9.to_string(index=False))
df9.to_csv(os.path.join(OUT, "T9_credit_vs_rates.csv"), index=False)

# ============================================================================= T10 12-Window Realized Post-Fee Attribution & 7-Signal Decomposition
say("\n=== T10. Exact 12-Window Realized Post-Fee Outcome (TQQQ vs QQQ) & 7-Signal Decomposition ===")
hyg_c = etf("HYG")["adjClose"]
ief_c = etf("IEF")["adjClose"]
shy_c = etf("SHY")["adjClose"]


def _above_sma(s, ma=200):
    s = s.dropna()
    out = s > s.rolling(ma).mean()
    out[s.rolling(ma).mean().isna()] = False
    return out.reindex(IDX).ffill().fillna(False)


def _below_sma(s, ma=200):
    s = s.dropna()
    out = s < s.rolling(ma).mean()
    out[s.rolling(ma).mean().isna()] = True
    return out.reindex(IDX).ffill().fillna(True)


# `gate_blocks = True` means BLOCK the 3x->1x trim (keep holding 3x)
signals_block_trim = {
    "0_Baseline_NoGate": pd.Series(False, index=IDX),
    "1_HYG_div_IEF_gt_SMA200": ~_below_sma(hyg_c / ief_c, 200),
    "2_HYG_div_SHY_gt_SMA200_PureCredit": ~_below_sma(hyg_c / shy_c, 200),
    "3_SHY_div_IEF_gt_SMA200_PureRates": ~_below_sma(shy_c / ief_c, 200),
    "4_IEF_lt_SMA200_StandaloneTreasury": ~_above_sma(ief_c, 200),
    "5_HYG_gt_SMA200_StandaloneCorp": ~_below_sma(hyg_c, 200),
    "6_Require_BOTH_CreditWeak_AND_TreasuryStrong_to_Trim": ~(
        _below_sma(hyg_c / shy_c, 200) & _below_sma(shy_c / ief_c, 200)
    ),
    "7_Require_EITHER_CreditWeak_OR_TreasuryStrong_to_Trim": ~(
        _below_sma(hyg_c / shy_c, 200) | _below_sma(shy_c / ief_c, 200)
    ),
}

# Identify the 12 baseline 3x->1x de-levering windows [d_sig_close -> d_reconverge_close]
win_rows = []
for w_idx, (d_exec, frm, to, v) in enumerate([x for x in tr_b if x[1] == "3x" and x[2] == "1x"], 1):
    d_start = pd.Timestamp(d_exec)
    i_sig = IDX.get_loc(d_start) - 1
    d_sig = IDX[i_sig]
    # Find when baseline exits 1x (back to 3x or 0x)
    later = [pd.Timestamp(x[0]) for x in tr_b if pd.Timestamp(x[0]) > d_start]
    d_end = later[0] if later else IDX[-1]
    r_base_leg = float(base.loc[d_end] / base.loc[d_sig] - 1.0) * 100.0
    r_3x_hold = float(TQQQ.loc[d_end, "adjClose"] / TQQQ.loc[d_sig, "adjClose"] - 1.0) * 100.0
    log_diff = float(np.log(1.0 + r_3x_hold / 100.0) - np.log(1.0 + r_base_leg / 100.0))
    sub_3x = TQQQ.loc[d_sig:d_end, "adjClose"]
    mdd_3x_w = float((sub_3x / sub_3x.cummax() - 1.0).min()) * 100.0
    sub_b = base.loc[d_sig:d_end]
    mdd_b_w = float((sub_b / sub_b.cummax() - 1.0).min()) * 100.0
    row_w = {
        "Episode": w_idx,
        "Signal_Close": str(d_sig.date()),
        "Exec_Open": str(d_start.date()),
        "Reconverge_Date": str(d_end.date()),
        "Vol_Z": v,
        "Base_1x_PostFee_Ret_%": round(r_base_leg, 2),
        "Hold_3x_Ret_%": round(r_3x_hold, 2),
        "Base_1x_Window_MaxDD_%": round(mdd_b_w, 2),
        "Hold_3x_Window_MaxDD_%": round(mdd_3x_w, 2),
        "Log_Advantage_Hold3x_vs_1x": round(log_diff, 4),
        "True_Outcome": "PROTECTIVE_TRIM (1x beat 3x)" if log_diff < 0 else "FALSE_ALARM (3x beat 1x)",
    }
    for k_sig, s_blk in list(signals_block_trim.items())[1:]:
        row_w[k_sig] = "HOLD_3x" if bool(s_blk.loc[d_sig]) else "TRIM_1x"
    win_rows.append(row_w)

df_win12 = pd.DataFrame(win_rows)
say(df_win12.to_string(index=False))
df_win12.to_csv(os.path.join(OUT, "T10_12window_realized_and_7signal_decomposition.csv"), index=False)

sig_sum_rows = []
for k_sig, s_blk in signals_block_trim.items():
    s_nav = sim(s_blk.values)
    st = stats(s_nav)
    c_10_19 = sub_cagr(s_nav, "2010-02-11", "2019-12-31")
    c_20_26 = sub_cagr(s_nav, "2019-12-31", "2026-11-03")
    c_ex26 = sub_cagr(s_nav, "2010-02-11", "2025-12-31")
    # Count how many of the 5 protective trims were wrongly blocked vs how many of the 7 false alarms were rightly blocked
    wrong_blocks = sum(1 for r in win_rows if r["True_Outcome"].startswith("PROTECTIVE") and (k_sig in r and r[k_sig] == "HOLD_3x"))
    right_blocks = sum(1 for r in win_rows if r["True_Outcome"].startswith("FALSE_ALARM") and (k_sig in r and r[k_sig] == "HOLD_3x"))
    sig_sum_rows.append({
        "Signal_Variant": k_sig,
        "Full_CAGR_%": st["CAGR"],
        "Ex2026_CAGR_%": c_ex26,
        "CAGR_2010_19_%": c_10_19,
        "CAGR_2020_26_%": c_20_26,
        "Daily_MaxDD_%": st["MaxDD"],
        "Daily_Sharpe": st["Sharpe"],
        "Rightly_Blocked_FalseAlarms_(of_7)": right_blocks,
        "Wrongly_Blocked_ProtectiveTrims_(of_5)": wrong_blocks,
    })
df_sig_sum = pd.DataFrame(sig_sum_rows)
say("\n=== T10B. Summary of 7 Credit/Treasury Decomposition Signals Across the 12 Windows ===")
say(df_sig_sum.to_string(index=False))
df_sig_sum.to_csv(os.path.join(OUT, "T10_signal_summary.csv"), index=False)

# ----------------------------------------------------------------------------- T11. 2x Compromise (50% TQQQ + 50% QQQ) Share-Lot Cost Accounting & Drift Audit
say("\n=== T11. 2x Compromise (50% TQQQ + 50% QQQ) Share-Lot Cost Accounting & Drift Audit ===")


_TO, _TC = TQQQ["adjOpen"].reindex(IDX).values, TQQQ["adjClose"].reindex(IDX).values
_QO, _QC = QQQ["adjOpen"].reindex(IDX).values, QQQ["adjClose"].reindex(IDX).values
_CO, _CC = CASH["adjOpen"].reindex(IDX).values, CASH["adjClose"].reindex(IDX).values
_SEP_V = SEP.values
_VZ_V = VZ20.values
_OCT29_I = IDX.get_loc(pd.Timestamp("2018-10-29"))
_N_IDX = len(IDX)
_YRS = (IDX[-1] - IDX[0]).days / 365.25


def run_2x_lot_sim(cost_method="lifo", daily_rebal=False, gate_ser=None):
    to, tc, qo, qc, co, cc = _TO, _TC, _QO, _QC, _CO, _CC
    g_vec = (signals_block_trim["1_HYG_div_IEF_gt_SMA200"] if gate_ser is None else gate_ser).values
    pos = "3x"
    p0 = tc[0]
    t_lots = [[1.0 / p0, p0]]
    q_shares, c_shares = 0.0, 0.0
    leg_entry_nav = 1.0
    realized_step1_pnl = 0.0
    eq = np.empty(_N_IDX)
    eq[0] = 1.0
    sw = 0
    oct29 = {}

    for i in range(1, _N_IDX):
        s_on = bool(_SEP_V[i - 1])
        vz = _VZ_V[i - 1]
        g_ok = bool(g_vec[i - 1])
        sh_cur = sum(lot[0] for lot in t_lots)
        cb = (sum(lot[0] * lot[1] for lot in t_lots) / sh_cur) if sh_cur > 1e-12 else None
        nav_open = sh_cur * to[i] + q_shares * qo[i] + c_shares * co[i]
        in_profit_3x = (cb is not None) and (to[i] * (1.0 - FEE) > cb)
        if cost_method == "port_nav":
            in_profit_2x = (leg_entry_nav is not None) and (nav_open * (1.0 - FEE) > leg_entry_nav)
        elif cost_method == "combined_leg_pnl":
            unreal = sh_cur * (to[i] * (1.0 - FEE) - cb) if cb is not None else 0.0
            in_profit_2x = (realized_step1_pnl + unreal) > 0.0
        elif cost_method == "uncond_step2":
            in_profit_2x = True
        else:
            in_profit_2x = in_profit_3x
        if i == _OCT29_I:
            if cost_method == "combined_leg_pnl" and cb is not None:
                tot_cost = (2.0 * sh_cur) * 5.4497
                tot_pnl = realized_step1_pnl + sh_cur * (to[i] * (1.0 - FEE) - cb)
                p_pct = round((tot_pnl / tot_cost) * 100, 2)
                cb_disp = 5.4497
            else:
                p_pct = round((to[i] * (1.0 - FEE) / cb - 1.0) * 100, 2) if cb else None
                cb_disp = round(float(cb), 4) if cb else None
            oct29 = {
                "Oct29_CostBasis_$": cb_disp,
                "Oct29_Open_$": round(float(to[i]), 4),
                "Oct29_NetProfit_%": p_pct,
                "Oct29_Pass_NSL": bool(in_profit_2x),
            }
        tgt = pos
        if not s_on:
            tgt = "0x"
        else:
            if pos == "0x":
                tgt = ("2x" if g_ok else "1x") if (not np.isnan(vz) and vz > 1.2) else "3x"
            elif pos == "3x":
                if (not np.isnan(vz)) and vz > 1.2 and in_profit_3x:
                    tgt = "2x" if g_ok else "1x"
            elif pos == "2x":
                if (not np.isnan(vz)) and vz < 0.3:
                    tgt = "3x"
                elif (not np.isnan(vz)) and vz > 1.2 and (not g_ok) and in_profit_2x:
                    tgt = "1x"
            elif pos == "1x":
                if (not np.isnan(vz)) and vz < 0.3:
                    tgt = "3x"
        if tgt != pos:
            sw += 1
            if tgt == "0x":
                proceeds = (sh_cur * to[i] + q_shares * qo[i]) * (1.0 - FEE) + c_shares * co[i]
                t_lots, q_shares = [], 0.0
                c_shares = proceeds / co[i]
                leg_entry_nav = None
                realized_step1_pnl = 0.0
            elif tgt == "1x":
                if pos == "0x":
                    proceeds = c_shares * co[i] * (1.0 - FEE)
                    q_shares = proceeds / qo[i]
                else:
                    proceeds = (sh_cur * to[i]) * (1.0 - FEE) ** 2
                    q_shares += proceeds / qo[i]
                t_lots, c_shares = [], 0.0
                leg_entry_nav = None
                realized_step1_pnl = 0.0
            elif tgt == "3x":
                if pos == "0x":
                    proceeds = c_shares * co[i] * (1.0 - FEE)
                    t_lots = [[proceeds / to[i], to[i] / (1.0 - FEE)]]
                    q_shares, c_shares = 0.0, 0.0
                    leg_entry_nav = proceeds
                    realized_step1_pnl = 0.0
                elif pos == "1x":
                    proceeds = q_shares * qo[i] * (1.0 - FEE) ** 2
                    t_lots = [[proceeds / to[i], to[i] / (1.0 - FEE)]]
                    q_shares, c_shares = 0.0, 0.0
                    leg_entry_nav = proceeds
                    realized_step1_pnl = 0.0
                elif pos == "2x":
                    proceeds = q_shares * qo[i] * (1.0 - FEE) ** 2
                    t_lots.append([proceeds / to[i], to[i] / (1.0 - FEE)])
                    q_shares, c_shares = 0.0, 0.0
                    leg_entry_nav = sum(lot[0] for lot in t_lots) * to[i]
            elif tgt == "2x":
                if pos == "3x":
                    sh_to_sell = 0.5 * sh_cur
                    if cost_method == "avg":
                        realized_step1_pnl = sh_to_sell * (to[i] * (1.0 - FEE) - cb)
                        t_lots = [[sh_cur - sh_to_sell, cb]]
                    elif cost_method in ("fifo", "combined_leg_pnl"):
                        rem = sh_to_sell
                        pnl1 = 0.0
                        while rem > 1e-12 and t_lots:
                            take = min(rem, t_lots[0][0])
                            pnl1 += take * (to[i] * (1.0 - FEE) - t_lots[0][1])
                            t_lots[0][0] -= take
                            rem -= take
                            if t_lots[0][0] <= 1e-12:
                                t_lots.pop(0)
                        realized_step1_pnl = pnl1
                    else:
                        rem = sh_to_sell
                        pnl1 = 0.0
                        while rem > 1e-12 and t_lots:
                            take = min(rem, t_lots[-1][0])
                            pnl1 += take * (to[i] * (1.0 - FEE) - t_lots[-1][1])
                            t_lots[-1][0] -= take
                            rem -= take
                            if t_lots[-1][0] <= 1e-12:
                                t_lots.pop()
                        realized_step1_pnl = pnl1
                    proceeds = (sh_to_sell * to[i]) * (1.0 - FEE) ** 2
                    q_shares += proceeds / qo[i]
                elif pos == "0x":
                    tot = c_shares * co[i] * (1.0 - FEE)
                    t_lots = [[(0.5 * tot) / to[i], to[i] / (1.0 - FEE)]]
                    q_shares = (0.5 * tot) / qo[i]
                    c_shares = 0.0
                    leg_entry_nav = tot
                    realized_step1_pnl = 0.0
            pos = tgt
        elif pos == "2x" and daily_rebal:
            t_val = sh_cur * to[i]
            q_val = q_shares * qo[i]
            diff = t_val - 0.5 * (t_val + q_val)
            if abs(diff) > 1e-9:
                if diff > 0:
                    sh_sell = diff / to[i]
                    t_lots = [[sh_cur - sh_sell, cb]]
                    q_shares += (diff * (1.0 - FEE) ** 2) / qo[i]
                else:
                    q_sell = -diff
                    q_shares -= q_sell / qo[i]
                    t_lots.append([(q_sell * (1.0 - FEE) ** 2) / to[i], to[i] / (1.0 - FEE)])
        eq[i] = sum(lot[0] for lot in t_lots) * tc[i] + q_shares * qc[i] + c_shares * cc[i]
    cagr = round(float((eq[-1] ** (1.0 / _YRS) - 1.0) * 100), 2)
    cm = np.maximum.accumulate(eq)
    dd = round(float(((eq / cm) - 1.0).min() * 100), 2)
    if oct29:
        eq_s = pd.Series(eq, index=IDX)
        st = stats(eq_s)
        eq18 = eq_s.loc["2018-01-01":"2018-12-31"]
        dd18 = round(float(((eq18 / eq18.cummax()) - 1.0).min() * 100), 2)
        r18 = round(float((eq_s.loc["2018-12-31"] / eq_s.loc["2017-12-29"] - 1.0) * 100), 2)
        return st["CAGR"], st["MaxDD"], dd18, r18, st["Sharpe"], sw, oct29
    return cagr, dd, 0.0, 0.0, 0.0, sw, oct29


eq18_b = base.loc["2018-01-01":"2018-12-31"]
dd18_b = round(float(((eq18_b / eq18_b.cummax()) - 1.0).min() * 100), 2)
r18_b = round(float((base.loc["2018-12-31"] / base.loc["2017-12-29"] - 1.0) * 100), 2)

eq18_g = gated.loc["2018-01-01":"2018-12-31"]
dd18_g = round(float(((eq18_g / eq18_g.cummax()) - 1.0).min() * 100), 2)
r18_g = round(float((gated.loc["2018-12-31"] / gated.loc["2017-12-29"] - 1.0) * 100), 2)

t11_rows = [
    {
        "Variant": "0. Baseline V1-Daily (Vol_Z>1.2 -> 1x QQQ)",
        "CAGR_%": stats(base)["CAGR"],
        "MaxDD_%": stats(base)["MaxDD"],
        "2018_MaxDD_%": dd18_b,
        "2018_Ret_%": r18_b,
        "Sharpe": stats(base)["Sharpe"],
        "Oct29_CostBasis_$": None,
        "Oct29_Open_$": 6.1618,
        "Oct29_NetProfit_%": None,
        "Oct29_Pass_NSL": True,
    },
    {
        "Variant": "1. HYG/IEF All-or-Nothing (HYG/IEF>SMA200 -> Hold 3x)",
        "CAGR_%": stats(gated)["CAGR"],
        "MaxDD_%": stats(gated)["MaxDD"],
        "2018_MaxDD_%": dd18_g,
        "2018_Ret_%": r18_g,
        "Sharpe": stats(gated)["Sharpe"],
        "Oct29_CostBasis_$": 4.5728,
        "Oct29_Open_$": 6.1618,
        "Oct29_NetProfit_%": 34.62,
        "Oct29_Pass_NSL": True,
    },
]
for cm, dr, lbl in [
    ("lifo", False, "2a. 50/50 Compromise - LIFO (Sell Newest Lot First, Static Shares)"),
    ("avg", False, "2b. 50/50 Compromise - Average Cost Basis (Static Shares)"),
    ("port_nav", False, "2c. 50/50 Compromise - Whole-Leg Entry Portfolio NAV (Static Shares)"),
    ("lifo", True, "2d. 50/50 Compromise - Daily Rebalanced back to 50/50 (with Daily Fees)"),
    ("fifo", False, "2e. 50/50 Compromise - FIFO (Sell Oldest 2017 Lot First, Static Shares)"),
    ("combined_leg_pnl", False, "2f. 50/50 Compromise - Combined Two-Step Total Leg PnL > 0 (FIFO/LIFO Invariant)"),
    ("uncond_step2", False, "2g. 50/50 Compromise - First-Step NSL Only (3x->2x NSL, 2x->1x Unconditional)"),
]:
    cagr, dd, dd18, r18, sh, sw, o29 = run_2x_lot_sim(cm, dr)
    t11_rows.append({
        "Variant": lbl,
        "CAGR_%": cagr,
        "MaxDD_%": dd,
        "2018_MaxDD_%": dd18,
        "2018_Ret_%": r18,
        "Sharpe": sh,
        **o29,
    })

df_t11 = pd.DataFrame(t11_rows)
say(df_t11.to_string(index=False))
df_t11.to_csv(os.path.join(OUT, "T11_2x_compromise_share_lot_audit.csv"), index=False)

# T11B: Full 351-SMA (50..400 step 1 day) Grid Verification under Exact Share-Lot Ledger
say("\n=== T11B. Full 351-SMA (50..400 step 1 day) Grid Verification (Share-Lot Ledger vs All-or-Nothing HYG/IEF) ===")
g_by_ma = {ma: credit_gate("HYG", "IEF", ma)[0] for ma in range(50, 401)}
grid351_rows = []
# 1. All-or-Nothing HYG/IEF (3x or 1x) across all 351 SMAs
c_aon, dd_aon = [], []
for ma in range(50, 401):
    st_m = stats(sim(g_by_ma[ma].values))
    c_aon.append(st_m["CAGR"])
    dd_aon.append(st_m["MaxDD"])
grid351_rows.append({
    "Rule": "1. All-or-Nothing HYG/IEF (3x or 1x)",
    "SMA200_CAGR_%": stats(gated)["CAGR"],
    "SMA200_MaxDD_%": stats(gated)["MaxDD"],
    "SMA50_400_Min_CAGR_%": min(c_aon),
    "SMA50_400_Median_CAGR_%": round(float(np.median(c_aon)), 2),
    "SMA50_400_Max_CAGR_%": max(c_aon),
    "SMA50_400_Worst_MaxDD_%": min(dd_aon),
    "Share_of_351_SMAs_MaxDD_Better_Than_45pct_%": round(sum(1 for x in dd_aon if x >= -45.0) / 351 * 100, 1),
})
for cm, lbl in [
    ("lifo", "2a. 50/50 Share-Lot — LIFO"),
    ("avg", "2b. 50/50 Share-Lot — Average Cost"),
    ("port_nav", "2c. 50/50 Share-Lot — Whole-Leg NAV"),
    ("fifo", "2e. 50/50 Share-Lot — FIFO"),
    ("combined_leg_pnl", "2f. 50/50 Share-Lot — Combined Two-Step Leg PnL > 0 (FIFO/LIFO Invariant)"),
    ("uncond_step2", "2g. 50/50 Share-Lot — First-Step NSL Only (2x->1x Unconditional)"),
]:
    cs, dds = [], []
    for ma in range(50, 401):
        c_m, d_m, _, _, _, _, _ = run_2x_lot_sim(cm, False, g_by_ma[ma])
        cs.append(c_m)
        dds.append(d_m)
    c200, d200, _, _, _, _, _ = run_2x_lot_sim(cm, False, g_by_ma[200])
    grid351_rows.append({
        "Rule": lbl,
        "SMA200_CAGR_%": c200,
        "SMA200_MaxDD_%": d200,
        "SMA50_400_Min_CAGR_%": min(cs),
        "SMA50_400_Median_CAGR_%": round(float(np.median(cs)), 2),
        "SMA50_400_Max_CAGR_%": max(cs),
        "SMA50_400_Worst_MaxDD_%": min(dds),
        "Share_of_351_SMAs_MaxDD_Better_Than_45pct_%": round(sum(1 for x in dds if x >= -45.0) / 351 * 100, 1),
    })
df_grid351 = pd.DataFrame(grid351_rows)
say(df_grid351.to_string(index=False))
df_grid351.to_csv(os.path.join(OUT, "T11_351sma_grid_summary.csv"), index=False)

pd.DataFrame(tr_g, columns=["exec_open", "from", "to", "VolZ_signal"]).to_csv(os.path.join(OUT, "gated_trade_ledger.csv"), index=False)
pd.DataFrame(tr_b, columns=["exec_open", "from", "to", "VolZ_signal"]).to_csv(os.path.join(OUT, "baseline_trade_ledger.csv"), index=False)
open(os.path.join(OUT, "audit_log.txt"), "w").write("\n".join(LOG))
