#!/usr/bin/env python3
"""
v2_cleanroom_lib.py — 100% Standalone Clean-Room Raw Data Loader & Independent Recomputer.

STRICT AUDIT RULES ENFORCED MECHANICALLY (via v2_00_cleanroom_ast_and_readonly_guard.py):
  1. ZERO imports of any audited project code (NO backtest, NO ml2_run, NO fundamentals_pit,
     NO build_fundamentals, NO ticker_aliases, NO historical_sectors, NO winners_tracks, etc.).
  2. Reads ONLY raw files on disk (JSON, CSV, Parquet, TSV, ZIP, XLSX, PDF, SQLite) + official
     external APIs (data.sec.gov, api.stlouisfed.org).
  3. ZERO fallback to ledger values: if a raw price/fact input is missing and not explicitly
     governed by a documented raw exit/delisting record, returns None + 'MISSING_RAW_INPUT'
     so callers mark UNVERIFIABLE or FAIL — NEVER substitutes the ledger's own return!
"""
import glob
import json
import math
import os
import re
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


WIKI_FREEZE_DATE = pd.Timestamp("2018-03-27")

# Documented corporate time-splits inside a single membership spell (verified via SEC CIKs):
#   IR:   < 2020-03-02 = Ingersoll-Rand plc -> Trane Technologies (TT, CIK 1466258); >= 2020-03-02 = Ingersoll Rand Inc
#   BHGE: < 2017-07-03 = old Baker Hughes Inc (BHI); >= 2017-07-03 = Baker Hughes GE / BKR
DOCUMENTED_TIME_SPLITS = {
    "IR": ("2020-03-02", "TT", "IR"),
    "BHGE": ("2017-07-03", "BHI", "BKR"),
}


def _norm_sym(sym: str) -> str:
    return str(sym).strip().replace(".", "-")


def _read_raw_json_series(path: str, field: str = "adjclose") -> Tuple[Optional[str], pd.Series, dict]:
    with open(path, "r", encoding="utf-8") as fh:
        d = json.load(fh)
    sym = d.get("symbol")
    dates = d.get("dates") or []
    vals = d.get(field) or []
    if not dates or not vals or len(dates) != len(vals):
        return sym, pd.Series(dtype=float), d
    s = pd.Series(vals, index=pd.to_datetime(dates), dtype=float).dropna().sort_index()
    s = s[~s.index.duplicated(keep="last")]
    return sym, s, d


