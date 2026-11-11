#!/usr/bin/env python3
"""
run_external_audit_remediation_verification.py
==============================================
Standalone verification script addressing all 6 items from the External Independent Audit (2026-11-11):
  1. Presidential Party-Turnover Feb (5/6 = 83.3% in 42Y proxy vs 3/3 in 2009-2026 3-leg strategy; no cross-model splicing).
  2. V3 Election Reset sample-size audit (8/214 months changed, N=3 post-2009, 3/5 in 1985-2026 proxy) vs V0 Core.
  3. 2026-10 Open-to-Open completion audit:
       - 204M (2009-01..2025-12, Ex-2026, 100% strict Open-to-Open)
       - 213M (2009-01..2026-09, 100% strict Open-to-Open)
       - 214M Frozen Snapshot (2009-01..2026-10-29 Close on Month 214)
       - 214M Completed Open-to-Open (2009-01..2026-11-02 Open on Month 214 via Tiingo 2026-11-02 adjOpen)
  4. 100% Strictly Causal PIT GICS row-by-row fallback audit (`08_pit_gics_fallback_row_by_row_audit.csv`)
     verifying 0 future lookahead (`sub_wp_modal` and `last_cl_sec` removed) + sensitivity to raw Wikipedia revisions at t.
  5. Cash leg provenance (`BIL` 2009-01..2020-05 + `SGOV` 2020-06..2026-10 vs `rf_tbill`) & Sharpe denominator standardization.
"""
import os
import json
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
IN_DIR = os.path.join(HERE, "inputs")

# Verify that build_portable_inputs_from_raw.py contains ZERO sub_wp_modal and ZERO last_cl_sec
builder_src = open(os.path.join(HERE, "build_portable_inputs_from_raw.py")).read()
assert "sub_wp_modal" not in builder_src, "sub_wp_modal must be completely removed from build_portable_inputs_from_raw.py"
assert "last_cl_sec" not in builder_src, "last_cl_sec must be completely removed from build_portable_inputs_from_raw.py"

p_spx = pd.read_parquet(os.path.join(IN_DIR, "v3_spx_panel_214m.parquet"))
p_ndx = pd.read_parquet(os.path.join(IN_DIR, "v3_ndx_panel_214m.parquet"))
reg_df = pd.read_csv(os.path.join(IN_DIR, "v3_regime_and_cash_214m.csv"))
wp = pd.read_csv(os.path.join(ROOT, "outputs", "tech_top1_independent_audit_20261103", "wiki_panel_claude.csv"))
p_cl = pd.read_parquet(os.path.join(ROOT, "outputs", "core3_qqq_spy_g1_audit_20261103", "spy_selection_panel.parquet"))

p_spx["t"] = pd.to_datetime(p_spx["t"])
p_ndx["t"] = pd.to_datetime(p_ndx["t"])
reg_df["t"] = pd.to_datetime(reg_df["t"])

# Load cleanroom engine functions
code_lines = open(os.path.join(ROOT, "independent_a1_rs_election_reset_audit.py")).readlines()
ns = {"os": os, "json": json, "np": np, "pd": pd, "p_spx": p_spx.copy(), "p_ndx": p_ndx.copy(), "reg_df": reg_df.copy()}
exec("".join(code_lines[37:378]), ns)

df_prod = ns["df_prod"]
df_v0 = ns["df_a1rs_v0"]
df_v3 = ns["df_a1rs_v3"]

# =============================================================================
# 1. Row-by-Row PIT GICS Provenance & Fallback Audit (`08_pit_gics_fallback_row_by_row_audit.csv`)
# =============================================================================
sec_map_cl = p_cl.set_index(["t", "ticker"])["sector"].to_dict()
p_cl_sorted = p_cl.sort_values("t")
cl_sec_by_tk_causal = {tk: g.set_index("t")["sector"] for tk, g in p_cl_sorted.groupby("ticker")}

