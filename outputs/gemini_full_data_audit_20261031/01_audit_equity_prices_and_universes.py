#!/usr/bin/env python3
"""
01_audit_equity_prices_and_universes.py
Exhaustive (100% population) audit of all equity price, open, volume, corporate-action,
and universe membership datasets across S&P 500, Nasdaq-100, and Small/Mid-Cap stores.
Read-only on all project inputs; writes outputs solely to outputs/gemini_full_data_audit_20261031/.
"""
import glob
import json
import os
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/happygolucky/Desktop/宏观观察器")
SSM = ROOT / "research/sector_stock_momentum"
OUT_DIR = ROOT / "outputs/gemini_full_data_audit_20261031"
OUT_DIR.mkdir(parents=True, exist_ok=True)

sys.dont_write_bytecode = True
sys.path.insert(0, str(SSM))
import backtest as bt
import historical_sectors as hs


def audit_raw_json_stores():
    stores = [
        "raw",
        "raw_open",
        "raw_volume",
        "raw_tiingo",
        "raw_wiki",
        "raw_archive",
        "raw_ndx",
        "raw_smallcap",
    ]
    summary = {}
    open_ratio_diffs = []
    open_vs_raw_close_mismatches = 0
    open_vs_raw_overlap_bars = 0
    raw_cache = {}

    for st in stores:
        dpath = SSM / "data" / st
        files = sorted([Path(p) for p in glob.glob(str(dpath / "*.json")) if not Path(p).name.startswith("_")])
        n_files = len(files)
        total_bars = 0
        non_monotonic = 0
        dup_dates = 0
        nonpos_close = 0
        nonpos_adj = 0
        nonpos_open = 0
        nan_bars = 0
        extreme_daily_5x = 0
        zero_adj_files = []

        for fp in files:
            d = json.loads(fp.read_text())
            sym = d.get("symbol", fp.stem)
            dates = d.get("dates", [])
            n = len(dates)
            total_bars += n
            if n > 1:
                if any(dates[i] >= dates[i + 1] for i in range(n - 1)):
                    if len(set(dates)) < n:
                        dup_dates += 1
                    else:
                        non_monotonic += 1

            if st == "raw":
                raw_cache[sym] = (dates, d.get("close", []), d.get("adjclose", []), d.get("splits", []))

            if "close" in d:
                c = np.asarray(d["close"], dtype=float)
                nan_bars += int(np.isnan(c).sum())
                nonpos_close += int((c <= 0).sum())
            if "adjclose" in d:
                ac = np.asarray(d["adjclose"], dtype=float)
                nan_bars += int(np.isnan(ac).sum())
                bad_ac = int((ac <= 0).sum())
                nonpos_adj += bad_ac
                if bad_ac > 0:
                    zero_adj_files.append({"symbol": sym, "nonpos_adj_bars": bad_ac, "min_adj": float(np.nanmin(ac))})
                valid = ac[ac > 0]
                if len(valid) > 1:
                    r = valid[1:] / valid[:-1]
                    extreme_daily_5x += int(((r > 5.0) | (r < 0.2)).sum())
            if st == "raw_open":
                op = np.asarray(d["open"], dtype=float)
                aop = np.asarray(d["adj_open"], dtype=float)
                cl = np.asarray(d["close"], dtype=float)
                acl = np.asarray(d["adjclose"], dtype=float)
                nonpos_open += int(((op <= 0) | (aop <= 0)).sum())
                m = (op > 0) & (cl > 0) & np.isfinite(aop) & np.isfinite(acl)
                if m.any():
                    diff = np.abs((aop[m] / op[m]) - (acl[m] / cl[m]))
                    open_ratio_diffs.append(float(diff.max()))
                if sym in raw_cache:
                    rd, rc, rac, _ = raw_cache[sym]
                    rmap = dict(zip(rd, rc))
                    shared_c = [(cl[i], rmap[dt]) for i, dt in enumerate(dates) if dt in rmap and cl[i] > 0 and rmap[dt] > 0]
                    open_vs_raw_overlap_bars += len(shared_c)
                    if shared_c:
                        arr = np.asarray(shared_c, dtype=float)
                        rel = np.abs(arr[:, 0] - arr[:, 1]) / arr[:, 1]
                        open_vs_raw_close_mismatches += int((rel > 1e-4).sum())

        summary[st] = {
            "files": n_files,
            "total_bars": total_bars,
            "non_monotonic_files": non_monotonic,
            "duplicate_date_files": dup_dates,
            "nan_values": nan_bars,
            "nonpos_close_bars": nonpos_close,
            "nonpos_adjclose_bars": nonpos_adj,
            "nonpos_open_bars": nonpos_open,
            "extreme_daily_5x_or_80pct_drop_bars": extreme_daily_5x,
            "zero_or_neg_adjclose_examples": zero_adj_files[:15],
        }

    open_check = {
        "max_adj_open_factor_diff_across_all_files": float(max(open_ratio_diffs)) if open_ratio_diffs else None,
        "raw_vs_raw_open_overlapping_bars": open_vs_raw_overlap_bars,
        "raw_vs_raw_open_close_diff_gt_1bp_bars": open_vs_raw_close_mismatches,
    }
    return summary, open_check, raw_cache


