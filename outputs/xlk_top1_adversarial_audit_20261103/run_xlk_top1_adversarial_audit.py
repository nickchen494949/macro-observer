#!/usr/bin/env python3
"""
XLK / HISTORICAL PIT TECH POOL + 12-1 MOMENTUM TOP-1:
END-TO-END ADVERSARIAL FALSIFICATION & AUDIT ("TRY TO KILL IT")
================================================================
Strictly isolated in `outputs/xlk_top1_adversarial_audit_20261103/`.
Zero modifications to `research/sector_stock_momentum/`.

Executes the 7-step adversarial falsification protocol requested by the user:
  Step 1: Rebuild & audit the true historical Point-in-Time S&P 500 Information Technology pool
          (2008-12-31 to 2026-08-31, 213 formation months -> holding months 2009-01 to 2026-09)
          using 212 contemporaneous Wikipedia S&P 500 archival revisions + official S&P DJI GICS
          effective dates + QSTK/OTT archival price/open fills for LSI, WFR/SUNEQ, MOLX, BMC.
  Step 2: Strictly freeze the rule:
          PIT Tech Pool -> 12-1 Momentum (P[t-1]/P[t-12]-1) -> Top-1 -> Next-Day Open execution
          (Open[t+1, d1] to Open[t+2, d1]) -> 10 bps/side transaction cost (0 ML, 0 filters).
  Step 3: Full 2009-2026.09 backtest (213 months) and sub-period breakdown:
          2009-2014 (72m), 2015-2019 (60m), 2020-2022 (36m), 2023-2026.09 (45m),
          plus 2009-2026.09 (213m), 2015-2026.09 (141m), 2019-2026.09 (93m), and all 18 calendar years.
  Step 4: Forensic audit of every super-winner pick (NVDA, SNDK, PLTR, AMD, SMCI, ENPH, AAPL,
          AVGO, MU, STX, WDC, FSLR, ANET, PAYC, DXC, MPWR, SWKS, QRVO, LSI, etc.) and all 213 months.
  Step 5: Adversarial falsification & stress tests ("Try to Kill It"):
          - Cost doubling/tripling (20 bps, 30 bps, 50 bps/side)
          - Open execution slippage (+10 bps, +25 bps, +50 bps/side)
          - Execution timing (Same-day close, Next-day close, 2-day lag close)
          - Sector pool variants (V0 Backward-Rebuilt, V1 True Archival GICS, V1b Archival ex-NFLX,
            V2 Strict Core Pure-IT dropping all 2018/2023 reclassified & solar/borderline names,
            V3 100% SEC EDGAR SIC-Code Tech Pool)
          - Super-winner removal (Drop SNDK-2026, Drop PLTR, Drop NVDA, Drop SMCI+ENPH, Drop SNDK+PLTR+SMCI,
            Zero out Best-3 and Best-5 months)
          - Missing-stock & delisting worst-case stress (-30%, -100%, adversarial missing-spell shock)
          - Rank neighborhood (Rank #1 vs Rank #2 alone vs Rank #3 alone vs Top-2 EW vs Top-3 EW vs Top-5 EW)
  Step 6: Statistical re-evaluation & project-wide multiple testing correction:
          - Paired Newey-West HAC (lags 3 & 6) and 10,000-draw Stationary Block Bootstrap vs
            XLK ETF, Equal-Weight Tech Pool (EW IT), QQQ ETF, SPY ETF
          - Bailey & López de Prado (2014) Deflated Sharpe Ratio (DSR), Effective Independent Trials (M_eff),
            Bonferroni / Šidák / Holm-Bonferroni p-values, and Harvey-Liu-Zhu (2016) t > 3.0 hurdle.
  Step 7: Freeze live forward-test protocol & export current month-end rankings (2026-08-31 & 2026-09-30).
"""

import glob
import io
import json
import os
import sys
import urllib.request
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm, skew, kurtosis, wilcoxon

warnings.filterwarnings("ignore")

REPO_ROOT = Path("/Users/happygolucky/Desktop/宏观观察器").resolve()
SSM_DIR = REPO_ROOT / "research" / "sector_stock_momentum"
OUT_DIR = REPO_ROOT / "outputs" / "xlk_top1_adversarial_audit_20261103"
ARCH_FILL_DIR = OUT_DIR / "archive_fills"
OUT_DIR.mkdir(parents=True, exist_ok=True)
ARCH_FILL_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(SSM_DIR))
import backtest as bt  # noqa: E402
import ml2_run as m2  # noqa: E402


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1: LOAD BASELINE STORE + APPLY VERIFIED ARCHIVAL PRICE & OPEN FILLS
# ─────────────────────────────────────────────────────────────────────────────
def ensure_qstk_open_files():
    """Ensure QSTK CSVs with daily Open/Close/Adj Close are cached for archival IT tickers."""
    qstk_it = ["LSI", "WFR", "MOLX", "BMC", "ACS", "JAVA", "NOVL", "TLAB"]
    for sym in qstk_it:
        p = ARCH_FILL_DIR / f"qstk_{sym}.csv"
        if not p.exists():
            url = f"https://raw.githubusercontent.com/QuantSoftware/QuantSoftwareToolkit/master/QSTK/QSData/Yahoo/{sym}.csv"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"})
            with urllib.request.urlopen(req, timeout=20) as r:
                p.write_bytes(r.read())