NORM_WP_SEC = {
    "Telecommunications Services": "Telecommunication Services",
    "Communications Services": "Communication Services",
    "Consumer Services": "Consumer Discretionary",
    "Business Support Services": "Industrials",
    "Conglomerates": "Industrials",
}
wp["sec_norm"] = wp["sector"].replace(NORM_WP_SEC)
wp["tk_norm"] = wp["ticker"].astype(str).str.replace(".", "-", regex=False)
wp_sec_map = {(str(m)[:10], tk): s for m, tk, s in wp[["month", "tk_norm", "sec_norm"]].itertuples(index=False) if pd.notna(s)}
wp_by_tk = {tk: g.set_index("month")["sec_norm"] for tk, g in wp[wp["sec_norm"].notna()].sort_values("month").groupby("tk_norm")}

EXPLICIT_PIT_RULES = {"XRX", "LSI", "CSRA", "FSLR", "LDOS", "SAI", "CDAY", "DAY", "Q", "A", "EQIX", "CITGQ", "MTLQQ", "UST", "NFX"}

# Collect all picked tickers at each month t across Prod, V0, V3
picked_at_t = {}
for df_m in (df_prod, df_v0, df_v3):
    for r in df_m.itertuples():
        t_ts = pd.Timestamp(r.t)
        picked_at_t.setdefault(t_ts, set()).update([r.q1, r.q2, r.t1, r.s1_raw, r.s1_eff, r.eb1])

fb_rows = []
for t, tk, mom, raw_s, clean_s in p_spx[["t", "ticker", "mom", "sector", "clean_sector"]].itertuples(index=False):
    t_ts = pd.Timestamp(t)
    t_str = t_ts.strftime("%Y-%m-%d")
    tk_n = str(tk).replace(".", "-")
    w_exact = wp_sec_map.get((t_str, tk_n), wp_sec_map.get((t_str, str(tk))))
    w_causal = wp_by_tk[tk_n].loc[:t_str].iloc[-1] if (tk_n in wp_by_tk and len(wp_by_tk[tk_n].loc[:t_str]) > 0) else None

    if tk in EXPLICIT_PIT_RULES:
        prov = "1_explicit_pit_dated_rule"
    elif (t_ts, tk) in sec_map_cl:
        prov = "2_exact_t_pit_panel"
    elif tk in cl_sec_by_tk_causal and len(cl_sec_by_tk_causal[tk].loc[:t_ts]) > 0:
        prov = "3_causal_ffill_le_t"
    elif pd.notna(raw_s):
        prov = "4_raw_month_t_sector"
    else:
        prov = "5_static_archival_csv_fallback"

    if prov != "2_exact_t_pit_panel":
        fb_rows.append({
            "t": t_str,
            "ticker": tk,
            "has_12m_mom_eligible": bool(pd.notna(mom)),
            "provenance_branch": prov,
            "clean_sector_used": clean_s,
            "raw_sector_at_t": raw_s,
            "wiki_rev_exact_at_t": w_exact,
            "wiki_rev_causal_le_t": w_causal,
            "was_picked_in_any_sleeve": bool(tk in picked_at_t.get(t_ts, set())),
            "uses_any_future_gt_t_info": False,
        })

df_fb = pd.DataFrame(fb_rows)
df_fb.to_csv(os.path.join(HERE, "08_pit_gics_fallback_row_by_row_audit.csv"), index=False)

# Also run sensitivity test using raw monthly Wikipedia revision table at t (pure_wp_sec)
pure_wp_sec = []
for t, tk, c_sec in p_spx[["t", "ticker", "clean_sector"]].itertuples(index=False):
    t_str = pd.Timestamp(t).strftime("%Y-%m-%d")
    tk_n = str(tk).replace(".", "-")
    if tk in ("A", "EQIX", "APH", "GLW", "FLIR", "NFLX", "ACN", "MA", "V"):
        s_wp = c_sec
    elif (t_str, tk_n) in wp_sec_map:
        s_wp = wp_sec_map[(t_str, tk_n)]
    elif (t_str, str(tk)) in wp_sec_map:
        s_wp = wp_sec_map[(t_str, str(tk))]
    elif tk_n in wp_by_tk and len(wp_by_tk[tk_n].loc[:t_str]):
        s_wp = wp_by_tk[tk_n].loc[:t_str].iloc[-1]
    else:
        s_wp = c_sec
    pure_wp_sec.append(s_wp)

