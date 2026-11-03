#!/usr/bin/env python3
"""
STEP 2 (CLEAN-ROOM): Standalone Price, Open, Volume & Sector Engine + Tiingo Second-Source Audit
================================================================================================
Strict Clean-Room Rules:
- Zero imports from original project `.py` modules (`backtest.py`, `ndx_universe.py`, `ml2_run.py`, etc.).
- Zero reading of intermediate `.parquet` panels.
- Loads raw JSON/CSV/YAML files directly, implements segment-break detection (>30d gaps + time splits),
  alias resolution, PIT sector reconstruction, and Open-to-Open execution (`Open[t+1, d1] -> Open[t+2, d1]`),
  plus `T+1 Close`, `T+2 Close`, and independent Tiingo EOD (`adjOpen` / `adjClose`) cross-checking.
"""

import datetime
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

REPO_ROOT = Path("/Users/happygolucky/Desktop/宏观观察器").resolve()
DATA_DIR = REPO_ROOT / "research" / "sector_stock_momentum" / "data"
OUT_DIR = REPO_ROOT / "outputs" / "qqq_lgbm_cleanroom_audit_20261103"
TIINGO_AUDIT_DIR = REPO_ROOT / "outputs" / "tech_top1_independent_audit_20261103" / "tiingo"
ORIG_LEDGER_DIR = REPO_ROOT / "outputs" / "ml3_feature_discovery_20261102" / "ledgers_qqq_iwm"
OUT_DIR.mkdir(parents=True, exist_ok=True)

WIKI_CUTOFF = pd.Timestamp("2018-03-27")
NON_STOCK = {"XLK", "XLC", "XLY", "XLF", "XLI", "XLU", "XLE", "XLRE", "XLB", "XLP", "XLV", "SPY", "RSP", "QQQ"}

MANUAL_ALIASES = {
    "LB": ("BBWI", "L Brands -> Bath & Body Works CIK 701985"),
    "CTL": ("LUMN", "CenturyLink -> Lumen CIK 18926"),
    "CBS": ("VIAC", "CBS -> ViacomCBS CIK 813828"),
    "VIAC": ("PARA", "ViacomCBS -> Paramount CIK 813828"),
    "HCP": ("PEAK", "HCP -> Healthpeak CIK 765880"),
    "SYMC": ("NLOK", "Symantec -> NortonLifeLock CIK 849399"),
    "UTX": ("RTX", "United Technologies -> RTX CIK 101829"),
    "GPS": ("GAP", "Gap GPS -> GAP CIK 39911"),
    "FBHS": ("FBIN", "Fortune Brands CIK 1519751"),
    "KORS": ("CPRI", "Michael Kors -> Capri CIK 1530721"),
    "COG": ("CTRA", "Cabot Oil & Gas -> Coterra CIK 858470"),
    "DISCA": ("WBD", "Discovery Series A -> WBD CIK 1437107"),
    "ARNC": ("HWM", "Arconic -> Howmet CIK 4281"),
    "WLTW": ("WTW", "Willis Towers Watson CIK 1140536"),
    "SIVB": ("SIVBQ", "SVB Financial OTC"),
    "FRC": ("FRCB", "First Republic OTC"),
    "WYND": ("TNL", "Wyndham -> Travel + Leisure CIK 1361658"),
    "CDAY": ("DAY", "Ceridian -> Dayforce CIK 1725057"),
    "HFC": ("DINO", "HollyFrontier -> HF Sinclair"),
    "DWDP": ("DD", "DowDuPont -> DuPont CIK 1666700"),
}

TIME_SPLIT = {
    "IR": ("2020-03-02", "TT", "IR"),
    "BHGE": ("2017-07-03", "BHI", "BKR"),
}

# Historical GICS reshuffle rules (2016 Real Estate, 2018 Communication Services, 2023 Payments/Data Processing)
D_RE = pd.Timestamp("2016-09-01")
D_CS = pd.Timestamp("2018-09-24")
D_23 = pd.Timestamp("2023-03-20")