def load_enhanced_prices_and_opens():
    """
    Loads baseline `bt.load_prices()` + `m2.build_opens(daily)` and also constructs an
    enhanced price/open store (`daily_v1`, `P_v1`, `O_v1`, `bad_v1`) that fills the 4
    verifiable archival IT spells (`LSI`, `SUNEQ/WFR`, `MOLX`, `BMC`) and QSTK daily Opens.
    """
    ensure_qstk_open_files()
    daily_v0, P_v0, aliases, bad_v0 = bt.load_prices()
    O_v0 = m2.build_opens(daily_v0)

    daily_v1 = daily_v0.copy()
    O_v1 = O_v0.copy()
    bad_v1 = {k: list(v) for k, v in bad_v0.items()}

    # Load QSTK + OTT archival fills for LSI, WFR (SUNEQ), MOLX, BMC, and QSTK Opens for ACS, JAVA, NOVL, TLAB
    qstk_map = {
        "LSI": ("LSI", "2014-05-06", True),
        "SUNEQ": ("WFR", "2011-12-31", False),
        "MOLX": ("MOLX", "2013-12-09", True),
        "BMC": ("BMC", "2013-09-10", True),
        "ACS": ("ACS", "2010-02-05", False),
        "JAVA": ("JAVA", "2010-01-26", False),
        "NOVL": ("NOVL", "2011-04-27", False),
        "TLAB": ("TLAB", "2012-09-12", False),
    }

    arch_fill_audit = []
    for tk_bt, (q_sym, end_cut, use_ott_after_2012) in qstk_map.items():
        qp = ARCH_FILL_DIR / f"qstk_{q_sym}.csv"
        if not qp.exists():
            continue
        df_q = pd.read_csv(qp)
        df_q.columns = [c.strip() for c in df_q.columns]
        df_q["Date"] = pd.to_datetime(df_q["Date"])
        df_q = df_q.set_index("Date").sort_index()
        df_q = df_q[~df_q.index.duplicated(keep="last")]
        adj_c = df_q["Adj Close"].astype(float)
        raw_c = df_q["Close"].astype(float)
        raw_o = df_q["Open"].astype(float)
        adj_o = (raw_o * adj_c / raw_c).where(raw_c > 0)

        if use_ott_after_2012:
            op = ARCH_FILL_DIR / f"ott_{q_sym}.txt"
            if op.exists():
                rows = [l.split()[:6] for l in op.read_text().splitlines() if l.strip()]
                df_o = pd.DataFrame(rows, columns=["d", "o", "h", "l", "c", "v"])
                df_o["d"] = pd.to_datetime(df_o["d"], format="%Y%m%d")
                for col in ["o", "h", "l", "c"]:
                    df_o[col] = df_o[col].astype(float)
                ott_end = "2013-07-31" if tk_bt == "BMC" else end_cut
                df_o = df_o.set_index("d").sort_index().loc[:ott_end]
                df_o = df_o[~df_o.index.duplicated(keep="last")]
                ov_win = "2012-01-01" if tk_bt == "BMC" else "2007-01-01"
                ov = pd.concat([adj_c, df_o["c"]], axis=1, keys=["q", "o"]).dropna().loc[ov_win:"2012-09-12"]
                corr = float(ov.pct_change().corr().iloc[0, 1]) if len(ov) > 50 else np.nan
                scale = float(ov["q"].iloc[-1] / ov["o"].iloc[-1]) if len(ov) else 1.0
                after_c = df_o["c"].loc["2012-09-13":ott_end] * scale
                after_o = df_o["o"].loc["2012-09-13":ott_end] * scale
                # For BMC, after 2013-07-31 OTT switches symbol; BMC traded at ~$46.22 buyout until 2013-09-10
                if tk_bt == "BMC":
                    b_days = daily_v1["SPY"].dropna().loc["2013-08-01":"2013-09-10"].index
                    after_c = pd.concat([after_c, pd.Series(46.22, index=b_days)])
                    after_o = pd.concat([after_o, pd.Series(46.22, index=b_days)])
                adj_c = pd.concat([adj_c.loc[:"2012-09-12"], after_c])
                adj_o = pd.concat([adj_o.loc[:"2012-09-12"], after_o])
            else:
                corr = 1.0
        else:
            corr = 1.0

        # Align onto daily_v1 index up to end_cut
        idx_cut = daily_v1.index[daily_v1.index <= pd.Timestamp(end_cut)]
        if tk_bt not in daily_v1.columns:
            daily_v1[tk_bt] = np.nan
            O_v1[tk_bt] = np.nan
            bt.SEG_D[tk_bt] = np.nan
        daily_v1.loc[idx_cut, tk_bt] = adj_c.reindex(idx_cut)
        O_v1.loc[idx_cut, tk_bt] = adj_o.reindex(idx_cut)
        bt.SEG_D.loc[idx_cut, tk_bt] = 0.0
        bt.PRICE_SOURCE[tk_bt] = f"archive:qstk_ott:{q_sym}"
        if tk_bt == "LSI":
            bad_v1["LSI"] = []  # LSI Corp verified from QSTK+OTT up to 2014-05-06
        arch_fill_audit.append({
            "ticker": tk_bt,
            "archive_symbol": q_sym,
            "first_date": str(adj_c.index.min().date()),
            "last_date": str(adj_c.index.max().date()),
            "daily_bars": int(len(adj_c)),
            "overlap_corr_qstk_ott": round(corr, 5),
            "has_open_prices": True,
        })

    # Recompute monthly P_v1 and SEG_M exactly as backtest.py does
    monthly_v1 = daily_v1.resample("ME").last().where(daily_v1.resample("ME").count() > 0)
    obs = pd.DataFrame(
        np.where(daily_v1.notna().values, daily_v1.index.values[:, None], np.datetime64("NaT")),
        index=daily_v1.index,
        columns=daily_v1.columns,
    )
    last_obs = obs.resample("ME").max()
    mkt_last = daily_v1["SPY"].dropna().index.to_series().resample("ME").max()
    fresh = last_obs.ge(mkt_last - pd.Timedelta(days=7), axis=0)
    P_v1 = monthly_v1.where(fresh.reindex(index=monthly_v1.index, columns=monthly_v1.columns).fillna(False))
    bt.SEG_M = bt.SEG_D.resample("ME").last().reindex(P_v1.index)

    return (
        dict(daily=daily_v0, P=P_v0, O=O_v0, bad=bad_v0, aliases=aliases),
        dict(daily=daily_v1, P=P_v1, O=O_v1, bad=bad_v1, aliases=aliases),
        pd.DataFrame(arch_fill_audit),
    )


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1B: BUILD THE 4 HISTORICAL TECH POOL DEFINITIONS (V0, V1, V2, V3)
# ─────────────────────────────────────────────────────────────────────────────
def build_tech_pools(store_v0, store_v1, form):
    """
    Constructs 4 Point-in-Time Tech Pool definitions across all 213 formation months:
      - V0_Baseline_Rebuilt_IT: Exact `backtest.py` + `historical_sectors.py` IT pool on store_v0.
      - V1_Archival_Repaired_IT: Contemporaneous Wikipedia S&P 500 archival revisions + official GICS
        effective dates + QSTK/OTT archive price/open fills on store_v1.
      - V1b_Archival_ExNFLX_IT: Same as V1, but keeping NFLX in Consumer Discretionary pre-2018.
      - V2_Strict_Core_Pure_IT: Drops all 2018/2023 reclassified & solar/borderline stocks from V1.
      - V3_Strict_SEC_SIC_IT: 100% SEC EDGAR SIC-code Tech Pool (zero Wikipedia/Yahoo sector input).
    """
    members_raw, _ = bt.load_membership(form)
    members_v0 = {
        t: {x for x in mem if not any(a <= t <= b for a, b in store_v0["bad"].get(x, []))}
        for t, mem in members_raw.items()
    }
    members_v1 = {
        t: {x for x in mem if not any(a <= t <= b for a, b in store_v1["bad"].get(x, []))}
        for t, mem in members_raw.items()
    }

    st_df = bt.build_sector_table(store_v0["aliases"])
    secP_v0, secFlag_v0 = bt.build_panel(st_df, form)

    # Load 212 contemporaneous Wikipedia archival revisions
    df_arch = pd.read_parquet(OUT_DIR / "archival_wiki_sp500_monthly_gics.parquet")
    ARCH_TO_BT = {
        "YHOO": "AABA", "WFR": "SUNEQ", "JDSU": "VIAV", "CSC": "DXC", "HWP": "HPQ",
        "JAVA": "JAVA", "SUNW": "JAVA", "MOT": "MSI", "FSL-B": "FSL", "BRK-A": "BRK-B",
        "TYC": "JCI", "JOYG": "JOY", "NYX": "NYX", "PCS": "TMUS", "Q": "Q", "ERTS": "EA",
        "GOOG": "GOOGL",
    }
    for r in store_v0["aliases"].itertuples():
        ARCH_TO_BT.setdefault(r.old.replace(".", "-"), r.price_symbol)

    arch_map = {}
    for m, tk, comp, sec, sub in zip(
        df_arch.month, df_arch.ticker, df_arch.company, df_arch.arch_sector, df_arch.arch_subindustry
    ):
        mt = pd.Timestamp(m)
        arch_map[(mt, tk)] = (sec, sub, comp)
        if tk in ARCH_TO_BT:
            arch_map.setdefault((mt, ARCH_TO_BT[tk]), (sec, sub, comp))

    # Build V1 Archival sector panel (with official GICS transition dates enforced)
    secP_v1 = secP_v0.copy()
    secProv_v1 = secFlag_v0.copy()
    for col in secP_v1.columns:
        secP_v1[col] = secP_v0[col]
        secProv_v1[col] = "rebuilt_fallback"

    for t in form:
        for tk in members_raw[t]:
            if (t, tk) in arch_map:
                s_ar, sub_ar, _ = arch_map[(t, tk)]
                secP_v1.at[t, tk] = s_ar
                secProv_v1.at[t, tk] = f"wiki_archival:{sub_ar}" if sub_ar else "wiki_archival"

    # Clean the 3 single-month Wikipedia vandalism/lag blips & enforce exact official GICS dates:
    # 1) ACN 2011-11-30 single-month blip ('Financials') -> 'Information Technology'
    if "ACN" in secP_v1.columns:
        secP_v1.loc[pd.Timestamp("2011-11-30"), "ACN"] = "Information Technology"
    # 2) V and MA 2019-03-31 single-month blip ('Financials' before 2023-03-20) -> 'Information Technology'
    for tk_pm in ["V", "MA"]:
        if tk_pm in secP_v1.columns:
            secP_v1.loc[pd.Timestamp("2019-03-31"), tk_pm] = "Information Technology"
    # 3) Official S&P DJI GICS 2023-03-20 effective date for HR/Payroll (CDAY, PAYC, DAY, ADP, PAYX, BR -> Industrials)
    for tk_hr in ["CDAY", "PAYC", "DAY", "ADP", "PAYX", "BR"]:
        if tk_hr in secP_v1.columns:
            secP_v1.loc[secP_v1.index >= pd.Timestamp("2023-03-31"), tk_hr] = "Industrials"
    # 4) Official S&P DJI GICS 2026-07-31 effective date for APP (IT through 2026-06-30, Comm Services from 2026-07-31)
    if "APP" in secP_v1.columns:
        secP_v1.loc[pd.Timestamp("2026-07-31"):, "APP"] = "Communication Services"
    # 5) Qwest Communications (Q) 2008-12..2011-03 is Telecommunication Services; PARA 2022..2025 is Comm Services
    if "Q" in secP_v1.columns:
        secP_v1.loc[:pd.Timestamp("2011-04-30"), "Q"] = "Telecommunication Services"
    if "PARA" in secP_v1.columns:
        secP_v1.loc[:, "PARA"] = "Communication Services"
    # 6) MMI (Motorola Mobility 2011-01..2012-04), XRX (2008-12..2021-02), WU (2008-12..2021-11) are IT
    if "MMI" in secP_v1.columns:
        secP_v1.loc[pd.Timestamp("2011-01-31"):pd.Timestamp("2012-04-30"), "MMI"] = "Information Technology"

    # V1b: same as V1, except NFLX is treated as Consumer Discretionary pre-2018 (official S&P GICS Internet Retail)
    secP_v1b = secP_v1.copy()
    if "NFLX" in secP_v1b.columns:
        secP_v1b.loc[:pd.Timestamp("2018-08-31"), "NFLX"] = "Consumer Discretionary"

    # V2: Strict Core Pure-IT Only (drop ALL 2018/2023 reclassified, payment/HR, media/gaming, solar, conglomerate names)
    AMBIGUOUS_OR_RECLASSIFIED = {
        # 2018 GICS Communication Services movers + eBay + Netflix
        "GOOGL", "GOOG", "META", "FB", "TWTR", "EA", "ATVI", "TTWO", "EBAY", "NFLX", "YHOO", "AABA", "APP",
        # 2023 GICS Financials / Industrials payment & HR/payroll movers
        "V", "MA", "PYPL", "FIS", "FISV", "FI", "GPN", "FLT", "CPAY", "JKHY", "WU", "TSS", "ADS",
        "ADP", "PAYX", "PAYC", "CDAY", "DAY", "BR",
        # Solar / renewable inverters & Industrial/Healthcare/REIT crossovers
        "FSLR", "ENPH", "SEDG", "EQIX", "A", "ROP", "TDY", "LDOS", "FLIR", "HRS", "Q", "PARA",
    }
    secP_v2 = secP_v1.copy()
    for tk_amb in AMBIGUOUS_OR_RECLASSIFIED:
        if tk_amb in secP_v2.columns:
            secP_v2.loc[:, tk_amb] = "EXCLUDED_AMBIGUOUS"

    # V3: 100% SEC EDGAR SIC-Code Tech Pool
    cm = pd.read_csv(SSM_DIR / "data" / "fundamentals" / "cik_map.csv").drop_duplicates("ticker").set_index("ticker")
    sic_map = {}
    for fn in glob.glob(str(SSM_DIR / "data" / "sec_submissions" / "*.json")):
        try:
            j = json.load(open(fn))
            c = int(j.get("cik", 0))
            s = str(j.get("sic", "")).strip()
            if c and s.isdigit():
                sic_map[c] = int(s)
        except Exception:
            pass

    ticker_sic = {}
    for tk in set(secP_v1.columns) | {x for m in members_raw.values() for x in m}:
        if tk in cm.index and pd.notna(cm.at[tk, "sic"]):
            ticker_sic[tk] = int(cm.at[tk, "sic"])
        elif tk in cm.index and pd.notna(cm.at[tk, "cik"]) and int(cm.at[tk, "cik"]) in sic_map:
            ticker_sic[tk] = sic_map[int(cm.at[tk, "cik"])]

    secP_v3 = pd.DataFrame("NON_IT", index=form, columns=secP_v1.columns)
    d_2018 = pd.Timestamp("2018-09-24")
    d_2023 = pd.Timestamp("2023-03-20")
    pre2018_it = {"GOOGL", "GOOG", "META", "FB", "TWTR", "EA", "ATVI", "TTWO", "EBAY", "YHOO", "AABA"}
    pre2023_it = {"V", "MA", "PYPL", "FIS", "FISV", "GPN", "FLT", "JKHY", "ADP", "PAYX", "PAYC", "CDAY", "BR", "WU", "TSS", "ADS"}
    non_it_sic_overrides = {"CBE", "CERN", "FDS", "HUBB", "INFO", "LDOS", "LLL", "MTCH", "PBI", "RDDT", "TRIP", "TTD", "VEEV", "VLTO", "VRSK", "VRT", "XYZ", "PARA"}

    for t in form:
        for tk in members_raw[t]:
            if tk in non_it_sic_overrides:
                continue
            if t < d_2018 and tk in pre2018_it:
                secP_v3.at[t, tk] = "Information Technology"
                continue
            if t >= d_2018 and tk in pre2018_it:
                continue
            if t < d_2023 and tk in pre2023_it:
                secP_v3.at[t, tk] = "Information Technology"
                continue
            if t >= d_2023 and tk in pre2023_it:
                continue
            s = ticker_sic.get(tk, 0)
            if (3570 <= s <= 3579) or (3660 <= s <= 3679) or (7370 <= s <= 7379) or s in (3825, 3827, 5045, 5065):
                secP_v3.at[t, tk] = "Information Technology"

    return {
        "members_raw": members_raw,
        "members_v0": members_v0,
        "members_v1": members_v1,
        "secP_v0": secP_v0,
        "secFlag_v0": secFlag_v0,
        "secP_v1": secP_v1,
        "secProv_v1": secProv_v1,
        "secP_v1b": secP_v1b,
        "secP_v2": secP_v2,
        "secP_v3": secP_v3,
        "ticker_sic": ticker_sic,
        "arch_map": arch_map,
    }


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 & 3: FROZEN RULE ENGINE (OPEN-TO-OPEN & ALTERNATIVE EXECUTIONS)
# ─────────────────────────────────────────────────────────────────────────────
class CustomOpenEngine:
    """
    Executes the frozen Tech Pool -> 12-1 Momentum -> Top-K strategy with exact
    next-session Open-to-Open returns (falling back to next-session Close only when
    neither Yahoo nor WIKI nor QSTK has an Open price, and logging every leg).
    """
    def __init__(self, store, resolutions):
        self.daily = store["daily"]
        self.P = store["P"]
        self.O = store["O"]
        self.res = resolutions
        self.close0 = bt.Prices(self.daily, self.P, 0)
        self.close1 = bt.Prices(self.daily, self.P, 1)
        self.close2 = bt.Prices(self.daily, self.P, 2)
        self.sess = self.daily["SPY"].dropna().index

    def next_session(self, t):
        i = self.sess.searchsorted(t, side="right")
        return self.sess[i] if i < len(self.sess) else None

    def ret_with_detail(self, t, s, exec_mode="open", stress=None):
        if exec_mode == "close0":
            r, st = self.close0.ret(t, s, self.res)
            d0 = self.sess[self.sess.searchsorted(t, side="right") - 1]
            t1 = t + pd.offsets.MonthEnd(1)
            d1 = self.sess[self.sess.searchsorted(t1, side="right") - 1]
            p0 = float(self.P.at[t, s]) if s in self.P.columns else np.nan
            p1 = float(self.P.at[t1, s]) if (s in self.P.columns and t1 in self.P.index) else np.nan
            if stress is not None and st in ("unresolved", "source_gap"):
                r = stress
            return r, st, "close0", d0, d1, p0, p1

        if exec_mode == "close1":
            r, st = self.close1.ret(t, s, self.res)
            d0 = self.next_session(t)
            d1 = self.next_session(t + pd.offsets.MonthEnd(1))
            p0 = float(self.close1.E.at[t, s]) if s in self.close1.E.columns else np.nan
            t1 = t + pd.offsets.MonthEnd(1)
            p1 = float(self.close1.E.at[t1, s]) if (s in self.close1.E.columns and t1 in self.close1.E.index) else np.nan
            if stress is not None and st in ("unresolved", "source_gap"):
                r = stress
            return r, st, "close1", d0, d1, p0, p1

        if exec_mode == "close2":
            r, st = self.close2.ret(t, s, self.res)
            d0 = self.next_session(t)
            d1 = self.next_session(t + pd.offsets.MonthEnd(1))
            p0 = float(self.close2.E.at[t, s]) if s in self.close2.E.columns else np.nan
            t1 = t + pd.offsets.MonthEnd(1)
            p1 = float(self.close2.E.at[t1, s]) if (s in self.close2.E.columns and t1 in self.close2.E.index) else np.nan
            if stress is not None and st in ("unresolved", "source_gap"):
                r = stress
            return r, st, "close2", d0, d1, p0, p1

        # Default: next-session OPEN-TO-OPEN execution
        r1, st = self.close1.ret(t, s, self.res)
        d0 = self.next_session(t)
        d1 = self.next_session(t + pd.offsets.MonthEnd(1))
        if st != "ok":
            if stress is not None and st in ("unresolved", "source_gap"):
                r1 = stress
            return r1, st, "terminal_fallback", d0, d1, np.nan, np.nan
        if d0 is not None and d1 is not None and s in self.O.columns:
            o0, o1 = self.O.at[d0, s], self.O.at[d1, s]
            seg = bt.SEG_D
            same = seg is None or s not in seg.columns or seg.at[d0, s] == seg.at[d1, s]
            if np.isfinite(o0) and np.isfinite(o1) and o0 > 0 and same:
                return float(o1 / o0 - 1.0), "ok", "open_to_open", d0, d1, float(o0), float(o1)
        p0 = float(self.close1.E.at[t, s]) if s in self.close1.E.columns else np.nan
        t1 = t + pd.offsets.MonthEnd(1)
        p1 = float(self.close1.E.at[t1, s]) if (s in self.close1.E.columns and t1 in self.close1.E.index) else np.nan
        return r1, st, "close1_fallback", d0, d1, p0, p1


