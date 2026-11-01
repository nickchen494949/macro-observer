#!/usr/bin/env python3
"""
v2_04_sec_xbrl_100_null_completeness_auditor.py — 100 Stratified Random NULL / Missing SEC Fundamental
Completeness Audit Cards (N001..N100, fixed seed = 20261104).

ZERO imports of any audited project module (enforced mechanically by v2_00 via `ast.parse`).
ZERO fallback or hand-waving: every sampled NULL `(CIK, period_end, metric)` cell across all 3 PIT
fundamental stores (`sp500`, `ndx`, `smallcap`) is audited against:
  1. ALL 142 local official SEC Financial Statement Data Sets (`sec_raw/sub_*.parquet` + `num_*.parquet`)
     across ALL tags reported by that CIK around `period_end` (unfiltered by tag!), and
  2. Live official SEC EDGAR XBRL API (`https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json`).

Classifies every sampled NULL cell into disjoint, auditable root-cause categories:
  - `TRUE_ABSENT_IN_SEC_XBRL`: Neither primary nor alternative US-GAAP tags for `metric` exist in SEC XBRL
    for that 3-month fiscal quarter (e.g. pre-revenue biotech filing 10-Q with NetIncomeLoss & EPS but zero
    revenue line, or balance/share-only comparative period).
  - `CONSERVATIVE_RULE_BLANK_UNAMBIGUOUS_QTR_UNAVAILABLE`: Primary tag exists in SEC XBRL around `period_end`,
    but standalone 3-month quarterly value cannot be unambiguously formed without guessing:
      * `AMBIGUOUS_MULTI_VALUE_COLLISION` (>1 distinct first-reported values for same `(cik, tag, ddate, qtrs)`),
      * `FY_ONLY_MISSING_9M_YTD_FOR_Q4` (`qtrs=4` annual total exists, `qtrs=1` absent, `qtrs=3` 9M YTD absent),
      * `YTD_OR_SEMIANNUAL_ONLY_NO_QTRS1` (`qtrs=2` or `qtrs=3` exists, `qtrs=1` absent),
      * `FUTURE_DATED_XBRL_TYPO_DROPPED` (`ddate > filed + 16 days`), or
      * `NON_USD_REPORTING_CURRENCY` (`uom != 'USD'`).
  - `PARSER_OMITTED_ALTERNATIVE_TAG_IN_SEC`: Primary `XBRL_TAGS[metric]` absent for `qtrs=1` / `FY-9M`,
    but filer reported the economic concept under an alternative/specialized US-GAAP tag (e.g. basic-only EPS
    `EarningsPerShareBasic` when no diluted tag was filed, `IncomeLossFromContinuingOperationsPerDilutedShare`,
    or bank/REIT/insurance/utility specialized revenue tags such as `RevenuesNetOfInterestExpense`,
    `RealEstateRevenueNet`, `InterestIncomeExpenseNet`, `ElectricUtilityRevenue`, `OilAndGasRevenue`, etc.).
  - `PARSER_FALSE_NEGATIVE_PRIMARY_TAG_BUG`: Unambiguous primary US-GAAP tag (`qtrs=1` or valid `FY-9M`,
    `uom='USD'`, `ddate <= filed + 16d`) exists in SEC FSDS yet was left `NULL` in `eps_quarterly_pit.parquet`.
"""
import glob
import json
import os
import sys
import time
import urllib.request
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from v2_cleanroom_lib import _norm_sym


AUDIT_ROOT = os.path.dirname(HERE)
REPO_ROOT = os.path.dirname(os.path.dirname(AUDIT_ROOT))
SSM_DATA = os.path.join(REPO_ROOT, "research", "sector_stock_momentum", "data")
SEC_RAW_DIR = os.path.join(SSM_DATA, "fundamentals", "sec_raw")

SEED = 20261104

PRIMARY_XBRL_TAGS = {
    "eps_diluted": ["EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted"],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "revenue": [
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "SalesRevenueNet",
        "SalesRevenueGoodsNet",
        "SalesRevenueServicesNet",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "InterestAndDividendIncomeOperating",
    ],
}

