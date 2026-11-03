#!/usr/bin/env python3
"""
STEP 3 (CLEAN-ROOM): Standalone Computation of All 18 Price Features + Truncation Invariance Test
=================================================================================================
Strict Clean-Room Rules:
- Zero imports from original project `.py` modules (`ml_features.py`, `explosive_factors.py`, `ml2_run.py`, etc.).
- Zero reading of intermediate `.parquet` panels.
- Computes all 18 pure price features directly from the clean-room daily/monthly matrices:
  `mom_12_1, mom_6_1, mom_3_1, rev_1m, dist_sma200, dist_sma50, dist_52wh, vol_3m, vol_12m,
   beta_12m, maxret_1m, smooth, mom_accel, dv_ratio, mkt_ret12, mkt_above200, mkt_vol3m, sector_mom`
- Supports two clean-room modes:
  1) `spec_mode='hybrid_repro'`: Replicates the exact original `run_ml3_qqq_iwm_pools.py` behavior
     (where S&P-member NDX rows got S&P-500 `sector_mom` and `raw_volume` `dv_ratio`, while NDX-only
     rows got Union `sector_mom` and `raw_volume + raw_ndx` `dv_ratio`).
  2) `spec_mode='pure_qqq'`: Pure standalone Nasdaq-100 feature computation (`sector_mom` computed
     strictly within the Nasdaq-100 pool; `dv_ratio` computed uniformly across all available stores).
- Runs a physical price-truncation test at 5 historical cutoff dates proving zero look-ahead leakage
  in any of the 18 features or eligibility rules.
"""

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

from q2_cleanroom_price_engine import (
    DATA_DIR,
    OUT_DIR,
    TIINGO_AUDIT_DIR,
    CleanRoomPriceEngine,
    load_cleanroom_prices_and_universe,
)

FEATURES_18 = [
    "mom_12_1",
    "mom_6_1",
    "mom_3_1",
    "rev_1m",
    "dist_sma200",
    "dist_sma50",
    "dist_52wh",
    "vol_3m",
    "vol_12m",
    "beta_12m",
    "maxret_1m",
    "smooth",
    "mom_accel",
    "dv_ratio",
    "mkt_ret12",
    "mkt_above200",
    "mkt_vol3m",
    "sector_mom",
]


def cleanroom_momentum(P: pd.DataFrame, seg_m: pd.DataFrame, look: int) -> pd.DataFrame:
    m = P.shift(1) / P.shift(look) - 1.0
    sg = seg_m.reindex(index=P.index, columns=P.columns)
    return m.where((sg.shift(look) == sg.shift(1)) & (sg.shift(1) == sg))


def compute_base_price_features(U: dict) -> dict[str, pd.DataFrame]:
    d = U["daily"]
    P = U["P"]
    form = U["form"]
    seg_d = U["seg_d"].reindex(index=d.index, columns=d.columns)
    seg_m = U["seg_m"].reindex(index=P.index, columns=P.columns)

    r = d.pct_change(fill_method=None)
    r = r.where(seg_d == seg_d.shift(1))

    sma200 = d.rolling(200, min_periods=180).mean()
    sma50 = d.rolling(50, min_periods=45).mean()
    hi252 = d.rolling(252, min_periods=200).max()
    vol63 = r.rolling(63, min_periods=50).std() * np.sqrt(252.0)
    vol252 = r.rolling(252, min_periods=200).std() * np.sqrt(252.0)

    spy_r = r["SPY"]
    cov = r.rolling(252, min_periods=200).cov(spy_r)
    beta = cov.div(spy_r.rolling(252, min_periods=200).var(), axis=0)
    maxr = r.rolling(21, min_periods=15).max()
    ok252 = seg_d == seg_d.shift(252)

    pos = d.index.searchsorted(form, side="right") - 1
    take = lambda x: x.iloc[pos].set_axis(form)

    feats = {
        "dist_sma200": take(d / sma200 - 1.0),
        "dist_sma50": take(d / sma50 - 1.0),
        "dist_52wh": take((d / hi252 - 1.0).where(ok252)),
        "vol_3m": take(vol63),
        "vol_12m": take(vol252.where(ok252)),
        "beta_12m": take(beta.where(ok252)),
        "maxret_1m": take(maxr),
    }

    for look, name in [(12, "mom_12_1"), (6, "mom_6_1"), (3, "mom_3_1")]:
        feats[name] = cleanroom_momentum(P, seg_m, look).reindex(form)

    rev = P / P.shift(1) - 1.0
    rev = rev.where(seg_m == seg_m.shift(1))
    feats["rev_1m"] = rev.reindex(form)

    # Frog-in-the-pan continuous momentum (`smooth`)
    pos_d = (r > 0).astype(float).where(r.notna())
    neg_d = (r < 0).astype(float).where(r.notna())
    pf_roll = pos_d.shift(21).rolling(231, min_periods=180).mean()
    nf_roll = neg_d.shift(21).rolling(231, min_periods=180).mean()
    m12 = feats["mom_12_1"]
    info_disc = np.sign(m12) * (take(nf_roll) - take(pf_roll))
    feats["smooth"] = -info_disc

    feats["mom_accel"] = feats["mom_3_1"] - feats["mom_12_1"] * (3.0 / 11.0)
    return feats