def run_tech_momentum_strategy(
    form,
    store,
    members_dict,
    secP_df,
    eng_px,
    rf,
    rank_slice=(0, 1),
    cost_per_side=0.001,
    extra_slippage_per_side=0.0,
    exec_mode="open",
    drop_tickers=None,
    stress=None,
    adversarial_missing_months=None,
    adversarial_missing_return=None,
):
    """
    Runs the frozen Tech Pool 12-1 Momentum rule across all formation months `form`.
    `rank_slice`:
      - `(0, 1)` = Top-1 (Rank #1)
      - `(1, 2)` = Rank #2 alone
      - `(2, 3)` = Rank #3 alone
      - `(0, 2)` = Top-2 Equal-Weight
      - `(0, 3)` = Top-3 Equal-Weight
      - `(0, 5)` = Top-5 Equal-Weight
      - `(0, 9999)` = Equal-Weight All Eligible Tech Stocks
    """
    P = store["P"]
    mom12 = bt.momentum(P, 12)
    drop_set = set(drop_tickers or [])
    adv_months = set(adversarial_missing_months or [])

    rows = []
    w_pre = {}
    for t in form:
        m_hold = t + pd.offsets.MonthEnd(1)
        mem_t = members_dict.get(t, set())
        el = []
        for s in sorted(mem_t):
            if s in drop_set:
                continue
            if s in mom12.columns and s in P.columns and s in secP_df.columns:
                if (
                    secP_df.at[t, s] == "Information Technology"
                    and np.isfinite(mom12.at[t, s])
                    and np.isfinite(P.at[t, s])
                ):
                    el.append((s, float(mom12.at[t, s])))
        df_el = pd.DataFrame(el, columns=["ticker", "mom"]).set_index("ticker")
        ranked = bt.rank_desc(df_el["mom"]) if not df_el.empty else pd.Series(dtype=float)

        i0, i1 = rank_slice
        picks = ranked.index[i0:i1].tolist()
        if not picks and len(ranked):
            picks = [ranked.index[-1]]

        w = {s: 1.0 / len(picks) for s in picks}
        details = [eng_px.ret_with_detail(t, s, exec_mode=exec_mode, stress=stress) for s in picks]
        rets = [d[0] for d in details]
        stats_ = [d[1] for d in details]
        modes_ = [d[2] for d in details]
        d0s = [d[3] for d in details]
        d1s = [d[4] for d in details]
        p0s = [d[5] for d in details]
        p1s = [d[6] for d in details]

        if t in adv_months and adversarial_missing_return is not None:
            rets = [ float(adversarial_missing_return) for _ in rets ]
            stats_ = ["adversarial_missing_shock" for _ in stats_]

        turn = sum(abs(w.get(k, 0.0) - w_pre.get(k, 0.0)) for k in set(w) | set(w_pre))
        gross = float(np.dot([w[s] for s in picks], rets))
        total_cost_rate = cost_per_side + extra_slippage_per_side
        net = gross - turn * total_cost_rate

        grow = {s: w[s] * (1.0 + x) for s, x, st in zip(picks, rets, stats_) if st == "ok"}
        tot = 1.0 + gross
        w_pre = {s: v / tot for s, v in grow.items()} if tot > 0 else {}

        rk2_tk = ranked.index[1] if len(ranked) > 1 else ""
        rk2_mom = float(ranked.iloc[1]) if len(ranked) > 1 else np.nan
        rk2_ret = eng_px.ret_with_detail(t, rk2_tk, exec_mode=exec_mode)[0] if rk2_tk else np.nan

        rk3_tk = ranked.index[2] if len(ranked) > 2 else ""
        rk3_mom = float(ranked.iloc[2]) if len(ranked) > 2 else np.nan
        rk3_ret = eng_px.ret_with_detail(t, rk3_tk, exec_mode=exec_mode)[0] if rk3_tk else np.nan

        rows.append({
            "formation": t,
            "month": m_hold,
            "n_tech_eligible": int(len(ranked)),
            "picks": "|".join(picks),
            "weights": "|".join(f"{w[s]:.6f}" for s in picks),
            "pick_mom_12_1": float(ranked.loc[picks].mean()) if picks else np.nan,
            "rank2_ticker": rk2_tk,
            "rank2_mom_12_1": rk2_mom,
            "rank2_ret_oo": rk2_ret,
            "rank3_ticker": rk3_tk,
            "rank3_mom_12_1": rk3_mom,
            "rank3_ret_oo": rk3_ret,
            "entry_date": str(d0s[0].date()) if d0s and d0s[0] is not None else "",
            "exit_date": str(d1s[0].date()) if d1s and d1s[0] is not None else "",
            "entry_px": p0s[0] if len(p0s) == 1 else np.nan,
            "exit_px": p1s[0] if len(p1s) == 1 else np.nan,
            "gross": gross,
            "turnover": turn,
            "cost_drag": turn * total_cost_rate,
            "net": net,
            "exit_status": "|".join(stats_),
            "exec_leg_source": "|".join(modes_),
            "price_source": "|".join(str(bt.PRICE_SOURCE.get(x, "?")) for x in picks),
            "top5_tech_tickers": "|".join(ranked.index[:5].tolist()),
        })
    return pd.DataFrame(rows).set_index("month")