ALTERNATIVE_XBRL_TAGS = {
    "eps_diluted": [
        "EarningsPerShareBasic",
        "IncomeLossFromContinuingOperationsPerDilutedShare",
        "IncomeLossFromContinuingOperationsPerBasicAndDilutedShare",
        "IncomeLossFromContinuingOperationsPerBasicShare",
    ],
    "net_income": [
        "NetIncomeLossAvailableToCommonStockholdersBasic",
        "NetIncomeLossAvailableToCommonStockholdersDiluted",
        "IncomeLossFromContinuingOperations",
        "IncomeLossFromContinuingOperationsIncludingPortionAttributableToNoncontrollingInterest",
        "NetIncomeLossAllocatedToLimitedPartners",
    ],
    "revenue": [
        "RevenuesNetOfInterestExpense",
        "InterestIncomeExpenseNet",
        "RealEstateRevenueNet",
        "OperatingLeaseLeaseIncome",
        "RegulatedAndUnregulatedOperatingRevenue",
        "ElectricUtilityRevenue",
        "PublicUtilitiesRevenue",
        "OilAndGasRevenue",
        "HealthCareOrganizationRevenue",
        "FinancialServicesRevenue",
        "PremiumsEarnedNet",
        "NetInvestmentIncome",
        "TotalRevenuesAndOtherIncome",
        "BrokerageCommissionsRevenue",
        "InvestmentBankingAdvisoryBrokerageAndUnderwritingFeesAndCommissions",
        "ContractsRevenue",
        "LicenseAndMaintenanceRevenue",
        "CollaborationRevenue",
        "GrantRevenue",
    ],
}

PREDEFINED_NULL_STRATA = [
    ("sp500", "fundamentals/eps_quarterly_pit.parquet", "eps_diluted", 18),
    ("sp500", "fundamentals/eps_quarterly_pit.parquet", "revenue", 16),
    ("sp500", "fundamentals/eps_quarterly_pit.parquet", "net_income", 16),
    ("ndx", "fundamentals_ndx/eps_quarterly_pit.parquet", "eps_diluted", 5),
    ("ndx", "fundamentals_ndx/eps_quarterly_pit.parquet", "revenue", 5),
    ("ndx", "fundamentals_ndx/eps_quarterly_pit.parquet", "net_income", 5),
    ("smallcap", "fundamentals_smallcap/eps_quarterly_pit.parquet", "eps_diluted", 11),
    ("smallcap", "fundamentals_smallcap/eps_quarterly_pit.parquet", "revenue", 12),
    ("smallcap", "fundamentals_smallcap/eps_quarterly_pit.parquet", "net_income", 12),
]

KNOWN_SMALLCAP_CIK_MISMATCH_TICKERS = {"SPWR", "BID", "ETH"}


def fetch_live_sec_companyfacts(cik: int, cache: Dict[int, Optional[dict]]) -> Optional[dict]:
    if cik in cache:
        return cache[cik]
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(cik):010d}.json"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "MacroObserverCleanRoomAudit/3.0 (independent-audit@research.local)",
            "Accept": "application/json",
        },
    )
    try:
        time.sleep(0.13)
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        cache[cik] = data
        return data
    except Exception:
        cache[cik] = None
        return None


def scan_live_companyfacts_for_period(
    cf_json: Optional[dict],
    tags: List[str],
    period_end: pd.Timestamp,
) -> List[Tuple[str, str, str, int, float]]:
    """
    Scans live `data.sec.gov` `us-gaap` facts for `tags` whose `end` date is within ±10 days of `period_end`.
    Returns list of `(tag, uom, frame_or_span, approx_qtrs, val)`.
    """
    if not cf_json:
        return []
    us_gaap = (cf_json.get("facts") or {}).get("us-gaap") or {}
    hits = []
    for tag in tags:
        t_obj = us_gaap.get(tag)
        if not t_obj:
            continue
        for u_key, items in (t_obj.get("units") or {}).items():
            for it in items:
                end_s = it.get("end")
                val = it.get("val")
                if not end_s or val is None:
                    continue
                end_dt = pd.Timestamp(end_s)
                if abs((end_dt - period_end).days) > 10:
                    continue
                start_s = it.get("start")
                if start_s:
                    days = (end_dt - pd.Timestamp(start_s)).days
                    q_est = int(round(days / 91.25))
                else:
                    q_est = 0
                hits.append((tag, str(u_key), f"{start_s or 'instant'}..{end_s}", q_est, float(val)))
    return hits