def compute_market_context(daily: pd.DataFrame, form: pd.DatetimeIndex) -> pd.DataFrame:
    spy = daily["SPY"].dropna()
    pos = spy.index.searchsorted(form, side="right") - 1
    sma = spy.rolling(200).mean()
    vol3 = spy.pct_change().rolling(63).std() * np.sqrt(252.0)
    return pd.DataFrame({
        "t": form,
        "mkt_ret12": spy.iloc[pos].values / spy.shift(252).iloc[pos].values - 1.0,
        "mkt_above200": (spy.iloc[pos].values > sma.iloc[pos].values).astype(float),
        "mkt_vol3m": vol3.iloc[pos].values,
    })


def compute_dvr_matrices(form: pd.DatetimeIndex, cutoff: pd.Timestamp | None = None):
    """
    Computes two `dv_ratio` matrices:
      1) `DVR_sp`: using only `data/raw_volume` + `data/raw` (exact match to `ml2_run.py` for S&P rows)
      2) `DVR_nd`: using `data/raw_volume` + `data/raw` AND `data/raw_ndx` (exact match to `run_ml3_qqq_iwm_pools.py` for NDX-only rows)
      3) `DVR_pure`: also filling from `data/raw_tiingo`, `data/raw_wiki`, and `tiingo/` where volume & close exist
    """
    dvr_sp = {}
    vd = DATA_DIR / "raw_volume"
    rd = DATA_DIR / "raw"
    if vd.exists():
        for fn in sorted(os.listdir(vd)):
            if not fn.endswith(".json") or fn.startswith("_"):
                continue
            rp = rd / fn
            if not rp.exists():
                continue
            j = json.load(open(vd / fn))
            r = json.load(open(rp))
            if not j.get("volume") or not r.get("close"):
                continue
            v = pd.Series([x if x is not None else np.nan for x in j["volume"]], index=pd.to_datetime(j["dates"]), dtype=float)
            c = pd.Series([x if x is not None else np.nan for x in r["close"]], index=pd.to_datetime(r["dates"]), dtype=float)
            if cutoff is not None:
                v = v[v.index <= pd.Timestamp(cutoff)]
                c = c[c.index <= pd.Timestamp(cutoff)]
            dv = (v * c.reindex(v.index)).dropna()
            if len(dv) >= 180:
                dvr_sp[fn[:-5]] = dv.rolling(63, min_periods=40).median() / dv.rolling(252, min_periods=180).median()

    dvr_nd = dict(dvr_sp)
    nd_dir = DATA_DIR / "raw_ndx"
    if nd_dir.exists():
        for fn in sorted(os.listdir(nd_dir)):
            if not fn.endswith(".json") or fn.startswith("_"):
                continue
            j = json.load(open(nd_dir / fn))
            if not j.get("volume") or not j.get("close"):
                continue
            v = pd.Series([x if x is not None else np.nan for x in j["volume"]], index=pd.to_datetime(j["dates"]), dtype=float)
            c = pd.Series([x if x is not None else np.nan for x in j["close"]], index=pd.to_datetime(j["dates"]), dtype=float)
            if cutoff is not None:
                v = v[v.index <= pd.Timestamp(cutoff)]
                c = c[c.index <= pd.Timestamp(cutoff)]
            dv = (v * c.reindex(v.index)).dropna()
            if len(dv) >= 180:
                dvr_nd[fn[:-5]] = dv.rolling(63, min_periods=40).median() / dv.rolling(252, min_periods=180).median()

    dvr_pure = dict(dvr_nd)
    for extra_dir in [DATA_DIR / "raw_tiingo", DATA_DIR / "raw_wiki"]:
        if not extra_dir.exists():
            continue
        for fn in sorted(os.listdir(extra_dir)):
            if not fn.endswith(".json") or fn.startswith("_"):
                continue
            sym = fn[:-5]
            if sym in dvr_pure:
                continue
            j = json.load(open(extra_dir / fn))
            if not j.get("volume") or not j.get("close"):
                continue
            v = pd.Series([x if x is not None else np.nan for x in j["volume"]], index=pd.to_datetime(j["dates"]), dtype=float)
            c = pd.Series([x if x is not None else np.nan for x in j["close"]], index=pd.to_datetime(j["dates"]), dtype=float)
            if cutoff is not None:
                v = v[v.index <= pd.Timestamp(cutoff)]
                c = c[c.index <= pd.Timestamp(cutoff)]
            dv = (v * c.reindex(v.index)).dropna()
            if len(dv) >= 180:
                dvr_pure[sym] = dv.rolling(63, min_periods=40).median() / dv.rolling(252, min_periods=180).median()

    def align_to_form(d_map):
        df = pd.DataFrame(d_map).sort_index()
        pos = df.index.searchsorted(form, side="right") - 1
        return df.iloc[pos].set_axis(form)

    return align_to_form(dvr_sp), align_to_form(dvr_nd), align_to_form(dvr_pure)