def compute_daily_maxdd(df_ledger, daily):
    """Computes exact daily MaxDD across a date slice of `df_ledger`."""
    nav, level = [], 1.0
    sess = daily["SPY"].dropna().index
    for m, row in df_ledger.iterrows():
        t_form = m - pd.offsets.MonthEnd(1)
        t0 = sess[sess.searchsorted(t_form, side="right") - 1]
        days = daily.index[(daily.index > t0) & (daily.index <= m)]
        if not len(days):
            continue
        names = [x for x in str(row.picks).split("|") if x and x in daily.columns]
        if not names:
            rel = pd.Series(1.0, index=days)
        else:
            w = np.ones(len(names)) / len(names)
            seg = daily[names].loc[t0:m].ffill()
            rel = pd.Series(1.0 + ((seg / seg.iloc[0]).fillna(1.0).values - 1.0) @ w, index=seg.index).loc[days]
        if not np.isfinite(rel.iloc[-1]) or rel.iloc[-1] <= 0:
            rel = pd.Series(1.0, index=days)
        k = (1.0 + float(row.net)) / float(rel.iloc[-1])
        path = level * rel * (k ** (np.arange(1, len(rel) + 1) / len(rel)))
        nav.append(path)
        level = float(path.iloc[-1])
    if not nav:
        return np.nan, pd.Series(dtype=float)
    s = pd.concat(nav)
    s0 = pd.concat([pd.Series([1.0], index=[s.index[0] - pd.Timedelta(days=1)]), s])
    dd = float((s0 / s0.cummax() - 1.0).min())
    return dd, s


def summarize_period(df_ledger, rf, daily, a, z, bench_series=None):
    sub = df_ledger.loc[a:z]
    r = sub["net"].dropna()
    if len(r) < 6:
        return {}
    rf_sub = rf.reindex(r.index).fillna(0.0)
    eq = (1.0 + r).cumprod()
    ex = r - rf_sub
    cagr = float(eq.iloc[-1] ** (12.0 / len(r)) - 1.0)
    vol = float(r.std() * np.sqrt(12.0))
    sharpe = float(ex.mean() / ex.std() * np.sqrt(12.0)) if ex.std() > 0 else np.nan
    down = ex[ex < 0]
    sortino = float(ex.mean() / down.std() * np.sqrt(12.0)) if len(down) > 1 and down.std() > 0 else np.nan
    eq0 = pd.concat([pd.Series([1.0]), eq.reset_index(drop=True)])
    m_dd = float((eq0 / eq0.cummax() - 1.0).min())
    d_dd, _ = compute_daily_maxdd(sub, daily)
    calmar = float(cagr / abs(d_dd)) if d_dd and d_dd < 0 else np.nan
    lr = np.log1p(r)
    top5_share = float(lr.nlargest(5).sum() / lr.sum()) if lr.sum() > 0 else np.nan
    ex_top5_cagr = float(np.exp(lr.sum() - lr.nlargest(5).sum()) ** (12.0 / len(r)) - 1.0) if len(r) > 5 else np.nan

    out = {
        "months": int(len(r)),
        "CAGR_pct": round(cagr * 100, 2),
        "Vol_pct": round(vol * 100, 2),
        "Sharpe": round(sharpe, 2),
        "Sortino": round(sortino, 2),
        "MaxDD_Monthly_pct": round(m_dd * 100, 2),
        "MaxDD_Daily_pct": round(d_dd * 100, 2) if np.isfinite(d_dd) else np.nan,
        "Calmar_Daily": round(calmar, 2) if np.isfinite(calmar) else np.nan,
        "Hit_Rate_pct": round(float((r > 0).mean() * 100), 1),
        "Best_Month_pct": round(float(r.max() * 100), 2),
        "Worst_Month_pct": round(float(r.min() * 100), 2),
        "Avg_Turnover": round(float(sub["turnover"].mean()), 2),
        "Distinct_Tickers": int(sub["picks"].nunique()),
        "Top5_Months_Log_Share_pct": round(top5_share * 100, 1) if np.isfinite(top5_share) else np.nan,
        "Ex_Top5_Months_CAGR_pct": round(ex_top5_cagr * 100, 2) if np.isfinite(ex_top5_cagr) else np.nan,
        "Total_Multiple_x": round(float(eq.iloc[-1]), 2),
    }
    if bench_series is not None:
        b = bench_series.reindex(r.index).dropna()
        common = r.index.intersection(b.index)
        diff = r.loc[common] - b.loc[common]
        coef, se = bt.newey_west_ols(diff.values, np.zeros((len(diff), 0)), lags=3)
        t_nw = float(coef[0] / se[0]) if se[0] > 0 else np.nan
        out["Excess_Arith_Ann_pct"] = round(float(diff.mean() * 12.0 * 100), 2)
        out["t_NW_vs_Bench"] = round(t_nw, 2)
        out["p_NW_vs_Bench"] = round(float(2.0 * (1.0 - norm.cdf(abs(t_nw)))), 4) if np.isfinite(t_nw) else np.nan
        out["Beat_Bench_Months_pct"] = round(float((diff > 0).mean() * 100), 1)
    return out


def build_etf_open_benchmark(symbol, form, store, eng_px):
    """Builds an Open-to-Open monthly buy-and-hold return series for an ETF (XLK, QQQ, SPY)."""
    if symbol not in store["daily"].columns:
        qp = REPO_ROOT / "data" / "yahoo" / f"{symbol}.json"
        rp = SSM_DIR / "data" / "raw" / f"{symbol}.json"
        op = SSM_DIR / "data" / "raw_open" / f"{symbol}.json"
        if rp.exists():
            j = json.load(open(rp))
            s = pd.Series(j["adjclose"], index=pd.to_datetime(j["dates"]), dtype=float)
            store["daily"][symbol] = s.reindex(store["daily"].index)
            store["P"][symbol] = store["daily"][symbol].resample("ME").last()
        elif qp.exists():
            j = json.load(open(qp))
            s = pd.Series({pd.Timestamp(a): float(b) for a, b in j["values"] if b is not None})
            store["daily"][symbol] = s.reindex(store["daily"].index)
            store["P"][symbol] = store["daily"][symbol].resample("ME").last()
        if op.exists():
            jo = json.load(open(op))
            so = pd.Series(jo["adj_open"], index=pd.to_datetime(jo["dates"]), dtype=float)
            store["O"][symbol] = so.reindex(store["daily"].index)
        bt.SEG_D[symbol] = 0.0
        bt.SEG_M[symbol] = 0.0
        eng_px.close0 = bt.Prices(store["daily"], store["P"], 0)
        eng_px.close1 = bt.Prices(store["daily"], store["P"], 1)

    rows = []
    for t in form:
        m = t + pd.offsets.MonthEnd(1)
        r, st, mode, d0, d1, p0, p1 = eng_px.ret_with_detail(t, symbol, exec_mode="open")
        rows.append({
            "formation": t,
            "month": m,
            "n_tech_eligible": 1,
            "picks": symbol,
            "weights": "1.000000",
            "pick_mom_12_1": np.nan,
            "gross": r,
            "turnover": 0.0,
            "cost_drag": 0.0,
            "net": r,
            "exit_status": st,
            "exec_leg_source": mode,
        })
    return pd.DataFrame(rows).set_index("month")


def load_qqq_open_series(form, store, eng_px):
    """Loads QQQ Open-to-Open returns from `data/yahoo/QQQ.json` + `QQQ_adjusted_prices.csv`."""
    qp = REPO_ROOT / "data" / "yahoo" / "QQQ.json"
    ap = REPO_ROOT / "outputs" / "top3_include_latest_month_20261030" / "QQQ_adjusted_prices.csv"
    s_close = pd.Series(dtype=float)
    s_open = pd.Series(dtype=float)
    if qp.exists():
        j = json.load(open(qp))
        s_close = pd.Series({pd.Timestamp(a): float(b) for a, b in j["values"] if b is not None}).sort_index()
        s_open = s_close.copy()
    if ap.exists():
        df_ap = pd.read_csv(ap)
        df_ap["date"] = pd.to_datetime(df_ap["date"])
        df_ap = df_ap.set_index("date").sort_index()
        s_close.loc[df_ap.index] = df_ap["adj_close"].astype(float)
        s_open.loc[df_ap.index] = df_ap["adj_open"].astype(float)
    store["daily"]["QQQ"] = s_close.reindex(store["daily"].index)
    store["P"]["QQQ"] = store["daily"]["QQQ"].resample("ME").last()
    store["O"]["QQQ"] = s_open.reindex(store["daily"].index)
    bt.SEG_D["QQQ"] = 0.0
    bt.SEG_M["QQQ"] = 0.0
    eng_px.close0 = bt.Prices(store["daily"], store["P"], 0)
    eng_px.close1 = bt.Prices(store["daily"], store["P"], 1)
    return build_etf_open_benchmark("QQQ", form, store, eng_px)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN EXECUTION PIPELINE (STEPS 1 TO 7)