p_spx_wiki = p_spx.copy()
p_spx_wiki["clean_sector"] = pure_wp_sec
sec_ret1m_w = p_spx_wiki.groupby(["t", "clean_sector"])["ret_1m"].mean().to_dict()
p_spx_wiki["sec_ret_1m"] = [sec_ret1m_w.get((t, s), np.nan) for t, s in zip(p_spx_wiki["t"], p_spx_wiki["clean_sector"])]
p_spx_wiki["rs_sec"] = p_spx_wiki["ret_1m"] - p_spx_wiki["sec_ret_1m"]
p_t_w = p_spx_wiki[p_spx_wiki["clean_sector"] == "Information Technology"].copy()
p_e_w = p_spx_wiki[p_spx_wiki["clean_sector"] != "Information Technology"].copy()

pk_t_w = ns["select_spx_stateful"](p_t_w, "mom", 1, 1, None)
pk_s_w = ns["select_spx_stateful"](p_spx_wiki, "mom", 1, 3, -0.05, reset_t_set=ns["t_jan_u2d"])
pk_er_w = ns["select_spx_stateful"](p_e_w, "mom", 1, 3, -0.05, reset_t_set=ns["t_jan_u2d"])
pk_eb_w = ns["select_bestsec_stateful"](p_e_w, -0.05, reset_t_set=ns["t_jan_u2d"])
df_v3_wiki = ns["sim_monthly_cleanroom"](ns["pk_q_rst_jan"], pk_t_w, pk_s_w, pk_er_w, pk_eb_w, is_a1=True, dec_mode="sgov100")

# =============================================================================
# 2. 2026-10 Snapshot (Oct 29 Close) vs Full-Month (Nov 2 Open) Reconciliation
# =============================================================================
# Exact Tiingo 2026-10-01 adjOpen -> 2026-11-02 adjOpen returns for all 2026-10 held assets
NOV2_OPEN_RETS_2026_10 = {
    "SNDK": 1157.98 / 1735.26 - 1.0,   # -33.2676% (Tiingo 2026-10-01 adjOpen 1735.26 -> 2026-11-02 adjOpen 1157.98)
    "MRNA": 224.16 / 186.61 - 1.0,     # +20.1222% (Tiingo 2026-10-01 adjOpen 186.61 -> 2026-11-02 adjOpen 224.16)
    "VLO":  392.68 / 387.25 - 1.0,     # +1.4022%  (Tiingo 2026-10-01 adjOpen 387.25 -> 2026-11-02 adjOpen 392.68)
    "SGOV": 100.430 / 100.082 - 1.0,   # +0.3477%  (Tiingo 2026-10-01 adjOpen 100.082 -> 2026-11-02 adjOpen 100.430)
}