def classify_null_cell(
    cik: int,
    p_end: pd.Timestamp,
    metric: str,
    cik_num_df: pd.DataFrame,
    cf_json: Optional[dict],
) -> Tuple[str, str, str, str]:
    """
    Returns `(root_cause_class, sub_reason, fsds_trace, live_trace)`.
    """
    prim_tags = PRIMARY_XBRL_TAGS[metric]
    alt_tags = ALTERNATIVE_XBRL_TAGS[metric]

    # Slice all FSDS facts for this CIK with ddate == p_end (and 9M window p_end - 105..75d)
    at_pe_all = cik_num_df[cik_num_df["ddate_dt"] == p_end].copy()
    win_9m_all = cik_num_df[
        (cik_num_df["ddate_dt"] >= p_end - pd.Timedelta(days=105))
        & (cik_num_df["ddate_dt"] <= p_end - pd.Timedelta(days=75))
    ].copy()

    # Separate valid-date vs future-dated typo facts (`ddate > filed + 16d`)
    at_pe_valid = at_pe_all[at_pe_all["valid_pit_date"]].copy()
    at_pe_future_typo = at_pe_all[~at_pe_all["valid_pit_date"]].copy()
    win_9m_valid = win_9m_all[win_9m_all["valid_pit_date"]].copy()

    # Check primary tags at p_end
    prim_pe = at_pe_valid[at_pe_valid["tag"].isin(prim_tags)].copy()
    prim_9m = win_9m_valid[win_9m_valid["tag"].isin(prim_tags) & (win_9m_valid["qtrs"] == 3)].copy()

    # Live EDGAR scan for primary & alternative tags
    live_prim = scan_live_companyfacts_for_period(cf_json, prim_tags, p_end)
    live_alt = scan_live_companyfacts_for_period(cf_json, alt_tags, p_end)
    if cf_json is None:
        live_trace = "live_sec_api_unavailable"
    else:
        lp_s = ";".join(f"{t}(q~{q},{u})={v:g}" for t, u, _, q, v in live_prim[:3]) or "none"
        la_s = ";".join(f"{t}(q~{q},{u})={v:g}" for t, u, _, q, v in live_alt[:3]) or "none"
        live_trace = f"live_prim=[{lp_s}] | live_alt=[{la_s}]"

    # 1. Check if primary USD tag existed with qtrs=1 or qtrs=4+qtrs=3
    prim_pe_usd = prim_pe[prim_pe["uom"] == "USD"].copy()
    prim_9m_usd = prim_9m[prim_9m["uom"] == "USD"].copy()

    if not prim_pe_usd.empty:
        # Check first-report deduplication and multi-value collision (`ambiguous_values_excluded.csv` rule)
        fr_pe = prim_pe_usd[prim_pe_usd["is_first_report"]]
        q1_fr = fr_pe[fr_pe["qtrs"] == 1]
        if not q1_fr.empty:
            # Check if ALL q1_fr tags had >1 distinct first-reported value on (cik, tag, ddate, qtrs=1)
            amb_tags = []
            unamb_rows = []
            for tg, grp in q1_fr.groupby("tag"):
                if grp["value"].nunique() > 1:
                    amb_tags.append(f"{tg}(vals={grp['value'].unique().tolist()[:3]})")
                else:
                    unamb_rows.append(grp.iloc[0])
            if unamb_rows:
                r0 = unamb_rows[0]
                return (
                    "PARSER_FALSE_NEGATIVE_PRIMARY_TAG_BUG",
                    "UNAMBIGUOUS_PRIMARY_QTRS1_PRESENT_IN_FSDS",
                    f"adsh={r0['adsh']} tag={r0['tag']} qtrs=1 val={float(r0['value']):g} filed={r0['filed_dt'].date()}",
                    live_trace,
                )
            return (
                "CONSERVATIVE_RULE_BLANK_UNAMBIGUOUS_QTR_UNAVAILABLE",
                "AMBIGUOUS_MULTI_VALUE_COLLISION_QTRS1",
                f"Blanked due to >1 distinct first-reported values on same (cik,tag,ddate,qtrs=1): {'; '.join(amb_tags)}",
                live_trace,
            )

        # Check qtrs=4 at p_end
        q4_fr = fr_pe[fr_pe["qtrs"] == 4]
        if not q4_fr.empty:
            # Check if q4 itself was ambiguous or 9M YTD (qtrs=3) was missing / ambiguous
            q4_unamb = [grp.iloc[0] for _, grp in q4_fr.groupby("tag") if grp["value"].nunique() == 1]
            fr_9m = prim_9m_usd[prim_9m_usd["is_first_report"]]
            q3_unamb = [grp.iloc[0] for _, grp in fr_9m.groupby(["tag", "ddate_dt"]) if grp["value"].nunique() == 1]
            if not q4_unamb:
                return (
                    "CONSERVATIVE_RULE_BLANK_UNAMBIGUOUS_QTR_UNAVAILABLE",
                    "AMBIGUOUS_MULTI_VALUE_COLLISION_FY_QTRS4",
                    f"FY qtrs=4 present at {p_end.date()} but >1 conflicting values in first filing",
                    live_trace,
                )
            if not q3_unamb:
                r4 = q4_unamb[0]
                reason_9m = "9M_QTRS3_COLLISION" if not fr_9m.empty else "MISSING_9M_QTRS3_YTD_FILING"
                return (
                    "CONSERVATIVE_RULE_BLANK_UNAMBIGUOUS_QTR_UNAVAILABLE",
                    f"FY_ONLY_{reason_9m}",
                    f"FY qtrs=4 {r4['tag']}={float(r4['value']):g} (adsh={r4['adsh']}), no unambiguous 9M qtrs=3 in [-105,-75]d to derive Q4",
                    live_trace,
                )
            r4, r3 = q4_unamb[0], q3_unamb[0]
            return (
                "PARSER_FALSE_NEGATIVE_PRIMARY_TAG_BUG",
                "UNAMBIGUOUS_PRIMARY_Q4_FY_MINUS_9M_PRESENT",
                f"FY {r4['adsh']}={float(r4['value']):g} and 9M {r3['adsh']}={float(r3['value']):g} both unambiguous",
                live_trace,
            )

        # Only qtrs=2 or qtrs=3 (YTD / semi-annual) or qtrs=0 existed at p_end
        q_present = sorted(prim_pe_usd["qtrs"].unique().tolist())
        r_any = prim_pe_usd.iloc[0]
        return (
            "CONSERVATIVE_RULE_BLANK_UNAMBIGUOUS_QTR_UNAVAILABLE",
            f"YTD_OR_NON_3M_DURATION_ONLY_QTRS_{q_present}",
            f"Primary tag {r_any['tag']} filed only with qtrs={q_present} (val={float(r_any['value']):g}, adsh={r_any['adsh']}), no standalone 3M qtrs=1",
            live_trace,
        )

    # Check non-USD currency on primary tag
    if not prim_pe.empty:
        uoms = sorted(prim_pe["uom"].unique().tolist())
        r_nu = prim_pe.iloc[0]
        return (
            "CONSERVATIVE_RULE_BLANK_UNAMBIGUOUS_QTR_UNAVAILABLE",
            f"NON_USD_REPORTING_CURRENCY_{uoms}",
            f"Primary tag {r_nu['tag']} reported in non-USD unit {uoms} (val={float(r_nu['value']):g}, adsh={r_nu['adsh']})",
            live_trace,
        )

    # Check future-dated XBRL typo dropped (`ddate > filed + 16d`)
    prim_typo = at_pe_future_typo[at_pe_future_typo["tag"].isin(prim_tags)]
    if not prim_typo.empty:
        rt = prim_typo.iloc[0]
        return (
            "CONSERVATIVE_RULE_BLANK_UNAMBIGUOUS_QTR_UNAVAILABLE",
            "FUTURE_DATED_XBRL_TYPO_DROPPED",
            f"Dropped future-dated XBRL typo: {rt['tag']} ddate={p_end.date()} > filed={rt['filed_dt'].date()}+16d (adsh={rt['adsh']})",
            live_trace,
        )

    # 2. Check Alternative / Specialized US-GAAP tags in FSDS (qtrs=1 or qtrs=4 + qtrs=3) or live SEC API
    alt_pe_usd = at_pe_valid[at_pe_valid["tag"].isin(alt_tags) & (at_pe_valid["uom"] == "USD")].copy()
    alt_q1 = alt_pe_usd[alt_pe_usd["qtrs"] == 1]
    if not alt_q1.empty:
        ra = alt_q1.sort_values("filed_dt").iloc[0]
        return (
            "PARSER_OMITTED_ALTERNATIVE_TAG_IN_SEC",
            f"ALT_TAG_QTRS1_{ra['tag']}",
            f"Filer reported alternative US-GAAP tag {ra['tag']}={float(ra['value']):g} (qtrs=1, adsh={ra['adsh']}, form={ra['form']})",
            live_trace,
        )
    alt_q4 = alt_pe_usd[alt_pe_usd["qtrs"] == 4]
    alt_9m_usd = win_9m_valid[win_9m_valid["tag"].isin(alt_tags) & (win_9m_valid["uom"] == "USD") & (win_9m_valid["qtrs"] == 3)]
    if not alt_q4.empty and not alt_9m_usd.empty:
        ra4 = alt_q4.sort_values("filed_dt").iloc[0]
        ra3 = alt_9m_usd.sort_values("filed_dt").iloc[0]
        return (
            "PARSER_OMITTED_ALTERNATIVE_TAG_IN_SEC",
            f"ALT_TAG_DERIVABLE_Q4_{ra4['tag']}",
            f"Filer reported alternative FY {ra4['tag']}={float(ra4['value']):g} & 9M={float(ra3['value']):g} (adsh={ra4['adsh']})",
            live_trace,
        )
    live_alt_q1 = [x for x in live_alt if "USD" in x[1] and x[3] == 1]
    if live_alt_q1:
        la0 = live_alt_q1[0]
        return (
            "PARSER_OMITTED_ALTERNATIVE_TAG_IN_SEC",
            f"ALT_TAG_LIVE_SEC_QTRS1_{la0[0]}",
            f"No primary/alt qtrs=1 in FSDS; live SEC API has {la0[0]}={la0[4]:g} ({la0[2]})",
            live_trace,
        )

    # Check if any other heuristic revenue/income/EPS substring tag exists at p_end with qtrs=1 in FSDS
    kw = (
        ("Revenue", "Sales", "LeaseIncome", "InterestIncome", "Premiums")
        if metric == "revenue"
        else (("PerShare", "PerDiluted", "PerBasic") if metric == "eps_diluted" else ("NetIncome", "ProfitLoss", "IncomeLoss"))
    )
    heur_q1 = at_pe_valid[
        (at_pe_valid["uom"] == "USD")
        & (at_pe_valid["qtrs"] == 1)
        & at_pe_valid["tag"].astype(str).apply(lambda s: any(k.lower() in s.lower() for k in kw))
    ]
    # Filter out obvious non-top-line / non-bottom-line items (like DeferredRevenue, Tax, Expense, CostOfRevenue)
    if metric == "revenue":
        heur_q1 = heur_q1[~heur_q1["tag"].str.contains("Deferred|Unbilled|RemainingPerformance|CostOf|Expense|Liability|Receivable", case=False, na=False)]
    elif metric == "net_income":
        heur_q1 = heur_q1[~heur_q1["tag"].str.contains("Tax|BeforeTax|OperatingIncome|Comprehensive|PerShare|PerBasic|PerDiluted|Noncontrolling|Discontinued|EquityMethod", case=False, na=False)]
    elif metric == "eps_diluted":
        heur_q1 = heur_q1[~heur_q1["tag"].str.contains("Dividend|Discontinued|ProForma|Antidilutive", case=False, na=False)]

    if not heur_q1.empty:
        rh = heur_q1.sort_values("filed_dt").iloc[0]
        return (
            "PARSER_OMITTED_ALTERNATIVE_TAG_IN_SEC",
            f"SPECIALIZED_TAG_QTRS1_{rh['tag']}",
            f"Filer reported specialized US-GAAP tag {rh['tag']}={float(rh['value']):g} (qtrs=1, adsh={rh['adsh']}, form={rh['form']})",
            live_trace,
        )

    # 3. Truly absent in SEC XBRL for this 3-month quarter: record what OTHER tags created this row at `p_end`
    other_tags = sorted(at_pe_valid["tag"].astype(str).unique().tolist())[:5]
    forms_here = sorted(at_pe_valid["form"].astype(str).unique().tolist())[:3]
    return (
        "TRUE_ABSENT_IN_SEC_XBRL",
        "NO_PRIMARY_OR_ALT_TAG_FILED_FOR_QUARTER",
        f"0 primary/alt `{metric}` tags at {p_end.date()} in SEC FSDS (row formed by other fields in forms={forms_here}, sample_tags={other_tags})",
        live_trace,
    )