def audit_ivv_external_prices_and_sectors(raw_cache):
    ivv_path = ROOT / "outputs/sector_eps_then_momentum_20261030/universe_audit/ivv_primary_holdings.csv"
    if not ivv_path.exists():
        return {"status": "SKIPPED_NO_FILE"}

    ivv = pd.read_csv(ivv_path, dtype={"cusip": str, "isin": str, "sedol": str})
    ivv = ivv[ivv["assetClass"] == "Equity"].copy()
    ivv["norm_ticker"] = (
        ivv["ticker"]
        .astype(str)
        .str.replace(".", "-", regex=False)
        .str.replace("/", "-", regex=False)
        .str.replace(" ", "-", regex=False)
        .replace({"BRKB": "BRK-B", "BFB": "BF-B"})
    )
    ivv["asof_dt"] = pd.to_datetime(ivv["source_asof"].astype(str), format="%Y%m%d", errors="coerce")
    ivv["unitPrice"] = pd.to_numeric(ivv["unitPrice"], errors="coerce")

    # Build fast lookup for Yahoo raw_cache (close is split-adjusted to download date; reverse post-asof splits!)
    yahoo_lookup = {}
    for sym, (dates, closes, adjcloses, splits) in raw_cache.items():
        s_cl = pd.Series(closes, index=pd.to_datetime(dates), dtype=float)
        sp_list = [(pd.Timestamp(a), float(n or 1) / float(dd or 1)) for a, n, dd in (splits or [])]
        yahoo_lookup[sym] = (s_cl, sp_list)

    # Also build Tiingo and WIKI raw unadjusted close lookup
    tiingo_lookup = {}
    for fp in sorted(glob.glob(str(SSM / "data/raw_tiingo/*.json"))):
        if Path(fp).name.startswith("_"):
            continue
        d = json.loads(Path(fp).read_text())
        if d.get("dates") and d.get("close"):
            tiingo_lookup[d["symbol"]] = pd.Series(d["close"], index=pd.to_datetime(d["dates"]), dtype=float)

    wiki_lookup = {}
    for fp in sorted(glob.glob(str(SSM / "data/raw_wiki/*.json"))):
        if Path(fp).name.startswith("_"):
            continue
        d = json.loads(Path(fp).read_text())
        if d.get("dates") and d.get("close"):
            wiki_lookup[d["symbol"]] = pd.Series(d["close"], index=pd.to_datetime(d["dates"]), dtype=float)

    matched = 0
    within_10bp = 0
    within_50bp = 0
    within_1pct = 0
    gt_1pct = []

    for r in ivv.itertuples():
        if pd.isna(r.asof_dt) or pd.isna(r.unitPrice) or r.unitPrice <= 0:
            continue
        sym = r.norm_ticker
        dt = r.asof_dt
        est_raw = None
        src = None

        if sym in yahoo_lookup:
            s_cl, sp_list = yahoo_lookup[sym]
            if dt in s_cl.index:
                fac = 1.0
                for sdt, sr in sp_list:
                    if sdt > dt:
                        fac *= sr
                est_raw = float(s_cl.loc[dt]) * fac
                src = "yahoo_unsplit"
        if (est_raw is None or abs(est_raw - r.unitPrice) / r.unitPrice > 0.02) and sym in tiingo_lookup:
            s_t = tiingo_lookup[sym]
            if dt in s_t.index:
                cand = float(s_t.loc[dt])
                if est_raw is None or abs(cand - r.unitPrice) < abs(est_raw - r.unitPrice):
                    est_raw = cand
                    src = "tiingo_raw"
        if (est_raw is None or abs(est_raw - r.unitPrice) / r.unitPrice > 0.02) and sym in wiki_lookup:
            s_w = wiki_lookup[sym]
            if dt in s_w.index:
                cand = float(s_w.loc[dt])
                if est_raw is None or abs(cand - r.unitPrice) < abs(est_raw - r.unitPrice):
                    est_raw = cand
                    src = "wiki_raw"

        if est_raw is not None and est_raw > 0:
            matched += 1
            rel = abs(est_raw - r.unitPrice) / r.unitPrice
            if rel <= 0.001:
                within_10bp += 1
            if rel <= 0.005:
                within_50bp += 1
            if rel <= 0.01:
                within_1pct += 1
            else:
                gt_1pct.append({
                    "formation": r.formation,
                    "asof": str(dt.date()),
                    "ticker": sym,
                    "issueName": r.issueName,
                    "ivv_unitPrice": float(r.unitPrice),
                    "store_unadj_close": round(est_raw, 4),
                    "rel_diff_pct": round(rel * 100, 3),
                    "source": src,
                })

    # Check if the 59 confirmed IVV membership defects ever changed Top-1 or Top-3 picks!
    corr_p = ROOT / "outputs/sector_eps_then_momentum_20261030/universe_audit/confirmed_corrections.csv"
    defect_impact = {}
    if corr_p.exists():
        corr = pd.read_csv(corr_p)
        spec_led = pd.read_csv(SSM / "results/monthly_SPEC.csv")
        top1_led = pd.read_csv(SSM / "results/monthly_NO_SECTOR_FILTER__top_1_stock.csv")
        top10_led = pd.read_csv(SSM / "results/monthly_Ref__top_10__no_sector_filter.csv")
        ml2_top3_p = SSM / "results/ml2/monthly_C_lgbm_top3.csv"
        ml2_top3_led = pd.read_csv(ml2_top3_p) if ml2_top3_p.exists() else pd.DataFrame()
        defect_tickers = set(corr["ticker"].astype(str))
        spec_hits, top1_hits, top10_hits, ml2_hits = [], [], [], []
        for row in corr.itertuples():
            tk = str(row.ticker)
            hm = str((pd.Timestamp(row.formation) + pd.offsets.MonthEnd(1)).date())[:7]
            info = {"formation": str(row.formation), "ticker": tk, "action": str(row.action), "reason": str(row.reason)}
            s_m = spec_led[spec_led["month"].astype(str).str.startswith(hm)]
            if not s_m.empty and tk in str(s_m.iloc[0].get("picks", "")).split("|"):
                spec_hits.append(info)
            t1_m = top1_led[top1_led["month"].astype(str).str.startswith(hm)]
            if not t1_m.empty and tk in str(t1_m.iloc[0].get("picks", "")).split("|"):
                top1_hits.append(info)
            t10_m = top10_led[top10_led["month"].astype(str).str.startswith(hm)]
            if not t10_m.empty and tk in str(t10_m.iloc[0].get("picks", "")).split("|"):
                top10_hits.append(info)
            if not ml2_top3_led.empty:
                m2_m = ml2_top3_led[ml2_top3_led["month"].astype(str).str.startswith(hm)]
                if not m2_m.empty and tk in str(m2_m.iloc[0].get("picks", "")).split("|"):
                    ml2_hits.append(info)
        defect_impact = {
            "confirmed_membership_corrections_rows": int(len(corr)),
            "unique_tickers_in_corrections": sorted(list(defect_tickers)),
            "hits_in_SPEC_picks_during_defect_month": spec_hits,
            "hits_in_PureMom_Top1_during_defect_month": top1_hits,
            "hits_in_PureMom_Top10_during_defect_month": top10_hits,
            "hits_in_ML2_C_lgbm_Top3_during_defect_month": ml2_hits,
        }

    pd.DataFrame(gt_1pct).to_csv(OUT_DIR / "ivv_vs_store_price_outliers_gt1pct.csv", index=False)
    return {
        "ivv_equity_rows_total": int(len(ivv)),
        "matched_ticker_months_with_same_day_quote": matched,
        "exact_match_within_10bp": within_10bp,
        "exact_match_within_10bp_pct": round(within_10bp / max(1, matched) * 100, 4),
        "match_within_50bp": within_50bp,
        "match_within_50bp_pct": round(within_50bp / max(1, matched) * 100, 4),
        "match_within_1pct": within_1pct,
        "match_within_1pct_pct": round(within_1pct / max(1, matched) * 100, 4),
        "outliers_gt_1pct_count": len(gt_1pct),
        "outliers_gt_1pct_sample": gt_1pct[:20],
        "confirmed_59_membership_defects_pick_impact": defect_impact,
    }