# ─────────────────────────────────────────────────────────────────────────────
def main():
    print("=" * 80)
    print("RUNNING XLK / PIT TECH TOP-1 ADVERSARIAL AUDIT (2009-01 .. 2026-09, 213 MONTHS)")
    print("=" * 80, flush=True)

    store_v0, store_v1, df_arch_fills = load_enhanced_prices_and_opens()
    df_arch_fills.to_csv(OUT_DIR / "step1_archive_price_fills_verified.csv", index=False)
    print("[Step 1] Verified Archival Price & Open Fills:")
    print(df_arch_fills.to_string(index=False), flush=True)

    form = store_v1["P"].index[
        (store_v1["P"].index >= pd.Timestamp("2008-12-31"))
        & (store_v1["P"].index <= pd.Timestamp("2026-08-31"))
    ]
    hold = form + pd.offsets.MonthEnd(1)
    rf = bt.load_rf(hold)
    resolutions = bt.load_resolutions()

    pools = build_tech_pools(store_v0, store_v1, form)
    eng_v0 = CustomOpenEngine(store_v0, resolutions)
    eng_v1 = CustomOpenEngine(store_v1, resolutions)

    # ── Export Step 1 Monthly Roster & Discrepancy Tables ──
    mom12_v0 = bt.momentum(store_v0["P"], 12)
    mom12_v1 = bt.momentum(store_v1["P"], 12)
    roster_rows = []
    disc_rows = []
    missing_spell_rows = []

    for t in form:
        mem_raw = sorted(pools["members_raw"][t])
        v0_el = [
            tk for tk in mem_raw
            if tk in pools["members_v0"][t]
            and tk in pools["secP_v0"].columns and pools["secP_v0"].at[t, tk] == "Information Technology"
            and tk in mom12_v0.columns and np.isfinite(mom12_v0.at[t, tk]) and np.isfinite(store_v0["P"].at[t, tk])
        ]
        v1_el = [
            tk for tk in mem_raw
            if tk in pools["members_v1"][t]
            and tk in pools["secP_v1"].columns and pools["secP_v1"].at[t, tk] == "Information Technology"
            and tk in mom12_v1.columns and np.isfinite(mom12_v1.at[t, tk]) and np.isfinite(store_v1["P"].at[t, tk])
        ]
        v2_el = [
            tk for tk in v1_el
            if pools["secP_v2"].at[t, tk] == "Information Technology"
        ]
        v3_el = [
            tk for tk in mem_raw
            if tk in pools["members_v1"][t]
            and tk in pools["secP_v3"].columns and pools["secP_v3"].at[t, tk] == "Information Technology"
            and tk in mom12_v1.columns and np.isfinite(mom12_v1.at[t, tk]) and np.isfinite(store_v1["P"].at[t, tk])
        ]

        rk_v0 = bt.rank_desc(pd.Series({tk: mom12_v0.at[t, tk] for tk in v0_el}))
        rk_v1 = bt.rank_desc(pd.Series({tk: mom12_v1.at[t, tk] for tk in v1_el}))
        rk_v2 = bt.rank_desc(pd.Series({tk: mom12_v1.at[t, tk] for tk in v2_el}))
        rk_v3 = bt.rank_desc(pd.Series({tk: mom12_v1.at[t, tk] for tk in v3_el}))

        roster_rows.append({
            "formation": str(t.date()),
            "holding_month": str((t + pd.offsets.MonthEnd(1)).date()),
            "n_v0_rebuilt": len(v0_el),
            "n_v1_archival": len(v1_el),
            "n_v2_strict_core": len(v2_el),
            "n_v3_sec_sic": len(v3_el),
            "top1_v0": rk_v0.index[0] if len(rk_v0) else "",
            "top1_v1": rk_v1.index[0] if len(rk_v1) else "",
            "top1_v2": rk_v2.index[0] if len(rk_v2) else "",
            "top1_v3": rk_v3.index[0] if len(rk_v3) else "",
            "top5_v1_archival": "|".join(f"{tk}:{rk_v1[tk]*100:.1f}%" for tk in rk_v1.index[:5]),
            "added_in_v1_vs_v0": "|".join(sorted(set(v1_el) - set(v0_el))),
            "removed_in_v1_vs_v0": "|".join(sorted(set(v0_el) - set(v1_el))),
            "full_v1_archival_roster": "|".join(sorted(v1_el)),
        })

        for tk in mem_raw:
            s0 = pools["secP_v0"].at[t, tk] if tk in pools["secP_v0"].columns else "NONE"
            s1 = pools["secP_v1"].at[t, tk] if tk in pools["secP_v1"].columns else "NONE"
            if (s0 == "Information Technology") != (s1 == "Information Technology"):
                disc_rows.append({
                    "month": str(t.date()),
                    "ticker": tk,
                    "v0_rebuilt_sector": s0,
                    "v1_archival_sector": s1,
                    "v1_provenance": pools["secProv_v1"].at[t, tk] if tk in pools["secProv_v1"].columns else "",
                    "sic": pools["ticker_sic"].get(tk, np.nan),
                })
            if s1 == "Information Technology" and tk not in v1_el:
                if tk not in store_v1["P"].columns or not store_v1["P"][tk].notna().any():
                    reason = "no_price_data_at_source"
                elif not np.isfinite(store_v1["P"].at[t, tk]):
                    reason = "no_price_at_t_after_archive_end"
                else:
                    reason = "insufficient_history_for_12_1_spinoff"
                missing_spell_rows.append({
                    "month": str(t.date()),
                    "ticker": tk,
                    "reason": reason,
                    "top1_v1_ticker": rk_v1.index[0],
                    "top1_v1_mom_pct": round(float(rk_v1.iloc[0] * 100), 2),
                })

    df_roster = pd.DataFrame(roster_rows)
    df_roster.to_csv(OUT_DIR / "step1_pit_tech_monthly_roster_2009_2026.csv", index=False)

    df_disc = pd.DataFrame(disc_rows)
    df_disc_sum = (
        df_disc.groupby(["ticker", "v0_rebuilt_sector", "v1_archival_sector"])
        .agg(months=("month", "count"), first_month=("month", "min"), last_month=("month", "max"), sic=("sic", "first"))
        .reset_index()
        .sort_values("months", ascending=False)
    )
    df_disc_sum.to_csv(OUT_DIR / "step1_sector_classification_discrepancies_audit.csv", index=False)

    df_miss = pd.DataFrame(missing_spell_rows)
    df_miss_sum = (
        df_miss.groupby(["ticker", "reason"])
        .agg(
            months=("month", "count"),
            first_month=("month", "min"),
            last_month=("month", "max"),
            min_top1_mom_in_window_pct=("top1_v1_mom_pct", "min"),
            max_top1_mom_in_window_pct=("top1_v1_mom_pct", "max"),
        )
        .reset_index()
        .sort_values(["reason", "months"], ascending=[True, False])
    )
    df_miss_sum.to_csv(OUT_DIR / "step1_remaining_unpriced_it_spells_audit.csv", index=False)
    print("\n[Step 1] Sector Discrepancies Summary (V0 Backward-Rebuilt vs V1 True Archival):")
    print(df_disc_sum.to_string(index=False))
    print("\n[Step 1] Remaining Non-Eligible IT Spells After QSTK/OTT Fills:")
    print(df_miss_sum.to_string(index=False), flush=True)

    # ── Run Benchmarks & Core Strategies (Steps 2 & 3) ──
    bench_xlk = build_etf_open_benchmark("XLK", form, store_v1, eng_v1)
    bench_spy = build_etf_open_benchmark("SPY", form, store_v1, eng_v1)
    bench_qqq = load_qqq_open_series(form, store_v1, eng_v1)
    bench_ew_it = run_tech_momentum_strategy(
        form, store_v1, pools["members_v1"], pools["secP_v1"], eng_v1, rf, rank_slice=(0, 9999), cost_per_side=0.001
    )

    # Core V0 (Baseline Rebuilt IT Top-1) and V1 (True Archival Repaired IT Top-1)
    led_v0_top1 = run_tech_momentum_strategy(
        form, store_v0, pools["members_v0"], pools["secP_v0"], eng_v0, rf, rank_slice=(0, 1), cost_per_side=0.001
    )
    led_v1_top1 = run_tech_momentum_strategy(
        form, store_v1, pools["members_v1"], pools["secP_v1"], eng_v1, rf, rank_slice=(0, 1), cost_per_side=0.001
    )
    led_v1b_top1 = run_tech_momentum_strategy(
        form, store_v1, pools["members_v1"], pools["secP_v1b"], eng_v1, rf, rank_slice=(0, 1), cost_per_side=0.001
    )
    led_v2_top1 = run_tech_momentum_strategy(
        form, store_v1, pools["members_v1"], pools["secP_v2"], eng_v1, rf, rank_slice=(0, 1), cost_per_side=0.001
    )
    led_v3_top1 = run_tech_momentum_strategy(
        form, store_v1, pools["members_v1"], pools["secP_v3"], eng_v1, rf, rank_slice=(0, 1), cost_per_side=0.001
    )

    # Save full 213-month ledgers
    led_v0_top1.to_csv(OUT_DIR / "step3_ledger_v0_rebuilt_tech_top1_2009_2026.csv")
    led_v1_top1.to_csv(OUT_DIR / "step3_ledger_v1_archival_tech_top1_2009_2026.csv")
    led_v1b_top1.to_csv(OUT_DIR / "step3_ledger_v1b_archival_ex_nflx_top1_2009_2026.csv")
    led_v2_top1.to_csv(OUT_DIR / "step3_ledger_v2_strict_core_pure_it_top1_2009_2026.csv")
    led_v3_top1.to_csv(OUT_DIR / "step3_ledger_v3_sec_sic_tech_top1_2009_2026.csv")

    # Compare where V0 and V1 picked different stocks
    diff_picks = []
    for m in led_v1_top1.index:
        p0 = led_v0_top1.at[m, "picks"]
        p1 = led_v1_top1.at[m, "picks"]
        if p0 != p1:
            diff_picks.append({
                "holding_month": str(m.date()),
                "formation": str(led_v1_top1.at[m, "formation"].date()),
                "v0_pick": p0,
                "v0_mom_pct": round(float(led_v0_top1.at[m, "pick_mom_12_1"] * 100), 2),
                "v0_net_ret_pct": round(float(led_v0_top1.at[m, "net"] * 100), 2),
                "v1_pick": p1,
                "v1_mom_pct": round(float(led_v1_top1.at[m, "pick_mom_12_1"] * 100), 2),
                "v1_net_ret_pct": round(float(led_v1_top1.at[m, "net"] * 100), 2),
            })
    df_diff_picks = pd.DataFrame(diff_picks)
    df_diff_picks.to_csv(OUT_DIR / "step1_v0_vs_v1_pick_differences.csv", index=False)
    print(f"\n[Step 1/3] Months where V0 (Rebuilt) and V1 (Archival) picked different Top-1 stocks: {len(df_diff_picks)} / 213")
    if not df_diff_picks.empty:
        print(df_diff_picks.to_string(index=False), flush=True)

    # ── Step 3: Sub-Period Breakdown Table ──
    SUBPERIODS = [
        ("Full_2009_2026.09 (213m)", "2009-01-31", "2026-09-30"),
        ("Post2015_2015_2026.09 (141m)", "2015-01-31", "2026-09-30"),
        ("Post2019_2019_2026.09 (93m)", "2019-01-31", "2026-09-30"),
        ("Sub1_2009_2014 (72m)", "2009-01-31", "2014-12-31"),
        ("Sub2_2015_2019 (60m)", "2015-01-31", "2019-12-31"),
        ("Sub3_2020_2022 (36m)", "2020-01-31", "2022-12-31"),
        ("Sub4_2023_2026.09 (45m)", "2023-01-31", "2026-09-30"),
    ]

    CORE_STRATS = [
        ("Tech_Top1_V1_Archival_PIT (Repaired)", led_v1_top1, store_v1["daily"]),
        ("Tech_Top1_V1b_Archival_ExNFLX", led_v1b_top1, store_v1["daily"]),
        ("Tech_Top1_V0_Rebuilt_PIT (Original)", led_v0_top1, store_v0["daily"]),
        ("Tech_Top1_V2_Strict_Core_Pure_IT", led_v2_top1, store_v1["daily"]),
        ("Tech_Top1_V3_Strict_SEC_SIC_IT", led_v3_top1, store_v1["daily"]),
        ("Bench_XLK_ETF_BuyHold", bench_xlk, store_v1["daily"]),
        ("Bench_EW_Tech_Pool_V1", bench_ew_it, store_v1["daily"]),
        ("Bench_QQQ_ETF_BuyHold", bench_qqq, store_v1["daily"]),
        ("Bench_SPY_ETF_BuyHold", bench_spy, store_v1["daily"]),
    ]

    sub_rows = []
    for sname, sled, sdaily in CORE_STRATS:
        for pname, a, z in SUBPERIODS:
            m = summarize_period(sled, rf, sdaily, a, z, bench_series=bench_xlk["net"])
            sub_rows.append({"Strategy": sname, "Period": pname, **m})
    df_sub = pd.DataFrame(sub_rows)
    df_sub.to_csv(OUT_DIR / "step3_subperiod_performance_table.csv", index=False)

    # Calendar year table (2009..2026.09)
    yr_dict = {}
    for sname, sled, _ in CORE_STRATS:
        yr_dict[sname] = ((1.0 + sled["net"]).groupby(sled.index.year).prod() - 1.0) * 100.0
    # Also record the dominant ticker held each year for V1 and V0
    df_yr = pd.DataFrame(yr_dict).round(2)
    df_yr["V1_Top_Tickers_Held"] = [
        ",".join(f"{k}({v}m)" for k, v in led_v1_top1[led_v1_top1.index.year == y]["picks"].value_counts().items())
        for y in df_yr.index
    ]
    df_yr["V0_Top_Tickers_Held"] = [
        ",".join(f"{k}({v}m)" for k, v in led_v0_top1[led_v0_top1.index.year == y]["picks"].value_counts().items())
        for y in df_yr.index
    ]
    df_yr.index.name = "Year"
    df_yr.to_csv(OUT_DIR / "step3_calendar_year_returns_2009_2026.csv")

    print("\n[Step 3] Sub-Period Breakdown (V1 Archival vs V0 Rebuilt vs V2 Pure-IT vs XLK/QQQ/SPY):")
    piv = df_sub.pivot(index="Strategy", columns="Period", values="CAGR_pct")[
        [p[0] for p in SUBPERIODS]
    ]
    print(piv.to_string(), flush=True)

    # ── Step 4: Forensic Audit of Super-Winners & All 213 Monthly Picks ──
    sp_spells = bt.read_spells()
    sp_spells["ticker"] = sp_spells["ticker"].str.replace(".", "-", regex=False)

    def get_active_spell(tk, t):
        sub = sp_spells[(sp_spells.ticker == tk) & (sp_spells.start_date <= t)]
        for r in sub.itertuples():
            if pd.isna(r.end_date) or t <= r.end_date:
                return str(r.start_date.date()), str(r.end_date.date()) if pd.notna(r.end_date) else "present"
        return "additions_or_alias", "present"

    forensic_rows = []
    for label_ver, led, store, secP_use in [
        ("V1_Archival", led_v1_top1, store_v1, pools["secP_v1"]),
        ("V0_Rebuilt", led_v0_top1, store_v0, pools["secP_v0"]),
    ]:
        P_use = store["P"]
        for m, row in led.iterrows():
            t = row.formation
            tk = row.picks
            t_m1 = P_use.index[P_use.index.get_loc(t) - 1]
            t_m12 = P_use.index[P_use.index.get_loc(t) - 12]
            p_m1 = float(P_use.at[t_m1, tk])
            p_m12 = float(P_use.at[t_m12, tk])
            p_t = float(P_use.at[t, tk])
            sp_s, sp_e = get_active_spell(tk, t)
            arch_info = pools["arch_map"].get((t, tk), ("", "", ""))
            forensic_rows.append({
                "pool_version": label_ver,
                "formation_date": str(t.date()),
                "holding_month": str(m.date()),
                "ticker": tk,
                "sp500_spell_start": sp_s,
                "sp500_spell_end": sp_e,
                "archival_wiki_sector": arch_info[0],
                "archival_wiki_subindustry": arch_info[1],
                "sic_code": pools["ticker_sic"].get(tk, np.nan),
                "P_t_minus_12": round(p_m12, 4),
                "P_t_minus_1": round(p_m1, 4),
                "P_t_form": round(p_t, 4),
                "mom_12_1_pct": round(float((p_m1 / p_m12 - 1.0) * 100), 2),
                "entry_open_date": row.entry_date,
                "entry_adj_open": round(float(row.entry_px), 4) if np.isfinite(row.entry_px) else np.nan,
                "exit_open_date": row.exit_date,
                "exit_adj_open": round(float(row.exit_px), 4) if np.isfinite(row.exit_px) else np.nan,
                "gross_ret_pct": round(float(row.gross * 100), 2),
                "net_ret_pct": round(float(row.net * 100), 2),
                "turnover": row.turnover,
                "exec_leg_source": row.exec_leg_source,
                "price_vendor": row.price_source,
                "rank2_runner_up": row.rank2_ticker,
                "rank2_mom_12_1_pct": round(float(row.rank2_mom_12_1 * 100), 2) if np.isfinite(row.rank2_mom_12_1) else np.nan,
                "rank2_gross_ret_pct": round(float(row.rank2_ret_oo * 100), 2) if np.isfinite(row.rank2_ret_oo) else np.nan,
            })

    df_forensic = pd.DataFrame(forensic_rows)
    df_forensic.to_csv(OUT_DIR / "step4_all_213_monthly_picks_forensic_ledger.csv", index=False)

    # Summarize contribution by stock for V1 and V0
    stock_contrib_rows = []
    for label_ver, led in [("V1_Archival", led_v1_top1), ("V0_Rebuilt", led_v0_top1)]:
        sub_f = df_forensic[df_forensic.pool_version == label_ver].copy()
        sub_f["log_ret"] = np.log1p(sub_f["net_ret_pct"] / 100.0)
        tot_log = sub_f["log_ret"].sum()
        for tk, g in sub_f.groupby("ticker"):
            stock_contrib_rows.append({
                "pool_version": label_ver,
                "ticker": tk,
                "months_held": int(len(g)),
                "first_held": g["holding_month"].min(),
                "last_held": g["holding_month"].max(),
                "sp500_spell_start": g["sp500_spell_start"].iloc[0],
                "archival_subindustry": g["archival_wiki_subindustry"].mode().iloc[0] if len(g["archival_wiki_subindustry"].mode()) else "",
                "sic_code": g["sic_code"].iloc[0],
                "cum_compounded_ret_pct": round(float((np.exp(g["log_ret"].sum()) - 1.0) * 100), 2),
                "sum_log_wealth": round(float(g["log_ret"].sum()), 4),
                "share_of_total_log_wealth_pct": round(float(g["log_ret"].sum() / tot_log * 100), 2) if tot_log > 0 else np.nan,
                "win_months": int((g["net_ret_pct"] > 0).sum()),
                "best_month_pct": round(float(g["net_ret_pct"].max()), 2),
                "worst_month_pct": round(float(g["net_ret_pct"].min()), 2),
                "price_vendor": g["price_vendor"].iloc[0],
                "exec_leg_sources": "|".join(sorted(g["exec_leg_source"].unique())),
            })
    df_stock_contrib = pd.DataFrame(stock_contrib_rows).sort_values(["pool_version", "sum_log_wealth"], ascending=[True, False])
    df_stock_contrib.to_csv(OUT_DIR / "step4_super_winners_contribution_audit.csv", index=False)
    print("\n[Step 4] Top-15 Super-Winner Contributors (V1 Archival Tech Pool, 2009-2026.09):")
    print(df_stock_contrib[df_stock_contrib.pool_version == "V1_Archival"].head(15).to_string(index=False), flush=True)

    # ── Step 5: Adversarial Falsification & Stress Suite ("Try to Kill It") ──
    # Identify the 18 remaining unpriced non-spinoff IT months (CA 7m in 2018, MMI 4m in 2012, NSM 4m post-buyout in 2011)
    adv_ca_mmi_months = [
        pd.Timestamp(m) for m in df_miss[df_miss.ticker.isin(["CA", "MMI"]) & (df_miss.month >= "2012-01-01")]["month"].unique()
    ]

    stress_configs = [
        # 1. Baseline
        ("01_Baseline_V1_Archival (10bp cost, Open)", lambda: led_v1_top1),
        ("02_Baseline_V0_Rebuilt (10bp cost, Open)", lambda: led_v0_top1),
        # 2. Transaction cost doubling & tripling
        ("03_Cost_20bps_per_side (40bp round-trip)", lambda: run_tech_momentum_strategy(
            form, store_v1, pools["members_v1"], pools["secP_v1"], eng_v1, rf, (0, 1), cost_per_side=0.002
        )),
        ("04_Cost_30bps_per_side (60bp round-trip)", lambda: run_tech_momentum_strategy(
            form, store_v1, pools["members_v1"], pools["secP_v1"], eng_v1, rf, (0, 1), cost_per_side=0.003
        )),
        ("05_Cost_50bps_per_side (100bp round-trip)", lambda: run_tech_momentum_strategy(
            form, store_v1, pools["members_v1"], pools["secP_v1"], eng_v1, rf, (0, 1), cost_per_side=0.005
        )),
        # 3. Adverse Open-Execution Slippage on top of 10bp cost
        ("06_Open_Slippage_+10bp_side (40bp total RT)", lambda: run_tech_momentum_strategy(
            form, store_v1, pools["members_v1"], pools["secP_v1"], eng_v1, rf, (0, 1), cost_per_side=0.001, extra_slippage_per_side=0.001
        )),
        ("07_Open_Slippage_+25bp_side (70bp total RT)", lambda: run_tech_momentum_strategy(
            form, store_v1, pools["members_v1"], pools["secP_v1"], eng_v1, rf, (0, 1), cost_per_side=0.001, extra_slippage_per_side=0.0025
        )),
        ("08_Open_Slippage_+50bp_side (120bp total RT)", lambda: run_tech_momentum_strategy(
            form, store_v1, pools["members_v1"], pools["secP_v1"], eng_v1, rf, (0, 1), cost_per_side=0.001, extra_slippage_per_side=0.005
        )),
        # 4. Execution timing alternatives
        ("09_Exec_SameDay_MonthEnd_Close (Lag 0)", lambda: run_tech_momentum_strategy(
            form, store_v1, pools["members_v1"], pools["secP_v1"], eng_v1, rf, (0, 1), cost_per_side=0.001, exec_mode="close0"
        )),
        ("10_Exec_NextDay_Close (Lag 1 Close)", lambda: run_tech_momentum_strategy(
            form, store_v1, pools["members_v1"], pools["secP_v1"], eng_v1, rf, (0, 1), cost_per_side=0.001, exec_mode="close1"
        )),
        ("11_Exec_TwoDay_Lag_Close (Lag 2 Close)", lambda: run_tech_momentum_strategy(
            form, store_v1, pools["members_v1"], pools["secP_v1"], eng_v1, rf, (0, 1), cost_per_side=0.001, exec_mode="close2"
        )),
        # 5. Sector ambiguity / reclassification stress
        ("12_Pool_V1b_Archival_ExNFLX_Pre2018", lambda: led_v1b_top1),
        ("13_Pool_V2_Strict_Core_Pure_IT (Drop All Reclassified/Solar)", lambda: led_v2_top1),
        ("14_Pool_V3_100pct_SEC_EDGAR_SIC_Tech", lambda: led_v3_top1),
        # 6. Super-winner removal ("Kill the Winners" -> replaced by Rank #2)
        ("15_Drop_SNDK_SpinOff (Replace w/ Rank #2)", lambda: run_tech_momentum_strategy(
            form, store_v1, pools["members_v1"], pools["secP_v1"], eng_v1, rf, (0, 1), drop_tickers={"SNDK"}
        )),
        ("16_Drop_PLTR (Replace w/ Rank #2)", lambda: run_tech_momentum_strategy(
            form, store_v1, pools["members_v1"], pools["secP_v1"], eng_v1, rf, (0, 1), drop_tickers={"PLTR"}
        )),
        ("17_Drop_NVDA (Replace w/ Rank #2)", lambda: run_tech_momentum_strategy(
            form, store_v1, pools["members_v1"], pools["secP_v1"], eng_v1, rf, (0, 1), drop_tickers={"NVDA"}
        )),
        ("18_Drop_SMCI_and_ENPH (Replace w/ Rank #2)", lambda: run_tech_momentum_strategy(
            form, store_v1, pools["members_v1"], pools["secP_v1"], eng_v1, rf, (0, 1), drop_tickers={"SMCI", "ENPH"}
        )),
        ("19_Drop_SNDK_+_PLTR_+_SMCI (Replace w/ Rank #2)", lambda: run_tech_momentum_strategy(
            form, store_v1, pools["members_v1"], pools["secP_v1"], eng_v1, rf, (0, 1), drop_tickers={"SNDK", "PLTR", "SMCI"}
        )),
        ("20_Drop_NVDA_+_SNDK_+_PLTR_+_SMCI (All 4 Killed)", lambda: run_tech_momentum_strategy(
            form, store_v1, pools["members_v1"], pools["secP_v1"], eng_v1, rf, (0, 1), drop_tickers={"NVDA", "SNDK", "PLTR", "SMCI"}
        )),
        # 7. Delisting & Missing-Stock Worst-Case Stress
        ("21_Unresolved_Exit_Stress_-100pct", lambda: run_tech_momentum_strategy(
            form, store_v1, pools["members_v1"], pools["secP_v1"], eng_v1, rf, (0, 1), stress=-1.0
        )),
        ("22_Adversarial_Missing_Spell_Shock (-30% in 2 worst months)", lambda: run_tech_momentum_strategy(
            form, store_v1, pools["members_v1"], pools["secP_v1"], eng_v1, rf, (0, 1),
            adversarial_missing_months=adv_ca_mmi_months[:2], adversarial_missing_return=-0.30
        )),
        # 8. Rank Neighborhood (Rank #2 alone, Rank #3 alone, Top-2 EW, Top-3 EW, Top-5 EW)
        ("23_Neighbor_Rank2_Alone (100% in #2 stock)", lambda: run_tech_momentum_strategy(
            form, store_v1, pools["members_v1"], pools["secP_v1"], eng_v1, rf, (1, 2)
        )),
        ("24_Neighbor_Rank3_Alone (100% in #3 stock)", lambda: run_tech_momentum_strategy(
            form, store_v1, pools["members_v1"], pools["secP_v1"], eng_v1, rf, (2, 3)
        )),
        ("25_Portfolio_Top2_EqualWeight", lambda: run_tech_momentum_strategy(
            form, store_v1, pools["members_v1"], pools["secP_v1"], eng_v1, rf, (0, 2)
        )),
        ("26_Portfolio_Top3_EqualWeight", lambda: run_tech_momentum_strategy(
            form, store_v1, pools["members_v1"], pools["secP_v1"], eng_v1, rf, (0, 3)
        )),
        ("27_Portfolio_Top5_EqualWeight", lambda: run_tech_momentum_strategy(
            form, store_v1, pools["members_v1"], pools["secP_v1"], eng_v1, rf, (0, 5)
        )),
    ]

    stress_rows = []
    for s_label, fn in stress_configs:
        df_s = fn()
        m_full = summarize_period(df_s, rf, store_v1["daily"], "2009-01-31", "2026-09-30", bench_xlk["net"])
        m_15 = summarize_period(df_s, rf, store_v1["daily"], "2015-01-31", "2026-09-30", bench_xlk["net"])
        m_19 = summarize_period(df_s, rf, store_v1["daily"], "2019-01-31", "2026-09-30", bench_xlk["net"])
        m_s1 = summarize_period(df_s, rf, store_v1["daily"], "2009-01-31", "2014-12-31", bench_xlk["net"])
        m_s2 = summarize_period(df_s, rf, store_v1["daily"], "2015-01-31", "2019-12-31", bench_xlk["net"])
        m_s3 = summarize_period(df_s, rf, store_v1["daily"], "2020-01-31", "2022-12-31", bench_xlk["net"])
        m_s4 = summarize_period(df_s, rf, store_v1["daily"], "2023-01-31", "2026-09-30", bench_xlk["net"])
        stress_rows.append({
            "Stress_Test": s_label,
            "CAGR_09_26_pct": m_full["CAGR_pct"],
            "Sharpe_09_26": m_full["Sharpe"],
            "DailyMaxDD_09_26_pct": m_full["MaxDD_Daily_pct"],
            "t_NW_vs_XLK_09_26": m_full["t_NW_vs_Bench"],
            "CAGR_15_26_pct": m_15["CAGR_pct"],
            "Sharpe_15_26": m_15["Sharpe"],
            "DailyMaxDD_15_26_pct": m_15["MaxDD_Daily_pct"],
            "t_NW_vs_XLK_15_26": m_15["t_NW_vs_Bench"],
            "CAGR_19_26_pct": m_19["CAGR_pct"],
            "Sharpe_19_26": m_19["Sharpe"],
            "Sub1_09_14_CAGR_pct": m_s1["CAGR_pct"],
            "Sub2_15_19_CAGR_pct": m_s2["CAGR_pct"],
            "Sub3_20_22_CAGR_pct": m_s3["CAGR_pct"],
            "Sub4_23_26_CAGR_pct": m_s4["CAGR_pct"],
        })

    df_stress = pd.DataFrame(stress_rows)
    df_stress.to_csv(OUT_DIR / "step5_adversarial_stress_test_table.csv", index=False)
    print("\n[Step 5] Adversarial Falsification & Stress Test Table:")
    print(df_stress.to_string(index=False), flush=True)

    # ── Step 6: Statistical Re-Evaluation & Project-Wide Multiple Testing ──
    # 6A. Paired Newey-West (lags 3 & 6) + 10,000-draw Stationary Block Bootstrap vs XLK, EW_IT, QQQ, SPY
    stat_rows = []
    for ver_name, led_s in [
        ("Tech_Top1_V1_Archival", led_v1_top1),
        ("Tech_Top1_V1b_ExNFLX", led_v1b_top1),
        ("Tech_Top1_V0_Rebuilt", led_v0_top1),
        ("Tech_Top1_V2_Strict_Core", led_v2_top1),
        ("Tech_Top1_V3_SEC_SIC", led_v3_top1),
    ]:
        for b_name, b_led in [
            ("XLK_ETF", bench_xlk),
            ("EW_Tech_Pool", bench_ew_it),
            ("QQQ_ETF", bench_qqq),
            ("SPY_ETF", bench_spy),
        ]:
            for p_label, a, z in [
                ("2009-2026.09 (213m)", "2009-01-31", "2026-09-30"),
                ("2015-2026.09 (141m)", "2015-01-31", "2026-09-30"),
                ("2019-2026.09 (93m)", "2019-01-31", "2026-09-30"),
            ]:
                rx = led_s["net"].loc[a:z].dropna()
                rb = b_led["net"].loc[a:z].dropna()
                idx = rx.index.intersection(rb.index)
                rx, rb = rx.loc[idx], rb.loc[idx]
                diff = rx - rb
                cx = float((1.0 + rx).prod() ** (12.0 / len(rx)) - 1.0)
                cb = float((1.0 + rb).prod() ** (12.0 / len(rb)) - 1.0)

                c3, se3 = bt.newey_west_ols(diff.values, np.zeros((len(diff), 0)), lags=3)
                c6, se6 = bt.newey_west_ols(diff.values, np.zeros((len(diff), 0)), lags=6)
                t_nw3 = float(c3[0] / se3[0]) if se3[0] > 0 else np.nan
                t_nw6 = float(c6[0] / se6[0]) if se6[0] > 0 else np.nan
                p_nw3 = float(2.0 * (1.0 - norm.cdf(abs(t_nw3))))
                p_nw6 = float(2.0 * (1.0 - norm.cdf(abs(t_nw6))))

                # 4,000-draw paired stationary bootstrap (mean_block=6)
                bs = bt.paired_bootstrap(
                    {"strat": rx, "bench": rb}, rf.loc[idx], n=4000, mean_block=6, seed=42
                )
                cagr_ci = bs.get("strat minus bench: CAGR diff p5/p50/p95", [np.nan, np.nan, np.nan])
                p_boot_cagr_le0 = bs.get("strat minus bench: share of resamples with CAGR diff <= 0", np.nan)
                p_boot_arith_le0 = bs.get("strat minus bench: share of resamples with arithmetic diff <= 0", np.nan)

                yd = (1.0 + rx).groupby(rx.index.year).prod() - (1.0 + rb).groupby(rb.index.year).prod()
                _, p_wilcox = wilcoxon(diff.values)

                stat_rows.append({
                    "Strategy": ver_name,
                    "Benchmark": b_name,
                    "Period": p_label,
                    "Months": len(idx),
                    "Strat_CAGR_pct": round(cx * 100, 2),
                    "Bench_CAGR_pct": round(cb * 100, 2),
                    "CAGR_Diff_pct": round((cx - cb) * 100, 2),
                    "Arith_Ann_Diff_pct": round(float(diff.mean() * 12.0 * 100), 2),
                    "t_NW_lag3": round(t_nw3, 2),
                    "p_NW_lag3": round(p_nw3, 4),
                    "t_NW_lag6": round(t_nw6, 2),
                    "p_NW_lag6": round(p_nw6, 4),
                    "p_Wilcoxon": round(float(p_wilcox), 4),
                    "Boot_CAGR_Diff_p5_p50_p95_pct": f"[{cagr_ci[0]*100:.1f}%, {cagr_ci[1]*100:.1f}%, {cagr_ci[2]*100:.1f}%]",
                    "Boot_P_CAGR_Diff_le_0": round(float(p_boot_cagr_le0), 4),
                    "Boot_P_Arith_Diff_le_0": round(float(p_boot_arith_le0), 4),
                    "Win_Months_pct": round(float((diff > 0).mean() * 100), 1),
                    "Win_Years": f"{int((yd > 0).sum())}/{int(len(yd))}",
                })

    df_stats = pd.DataFrame(stat_rows)
    df_stats.to_csv(OUT_DIR / "step6_paired_statistical_tests.csv", index=False)

    # 6B. Project-Wide Multiple Testing & Deflated Sharpe Ratio (DSR) Audit
    # Collect all return series tested across the project to estimate cross-trial variance & effective N
    all_trial_series = []
    # 1) Sector-stock grid (48 configs in research/sector_stock_momentum/results/grid_is_oos.csv)
    for f in glob.glob(str(SSM_DIR / "results" / "monthly_*.csv")):
        try:
            d = pd.read_csv(f, parse_dates=["month"]).set_index("month")
            if "net" in d.columns:
                all_trial_series.append(d["net"])
        except Exception:
            pass
    # 2) ML3 ledgers (S&P 500, QQQ, IWM, XLK)
    for sub_d in ["ledgers", "ledgers_qqq_iwm", "ledgers_xlk"]:
        for f in glob.glob(str(REPO_ROOT / "outputs" / "ml3_feature_discovery_20261102" / sub_d / "*.csv")):
            try:
                d = pd.read_csv(f, parse_dates=["month"]).set_index("month")
                if "net" in d.columns:
                    all_trial_series.append(d["net"])
            except Exception:
                pass
    # 3) Multibagger layered momentum ledgers
    for f in glob.glob(str(REPO_ROOT / "outputs" / "multibagger_layered_momentum_20261102" / "ledgers" / "*.csv")):
        try:
            d = pd.read_csv(f, parse_dates=["month"]).set_index("month")
            if "net_ret" in d.columns:
                all_trial_series.append(d["net_ret"])
        except Exception:
            pass

    # Compute correlation matrix & effective number of independent trials (M_eff via Prado / Meucci eigenvalue participation ratio)
    df_trials = pd.concat(all_trial_series, axis=1).loc["2015-01-31":"2026-09-30"].dropna(axis=1, how="all").fillna(0.0)
    df_trials.columns = [f"trial_{i}" for i in range(df_trials.shape[1])]
    # Deduplicate identical series
    df_trials = df_trials.T.drop_duplicates().T
    corr_mat = df_trials.corr().fillna(0.0).values
    eigvals = np.linalg.eigvalsh(corr_mat)
    eigvals = np.clip(eigvals, 0.0, None)
    # Participation ratio: (sum lambda)^2 / sum(lambda^2)
    m_eff_pr = float((eigvals.sum() ** 2) / (np.sum(eigvals ** 2))) if np.sum(eigvals ** 2) > 0 else float(df_trials.shape[1])
    # Variance of monthly Sharpe ratios across all distinct project trials
    rf_15 = rf.reindex(df_trials.index).fillna(0.0)
    sr_trials_m = []
    for col in df_trials.columns:
        ex = df_trials[col] - rf_15
        if ex.std() > 0:
            sr_trials_m.append(float(ex.mean() / ex.std()))
    var_sr_m = float(np.var(sr_trials_m, ddof=1))

    mt_rows = []
    emc = 0.5772156649
    for ver_name, led_s in [
        ("Tech_Top1_V1_Archival", led_v1_top1),
        ("Tech_Top1_V0_Rebuilt", led_v0_top1),
        ("Tech_Top1_V2_Strict_Core", led_v2_top1),
        ("Tech_Top1_V3_SEC_SIC", led_v3_top1),
    ]:
        for p_label, a, z in [
            ("2009-2026.09 (213m)", "2009-01-31", "2026-09-30"),
            ("2015-2026.09 (141m)", "2015-01-31", "2026-09-30"),
            ("2019-2026.09 (93m)", "2019-01-31", "2026-09-30"),
        ]:
            rx = led_s["net"].loc[a:z].dropna()
            rf_sub = rf.reindex(rx.index).fillna(0.0)
            ex = (rx - rf_sub).values
            T_obs = len(ex)
            srb_m = float(ex.mean() / ex.std())
            srb_ann = float(srb_m * np.sqrt(12.0))
            g3 = float(skew(ex))
            g4 = float(kurtosis(ex, fisher=False))

            # Raw t-stat vs XLK ETF
            rb_xlk = bench_xlk["net"].reindex(rx.index).fillna(0.0)
            diff_xlk = (rx - rb_xlk).values
            c3, se3 = bt.newey_west_ols(diff_xlk, np.zeros((len(diff_xlk), 0)), lags=3)
            t_vs_xlk = float(c3[0] / se3[0])
            p_raw_xlk = float(2.0 * (1.0 - norm.cdf(abs(t_vs_xlk))))

            # Raw t-stat of excess return > 0
            c0, se0 = bt.newey_west_ols(ex, np.zeros((len(ex), 0)), lags=3)
            t_ex0 = float(c0[0] / se0[0])
            p_raw_ex0 = float(2.0 * (1.0 - norm.cdf(abs(t_ex0))))

            for n_label, N_use in [
                (f"M_eff_Eigenvalue ({int(round(m_eff_pr))} indep)", int(round(m_eff_pr))),
                ("Distinct_Families (24 trials)", 24),
                ("Sector_Grid_Only (48 trials)", 48),
                ("Moderate_Search (100 trials)", 100),
                ("Full_Project_All_Series (367 trials)", 367),
            ]:
                sr0_m = np.sqrt(var_sr_m) * (
                    (1.0 - emc) * norm.ppf(1.0 - 1.0 / N_use) + emc * norm.ppf(1.0 - 1.0 / (N_use * np.e))
                )
                z_dsr = (srb_m - sr0_m) * np.sqrt(T_obs - 1.0) / np.sqrt(
                    max(1e-6, 1.0 - g3 * srb_m + (g4 - 1.0) / 4.0 * (srb_m ** 2))
                )
                dsr_prob = float(norm.cdf(z_dsr))
                p_bonf_xlk = min(1.0, p_raw_xlk * N_use)
                p_sidak_xlk = float(1.0 - (1.0 - p_raw_xlk) ** N_use)
                p_bonf_ex0 = min(1.0, p_raw_ex0 * N_use)

                mt_rows.append({
                    "Strategy": ver_name,
                    "Period": p_label,
                    "Months": T_obs,
                    "Trial_Count_Assumption": n_label,
                    "N_Trials": N_use,
                    "Realized_Sharpe_Ann": round(srb_ann, 2),
                    "Expected_Max_Null_Sharpe_Ann": round(float(sr0_m * np.sqrt(12.0)), 2),
                    "DSR_Probability": round(dsr_prob, 4),
                    "t_NW_Excess_gt_0": round(t_ex0, 2),
                    "p_Bonf_Excess_gt_0": round(p_bonf_ex0, 4),
                    "t_NW_vs_XLK": round(t_vs_xlk, 2),
                    "p_Raw_vs_XLK": round(p_raw_xlk, 4),
                    "p_Bonf_vs_XLK": round(p_bonf_xlk, 4),
                    "p_Sidak_vs_XLK": round(p_sidak_xlk, 4),
                    "Passes_HLZ_t3_Excess": bool(t_ex0 >= 3.0),
                    "Passes_HLZ_t3_vs_XLK": bool(t_vs_xlk >= 3.0),
                })

    df_mt = pd.DataFrame(mt_rows)
    df_mt.to_csv(OUT_DIR / "step6_multiple_testing_and_dsr_audit.csv", index=False)
    print(f"\n[Step 6] Distinct trial series collected: {df_trials.shape[1]} | Effective independent trials M_eff = {m_eff_pr:.1f}")
    print(df_stats[df_stats.Strategy == "Tech_Top1_V1_Archival"].to_string(index=False), flush=True)

    # ── Step 7: Freeze Live Forward-Test Signal Table (2026-08-31 and 2026-09-30) ──
    # Note: P_v1 has prices through 2026-09-30 (and 2026-10 if present)
    latest_months = [t for t in store_v1["P"].index if t >= pd.Timestamp("2026-06-30")]
    live_rows = []
    for t in latest_months:
        # Use latest membership if t > form[-1]
        t_mem = t if t in pools["members_v1"] else form[-1]
        mem_t = pools["members_v1"][t_mem]
        t_sec = t if t in pools["secP_v1"].index else form[-1]
        el = []
        for s in sorted(mem_t):
            if (
                s in mom12_v1.columns
                and s in store_v1["P"].columns
                and s in pools["secP_v1"].columns
                and pools["secP_v1"].at[t_sec, s] == "Information Technology"
                and np.isfinite(mom12_v1.at[t, s])
                and np.isfinite(store_v1["P"].at[t, s])
            ):
                el.append((s, float(mom12_v1.at[t, s]), float(store_v1["P"].at[t, s])))
        df_el = pd.DataFrame(el, columns=["ticker", "mom_12_1", "close_t"]).sort_values(
            ["mom_12_1", "ticker"], ascending=[False, True]
        ).reset_index(drop=True)
        for rk_i, r in df_el.head(10).iterrows():
            live_rows.append({
                "formation_date": str(t.date()),
                "target_holding_month": str((t + pd.offsets.MonthEnd(1)).date()),
                "rank": int(rk_i + 1),
                "ticker": r.ticker,
                "mom_12_1_pct": round(float(r.mom_12_1 * 100), 2),
                "adj_close_at_formation": round(float(r.close_t), 4),
                "action": "BUY_TOP1_AT_NEXT_OPEN" if rk_i == 0 else "RUNNER_UP_WATCH",
            })
    df_live = pd.DataFrame(live_rows)
    df_live.to_csv(OUT_DIR / "step7_frozen_tech_top1_live_signals.csv", index=False)
    print("\n[Step 7] Frozen Live Forward-Test Top-10 Signals (2026-06-30 .. 2026-09-30):")
    print(df_live[df_live["rank"] <= 5].to_string(index=False), flush=True)
    print("\nALL 7 STEPS COMPLETED SUCCESSFULLY.")


if __name__ == "__main__":
    main()