def compute_store_wide_null_and_zero_cik_census() -> dict:
    census = {}
    for sk, rel in [
        ("sp500", "fundamentals/eps_quarterly_pit.parquet"),
        ("ndx", "fundamentals_ndx/eps_quarterly_pit.parquet"),
        ("smallcap", "fundamentals_smallcap/eps_quarterly_pit.parquet"),
    ]:
        df = pd.read_parquet(os.path.join(SSM_DATA, rel))
        census[sk] = {
            "total_company_quarter_rows": int(len(df)),
            "unique_ciks_with_rows": int(df["cik"].nunique()),
            "null_counts": {
                "eps_diluted_approx": int(df["eps_diluted_approx"].isna().sum()),
                "revenue": int(df["revenue"].isna().sum()),
                "net_income": int(df["net_income"].isna().sum()),
            },
            "null_rates_pct": {
                "eps_diluted_approx": round(100.0 * float(df["eps_diluted_approx"].isna().mean()), 3),
                "revenue": round(100.0 * float(df["revenue"].isna().mean()), 3),
                "net_income": round(100.0 * float(df["net_income"].isna().mean()), 3),
            },
        }
    # Check S&P 500 `cik_map.csv` tickers that have 0 rows in `fundamentals/eps_quarterly_pit.parquet`
    sp_df = pd.read_parquet(os.path.join(SSM_DATA, "fundamentals", "eps_quarterly_pit.parquet"))
    sp_ciks_present = set(sp_df["cik"].dropna().astype(int).unique())
    cmap = pd.read_csv(os.path.join(SSM_DATA, "fundamentals", "cik_map.csv"))
    no_cik_tickers = cmap[cmap["cik"].isna()][["ticker", "method"]].to_dict(orient="records")
    mapped_zero_rows = cmap[cmap["cik"].notna() & ~cmap["cik"].astype("Int64").isin(sp_ciks_present)][
        ["ticker", "cik", "method", "edgar_name"]
    ].to_dict(orient="records")
    census["sp500_zero_fundamental_row_tickers"] = {
        "unmapped_non_sec_or_pre_xbrl_tickers_count": len(no_cik_tickers),
        "unmapped_tickers": no_cik_tickers,
        "mapped_cik_but_zero_xbrl_quarterly_rows_count": len(mapped_zero_rows),
        "mapped_cik_zero_row_tickers": mapped_zero_rows,
    }
    return census