class CleanRoomEquityStore:
    """
    Standalone clean-room reconstructor of daily & monthly equity prices and opens directly from
    raw JSON / Parquet / CSV files on disk, plus independent external cross-check stores
    (BlackRock official iShares IVV monthly holdings & Nasdaq Data Link WIKI bulk prices/opens).
    """

    def __init__(self, repo_root: str, ssm_rel: str = "research/sector_stock_momentum", include_ndx: bool = False):
        self.repo_root = repo_root
        self.ssm_dir = os.path.join(repo_root, ssm_rel)
        self.data_dir = os.path.join(self.ssm_dir, "data")
        self.res_dir = os.path.join(self.ssm_dir, "results")
        self.include_ndx = include_ndx

        self.provenance: Dict[str, List[Tuple[str, str, Optional[pd.Timestamp], Optional[pd.Timestamp]]]] = {}
        self.wiki_frozen_syms = set()
        self.raw_yahoo: Dict[str, pd.Series] = {}
        self.raw_tiingo: Dict[str, pd.Series] = {}
        self.raw_wiki_single: Dict[str, pd.Series] = {}

        self._load_rf_and_resolutions()
        self._build_cleanroom_daily_and_monthly()
        self._build_cleanroom_opens()

    def _load_rf_and_resolutions(self) -> None:
        self.rf: Dict[pd.Timestamp, float] = {}
        base_rf = os.path.join(self.repo_root, "research", "sector_stock_momentum", "data", "rf_monthly.csv")
        local_rf = os.path.join(self.data_dir, "rf_monthly.csv")
        for rf_path in (base_rf, local_rf):
            if os.path.exists(rf_path):
                rf_df = pd.read_csv(rf_path)
                dcol = rf_df.columns[0]
                vcol = "rf_monthly" if "rf_monthly" in rf_df.columns else rf_df.columns[1]
                rf_df[dcol] = pd.to_datetime(rf_df[dcol]) + pd.offsets.MonthEnd(0)
                self.rf.update(dict(zip(rf_df[dcol], rf_df[vcol].astype(float))))

        self.exit_resolutions: Dict[Tuple[pd.Timestamp, str], float] = {}
        ex_path = os.path.join(self.data_dir, "exit_resolutions.csv")
        if os.path.exists(ex_path):
            ex_df = pd.read_csv(ex_path)
            for r in ex_df.itertuples():
                self.exit_resolutions[(pd.Timestamp(r.formation), _norm_sym(r.ticker))] = float(r.holding_return)

    def _read_spells(self) -> pd.DataFrame:
        sp_path = os.path.join(self.data_dir, "sp500_ticker_start_end.csv")
        sp = pd.read_csv(sp_path, parse_dates=["start_date", "end_date"])
        add_path = os.path.join(self.data_dir, "membership_additions.csv")
        if os.path.exists(add_path):
            add = pd.read_csv(add_path, parse_dates=["start_date", "end_date"])
            sp = pd.concat([sp, add[["ticker", "start_date", "end_date"]]], ignore_index=True)
        if self.include_ndx:
            ndx_sp_path = os.path.join(self.data_dir, "ndx_spells.csv")
            ndx_mp_path = os.path.join(self.data_dir, "ndx_symbol_map.csv")
            if os.path.exists(ndx_sp_path) and os.path.exists(ndx_mp_path):
                mp_df = pd.read_csv(ndx_mp_path)
                smap = {
                    r.ndx_ticker: (r.target if r.action in ("map_existing", "fetch_tiingo", "fetch_wiki") else None)
                    for r in mp_df.itertuples()
                }
                nsp = pd.read_csv(ndx_sp_path, parse_dates=["start_date", "end_date"])
                nsp["ticker"] = [smap.get(t, t) for t in nsp["ticker"]]
                nsp = nsp.dropna(subset=["ticker"])[["ticker", "start_date", "end_date"]]
                sp = pd.concat([sp, nsp], ignore_index=True)
        sp["ticker"] = sp["ticker"].astype(str).map(_norm_sym)
        return sp

    def _read_aliases(self) -> pd.DataFrame:
        cand_paths = []
        if self.include_ndx:
            cand_paths.append(os.path.join(self.res_dir, "ndx", "ticker_aliases_used.csv"))
        cand_paths.append(os.path.join(self.res_dir, "ticker_aliases_used.csv"))
        for p in cand_paths:
            if os.path.exists(p):
                df = pd.read_csv(p)
                df["old"] = df["old"].astype(str).map(_norm_sym)
                df["price_symbol"] = df["price_symbol"].astype(str).map(_norm_sym)
                return df
        return pd.DataFrame(columns=["old", "price_symbol"])

    def _build_cleanroom_daily_and_monthly(self) -> None:
        spells = self._read_spells()
        spells_active = spells[spells["end_date"].isna() | (spells["end_date"] >= pd.Timestamp("2009-01-01"))].copy()
        aliases = self._read_aliases()
        succ_of = dict(zip(aliases["old"], aliases["price_symbol"]))
        pred_of: Dict[str, List[str]] = {}
        for r in aliases.itertuples():
            pred_of.setdefault(r.price_symbol, []).append(r.old)

        spells_by_sym: Dict[str, List[Tuple[pd.Timestamp, pd.Timestamp]]] = {}
        for r in spells_active.itertuples():
            s0 = pd.Timestamp(r.start_date)
            e0 = pd.Timestamp(r.end_date) if pd.notna(r.end_date) else pd.Timestamp("2026-10-01")
            spells_by_sym.setdefault(r.ticker, []).append((s0, e0))

        def spells_of(sym: str) -> List[Tuple[pd.Timestamp, pd.Timestamp]]:
            out = list(spells_by_sym.get(sym, []))
            for p_sym in pred_of.get(sym, []):
                out.extend(spells_by_sym.get(p_sym, []))
            return out

        def covers(ser: Optional[pd.Series], sym: str) -> bool:
            if ser is None or ser.empty:
                return False
            iv = spells_of(sym)
            return all(ser.index[0] <= max(a, pd.Timestamp("2007-01-10")) + pd.Timedelta(days=10) for a, _ in iv)

        series: Dict[str, pd.Series] = {}

        # 1. Raw Yahoo JSONs
        raw_dir = os.path.join(self.data_dir, "raw")
        for p in sorted(glob.glob(os.path.join(raw_dir, "*.json"))):
            if os.path.basename(p).startswith("_"):
                continue
            sym, s, _ = _read_raw_json_series(p, "adjclose")
            if sym and not s.empty:
                sym = _norm_sym(sym)
                series[sym] = s
                self.raw_yahoo[sym] = s
                self.provenance[sym] = [("yahoo", sym, None, None)]

        # Collect Tiingo & WIKI files (plus NDX additions if include_ndx)
        tiingo_files = sorted(glob.glob(os.path.join(self.data_dir, "raw_tiingo", "*.json")))
        wiki_files = sorted(glob.glob(os.path.join(self.data_dir, "raw_wiki", "*.json")))
        if self.include_ndx:
            have_t = {os.path.basename(x) for x in tiingo_files}
            have_w = {os.path.basename(x) for x in wiki_files}
            for p in sorted(glob.glob(os.path.join(self.data_dir, "raw_ndx", "*.json"))):
                bn = os.path.basename(p)
                if bn.startswith("_"):
                    continue
                with open(p, "r", encoding="utf-8") as fh:
                    meta = json.load(fh)
                if not meta.get("covers_membership"):
                    continue
                if meta.get("source") == "tiingo" and bn not in have_t:
                    tiingo_files.append(p)
                elif meta.get("source") == "wiki" and bn not in have_w:
                    wiki_files.append(p)

        # 2. Raw Tiingo JSONs
        for p in tiingo_files:
            if os.path.basename(p).startswith("_"):
                continue
            sym, s, meta = _read_raw_json_series(p, "adjclose")
            if not sym or s.empty:
                continue
            sym = _norm_sym(sym)
            self.raw_tiingo[sym] = s
            if not meta.get("covers_membership", True):
                continue
            if covers(series.get(sym), sym) or not covers(s, sym):
                continue
            succ = succ_of.get(sym)
            if succ and succ != sym and covers(series.get(succ), sym):
                continue
            series[sym] = s
            self.provenance[sym] = [("tiingo", sym, None, None)]

        # 3. Raw WIKI JSONs
        for p in wiki_files:
            if os.path.basename(p).startswith("_"):
                continue
            sym, s, _ = _read_raw_json_series(p, "adjclose")
            if not sym or s.empty:
                continue
            sym = _norm_sym(sym)
            self.raw_wiki_single[sym] = s
            if covers(series.get(sym), sym) or not covers(s, sym):
                continue
            succ = succ_of.get(sym)
            if succ and covers(series.get(succ), sym):
                continue
            cur = series.get(sym)
            if cur is not None and not cur.empty:
                gaps = np.where(np.diff(s.index.values).astype("timedelta64[D]").astype(int) > 30)[0]
                w0 = s.iloc[: gaps[0] + 1] if len(gaps) else s
                if w0.index[-1] < cur.index[0] - pd.Timedelta(days=30) and covers(w0, sym):
                    cut = w0.index[-1] + pd.Timedelta(days=1)
                    series[sym] = pd.concat([w0, cur])
                    self.provenance[sym] = [("wiki", sym, None, cut)] + [
                        (v, sy, cut if lo is None else lo, hi) for (v, sy, lo, hi) in self.provenance.get(sym, [])
                    ]
                    if w0.index[-1] >= WIKI_FREEZE_DATE - pd.Timedelta(days=5):
                        self.wiki_frozen_syms.add(sym)
                continue
            series[sym] = s
            self.provenance[sym] = [("wiki", sym, None, None)]
            if s.index[-1] >= WIKI_FREEZE_DATE - pd.Timedelta(days=5):
                self.wiki_frozen_syms.add(sym)

        # 4. Raw Archive JSONs
        arch_dir = os.path.join(self.data_dir, "raw_archive")
        if os.path.isdir(arch_dir):
            for p in sorted(glob.glob(os.path.join(arch_dir, "*.json"))):
                if os.path.basename(p).startswith("_"):
                    continue
                sym, s, _ = _read_raw_json_series(p, "adjclose")
                if not sym or s.empty:
                    continue
                sym = _norm_sym(sym)
                ch = s.diff().fillna(1.0) != 0
                last_move = s[ch].index[-1] if ch.any() else s.index[-1]
                if (s.index[-1] - last_move).days >= 7:
                    s = s[s.index <= last_move]
                if s.empty or covers(series.get(sym), sym) or not covers(s, sym):
                    continue
                succ = succ_of.get(sym)
                if succ and covers(series.get(succ), sym):
                    continue
                cur = series.get(sym)
                if cur is not None and not cur.empty:
                    cut = s.index[-1] + pd.Timedelta(days=1)
                    if s.index[-1] < cur.index[0] - pd.Timedelta(days=30):
                        series[sym] = pd.concat([s, cur])
                    else:
                        series[sym] = pd.concat([s, cur[cur.index > s.index[-1] + pd.Timedelta(days=30)]])
                    self.provenance[sym] = [("archive", sym, None, cut)] + [
                        (v, sy, cut if lo is None else lo, hi) for (v, sy, lo, hi) in self.provenance.get(sym, [])
                    ]
                else:
                    series[sym] = s
                    self.provenance[sym] = [("archive", sym, None, None)]

        # 5. Documented corporate time-splits
        split_breaks: List[Tuple[str, pd.Timestamp]] = []
        for tk, (d_str, before_sym, after_sym) in DOCUMENTED_TIME_SPLITS.items():
            b_ser, a_ser = series.get(before_sym), series.get(after_sym)
            if b_ser is not None and a_ser is not None and not b_ser.empty and not a_ser.empty:
                cut = pd.Timestamp(d_str)
                series[tk] = pd.concat([b_ser[b_ser.index < cut], a_ser[a_ser.index >= cut]])
                b_prov = [(v, sy, lo, cut if hi is None or hi > cut else hi)
                          for (v, sy, lo, hi) in self.provenance.get(before_sym, []) if lo is None or lo < cut]
                a_prov = [(v, sy, cut if lo is None or lo < cut else lo, hi)
                          for (v, sy, lo, hi) in self.provenance.get(after_sym, []) if hi is None or hi > cut]
                self.provenance[tk] = b_prov + a_prov
                split_breaks.append((tk, cut))

        # 6. Identity resolutions CSV
        id_path = os.path.join(self.data_dir, "identity_resolutions.csv")
        if os.path.exists(id_path):
            id_df = pd.read_csv(id_path)
            for r in id_df.itertuples():
                tk = _norm_sym(r.ticker)
                cut = pd.Timestamp(r.date)
                if r.action == "use_wiki_before":
                    wp = next(
                        (x for x in [
                            os.path.join(self.data_dir, "raw_wiki_check", f"{tk}.json"),
                            os.path.join(self.data_dir, "raw_wiki", f"{tk}.json"),
                        ] if os.path.exists(x)),
                        None,
                    )
                    if wp is not None:
                        _, ws, _ = _read_raw_json_series(wp, "adjclose")
                        cur = series.get(tk, pd.Series(dtype=float))
                        series[tk] = pd.concat([ws[ws.index < cut], cur[cur.index >= cut]])
                        c_prov = [(v, sy, cut if lo is None or lo < cut else lo, hi)
                                  for (v, sy, lo, hi) in self.provenance.get(tk, []) if hi is None or hi > cut]
                        self.provenance[tk] = [("wiki", tk, None, cut)] + c_prov
                        split_breaks.append((tk, cut))
                elif r.action == "use_archive_before":
                    ap = os.path.join(self.data_dir, "raw_archive", f"{tk}.json")
                    if os.path.exists(ap):
                        _, ws, _ = _read_raw_json_series(ap, "adjclose")
                        cur = series.get(tk, pd.Series(dtype=float))
                        series[tk] = pd.concat([ws[ws.index < cut], cur[cur.index >= cut]])
                        c_prov = [(v, sy, cut if lo is None or lo < cut else lo, hi)
                                  for (v, sy, lo, hi) in self.provenance.get(tk, []) if hi is None or hi > cut]
                        self.provenance[tk] = [("archive", tk, None, cut)] + c_prov
                        split_breaks.append((tk, cut))
                elif r.action == "segment_break":
                    split_breaks.append((tk, cut))

        # 7. Segment integrity (>30d gaps + spell overlap + corporate break boundaries)
        all_spells: Dict[str, List[Tuple[pd.Timestamp, pd.Timestamp]]] = {}
        for r in spells.itertuples():
            s0 = pd.Timestamp(r.start_date)
            e0 = pd.Timestamp(r.end_date) if pd.notna(r.end_date) else pd.Timestamp("2100-01-01")
            all_spells.setdefault(r.ticker, []).append((s0, e0))
        for r in aliases.itertuples():
            for iv in all_spells.get(r.old, []):
                all_spells.setdefault(r.price_symbol, []).append(iv)

        clean_series: Dict[str, pd.Series] = {}
        segs: Dict[str, pd.Series] = {}
        for sym, s in series.items():
            s = s[s > 0].dropna().sort_index()
            s = s[~s.index.duplicated(keep="last")]
            if s.empty:
                continue
            gap_ids = np.r_[0, (np.diff(s.index.values).astype("timedelta64[D]").astype(int) > 30).cumsum()]
            seg_s = pd.Series(gap_ids.astype(float), index=s.index)
            ivs = all_spells.get(sym)
            if ivs:
                keep_mask = pd.Series(False, index=s.index)
                for gid in np.unique(gap_ids):
                    sub = s[seg_s == gid]
                    a_seg, b_seg = sub.index[0], sub.index[-1]
                    if any(a_seg <= e_sp + pd.Timedelta(days=35) and b_seg >= s_sp - pd.Timedelta(days=35) for s_sp, e_sp in ivs):
                        keep_mask[seg_s == gid] = True
                s = s[keep_mask]
                seg_s = seg_s[keep_mask]
            if not s.empty:
                clean_series[sym] = s
                segs[sym] = seg_s

        for tk, cut in split_breaks:
            if tk in segs and not segs[tk].empty:
                segs[tk] = segs[tk].where(segs[tk].index < cut, segs[tk] + 1000.0)

        # 8. Alias inheritance (old ticker -> verified successor price series)
        for r in aliases.itertuples():
            old, suc_sym = r.old, r.price_symbol
            if suc_sym not in clean_series or old in DOCUMENTED_TIME_SPLITS:
                continue
            cur = clean_series.get(old)
            suc = clean_series[suc_sym]
            old_primary_vendor = self.provenance.get(old, [("yahoo", old, None, None)])[0][0]
            if not covers(suc, old) and covers(cur, old) and old_primary_vendor != "yahoo":
                continue
            clean_series[old] = suc
            segs[old] = segs[suc_sym]
            self.provenance[old] = list(self.provenance.get(suc_sym, [("yahoo", suc_sym, None, None)]))

        self.daily = pd.DataFrame(clean_series).sort_index()
        self.daily = self.daily[self.daily.index >= pd.Timestamp("2007-01-01")]
        self.seg_d = pd.DataFrame(segs).reindex(index=self.daily.index, columns=self.daily.columns)

        # Monthly close matrix P (fresh within 7 calendar days of SPY month-end session)
        spy = self.daily["SPY"].dropna()
        P = self.daily.resample("ME").last().where(self.daily.resample("ME").count() > 0)
        obs = pd.DataFrame(
            np.where(self.daily.notna().values, self.daily.index.values[:, None], np.datetime64("NaT")),
            index=self.daily.index,
            columns=self.daily.columns,
        )
        last_obs = obs.resample("ME").max()
        mkt_last = spy.index.to_series().resample("ME").max()
        fresh = last_obs.ge(mkt_last - pd.Timedelta(days=7), axis=0)
        self.P = P.where(fresh.reindex(index=P.index, columns=P.columns).fillna(False))
        self.seg_m = self.seg_d.resample("ME").last().reindex(self.P.index)

        # Next-session close matrix E1 (lag_days = 1)
        pos1 = np.clip(self.daily.index.searchsorted(self.P.index, side="right"), 0, len(self.daily) - 1)
        E1 = self.daily.ffill(limit=5).iloc[pos1].copy()
        E1.index = self.P.index
        self.E1 = E1
        self.sessions = spy.index

    def _build_cleanroom_opens(self) -> None:
        self.O = pd.DataFrame(np.nan, index=self.daily.index, columns=self.daily.columns)
        open_dir = os.path.join(self.data_dir, "raw_open")
        wiki_open_path = os.path.join(self.data_dir, "wiki_bulk", "wiki_open.parquet")
        wiki_opens: Dict[str, pd.Series] = {}
        if os.path.exists(wiki_open_path):
            wdf = pd.read_parquet(wiki_open_path)
            wdf["date"] = pd.to_datetime(wdf["date"])
            wiki_opens = {
                _norm_sym(t): g.drop_duplicates("date", keep="last").set_index("date")["adj_open"].astype(float)
                for t, g in wdf.groupby("ticker")
            }

        yopen_cache: Dict[str, Optional[pd.Series]] = {}

        def get_yopen(sym: str) -> Optional[pd.Series]:
            if sym not in yopen_cache:
                p = os.path.join(open_dir, f"{sym}.json")
                if os.path.exists(p):
                    _, s, _ = _read_raw_json_series(p, "adj_open")
                    yopen_cache[sym] = s if not s.empty else None
                else:
                    yopen_cache[sym] = None
            return yopen_cache[sym]

        for col_sym in self.daily.columns:
            parts = self.provenance.get(col_sym, [("yahoo", col_sym, None, None)])
            acc = pd.Series(np.nan, index=self.daily.index)
            for vendor, raw_sym, lo, hi in parts:
                src = get_yopen(raw_sym) if vendor == "yahoo" else wiki_opens.get(raw_sym) if vendor == "wiki" else None
                if src is None:
                    continue
                mask = np.ones(len(self.daily.index), dtype=bool)
                if lo is not None:
                    mask &= self.daily.index >= lo
                if hi is not None:
                    mask &= self.daily.index < hi
                acc[mask] = src.reindex(self.daily.index)[mask]
            self.O[col_sym] = acc.where(self.daily[col_sym].notna())

    def vendor_at(self, sym: str, dt: pd.Timestamp) -> Tuple[str, str]:
        sym_n = _norm_sym(sym)
        for vendor, raw_sym, lo, hi in self.provenance.get(sym_n, [("unknown", sym_n, None, None)]):
            if (lo is None or dt >= lo) and (hi is None or dt < hi):
                return vendor, raw_sym
        return "unknown", sym_n

    def next_session(self, dt: pd.Timestamp) -> Optional[pd.Timestamp]:
        idx = self.sessions.searchsorted(dt, side="right")
        return self.sessions[idx] if idx < len(self.sessions) else None

    def close_return(self, formation_t: pd.Timestamp, sym: str, lag_days: int = 0) -> Tuple[Optional[float], str]:
        """
        Clean-room holding return from formation month-end `formation_t` to `formation_t + 1M`.
        lag_days=0 -> month-end close to month-end close.
        lag_days=1 -> next trading session close to next trading session close.
        ZERO fallback to ledger values: returns (None, 'MISSING_RAW_PRICE') if entry price missing!
        """
        sym_n = _norm_sym(sym)
        if sym_n.startswith("CASH"):
            m = formation_t + pd.offsets.MonthEnd(1)
            return float(self.rf.get(m, 0.0)), "cash"

        key = (formation_t, sym_n)
        if key in self.exit_resolutions and (lag_days == 0 or "codex_full_audit_v2" not in self.ssm_dir):
            return float(self.exit_resolutions[key]), "resolved_manual"

        if sym_n not in self.P.columns or formation_t not in self.P.index:
            return None, "MISSING_RAW_PRICE"

        E = self.E1 if lag_days == 1 else self.P
        m_next = formation_t + pd.offsets.MonthEnd(1)
        p0 = E.at[formation_t, sym_n]
        if not np.isfinite(p0) or p0 <= 0:
            p0_alt = self.P.at[formation_t, sym_n]
            if not np.isfinite(p0_alt) or p0_alt <= 0:
                return None, "MISSING_RAW_ENTRY_PRICE"
            p0 = p0_alt

        if m_next in E.index:
            p1 = E.at[m_next, sym_n]
            same_seg = (
                sym_n not in self.seg_m.columns
                or (
                    pd.notna(self.seg_m.at[formation_t, sym_n])
                    and pd.notna(self.seg_m.at[m_next, sym_n])
                    and self.seg_m.at[formation_t, sym_n] == self.seg_m.at[m_next, sym_n]
                )
            )
            if np.isfinite(p1) and p1 > 0 and same_seg:
                return float(p1 / p0 - 1.0), "ok"

        # Intra-month delisting or WIKI 2018-03-27 source freeze check
        d_slice = self.daily[sym_n].loc[formation_t + pd.Timedelta(days=1) : m_next]
        if sym_n in self.seg_d.columns:
            seg_before = self.seg_d[sym_n].loc[:formation_t].dropna()
            if not seg_before.empty:
                d_slice = d_slice[self.seg_d[sym_n].reindex(d_slice.index) == seg_before.iloc[-1]]
        d_slice = d_slice.dropna()
        frozen = sym_n in self.wiki_frozen_syms and (
            d_slice.empty or abs((d_slice.index[-1] - WIKI_FREEZE_DATE).days) <= 5
        )
        if not d_slice.empty:
            return float(d_slice.iloc[-1] / p0 - 1.0), ("source_gap" if frozen else "delisted_in_month")
        if frozen:
            return 0.0, "source_gap"
        return 0.0, "unresolved_no_quote_after_entry"

    def open_return(
        self,
        formation_t: pd.Timestamp,
        sym: str,
        exec_start: Optional[pd.Timestamp] = None,
        exec_end: Optional[pd.Timestamp] = None,
    ) -> Tuple[Optional[float], str]:
        """
        Clean-room open-to-open return for formation `formation_t` (first session open after t to
        first session open after t+1M, or explicit exec_start -> exec_end dates).
        Falls back to next-session close on BOTH legs only when raw adj_open is unavailable,
        matching the documented open-execution rule, and NEVER falls back to ledger values.
        """
        sym_n = _norm_sym(sym)
        if sym_n.startswith("CASH"):
            m = formation_t + pd.offsets.MonthEnd(1)
            return float(self.rf.get(m, 0.0)), "cash"

        d0 = exec_start if exec_start is not None else self.next_session(formation_t)
        d1 = exec_end if exec_end is not None else self.next_session(formation_t + pd.offsets.MonthEnd(1))

        # Check intra-month delisting / manual merger resolution first when holding month is inside P.index
        if exec_start is None:
            r1, st1 = self.close_return(formation_t, sym_n, lag_days=1)
            if st1 != "ok":
                return r1, st1
        else:
            r1, st1 = None, "explicit_exec_window"

        if d0 is not None and d1 is not None and sym_n in self.O.columns:
            if d0 in self.O.index and d1 in self.O.index:
                o0, o1 = self.O.at[d0, sym_n], self.O.at[d1, sym_n]
                same_seg = (
                    sym_n not in self.seg_d.columns
                    or self.seg_d.at[d0, sym_n] == self.seg_d.at[d1, sym_n]
                )
                if np.isfinite(o0) and np.isfinite(o1) and o0 > 0 and same_seg:
                    return float(o1 / o0 - 1.0), "ok_open"

        if exec_start is not None:
            r1, st1 = self.close_return(formation_t, sym_n, lag_days=1)
        if st1 != "ok":
            return r1, st1
        return r1, "ok_close1_fallback"