def audit_yahoo_vs_wiki_overlap(raw_cache):
    wp_path = SSM / "data/wiki_bulk/wiki_prices.parquet"
    if not wp_path.exists():
        return {"status": "SKIPPED_NO_WIKI_BULK"}

    # Read only ticker, date, adj_close from wiki_prices.parquet for speed & low RAM
    wp = pd.read_parquet(wp_path, columns=["ticker", "date", "adj_close"])
    wp["date"] = pd.to_datetime(wp["date"])
    wp = wp[(wp["date"] >= "2008-12-01") & (wp["date"] <= "2018-03-27")]
    wp["ym"] = wp["date"].dt.to_period("M")
    w_me = wp.sort_values("date").groupby(["ticker", "ym"], as_index=False).last()
    w_me["w_ret"] = w_me.groupby("ticker")["adj_close"].pct_change()
    w_piv = w_me.dropna(subset=["w_ret"]).set_index(["ticker", "ym"])["w_ret"]

    # Compare against S&P Yahoo raw_cache
    sp_rows = []
    for sym, (dates, _, adjc, _) in raw_cache.items():
        if not dates:
            continue
        s = pd.Series(adjc, index=pd.to_datetime(dates), dtype=float)
        s = s[(s.index >= "2008-12-01") & (s.index <= "2018-03-27") & (s > 0)]
        if len(s) < 25:
            continue
        me = s.groupby(s.index.to_period("M")).last()
        ret = me.pct_change().dropna()
        for ym, r in ret.items():
            sp_rows.append((sym, ym, float(r)))
    sp_df = pd.DataFrame(sp_rows, columns=["ticker", "ym", "y_ret"]).set_index(["ticker", "ym"])
    both_sp = sp_df.join(w_piv, how="inner").dropna()
    diff_sp = (both_sp["y_ret"] - both_sp["w_ret"]).abs()

    # Also check already-computed smallcap overlap summary + recompute exact counts
    sc_monthly_p = SSM / "data/smallcap/wiki_vs_yahoo_monthly.csv"
    sc_overlap_info = {}
    if sc_monthly_p.exists():
        scm = pd.read_csv(sc_monthly_p)
        sc_overlap_info = {
            "smallcap_overlap_CSV_rows": int(len(scm)),
            "smallcap_overlap_columns": list(scm.columns),
        }
        diff_col = [c for c in scm.columns if "diff" in c.lower()]
        if diff_col:
            dc = pd.to_numeric(scm[diff_col[0]], errors="coerce").dropna().abs()
            sc_overlap_info["within_50bp_pct"] = round(float((dc <= 0.005).mean() * 100), 4)
            sc_overlap_info["within_1pct_pct"] = round(float((dc <= 0.01).mean() * 100), 4)
            sc_overlap_info["gt_5pct_count"] = int((dc > 0.05).sum())

    outliers = both_sp[diff_sp > 0.02].copy()
    outliers["abs_diff"] = diff_sp[diff_sp > 0.02]
    outliers = outliers.sort_values("abs_diff", ascending=False).reset_index()
    outliers["ym"] = outliers["ym"].astype(str)
    outliers.head(200).to_csv(OUT_DIR / "sp500_yahoo_vs_wiki_monthly_outliers_gt2pct.csv", index=False)

    return {
        "wiki_bulk_total_tickers_2008_2018": int(wp["ticker"].nunique()),
        "sp500_overlapping_tickers": int(both_sp.index.get_level_values(0).nunique()),
        "sp500_overlapping_stock_months": int(len(both_sp)),
        "sp500_monthly_ret_within_10bp_pct": round(float((diff_sp <= 0.001).mean() * 100), 4),
        "sp500_monthly_ret_within_50bp_pct": round(float((diff_sp <= 0.005).mean() * 100), 4),
        "sp500_monthly_ret_within_1pct_pct": round(float((diff_sp <= 0.01).mean() * 100), 4),
        "sp500_monthly_ret_gt_2pct_count": int((diff_sp > 0.02).sum()),
        "sp500_monthly_ret_gt_5pct_count": int((diff_sp > 0.05).sum()),
        "top_outliers_sample": outliers.head(15).to_dict(orient="records"),
        "smallcap_wiki_vs_yahoo": sc_overlap_info,
    }