def build_cleanroom_qqq_panel(U: dict, px_eng: CleanRoomPriceEngine, spec_mode: str = "hybrid_repro", cutoff: pd.Timestamp | None = None) -> pd.DataFrame:
    """
    Builds the clean-room QQQ Full100 18-feature panel directly from U and px_eng.
      - `spec_mode='hybrid_repro'`: Replicates the exact original `run_ml3_qqq_iwm_pools.py` panel construction.
      - `spec_mode='pure_qqq'`: Pure standalone QQQ panel (`sector_mom` strictly within QQQ; uniform `dv_ratio`).
    """
    P = U["P"]
    secP = U["secP"]
    form = U["form"]
    feats = compute_base_price_features(U)
    mom12_df = feats["mom_12_1"]
    ctx = compute_market_context(U["daily"], form).set_index("t")
    dvr_sp, dvr_nd, dvr_pure = compute_dvr_matrices(form, cutoff=cutoff)

    rows = []
    for t in form:
        m_t = mom12_df.loc[t]
        sec_t = secP.loc[t]
        p_t = P.loc[t]

        # Eligible S&P, NDX, and Union sets at month-end t (strictly using info at t only)
        def elig_set(mem_set):
            return [
                s for s in sorted(mem_set)
                if s in m_t.index and s in sec_t.index and np.isfinite(m_t[s]) and np.isfinite(p_t[s]) and isinstance(sec_t[s], str)
            ]

        el_sp = elig_set(U["members_sp"].get(t, set()))
        el_nd = elig_set(U["members_nd"].get(t, set()))
        el_un = elig_set(U["members_union"].get(t, set()))

        if not el_nd:
            continue

        # Compute sector momentum means under each universe definition
        df_sp = pd.DataFrame({"s": el_sp, "mom": [m_t[s] for s in el_sp], "sec": [sec_t[s] for s in el_sp]})
        sec_mean_sp = df_sp.groupby("sec")["mom"].mean().to_dict() if len(df_sp) else {}

        df_un = pd.DataFrame({"s": el_un, "mom": [m_t[s] for s in el_un], "sec": [sec_t[s] for s in el_un]})
        sec_mean_un = df_un.groupby("sec")["mom"].mean().to_dict() if len(df_un) else {}

        df_nd = pd.DataFrame({"s": el_nd, "mom": [m_t[s] for s in el_nd], "sec": [sec_t[s] for s in el_nd]})
        sec_mean_nd = df_nd.groupby("sec")["mom"].mean().to_dict() if len(df_nd) else {}

        sp_set_t = set(el_sp)
        for s in el_nd:
            in_sp = s in sp_set_t
            sec_name = sec_t[s]
            if spec_mode == "hybrid_repro":
                smom = sec_mean_sp.get(sec_name, np.nan) if in_sp else sec_mean_un.get(sec_name, np.nan)
                dvr_val = (dvr_sp.at[t, s] if s in dvr_sp.columns else np.nan) if in_sp else (dvr_nd.at[t, s] if s in dvr_nd.columns else np.nan)
            else:
                smom = sec_mean_nd.get(sec_name, np.nan)
                dvr_val = dvr_pure.at[t, s] if s in dvr_pure.columns else np.nan

            rec = {
                "t": t,
                "ticker": s,
                "sector": sec_name,
                "in_sp": in_sp,
                "in_ndx": True,
                "sector_mom": float(smom) if np.isfinite(smom) else np.nan,
                "dv_ratio": float(dvr_val) if np.isfinite(dvr_val) else np.nan,
                "mkt_ret12": float(ctx.at[t, "mkt_ret12"]),
                "mkt_above200": float(ctx.at[t, "mkt_above200"]),
                "mkt_vol3m": float(ctx.at[t, "mkt_vol3m"]),
            }
            for k in ["mom_12_1", "mom_6_1", "mom_3_1", "rev_1m", "dist_sma200", "dist_sma50", "dist_52wh", "vol_3m", "vol_12m", "beta_12m", "maxret_1m", "smooth", "mom_accel"]:
                rec[k] = float(feats[k].at[t, s]) if s in feats[k].columns and np.isfinite(feats[k].at[t, s]) else np.nan

            r_oo, st_oo = px_eng.ret(t, s)
            rec["ret_oo"] = r_oo
            rec["status_oo"] = st_oo
            rows.append(rec)

    df_panel = pd.DataFrame(rows)
    df_panel = df_panel.sort_values(["t", "mom_12_1", "ticker"], ascending=[True, False, True]).reset_index(drop=True)
    df_panel["mom_rank_qqq"] = df_panel.groupby("t").cumcount() + 1
    return df_panel