CS_PRE2018_GICS = {
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
CS_PRE2018_YAHOO = {
    "Telecom Services": "Telecommunication Services",
    "Internet Content & Information": "Information Technology",
    "Electronic Gaming & Multimedia": "Information Technology",
    "Entertainment": "Consumer Discretionary",
    "Broadcasting": "Consumer Discretionary",
    "Publishing": "Consumer Discretionary",
    "Advertising Agencies": "Consumer Discretionary",
}
MOVED_2018_TO_CD_FROM_IT = {"EBAY"}
PAYMENTS_SUB = {"Transaction & Payment Processing Services"}
MOVED_2023_IT_TO_IND = {"ADP", "PAYX", "PAYC", "DAY", "CDAY", "BR"}
MOVED_2023_CD_TO_CS = {"DG", "DLTR", "TGT"}


def load_yaml_year(year: int) -> dict:
    with open(DATA_DIR / "nasdaq100_src" / f"n100-ticker-changes-{year}.yaml", encoding="utf-8") as f:
        return yaml.load(f, Loader=yaml.BaseLoader)


def raw_ndx_tickers_as_of(d: datetime.date) -> set[str]:
    y_data = load_yaml_year(d.year)
    res = {str(x).strip() for x in y_data.get("tickers_on_Jan_1", [])}
    changes = y_data.get("changes") or {}
    for k in sorted(changes.keys(), key=str):
        kd = k if isinstance(k, datetime.date) else datetime.date.fromisoformat(str(k))
        if kd <= d:
            for op, xs in changes[k].items():
                tset = {str(x).strip() for x in xs}
                if op == "union":
                    res |= tset
                elif op == "difference":
                    res -= tset
    return res


def load_ndx_symbol_map() -> dict[str, str | None]:
    mp = pd.read_csv(DATA_DIR / "ndx_symbol_map.csv")
    out = {}
    for r in mp.itertuples():
        out[r.ndx_ticker] = str(r.target) if r.action in ("map_existing", "fetch_tiingo", "fetch_wiki") else None
    return out


def read_union_spells() -> pd.DataFrame:
    sp = pd.read_csv(DATA_DIR / "sp500_ticker_start_end.csv", parse_dates=["start_date", "end_date"])
    ap = DATA_DIR / "membership_additions.csv"
    if ap.exists():
        add = pd.read_csv(ap, parse_dates=["start_date", "end_date"])[["ticker", "start_date", "end_date"]]
        sp = pd.concat([sp, add], ignore_index=True)

    # Reconstruct NDX spells directly from YAML changes
    ev = set()
    for y in range(2007, 2027):
        ev.add(datetime.date(y, 1, 1))
        for k in (load_yaml_year(y).get("changes") or {}):
            ev.add(datetime.date.fromisoformat(str(k)))
    ev = sorted(e for e in ev if e <= datetime.date(2026, 9, 30))
    open_, nd_spells = {}, []
    prev = set()
    for e in ev:
        cur = raw_ndx_tickers_as_of(e)
        for tk in cur - prev:
            open_[tk] = e
        for tk in prev - cur:
            nd_spells.append((tk.replace(".", "-"), pd.Timestamp(open_.pop(tk)), pd.Timestamp(e - datetime.timedelta(days=1))))
        prev = cur
    for tk, s in open_.items():
        nd_spells.append((tk.replace(".", "-"), pd.Timestamp(s), pd.NaT))

    nd_df = pd.DataFrame(nd_spells, columns=["ticker", "start_date", "end_date"])
    smap = load_ndx_symbol_map()
    nd_df["ticker"] = [smap.get(t, t) for t in nd_df["ticker"]]
    nd_df = nd_df.dropna(subset=["ticker"])
    return pd.concat([sp[["ticker", "start_date", "end_date"]], nd_df[["ticker", "start_date", "end_date"]]], ignore_index=True)


def build_cleanroom_aliases(first_price_date: dict[str, pd.Timestamp]) -> pd.DataFrame:
    sp = pd.read_csv(DATA_DIR / "sp500_ticker_start_end.csv", parse_dates=["start_date", "end_date"])
    ch = pd.read_csv(DATA_DIR / "wiki_changes.csv")
    ch["date"] = pd.to_datetime(ch.date, errors="coerce")
    cmap_p = DATA_DIR / "fundamentals" / "cik_map.csv"
    cik = dict(pd.read_csv(cmap_p)[["ticker", "cik"]].dropna().values) if cmap_p.exists() else {}
    wiki = pd.read_csv(DATA_DIR / "wiki_current_constituents.csv")
    cik.update({t: c for t, c in zip(wiki.Symbol, wiki.CIK)})

    def listed(tk, col, d):
        x = ch[(ch[col] == tk) & ((ch.date - d).abs() <= pd.Timedelta(days=7))]
        return len(x) > 0

    y = lambda t: t.replace(".", "-")
    added = dict(zip(wiki.Symbol, pd.to_datetime(wiki["Date added"], errors="coerce")))
    acc = []
    succ = {}

    def cik_of(t):
        seen = set()
        while t not in cik and t in succ and t not in seen:
            seen.add(t)
            t = succ[t]
        return cik.get(t)

    starts = sp.sort_values("start_date", ascending=False)
    for b in starts.itertuples():
        if b.start_date < pd.Timestamp("2008-01-01"):
            continue
        cands = sp[sp.end_date.notna() & ((sp.end_date - b.start_date).abs() <= pd.Timedelta(days=3)) & (sp.ticker != b.ticker)]
        cands = [a for a in cands.ticker if not listed(a, "removed_ticker", b.start_date)]
        if not cands or listed(b.ticker, "added_ticker", b.start_date):
            continue
        fp = first_price_date.get(y(b.ticker))
        carries = fp is not None and fp <= b.start_date - pd.Timedelta(days=365)
        cb = cik_of(b.ticker)
        same = [a for a in cands if cb is not None and cik.get(a) == cb]
        if len(same) == 1:
            cands, evidence = same, "same_cik"
        else:
            cands = [a for a in cands if cik.get(a) is None or cik.get(a) == cb]
            old_member = b.ticker in added and pd.notna(added[b.ticker]) and added[b.ticker] <= b.start_date - pd.Timedelta(days=365)
            evidence = "wiki_date_added" if old_member else None
        if len(cands) == 1 and carries and evidence:
            acc.append({"old": cands[0], "new": b.ticker, "evidence": evidence})
            succ[cands[0]] = b.ticker

    done = {r["old"] for r in acc}
    sp_sec = DATA_DIR / "sec_successor_aliases.csv"
    if sp_sec.exists():
        def overlap(a, b):
            A, B = sp[sp.ticker == a], sp[sp.ticker == b.replace("-", ".")]
            return any(
                x.start_date < (y_.end_date if pd.notna(y_.end_date) else pd.Timestamp("2100-01-01"))
                and y_.start_date < (x.end_date if pd.notna(x.end_date) else pd.Timestamp("2100-01-01"))
                for x in A.itertuples()
                for y_ in B.itertuples()
            )
        for r in pd.read_csv(sp_sec).itertuples():
            if r.status == "accepted" and r.old not in done and r.old not in MANUAL_ALIASES and not overlap(r.old, r.new):
                acc.append({"old": r.old, "new": r.new.replace("-", "."), "evidence": f"sec_same_cik_{int(r.cik)}"})
                done.add(r.old)

    for a, (b, why) in MANUAL_ALIASES.items():
        if a not in done:
            acc.append({"old": a, "new": b, "evidence": "manual: " + why})

    acc_df = pd.DataFrame(acc)
    if len(acc_df):
        nxt = dict(zip(acc_df.old, acc_df.new))
        def final(t):
            seen = set()
            while t in nxt and t not in seen:
                seen.add(t)
                t = nxt[t]
            return t
        acc_df["price_symbol"] = [y(final(t)) for t in acc_df.new]
    return acc_df


def load_cleanroom_prices_and_universe(cutoff: pd.Timestamp | None = None):
    """
    Loads S&P 500 U Nasdaq-100 daily & monthly prices, segments, opens, memberships, and PIT sectors
    entirely from raw JSON/CSV/YAML files, with optional strict date cutoff (`cutoff`).
    """
    raw_dir = DATA_DIR / "raw"
    tiingo_dir = DATA_DIR / "raw_tiingo"
    wiki_dir = DATA_DIR / "raw_wiki"
    arch_dir = DATA_DIR / "raw_archive"
    ndx_dir = DATA_DIR / "raw_ndx"

    series = {}
    price_source = {}
    for f in sorted(os.listdir(raw_dir)):
        if not f.endswith(".json") or f.startswith("_"):
            continue
        d = json.load(open(raw_dir / f))
        s = pd.Series(d["adjclose"], index=pd.to_datetime(d["dates"]), dtype=float)
        s = s[~s.index.duplicated(keep="last")].sort_index()
        if cutoff is not None:
            s = s[s.index <= pd.Timestamp(cutoff)]
        series[d["symbol"]] = s
        price_source[d["symbol"]] = "yahoo"

    sp = read_union_spells()
    sp["ticker"] = sp.ticker.str.replace(".", "-", regex=False)
    sp = sp[sp.end_date.isna() | (sp.end_date >= "2007-12-01")]

    # Build combined Tiingo & WIKI stores (base S&P + raw_ndx where covers_membership=True)
    tiingo = {}
    for f in sorted(os.listdir(tiingo_dir)) if tiingo_dir.exists() else []:
        if f.endswith(".json") and not f.startswith("_"):
            d = json.load(open(tiingo_dir / f))
            t = pd.Series(d["adjclose"], index=pd.to_datetime(d["dates"]), dtype=float)
            t = t[~t.index.duplicated(keep="last")].sort_index()
            if cutoff is not None:
                t = t[t.index <= pd.Timestamp(cutoff)]
            if len(t):
                tiingo[d["symbol"]] = t

    wiki_raw = {}
    for f in sorted(os.listdir(wiki_dir)) if wiki_dir.exists() else []:
        if f.endswith(".json") and not f.startswith("_"):
            d = json.load(open(wiki_dir / f))
            w = pd.Series(d["adjclose"], index=pd.to_datetime(d["dates"]), dtype=float)
            w = w[~w.index.duplicated(keep="last")].sort_index()
            if cutoff is not None:
                w = w[w.index <= pd.Timestamp(cutoff)]
            if len(w):
                wiki_raw[d["symbol"]] = w

    for f in sorted(os.listdir(ndx_dir)) if ndx_dir.exists() else []:
        if not f.endswith(".json") or f.startswith("_"):
            continue
        d = json.load(open(ndx_dir / f))
        if not d.get("covers_membership"):
            continue
        sym = d["symbol"]
        s = pd.Series(d["adjclose"], index=pd.to_datetime(d["dates"]), dtype=float)
        s = s[~s.index.duplicated(keep="last")].sort_index()
        if cutoff is not None:
            s = s[s.index <= pd.Timestamp(cutoff)]
        if not len(s):
            continue
        if d.get("source") == "tiingo" and sym not in tiingo:
            tiingo[sym] = s
        elif d.get("source") == "wiki" and sym not in wiki_raw:
            wiki_raw[sym] = s

    first = {k: v.index[0] for k, v in series.items() if len(v)}
    for k, v in tiingo.items():
        first[k] = min(first.get(k, v.index[0]), v.index[0])

    aliases = build_cleanroom_aliases(first)
    pred = {}
    for r in aliases.itertuples():
        pred.setdefault(r.price_symbol, []).append(r.old.replace(".", "-"))
    succ_of = {r.old.replace(".", "-"): r.price_symbol for r in aliases.itertuples()}

    def spells_of(sym):
        tk = [sym] + pred.get(sym, [])
        return [(r.start_date, r.end_date) for r in sp[sp.ticker.isin(tk)].itertuples()]

    def covers(x, sym):
        return x is not None and len(x) > 0 and all(
            x.index[0] <= max(a, pd.Timestamp("2007-01-10")) + pd.Timedelta(days=10) for a, _ in spells_of(sym)
        )

    for sym, t in tiingo.items():
        if covers(series.get(sym), sym) or not covers(t, sym):
            continue
        if succ_of.get(sym) and covers(series.get(succ_of[sym]), sym) and succ_of[sym] != sym:
            continue
        series[sym] = t
        price_source[sym] = "tiingo"

    wiki_syms = set()
    for sym, w in wiki_raw.items():
        if covers(series.get(sym), sym) or not covers(w, sym):
            continue
        succ_sym = succ_of.get(sym)
        if succ_sym and covers(series.get(succ_sym), sym):
            continue
        cur = series.get(sym)
        if cur is not None and len(cur):
            gaps = np.where(np.diff(w.index.values).astype("timedelta64[D]").astype(int) > 30)[0]
            w0 = w.iloc[: gaps[0] + 1] if len(gaps) else w
            if w0.index[-1] < cur.index[0] - pd.Timedelta(days=30) and covers(w0, sym):
                series[sym] = pd.concat([w0, cur])
                price_source[sym] = f"wiki<{w0.index[-1].date()}|{price_source.get(sym)}"
                if w0.index[-1] >= WIKI_CUTOFF - pd.Timedelta(days=5):
                    wiki_syms.add(sym)
            continue
        else:
            series[sym] = w
            price_source[sym] = "wiki"
        if w.index[-1] >= WIKI_CUTOFF - pd.Timedelta(days=5):
            wiki_syms.add(sym)

    for f in sorted(os.listdir(arch_dir)) if arch_dir.exists() else []:
        if not f.endswith(".json") or f.startswith("_"):
            continue
        d = json.load(open(arch_dir / f))
        sym = d["symbol"]
        a_ = pd.Series(d["adjclose"], index=pd.to_datetime(d["dates"]), dtype=float).dropna().sort_index()
        a_ = a_[~a_.index.duplicated(keep="last")]
        ch = a_.diff().fillna(1) != 0
        last_move = a_[ch].index[-1] if ch.any() else a_.index[-1]
        if (a_.index[-1] - last_move).days >= 7:
            a_ = a_[a_.index <= last_move]
        if cutoff is not None:
            a_ = a_[a_.index <= pd.Timestamp(cutoff)]
        if not len(a_) or covers(series.get(sym), sym) or not covers(a_, sym):
            continue
        succ_sym = succ_of.get(sym)
        if succ_sym and covers(series.get(succ_sym), sym):
            continue
        cur = series.get(sym)
        if cur is not None and len(cur):
            if a_.index[-1] < cur.index[0] - pd.Timedelta(days=30):
                series[sym] = pd.concat([a_, cur])
                price_source[sym] = f"archive:{d['source']}<{a_.index[-1].date()}|{price_source.get(sym)}"
            else:
                series[sym] = pd.concat([a_, cur[cur.index > a_.index[-1] + pd.Timedelta(days=30)]])
                price_source[sym] = f"archive:{d['source']}<{a_.index[-1].date()}|{price_source.get(sym)}"
        else:
            series[sym] = a_
            price_source[sym] = f"archive:{d['source']}"

    split_log = []
    for tk, (d_str, before, after) in TIME_SPLIT.items():
        b_, a_ = series.get(before), series.get(after)
        if b_ is not None and a_ is not None and len(b_) and len(a_):
            cut = pd.Timestamp(d_str)
            series[tk] = pd.concat([b_[b_.index < cut], a_[a_.index >= cut]])
            price_source[tk] = f"{price_source.get(before)}:{before}<{d_str}|{price_source.get(after)}:{after}"
            split_log.append((tk, d_str))

    id_exclude = {}
    rp = DATA_DIR / "identity_resolutions.csv"
    if rp.exists():
        for r in pd.read_csv(rp).itertuples():
            tk, d = r.ticker, pd.Timestamp(r.date)
            if r.action == "use_wiki_before":
                wp = next((x for x in [DATA_DIR / "raw_wiki_check" / f"{tk}.json", wiki_dir / f"{tk}.json"] if x.exists()), None)
                if wp is None:
                    id_exclude.setdefault(tk, []).append((pd.Timestamp("1900-01-01"), d))
                    continue
                w = json.load(open(wp))
                ws = pd.Series(w["adjclose"], index=pd.to_datetime(w["dates"]), dtype=float).sort_index()
                ws = ws[~ws.index.duplicated(keep="last")]
                if cutoff is not None:
                    ws = ws[ws.index <= pd.Timestamp(cutoff)]
                cur = series.get(tk, pd.Series(dtype=float))
                series[tk] = pd.concat([ws[ws.index < d], cur[cur.index >= d]])
                price_source[tk] = f"wiki:{tk}<{d.date()}|{price_source.get(tk)}"
                split_log.append((tk, str(d.date())))
            elif r.action == "use_archive_before":
                ap_ = arch_dir / f"{tk}.json"
                if not ap_.exists():
                    id_exclude.setdefault(tk, []).append((pd.Timestamp("1900-01-01"), d))
                    continue
                w = json.load(open(ap_))
                ws = pd.Series(w["adjclose"], index=pd.to_datetime(w["dates"]), dtype=float).dropna().sort_index()
                ws = ws[~ws.index.duplicated(keep="last")]
                if cutoff is not None:
                    ws = ws[ws.index <= pd.Timestamp(cutoff)]
                cur = series.get(tk, pd.Series(dtype=float))
                series[tk] = pd.concat([ws[ws.index < d], cur[cur.index >= d]])
                price_source[tk] = f"archive:{w['source']}:{tk}<{d.date()}|{price_source.get(tk)}"
                split_log.append((tk, str(d.date())))
            elif r.action == "segment_break":
                split_log.append((tk, str(d.date())))
            elif r.action == "exclude_before":
                id_exclude.setdefault(tk, []).append((pd.Timestamp("1900-01-01"), d - pd.Timedelta(days=1)))
            elif r.action == "exclude_spell":
                id_exclude.setdefault(tk, []).append((d, pd.Timestamp(r.date_to)))

    # Segment integrity check (>30 day gaps)
    sp_all = read_union_spells()
    sp_all["ticker"] = sp_all.ticker.str.replace(".", "-", regex=False)
    spells_dict = {}
    for r in sp_all.itertuples():
        spells_dict.setdefault(r.ticker, []).append((r.start_date, r.end_date if pd.notna(r.end_date) else pd.Timestamp("2100-01-01")))
    for r in aliases.itertuples():
        for q in sp_all[sp_all.ticker == r.old.replace(".", "-")].itertuples():
            spells_dict.setdefault(r.price_symbol, []).append((q.start_date, q.end_date if pd.notna(q.end_date) else pd.Timestamp("2100-01-01")))

    out_series, seg_ids = {}, {}
    for sym, s in series.items():
        if s.empty:
            out_series[sym], seg_ids[sym] = s, s
            continue
        gaps = np.where(np.diff(s.index.values).astype("timedelta64[D]").astype(int) > 30)[0]
        bounds = [0] + list(gaps + 1) + [len(s)]
        sid = pd.Series(np.repeat(np.arange(len(bounds) - 1), np.diff(bounds)), index=s.index, dtype=float)
        if sym in NON_STOCK or sym not in spells_dict:
            out_series[sym], seg_ids[sym] = s, sid
            continue
        keep = np.zeros(len(s), bool)
        for a, b in zip(bounds[:-1], bounds[1:]):
            g0, g1 = s.index[a], s.index[b - 1]
            if any(g0 <= e and g1 >= st for st, e in spells_dict[sym]):
                keep[a:b] = True
        out_series[sym], seg_ids[sym] = s[keep], sid[keep]
    series, segs = out_series, seg_ids

    for tk, d_str in split_log:
        if tk in segs and len(segs[tk]):
            segs[tk] = segs[tk].where(segs[tk].index < pd.Timestamp(d_str), segs[tk] + 1000)

    for r in aliases.itertuples():
        old = r.old.replace(".", "-")
        if r.price_symbol not in series or old in TIME_SPLIT:
            continue
        cur, suc = series.get(old), series[r.price_symbol]
        if not covers(suc, old) and covers(cur, old) and price_source.get(old, "yahoo") != "yahoo":
            continue
        series[old] = suc
        segs[old] = segs[r.price_symbol]
        price_source[old] = f"alias:{r.price_symbol}:{price_source.get(r.price_symbol)}"

    # Untrusted spells check
    bad = {}
    for r in sp_all.itertuples():
        e = r.end_date if pd.notna(r.end_date) else pd.Timestamp("2100-01-01")
        if e < pd.Timestamp("2007-12-01"):
            continue
        s_ = series.get(r.ticker)
        first_dt = s_.index[0] if s_ is not None and len(s_) else None
        need = max(r.start_date, pd.Timestamp("2007-01-10")) + pd.Timedelta(days=10)
        if first_dt is not None and first_dt > need:
            bad.setdefault(r.ticker, []).append((r.start_date, e))
    for tk, iv in id_exclude.items():
        bad.setdefault(tk, []).append if isinstance(iv, tuple) else bad.setdefault(tk, []).extend(iv)

    daily = pd.DataFrame(series).sort_index()
    monthly = daily.resample("ME").last().where(daily.resample("ME").count() > 0)
    obs = pd.DataFrame(np.where(daily.notna().values, daily.index.values[:, None], np.datetime64("NaT")), index=daily.index, columns=daily.columns)
    last_obs = obs.resample("ME").max()
    mkt_last = daily["SPY"].dropna().index.to_series().resample("ME").max()
    fresh = last_obs.ge(mkt_last - pd.Timedelta(days=7), axis=0)
    monthly = monthly.where(fresh.reindex(index=monthly.index, columns=monthly.columns).fillna(False))

    seg_d = pd.DataFrame(segs).reindex(index=daily.index, columns=daily.columns)
    seg_m = seg_d.resample("ME").last().reindex(monthly.index)

    # Monthly memberships (S&P 500, NDX, and Union)
    end_bound = pd.Timestamp("2026-08-31") if cutoff is None else min(pd.Timestamp("2026-08-31"), pd.Timestamp(cutoff))
    form = monthly.index[(monthly.index >= pd.Timestamp("2010-12-31")) & (monthly.index <= end_bound)]

    # S&P 500 membership at month-ends
    h = pd.read_csv(DATA_DIR / "sp500_hist_components.csv", parse_dates=["date"]).sort_values("date")
    last_date = h.date.max()
    ch = pd.read_csv(DATA_DIR / "wiki_changes.csv")
    ch["date"] = pd.to_datetime(ch.date, errors="coerce")
    ch = ch[ch.date > last_date].sort_values("date")
    add_df = pd.read_csv(DATA_DIR / "membership_additions.csv", parse_dates=["start_date", "end_date"]) if (DATA_DIR / "membership_additions.csv").exists() else pd.DataFrame()

    sp_raw = {}
    for t in form:
        row = h[h.date <= t]
        if row.empty:
            continue
        mem = {x.replace(".", "-") for x in row.tickers.iloc[-1].split(",")}
        for c in ch[ch.date <= t].itertuples():
            if isinstance(c.removed_ticker, str):
                mem.discard(c.removed_ticker.replace(".", "-"))
            if isinstance(c.added_ticker, str):
                mem.add(c.added_ticker.replace(".", "-"))
        for r in add_df.itertuples():
            if r.start_date <= t and (pd.isna(r.end_date) or t < r.end_date):
                mem.add(r.ticker)
        sp_raw[t] = mem

    # NDX membership at month-ends directly from YAML logs
    smap = load_ndx_symbol_map()
    nd_raw = {}
    for t in form:
        r_set = raw_ndx_tickers_as_of(t.date())
        mapped = {smap.get(x.replace(".", "-"), x.replace(".", "-")) for x in r_set}
        mapped.discard(None)
        nd_raw[t] = mapped

    clean = lambda mem, t: {x for x in mem if not any(a <= t <= b for a, b in bad.get(x, []))}
    members_sp = {t: clean(sp_raw.get(t, set()), t) for t in form}
    members_nd = {t: clean(nd_raw.get(t, set()), t) for t in form}
    members_union = {t: members_sp[t] | members_nd[t] for t in form}

    # Build PIT sector panel
    sec_df = build_cleanroom_sector_table(aliases, price_source)
    secP = build_cleanroom_sector_panel(sec_df, form)

    # Build Open matrix
    O = build_cleanroom_opens(daily, price_source, cutoff=cutoff)

    return {
        "daily": daily,
        "P": monthly,
        "O": O,
        "seg_d": seg_d,
        "seg_m": seg_m,
        "price_source": price_source,
        "wiki_syms": wiki_syms,
        "aliases": aliases,
        "bad": bad,
        "form": form,
        "members_sp": members_sp,
        "members_nd": members_nd,
        "members_union": members_union,
        "secP": secP,
    }


def build_cleanroom_sector_table(aliases: pd.DataFrame, price_source: dict[str, str]) -> pd.DataFrame:
    raw = pd.read_csv(DATA_DIR / "sectors.csv")
    wiki = raw[raw.source == "wikipedia_gics"].set_index("ticker")
    yahoo = raw[raw.source == "yahoo"].set_index("ticker")
    cm_p = DATA_DIR / "fundamentals" / "cik_map.csv"
    sic = {}
    if cm_p.exists():
        cm = pd.read_csv(cm_p)
        if "sic_sector" in cm:
            sic = {t.replace(".", "-"): (sec, ind) for t, sec, ind in zip(cm.ticker, cm.sic_sector, cm.sic) if isinstance(sec, str)}
    succ = {r.old.replace(".", "-"): r.price_symbol for r in aliases.itertuples()}
    tickers = set(raw.ticker) | set(sic) | set(succ)
    rows = []

    def base_row(t, depth=0):
        if t in wiki.index:
            return wiki.at[t, "sector"], "wikipedia_gics", wiki.at[t, "industry"]
        if t in succ and depth < 5:
            r = base_row(succ[t], depth + 1)
            if r:
                return r[0], f"alias:{succ[t]}:{r[1]}", r[2]
        if t in yahoo.index and price_source.get(t) == "yahoo" and isinstance(yahoo.at[t, "sector"], str) and yahoo.at[t, "sector"] != "UNKNOWN":
            return yahoo.at[t, "sector"], "yahoo", yahoo.at[t, "industry"]
        if t in sic:
            return sic[t][0], "sic", f"SIC {sic[t][1]}"
        return None

    for t in sorted(tickers):
        r = base_row(t)
        if r:
            rows.append({"ticker": t, "sector": r[0], "source": r[1], "industry": r[2]})
    out = pd.DataFrame(rows)
    ov_p = DATA_DIR / "sector_overrides.csv"
    if ov_p.exists():
        ov = pd.read_csv(ov_p)
        out = out[~out.ticker.isin(ov.ticker)]
        cols = ["ticker", "sector", "source", "industry"] + [c for c in ["valid_from", "valid_to"] if c in ov]
        out = pd.concat([out, ov.assign(source="manual:" + ov.source)[cols]], ignore_index=True)

    # Append NDX-specific sectors
    ndx_sec = pd.read_csv(DATA_DIR / "ndx_sectors.csv")
    ndx_sec = ndx_sec[~ndx_sec.ticker.isin(out.ticker)][["ticker", "sector", "source", "industry"]]
    return pd.concat([out, ndx_sec], ignore_index=True)


def sector_asof_cleanroom(ticker, date, sector, source, industry):
    d = pd.Timestamp(date)
    sec = sector
    ind = industry if isinstance(industry, str) else ""
    if d < D_23:
        if sec == "Financials" and (ind in PAYMENTS_SUB or (source == "yahoo" and ind == "Credit Services" and ticker in {"V", "MA"})):
            sec = "Information Technology"
        elif sec == "Industrials" and ticker in MOVED_2023_IT_TO_IND:
            sec = "Information Technology"
        elif sec == "Consumer Staples" and ticker in MOVED_2023_CD_TO_CS:
            sec = "Consumer Discretionary"
    if d < D_CS:
        if sec == "Communication Services":
            gics = "wikipedia_gics" in str(source) or str(source).startswith("manual")
            m = CS_PRE2018_GICS.get(ind) if gics else CS_PRE2018_YAHOO.get(ind)
            if m is None and ind.startswith("SIC "):
                code = ind[4:].split(".")[0]
                m = "Telecommunication Services" if code.startswith("48") and code not in ("4833", "4841") else "Information Technology" if code.startswith("737") else "Consumer Discretionary"
            sec = m if m else "Consumer Discretionary"
        elif ticker in MOVED_2018_TO_CD_FROM_IT and sec == "Consumer Discretionary":
            sec = "Information Technology"
    if d < D_RE and sec == "Real Estate":
        sec = "Financials"
    return sec


def build_cleanroom_sector_panel(sector_df: pd.DataFrame, month_ends: pd.DatetimeIndex) -> pd.DataFrame:
    sec = {}
    has_dates = "valid_from" in sector_df.columns
    for tk, g in sector_df.groupby("ticker", sort=True):
        g = g[g.sector.apply(lambda x: isinstance(x, str) and x != "UNKNOWN")]
        if g.empty:
            continue
        col_s = [None] * len(month_ends)
        undated = g[g.valid_from.isna() & g.valid_to.isna()] if has_dates else g
        dated = g[~g.index.isin(undated.index)]
        if len(undated):
            r = undated.iloc[0]
            for i, t in enumerate(month_ends):
                col_s[i] = sector_asof_cleanroom(tk, t, r.sector, r.source, r.get("industry"))
        for _, r in dated.iterrows():
            a = pd.Timestamp(r.valid_from) if pd.notna(r.valid_from) else pd.Timestamp("1900-01-01")
            b = pd.Timestamp(r.valid_to) if pd.notna(r.valid_to) else pd.Timestamp("2100-01-01")
            for i, t in enumerate(month_ends):
                if a <= t < b:
                    col_s[i] = r.sector
        sec[tk] = col_s
    return pd.DataFrame(sec, index=month_ends)


def _parse_source(ps: str, s: str):
    if ps.startswith("alias:"):
        _, sym, rest = ps.split(":", 2)
        return _parse_source(rest, sym)
    out = []
    for part in ps.split("|"):
        cut = None
        if "<" in part:
            part, c = part.split("<", 1)
            cut = pd.Timestamp(c[:10])
        tok = part.split(":")
        vendor = tok[0]
        sym = s
        if vendor in ("yahoo", "tiingo", "wiki") and len(tok) > 1:
            sym = tok[1]
        elif vendor == "archive" and len(tok) > 2:
            sym = tok[2]
        out.append((vendor, sym, cut))
    return out


def build_cleanroom_opens(daily: pd.DataFrame, price_source: dict[str, str], cutoff: pd.Timestamp | None = None) -> pd.DataFrame:
    O = pd.DataFrame(np.nan, index=daily.index, columns=daily.columns)
    od = DATA_DIR / "raw_open"
    W = pd.read_parquet(DATA_DIR / "wiki_bulk" / "wiki_open.parquet")
    if cutoff is not None:
        W = W[W.date <= pd.Timestamp(cutoff)]
    wiki = {t: g.set_index("date").adj_open for t, g in W.groupby("ticker")}
    cache = {}

    def yopen(sym):
        if sym not in cache:
            p = od / f"{sym}.json"
            if p.exists():
                j = json.load(open(p))
                x = pd.Series(j["adj_open"], index=pd.to_datetime(j["dates"]), dtype=float)
                x = x[~x.index.duplicated(keep="last")]
                if cutoff is not None:
                    x = x[x.index <= pd.Timestamp(cutoff)]
                cache[sym] = x
            else:
                cache[sym] = None
        return cache[sym]

    for s in daily.columns:
        parts = _parse_source(str(price_source.get(s, "")), s)
        col = pd.Series(np.nan, index=daily.index)
        lo = None
        for vendor, sym, cut in parts:
            x = yopen(sym) if vendor == "yahoo" else wiki.get(sym) if vendor == "wiki" else None
            m = np.ones(len(daily.index), bool)
            if lo is not None:
                m &= daily.index >= lo
            if cut is not None:
                m &= daily.index < cut
            if x is not None:
                col[m] = x.reindex(daily.index)[m]
            lo = cut
        O[s] = col.where(daily[s].notna())
    return O


def load_resolutions() -> dict[tuple[pd.Timestamp, str], float]:
    p = DATA_DIR / "exit_resolutions.csv"
    if not p.exists():
        return {}
    r = pd.read_csv(p, parse_dates=["formation"])
    return {(a, b): float(c) for a, b, c in zip(r.formation, r.ticker, r.holding_return)}


def load_rf(hold_months: pd.DatetimeIndex) -> pd.Series:
    p_local = DATA_DIR / "fred_DGS3MO.json"
    p_dash = REPO_ROOT / "data" / "fred" / "DGS3MO.json"
    d = json.load(open(p_local if p_local.exists() else p_dash))
    s = pd.Series({pd.Timestamp(a): b for a, b in d["values"] if b is not None}, dtype=float).sort_index()
    form = hold_months - pd.offsets.MonthEnd(1)
    y = s.resample("ME").last().reindex(form).ffill().values / 100.0
    return pd.Series((1.0 + y) ** (1.0 / 12.0) - 1.0, index=hold_months)


class CleanRoomPriceEngine:
    """
    Standalone holding-period return engine supporting:
      - mode='open' (default: next-session Open-to-Open, fallback to next-session Close)
      - mode='close_t1' (next-session T+1 Close-to-Close)
      - mode='close_t2' (T+2 Close-to-Close)
    """
    def __init__(self, U: dict, mode: str = "open"):
        self.daily = U["daily"]
        self.P = U["P"]
        self.O = U["O"]
        self.seg_d = U["seg_d"]
        self.seg_m = U["seg_m"]
        self.wiki_syms = U["wiki_syms"]
        self.resolutions = load_resolutions()
        self.mode = mode
        self.sess = self.daily["SPY"].dropna().index
        self.used_open = 0
        self.used_close = 0

        lag_days = 2 if mode == "close_t2" else 1
        pos = np.clip(self.daily.index.searchsorted(self.P.index, side="right") + lag_days - 1, 0, len(self.daily) - 1)
        E = self.daily.ffill(limit=5).iloc[pos].copy()
        E.index = self.P.index
        self.E = E
        self.nxt = E.shift(-1) / E - 1.0
        sg = self.seg_m.reindex(index=self.P.index, columns=self.P.columns)
        self.nxt = self.nxt.where(sg.shift(-1) == sg)
        self.cache = {}

    def _next_session(self, t: pd.Timestamp):
        i = self.sess.searchsorted(t, side="right")
        return self.sess[i] if i < len(self.sess) else None

    def _close_ret(self, t: pd.Timestamp, s: str):
        key = (t, s)
        if key in self.resolutions:
            return float(self.resolutions[key]), "resolved_manual"
        if t not in self.nxt.index or s not in self.nxt.columns:
            return np.nan, "missing"
        v = self.nxt.at[t, s]
        if np.isfinite(v):
            return float(v), "ok"
        if key not in self.cache:
            b = self.E.at[t, s] if np.isfinite(self.E.at[t, s]) else self.P.at[t, s]
            d = self.daily[s].loc[t + pd.Timedelta(days=1) : t + pd.offsets.MonthEnd(1)]
            if s in self.seg_d.columns:
                seg_t = self.seg_d[s].loc[:t].dropna()
                if len(seg_t):
                    d = d[self.seg_d[s].reindex(d.index) == seg_t.iloc[-1]]
            d = d.dropna()
            frozen = s in self.wiki_syms and (len(d) == 0 or abs((d.index[-1] - WIKI_CUTOFF).days) <= 5)
            if len(d):
                self.cache[key] = (float(d.iloc[-1] / b - 1.0), "source_gap" if frozen else "delisted_in_month")
            else:
                self.cache[key] = (0.0, "source_gap" if frozen else "unresolved")
        return self.cache[key]

    def ret(self, t: pd.Timestamp, s: str):
        r1, st = self._close_ret(t, s)
        if self.mode != "open" or st != "ok":
            return r1, st
        d0 = self._next_session(t)
        d1 = self._next_session(t + pd.offsets.MonthEnd(1))
        if d0 is None or d1 is None or s not in self.O.columns:
            self.used_close += 1
            return r1, st
        o0, o1 = self.O.at[d0, s], self.O.at[d1, s]
        same = s not in self.seg_d.columns or self.seg_d.at[d0, s] == self.seg_d.at[d1, s]
        if np.isfinite(o0) and np.isfinite(o1) and o0 > 0 and same:
            self.used_open += 1
            return float(o1 / o0 - 1.0), "ok"
        self.used_close += 1
        return r1, st


def load_tiingo_second_source_series() -> dict[str, dict[str, pd.Series]]:
    """
    Loads independent Tiingo EOD `adjClose` and `adjOpen` series from:
      1) `outputs/tech_top1_independent_audit_20261103/tiingo/*.json` (full EOD rows incl. `adjOpen`, `adjClose`)
      2) `research/sector_stock_momentum/data/raw_tiingo/*.json` (`adjclose`)
      3) `research/sector_stock_momentum/data/raw_ndx/*.json` (where `source == 'tiingo'`)
    """
    store = {}
    if TIINGO_AUDIT_DIR.exists():
        for fn in sorted(os.listdir(TIINGO_AUDIT_DIR)):
            if not fn.endswith(".json") or fn.startswith("_"):
                continue
            j = json.load(open(TIINGO_AUDIT_DIR / fn))
            rows = j.get("rows", [])
            if not rows:
                continue
            idx = pd.to_datetime([r["date"][:10] for r in rows])
            ac = pd.Series([r.get("adjClose") for r in rows], index=idx, dtype=float)
            ao = pd.Series([r.get("adjOpen") for r in rows], index=idx, dtype=float)
            ac = ac[~ac.index.duplicated(keep="last")].sort_index()
            ao = ao[~ao.index.duplicated(keep="last")].sort_index()
            store[j["symbol"]] = {"adjClose": ac, "adjOpen": ao, "origin": "tiingo_full_eod"}

    for sub_dir, tag in [(DATA_DIR / "raw_tiingo", "raw_tiingo"), (DATA_DIR / "raw_ndx", "raw_ndx_tiingo")]:
        if not sub_dir.exists():
            continue
        for fn in sorted(os.listdir(sub_dir)):
            if not fn.endswith(".json") or fn.startswith("_"):
                continue
            j = json.load(open(sub_dir / fn))
            if sub_dir.name == "raw_ndx" and j.get("source") != "tiingo":
                continue
            sym = j["symbol"]
            if sym in store:
                continue
            idx = pd.to_datetime(j["dates"])
            ac = pd.Series(j["adjclose"], index=idx, dtype=float)
            ac = ac[~ac.index.duplicated(keep="last")].sort_index()
            store[sym] = {"adjClose": ac, "adjOpen": None, "origin": tag}

    return store


def run_step2_tiingo_crosscheck(U: dict, px_eng: CleanRoomPriceEngine):
    """
    Cross-checks every monthly holding in `QQQ_Full100__T1_SetA_Price_Only__lgbm__Top1.csv`
    against independent Tiingo second-source prices (`adjOpen` open-to-open and `adjClose` next-session close).
    """
    tiingo_store = load_tiingo_second_source_series()
    orig_ledger = pd.read_csv(ORIG_LEDGER_DIR / "QQQ_Full100__T1_SetA_Price_Only__lgbm__Top1.csv", parse_dates=["month"])
    sess = U["daily"]["SPY"].dropna().index

    rows = []
    for r in orig_ledger.itertuples():
        hold_m = pd.Timestamp(r.month)
        form_t = hold_m - pd.offsets.MonthEnd(1)
        tk = str(r.picks)
        prim_ret, prim_st = px_eng.ret(form_t, tk)
        prim_src = U["price_source"].get(tk, "unknown")

        i0 = sess.searchsorted(form_t, side="right")
        i1 = sess.searchsorted(hold_m, side="right")
        d0 = sess[i0] if i0 < len(sess) else None
        d1 = sess[i1] if i1 < len(sess) else None

        t_info = tiingo_store.get(tk)
        t_oo_ret = np.nan
        t_cc_ret = np.nan
        t_orig = "not_yet_cached"
        if t_info is not None and d0 is not None and d1 is not None:
            t_orig = t_info["origin"]
            ac = t_info["adjClose"]
            ao = t_info["adjOpen"]
            if ao is not None and d0 in ao.index and d1 in ao.index and ao.at[d0] > 0:
                t_oo_ret = float(ao.at[d1] / ao.at[d0] - 1.0)
            if ac is not None and d0 in ac.index and d1 in ac.index and ac.at[d0] > 0:
                t_cc_ret = float(ac.at[d1] / ac.at[d0] - 1.0)

        rows.append({
            "formation_month": form_t.strftime("%Y-%m-%d"),
            "holding_month": hold_m.strftime("%Y-%m-%d"),
            "ticker": tk,
            "orig_ledger_gross": round(float(r.gross), 6),
            "cleanroom_primary_gross": round(float(prim_ret), 6),
            "diff_orig_vs_cleanroom_bps": round(float((prim_ret - r.gross) * 10000), 2),
            "primary_source": prim_src,
            "entry_session": d0.strftime("%Y-%m-%d") if d0 is not None else "",
            "exit_session": d1.strftime("%Y-%m-%d") if d1 is not None else "",
            "tiingo_origin": t_orig,
            "tiingo_open_to_open_ret": round(float(t_oo_ret), 6) if np.isfinite(t_oo_ret) else np.nan,
            "tiingo_close_t1_ret": round(float(t_cc_ret), 6) if np.isfinite(t_cc_ret) else np.nan,
            "diff_primary_vs_tiingo_oo_bps": round(float((prim_ret - t_oo_ret) * 10000), 2) if np.isfinite(t_oo_ret) else np.nan,
        })

    df_check = pd.DataFrame(rows)
    df_check.to_csv(OUT_DIR / "step2_tiingo_vs_primary_crosscheck.csv", index=False)
    return df_check


def main():
    print("Step 2: Loading clean-room price/open/sector engine from raw files...", flush=True)
    U = load_cleanroom_prices_and_universe()
    px_eng = CleanRoomPriceEngine(U, mode="open")
    df_check = run_step2_tiingo_crosscheck(U, px_eng)

    max_diff_orig = df_check["diff_orig_vs_cleanroom_bps"].abs().max()
    has_t_oo = df_check["diff_primary_vs_tiingo_oo_bps"].notna()
    has_t_any = df_check["tiingo_close_t1_ret"].notna()
    med_abs_t_oo = df_check.loc[has_t_oo, "diff_primary_vs_tiingo_oo_bps"].abs().median() if has_t_oo.any() else np.nan

    print(f"   Daily matrix shape: {U['daily'].shape}, Monthly matrix shape: {U['P'].shape}")
    print(f"   Clean-room primary gross vs original ledger gross across 140 holding months: max |diff| = {max_diff_orig:.4f} bps")
    print(f"   Holdings covered by independent Tiingo series right now: {int(has_t_any.sum())}/140 months ({int(has_t_oo.sum())}/140 with full Tiingo adjOpen)")
    print(f"   Median |Primary Open-to-Open vs Tiingo adjOpen-to-adjOpen diff|: {med_abs_t_oo:.2f} bps")


if __name__ == "__main__":
    main()