def audit_universes_sp_ndx_smallcap():
    # 1. S&P 500 coverage funnel & gap ledger
    cf = pd.read_csv(SSM / "results/coverage_funnel_by_month.csv")
    gl = pd.read_csv(SSM / "results/gap_ledger.csv")
    ex = pd.read_csv(SSM / "data/exit_resolutions.csv")
    idr = pd.read_csv(SSM / "data/identity_resolutions.csv")
    ise = pd.read_csv(SSM / "results/identity_screen_earnings.csv")

    # 2. Nasdaq-100 universe
    ndx_m = pd.read_csv(SSM / "data/ndx_monthly_members.csv")
    ndx_counts = ndx_m.groupby("month_end")["ticker"].nunique()

    # 3. Small/Mid-Cap Holdout store & PIT defects
    qf = pd.read_csv(SSM / "data/smallcap/quality_flags.csv")
    pc = pd.read_csv(SSM / "data/smallcap/price_corrections.csv")
    us = pd.read_csv(SSM / "data/smallcap/universe_size.csv")
    ps = pd.read_csv(SSM / "data/smallcap/price_source.csv")

    f1 = qf[qf["flag"] == "F1_spike_reversal"].copy()
    f1_same_day_bug = int((f1["date"] == f1["end"]).sum())

    # Check F2 split corrections in price_corrections.csv against actual recorded split ratios!
    f2_mismatches = []
    for r in pc.itertuples():
        tk = str(r.ticker)
        # Look up recorded splits in raw_smallcap or wiki
        sp_candidates = []
        p_sc = SSM / "data/raw_smallcap" / f"{tk}.json"
        if p_sc.exists():
            jd = json.loads(p_sc.read_text())
            for sdt, num, den in jd.get("splits", []):
                if num and den:
                    sr = float(num) / float(den)
                    sp_candidates.extend([sr, 1.0 / sr])
        applied = float(r.factor)
        matched_sr = any(abs(applied - sr) / max(sr, 1e-9) <= 0.02 for sr in sp_candidates)
        if not matched_sr:
            f2_mismatches.append({
                "ticker": tk,
                "end": r.end,
                "applied_factor": round(applied, 6),
                "recorded_split_factors_nearby": [round(x, 6) for x in sp_candidates[:6]],
                "evidence": str(r.evidence)[:120],
            })

    # Check Small-Cap PIT SEC operating-company eligibility across SEC FSDS sub_*.parquet!
    sub_files = sorted(glob.glob(str(SSM / "data/fundamentals/sec_raw/sub_*.parquet")))
    sec_pit_stats = {}
    if sub_files:
        subs = []
        for sf in sub_files:
            df_s = pd.read_parquet(sf, columns=["cik", "name", "sic", "form", "filed"])
            df_s = df_s[df_s["form"].isin(["10-K", "10-K/A", "10-Q", "10-Q/A"])]
            subs.append(df_s)
        all_sub = pd.concat(subs, ignore_index=True)
        all_sub["cik"] = pd.to_numeric(all_sub["cik"], errors="coerce").astype("Int64")
        all_sub["sic"] = pd.to_numeric(all_sub["sic"], errors="coerce").astype("Int64")
        all_sub["filed_dt"] = pd.to_datetime(all_sub["filed"].astype(str), format="%Y%m%d", errors="coerce")

        # Load smallcap_candidates.csv
        scc = pd.read_csv(SSM / "data/smallcap_candidates.csv")
        scc["cik"] = pd.to_numeric(scc["cik"], errors="coerce").astype("Int64")
        cik_first_10k10q = all_sub.groupby("cik")["filed_dt"].min().to_dict()
        cik_sics = all_sub.dropna(subset=["sic"]).groupby("cik")["sic"].agg(lambda s: sorted(set(int(x) for x in s))).to_dict()
        non_op_sics = {6221, 6770, 6722, 6726, 6799}

        # Check actual winners_holdout main (non-stress/non-strict) picks against SEC PIT 10-K/10-Q & latest SIC as of t!
        all_sub_sorted = all_sub.dropna(subset=["cik", "filed_dt"]).sort_values("filed_dt")
        cik_filings = {int(c): g[["filed_dt", "sic"]].values.tolist() for c, g in all_sub_sorted.groupby("cik")}

        wh_no_prior_10k10q = []
        wh_nonop_sic_at_t = []
        for led_p in sorted(glob.glob(str(SSM / "results/winners_holdout/monthly_*.csv"))):
            sname = Path(led_p).stem
            if "STRICT" in sname or "stress" in sname or "REF_SPY" in sname:
                continue
            ldf = pd.read_csv(led_p)
            if "picks" not in ldf.columns:
                continue
            tk_to_cik = dict(zip(scc["ticker"].astype(str), scc["cik"]))
            for row in ldf.itertuples():
                if pd.isna(row.picks) or not str(row.picks):
                    continue
                m_dt = pd.Timestamp(str(row.month))
                form_dt = m_dt - pd.offsets.MonthEnd(1)
                for tk in str(row.picks).split("|"):
                    if tk in ("CASH", ""):
                        continue
                    cik = tk_to_cik.get(tk)
                    if cik is not None and pd.notna(cik):
                        icik = int(cik)
                        fmin = cik_first_10k10q.get(icik)
                        # Check post-2012-01-01 (after SEC XBRL Phase-3 mandate covered all US operating filers)
                        if form_dt >= pd.Timestamp("2012-01-01") and (fmin is None or fmin > form_dt):
                            wh_no_prior_10k10q.append({
                                "ledger": sname,
                                "holding_month": str(row.month),
                                "ticker": tk,
                                "cik": icik,
                                "first_10K_10Q": str(fmin.date()) if fmin is not None else None,
                            })
                        hist = [s for fd, s in cik_filings.get(icik, []) if fd <= form_dt and pd.notna(s)]
                        cur_sic = int(hist[-1]) if hist else None
                        if cur_sic in non_op_sics:
                            wh_nonop_sic_at_t.append({
                                "ledger": sname,
                                "holding_month": str(row.month),
                                "ticker": tk,
                                "cik": icik,
                                "pit_sic": cur_sic,
                            })

        non_op_candidates = [
            {"ticker": r.ticker, "cik": int(r.cik), "sics": cik_sics.get(int(r.cik), [])}
            for r in scc.dropna(subset=["cik"]).itertuples()
            if set(cik_sics.get(int(r.cik), [])).issubset(non_op_sics) and len(cik_sics.get(int(r.cik), [])) > 0
        ]
        no_filing_pre2018 = [
            r.ticker
            for r in scc.dropna(subset=["cik"]).itertuples()
            if cik_first_10k10q.get(int(r.cik), pd.Timestamp("2099-01-01")) > pd.Timestamp("2018-03-31")
        ]
        sec_pit_stats = {
            "smallcap_candidates_total": int(len(scc)),
            "candidates_pure_non_operating_trust_SPAC_SIC": len(non_op_candidates),
            "pure_non_operating_SIC_examples": non_op_candidates[:20],
            "candidates_with_no_SEC_10K_10Q_until_after_2018_03": len(no_filing_pre2018),
            "main_holdout_trade_picks_with_no_prior_10K_10Q_count": len(wh_no_prior_10k10q),
            "main_holdout_trade_picks_with_no_prior_10K_10Q_unique_tickers": sorted(list({x["ticker"] for x in wh_no_prior_10k10q})),
            "main_holdout_trade_picks_with_no_prior_10K_10Q_sample": wh_no_prior_10k10q[:25],
            "main_holdout_trade_picks_with_non_operating_PIT_SIC_count": len(wh_nonop_sic_at_t),
            "main_holdout_trade_picks_with_non_operating_PIT_SIC_sample": wh_nonop_sic_at_t[:25],
        }

    return {
        "sp500": {
            "formation_months": int(len(cf)),
            "members_min_median_max": [
                int(cf["members"].min()),
                float(cf["members"].median()),
                int(cf["members"].max()),
            ],
            "eligible_min_median_max": [
                int(cf["eligible"].min()),
                float(cf["eligible"].median()),
                int(cf["eligible"].max()),
            ],
            "gap_ledger_total_rows": int(len(gl)),
            "gap_ledger_by_category": gl["category"].value_counts().to_dict() if "category" in gl.columns else {},
            "manual_exit_resolutions": ex.to_dict(orient="records"),
            "identity_resolutions": idr.to_dict(orient="records"),
            "earnings_volatility_identity_screen_rows": int(len(ise)),
        },
        "nasdaq100": {
            "months": int(ndx_counts.shape[0]),
            "unique_tickers_all_time": int(ndx_m["ticker"].nunique()),
            "members_per_month_min_median_max": [
                int(ndx_counts.min()),
                float(ndx_counts.median()),
                int(ndx_counts.max()),
            ],
        },
        "smallcap": {
            "price_source_counts": ps["source"].value_counts().to_dict() if "source" in ps.columns else {},
            "quality_flags_by_type": qf["flag"].value_counts().to_dict(),
            "F1_spike_reversal_total": int(len(f1)),
            "F1_single_day_skipped_by_strict_lt_end_bug": f1_same_day_bug,
            "F2_price_corrections_total": int(len(pc)),
            "F2_corrections_not_matching_exact_split_factor_within_2pct": len(f2_mismatches),
            "F2_mismatch_examples": f2_mismatches[:15],
            "universe_size_rows": int(len(us)),
            "sec_pit_operating_company_audit": sec_pit_stats,
        },
    }