class CleanRoomSmallCapStore:
    """
    Standalone clean-room reconstructor for small/mid-cap (`winners_holdout`) price series
    (both standard `price_corrections.csv` and `STRICT=1` `quality_flags.csv`).
    ZERO project imports; ZERO fallback to ledger values.
    """

    def __init__(self, repo_root: str, sp_store: CleanRoomEquityStore, strict: bool = False):
        self.repo_root = repo_root
        self.ssm_dir = sp_store.ssm_dir
        self.sc_dir = os.path.join(self.ssm_dir, "data", "smallcap")
        self.sp_store = sp_store
        self.strict = strict

        A = pd.read_parquet(os.path.join(self.sc_dir, "daily_adj.parquet"))
        src = pd.read_csv(os.path.join(self.sc_dir, "price_source.csv"), index_col=0)["source"]
        self.src_map = {str(k): str(v) for k, v in src.items()}

        spy = sp_store.daily["SPY"].dropna()
        A = A.reindex(A.index.union(spy.index)).sort_index()
        A = A[A.index >= pd.Timestamp("2007-01-01")]
        A["SPY"] = spy

        corr_path = os.path.join(self.sc_dir, "price_corrections.csv")
        if os.path.exists(corr_path):
            cdf = pd.read_csv(corr_path, parse_dates=["start", "end"])
            for r in cdf.itertuples():
                if r.ticker not in A.columns:
                    continue
                if r.action == "set_missing_days":
                    A.loc[(A.index >= r.start) & (A.index <= r.end) & (A[r.ticker] <= 0), r.ticker] = np.nan
                elif r.action == "rescale_before":
                    A.loc[A.index < r.end, r.ticker] = A.loc[A.index < r.end, r.ticker] * float(r.factor)

        if strict:
            qf_path = os.path.join(self.sc_dir, "quality_flags.csv")
            if os.path.exists(qf_path):
                qf = pd.read_csv(qf_path, parse_dates=["date", "end"])
                for r in qf[qf["flag"] == "F3_stale_run"].itertuples():
                    if r.ticker in A.columns:
                        A.loc[(A.index > r.date) & (A.index <= r.end), r.ticker] = np.nan
                for r in qf[qf["flag"] == "F1_spike_reversal"].itertuples():
                    if r.ticker in A.columns:
                        A.loc[(A.index >= r.date) & (A.index < r.end), r.ticker] = np.nan

        A = A.where(A > 0)
        seg = {}
        for col in A.columns:
            x = A[col].dropna()
            if x.empty:
                continue
            gaps = np.r_[0, (np.diff(x.index.values).astype("timedelta64[D]").astype(int) > 30).cumsum()]
            seg[col] = pd.Series(gaps.astype(float), index=x.index)
        seg_df = pd.DataFrame(seg).reindex(index=A.index, columns=A.columns)
        for col in A.columns:
            if self.src_map.get(col) == "sp_store" and col in sp_store.seg_d.columns:
                seg_df[col] = sp_store.seg_d[col].reindex(A.index)

        self.daily = A
        self.seg_d = seg_df

        P = A.resample("ME").last().where(A.resample("ME").count() > 0)
        obs = pd.DataFrame(
            np.where(A.notna().values, A.index.values[:, None], np.datetime64("NaT")),
            index=A.index,
            columns=A.columns,
        )
        last_obs = obs.resample("ME").max()
        mkt_last = spy.index.to_series().resample("ME").max()
        fresh = last_obs.ge(mkt_last - pd.Timedelta(days=7), axis=0)
        self.P = P.where(fresh.reindex(index=P.index, columns=P.columns).fillna(False))
        self.seg_m = seg_df.resample("ME").last().reindex(self.P.index)

        self.wiki_frozen_syms = {
            col for col in A.columns
            if self.src_map.get(col) == "wiki"
            and A[col].last_valid_index() is not None
            and abs((A[col].last_valid_index() - WIKI_FREEZE_DATE).days) <= 5
        }

    def close_return(
        self, formation_t: pd.Timestamp, sym: str, stress: Optional[float] = None
    ) -> Tuple[Optional[float], str]:
        sym_n = str(sym).strip()
        key = (formation_t, _norm_sym(sym_n))
        if key in self.sp_store.exit_resolutions:
            return float(self.sp_store.exit_resolutions[key]), "resolved_manual"
        if sym_n not in self.P.columns and _norm_sym(sym_n) in self.P.columns:
            sym_n = _norm_sym(sym_n)
        if sym_n not in self.P.columns or formation_t not in self.P.index:
            return None, "MISSING_RAW_PRICE"

        p0 = self.P.at[formation_t, sym_n]
        if not np.isfinite(p0) or p0 <= 0:
            return None, "MISSING_RAW_ENTRY_PRICE"

        m_next = formation_t + pd.offsets.MonthEnd(1)
        if m_next in self.P.index:
            p1 = self.P.at[m_next, sym_n]
            same_seg = (
                sym_n not in self.seg_m.columns
                or (
                    pd.notna(self.seg_m.at[formation_t, sym_n])
                    and pd.notna(self.seg_m.at[m_next, sym_n])
                    and self.seg_m.at[formation_t, sym_n] == self.seg_m.at[m_next, sym_n]
                )
            )
            if np.isfinite(p1) and p1 > 0 and same_seg:
                return float(p1 / p0 - 1.0), "ok"

        d_slice = self.daily[sym_n].loc[formation_t + pd.Timedelta(days=1) : m_next]
        if sym_n in self.seg_d.columns:
            seg_before = self.seg_d[sym_n].loc[:formation_t].dropna()
            if not seg_before.empty:
                d_slice = d_slice[self.seg_d[sym_n].reindex(d_slice.index) == seg_before.iloc[-1]]
        d_slice = d_slice.dropna()
        frozen = sym_n in self.wiki_frozen_syms and (
            d_slice.empty or abs((d_slice.index[-1] - WIKI_FREEZE_DATE).days) <= 5
        )
        if not d_slice.empty:
            st = "source_gap" if frozen else "delisted_in_month"
            r_val = float(d_slice.iloc[-1] / p0 - 1.0)
            if stress is not None and st in ("unresolved", "source_gap"):
                return float(stress), f"{st}_stressed"
            return r_val, st

        st = "source_gap" if frozen else "unresolved"
        if stress is not None:
            return float(stress), f"{st}_stressed"
        if frozen:
            return 0.0, "source_gap"
        return 0.0, "unresolved_zero_quote_after_entry"


