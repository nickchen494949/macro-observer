#!/usr/bin/env python3
"""
run_multibagger_layered_backtest.py — 100% Standalone Clean-Room Multi-Bagger Layered Momentum Backtest
=======================================================================================================
Tests the Pre-Frozen 4-Layer Multi-Bagger Reranking Progression & 4 Core Factor Versions:

  UNIVERSES TESTED:
    1. `Tech_Only`: PIT S&P 500 `Information Technology` (historical GICS 2016/2018/2023 as-of each `t`)
    2. `All_SP500`: PIT S&P 500 (`sp500_hist_components.csv` + spell-trust filter)

  CONCENTRATION & EXECUTION (FIXED):
    - Portfolio Concentration: `Top-1` (`k=1`) and `Top-3` (`k=3`, equal-weighted 1/3 per slot)
    - Execution: Next-Day Open-to-Open (`Open[t+1_day1] -> Open[t+2_day1]`), Drifted Weights
    - Transaction Cost: 0.1% (`10bp`) per side (both `Additive` and `Self-Financing` reported)
    - Risk-Control Filter: NONE (0% Cash, 100% Invested — isolating pure multi-bagger stock selection)

  PRE-FROZEN 4-LAYER PROGRESSION (Stage 1: `12-1` Top-20 Shortlist -> Stage 2: Equal-Weight Percentile Rank):
    - Layer 1 (`L1_Price_12_1_Baseline`): Pure `12-1` Price Momentum (`Close[t-1]/Close[t-12] - 1`)
    - Layer 2 (`L2_Price_Plus_Fund`):     `1/2 Price (12-1) + 1/2 PIT Fundamental Momentum`
                                          (EPS/Operating Profit Growth + Revenue Growth/Accel + Margin Improvement)
    - Layer 3 (`L3_Price_Fund_ResMom`):   `1/3 Price + 1/3 PIT Fundamental + 1/3 Residual Momentum (12-1 vs SPY+Sector)`
    - Layer 4 (`L4_Price_Fund_Res_52WH`): `1/4 Price + 1/4 PIT Fundamental + 1/4 Residual Momentum + 1/4 52W-High Proximity`

  4 CORE STANDALONE / PAIRWISE VERSIONS & ABLATIONS:
    - V1: `Price Momentum (12-1)` Baseline
    - V2: `Price (Top-20) + PIT Fundamental Momentum` (Composite + breakdown by Profit Growth, Rev Accel, Margin Imp)
    - V3: `Residual Momentum (12-1)` (Standalone & Top-20 Rerank; Market+Sector vs Market-Only; IR vs Cumulative)
    - V4: `Price Momentum + 52-Week-High Proximity` (Top-20 Rerank, Full-Universe 50/50, Lag-1 52WH)
    - V5: `Price + Residual Momentum + 52W-High Proximity` (Pure Price/Idiosyncratic Composite without SEC filing lag)
"""
import difflib
import glob
import json
import math
import os
import re
import sys
import time
from typing import Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
V2_LIB_DIR = os.path.join(REPO_ROOT, "outputs", "gemini_full_data_audit_20261031", "v2_standalone")
if V2_LIB_DIR not in sys.path:
    sys.path.insert(0, V2_LIB_DIR)

from v2_cleanroom_lib import (
    DOCUMENTED_MANUAL_CIKS,
    DOCUMENTED_NAME_HINTS,
    DOCUMENTED_TIME_SPLITS,
    NO_SEC_FILINGS_TICKERS,
    CleanRoomEquityStore,
    _norm_company_name,
    _norm_sym,
    solve_self_financing_capital,
)

ORIG_SSM_REL = "research/sector_stock_momentum"
COST_PER_SIDE = 0.0010
SHORTLIST_N = 20

SECTOR_ETF_MAP = {
    "Information Technology": "XLK",
    "Health Care": "XLV",
    "Financials": "XLF",
    "Consumer Discretionary": "XLY",
    "Communication Services": "XLC",
    "Industrials": "XLI",
    "Consumer Staples": "XLP",
    "Energy": "XLE",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Materials": "XLB",
    "Telecommunication Services": "XLC",
}

ALL_NEEDED_XBRL_TAGS = {
    "EarningsPerShareDiluted",
    "EarningsPerShareBasicAndDiluted",
    "EarningsPerShareBasic",
    "NetIncomeLoss",
    "ProfitLoss",
    "OperatingIncomeLoss",
    "GrossProfit",
    "CostOfRevenue",
    "CostOfGoodsAndServicesSold",
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "SalesRevenueNet",
    "SalesRevenueGoodsNet",
    "SalesRevenueServicesNet",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "InterestAndDividendIncomeOperating",
    "WeightedAverageNumberOfDilutedSharesOutstanding",
}


def _sic_to_sector(sic_val) -> Optional[str]:
    try:
        s = int(sic_val)
    except Exception:
        return None
    if 1000 <= s < 1500 and s not in (1311, 1381, 1382, 1389):
        return "Materials"
    if s in (1311, 1381, 1382, 1389, 2911, 2990, 4610, 4612, 4613, 4922, 4923, 5171, 5172):
        return "Energy"
    if 1500 <= s < 1800 or 4950 <= s < 4960:
        return "Industrials"
    if 8200 <= s < 8300 or s in (3651, 3630, 3634, 3639):
        return "Consumer Discretionary"
    if s in (2833, 2834, 2835, 2836, 3826, 3841, 3842, 3843, 3844, 3845, 3851, 5047, 5122, 8000, 8011, 8050, 8060, 8062, 8071, 8090, 8093, 6324):
        return "Health Care"
    if s in (3570, 3571, 3572, 3575, 3576, 3577, 3578, 3579, 3661, 3663, 3669, 3670, 3672, 3674, 3677, 3678, 3679, 3825, 3827, 7370, 7371, 7372, 7373, 7374, 7379, 3559):
        return "Information Technology"
    if s in (4800, 4812, 4813, 4822, 4833, 4841, 4899, 2711, 2721, 2731, 7812, 7819, 7822, 7829, 7830, 7841, 7900):
        return "Communication Services"
    if 4900 <= s < 5000:
        return "Utilities"
    if s == 6798 or 6500 <= s < 6600:
        return "Real Estate"
    if 6000 <= s < 6800:
        return "Financials"
    if 2000 <= s < 2200 or s in (5140, 5141, 5149, 5180, 5190, 5400, 5411, 5412, 2840, 2844):
        return "Consumer Staples"
    if 2800 <= s < 3000 or 2400 <= s < 2700 or 3200 <= s < 3400:
        return "Materials"
    if 5000 <= s < 6000 or 7000 <= s < 7100 or s in (3711, 3714, 3751, 2300, 2320, 3021, 3942, 3944, 7510):
        return "Consumer Discretionary"
    return "Industrials"