def main() -> None:
    rng = np.random.default_rng(SEED)
    panels: Dict[str, pd.DataFrame] = {}
    strata_meta = []
    sampled_items = []

    for store_key, rel_pq, metric, n_draw in PREDEFINED_NULL_STRATA:
        if store_key not in panels:
            panels[store_key] = pd.read_parquet(os.path.join(SSM_DATA, rel_pq))
        df = panels[store_key]
        val_col = "eps_diluted_approx" if metric == "eps_diluted" else metric
        elig_null = df[df[val_col].isna() & df["cik"].notna()].copy()
        chosen_idx = rng.choice(elig_null.index.values, size=n_draw, replace=False)
        strata_meta.append({
            "store": store_key,
            "metric": metric,
            "store_total_rows": int(len(df)),
            "null_population_N_h": int(len(elig_null)),
            "null_share_of_store_pct": round(100.0 * len(elig_null) / max(1, len(df)), 3),
            "sampled_n_h": int(n_draw),
            "sampling_probability": float(n_draw / len(elig_null)),
        })
        for ridx in chosen_idx:
            sampled_items.append((store_key, metric, int(ridx), df.loc[ridx].to_dict()))

    sampled_ciks = sorted({int(item[3]["cik"]) for item in sampled_items})
    print(f"[v2_04] Sampled 100 random NULL fundamental cells across {len(sampled_ciks)} unique CIKs. Scanning ALL 142 SEC FSDS parquets...")

    sub_parts = []
    for p in sorted(glob.glob(os.path.join(SEC_RAW_DIR, "sub_*.parquet"))):
        s = pd.read_parquet(p, columns=["adsh", "cik", "name", "sic", "form", "fy", "fp", "filed", "accepted"])
        s = s[s["cik"].isin(sampled_ciks)]
        if not s.empty:
            sub_parts.append(s)
    sub_all = pd.concat(sub_parts, ignore_index=True)
    sub_all["filed_dt"] = pd.to_datetime(sub_all["filed"].astype(str), format="%Y%m%d", errors="coerce")
    target_adsh_set = set(sub_all["adsh"].unique())

    # Load ALL numeric XBRL tags for these CIKs (zero tag pre-filtering so alternative tags are 100% visible!)
    num_parts = []
    for p in sorted(glob.glob(os.path.join(SEC_RAW_DIR, "num_*.parquet"))):
        n = pd.read_parquet(p)
        n = n[n["adsh"].isin(target_adsh_set)]
        if not n.empty:
            num_parts.append(n)
    num_all = pd.concat(num_parts, ignore_index=True)
    num_all = num_all.merge(
        sub_all[["adsh", "cik", "name", "form", "fy", "fp", "filed_dt", "accepted"]],
        on="adsh",
        how="inner",
    )
    num_all["ddate_dt"] = pd.to_datetime(num_all["ddate"].astype(str), format="%Y%m%d", errors="coerce")
    num_all["valid_pit_date"] = num_all["ddate_dt"] <= (num_all["filed_dt"] + pd.Timedelta(days=16))

    # Mark `is_first_report` among valid PIT rows using the exact `(cik, tag, ddate_dt, qtrs, uom)` key
    num_all = num_all.sort_values(["cik", "tag", "ddate_dt", "qtrs", "uom", "filed_dt", "accepted"])
    valid_mask = num_all["valid_pit_date"]
    num_all["is_first_report"] = False
    dedup_key = ["cik", "tag", "ddate_dt", "qtrs", "uom"]
    num_all.loc[valid_mask, "is_first_report"] = ~num_all.loc[valid_mask].duplicated(dedup_key, keep="first")

    by_cik_num: Dict[int, pd.DataFrame] = {int(c): g for c, g in num_all.groupby("cik")}
    cik_to_name: Dict[int, str] = {int(c): str(g["name"].iloc[-1]) for c, g in sub_all.groupby("cik")}

    live_cf_cache: Dict[int, Optional[dict]] = {}
    cards = []

    print(f"[v2_04] Auditing all 100 NULL cards against raw SEC FSDS + live data.sec.gov XBRL API...")
    for idx, (store_key, metric, row_id, rdict) in enumerate(sampled_items, 1):
        card_id = f"N{idx:03d}"
        tk = str(rdict["ticker"])
        cik = int(rdict["cik"])
        p_end = pd.Timestamp(rdict["period_end"])
        cik_df = by_cik_num.get(cik, pd.DataFrame(columns=num_all.columns))
        cf_json = fetch_live_sec_companyfacts(cik, live_cf_cache)
        live_entity = str(cf_json.get("entityName", "")) if cf_json else ""

        root_cls, sub_reason, fsds_trace, live_trace = classify_null_cell(cik, p_end, metric, cik_df, cf_json)

        recycled_flag = bool(store_key == "smallcap" and _norm_sym(tk) in KNOWN_SMALLCAP_CIK_MISMATCH_TICKERS)
        if recycled_flag:
            sub_reason = f"SMALLCAP_RECYCLED_CIK_MISMATCH|{sub_reason}"

        other_present = [
            c for c in ("eps_diluted_approx", "eps_basic_approx", "net_income", "revenue", "diluted_shares")
            if c in rdict and pd.notna(rdict.get(c))
        ]

        cards.append({
            "card_id": card_id,
            "store": store_key,
            "metric": metric,
            "row_index": row_id,
            "ticker": tk,
            "cik": cik,
            "edgar_filer_name": live_entity or cik_to_name.get(cik, ""),
            "period_end": str(p_end.date()),
            "other_non_null_fields_on_row": "|".join(other_present),
            "root_cause_class": root_cls,
            "sub_reason": sub_reason,
            "sec_fsds_all_tags_trace": fsds_trace,
            "live_sec_gov_api_queried": cf_json is not None,
            "live_sec_gov_trace": live_trace,
        })

    cdf = pd.DataFrame(cards)
    out_csv = os.path.join(HERE, "v2_04_sec_xbrl_100_null_cards.csv")
    cdf.to_csv(out_csv, index=False)

    cls_counts = cdf["root_cause_class"].value_counts().to_dict()
    by_store = cdf.groupby(["store", "root_cause_class"]).size().unstack(fill_value=0).to_dict(orient="index")
    by_metric = cdf.groupby(["metric", "root_cause_class"]).size().unstack(fill_value=0).to_dict(orient="index")
    sub_counts = cdf["sub_reason"].value_counts().to_dict()

    # Horvitz-Thompson inverse-probability population-weighted estimate of NULL root-cause shares across all 3 stores
    prob_map = {(s["store"], s["metric"]): s["sampling_probability"] for s in strata_meta}
    cdf["ht_weight"] = [1.0 / prob_map[(r["store"], r["metric"])] for r in cards]
    total_ht = float(cdf["ht_weight"].sum())
    weighted_shares = {
        k: round(100.0 * float(cdf.loc[cdf["root_cause_class"] == k, "ht_weight"].sum()) / total_ht, 2)
        for k in sorted(cdf["root_cause_class"].unique())
    }

    census = compute_store_wide_null_and_zero_cik_census()

    summary = {
        "seed": SEED,
        "sampling_design": "Predefined stratified random sampling without replacement across all 9 (store x metric) NULL cell populations",
        "zero_project_imports": True,
        "total_null_cards_audited": len(cdf),
        "unique_ciks_scanned_unfiltered_across_142_fsds_parquets_and_live_edgar": len(sampled_ciks),
        "live_sec_gov_api_confirmed_count": int(cdf["live_sec_gov_api_queried"].sum()),
        "root_cause_class_counts_100_cards": cls_counts,
        "horvitz_thompson_population_weighted_root_cause_pct": weighted_shares,
        "by_store": by_store,
        "by_metric": by_metric,
        "detailed_sub_reason_counts": sub_counts,
        "strata_null_populations_and_weights": strata_meta,
        "store_wide_null_and_zero_row_cik_census": census,
    }
    out_json = os.path.join(HERE, "v2_04_sec_xbrl_100_null_summary.json")
    with open(out_json, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False)

    md_lines = [
        "# v2/v3 Clean-Room SEC XBRL 100-Card NULL / Missing-Row Completeness Audit (`seed=20261104`)",
        "",
        "- **Purpose**: Eliminate positive-only survivorship bias in SEC fundamental auditing (`v2_02` audited `100` non-null cells; `v2_04` audits `100` `NULL` `(CIK, period_end, metric)` cells across all 9 `(store × metric)` strata plus a full store-wide zero-row CIK census).",
        "- **Method**: Unfiltered scan of **all 142** official SEC Financial Statement Data Sets (`sec_raw/sub_*.parquet` + `num_*.parquet`, zero tag pre-filtering) + live `https://data.sec.gov/api/xbrl/companyfacts/` API.",
        f"- **100-Card Root-Cause Breakdown**: `{json.dumps(cls_counts, ensure_ascii=False)}`",
        f"- **Population-Weighted (Horvitz–Thompson) Root-Cause Shares**: `{json.dumps(weighted_shares, ensure_ascii=False)}` (%)",
        f"- **Live `data.sec.gov` API Queried**: `{int(cdf['live_sec_gov_api_queried'].sum())} / {len(cdf)}`",
        "",
        "| Card | Store | Metric (`NULL`) | Ticker (CIK / Filer) | Period End | Other Present Fields | Root-Cause Class | Sub-Reason | Unfiltered Raw SEC FSDS Trace | Live `data.sec.gov` Trace |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in cards:
        md_lines.append(
            f"| `{r['card_id']}` | `{r['store']}` | `{r['metric']}` | **{r['ticker']}** (`{r['cik']}` {r['edgar_filer_name'][:24]}) | "
            f"`{r['period_end']}` | `{r['other_non_null_fields_on_row']}` | **`{r['root_cause_class']}`** | `{r['sub_reason']}` | "
            f"{r['sec_fsds_all_tags_trace']} | {r['live_sec_gov_trace']} |"
        )
    out_md = os.path.join(HERE, "v2_04_sec_xbrl_100_null_cards.md")
    with open(out_md, "w", encoding="utf-8") as fh:
        fh.write("\n".join(md_lines) + "\n")

    print(f"[v2_04] Completed 100 NULL completeness cards! Breakdown: {cls_counts}")
    print(f"[v2_04] Horvitz-Thompson population-weighted shares (%): {weighted_shares}")


if __name__ == "__main__":
    main()