def main():
    print("[01] Auditing all 8 raw equity price/open/volume stores...")
    store_summary, open_check, raw_cache = audit_raw_json_stores()
    print("[01] Cross-checking S&P 500 prices & membership defects against BlackRock official IVV (68,620 rows)...")
    ivv_audit = audit_ivv_external_prices_and_sectors(raw_cache)
    print("[01] Cross-checking Yahoo vs Nasdaq Data Link WIKI (2009-2018 overlap)...")
    wiki_audit = audit_yahoo_vs_wiki_overlap(raw_cache)
    print("[01] Auditing S&P 500, Nasdaq-100, and Small/Mid-Cap universes & corporate actions...")
    univ_audit = audit_universes_sp_ndx_smallcap()

    report = {
        "raw_stores": store_summary,
        "raw_open_integrity": open_check,
        "external_ivv_verification": ivv_audit,
        "external_wiki_overlap_verification": wiki_audit,
        "universes_and_corporate_actions": univ_audit,
    }
    out_p = OUT_DIR / "01_equity_prices_and_universes_audit.json"
    out_p.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"[01] DONE -> {out_p}")
    print(f"     IVV matched stock-months: {ivv_audit.get('matched_ticker_months_with_same_day_quote')} | <=10bp: {ivv_audit.get('exact_match_within_10bp_pct')}% | <=1%: {ivv_audit.get('match_within_1pct_pct')}%")
    print(f"     Yahoo vs WIKI S&P stock-months: {wiki_audit.get('sp500_overlapping_stock_months')} | <=10bp: {wiki_audit.get('sp500_monthly_ret_within_10bp_pct')}% | <=1%: {wiki_audit.get('sp500_monthly_ret_within_1pct_pct')}%")
    print(f"     raw_open max factor error: {open_check['max_adj_open_factor_diff_across_all_files']}")


if __name__ == "__main__":
    main()