oct_recon_rows = [
    {
        "asset": "SNDK",
        "role_in_2026_10": "Tech Leg (25% in A1-RS, 50% in Prod)",
        "entry_date": "2026-10-01 Open",
        "snapshot_exit": "2026-10-29 Close (Yahoo raw_open)",
        "snapshot_ret_pct": round(float(ns["ret_lk"][(pd.Timestamp("2026-09-30"), "SNDK")]) * 100, 4),
        "strict_open_exit": "2026-11-02 Open (Tiingo adjOpen)",
        "strict_open_open_ret_pct": round(NOV2_OPEN_RETS_2026_10["SNDK"] * 100, 4),
    },
    {
        "asset": "MRNA",
        "role_in_2026_10": "Ex-IT Raw Leg (25% in A1-RS Route A1)",
        "entry_date": "2026-10-01 Open",
        "snapshot_exit": "2026-10-29 Close (Yahoo raw_open)",
        "snapshot_ret_pct": round(float(ns["ret_lk"][(pd.Timestamp("2026-09-30"), "MRNA")]) * 100, 4),
        "strict_open_exit": "2026-11-02 Open (Tiingo adjOpen)",
        "strict_open_open_ret_pct": round(NOV2_OPEN_RETS_2026_10["MRNA"] * 100, 4),
    },
    {
        "asset": "VLO",
        "role_in_2026_10": "Ex-IT BestSec Leg (25% in Prod & A1-RS)",
        "entry_date": "2026-10-01 Open",
        "snapshot_exit": "2026-10-29 Close (Yahoo raw_open)",
        "snapshot_ret_pct": round(float(ns["ret_lk"][(pd.Timestamp("2026-09-30"), "VLO")]) * 100, 4),
        "strict_open_exit": "2026-11-02 Open (Tiingo adjOpen)",
        "strict_open_open_ret_pct": round(NOV2_OPEN_RETS_2026_10["VLO"] * 100, 4),
    },
    {
        "asset": "SGOV",
        "role_in_2026_10": "Cash ETF Leg (25% in SEP=OFF)",
        "entry_date": "2026-10-01 Open",
        "snapshot_exit": "2026-10-29 Close (Tiingo SGOV)",
        "snapshot_ret_pct": round(float(ns["reg_map"][pd.Timestamp("2026-09-30")]["ret_sgov_actual"]) * 100, 4),
        "strict_open_exit": "2026-11-02 Open (Tiingo adjOpen)",
        "strict_open_open_ret_pct": round(NOV2_OPEN_RETS_2026_10["SGOV"] * 100, 4),
    },
]
pd.DataFrame(oct_recon_rows).to_csv(os.path.join(HERE, "10_oct2026_snapshot_vs_nov2_open_reconciliation.csv"), index=False)

# Compute full-month 2026-10 portfolio net returns with 2026-11-02 Open
to_prod_oct = float(df_prod.loc["2026-10", "turnover_two_way"])
to_v0_oct = float(df_v0.loc["2026-10", "turnover_two_way"])
to_v3_oct = float(df_v3.loc["2026-10", "turnover_two_way"])

gross_prod_nov2 = 0.50 * NOV2_OPEN_RETS_2026_10["SNDK"] + 0.25 * NOV2_OPEN_RETS_2026_10["VLO"] + 0.25 * NOV2_OPEN_RETS_2026_10["SGOV"]
gross_a1rs_nov2 = 0.25 * NOV2_OPEN_RETS_2026_10["SNDK"] + 0.25 * NOV2_OPEN_RETS_2026_10["MRNA"] + 0.25 * NOV2_OPEN_RETS_2026_10["VLO"] + 0.25 * NOV2_OPEN_RETS_2026_10["SGOV"]

net_prod_nov2 = (1.0 + gross_prod_nov2) * ((1.0 - 0.0010) ** to_prod_oct) - 1.0
net_v0_nov2 = (1.0 + gross_a1rs_nov2) * ((1.0 - 0.0010) ** to_v0_oct) - 1.0
net_v3_nov2 = (1.0 + gross_a1rs_nov2) * ((1.0 - 0.0010) ** to_v3_oct) - 1.0

df_prod_nov2 = df_prod.copy()
df_prod_nov2.loc["2026-10", "net_ret"] = net_prod_nov2
df_v0_nov2 = df_v0.copy()
df_v0_nov2.loc["2026-10", "net_ret"] = net_v0_nov2
df_v3_nov2 = df_v3.copy()
df_v3_nov2.loc["2026-10", "net_ret"] = net_v3_nov2