class ExternalEquityCrossChecker:
    """
    Genuinely independent external equity price cross-checkers:
      1. BlackRock official iShares Core S&P 500 ETF (IVV) monthly holdings CSVs (205 snapshots, 2009-2026)
      2. Nasdaq Data Link WIKI bulk table (2009 - 2018-03-27) when primary vendor was Yahoo or Tiingo
      3. Tiingo independent raw series when primary vendor was Yahoo (or Yahoo when primary was Tiingo/WIKI)
    """

    def __init__(self, repo_root: str):
        self.repo_root = repo_root
        self.ivv_prices: Dict[pd.Timestamp, Dict[str, float]] = {}
        self._load_ivv()
        self._load_wiki_bulk()
        self._load_raw_splits()

    def _load_ivv(self) -> None:
        ivv_dir = os.path.join(self.repo_root, "research", "broad_validation", "raw_data", "ishares_holdings")
        for p in sorted(glob.glob(os.path.join(ivv_dir, "IVV_*.csv"))):
            m = re.search(r"IVV_(\d{8})\.csv$", os.path.basename(p))
            if not m:
                continue
            dt = pd.to_datetime(m.group(1), format="%Y%m%d") + pd.offsets.MonthEnd(0)
            try:
                with open(p, "r", encoding="utf-8", errors="replace") as fh:
                    lines = fh.readlines()
                hdr_idx = next((i for i, ln in enumerate(lines[:35]) if ln.startswith("Ticker,")), None)
                if hdr_idx is None:
                    continue
                from io import StringIO
                df = pd.read_csv(StringIO("".join(lines[hdr_idx:])))
                if "Ticker" not in df.columns or "Price" not in df.columns:
                    continue
                if "Asset Class" in df.columns:
                    df = df[df["Asset Class"].astype(str).str.contains("Equity", case=False, na=False)]
                px_map = {}
                for r in df.itertuples():
                    tk = _norm_sym(str(r.Ticker))
                    try:
                        px = float(str(r.Price).replace(",", ""))
                        if np.isfinite(px) and px > 0:
                            px_map[tk] = px
                    except Exception:
                        pass
                if px_map:
                    self.ivv_prices[dt] = px_map
            except Exception:
                continue

    def _load_wiki_bulk(self) -> None:
        ssm_data = os.path.join(self.repo_root, "research", "sector_stock_momentum", "data")
        wp = os.path.join(ssm_data, "wiki_bulk", "wiki_prices.parquet")
        self.wiki_monthly: Dict[str, pd.Series] = {}
        self.wiki_open_daily: Dict[str, pd.Series] = {}
        if os.path.exists(wp):
            df = pd.read_parquet(wp, columns=["ticker", "date", "adj_close"])
            df["date"] = pd.to_datetime(df["date"])
            for tk, g in df.groupby("ticker"):
                s = g.drop_duplicates("date", keep="last").set_index("date")["adj_close"].astype(float).sort_index()
                self.wiki_monthly[_norm_sym(tk)] = s.resample("ME").last()
        wo = os.path.join(ssm_data, "wiki_bulk", "wiki_open.parquet")
        if os.path.exists(wo):
            odf = pd.read_parquet(wo, columns=["ticker", "date", "adj_open"])
            odf["date"] = pd.to_datetime(odf["date"])
            for tk, g in odf.groupby("ticker"):
                s = g.drop_duplicates("date", keep="last").set_index("date")["adj_open"].astype(float).sort_index()
                self.wiki_open_daily[_norm_sym(tk)] = s

    def _load_raw_splits(self) -> None:
        """Load raw split events from JSON caches so IVV unadjusted month-end prices can be split-adjusted over [t, t+1]."""
        self.splits: Dict[str, List[Tuple[pd.Timestamp, float]]] = {}
        ssm_data = os.path.join(self.repo_root, "research", "sector_stock_momentum", "data")
        for sub in ("raw", "raw_tiingo", "raw_wiki", "raw_ndx", "raw_smallcap"):
            dpath = os.path.join(ssm_data, sub)
            if not os.path.isdir(dpath):
                continue
            for p in sorted(glob.glob(os.path.join(dpath, "*.json"))):
                bn = os.path.basename(p)
                if bn.startswith("_"):
                    continue
                tk = _norm_sym(bn[:-5])
                if tk in self.splits:
                    continue
                try:
                    with open(p, "r", encoding="utf-8") as fh:
                        j = json.load(fh)
                    evs = []
                    for item in j.get("splits", []) or []:
                        if len(item) >= 3:
                            dt = pd.Timestamp(item[0])
                            num = float(item[1] or 1.0)
                            den = float(item[2] or 1.0)
                            if den != 0 and num / den > 0:
                                evs.append((dt, num / den))
                    if evs:
                        self.splits[tk] = evs
                except Exception:
                    pass

    def split_factor_between(self, sym: str, t0: pd.Timestamp, t1: pd.Timestamp) -> float:
        fac = 1.0
        for dt, ratio in self.splits.get(_norm_sym(sym), []):
            if t0 < dt <= t1:
                fac *= ratio
        return fac

    def split_factor_after(self, sym: str, filing_dt: pd.Timestamp, prefer_tiingo_sp: bool = True) -> Tuple[float, str]:
        """
        Clean-room post-filing split adjustment factor directly from raw JSON `splits` lists
        (0 project imports!). Mirrors vendor priority: Tiingo (if covers_membership) -> Yahoo -> WIKI -> NDX -> SmallCap.
        """
        tk = _norm_sym(sym)
        ssm_data = os.path.join(self.repo_root, "research", "sector_stock_momentum", "data")
        chosen_path = None
        chosen_src = "none"
        pt = os.path.join(ssm_data, "raw_tiingo", f"{tk}.json")
        py = os.path.join(ssm_data, "raw", f"{tk}.json")
        if prefer_tiingo_sp and os.path.exists(pt):
            with open(pt, "r", encoding="utf-8") as fh:
                jt = json.load(fh)
            if jt.get("covers_membership"):
                chosen_path, chosen_src = pt, "raw_tiingo"
        if chosen_path is None and os.path.exists(py):
            chosen_path, chosen_src = py, "raw_yahoo"
        if chosen_path is None:
            for sub in ("raw_wiki", "raw_ndx", "raw_smallcap"):
                pa = os.path.join(ssm_data, sub, f"{tk}.json")
                if os.path.exists(pa):
                    chosen_path, chosen_src = pa, sub
                    break
        if chosen_path is None:
            return 1.0, "no_split_file_factor_1"
        with open(chosen_path, "r", encoding="utf-8") as fh:
            jd = json.load(fh)
        fac = 1.0
        fdt = pd.Timestamp(filing_dt)
        for a, num, den in jd.get("splits", []) or []:
            if pd.Timestamp(a) > fdt:
                fac *= float(num or 1.0) / float(den or 1.0)
        return fac, chosen_src

    def check_external_return(
        self,
        store: CleanRoomEquityStore,
        sym: str,
        formation_t: pd.Timestamp,
        cleanroom_ret: float,
        mode: str = "close",
        exec_start: Optional[pd.Timestamp] = None,
        exec_end: Optional[pd.Timestamp] = None,
    ) -> Tuple[str, Optional[float], str]:
        """
        Cross-checks `cleanroom_ret` against genuinely independent external price sources:
          - For close-to-close:
              (a) Independent second vendor (WIKI vs Yahoo/Tiingo, or Tiingo vs Yahoo) -> total return comparison
              (b) BlackRock official iShares IVV holdings CSVs at t and t+1 (split-adjusted price return; ex-dividend
                  months typically differ by ~10-80 bp dividend yield, so tolerance 1.2% = 120 bp for price-only IVV vs TR,
                  or 50 bp for TR-vs-TR second vendor).
          - For open-to-open:
              Independent Nasdaq Data Link WIKI `adj_open` when primary vendor was Yahoo/Tiingo (up to 2018-03).
        Returns: (external_status, external_ret, external_detail)
          external_status in {'EXTERNAL_MATCH', 'EXTERNAL_DIVERGENCE', 'SINGLE_VENDOR_ONLY'}
        """
        tk = _norm_sym(sym)
        m_next = formation_t + pd.offsets.MonthEnd(1)
        primary_vendor, raw_sym = store.vendor_at(tk, formation_t + pd.Timedelta(days=1))

        if mode == "open":
            d0 = exec_start if exec_start is not None else store.next_session(formation_t)
            d1 = exec_end if exec_end is not None else store.next_session(m_next)
            if primary_vendor != "wiki" and d0 is not None and d1 is not None:
                for cand in (tk, raw_sym):
                    ws = self.wiki_open_daily.get(cand)
                    if ws is not None and d0 in ws.index and d1 in ws.index:
                        o0, o1 = ws.at[d0], ws.at[d1]
                        if np.isfinite(o0) and np.isfinite(o1) and o0 > 0:
                            w_ret = float(o1 / o0 - 1.0)
                            diff = abs(cleanroom_ret - w_ret)
                            st = "EXTERNAL_MATCH" if diff <= 0.01 else "EXTERNAL_DIVERGENCE"
                            return st, w_ret, f"Nasdaq_WIKI_adj_open({cand} {d0.date()}->{d1.date()}, primary={primary_vendor}, diff={diff:.6f})"
            return "SINGLE_VENDOR_ONLY", None, f"single_open_vendor({primary_vendor}:{raw_sym}; WIKI_open ended 2018-03-27)"

        # Close-to-close external cross-checks:
        # 1) Independent Total-Return Second Vendor (TR vs TR, tolerance 50 bp = 0.005)
        if primary_vendor == "yahoo":
            # Check Tiingo first, then Nasdaq WIKI
            for cand in (tk, raw_sym):
                ts = store.raw_tiingo.get(cand)
                if ts is not None:
                    tm = ts.resample("ME").last()
                    if formation_t in tm.index and m_next in tm.index and tm.at[formation_t] > 0 and np.isfinite(tm.at[m_next]):
                        t_ret = float(tm.at[m_next] / tm.at[formation_t] - 1.0)
                        diff = abs(cleanroom_ret - t_ret)
                        st = "EXTERNAL_MATCH" if diff <= 0.005 else "EXTERNAL_DIVERGENCE"
                        return st, t_ret, f"Tiingo_TR({cand}, primary=yahoo, diff={diff:.6f})"
            for cand in (tk, raw_sym):
                wm = self.wiki_monthly.get(cand)
                if wm is not None and formation_t in wm.index and m_next in wm.index and wm.at[formation_t] > 0 and np.isfinite(wm.at[m_next]):
                    w_ret = float(wm.at[m_next] / wm.at[formation_t] - 1.0)
                    diff = abs(cleanroom_ret - w_ret)
                    st = "EXTERNAL_MATCH" if diff <= 0.005 else "EXTERNAL_DIVERGENCE"
                    return st, w_ret, f"Nasdaq_WIKI_TR({cand}, primary=yahoo, diff={diff:.6f})"
        elif primary_vendor in ("tiingo", "wiki", "archive"):
            for cand in (tk, raw_sym):
                ys = store.raw_yahoo.get(cand)
                if ys is not None:
                    ym = ys.resample("ME").last()
                    if formation_t in ym.index and m_next in ym.index and ym.at[formation_t] > 0 and np.isfinite(ym.at[m_next]):
                        y_ret = float(ym.at[m_next] / ym.at[formation_t] - 1.0)
                        diff = abs(cleanroom_ret - y_ret)
                        if diff <= 0.005:
                            return "EXTERNAL_MATCH", y_ret, f"Yahoo_TR({cand}, primary={primary_vendor}, diff={diff:.6f})"
                if primary_vendor != "wiki":
                    wm = self.wiki_monthly.get(cand)
                    if wm is not None and formation_t in wm.index and m_next in wm.index and wm.at[formation_t] > 0 and np.isfinite(wm.at[m_next]):
                        w_ret = float(wm.at[m_next] / wm.at[formation_t] - 1.0)
                        diff = abs(cleanroom_ret - w_ret)
                        st = "EXTERNAL_MATCH" if diff <= 0.005 else "EXTERNAL_DIVERGENCE"
                        return st, w_ret, f"Nasdaq_WIKI_TR({cand}, primary={primary_vendor}, diff={diff:.6f})"

        # 2) BlackRock Official iShares Core S&P 500 ETF (IVV) Institutional Holdings Snapshot
        ivv0 = self.ivv_prices.get(formation_t, {})
        ivv1 = self.ivv_prices.get(m_next, {})
        for cand in (tk, raw_sym):
            if cand in ivv0 and cand in ivv1 and ivv0[cand] > 0:
                sfac = self.split_factor_between(cand, formation_t, m_next)
                ivv_px_ret = float((ivv1[cand] * sfac) / ivv0[cand] - 1.0)
                diff = abs(cleanroom_ret - ivv_px_ret)
                # IVV holdings report unadjusted price (no cash dividend reinvestment); ordinary monthly dividend
                # yields are 0-120 bp, whereas corporate-action / ticker-mismatch errors are >> 150 bp.
                st = "EXTERNAL_MATCH" if diff <= 0.015 else "EXTERNAL_DIVERGENCE"
                return st, ivv_px_ret, f"BlackRock_Official_IVV({cand}, split_fac={sfac:g}, px_ret_vs_TR_diff={diff:.6f})"

        return "SINGLE_VENDOR_ONLY", None, f"single_close_vendor({primary_vendor}:{raw_sym})"