def run_step3_truncation_test(df_full: pd.DataFrame) -> pd.DataFrame:
    """
    Physically truncates all raw daily/open/volume series at 5 historical cutoff dates
    and verifies that all 18 features and eligible rosters at `t = cutoff` are 100.000% identical.
    """
    cutoffs = [
        pd.Timestamp("2015-06-30"),
        pd.Timestamp("2018-11-30"),
        pd.Timestamp("2020-08-31"),
        pd.Timestamp("2022-12-31"),
        pd.Timestamp("2025-05-31"),
    ]
    audit_rows = []
    for cut in cutoffs:
        U_cut = load_cleanroom_prices_and_universe(cutoff=cut)
        px_cut = CleanRoomPriceEngine(U_cut, mode="open")
        df_cut = build_cleanroom_qqq_panel(U_cut, px_cut, spec_mode="hybrid_repro", cutoff=cut)

        sub_full = df_full[df_full.t == cut].sort_values("ticker").reset_index(drop=True)
        sub_cut = df_cut[df_cut.t == cut].sort_values("ticker").reset_index(drop=True)

        same_tickers = list(sub_full.ticker) == list(sub_cut.ticker)
        max_abs_diff = 0.0
        worst_feat = "NONE"
        for f in FEATURES_18:
            a = sub_full[f].values
            b = sub_cut[f].values
            na_match = np.array_equal(np.isnan(a), np.isnan(b))
            valid = ~np.isnan(a) & ~np.isnan(b)
            diff = float(np.max(np.abs(a[valid] - b[valid]))) if valid.any() else 0.0
            if not na_match:
                diff = np.inf
            if diff > max_abs_diff:
                max_abs_diff = diff
                worst_feat = f

        audit_rows.append({
            "cutoff_date": cut.strftime("%Y-%m-%d"),
            "n_eligible_full": len(sub_full),
            "n_eligible_truncated": len(sub_cut),
            "exact_roster_match": same_tickers,
            "max_abs_feature_diff_across_18_features": max_abs_diff,
            "worst_feature": worst_feat,
            "pass": bool(same_tickers and max_abs_diff < 1e-12),
        })

    df_trunc = pd.DataFrame(audit_rows)
    df_trunc.to_csv(OUT_DIR / "step3_truncation_test_audit.csv", index=False)
    return df_trunc


def main():
    print("Step 3: Computing clean-room 18 price features (Hybrid Repro & Pure QQQ modes)...", flush=True)
    U = load_cleanroom_prices_and_universe()
    px_eng = CleanRoomPriceEngine(U, mode="open")

    df_hybrid = build_cleanroom_qqq_panel(U, px_eng, spec_mode="hybrid_repro")
    df_pure = build_cleanroom_qqq_panel(U, px_eng, spec_mode="pure_qqq")

    df_hybrid.to_parquet(OUT_DIR / "cleanroom_panel_qqq_hybrid_repro.parquet", index=False)
    df_pure.to_parquet(OUT_DIR / "cleanroom_panel_qqq_pure_standalone.parquet", index=False)

    print(f"   Clean-room QQQ panel built: {len(df_hybrid)} stock-months across {df_hybrid.t.nunique()} formation months.")
    cov = df_hybrid[FEATURES_18].notna().mean().round(4)
    cov_pure = df_pure[FEATURES_18].notna().mean().round(4)
    df_cov = pd.DataFrame({
        "feature": FEATURES_18,
        "coverage_hybrid_repro": [cov[f] for f in FEATURES_18],
        "coverage_pure_qqq": [cov_pure[f] for f in FEATURES_18],
    })
    df_cov.to_csv(OUT_DIR / "step3_feature_coverage_comparison.csv", index=False)
    print("   Feature coverage summary:")
    print(df_cov.to_string(index=False))

    print("   Running Step 3 Physical Price-Truncation Invariance Test at 5 cutoffs...", flush=True)
    df_trunc = run_step3_truncation_test(df_hybrid)
    print(df_trunc.to_string(index=False))


if __name__ == "__main__":
    main()