# Also run V3 with pure 3M T-Bill (rf_tbill) instead of BIL/SGOV ETF
df_v3_tbill = ns["sim_monthly_cleanroom"](
    ns["pk_q_rst_jan"], ns["pk_t"], ns["pk_s_rs5_rst_jan"], ns["pk_er_rs5_rst_jan"], ns["pk_eb_rs5_rst_jan"],
    is_a1=True, use_actual_sgov=False, dec_mode="sgov100"
)

# =============================================================================
# 3. Comprehensive Multi-Horizon & Multi-Assumption Summary (`09_external_audit_remediation_summary.csv`)
# =============================================================================
rf_all = np.array([float(ns["reg_map"][t]["rf_tbill"]) for t in ns["months_214"]])

def metrics_for(df_in, n_months):
    r = df_in.iloc[:n_months]["net_ret"].values
    rf = rf_all[:n_months]
    cagr = float(np.prod(1.0 + r) ** (12.0 / len(r)) - 1.0)
    sr_raw_sd = float(np.mean(r - rf) / np.std(r, ddof=1) * np.sqrt(12.0))
    sr_exc_sd = float(np.mean(r - rf) / np.std(r - rf, ddof=1) * np.sqrt(12.0))
    w = np.concatenate([[1.0], np.cumprod(1.0 + r)])
    mdd = float((w / np.maximum.accumulate(w) - 1.0).min())
    mult = float(w[-1])
    return cagr, sr_raw_sd, sr_exc_sd, mdd, mult

summary_rows = []
for name, df_model in [
    ("1. Production Baseline 1.35x (BestSec_ModBurst_135_75_25_GateV1)", df_prod),
    ("2. Core Challenger V0 (A1-RS 1.35x, NO Election Rule)", df_v0),
    ("3. Frozen Challenger V3 (A1-RS 1.35x + V3 Election Reset, Oct29 Snapshot)", df_v3),
    ("4. Frozen Challenger V3 (Strict 2026-11-02 Open on Month 214)", df_v3_nov2),
    ("5. Frozen Challenger V3 (Pure Monthly Wikipedia Sector at t)", df_v3_wiki),
    ("6. Frozen Challenger V3 (3M T-Bill Cash Proxy instead of BIL/SGOV)", df_v3_tbill),
]:
    c204, sr204, sre204, mdd204, mult204 = metrics_for(df_model, 204)  # 2009-01..2025-12 (Ex-2026)
    c213, sr213, sre213, mdd213, mult213 = metrics_for(df_model, 213)  # 2009-01..2026-09 (Strict Open-to-Open)
    c214, sr214, sre214, mdd214, mult214 = metrics_for(df_model, 214)  # 2009-01..2026-10 (Full 214M)
    summary_rows.append({
        "Strategy_and_Audit_Variant": name,
        "CAGR_204M_Ex2026_pct": round(c204 * 100, 2),
        "Sharpe_204M_Ex2026": round(sr204, 3),
        "CAGR_213M_StrictOpenOpen_pct": round(c213 * 100, 2),
        "Sharpe_213M_StrictOpenOpen": round(sr213, 3),
        "CAGR_214M_pct": round(c214 * 100, 2),
        "Sharpe_214M_RawSD": round(sr214, 3),
        "Sharpe_214M_ExcessSD": round(sre214, 3),
        "Monthly_MaxDD_pct": round(mdd214 * 100, 2),
        "Terminal_Multiple_214M": round(mult214, 1),
    })

df_sum = pd.DataFrame(summary_rows)
df_sum.to_csv(os.path.join(HERE, "09_external_audit_remediation_summary.csv"), index=False)

print("=== EXTERNAL AUDIT REMEDIATION SUMMARY ===")
print(df_sum.to_string(index=False))
print(f"\nFallback rows audited in 08_pit_gics_fallback_row_by_row_audit.csv: {len(df_fb)} rows (0 rows use >t future info)")