# ─────────────────────────────────────────────────────────────────────────────
# 1. Clean-Room CIK Map, Aliases, PIT Membership & Historical GICS Panel
# ─────────────────────────────────────────────────────────────────────────────
def cleanroom_reconstruct_cik_map_and_sub(ssm_dir: str, store: CleanRoomEquityStore) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    data_dir = os.path.join(ssm_dir, "data")
    sec_raw_dir = os.path.join(data_dir, "fundamentals", "sec_raw")
    subs = [pd.read_parquet(p, columns=["adsh", "cik", "name", "sic", "form", "fy", "fp", "filed", "accepted"]) for p in sorted(glob.glob(os.path.join(sec_raw_dir, "sub_*.parquet")))]
    sub = pd.concat(subs, ignore_index=True)
    sub["filed"] = pd.to_datetime(sub["filed"], format="%Y%m%d", errors="coerce")

    spans = pd.read_csv(os.path.join(data_dir, "sp500_ticker_start_end.csv"), parse_dates=["start_date", "end_date"])
    spans = spans[spans["end_date"].isna() | (spans["end_date"] >= pd.Timestamp("2008-01-01"))]
    tickers = sorted(spans["ticker"].unique())

    wiki = pd.read_csv(os.path.join(data_dir, "wiki_current_constituents.csv"))
    wiki_cik = dict(zip(wiki["Symbol"], wiki["CIK"]))
    sec_t = pd.read_csv(os.path.join(data_dir, "sec_company_tickers.csv"))
    sec_cik = dict(zip(sec_t["ticker"].str.replace("-", ".", regex=False), sec_t["cik_str"]))
    ch = pd.read_csv(os.path.join(data_dir, "wiki_changes.csv"))

    names: Dict[str, str] = {}
    for t, n in list(zip(ch["removed_ticker"], ch["removed_name"])) + list(zip(ch["added_ticker"], ch["added_name"])):
        if isinstance(t, str) and isinstance(n, str):
            names.setdefault(t, n)

    ylog = os.path.join(ssm_dir, "logs", "fetch_sectors.log")
    if os.path.exists(ylog):
        with open(ylog, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                m = re.match(r"\[\d+/\d+\] (\S+) .*\| (.+)$", line.strip())
                if m and m.group(2) != "None":
                    names.setdefault(m.group(1).replace("-", "."), m.group(2))
    for t, n in zip(wiki["Symbol"], wiki["Security"]):
        names.setdefault(t, n)
    for t, n in DOCUMENTED_NAME_HINTS.items():
        names[t] = n

    fil = sub.groupby("cik").agg(first=("filed", "min"), last=("filed", "max"), name=("name", "last"))
    allnames = sub[["cik", "name"]].drop_duplicates()
    allnames["n"] = allnames["name"].map(_norm_company_name)
    by_norm = allnames.groupby("n")["cik"].apply(set).to_dict()
    norm_keys = list(by_norm)
    ref_today = pd.Timestamp("2026-10-30")

    def active(c: int, s: pd.Timestamp, e: pd.Timestamp) -> bool:
        if c not in fil.index:
            return False
        r = fil.loc[c]
        e_eff = e if pd.notna(e) else ref_today
        return r["first"] <= e_eff + pd.Timedelta(days=120) and r["last"] >= max(s, pd.Timestamp("2009-06-01")) - pd.Timedelta(days=30)

    def overlap_days(c: int, s: pd.Timestamp, e: pd.Timestamp) -> int:
        if c not in fil.index:
            return -1
        r = fil.loc[c]
        e_eff = e if pd.notna(e) else ref_today
        lo = max(r["first"], s, pd.Timestamp("2009-04-01"))
        hi = min(r["last"], e_eff + pd.Timedelta(days=120))
        return int((hi - lo).days)

    def best_cand(cands, s: pd.Timestamp, e: pd.Timestamp) -> Optional[int]:
        valid_c = [c for c in cands if active(c, s, e)]
        return max(valid_c, key=lambda c: overlap_days(c, s, e)) if valid_c else None

    rows = []
    for t in tickers:
        sp_t = spans[spans["ticker"] == t]
        s = sp_t["start_date"].min()
        e = sp_t["end_date"].max() if sp_t["end_date"].notna().all() else pd.NaT
        c_val, how = None, None
        if t in NO_SEC_FILINGS_TICKERS:
            rows.append({"ticker": t, "cik": None, "method": "no_sec_filings"})
            continue
        if t in DOCUMENTED_MANUAL_CIKS:
            c_val, how = DOCUMENTED_MANUAL_CIKS[t], "manual_verified"
        if c_val is None and t in wiki_cik and pd.notna(wiki_cik[t]) and int(wiki_cik[t]) in fil.index:
            c_val, how = int(wiki_cik[t]), "wikipedia_current"
        if c_val is None and t in names:
            nm = _norm_company_name(names[t])
            c = best_cand(by_norm.get(nm, set()), s, e)
            if c is not None:
                c_val, how = c, "name_exact"
            else:
                for k in difflib.get_close_matches(nm, norm_keys, n=5, cutoff=0.88):
                    c = best_cand(by_norm[k], s, e)
                    if c is not None:
                        c_val, how = c, "name_fuzzy"
                        break
        if c_val is None and t in sec_cik and active(int(sec_cik[t]), s, e):
            c = int(sec_cik[t])
            if t not in names or difflib.SequenceMatcher(None, _norm_company_name(names[t]), _norm_company_name(fil["name"].get(c, ""))).ratio() >= 0.6:
                c_val, how = c, "sec_ticker_validated"
        if c_val is None and t in names:
            hw = set(_norm_company_name(names[t]).split())
            if hw:
                cands = [c for k_, cs in by_norm.items() for c in cs if hw <= set(k_.split())]
                c = best_cand(set(cands), s, e)
                if c is not None:
                    c_val, how = c, "name_tokens"
        rows.append({"ticker": t, "cik": c_val, "method": how})

    cmap = pd.DataFrame(rows)
    aliases = store._read_aliases()
    tk2cik = dict(zip(cmap["ticker"], cmap["cik"]))
    for r in aliases.itertuples():
        old, new = str(r.old).replace("-", "."), str(r.price_symbol).replace("-", ".")
        if pd.isna(tk2cik.get(old)) and pd.notna(tk2cik.get(new)):
            idx = cmap.index[cmap["ticker"] == old]
            cmap.loc[idx, ["cik", "method"]] = [tk2cik[new], f"alias_of_{new}"]
    cmap["cik"] = cmap["cik"].astype("Int64")

    sec_raw = pd.read_csv(os.path.join(data_dir, "sectors.csv"))
    sec_raw = sec_raw[sec_raw["sector"] != "UNKNOWN"]
    secmap = dict(zip(sec_raw["ticker"].str.replace("-", ".", regex=False), zip(sec_raw["sector"], sec_raw["source"])))
    sic_last = sub.dropna(subset=["sic"]).groupby("cik")["sic"].last()
    cmap["sic"] = [sic_last.get(int(c)) if pd.notna(c) else None for c in cmap["cik"]]
    cmap["sic_sector"] = [_sic_to_sector(x) if x is not None and pd.notna(x) else None for x in cmap["sic"]]

    def pick_sec(t: str, c) -> Tuple[Optional[str], Optional[str]]:
        v = secmap.get(t)
        if v and v[1] == "wikipedia_gics":
            return v
        if pd.notna(c) and int(c) in sic_last.index and _sic_to_sector(sic_last.get(int(c))):
            return _sic_to_sector(sic_last.get(int(c))), "sic_approx"
        return v if v else (None, None)

    cmap["sector"], cmap["sector_source"] = zip(*[pick_sec(t, c) for t, c in zip(cmap["ticker"], cmap["cik"])])
    return sub, cmap, aliases


def cleanroom_untrusted_and_excluded_spells(
    data_dir: str,
    store: CleanRoomEquityStore,
) -> Dict[str, List[Tuple[pd.Timestamp, pd.Timestamp]]]:
    sp = pd.read_csv(os.path.join(data_dir, "sp500_ticker_start_end.csv"), parse_dates=["start_date", "end_date"])
    ap = os.path.join(data_dir, "membership_additions.csv")
    if os.path.exists(ap):
        add = pd.read_csv(ap, parse_dates=["start_date", "end_date"])[["ticker", "start_date", "end_date"]]
        sp = pd.concat([sp, add], ignore_index=True)
    sp["ticker"] = sp["ticker"].astype(str).map(_norm_sym)

    bad: Dict[str, List[Tuple[pd.Timestamp, pd.Timestamp]]] = {}
    for r in sp.itertuples():
        e = r.end_date if pd.notna(r.end_date) else pd.Timestamp("2100-01-01")
        if e < pd.Timestamp("2007-12-01"):
            continue
        if r.ticker in store.daily.columns:
            s_ = store.daily[r.ticker].dropna()
            first = s_.index[0] if not s_.empty else None
        else:
            first = None
        need = max(r.start_date, pd.Timestamp("2007-01-10")) + pd.Timedelta(days=10)
        if first is not None and first > need:
            bad.setdefault(r.ticker, []).append((r.start_date, e))

    rp = os.path.join(data_dir, "identity_resolutions.csv")
    if os.path.exists(rp):
        for r in pd.read_csv(rp).itertuples():
            tk = _norm_sym(r.ticker)
            d = pd.Timestamp(r.date)
            if r.action == "exclude_before":
                bad.setdefault(tk, []).append((pd.Timestamp("1900-01-01"), d - pd.Timedelta(days=1)))
            elif r.action == "exclude_spell":
                bad.setdefault(tk, []).append((d, pd.Timestamp(r.date_to)))
            elif r.action == "use_wiki_before":
                wp = next(
                    (x for x in [
                        os.path.join(data_dir, "raw_wiki_check", f"{tk}.json"),
                        os.path.join(data_dir, "raw_wiki", f"{tk}.json"),
                    ] if os.path.exists(x)),
                    None,
                )
                if wp is None:
                    bad.setdefault(tk, []).append((pd.Timestamp("1900-01-01"), d))
            elif r.action == "use_archive_before":
                if not os.path.exists(os.path.join(data_dir, "raw_archive", f"{tk}.json")):
                    bad.setdefault(tk, []).append((pd.Timestamp("1900-01-01"), d))
    return bad


def cleanroom_load_pit_membership(
    data_dir: str,
    month_ends: pd.DatetimeIndex,
    bad_spells: Dict[str, List[Tuple[pd.Timestamp, pd.Timestamp]]],
) -> Dict[pd.Timestamp, Set[str]]:
    h = pd.read_csv(os.path.join(data_dir, "sp500_hist_components.csv"), parse_dates=["date"]).sort_values("date")
    last_date = h["date"].max()
    ch = pd.read_csv(os.path.join(data_dir, "wiki_changes.csv"))
    ch["date"] = pd.to_datetime(ch["date"], errors="coerce")
    ch = ch[ch["date"] > last_date].sort_values("date")

    ap = os.path.join(data_dir, "membership_additions.csv")
    additions = pd.read_csv(ap, parse_dates=["start_date", "end_date"]) if os.path.exists(ap) else pd.DataFrame(columns=["ticker", "start_date", "end_date"])
    rp = os.path.join(data_dir, "membership_symbol_changes.csv")
    renames = pd.read_csv(rp) if os.path.exists(rp) else pd.DataFrame(columns=["old_ticker", "new_ticker", "effective_date"])

    out: Dict[pd.Timestamp, Set[str]] = {}
    for t in month_ends:
        row = h[h["date"] <= t]
        if row.empty:
            continue
        mem = {_norm_sym(x) for x in str(row["tickers"].iloc[-1]).split(",")}
        for c in ch[ch["date"] <= t].itertuples():
            if isinstance(c.removed_ticker, str):
                mem.discard(_norm_sym(c.removed_ticker))
            if isinstance(c.added_ticker, str):
                mem.add(_norm_sym(c.added_ticker))
        for r in additions.itertuples():
            if r.start_date <= t and (pd.isna(r.end_date) or t < r.end_date):
                mem.add(_norm_sym(r.ticker))
        for change in renames.sort_values("effective_date").itertuples():
            if pd.Timestamp(change.effective_date) <= t and change.old_ticker in mem:
                mem.remove(change.old_ticker)
                mem.add(change.new_ticker)
        out[t] = {x for x in mem if not any(a <= t <= b for a, b in bad_spells.get(x, []))}
    return out


def cleanroom_sector_asof(
    ticker: str,
    date: pd.Timestamp,
    sector: str,
    source: str,
    industry: Optional[str],
) -> str:
    d = pd.Timestamp(date)
    sec = sector
    ind = industry if isinstance(industry, str) else ""

    cs_pre2018_gics = {
        "Integrated Telecommunication Services": "Telecommunication Services",
        "Wireless Telecommunication Services": "Telecommunication Services",
        "Alternative Carriers": "Telecommunication Services",
        "Interactive Media & Services": "Information Technology",
        "Interactive Home Entertainment": "Information Technology",
        "Movies & Entertainment": "Consumer Discretionary",
        "Broadcasting": "Consumer Discretionary",
        "Cable & Satellite": "Consumer Discretionary",
        "Publishing": "Consumer Discretionary",
        "Advertising": "Consumer Discretionary",
    }
    cs_pre2018_yahoo = {
        "Telecom Services": "Telecommunication Services",
        "Internet Content & Information": "Information Technology",
        "Electronic Gaming & Multimedia": "Information Technology",
        "Entertainment": "Consumer Discretionary",
        "Broadcasting": "Consumer Discretionary",
        "Publishing": "Consumer Discretionary",
        "Advertising Agencies": "Consumer Discretionary",
    }

    if d < pd.Timestamp("2023-03-20"):
        if sec == "Financials" and (
            ind == "Transaction & Payment Processing Services"
            or (source == "yahoo" and ind == "Credit Services" and ticker in {"V", "MA"})
        ):
            sec = "Information Technology"
        elif sec == "Industrials" and ticker in {"ADP", "PAYX", "PAYC", "DAY", "CDAY", "BR"}:
            sec = "Information Technology"
        elif sec == "Consumer Staples" and ticker in {"DG", "DLTR", "TGT"}:
            sec = "Consumer Discretionary"

    if d < pd.Timestamp("2018-09-24"):
        if sec == "Communication Services":
            is_gics = "wikipedia_gics" in str(source) or str(source).startswith("manual")
            m = cs_pre2018_gics.get(ind) if is_gics else cs_pre2018_yahoo.get(ind)
            if m is None and ind.startswith("SIC "):
                code = ind[4:].split(".")[0]
                m = (
                    "Telecommunication Services" if (code.startswith("48") and code not in ("4833", "4841"))
                    else "Information Technology" if code.startswith("737")
                    else "Consumer Discretionary"
                )
            sec = m if m else "Consumer Discretionary"
        elif ticker == "EBAY" and sec == "Consumer Discretionary":
            sec = "Information Technology"

    if d < pd.Timestamp("2016-09-01") and sec == "Real Estate":
        sec = "Financials"
    return sec


def cleanroom_build_pit_sector_panel(
    data_dir: str,
    store: CleanRoomEquityStore,
    aliases: pd.DataFrame,
    cmap: pd.DataFrame,
    month_ends: pd.DatetimeIndex,
) -> pd.DataFrame:
    raw = pd.read_csv(os.path.join(data_dir, "sectors.csv"))
    wiki = raw[raw["source"] == "wikipedia_gics"].set_index("ticker")
    yahoo = raw[raw["source"] == "yahoo"].set_index("ticker")
    sic_map = {
        _norm_sym(t): (sec, ind)
        for t, sec, ind in zip(cmap["ticker"], cmap["sic_sector"], cmap["sic"])
        if isinstance(sec, str)
    }
    succ = {_norm_sym(r.old): _norm_sym(r.price_symbol) for r in aliases.itertuples()}
    alias_olds = set(succ.keys())

    def is_direct_yahoo_only(tk: str) -> bool:
        if tk in alias_olds or tk in DOCUMENTED_TIME_SPLITS:
            return False
        prov = store.provenance.get(tk, [])
        return len(prov) == 1 and prov[0][0] == "yahoo" and prov[0][1] == tk and prov[0][2] is None and prov[0][3] is None

    def base_row(t: str, depth: int = 0) -> Optional[Tuple[str, str, Optional[str]]]:
        if t in wiki.index:
            return wiki.at[t, "sector"], "wikipedia_gics", wiki.at[t, "industry"]
        if t in succ and depth < 5:
            r = base_row(succ[t], depth + 1)
            if r:
                return r[0], f"alias:{succ[t]}:{r[1]}", r[2]
        if (
            t in yahoo.index
            and is_direct_yahoo_only(t)
            and isinstance(yahoo.at[t, "sector"], str)
            and yahoo.at[t, "sector"] != "UNKNOWN"
        ):
            return yahoo.at[t, "sector"], "yahoo", yahoo.at[t, "industry"]
        if t in sic_map:
            return sic_map[t][0], "sic", f"SIC {sic_map[t][1]}"
        return None

    tickers = sorted(set(raw["ticker"]) | set(sic_map) | set(succ))
    rows = []
    for t in tickers:
        r = base_row(t)
        if r:
            rows.append({"ticker": t, "sector": r[0], "source": r[1], "industry": r[2]})
    sec_df = pd.DataFrame(rows)

    ov_p = os.path.join(data_dir, "sector_overrides.csv")
    if os.path.exists(ov_p):
        ov = pd.read_csv(ov_p)
        sec_df = sec_df[~sec_df["ticker"].isin(ov["ticker"])]
        keep_cols = ["ticker", "sector", "source", "industry"] + [c for c in ["valid_from", "valid_to"] if c in ov.columns]
        sec_df = pd.concat([sec_df, ov.assign(source="manual:" + ov["source"])[keep_cols]], ignore_index=True)

    sec_panel: Dict[str, List[Optional[str]]] = {}
    has_dates = "valid_from" in sec_df.columns
    for tk, g in sec_df.groupby("ticker", sort=True):
        g = g[g["sector"].apply(lambda x: isinstance(x, str) and x != "UNKNOWN")]
        if g.empty:
            continue
        col_s: List[Optional[str]] = [None] * len(month_ends)
        undated = g[g["valid_from"].isna() & g["valid_to"].isna()] if has_dates else g
        dated = g[~g.index.isin(undated.index)]
        if len(undated):
            r0 = undated.iloc[0]
            for i, dt in enumerate(month_ends):
                col_s[i] = cleanroom_sector_asof(tk, dt, r0["sector"], r0["source"], r0.get("industry"))
        for _, rd in dated.iterrows():
            a = pd.Timestamp(rd["valid_from"]) if pd.notna(rd["valid_from"]) else pd.Timestamp("1900-01-01")
            b = pd.Timestamp(rd["valid_to"]) if pd.notna(rd["valid_to"]) else pd.Timestamp("2100-01-01")
            for i, dt in enumerate(month_ends):
                if a <= dt < b:
                    col_s[i] = rd["sector"]
        sec_panel[tk] = col_s
    return pd.DataFrame(sec_panel, index=month_ends)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Clean-Room PIT SEC XBRL Fundamentals Builder (`filed + 1d <= t`)
# ─────────────────────────────────────────────────────────────────────────────
def cleanroom_split_factor_after(
    data_dir: str,
    ticker: str,
    filing_dt: pd.Timestamp,
    cache: Dict[str, List[Tuple[pd.Timestamp, float]]],
) -> float:
    tk = _norm_sym(ticker)
    if tk not in cache:
        p = os.path.join(data_dir, "raw", f"{tk}.json")
        pt = os.path.join(data_dir, "raw_tiingo", f"{tk}.json")
        if os.path.exists(pt):
            with open(pt, "r", encoding="utf-8") as fh:
                if json.load(fh).get("covers_membership"):
                    p = pt
        for sub in ("raw_wiki", "raw_ndx", "raw_smallcap"):
            alt = os.path.join(data_dir, sub, f"{tk}.json")
            if not os.path.exists(p) and os.path.exists(alt):
                p = alt
        if not os.path.exists(p):
            cache[tk] = []
        else:
            with open(p, "r", encoding="utf-8") as fh:
                jd = json.load(fh)
            cache[tk] = [
                (pd.Timestamp(a), float(num or 1.0) / float(den or 1.0))
                for a, num, den in (jd.get("splits") or [])
            ]
    fac = 1.0
    fdt = pd.Timestamp(filing_dt)
    for dt, r in cache[tk]:
        if dt > fdt:
            fac *= r
    return fac


def cleanroom_build_pit_fundamentals(
    ssm_dir: str,
    sub: pd.DataFrame,
    cmap: pd.DataFrame,
    form_dates: pd.DatetimeIndex,
) -> pd.DataFrame:
    """
    Directly parses raw SEC FSDS `num_*.parquet` files into quarterly & TTM PIT fundamental growth
    and margin improvement features as-of each formation date `t`:
      - `eps_gs_q`    : Quarterly YoY diluted EPS symmetric growth
      - `eps_g_sym`   : TTM YoY diluted EPS symmetric growth
      - `opinc_gs_q`  : Quarterly YoY Operating Income (or Net Income fallback) symmetric growth
      - `rev_g_q`     : Quarterly YoY Revenue growth
      - `rev_accel`   : Quarterly YoY Revenue acceleration (`rev_g_q - rev_g_{q-1}`)
      - `rev_g_ttm`   : TTM YoY Revenue growth
      - `opm_chg`     : Quarterly YoY Operating Margin change (`OpInc_q/Rev_q - OpInc_{q-4}/Rev_{q-4}`)
      - `gm_chg`      : Quarterly YoY Gross Margin change (`GP_q/Rev_q - GP_{q-4}/Rev_{q-4}`)
      - `nm_chg`      : Quarterly YoY Net Margin change (`NI_q/Rev_q - NI_{q-4}/Rev_{q-4}`, TTM fallback)
    Strict PIT gating: every derived metric is public only after `max(all constituent filing dates) + 1 day <= t`
    and `t - period_end <= 200 days`.
    """
    data_dir = os.path.join(ssm_dir, "data")
    sec_raw_dir = os.path.join(data_dir, "fundamentals", "sec_raw")

    good = cmap.dropna(subset=["cik", "sector"]).copy()
    good["cik"] = good["cik"].astype("int64")
    good["_prio"] = (good["method"] != "wikipedia_current").astype(int)
    cik2 = good.sort_values(["_prio", "ticker"]).drop_duplicates("cik").set_index("cik")[["ticker", "sector"]]

    s_sub = sub[sub["cik"].isin(cik2.index)][["adsh", "cik", "form", "fy", "fp", "filed", "accepted"]].copy()
    valid_adsh = set(s_sub["adsh"])

    parts = []
    for p in sorted(glob.glob(os.path.join(sec_raw_dir, "num_*.parquet"))):
        n = pd.read_parquet(p)
        n = n[n["adsh"].isin(valid_adsh) & n["tag"].isin(ALL_NEEDED_XBRL_TAGS)]
        if not n.empty:
            parts.append(n.merge(s_sub, on="adsh", how="inner"))
    df = pd.concat(parts, ignore_index=True)
    df = df.join(cik2, on="cik")
    df["ddate"] = pd.to_datetime(df["ddate"], format="%Y%m%d", errors="coerce")
    df = df[df["ddate"] <= df["filed"] + pd.Timedelta(days=16)]
    df = df.sort_values(["cik", "tag", "ddate", "qtrs", "uom", "filed", "accepted"])
    key = ["cik", "tag", "ddate", "qtrs", "uom"]
    df["is_first_report"] = ~df.duplicated(key, keep="first")
    fr_all = df[df["is_first_report"]].copy()

    want = {
        "eps_diluted": ["EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted"],
        "eps_basic": ["EarningsPerShareBasic", "EarningsPerShareBasicAndDiluted"],
        "net_income": ["NetIncomeLoss", "ProfitLoss"],
        "op_income": ["OperatingIncomeLoss"],
        "gross_profit": ["GrossProfit"],
        "cost_of_rev": ["CostOfRevenue", "CostOfGoodsAndServicesSold"],
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

    fr_q = fr_all[fr_all["qtrs"].isin([1, 3, 4]) & (fr_all["uom"] == "USD")]
    out_parts = []
    for field, tags in want.items():
        sub_f = fr_q[fr_q["tag"].isin(tags)].copy()
        amb = sub_f.groupby(["cik", "tag", "ddate", "qtrs"])["value"].nunique()
        amb_idx = amb[amb > 1].index
        if len(amb_idx):
            sub_f = sub_f[~sub_f.set_index(["cik", "tag", "ddate", "qtrs"]).index.isin(amb_idx)]
        sub_f["prio"] = sub_f["tag"].map({t: i for i, t in enumerate(tags)})
        sub_f = sub_f.sort_values(["cik", "ddate", "qtrs", "filed", "prio"]).drop_duplicates(["cik", "ddate", "qtrs"])
        q1 = sub_f[sub_f["qtrs"] == 1][["cik", "ddate", "value", "filed", "fy", "fp", "form"]].assign(field=field, derived=False)

        fy = sub_f[sub_f["qtrs"] == 4][["cik", "ddate", "value", "filed", "fy", "fp", "form"]].copy()
        ytd = sub_f[sub_f["qtrs"] == 3][["cik", "ddate", "value", "filed"]].rename(columns={"ddate": "d9", "value": "v9", "filed": "f9"})
        fy["lo"] = fy["ddate"] - pd.Timedelta(days=105)
        fy["hi"] = fy["ddate"] - pd.Timedelta(days=75)
        mg = fy.merge(ytd, on="cik")
        mg = mg[(mg["d9"] >= mg["lo"]) & (mg["d9"] <= mg["hi"])].drop_duplicates(["cik", "ddate"])
        mg["filed"] = mg[["filed", "f9"]].max(axis=1)
        mg["value"] = mg["value"] - mg["v9"]
        q4 = mg[["cik", "ddate", "value", "filed", "fy", "fp", "form"]].assign(field=field, derived=True)
        have = set(zip(q1["cik"], q1["ddate"]))
        q4 = q4[[(c, d) not in have for c, d in zip(q4["cik"], q4["ddate"])]]
        out_parts.append(pd.concat([q1, q4], ignore_index=True))

    x = pd.concat(out_parts, ignore_index=True)
    piv = x.pivot_table(index=["cik", "ddate"], columns="field", values="value", aggfunc="first")
    fpiv = x.pivot_table(index=["cik", "ddate"], columns="field", values="filed", aggfunc="first")
    fpiv.columns = ["filed_" + c for c in fpiv.columns]
    p = piv.join(fpiv).reset_index().sort_values(["cik", "ddate"]).rename(columns={"ddate": "period_end"})
    p = p.join(cik2, on="cik")
    p = p[p["cik"].notna()].copy()
    p["cik"] = p["cik"].astype("int64")

    # Fill Gross Profit from `revenue - cost_of_rev` when `GrossProfit` is not directly tagged
    if "gross_profit" in p.columns and "cost_of_rev" in p.columns and "revenue" in p.columns:
        fb_gp = p["revenue"] - p["cost_of_rev"]
        f_fb = pd.concat([p["filed_revenue"], p["filed_cost_of_rev"]], axis=1).max(axis=1, skipna=False)
        need_fb = p["gross_profit"].isna() & fb_gp.notna() & f_fb.notna()
        p.loc[need_fb, "gross_profit"] = fb_gp[need_fb]
        p.loc[need_fb, "filed_gross_profit"] = f_fb[need_fb]

    # Split-adjust quarterly EPS for any stock splits occurring after the SEC filing date
    split_cache: Dict[str, List[Tuple[pd.Timestamp, float]]] = {}
    p["eps_raw"] = p["eps_diluted"].fillna(p.get("eps_basic"))
    p["filed_eps"] = p["filed_eps_diluted"].fillna(p.get("filed_eps_basic"))
    fac = [
        cleanroom_split_factor_after(data_dir, t, f, split_cache) if isinstance(t, str) and pd.notna(f) else np.nan
        for t, f in zip(p["ticker"], p["filed_eps"])
    ]
    p["eps_adj"] = p["eps_raw"] / np.array(fac, dtype=float)

    # TTM rolling sums (requiring 4 quarters spanning 250..290 days between q-3 and q)
    g = p.groupby("cik")
    span = (p["period_end"] - g["period_end"].shift(3)).dt.days
    for f, fcol in [
        ("eps_adj", "filed_eps"),
        ("net_income", "filed_net_income"),
        ("revenue", "filed_revenue"),
    ]:
        if f in p.columns and fcol in p.columns:
            roll = g[f].rolling(4, min_periods=4).sum().reset_index(level=0, drop=True)
            p[f + "_ttm"] = roll.where(span.between(250, 290))
            fn = p[fcol].astype("int64").where(p[fcol].notna())
            known = fn.groupby(p["cik"]).transform(lambda s_: s_.rolling(4, min_periods=4).max())
            p["av_" + f + "_ttm"] = pd.to_datetime(known.where(p[f + "_ttm"].notna())) + pd.Timedelta(days=1)

    # Quarterly Margins & Operating/Net Profit
    rev_pos = p["revenue"].where(p["revenue"] > 0)
    p["op_inc_eff"] = p["op_income"].fillna(p["net_income"])
    p["filed_op_eff"] = p["filed_op_income"].where(p["op_income"].notna(), p["filed_net_income"])
    p["opm"] = p["op_inc_eff"] / rev_pos
    p["gm"] = p["gross_profit"] / rev_pos
    p["nm"] = p["net_income"] / rev_pos
    p["nm_ttm"] = p["net_income_ttm"] / p["revenue_ttm"].where(p["revenue_ttm"] > 0)

    # Match with year-ago quarter (`period_end + 365 days`, tolerance 20 days)
    prior_cols = [
        "eps_adj", "filed_eps",
        "op_inc_eff", "filed_op_eff",
        "revenue", "filed_revenue",
        "opm", "filed_op_income",
        "gm", "filed_gross_profit",
        "nm", "filed_net_income",
        "eps_adj_ttm", "av_eps_adj_ttm",
        "revenue_ttm", "av_revenue_ttm",
        "nm_ttm", "av_net_income_ttm",
    ]
    prior = p[["cik", "period_end"] + prior_cols].copy()
    prior["period_end"] = prior["period_end"] + pd.Timedelta(days=365)
    prior.columns = ["cik", "period_end"] + [c + "_py" for c in prior_cols]

    p = pd.merge_asof(
        p.sort_values("period_end"),
        prior.sort_values("period_end"),
        on="period_end",
        by="cik",
        tolerance=pd.Timedelta(days=20),
        direction="nearest",
    ).sort_values(["cik", "period_end"])

    # Compute YoY Growth & Margin Changes
    den_eps_q = (p["eps_adj"].abs() + p["eps_adj_py"].abs()) / 2.0
    p["eps_gs_q"] = np.where(den_eps_q > 0, (p["eps_adj"] - p["eps_adj_py"]) / den_eps_q, np.nan)

    den_eps_ttm = (p["eps_adj_ttm"].abs() + p["eps_adj_ttm_py"].abs()) / 2.0
    p["eps_g_sym"] = np.where(den_eps_ttm > 0, (p["eps_adj_ttm"] - p["eps_adj_ttm_py"]) / den_eps_ttm, np.nan)

    den_op_q = (p["op_inc_eff"].abs() + p["op_inc_eff_py"].abs()) / 2.0
    p["opinc_gs_q"] = np.where(den_op_q > 0, (p["op_inc_eff"] - p["op_inc_eff_py"]) / den_op_q, np.nan)

    p["rev_g_q"] = np.where(p["revenue_py"] > 0, p["revenue"] / p["revenue_py"] - 1.0, np.nan)
    p["rev_g_ttm"] = np.where(p["revenue_ttm_py"] > 0, p["revenue_ttm"] / p["revenue_ttm_py"] - 1.0, np.nan)

    p["opm_chg"] = p["opm"] - p["opm_py"]
    p["gm_chg"] = p["gm"] - p["gm_py"]
    p["nm_chg"] = (p["nm"] - p["nm_py"]).fillna(p["nm_ttm"] - p["nm_ttm_py"])

    # Quarterly accelerations (`q - q_{t-1}`)
    g = p.groupby("cik")
    q_span = (p["period_end"] - g["period_end"].shift(1)).dt.days
    is_consec_q = q_span.between(70, 115)
    p["rev_accel"] = (p["rev_g_q"] - g["rev_g_q"].shift(1)).where(is_consec_q)
    p["eps_accel"] = (p["eps_gs_q"] - g["eps_gs_q"].shift(1)).where(is_consec_q)

    # Exact PIT availability dates (`max(all constituent filings) + 1 day`)
    one = pd.Timedelta(days=1)
    mx = lambda *cols: pd.concat(list(cols), axis=1).max(axis=1, skipna=False)
    p["f_eps_q"] = mx(p["filed_eps"], p["filed_eps_py"])
    p["f_op_q"] = mx(p["filed_op_eff"], p["filed_op_eff_py"])
    p["f_rev_q"] = mx(p["filed_revenue"], p["filed_revenue_py"])
    g = p.groupby("cik")

    p["av_eps_gs_q"] = p["f_eps_q"] + one
    p["av_eps_accel"] = mx(p["f_eps_q"], g["f_eps_q"].shift(1)) + one
    p["av_eps_g_sym"] = mx(p["av_eps_adj_ttm"], p["av_eps_adj_ttm_py"])
    p["av_opinc_gs_q"] = p["f_op_q"] + one
    p["av_rev_g_q"] = p["f_rev_q"] + one
    p["av_rev_accel"] = mx(p["f_rev_q"], g["f_rev_q"].shift(1)) + one
    p["av_rev_g_ttm"] = mx(p["av_revenue_ttm"], p["av_revenue_ttm_py"])
    p["av_opm_chg"] = mx(p["filed_op_eff"], p["filed_revenue"], p["filed_op_eff_py"], p["filed_revenue_py"]) + one
    p["av_gm_chg"] = mx(p["filed_gross_profit"], p["filed_revenue"], p["filed_gross_profit_py"], p["filed_revenue_py"]) + one
    av_nm_q = mx(p["filed_net_income"], p["filed_revenue"], p["filed_net_income_py"], p["filed_revenue_py"]) + one
    av_nm_ttm = mx(p["av_net_income_ttm"], p["av_revenue_ttm"], p["av_net_income_ttm_py"], p["av_revenue_ttm_py"])
    p["av_nm_chg"] = av_nm_q.fillna(av_nm_ttm)

    # As-of merge onto `(cik, t)` grid with monotonic fiscal period filter and 200-day freshness rule
    p = p[p["cik"].notna()].copy()
    p["cik"] = p["cik"].astype("int64")
    grid = pd.DataFrame([(int(c), t) for c in sorted(p["cik"].unique()) for t in form_dates], columns=["cik", "t"]).sort_values("t")
    grid["cik"] = grid["cik"].astype("int64")
    out = grid.copy()

    metric_av_pairs = [
        ("eps_gs_q", "av_eps_gs_q"),
        ("eps_accel", "av_eps_accel"),
        ("eps_g_sym", "av_eps_g_sym"),
        ("opinc_gs_q", "av_opinc_gs_q"),
        ("rev_g_q", "av_rev_g_q"),
        ("rev_accel", "av_rev_accel"),
        ("rev_g_ttm", "av_rev_g_ttm"),
        ("opm_chg", "av_opm_chg"),
        ("gm_chg", "av_gm_chg"),
        ("nm_chg", "av_nm_chg"),
    ]
    for col, av_col in metric_av_pairs:
        x_m = p.dropna(subset=[av_col, col])[["cik", av_col, "period_end", col]].copy()
        x_m["cik"] = x_m["cik"].astype("int64")
        x_m[av_col] = pd.to_datetime(x_m[av_col])
        x_m = x_m.sort_values([av_col, "period_end"], kind="mergesort")
        latest_pe = x_m.groupby("cik")["period_end"].cummax()
        x_m = x_m[x_m["period_end"] >= latest_pe]
        m = pd.merge_asof(grid, x_m, left_on="t", right_on=av_col, by="cik", direction="backward")
        stale = (m["t"] - m["period_end"]).dt.days > 200
        out[col] = m[col].where(~stale).values

    return out


# ─────────────────────────────────────────────────────────────────────────────
# 3. Clean-Room Residual Momentum (`12-1`) & 52-Week-High Proximity Builder
# ─────────────────────────────────────────────────────────────────────────────
def compute_residual_momentum_and_52wh_panel(
    store: CleanRoomEquityStore,
    members: Dict[pd.Timestamp, Set[str]],
    sec_panel: pd.DataFrame,
    cmap: pd.DataFrame,
    fund_grid: pd.DataFrame,
    ssm_dir: str,
    form_dates: pd.DatetimeIndex,
) -> pd.DataFrame:
    """
    Constructs the full monthly eligible stock panel (`2009-12-31 .. 2026-08-31`) with:
      1. `mom_12_1`, `mom_6_1`, `mom_3_1`
      2. `high52_prox` (`Close[t] / Max_252(Close[t])`) and `high52_prox_lag1` (`Close[t-1] / Max_252(Close[t-1])`)
      3. `res_mom_sec_ir`, `res_mom_sec_cum`, `res_mom_mkt_ir`:
         Daily OLS regression over `[t-12, t-1]` (`d_pos - 252 : d_pos - 21`, ~231 trading days)
         of stock return `r_{i,d}` on `SPY` and its GICS Sector ETF (`XLK`, `XLV`, etc.):
           - Strips out `beta_SPY * r_SPY + beta_Sec * r_Sec`
           - Computes `res_mom_sec_ir = mean(u_d) / std(eps_d) * sqrt(252)` (Information Ratio of residual momentum)
           - Computes `res_mom_sec_cum = prod(1 + u_d) - 1` (Cumulative market+sector-stripped return)
           - Computes `res_mom_mkt_ir` (vs `SPY` only)
      4. PIT SEC XBRL Fundamental Momentum columns (`eps_gs_q`, `eps_g_sym`, `opinc_gs_q`, `rev_g_q`, `rev_accel`, `opm_chg`, `gm_chg`, `nm_chg`)
    """
    data_dir = os.path.join(ssm_dir, "data")
    P = store.P
    seg_m = store.seg_m
    daily = store.daily
    seg_d = store.seg_d.reindex(index=daily.index, columns=daily.columns)
    r_d = daily.pct_change(fill_method=None).where(seg_d == seg_d.shift(1))

    mom_12_1 = (P.shift(1) / P.shift(12) - 1.0).where((seg_m == seg_m.shift(12)) & (seg_m == seg_m.shift(1)))
    mom_6_1 = (P.shift(1) / P.shift(6) - 1.0).where((seg_m == seg_m.shift(6)) & (seg_m == seg_m.shift(1)))
    mom_3_1 = (P.shift(1) / P.shift(3) - 1.0).where((seg_m == seg_m.shift(3)) & (seg_m == seg_m.shift(1)))

    # 52-week-high proximity (George & Hwang 2004): Close / 252-day Rolling Max Close
    hi252 = daily.rolling(252, min_periods=200).max()
    ok252 = seg_d == seg_d.shift(251)
    prox_d = (daily / hi252).where(ok252)

    # CIK validity map
    val_map: Dict[str, Tuple[pd.Timestamp, pd.Timestamp]] = {}
    cv_path = os.path.join(data_dir, "cik_validity.csv")
    if os.path.exists(cv_path):
        vdf = pd.read_csv(cv_path, parse_dates=["valid_from", "valid_to"])
        val_map = {r.ticker: (r.valid_from, r.valid_to) for r in vdf.itertuples()}

    def is_cik_valid(tk: str, dt: pd.Timestamp) -> bool:
        w = val_map.get(tk)
        if w is None:
            return True
        a, b = w
        return (pd.isna(a) or dt >= a) and (pd.isna(b) or dt < b)

    t2c = {_norm_sym(t): int(c) for t, c in zip(cmap["ticker"], cmap["cik"]) if pd.notna(c)}
    fund_idx = fund_grid.set_index(["t", "cik"])
    fund_cols = ["eps_gs_q", "eps_accel", "eps_g_sym", "opinc_gs_q", "rev_g_q", "rev_accel", "rev_g_ttm", "opm_chg", "gm_chg", "nm_chg"]

    d_idx = daily.index
    rows = []

    for t in form_dates:
        if t not in P.index or t not in members:
            continue
        el = [
            tk for tk in sorted(members[t])
            if tk in P.columns
            and pd.notna(P.at[t, tk])
            and tk in sec_panel.columns
            and isinstance(sec_panel.at[t, tk], str)
            and pd.notna(mom_12_1.at[t, tk])
        ]
        if not el:
            continue

        # Locate daily indices for formation `t`, `t-1` month-end (~21 sessions back), and `t-12` month-end (~252 sessions back)
        pos_t = int(d_idx.searchsorted(t, side="right") - 1)
        t_m1 = P.index[P.index.get_loc(t) - 1]
        t_m12 = P.index[P.index.get_loc(t) - 12]
        pos_m1 = int(d_idx.searchsorted(t_m1, side="right") - 1)
        pos_m12 = int(d_idx.searchsorted(t_m12, side="right") - 1)

        # Daily slice for `[t-12, t-1]` (`pos_m12 + 1 .. pos_m1`)
        win_slice = slice(pos_m12 + 1, pos_m1 + 1)
        r_win = r_d.iloc[win_slice]
        spy_win = r_win["SPY"].values if "SPY" in r_win.columns else None

        # Precompute OLS projection matrices for (1) SPY only, and (2) SPY + each Sector ETF
        mkt_beta_solver = None
        sec_beta_solvers: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}
        if spy_win is not None and np.isfinite(spy_win).all() and len(spy_win) >= 180:
            X_mkt = np.column_stack([np.ones(len(spy_win)), spy_win])
            # pinv for fast OLS: coeff = pinv(X) @ y -> [alpha, beta_mkt]
            mkt_pinv = np.linalg.pinv(X_mkt)
            mkt_beta_solver = (X_mkt, mkt_pinv)

            for sec_name, etf_tk in SECTOR_ETF_MAP.items():
                if etf_tk in r_win.columns:
                    etf_v = r_win[etf_tk].values
                    if np.isfinite(etf_v).all():
                        # Orthogonalize or include Sector ETF return alongside SPY
                        X_sec = np.column_stack([np.ones(len(spy_win)), spy_win, etf_v])
                        sec_beta_solvers[sec_name] = (X_sec, np.linalg.pinv(X_sec))

        for tk in el:
            sec = str(sec_panel.at[t, tk])
            rv_cc, st_cc = store.close_return(t, tk, lag_days=0)
            rv_oo, st_oo = store.open_return(t, tk)

            # 52-week-high proximity at `t` and at `t-1`
            h52_t = float(prox_d.iloc[pos_t][tk]) if (tk in prox_d.columns and pd.notna(prox_d.iloc[pos_t][tk])) else float("nan")
            h52_m1 = float(prox_d.iloc[pos_m1][tk]) if (tk in prox_d.columns and pd.notna(prox_d.iloc[pos_m1][tk])) else float("nan")

            # Residual Momentum (`12-1`) over `[pos_m12 + 1 .. pos_m1]`
            res_mkt_ir = float("nan")
            res_sec_ir = float("nan")
            res_sec_cum = float("nan")

            if tk in r_win.columns and seg_d.iloc[pos_m12][tk] == seg_d.iloc[pos_m1][tk]:
                y = r_win[tk].values
                valid_y = np.isfinite(y)
                if valid_y.all() and mkt_beta_solver is not None:
                    X_m, pinv_m = mkt_beta_solver
                    coef_m = pinv_m @ y
                    eps_m = y - X_m @ coef_m
                    u_m = coef_m[0] + eps_m  # Market-stripped daily return: r_i - beta_SPY * r_SPY
                    sd_m = float(np.std(eps_m, ddof=2))
                    if sd_m > 1e-8:
                        res_mkt_ir = float(np.mean(u_m) / sd_m * math.sqrt(252.0))

                    if sec in sec_beta_solvers:
                        X_s, pinv_s = sec_beta_solvers[sec]
                        coef_s = pinv_s @ y
                        eps_s = y - X_s @ coef_s
                        u_s = coef_s[0] + eps_s  # Market + Sector stripped daily return
                        sd_s = float(np.std(eps_s, ddof=3))
                        if sd_s > 1e-8:
                            res_sec_ir = float(np.mean(u_s) / sd_s * math.sqrt(252.0))
                        res_sec_cum = float(np.prod(1.0 + np.clip(u_s, -0.95, 5.0)) - 1.0)
                    else:
                        res_sec_ir = res_mkt_ir
                        res_sec_cum = float(np.prod(1.0 + np.clip(u_m, -0.95, 5.0)) - 1.0)

            rec = {
                "t": t,
                "ticker": tk,
                "sector": sec,
                "mom_12_1": float(mom_12_1.at[t, tk]),
                "mom_6_1": float(mom_6_1.at[t, tk]) if pd.notna(mom_6_1.at[t, tk]) else float("nan"),
                "mom_3_1": float(mom_3_1.at[t, tk]) if pd.notna(mom_3_1.at[t, tk]) else float("nan"),
                "high52_prox": h52_t,
                "high52_prox_lag1": h52_m1,
                "res_mom_sec_ir": res_sec_ir,
                "res_mom_sec_cum": res_sec_cum,
                "res_mom_mkt_ir": res_mkt_ir,
                "ret_cc": float(rv_cc) if rv_cc is not None else float("nan"),
                "status_cc": st_cc,
                "ret_oo": float(rv_oo) if rv_oo is not None else float("nan"),
                "status_oo": st_oo,
            }

            c = t2c.get(tk)
            if c is not None and not is_cik_valid(tk, t):
                c = None
            rec["cik"] = c if c is not None else np.nan
            if c is not None and (t, c) in fund_idx.index:
                frow = fund_idx.loc[(t, c)]
                for fc in fund_cols:
                    rec[fc] = float(frow[fc]) if pd.notna(frow[fc]) else float("nan")
            else:
                for fc in fund_cols:
                    rec[fc] = float("nan")

            rows.append(rec)

    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Pre-Frozen Percentile Rank & Multi-Layer Composite Scoring Engine
# ─────────────────────────────────────────────────────────────────────────────
def _pct_rank_within_group(s: pd.Series, fill_neutral: float = 0.5) -> pd.Series:
    """
    Computes cross-sectional percentile rank in `[0, 1]` (higher value -> closer to 1.0)
    within the candidate pool `s`. Missing values receive neutral rank `fill_neutral = 0.5`.
    """
    valid = s.dropna()
    n = len(valid)
    if n == 0:
        return pd.Series(fill_neutral, index=s.index, dtype=float)
    if n == 1:
        out = pd.Series(fill_neutral, index=s.index, dtype=float)
        out.loc[valid.index] = 1.0
        return out
    ranks = (valid.rank(ascending=True, method="average") - 1.0) / (n - 1.0)
    return ranks.reindex(s.index).fillna(fill_neutral)


def _mean_available_ranks(rank_series_list: List[pd.Series], raw_series_list: List[pd.Series], fill_neutral: float = 0.5) -> pd.Series:
    """
    Takes the equal-weight mean of percentile ranks across all non-missing metrics in a family.
    If all metrics in the family are missing for a stock, returns `fill_neutral = 0.5`.
    """
    idx = rank_series_list[0].index
    num = pd.Series(0.0, index=idx, dtype=float)
    den = pd.Series(0.0, index=idx, dtype=float)
    for r_s, raw_s in zip(rank_series_list, raw_series_list):
        mask = raw_s.notna()
        num = num + r_s.where(mask, 0.0)
        den = den + mask.astype(float)
    return (num / den.where(den > 0)).fillna(fill_neutral)


def score_candidates_at_month(
    g_uni: pd.DataFrame,
    strategy_id: str,
    shortlist_n: Optional[int] = 20,
) -> pd.DataFrame:
    """
    Given all eligible stocks `g_uni` in the chosen universe at month-end `t`:
      1. If `shortlist_n` is an integer (e.g., `20`), first filters to the Top-`shortlist_n` stocks by `mom_12_1`
         (tie-broken deterministically by `ticker`).
      2. Within that candidate pool, computes pre-frozen percentile ranks `[0, 1]` for:
           - `r_price`  : `mom_12_1`
           - `r_profit` : equal-weight mean rank of `(eps_gs_q, eps_g_sym, opinc_gs_q)`
           - `r_rev`    : equal-weight mean rank of `(rev_g_q, rev_accel)`
           - `r_margin` : equal-weight mean rank of `(opm_chg, gm_chg, nm_chg)`
           - `r_fund`   : equal-weight mean of available `(r_profit, r_rev, r_margin)`
           - `r_res_sec`: `res_mom_sec_ir`
           - `r_res_cum`: `res_mom_sec_cum`
           - `r_res_mkt`: `res_mom_mkt_ir`
           - `r_52wh`   : `high52_prox`
           - `r_52wh_l1`: `high52_prox_lag1`
      3. Combines the pre-frozen equal-weight composite score for `strategy_id` and sorts descending
         (tie-broken by `mom_12_1` descending, then `ticker` ascending).
    """
    g = g_uni.sort_values(["mom_12_1", "ticker"], ascending=[False, True]).copy()
    if shortlist_n is not None and shortlist_n > 0:
        g = g.head(shortlist_n).copy()
    if g.empty:
        return g

    # Price rank
    r_price = _pct_rank_within_group(g["mom_12_1"])

    # Fundamental sub-family ranks within pool
    r_eps_q = _pct_rank_within_group(g["eps_gs_q"])
    r_eps_ttm = _pct_rank_within_group(g["eps_g_sym"])
    r_op_q = _pct_rank_within_group(g["opinc_gs_q"])
    r_profit = _mean_available_ranks([r_eps_q, r_eps_ttm, r_op_q], [g["eps_gs_q"], g["eps_g_sym"], g["opinc_gs_q"]])
    has_profit = g[["eps_gs_q", "eps_g_sym", "opinc_gs_q"]].notna().any(axis=1)

    r_rev_q = _pct_rank_within_group(g["rev_g_q"])
    r_rev_acc = _pct_rank_within_group(g["rev_accel"])
    r_rev = _mean_available_ranks([r_rev_q, r_rev_acc], [g["rev_g_q"], g["rev_accel"]])
    has_rev = g[["rev_g_q", "rev_accel"]].notna().any(axis=1)

    r_opm = _pct_rank_within_group(g["opm_chg"])
    r_gm = _pct_rank_within_group(g["gm_chg"])
    r_nm = _pct_rank_within_group(g["nm_chg"])
    r_margin = _mean_available_ranks([r_opm, r_gm, r_nm], [g["opm_chg"], g["gm_chg"], g["nm_chg"]])
    has_margin = g[["opm_chg", "gm_chg", "nm_chg"]].notna().any(axis=1)

    # Combined Fundamental Momentum rank (equal weight across available profit, revenue, and margin pillars)
    f_num = (
        r_profit.where(has_profit, 0.0)
        + r_rev.where(has_rev, 0.0)
        + r_margin.where(has_margin, 0.0)
    )
    f_den = has_profit.astype(float) + has_rev.astype(float) + has_margin.astype(float)
    r_fund = (f_num / f_den.where(f_den > 0)).fillna(0.5)

    # Residual Momentum & 52-Week-High Proximity ranks
    r_res_sec = _pct_rank_within_group(g["res_mom_sec_ir"])
    r_res_cum = _pct_rank_within_group(g["res_mom_sec_cum"])
    r_res_mkt = _pct_rank_within_group(g["res_mom_mkt_ir"])
    r_52wh = _pct_rank_within_group(g["high52_prox"])
    r_52wh_l1 = _pct_rank_within_group(g["high52_prox_lag1"])

    if strategy_id == "L1_Price_12_1_Baseline":
        score = g["mom_12_1"]
    elif strategy_id == "L2_Price_Plus_Fund":
        score = 0.50 * r_price + 0.50 * r_fund
    elif strategy_id == "L3_Price_Fund_ResMom":
        score = (r_price + r_fund + r_res_sec) / 3.0
    elif strategy_id == "L4_Price_Fund_Res_52WH":
        score = (r_price + r_fund + r_res_sec + r_52wh) / 4.0

    # V2 Fundamental Sub-Variations (inside Top-20)
    elif strategy_id == "V2_Pure_Fund_In_Top20":
        score = r_fund
    elif strategy_id == "V2a_Price_Plus_ProfitGrowth":
        score = 0.50 * r_price + 0.50 * r_profit
    elif strategy_id == "V2b_Price_Plus_RevAccel":
        score = 0.50 * r_price + 0.50 * r_rev
    elif strategy_id == "V2c_Price_Plus_MarginImp":
        score = 0.50 * r_price + 0.50 * r_margin

    # V3 Residual Momentum Variations
    elif strategy_id == "V3a_ResMom_Sec_Standalone":
        score = g["res_mom_sec_ir"]
    elif strategy_id == "V3b_ResMom_Mkt_Standalone":
        score = g["res_mom_mkt_ir"]
    elif strategy_id == "V3c_Price_Top20_Plus_ResMom_Sec":
        score = 0.50 * r_price + 0.50 * r_res_sec
    elif strategy_id == "V3d_Price_Top20_Plus_ResMom_Cum":
        score = 0.50 * r_price + 0.50 * r_res_cum

    # V4 52-Week-High Proximity Variations
    elif strategy_id == "V4a_Price_Top20_Plus_52WH":
        score = 0.50 * r_price + 0.50 * r_52wh
    elif strategy_id == "V4b_FullUni_Price_Plus_52WH":
        score = 0.50 * r_price + 0.50 * r_52wh
    elif strategy_id == "V4c_52WH_Standalone":
        score = g["high52_prox"]
    elif strategy_id == "V4d_Price_Top20_Plus_52WH_Lag1":
        score = 0.50 * r_price + 0.50 * r_52wh_l1

    # V5 Pure Price/Idiosyncratic 3-Pillar Composite (Price + ResMom + 52WH, No SEC Lag)
    elif strategy_id == "V5_Price_ResMom_52WH_NoFund":
        score = (r_price + r_res_sec + r_52wh) / 3.0
    else:
        raise ValueError(f"Unknown strategy_id: {strategy_id}")

    g["composite_score"] = score
    g["r_price"] = r_price
    g["r_fund"] = r_fund
    g["r_profit"] = r_profit
    g["r_rev"] = r_rev
    g["r_margin"] = r_margin
    g["r_res_sec"] = r_res_sec
    g["r_52wh"] = r_52wh

    g = g[g["composite_score"].notna()].sort_values(
        ["composite_score", "mom_12_1", "ticker"],
        ascending=[False, False, True],
    )
    return g


# ─────────────────────────────────────────────────────────────────────────────
# 5. Portfolio Simulation & Paired Statistical Significance Engine
# ─────────────────────────────────────────────────────────────────────────────
def simulate_strategy(
    df_panel: pd.DataFrame,
    store: CleanRoomEquityStore,
    form_dates: pd.DatetimeIndex,
    strategy_id: str,
    shortlist_n: Optional[int] = 20,
    k: int = 1,
    exec_mode: str = "open",
    self_financing: bool = False,
) -> pd.DataFrame:
    rows = []
    w_prev: Dict[str, float] = {}
    ret_col = "ret_oo" if exec_mode == "open" else "ret_cc"
    st_col = "status_oo" if exec_mode == "open" else "status_cc"

    for t in form_dates:
        m = t + pd.offsets.MonthEnd(1)
        rf_m = float(store.rf.get(m, 0.0))
        g = df_panel[df_panel["t"] == t].copy()
        if exec_mode == "open":
            g = g[g["ret_oo"].notna()]
        ranked = score_candidates_at_month(g, strategy_id=strategy_id, shortlist_n=shortlist_n)
        top = ranked.head(k)

        target_stocks: Dict[str, float] = {}
        slot_picks: List[str] = []
        stock_rets: Dict[str, Tuple[float, str]] = {}

        if top.empty:
            slot_picks = ["CASH"] * k
        else:
            w_slot = 1.0 / len(top)
            for _, r in top.iterrows():
                tk = str(r["ticker"])
                rv = float(r[ret_col])
                st = str(r[st_col])
                st_ok = "ok" if st in ("ok", "ok_open", "ok_close1_fallback") else st
                target_stocks[tk] = target_stocks.get(tk, 0.0) + w_slot
                slot_picks.append(tk)
                stock_rets[tk] = (rv, st_ok)

        exposure = float(sum(target_stocks.values()))
        cash_weight = max(0.0, 1.0 - exposure)
        gross = float(sum(target_stocks[s] * stock_rets[s][0] for s in target_stocks) + cash_weight * rf_m)

        if self_financing:
            cap_frac, turn_val = solve_self_financing_capital(target_stocks, w_prev, COST_PER_SIDE)
            reconstructed_turn = float(turn_val)
            net = max(0.0, cap_frac * (1.0 + gross)) - 1.0
        else:
            all_eq = set(target_stocks.keys()) | set(w_prev.keys())
            eq_turn = float(sum(abs(target_stocks.get(s, 0.0) - w_prev.get(s, 0.0)) for s in all_eq))
            reconstructed_turn = eq_turn
            net = gross - eq_turn * COST_PER_SIDE

        grow = {s: target_stocks[s] * (1.0 + stock_rets[s][0]) for s in target_stocks if stock_rets[s][1] == "ok"}
        w_prev = {s: v / (1.0 + gross) for s, v in grow.items()} if (1.0 + gross) > 0 else {}

        rows.append({
            "formation": str(t.date()),
            "month": m,
            "picks": "|".join(slot_picks),
            "exposure": exposure,
            "gross": gross,
            "turnover": reconstructed_turn,
            "net": net,
            "rf": rf_m,
        })
    return pd.DataFrame(rows).set_index("month")


def compute_metrics(df_sim: pd.DataFrame, start: str, end: str, exclude_year: Optional[int] = None) -> dict:
    sub = df_sim.loc[start:end].copy()
    if exclude_year is not None:
        sub = sub[sub.index.year != exclude_year]
    n = len(sub)
    if n == 0:
        return {}
    tot = float((1.0 + sub["net"]).prod())
    cagr = float(tot ** (12.0 / n) - 1.0)
    ex = sub["net"] - sub["rf"]
    vol = float(sub["net"].std(ddof=1) * math.sqrt(12.0)) if n > 1 else 0.0
    sharpe = float(ex.mean() / ex.std(ddof=1) * math.sqrt(12.0)) if (n > 1 and ex.std(ddof=1) > 0) else 0.0
    eq = (1.0 + sub["net"]).cumprod()
    max_dd = float((eq / eq.cummax() - 1.0).min())
    avg_turn = float(sub["turnover"].mean())
    hit_gt10 = float((sub["net"] >= 0.10).mean() * 100.0)
    hit_gt20 = float((sub["net"] >= 0.20).mean() * 100.0)
    win_rate = float((sub["net"] > 0.0).mean() * 100.0)
    return {
        "months": int(n),
        "cagr_pct": round(cagr * 100.0, 2),
        "sharpe": round(sharpe, 2),
        "vol_pct": round(vol * 100.0, 2),
        "max_dd_pct": round(max_dd * 100.0, 2),
        "avg_turn": round(avg_turn, 3),
        "win_rate_pct": round(win_rate, 1),
        "months_ge_10pct": round(hit_gt10, 1),
        "months_ge_20pct": round(hit_gt20, 1),
    }


def evaluate_all_windows(df_sim: pd.DataFrame) -> dict:
    return {
        "2010_2026_full": compute_metrics(df_sim, "2010-01-31", "2026-09-30"),
        "2015_2026_full": compute_metrics(df_sim, "2015-01-31", "2026-09-30"),
        "2015_2026_ex2022": compute_metrics(df_sim, "2015-01-31", "2026-09-30", exclude_year=2022),
        "2010_2026_ex2022": compute_metrics(df_sim, "2010-01-31", "2026-09-30", exclude_year=2022),
        "sub_2010_2014": compute_metrics(df_sim, "2010-01-31", "2014-12-31"),
        "sub_2015_2019": compute_metrics(df_sim, "2015-01-31", "2019-12-31"),
        "sub_2020_2021": compute_metrics(df_sim, "2020-01-31", "2021-12-31"),
        "sub_2022_only": compute_metrics(df_sim, "2022-01-31", "2022-12-31"),
        "sub_2023_2026": compute_metrics(df_sim, "2023-01-31", "2026-09-30"),
    }


def compute_paired_stats(df_cand: pd.DataFrame, df_base: pd.DataFrame, start: str, end: str) -> dict:
    a = df_cand.loc[start:end, "net"]
    b = df_base.loc[start:end, "net"]
    diff_ari = a - b
    diff_log = np.log1p(a) - np.log1p(b)
    n = len(diff_ari)
    if n < 12:
        return {"t_ari": 0.0, "t_log": 0.0, "pct_diff_months": 0.0}
    sd_ari = float(diff_ari.std(ddof=1))
    sd_log = float(diff_log.std(ddof=1))
    t_ari = float(diff_ari.mean() / (sd_ari / math.sqrt(n))) if sd_ari > 1e-12 else 0.0
    t_log = float(diff_log.mean() / (sd_log / math.sqrt(n))) if sd_log > 1e-12 else 0.0
    diff_picks = float((df_cand.loc[start:end, "picks"] != df_base.loc[start:end, "picks"]).mean() * 100.0)
    return {
        "t_ari": round(t_ari, 2),
        "t_log": round(t_log, 2),
        "pct_diff_months": round(diff_picks, 1),
    }


def compute_nov2026_live_shortlist(
    store: CleanRoomEquityStore,
    members: Dict[pd.Timestamp, Set[str]],
    sec_panel: pd.DataFrame,
    cmap: pd.DataFrame,
    fund_grid: pd.DataFrame,
    ssm_dir: str,
) -> Dict[str, pd.DataFrame]:
    """
    Computes the November 2026 (`formation = 2026-10-30`) Top-20 shortlist and all 4-Layer scores
    for both `Tech_Only` and `All_SP500`.
    """
    t_sep = pd.Timestamp("2026-09-30")
    t_oct_prev = pd.Timestamp("2025-10-31")
    P = store.P
    seg_m = store.seg_m
    daily = store.daily
    seg_d = store.seg_d.reindex(index=daily.index, columns=daily.columns)
    r_d = daily.pct_change(fill_method=None).where(seg_d == seg_d.shift(1))

    hi252 = daily.rolling(252, min_periods=200).max()
    ok252 = seg_d == seg_d.shift(251)
    prox_d = (daily / hi252).where(ok252)

    t2c = {_norm_sym(t): int(c) for t, c in zip(cmap["ticker"], cmap["cik"]) if pd.notna(c)}
    fund_idx = fund_grid.set_index(["t", "cik"])
    fund_cols = ["eps_gs_q", "eps_accel", "eps_g_sym", "opinc_gs_q", "rev_g_q", "rev_accel", "rev_g_ttm", "opm_chg", "gm_chg", "nm_chg"]

    d_idx = daily.index
    pos_last = len(d_idx) - 1
    pos_sep = int(d_idx.searchsorted(t_sep, side="right") - 1)
    pos_oct_prev = int(d_idx.searchsorted(t_oct_prev, side="right") - 1)

    win_slice = slice(pos_oct_prev + 1, pos_sep + 1)
    r_win = r_d.iloc[win_slice]
    spy_win = r_win["SPY"].values
    X_mkt = np.column_stack([np.ones(len(spy_win)), spy_win])
    mkt_pinv = np.linalg.pinv(X_mkt)
    sec_solvers = {}
    for sec_name, etf_tk in SECTOR_ETF_MAP.items():
        if etf_tk in r_win.columns and np.isfinite(r_win[etf_tk].values).all():
            X_s = np.column_stack([np.ones(len(spy_win)), spy_win, r_win[etf_tk].values])
            sec_solvers[sec_name] = (X_s, np.linalg.pinv(X_s))

    rows = []
    for tk in sorted(members[t_sep]):
        if tk not in P.columns or pd.isna(P.at[t_sep, tk]) or pd.isna(P.at[t_oct_prev, tk]):
            continue
        if seg_m.at[t_sep, tk] != seg_m.at[t_oct_prev, tk]:
            continue
        if tk not in sec_panel.columns or not isinstance(sec_panel.at[t_sep, tk], str):
            continue
        sec = str(sec_panel.at[t_sep, tk])
        m12_1 = float(P.at[t_sep, tk] / P.at[t_oct_prev, tk] - 1.0)
        h52 = float(prox_d.iloc[pos_last][tk]) if (tk in prox_d.columns and pd.notna(prox_d.iloc[pos_last][tk])) else float("nan")
        h52_l1 = float(prox_d.iloc[pos_sep][tk]) if (tk in prox_d.columns and pd.notna(prox_d.iloc[pos_sep][tk])) else float("nan")

        res_mkt_ir, res_sec_ir, res_sec_cum = float("nan"), float("nan"), float("nan")
        if tk in r_win.columns and seg_d.iloc[pos_oct_prev][tk] == seg_d.iloc[pos_sep][tk]:
            y = r_win[tk].values
            if np.isfinite(y).all():
                c_m = mkt_pinv @ y
                eps_m = y - X_mkt @ c_m
                u_m = c_m[0] + eps_m
                sd_m = float(np.std(eps_m, ddof=2))
                if sd_m > 1e-8:
                    res_mkt_ir = float(np.mean(u_m) / sd_m * math.sqrt(252.0))
                if sec in sec_solvers:
                    X_s, pinv_s = sec_solvers[sec]
                    c_s = pinv_s @ y
                    eps_s = y - X_s @ c_s
                    u_s = c_s[0] + eps_s
                    sd_s = float(np.std(eps_s, ddof=3))
                    if sd_s > 1e-8:
                        res_sec_ir = float(np.mean(u_s) / sd_s * math.sqrt(252.0))
                    res_sec_cum = float(np.prod(1.0 + np.clip(u_s, -0.95, 5.0)) - 1.0)

        rec = {
            "ticker": tk,
            "sector": sec,
            "mom_12_1": m12_1,
            "high52_prox": h52,
            "high52_prox_lag1": h52_l1,
            "res_mom_sec_ir": res_sec_ir,
            "res_mom_sec_cum": res_sec_cum,
            "res_mom_mkt_ir": res_mkt_ir,
        }
        c = t2c.get(tk)
        if c is not None and (t_sep, c) in fund_idx.index:
            frow = fund_idx.loc[(t_sep, c)]
            for fc in fund_cols:
                rec[fc] = float(frow[fc]) if pd.notna(frow[fc]) else float("nan")
        else:
            for fc in fund_cols:
                rec[fc] = float("nan")
        rows.append(rec)

    df_live = pd.DataFrame(rows)
    return {
        "Tech_Only": df_live[df_live["sector"] == "Information Technology"].copy(),
        "All_SP500": df_live.copy(),
    }


def main():
    t0 = time.time()
    print("=" * 105)
    print("RUNNING 100% CLEAN-ROOM MULTI-BAGGER LAYERED MOMENTUM BACKTEST (outputs/multibagger_layered_momentum_20261102)")
    print("=" * 105)

    ssm_dir = os.path.join(REPO_ROOT, ORIG_SSM_REL)
    data_dir = os.path.join(ssm_dir, "data")
    store = CleanRoomEquityStore(REPO_ROOT, ORIG_SSM_REL)

    print("[1/5] Reconstructing Clean-Room CIK Map, Aliases, PIT Membership & Historical GICS Sectors...")
    sub, cmap, aliases = cleanroom_reconstruct_cik_map_and_sub(ssm_dir, store)
    bad_spells = cleanroom_untrusted_and_excluded_spells(data_dir, store)
    all_months = store.P.index[(store.P.index >= pd.Timestamp("2009-12-31")) & (store.P.index <= pd.Timestamp("2026-09-30"))]
    members = cleanroom_load_pit_membership(data_dir, all_months, bad_spells)
    sec_panel = cleanroom_build_pit_sector_panel(data_dir, store, aliases, cmap, all_months)

    print("[2/5] Parsing Raw SEC FSDS `num_*.parquet` (`filed + 1d <= t`) for PIT Fundamental Momentum...")
    fund_grid = cleanroom_build_pit_fundamentals(ssm_dir, sub, cmap, all_months)

    print("[3/5] Computing Daily Residual Momentum (`12-1` vs SPY + Sector ETF) & 52-Week-High Proximity Panel...")
    form_2010_2026 = store.P.index[(store.P.index >= pd.Timestamp("2009-12-31")) & (store.P.index <= pd.Timestamp("2026-08-31"))]
    df_all = compute_residual_momentum_and_52wh_panel(store, members, sec_panel, cmap, fund_grid, ssm_dir, form_2010_2026)
    df_tech = df_all[df_all["sector"] == "Information Technology"].copy()
    print(f"      -> Full S&P 500 panel rows: {len(df_all):,} | Tech-only rows: {len(df_tech):,} across {len(form_2010_2026)} months")

    # Define the Pre-Frozen Strategy Suite: (strategy_id, category, shortlist_n, description)
    STRATEGIES = [
        # 4-Layer Pre-Frozen Progression (Stage 1: 12-1 Top-20 -> Stage 2: Equal-Weight Percentile Rank)
        ("L1_Price_12_1_Baseline", "4-Layer Progression", 20, "Layer 1: Pure Price Momentum (12-1 Baseline)"),
        ("L2_Price_Plus_Fund", "4-Layer Progression", 20, "Layer 2: 12-1 Top-20 -> 50% Price + 50% PIT Fundamental Composite"),
        ("L3_Price_Fund_ResMom", "4-Layer Progression", 20, "Layer 3: 12-1 Top-20 -> 1/3 Price + 1/3 Fundamental + 1/3 Residual Mom"),
        ("L4_Price_Fund_Res_52WH", "4-Layer Progression", 20, "Layer 4: 12-1 Top-20 -> 1/4 Price + 1/4 Fund + 1/4 ResMom + 1/4 52W-High"),

        # Version 2 Ablations: PIT Fundamental Sub-Factors inside 12-1 Top-20
        ("V2_Pure_Fund_In_Top20", "V2 Fundamental Breakdown", 20, "V2 Pure: 12-1 Top-20 -> 100% PIT Fundamental Rank"),
        ("V2a_Price_Plus_ProfitGrowth", "V2 Fundamental Breakdown", 20, "V2a: 12-1 Top-20 -> 50% Price + 50% EPS/Operating Profit Growth"),
        ("V2b_Price_Plus_RevAccel", "V2 Fundamental Breakdown", 20, "V2b: 12-1 Top-20 -> 50% Price + 50% Revenue Growth & Acceleration"),
        ("V2c_Price_Plus_MarginImp", "V2 Fundamental Breakdown", 20, "V2c: 12-1 Top-20 -> 50% Price + 50% Margin Improvement (OpM/GM/NM)"),

        # Version 3 Ablations: Residual Momentum (12-1)
        ("V3a_ResMom_Sec_Standalone", "V3 Residual Momentum", None, "V3a: Pure Residual Momentum (12-1 IR vs SPY + Sector ETF, Full Uni)"),
        ("V3b_ResMom_Mkt_Standalone", "V3 Residual Momentum", None, "V3b: Pure Residual Momentum (12-1 IR vs SPY Only, Full Uni)"),
        ("V3c_Price_Top20_Plus_ResMom_Sec", "V3 Residual Momentum", 20, "V3c: 12-1 Top-20 -> 50% Price + 50% Residual Mom (IR vs SPY + Sector)"),
        ("V3d_Price_Top20_Plus_ResMom_Cum", "V3 Residual Momentum", 20, "V3d: 12-1 Top-20 -> 50% Price + 50% Cumulative Residual Return"),

        # Version 4 Ablations: 52-Week-High Proximity (George & Hwang 2004)
        ("V4a_Price_Top20_Plus_52WH", "V4 52W-High Proximity", 20, "V4a: 12-1 Top-20 -> 50% Price + 50% 52W-High Proximity (Close[t]/Max252)"),
        ("V4b_FullUni_Price_Plus_52WH", "V4 52W-High Proximity", None, "V4b: Full Universe -> 50% Price (12-1) + 50% 52W-High Proximity"),
        ("V4c_52WH_Standalone", "V4 52W-High Proximity", None, "V4c: Pure 52W-High Proximity (with 12-1 Mom Tie-Breaker)"),
        ("V4d_Price_Top20_Plus_52WH_Lag1", "V4 52W-High Proximity", 20, "V4d: 12-1 Top-20 -> 50% Price + 50% Lagged 52W-High Proximity (t-1)"),

        # Version 5: Pure Price + Residual + 52W-High (No SEC Filing Lag)
        ("V5_Price_ResMom_52WH_NoFund", "V5 No-Lag Price Composite", 20, "V5: 12-1 Top-20 -> 1/3 Price + 1/3 Residual Mom + 1/3 52W-High"),
    ]

    print("[4/5] Running Next-Day Open-to-Open Backtests Across Both Universes (`Tech_Only` & `All_SP500`) and `Top-1`/`Top-3`...")
    summary_rows = []
    full_json = {}
    ledgers_dir = os.path.join(HERE, "ledgers")
    os.makedirs(ledgers_dir, exist_ok=True)

    for uni_name, df_uni in [("Tech_Only", df_tech), ("All_SP500", df_all)]:
        full_json[uni_name] = {}
        for k in [1, 3]:
            base_df = simulate_strategy(df_uni, store, form_2010_2026, "L1_Price_12_1_Baseline", shortlist_n=20, k=k, exec_mode="open", self_financing=False)
            for strat_id, cat, sl_n, desc in STRATEGIES:
                df_open = simulate_strategy(df_uni, store, form_2010_2026, strat_id, shortlist_n=sl_n, k=k, exec_mode="open", self_financing=False)
                df_open_sf = simulate_strategy(df_uni, store, form_2010_2026, strat_id, shortlist_n=sl_n, k=k, exec_mode="open", self_financing=True)
                df_close = simulate_strategy(df_uni, store, form_2010_2026, strat_id, shortlist_n=sl_n, k=k, exec_mode="close", self_financing=False)

                win_open = evaluate_all_windows(df_open)
                win_sf = evaluate_all_windows(df_open_sf)
                win_close = evaluate_all_windows(df_close)
                p_2010 = compute_paired_stats(df_open, base_df, "2010-01-31", "2026-09-30")
                p_2015 = compute_paired_stats(df_open, base_df, "2015-01-31", "2026-09-30")

                # Save monthly ledger for the 4-layer progression & key versions
                if strat_id in ("L1_Price_12_1_Baseline", "L2_Price_Plus_Fund", "L3_Price_Fund_ResMom", "L4_Price_Fund_Res_52WH", "V3c_Price_Top20_Plus_ResMom_Sec", "V4a_Price_Top20_Plus_52WH", "V5_Price_ResMom_52WH_NoFund"):
                    df_open.to_csv(os.path.join(ledgers_dir, f"ledger_{uni_name}_Top{k}_{strat_id}.csv"))

                key_id = f"Top{k}_{strat_id}"
                full_json[uni_name][key_id] = {
                    "strategy_id": strat_id,
                    "category": cat,
                    "shortlist_n": sl_n,
                    "top_k": k,
                    "description": desc,
                    "open_drifted_additive": win_open,
                    "open_drifted_self_financing": win_sf,
                    "close_to_close_additive": win_close,
                    "paired_vs_L1_2010_2026": p_2010,
                    "paired_vs_L1_2015_2026": p_2015,
                }

                w10 = win_open["2010_2026_full"]
                w15 = win_open["2015_2026_full"]
                w15_ex22 = win_open["2015_2026_ex2022"]
                summary_rows.append({
                    "universe": uni_name,
                    "top_k": f"Top-{k}",
                    "strategy_id": strat_id,
                    "category": cat,
                    "shortlist_n": sl_n if sl_n is not None else "Full",
                    "cagr_2010_2026": w10["cagr_pct"],
                    "sharpe_2010_2026": w10["sharpe"],
                    "maxdd_2010_2026": w10["max_dd_pct"],
                    "vol_2010_2026": w10["vol_pct"],
                    "t_ari_2010_2026": p_2010["t_ari"],
                    "t_log_2010_2026": p_2010["t_log"],
                    "pct_diff_picks_2010": p_2010["pct_diff_months"],
                    "cagr_2015_2026": w15["cagr_pct"],
                    "sharpe_2015_2026": w15["sharpe"],
                    "maxdd_2015_2026": w15["max_dd_pct"],
                    "t_ari_2015_2026": p_2015["t_ari"],
                    "t_log_2015_2026": p_2015["t_log"],
                    "cagr_2015_ex2022": w15_ex22["cagr_pct"],
                    "sub_2010_2014": win_open["sub_2010_2014"]["cagr_pct"],
                    "sub_2015_2019": win_open["sub_2015_2019"]["cagr_pct"],
                    "sub_2020_2021": win_open["sub_2020_2021"]["cagr_pct"],
                    "sub_2022_only": win_open["sub_2022_only"]["cagr_pct"],
                    "sub_2023_2026": win_open["sub_2023_2026"]["cagr_pct"],
                    "avg_turn": w10["avg_turn"],
                    "months_ge_20pct": w10["months_ge_20pct"],
                    "cagr_sf_2010_2026": win_sf["2010_2026_full"]["cagr_pct"],
                    "cagr_cc_2010_2026": win_close["2010_2026_full"]["cagr_pct"],
                })

    # Shortlist N Sensitivity (Top-10 vs Top-15 vs Top-20 vs Top-30) for L2, L3, L4 on Tech Top-1 & All_SP500 Top-1
    sens_rows = []
    for uni_name, df_uni in [("Tech_Only", df_tech), ("All_SP500", df_all)]:
        for k in [1, 3]:
            for sl_n in [10, 15, 20, 30]:
                for strat_id in ["L2_Price_Plus_Fund", "L3_Price_Fund_ResMom", "L4_Price_Fund_Res_52WH", "V3c_Price_Top20_Plus_ResMom_Sec", "V4a_Price_Top20_Plus_52WH"]:
                    df_s = simulate_strategy(df_uni, store, form_2010_2026, strat_id, shortlist_n=sl_n, k=k, exec_mode="open", self_financing=False)
                    w10 = compute_metrics(df_s, "2010-01-31", "2026-09-30")
                    w15 = compute_metrics(df_s, "2015-01-31", "2026-09-30")
                    sens_rows.append({
                        "universe": uni_name,
                        "top_k": f"Top-{k}",
                        "strategy_id": strat_id,
                        "shortlist_n": sl_n,
                        "cagr_2010_2026": w10["cagr_pct"],
                        "sharpe_2010_2026": w10["sharpe"],
                        "maxdd_2010_2026": w10["max_dd_pct"],
                        "cagr_2015_2026": w15["cagr_pct"],
                        "sharpe_2015_2026": w15["sharpe"],
                        "maxdd_2015_2026": w15["max_dd_pct"],
                    })

    print("[5/5] Computing November 2026 Live Picks & Exporting Summary Tables...")
    live_panels = compute_nov2026_live_shortlist(store, members, sec_panel, cmap, fund_grid, ssm_dir)
    live_picks_summary = {}
    for uni_name, df_l in live_panels.items():
        live_picks_summary[uni_name] = {}
        for strat_id, _, sl_n, _ in STRATEGIES:
            rk = score_candidates_at_month(df_l, strategy_id=strat_id, shortlist_n=sl_n)
            live_picks_summary[uni_name][strat_id] = {
                "Top1": rk["ticker"].iloc[0] if len(rk) >= 1 else "CASH",
                "Top3": "|".join(rk["ticker"].iloc[:3].tolist()),
                "Top5": "|".join(rk["ticker"].iloc[:5].tolist()),
            }
        # Save full Top-20 live shortlist table with all factor scores
        rk_l4 = score_candidates_at_month(df_l, strategy_id="L4_Price_Fund_Res_52WH", shortlist_n=20)
        rk_l4.to_csv(os.path.join(HERE, f"nov2026_top20_shortlist_{uni_name}.csv"), index=False)

    full_json["shortlist_sensitivity"] = sens_rows
    full_json["november_2026_live_picks"] = live_picks_summary

    df_sum = pd.DataFrame(summary_rows)
    df_sum.to_csv(os.path.join(HERE, "multibagger_layered_summary_table.csv"), index=False)
    pd.DataFrame(sens_rows).to_csv(os.path.join(HERE, "shortlist_n_sensitivity_table.csv"), index=False)
    with open(os.path.join(HERE, "multibagger_layered_summary.json"), "w", encoding="utf-8") as fh:
        json.dump(full_json, fh, indent=2)

    # Print Console Summary
    for uni_name in ["Tech_Only", "All_SP500"]:
        for k_str in ["Top-1", "Top-3"]:
            print(f"\n--- {uni_name} | {k_str} (Next-Day Open, Drifted Wt, 0.1% Fee) ---")
            sub_t = df_sum[(df_sum["universe"] == uni_name) & (df_sum["top_k"] == k_str)]
            cols = [
                "strategy_id", "shortlist_n",
                "cagr_2010_2026", "sharpe_2010_2026", "maxdd_2010_2026", "t_ari_2010_2026",
                "cagr_2015_2026", "sharpe_2015_2026", "maxdd_2015_2026",
                "sub_2010_2014", "sub_2015_2019", "sub_2020_2021", "sub_2022_only", "sub_2023_2026",
            ]
            print(sub_t[cols].to_string(index=False))

    print("\n--- November 2026 Live Picks (Signal Date: 2026-10-30 -> Trade Date: 2026-11-02 Open) ---")
    for uni_name in ["Tech_Only", "All_SP500"]:
        print(f"  [{uni_name}]")
        for strat_id in ["L1_Price_12_1_Baseline", "L2_Price_Plus_Fund", "L3_Price_Fund_ResMom", "L4_Price_Fund_Res_52WH", "V3c_Price_Top20_Plus_ResMom_Sec", "V4a_Price_Top20_Plus_52WH", "V5_Price_ResMom_52WH_NoFund"]:
            p_info = live_picks_summary[uni_name][strat_id]
            print(f"    {strat_id:32s} -> Top-1: {p_info['Top1']:6s} | Top-3: {p_info['Top3']}")

    print(f"\nCompleted in {time.time() - t0:.1f}s.")


if __name__ == "__main__":
    main()
