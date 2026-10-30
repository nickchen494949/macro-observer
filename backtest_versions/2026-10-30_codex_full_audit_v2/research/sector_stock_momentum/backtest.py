#!/usr/bin/env python3
"""
backtest.py — "Best stock in the best sector" 12-1 momentum rotation, S&P 500.
EXPLORATORY backtest on the free-data sample (see REPORT.md for what that means).

FROZEN STRATEGY DEFINITION (decided before looking at final results; see FROZEN_SPEC.md; each run archives its
manifest in results/runs/)
  Formation at month-end t (close). Holding month = t → t+1, labelled by the month-end t+1.
    momentum(stock)  = P[t-1] / P[t-12] - 1          (12-1: 11 months, skipping the latest month)
    sector score     = 'ew'  : equal-weighted mean momentum of the sector's eligible members at t
                       'etf' : 12-1 momentum of the SPDR sector ETF that existed at t
    pick             = top n_sec sectors, then the top n_stk stocks INSIDE EACH selected sector
                       (total = n_sec × n_stk; fewer if a sector has fewer eligible stocks)
    weights          = equal across all picks; always fully invested (no cash filter, even if all
                       sector scores are negative)
  Spec (user)        = look 12, n_sec 1, n_stk 1, score 'ew'
  Eligibility at t   = S&P 500 member at t (point-in-time) ∧ price at t ∧ full 12-1 window
                       ∧ sector known AS OF t (historical GICS rebuild, historical_sectors.py).
                       Price history BEFORE index entry is used normally. No condition on t+1.
  Exits              = the held stock is sold at t+1 even if it left the index in between.
                       If its price series ends inside the holding month (delisting / acquisition)
                       the last traded close is used and the event is logged; if there is no price
                       at all after t the event is UNRESOLVED (base = 0 %, stressed = −30 % / −100 %),
                       unless a hand-researched outcome exists in data/exit_resolutions.csv.
  Costs              = 10 bp × Σ|w_target − w_pre-trade| (pre-trade = drifted weights). A→B = 20 bp,
                       hold = 0, first build = 10 bp.
  Sample             = holding months 2009-01 … 2026-09 (213). IS = first 70 % (149, to 2021-05),
                       OOS = last 64 (2021-06 …). IS parameter SELECTION uses IS months up to
                       2021-04 only, so the chosen config is known before the 2021-05-31 close at
                       which the first OOS position is formed.
  OOS protocol       = spec + IS-selected config evaluated once; the all-config IS/OOS rank
                       correlation is a pre-declared diagnostic, not a selection step.
"""
import hashlib, itertools, json, os, subprocess, sys
from datetime import datetime

import numpy as np
import pandas as pd
from portfolio_accounting import capital_after_costs

from historical_sectors import build_panel
from ticker_aliases import build_aliases, TIME_SPLIT

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'data', 'raw')
RAW_TIINGO = os.path.join(HERE, 'data', 'raw_tiingo')   # fills for delisted names Yahoo dropped
RAW_WIKI = os.path.join(HERE, 'data', 'raw_wiki')       # last resort: Nasdaq Data Link WIKI (frozen 2018-03-27)
RAW_ARCHIVE = os.path.join(HERE, 'data', 'raw_archive')  # QSTK Yahoo snapshot (~2012), optiontradingtips, BNSF
WIKI_CUTOFF = pd.Timestamp('2018-03-27')                # source stops here for EVERY ticker (not a delisting)
RES = os.path.join(HERE, 'results')
os.makedirs(RES, exist_ok=True)

START, END = '2009-01-31', '2026-09-30'          # holding-month labels
IS_FRAC = 0.70
COST_PER_SIDE = 0.0010
SPEC = dict(look=12, n_sec=1, n_stk=1, score='ew')
GRID = dict(look=[3, 6, 9, 12], n_sec=[1, 2, 3], n_stk=[1, 3, 5, 10], score=['ew', 'etf'])
STRESS_UNRESOLVED = [-0.30, -1.00]                 # Shumway (1997)-style performance-delisting stress, and total loss
ETF_OF = {'Information Technology': 'XLK', 'Telecommunication Services': 'XLK',  # Select Sector Tech held T/VZ pre-2018
          'Communication Services': 'XLC', 'Consumer Discretionary': 'XLY', 'Financials': 'XLF',
          'Industrials': 'XLI', 'Utilities': 'XLU', 'Energy': 'XLE', 'Real Estate': 'XLRE',
          'Materials': 'XLB', 'Consumer Staples': 'XLP', 'Health Care': 'XLV'}
NON_STOCK = set(ETF_OF.values()) | {'SPY', 'RSP'}


# ───────────────────────────── data ─────────────────────────────
def read_spells():
    """S&P membership spells (fja05680) + documented additions for members fja dropped when an acquirer took over
    the target's ticker (data/membership_additions.csv: JCI-OLD = Johnson Controls Inc, AGN-OLD = Allergan Inc)."""
    sp = pd.read_csv(os.path.join(HERE, 'data', 'sp500_ticker_start_end.csv'), parse_dates=['start_date', 'end_date'])
    ap = os.path.join(HERE, 'data', 'membership_additions.csv')
    if os.path.exists(ap):
        add = pd.read_csv(ap, parse_dates=['start_date', 'end_date'])[['ticker', 'start_date', 'end_date']]
        sp = pd.concat([sp, add], ignore_index=True)
    return sp


def check_integrity(series, extra_spells=None):
    """Guard against re-used Yahoo symbols — PIT-consistent version.
    Each daily series is cut into segments at gaps > 30 calendar days. A segment is kept if it overlaps ANY
    S&P membership spell of that symbol or of an old ticker that maps onto it (renames). Segments that never
    overlap a spell are dropped. All overlapping segments are kept (never "the best one"), so the decision for
    data before date C does not depend on data after C. Returns the kept series plus a segment-id series,
    so momentum and returns can refuse to bridge a gap (a gap may separate two different securities)."""
    sp = read_spells()
    sp['ticker'] = sp.ticker.str.replace('.', '-', regex=False)
    spells = {}
    for r in sp.itertuples():
        spells.setdefault(r.ticker, []).append((r.start_date, r.end_date if pd.notna(r.end_date) else pd.Timestamp('2100-01-01')))
    for k, v in (extra_spells or {}).items():
        spells.setdefault(k, []).extend(v)
    log, out, seg_ids = [], {}, {}
    for sym, s in series.items():
        if s.empty:
            out[sym], seg_ids[sym] = s, s
            continue
        gaps = np.where(np.diff(s.index.values).astype('timedelta64[D]').astype(int) > 30)[0]
        bounds = [0] + list(gaps + 1) + [len(s)]
        sid = pd.Series(np.repeat(np.arange(len(bounds) - 1), np.diff(bounds)), index=s.index, dtype=float)
        if sym in NON_STOCK or sym not in spells:
            out[sym], seg_ids[sym] = s, sid
            continue
        keep = np.zeros(len(s), bool)
        kept = []
        for i, (a, b) in enumerate(zip(bounds[:-1], bounds[1:])):
            g0, g1 = s.index[a], s.index[b - 1]
            if any(g0 <= e and g1 >= st for st, e in spells[sym]):
                keep[a:b] = True
                kept.append(str(g0.date()))
        if len(bounds) > 2 or not keep.any():
            log.append({'symbol': sym, 'series_first': s.index[0].date(), 'series_last': s.index[-1].date(),
                        'n_segments': len(bounds) - 1, 'kept_segments_starting': '|'.join(kept) or 'NONE (dropped)'})
        out[sym], seg_ids[sym] = s[keep], sid[keep]
    return out, seg_ids, pd.DataFrame(log)


def untrusted_spells(series):
    """Membership is checked spell by spell (a ticker can have several S&P spells, sometimes for different
    companies: old/new CEG, DOW, FOXA, DELL …). A spell is TRUSTED only if the price series we hold for that
    ticker already exists at the spell start (a stock must trade before it is added). Untrusted spells are
    removed from the eligible universe — the price we hold belongs to a different / re-listed security."""
    sp = read_spells()
    sp['ticker'] = sp.ticker.str.replace('.', '-', regex=False)
    bad, log = {}, []
    for r in sp.itertuples():
        e = r.end_date if pd.notna(r.end_date) else pd.Timestamp('2100-01-01')
        if e < pd.Timestamp('2007-12-01'):
            continue
        s_ = series.get(r.ticker)
        first = s_.index[0] if s_ is not None and len(s_) else None
        need = max(r.start_date, pd.Timestamp('2007-01-10')) + pd.Timedelta(days=10)
        if first is not None and first > need:
            bad.setdefault(r.ticker, []).append((r.start_date, e))
            log.append({'ticker': r.ticker, 'spell_start': r.start_date.date(), 'spell_end': r.end_date,
                        'series_first': first.date(), 'action': 'spell excluded (price belongs to another/re-listed security)'})
    return bad, pd.DataFrame(log)


def load_prices(cutoff=None):
    """cutoff: only used by pit_truncation_test.py — pretend today is `cutoff` (drop every later price)."""
    series = {}
    for f in sorted(os.listdir(RAW)):
        if not f.endswith('.json') or f.startswith('_'):
            continue
        d = json.load(open(os.path.join(RAW, f)))
        s = pd.Series(d['adjclose'], index=pd.to_datetime(d['dates']), dtype=float)
        s = s[~s.index.duplicated(keep='last')].sort_index()
        if cutoff is not None:
            s = s[s.index <= pd.Timestamp(cutoff)]
        series[d['symbol']] = s
    # Tiingo fill. A symbol's spells = its own S&P spells + the spells of every old ticker that maps onto it
    # (renames). Tiingo replaces Yahoo only where Tiingo covers those spells (identity-checked at download)
    # and Yahoo does not (missing, truncated, or starting after a spell began).
    global PRICE_SOURCE
    PRICE_SOURCE = {k: 'yahoo' for k in series}
    sp = read_spells()
    sp['ticker'] = sp.ticker.str.replace('.', '-', regex=False)
    sp = sp[sp.end_date.isna() | (sp.end_date >= '2007-12-01')]
    tiingo = {}
    if os.path.isdir(RAW_TIINGO):
        for f in sorted(os.listdir(RAW_TIINGO)):
            if f.endswith('.json') and not f.startswith('_'):
                d = json.load(open(os.path.join(RAW_TIINGO, f)))
                t = pd.Series(d['adjclose'], index=pd.to_datetime(d['dates']), dtype=float)
                t = t[~t.index.duplicated(keep='last')].sort_index()
                if cutoff is not None:
                    t = t[t.index <= pd.Timestamp(cutoff)]
                if len(t):
                    tiingo[d['symbol']] = t
    first = {k: v.index[0] for k, v in series.items() if len(v)}
    for k, v in tiingo.items():
        first[k] = min(first.get(k, v.index[0]), v.index[0])
    aliases, rejected = build_aliases(first)
    pred = {}
    for r in aliases.itertuples():
        pred.setdefault(r.price_symbol, []).append(r.old.replace('.', '-'))

    succ_of = {r.old.replace('.', '-'): r.price_symbol for r in aliases.itertuples()}

    def spells_of(sym):
        tk = [sym] + pred.get(sym, [])
        return [(r.start_date, r.end_date) for r in sp[sp.ticker.isin(tk)].itertuples()]

    def covers(x, sym):
        return x is not None and len(x) > 0 and all(
            x.index[0] <= max(a, pd.Timestamp('2007-01-10')) + pd.Timedelta(days=10) for a, _ in spells_of(sym))
    for sym, t in tiingo.items():
        if covers(series.get(sym), sym) or not covers(t, sym):
            continue
        if succ_of.get(sym) and covers(series.get(succ_of[sym]), sym) and succ_of[sym] != sym:
            continue
        series[sym] = t
        PRICE_SOURCE[sym] = 'tiingo'
    # WIKI last resort: only where neither Yahoo nor Tiingo covers the spells. If a later (different) company
    # holds the ticker on Yahoo, WIKI supplies the earlier company and a > 30-day gap separates the two
    # (old DOW / CEG / DELL / 21st-Century-Fox). WIKI prices after its 2018-03-27 freeze do not exist.
    global WIKI_SYMS
    WIKI_SYMS = set()
    if os.path.isdir(RAW_WIKI):
        for f in sorted(os.listdir(RAW_WIKI)):
            if not f.endswith('.json') or f.startswith('_'):
                continue
            d = json.load(open(os.path.join(RAW_WIKI, f)))
            sym = d['symbol']
            w = pd.Series(d['adjclose'], index=pd.to_datetime(d['dates']), dtype=float)
            w = w[~w.index.duplicated(keep='last')].sort_index()
            if cutoff is not None:
                w = w[w.index <= pd.Timestamp(cutoff)]
            if not len(w) or covers(series.get(sym), sym) or not covers(w, sym):
                continue
            succ_sym = succ_of.get(sym)
            if succ_sym and covers(series.get(succ_sym), sym):
                continue            # a verified rename already supplies this history (e.g. MMC → MRSH)
            cur = series.get(sym)
            if cur is not None and len(cur):
                # keep only the part of WIKI that ends ≥ 30 days before the other series starts (the old company);
                # WIKI is cut at its own gaps first so a re-used ticker inside WIKI is not carried over
                gaps = np.where(np.diff(w.index.values).astype('timedelta64[D]').astype(int) > 30)[0]
                w0 = w.iloc[:gaps[0] + 1] if len(gaps) else w
                if w0.index[-1] < cur.index[0] - pd.Timedelta(days=30) and covers(w0, sym):
                    series[sym] = pd.concat([w0, cur])
                    PRICE_SOURCE[sym] = f'wiki<{w0.index[-1].date()}|{PRICE_SOURCE.get(sym)}'
                    if w0.index[-1] >= WIKI_CUTOFF - pd.Timedelta(days=5):
                        WIKI_SYMS.add(sym)
                continue
            else:
                series[sym] = w
                PRICE_SOURCE[sym] = 'wiki'
            if w.index[-1] >= WIKI_CUTOFF - pd.Timedelta(days=5):
                WIKI_SYMS.add(sym)      # its WIKI part ends because the SOURCE froze, not because it delisted

    # ARCHIVE fill (QSTK Yahoo snapshot ~2012 validated vs current Yahoo: data/raw_archive/_validation_qstk.json;
    # optiontradingtips; BNSF). Same rule as WIKI: only where nothing else covers the spells; trailing flat runs
    # (stale quotes after a delisting) are dropped; series must start before the spell does (identity guard).
    if os.path.isdir(RAW_ARCHIVE):
        for f in sorted(os.listdir(RAW_ARCHIVE)):
            if not f.endswith('.json') or f.startswith('_'):
                continue
            d = json.load(open(os.path.join(RAW_ARCHIVE, f)))
            sym = d['symbol']
            a_ = pd.Series(d['adjclose'], index=pd.to_datetime(d['dates']), dtype=float).dropna().sort_index()
            a_ = a_[~a_.index.duplicated(keep='last')]
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
                    PRICE_SOURCE[sym] = f'archive:{d["source"]}<{a_.index[-1].date()}|{PRICE_SOURCE.get(sym)}'
                else:
                    # the current-source series overlaps (re-used ticker / truncated WIKI): archive wins up to its end
                    series[sym] = pd.concat([a_, cur[cur.index > a_.index[-1] + pd.Timedelta(days=30)]])
                    PRICE_SOURCE[sym] = f'archive:{d["source"]}<{a_.index[-1].date()}|{PRICE_SOURCE.get(sym)}'
            else:
                series[sym] = a_
                PRICE_SOURCE[sym] = f'archive:{d["source"]}'

    # time-split identities (one ticker = two companies inside one spell)
    split_log = []
    for tk, (d, before, after, why) in TIME_SPLIT.items():
        b_, a_ = series.get(before), series.get(after)
        if b_ is not None and a_ is not None and len(b_) and len(a_):
            cut = pd.Timestamp(d)
            series[tk] = pd.concat([b_[b_.index < cut], a_[a_.index >= cut]])
            PRICE_SOURCE[tk] = f'{PRICE_SOURCE.get(before)}:{before}<{d}|{PRICE_SOURCE.get(after)}:{after}'
            split_log.append((tk, d))

    # identity resolutions (data/identity_resolutions.csv, each with evidence): an acquirer that took over the
    # target's ticker makes Yahoo relabel the target's history (DD = Dow, CB = ACE, JCI = Tyco, EP/CPWR = microcaps)
    global ID_EXCLUDE
    ID_EXCLUDE = {}
    rp = os.path.join(HERE, 'data', 'identity_resolutions.csv')
    if os.path.exists(rp):
        for r in pd.read_csv(rp).itertuples():
            tk, d = r.ticker, pd.Timestamp(r.date)
            if r.action == 'use_wiki_before':
                wp = next((x for x in [os.path.join(HERE, 'data', 'raw_wiki_check', f'{tk}.json'),
                                       os.path.join(RAW_WIKI, f'{tk}.json')] if os.path.exists(x)), None)
                if wp is None:
                    ID_EXCLUDE.setdefault(tk, []).append((pd.Timestamp('1900-01-01'), d))
                    continue
                w = json.load(open(wp))
                ws = pd.Series(w['adjclose'], index=pd.to_datetime(w['dates']), dtype=float).sort_index()
                ws = ws[~ws.index.duplicated(keep='last')]
                if cutoff is not None:
                    ws = ws[ws.index <= pd.Timestamp(cutoff)]
                cur = series.get(tk, pd.Series(dtype=float))
                series[tk] = pd.concat([ws[ws.index < d], cur[cur.index >= d]])
                PRICE_SOURCE[tk] = f'wiki:{tk}<{d.date()}|{PRICE_SOURCE.get(tk)}'
                split_log.append((tk, str(d.date())))
            elif r.action == 'use_archive_before':
                ap_ = os.path.join(RAW_ARCHIVE, f'{tk}.json')
                if not os.path.exists(ap_):
                    ID_EXCLUDE.setdefault(tk, []).append((pd.Timestamp('1900-01-01'), d))
                    continue
                w = json.load(open(ap_))
                ws = pd.Series(w['adjclose'], index=pd.to_datetime(w['dates']), dtype=float).dropna().sort_index()
                ws = ws[~ws.index.duplicated(keep='last')]
                if cutoff is not None:
                    ws = ws[ws.index <= pd.Timestamp(cutoff)]
                cur = series.get(tk, pd.Series(dtype=float))
                series[tk] = pd.concat([ws[ws.index < d], cur[cur.index >= d]])
                PRICE_SOURCE[tk] = f'archive:{w["source"]}:{tk}<{d.date()}|{PRICE_SOURCE.get(tk)}'
                split_log.append((tk, str(d.date())))
            elif r.action == 'segment_break':
                split_log.append((tk, str(d.date())))
            elif r.action == 'exclude_before':
                ID_EXCLUDE.setdefault(tk, []).append((pd.Timestamp('1900-01-01'), d - pd.Timedelta(days=1)))
            elif r.action == 'exclude_spell':
                ID_EXCLUDE.setdefault(tk, []).append((d, pd.Timestamp(r.date_to)))

    # 1) security identity across renames: decided above from raw first-price dates (Yahoo ∪ Tiingo)
    # 2) integrity: a successor's series is judged against its own spells AND its predecessors' spells
    sp = read_spells()
    sp['ticker'] = sp.ticker.str.replace('.', '-', regex=False)
    extra = {}
    for r in aliases.itertuples():
        for q in sp[sp.ticker == r.old.replace('.', '-')].itertuples():
            extra.setdefault(r.price_symbol, []).append(
                (q.start_date, q.end_date if pd.notna(q.end_date) else pd.Timestamp('2100-01-01')))
    series, segs, integrity = check_integrity(series, extra)
    for tk, d in split_log:                      # new segment id from the split date onward
        if tk in segs and len(segs[tk]):
            segs[tk] = segs[tk].where(segs[tk].index < pd.Timestamp(d), segs[tk] + 1000)
    if cutoff is None:
        integrity.to_csv(os.path.join(RES, 'price_integrity.csv'), index=False)
    # 3) the old ticker gets the successor's full history (old symbol gone or re-used, e.g. FB) — unless the old
    #    ticker already holds an earlier-starting verified history (e.g. CBS from WIKI while the chain's final
    #    symbol PARA is now a re-used ticker), or it is a time-split ticker handled above
    for r in aliases.itertuples():
        old = r.old.replace('.', '-')
        if r.price_symbol not in series or old in TIME_SPLIT:
            continue
        cur, suc = series.get(old), series[r.price_symbol]
        if not covers(suc, old) and covers(cur, old) and PRICE_SOURCE.get(old, 'yahoo') != 'yahoo':
            continue            # successor's history is too short (re-used/new listing); keep the verified fill
        series[old] = suc
        segs[old] = segs[r.price_symbol]
        PRICE_SOURCE[old] = f'alias:{r.price_symbol}:{PRICE_SOURCE.get(r.price_symbol)}'
    if cutoff is None:
        aliases.to_csv(os.path.join(RES, 'ticker_aliases_used.csv'), index=False)
    if cutoff is None:
        rejected.to_csv(os.path.join(RES, 'ticker_aliases_rejected.csv'), index=False)
    bad, badlog = untrusted_spells(series)
    for tk, iv in ID_EXCLUDE.items():                 # identity resolutions: periods with no clean price source
        bad.setdefault(tk, []).extend(iv)
    if cutoff is None:
        badlog.to_csv(os.path.join(RES, 'membership_spells_excluded.csv'), index=False)
    daily = pd.DataFrame(series).sort_index()
    monthly = daily.resample('ME').last().where(daily.resample('ME').count() > 0)
    # a month-end price must be a month-end QUOTE: if a security's last trade in the month is more than 7 calendar
    # days (~5 sessions) before the market's last session, it stopped trading (delisting / cash-out) → no month-end
    # price; the holding-period logic then exits at the last trade and holds cash
    obs = pd.DataFrame(np.where(daily.notna().values, daily.index.values[:, None], np.datetime64('NaT')),
                       index=daily.index, columns=daily.columns)
    last_obs = obs.resample('ME').max()
    mkt_last = daily['SPY'].dropna().index.to_series().resample('ME').max()
    fresh = last_obs.ge(mkt_last - pd.Timedelta(days=7), axis=0)
    monthly = monthly.where(fresh.reindex(index=monthly.index, columns=monthly.columns).fillna(False))
    global SEG_D, SEG_M
    SEG_D = pd.DataFrame(segs).reindex(index=daily.index, columns=daily.columns)
    SEG_M = SEG_D.resample('ME').last().reindex(monthly.index)
    return daily, monthly, aliases, bad


_ap = os.path.join(HERE, 'data', 'membership_additions.csv')
ADDITIONS = (pd.read_csv(_ap, parse_dates=['start_date', 'end_date']) if os.path.exists(_ap)
             else pd.DataFrame(columns=['ticker', 'start_date', 'end_date']))


def apply_symbol_changes(members, asof, changes):
    """Point-in-time trading symbol changes, never a retroactive rename of the universe."""
    out = set(members)
    for change in changes.sort_values('effective_date').itertuples():
        if pd.Timestamp(change.effective_date) <= asof and change.old_ticker in out:
            out.remove(change.old_ticker)
            out.add(change.new_ticker)
    return out


def load_membership(month_ends):
    h = pd.read_csv(os.path.join(HERE, 'data', 'sp500_hist_components.csv'), parse_dates=['date']).sort_values('date')
    last_date = h.date.max()
    ch = pd.read_csv(os.path.join(HERE, 'data', 'wiki_changes.csv'))
    ch['date'] = pd.to_datetime(ch.date, errors='coerce')
    ch = ch[ch.date > last_date].sort_values('date')        # every change after the file ends, by effective date
    rename_path = os.path.join(HERE, 'data', 'membership_symbol_changes.csv')
    renames = pd.read_csv(rename_path) if os.path.exists(rename_path) else pd.DataFrame(columns=['old_ticker','new_ticker','effective_date'])
    out = {}
    for t in month_ends:
        row = h[h.date <= t]
        if row.empty:
            continue
        mem = {x.replace('.', '-') for x in row.tickers.iloc[-1].split(',')}
        for c in ch[ch.date <= t].itertuples():
            if isinstance(c.removed_ticker, str):
                mem.discard(c.removed_ticker.replace('.', '-'))
            if isinstance(c.added_ticker, str):
                mem.add(c.added_ticker.replace('.', '-'))
        for r in ADDITIONS.itertuples():
            if r.start_date <= t and (pd.isna(r.end_date) or t < r.end_date):
                mem.add(r.ticker)
        out[t] = apply_symbol_changes(mem, t, renames)
    return out, ch


def load_rf(hold_months):
    """FRED DGS3MO (3-month Treasury, investment-yield basis, annualised %) → monthly compounding rate,
    observed at the formation date t and applied to holding month t→t+1."""
    p_local = os.path.join(HERE, 'data', 'fred_DGS3MO.json')          # snapshot shipped with the repo
    p_dash = os.path.join(HERE, '..', '..', 'data', 'fred', 'DGS3MO.json')   # live dashboard cache, if present
    d = json.load(open(p_local if os.path.exists(p_local) else p_dash))
    s = pd.Series({pd.Timestamp(a): b for a, b in d['values'] if b is not None}, dtype=float).sort_index()
    form = hold_months - pd.offsets.MonthEnd(1)
    y = s.resample('ME').last().reindex(form).ffill().values / 100
    rf = pd.Series((1 + y) ** (1 / 12) - 1, index=hold_months)
    return rf


def load_resolutions():
    p = os.path.join(HERE, 'data', 'exit_resolutions.csv')
    if not os.path.exists(p):
        return {}
    r = pd.read_csv(p, parse_dates=['formation'])
    return {(a, b): c for a, b, c in zip(r.formation, r.ticker, r.holding_return)}


# ───────────────────────────── engine ─────────────────────────────
class Prices:
    """Holding-period returns for a given execution lag (0 = month-end close, 1 = next trading day close)."""

    def __init__(self, daily, P, lag_days=0):
        self.daily, self.P = daily, P
        self.lag_days = lag_days
        if lag_days:
            sessions = daily['SPY'].dropna().index if 'SPY' in daily else daily.index
            pos = sessions.searchsorted(P.index, side='right') + lag_days - 1
            dates = pd.DatetimeIndex([sessions[i] if i < len(sessions) else pd.NaT for i in pos])
            # An execution requires a quote on that session. Forward filling can
            # fabricate a purchase after a security has already ceased trading.
            E = daily.reindex(dates).set_axis(P.index)
        else:
            E = P
        self.E = E
        self.nxt = E.shift(-1) / E - 1
        if SEG_M is not None:
            sg = SEG_M.reindex(index=P.index, columns=P.columns)
            self.nxt = self.nxt.where(sg.shift(-1) == sg)
        self.cache = {}

    def ret(self, t, s, resolutions):
        """(return, status) for a position formed at t.
        ok                  normal month-end to month-end
        resolved_manual     verified terminal payout from data/exit_resolutions.csv (e.g. cash acquisition)
        delisted_in_month   stopped trading during the month → exit at its last trade, then cash
        source_gap          our price source froze (WIKI 2018-03-27), the company did NOT delist → unknown
        unresolved          no price at all after t"""
        key = (t, s)
        entry = self.E.at[t, s]
        if self.lag_days and (not np.isfinite(entry) or entry <= 0):
            return 0.0, 'source_gap' if s in WIKI_SYMS else 'unresolved'
        if key in resolutions:
            # Stored resolutions use the formation close as their denominator.
            # Preserve their terminal-value convention, but use the actual entry.
            r = ((1 + float(resolutions[key])) * self.P.at[t, s] / entry - 1
                 if self.lag_days else float(resolutions[key]))
            return float(r), 'resolved_manual'
        v = self.nxt.at[t, s]
        if np.isfinite(v):
            return float(v), 'ok'
        if key not in self.cache:
            b = self.E.at[t, s] if np.isfinite(self.E.at[t, s]) else self.P.at[t, s]
            d = self.daily[s].loc[t + pd.Timedelta(days=1):t + pd.offsets.MonthEnd(1)]
            if SEG_D is not None and s in SEG_D.columns:
                seg_t = SEG_D[s].loc[:t].dropna()
                if len(seg_t):
                    d = d[SEG_D[s].reindex(d.index) == seg_t.iloc[-1]]   # never cross into another segment
            d = d.dropna()
            frozen = s in WIKI_SYMS and (len(d) == 0 or abs((d.index[-1] - WIKI_CUTOFF).days) <= 5)
            if len(d):
                self.cache[key] = (float(d.iloc[-1] / b - 1), 'source_gap' if frozen else 'delisted_in_month')
            else:
                self.cache[key] = (0.0, 'source_gap' if frozen else 'unresolved')
        return self.cache[key]


SEG_D = SEG_M = None   # daily / monthly segment ids (set by load_prices)
PRICE_SOURCE = {}      # symbol → 'yahoo' | 'tiingo' | 'wiki' (or combinations)
WIKI_SYMS = set()      # symbols whose WIKI segment ends at the WIKI freeze
ID_EXCLUDE = {}        # ticker → [(from, to)] periods excluded by identity resolutions


def momentum(P, look):
    m = P.shift(1) / P.shift(look) - 1
    if SEG_M is not None:
        sg = SEG_M.reindex(index=P.index, columns=P.columns)
        m = m.where((sg.shift(look) == sg.shift(1)) & (sg.shift(1) == sg))
    return m


def rank_desc(x):
    """Deterministic ranking: value descending, ties broken by label ascending (never by set/hash order)."""
    return x.sort_index(kind='mergesort').sort_values(ascending=False, kind='mergesort')


def etf_group(sector, t):
    """Sector bucket used by the ETF score. Before XLC existed the Select Sector Technology index (XLK) held the
    telecom carriers, so 'Telecommunication Services' and 'Information Technology' form ONE bucket priced by XLK
    (they would otherwise tie with identical scores)."""
    return 'Information Technology' if sector == 'Telecommunication Services' else sector


class Engine:
    def __init__(self, P, daily, members, secP, months):
        self.P, self.daily, self.members, self.secP, self.months = P, daily, members, secP, months
        self.mom = {}

    def eligible(self, t, look):
        mom = self.mom.setdefault(look, momentum(self.P, look))
        m_t, sec_t, p_t = mom.loc[t], self.secP.loc[t], self.P.loc[t]
        # eligibility uses information at t only (no condition on t+1 or on future vendor coverage)
        rows = [(s, m_t[s], sec_t[s]) for s in sorted(self.members.get(t, ())) if s in m_t.index and s in sec_t.index
                and np.isfinite(m_t[s]) and np.isfinite(p_t[s]) and isinstance(sec_t[s], str)]
        return pd.DataFrame(rows, columns=['tk', 'mom', 'sector']).set_index('tk'), mom

    def run(self, cfg, px, resolutions, sector_filter=True, stress=None):
        look, n_sec, n_stk, score = cfg['look'], cfg['n_sec'], cfg['n_stk'], cfg['score']
        rows, w_pre, bankrupt = [], {}, False
        for t in self.months:
            if bankrupt:
                rows.append({'formation': t, 'month': t + pd.offsets.MonthEnd(1), 'sectors': '',
                             'picks': '', 'pick_mom': np.nan, 'sector_score': np.nan, 'n_eligible': 0,
                             'gross': 0.0, 'turnover': 0.0, 'net': 0.0, 'exit_status': 'bankrupt',
                             'price_source': '', 'capital_after_costs': 0.0, 'bankrupt': True})
                continue
            df, mom = self.eligible(t, look)
            if df.empty:
                continue
            if sector_filter:
                if score == 'ew':
                    ss = df.groupby('sector').mom.mean()
                    bucket = df.sector
                else:
                    bucket = df.sector.map(lambda x: etf_group(x, t))
                    ss = pd.Series({b: mom.at[t, ETF_OF[b]] for b in sorted(bucket.unique())
                                    if ETF_OF.get(b) in mom.columns}).dropna()
                top = rank_desc(ss).index[:n_sec].tolist()
                picks = []
                for sec in top:
                    picks += rank_desc(df.mom[bucket == sec]).index[:n_stk].tolist()
                sscore = float(ss[top].mean())
            else:
                top, sscore = ['ALL'], np.nan
                picks = rank_desc(df.mom).index[:n_sec * n_stk].tolist()
            w = {s: 1 / len(picks) for s in picks}
            rets, stats_ = zip(*[px.ret(t, s, resolutions) for s in picks])
            rets = list(rets)
            if stress is not None:
                rets = [stress if st in ('unresolved', 'source_gap') else r for r, st in zip(rets, stats_)]
            turn = sum(abs(w.get(k, 0) - w_pre.get(k, 0)) for k in set(w) | set(w_pre))
            r = float(np.dot([w[s] for s in picks], rets))
            capital, turn = capital_after_costs(w, w_pre, COST_PER_SIDE)
            net = max(0.0, capital * (1 + r)) - 1
            bankrupt = net <= -1
            # drifted (pre-trade) weights for next month; exited names become cash (no sale cost)
            grow = {s: w[s] * (1 + x) for s, x, st in zip(picks, rets, stats_) if st == 'ok'}
            tot = 1 + r
            w_pre = {s: v / tot for s, v in grow.items()} if tot > 0 else {}
            rows.append({'formation': t, 'month': t + pd.offsets.MonthEnd(1), 'sectors': '|'.join(top),
                         'picks': '|'.join(picks), 'pick_mom': float(df.loc[picks, 'mom'].mean()),
                         'sector_score': sscore, 'n_eligible': len(df), 'gross': r, 'turnover': turn,
                         'net': net, 'capital_after_costs': capital, 'bankrupt': bankrupt, 'exit_status': '|'.join(stats_),
                         'price_source': '|'.join(PRICE_SOURCE.get(x, '?') for x in picks)})
        return pd.DataFrame(rows).set_index('month')


# ───────────────────────────── statistics ─────────────────────────────
def newey_west_ols(y, X, lags=3):
    X = np.column_stack([np.ones(len(y)), X])
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    u = y - X @ b
    XtX_inv = np.linalg.inv(X.T @ X)
    S = (X * u[:, None]).T @ (X * u[:, None])
    for L in range(1, lags + 1):
        wgt = 1 - L / (lags + 1)
        G = (X[L:] * u[L:, None]).T @ (X[:-L] * u[:-L, None])
        S += wgt * (G + G.T)
    V = XtX_inv @ S @ XtX_inv
    return b, np.sqrt(np.diag(V))


def stats(r, rf, bench=None):
    r = r.dropna()
    if len(r) < 6:
        return {}
    rf = rf.reindex(r.index).fillna(0)
    eq = (1 + r).cumprod()
    ex = r - rf
    out = {'months': len(r), 'CAGR': eq.iloc[-1] ** (12 / len(r)) - 1, 'vol': r.std() * np.sqrt(12),
           'Sharpe': ex.mean() / ex.std() * np.sqrt(12) if ex.std() > 0 else np.nan,
           'maxDD_month_end': (lambda e: (e / e.cummax() - 1).min())(pd.concat([pd.Series([1.0]), eq.reset_index(drop=True)])),
           'hit_rate': (r > 0).mean(),
           'best_m': r.max(), 'worst_m': r.min(), 'total_return': eq.iloc[-1] - 1}
    if bench is not None:
        b = bench.reindex(r.index)
        a = r - b
        out['beat_bench_months'] = (a > 0).mean()
        out['excess_vs_bench_ann'] = a.mean() * 12
        coef, se = newey_west_ols(ex.values, (b - rf).values, lags=3)
        out.update(alpha_ann=coef[0] * 12, alpha_t_NW=coef[0] / se[0], beta=coef[1])
    return out


def stationary_bootstrap_idx(T, mean_block, rng):
    idx = np.empty(T, int)
    idx[0] = rng.integers(T)
    for i in range(1, T):
        idx[i] = rng.integers(T) if rng.random() < 1 / mean_block else (idx[i - 1] + 1) % T
    return idx


def paired_bootstrap(series, rf, n=4000, mean_block=6, seed=7):
    """Politis–Romano stationary bootstrap, SAME resampled months for every series (paired)."""
    df = pd.concat(series, axis=1).dropna()
    rfx = rf.reindex(df.index).fillna(0).values
    rng = np.random.default_rng(seed)
    T = len(df)
    res = {k: {'sharpe': [], 'cagr': []} for k in df.columns}
    diffs = {k: [] for k in df.columns[1:]}
    cdiffs = {k: [] for k in df.columns[1:]}
    for _ in range(n):
        i = stationary_bootstrap_idx(T, mean_block, rng)
        for k in df.columns:
            x = df[k].values[i]
            e = x - rfx[i]
            res[k]['sharpe'].append(e.mean() / e.std() * np.sqrt(12) if e.std() > 0 else np.nan)
            res[k]['cagr'].append(np.prod(1 + x) ** (12 / T) - 1)
        base = df.iloc[:, 0].values[i]
        for k in df.columns[1:]:
            diffs[k].append((base - df[k].values[i]).mean() * 12)
            cdiffs[k].append(np.prod(1 + base) ** (12 / T) - np.prod(1 + df[k].values[i]) ** (12 / T))
    q = lambda a: [round(float(np.nanpercentile(a, p)), 4) for p in (5, 50, 95)]
    out = {k: {'Sharpe_p5_p50_p95': q(v['sharpe']), 'CAGR_p5_p50_p95': q(v['cagr']),
               'P(Sharpe<=0)': float(np.mean(np.array(v['sharpe']) <= 0))} for k, v in res.items()}
    for k, v in diffs.items():
        out[f'{df.columns[0]} minus {k}: annualised ARITHMETIC mean-return diff p5/p50/p95'] = q(v)
        out[f'{df.columns[0]} minus {k}: share of resamples with arithmetic diff <= 0'] = float(np.mean(np.array(v) <= 0))
        out[f'{df.columns[0]} minus {k}: CAGR diff p5/p50/p95'] = q(cdiffs[k])
        out[f'{df.columns[0]} minus {k}: share of resamples with CAGR diff <= 0'] = float(np.mean(np.array(cdiffs[k]) <= 0))
    out['note'] = ('shares of bootstrap resamples conditional on the realised series; NOT p-values and NOT forecast '
                   'probabilities of future under-performance')
    return out


def deflated_sharpe(r_best, sr_trials_monthly, n_obs):
    """Bailey & López de Prado (2014). All inputs per-MONTH; trials = distinct return series only."""
    from scipy.stats import norm, skew, kurtosis
    sr = np.asarray(sr_trials_monthly, float)
    N = len(sr)
    emc = 0.5772156649
    sr0 = np.sqrt(np.var(sr, ddof=1)) * ((1 - emc) * norm.ppf(1 - 1 / N) + emc * norm.ppf(1 - 1 / (N * np.e)))
    srb = r_best.mean() / r_best.std()
    g3, g4 = skew(r_best), kurtosis(r_best, fisher=False)
    z = (srb - sr0) * np.sqrt(n_obs - 1) / np.sqrt(1 - g3 * srb + (g4 - 1) / 4 * srb ** 2)
    return float(norm.cdf(z)), float(sr0 * np.sqrt(12)), N


def daily_nav(picks_df, daily):
    """Gross daily close marks, accepted only when monthly endpoints reconcile."""
    if 'SPY' in daily:
        daily = daily.loc[daily.SPY.notna()]
    nav, level = [], 1.0
    for m, row in picks_df.iterrows():
        t = daily.index[daily.index.searchsorted(row.formation, side='right') - 1]   # last trading day ≤ month-end
        names = row.picks.split('|')
        seg = daily[names].loc[t:m]
        if seg.isna().any().any() or (seg <= 0).any().any():
            raise ValueError(f'{m}: missing observed holding-day close; daily risk unavailable')
        if len(seg) < 2:
            continue
        rel = (seg / seg.iloc[0]).mean(axis=1) * level
        if not np.isclose(rel.iloc[-1], level * (1 + row.gross), rtol=1e-7, atol=1e-10):
            raise ValueError(f'{m}: daily close marks do not reconcile the monthly outcome')
        nav.append(rel.iloc[1:])
        level = rel.iloc[-1]
    s = pd.concat(nav)
    return s


def contribution(df):
    lr = np.log1p(df['net'])
    by_stock = lr.groupby(df['picks']).sum().sort_values(ascending=False)
    top_m = lr.sort_values(ascending=False)
    return {'total_log_return': float(lr.sum()),
            'top5_months_log_return': float(top_m.head(5).sum()),
            'total_ex_top5_months_CAGR': float(np.exp(lr.sum() - top_m.head(5).sum()) ** (12 / len(lr)) - 1),
            'top5_stocks': {k: round(float(v), 3) for k, v in by_stock.head(5).items()},
            'bottom5_stocks': {k: round(float(v), 3) for k, v in by_stock.tail(5).items()},
            'distinct_stocks_held': int(df['picks'].nunique())}


# ───────────────────────────── provenance ─────────────────────────────
def provenance():
    def sh(cmd):
        try:
            return subprocess.run(cmd, capture_output=True, text=True, cwd=HERE).stdout.strip()
        except Exception:  # noqa
            return ''
    h = hashlib.sha256()
    for d_ in [RAW, RAW_TIINGO, RAW_WIKI, RAW_ARCHIVE]:
        if os.path.isdir(d_):
            for f in sorted(os.listdir(d_)):
                h.update(f.encode()); h.update(open(os.path.join(d_, f), 'rb').read())
    files = {}
    for f in ['data/sp500_hist_components.csv', 'data/wiki_changes.csv', 'data/sectors.csv',
              'data/wiki_current_constituents.csv', 'backtest.py', 'historical_sectors.py']:
        p = os.path.join(HERE, f)
        if os.path.exists(p):
            files[f] = hashlib.sha256(open(p, 'rb').read()).hexdigest()[:16]
    import scipy
    return {'run_at': datetime.now().isoformat(timespec='seconds'), 'git_head': sh(['git', 'rev-parse', 'HEAD']),
            'git_dirty_files': sh(['git', 'status', '--porcelain', '.']).splitlines(),
            'raw_price_snapshot_sha256': h.hexdigest()[:16], 'n_raw_files': len(os.listdir(RAW)),
            'n_tiingo_files': len(os.listdir(RAW_TIINGO)) if os.path.isdir(RAW_TIINGO) else 0,
            'n_symbols_priced_from_tiingo': sum(v == 'tiingo' for v in PRICE_SOURCE.values()),
            'n_symbols_using_wiki': sum('wiki' in v for v in PRICE_SOURCE.values()),
            'file_sha256_16': files, 'python': sys.version.split()[0], 'pandas': pd.__version__,
            'numpy': np.__version__, 'scipy': scipy.__version__,
            'sources': {'membership': 'github.com/fja05680/sp500 (Historical Components & Changes, Updated)',
                        'membership_after_file_end': 'en.wikipedia.org/wiki/Historical_components_of_the_S&P_500',
                        'sectors': 'Wikipedia current GICS + Yahoo sector/industry, rebuilt by historical_sectors.py',
                        'prices': 'Yahoo Finance chart API v8 (adjclose), fetched by fetch_prices.py; '
                                  'Tiingo EOD adjClose for delisted names Yahoo dropped (fetch_tiingo.py); '
                                  'Nasdaq Data Link WIKI/PRICES adj_close (frozen 2018-03-27) as last resort, '
                                  'validated vs Yahoo (data/raw_wiki/_validation.json)',
                        'rf': 'FRED DGS3MO'}}


# ───────────────────────────── main ─────────────────────────────
def build_sector_table(aliases):
    """One row per ticker: sector, source, industry — IDENTITY-SAFE (shared by backtest and truncation test).
    Priority: 1 dated manual overrides (data/sector_overrides.csv, each with a source)
              2 Wikipedia GICS (current members)
              3 rename alias → the successor's classification (same company)
              4 Yahoo sector ONLY if this ticker is priced from Yahoo, i.e. the Yahoo symbol is the same company
                (a re-used symbol describes its new owner: S → SentinelOne, POM → Pomdoctor, STI → Solidion …)
              5 SEC SIC code of the CIK matched by company name/filing window (build_fundamentals.py)"""
    raw = pd.read_csv(os.path.join(HERE, 'data', 'sectors.csv'))
    wiki = raw[raw.source == 'wikipedia_gics'].set_index('ticker')
    yahoo = raw[raw.source == 'yahoo'].set_index('ticker')
    cm_p = os.path.join(HERE, 'data', 'fundamentals', 'cik_map.csv')
    sic = {}
    if os.path.exists(cm_p):
        cm = pd.read_csv(cm_p)
        if 'sic_sector' in cm:
            sic = {t.replace('.', '-'): (sec, ind) for t, sec, ind in zip(cm.ticker, cm.sic_sector, cm.sic)
                   if isinstance(sec, str)}
    succ = {r.old.replace('.', '-'): r.price_symbol for r in aliases.itertuples()}
    tickers = set(raw.ticker) | set(sic) | set(succ)
    rows = []

    def base_row(t, depth=0):
        if t in wiki.index:
            return wiki.at[t, 'sector'], 'wikipedia_gics', wiki.at[t, 'industry']
        if t in succ and depth < 5:
            r = base_row(succ[t], depth + 1)
            if r:
                return r[0], f'alias:{succ[t]}:{r[1]}', r[2]
        if t in yahoo.index and PRICE_SOURCE.get(t) == 'yahoo' and isinstance(yahoo.at[t, 'sector'], str) \
                and yahoo.at[t, 'sector'] != 'UNKNOWN':
            return yahoo.at[t, 'sector'], 'yahoo', yahoo.at[t, 'industry']
        if t in sic:
            return sic[t][0], 'sic', f'SIC {sic[t][1]}'
        return None
    for t in sorted(tickers):
        r = base_row(t)
        if r:
            rows.append({'ticker': t, 'sector': r[0], 'source': r[1], 'industry': r[2]})
    out = pd.DataFrame(rows)
    ov_p = os.path.join(HERE, 'data', 'sector_overrides.csv')
    if os.path.exists(ov_p):
        ov = pd.read_csv(ov_p)
        out = out[~out.ticker.isin(ov.ticker)]
        out = pd.concat([out, ov.assign(source='manual:' + ov.source)[['ticker', 'sector', 'source', 'industry']
                                                                     + [c for c in ['valid_from', 'valid_to'] if c in ov]]],
                        ignore_index=True)
    return out


def main():
    daily, P, aliases, bad_spells = load_prices()
    form = P.index[(P.index >= pd.Timestamp(START) - pd.offsets.MonthEnd(1)) &
                   (P.index <= pd.Timestamp(END) - pd.offsets.MonthEnd(1))]
    hold = form + pd.offsets.MonthEnd(1)
    members_raw, late_changes = load_membership(form)
    # keep the full membership for the coverage funnel; drop untrusted spells only from eligibility
    members = {t: {x for x in mem if not any(a <= t <= b for a, b in bad_spells.get(x, []))}
               for t, mem in members_raw.items()}
    sec_df = build_sector_table(aliases)
    secP, secFlag = build_panel(sec_df, form)
    rf = load_rf(hold)
    resolutions = load_resolutions()
    n_is = int(round(len(hold) * IS_FRAC))
    is_idx, oos_idx = hold[:n_is], hold[n_is:]
    sel_idx = is_idx[:-1]
    split = {'FULL': (hold[0], hold[-1]), 'IS': (is_idx[0], is_idx[-1]), 'OOS': (oos_idx[0], oos_idx[-1]),
             'FULL_TO_2025': (hold[0], pd.Timestamp('2025-12-31')), 'OOS_TO_2025': (oos_idx[0], pd.Timestamp('2025-12-31'))}

    prov = provenance()
    frozen = {'spec': SPEC, 'grid': GRID, 'cost_per_side': COST_PER_SIDE, 'is_frac': IS_FRAC,
              'holding_months': [str(hold[0].date()), str(hold[-1].date()), len(hold)],
              'IS': [str(is_idx[0].date()), str(is_idx[-1].date()), len(is_idx)],
              'IS_selection_window': [str(sel_idx[0].date()), str(sel_idx[-1].date()), len(sel_idx)],
              'OOS': [str(oos_idx[0].date()), str(oos_idx[-1].date()), len(oos_idx)],
              'first_formation': str(form[0].date()), 'momentum_needs_prices_from': str((form[0] - pd.offsets.MonthEnd(12)).date()),
              'membership_changes_applied_after_file_end': late_changes[['date', 'added_ticker', 'removed_ticker']].astype(str).values.tolist(),
              'stress_unresolved_exit': STRESS_UNRESOLVED, 'provenance': prov}
    # FROZEN_SPEC.md (committed before the final run) holds the strategy definition; every run writes its own
    # manifest (code version, dirty files, data hashes) and archives it — nothing is overwritten silently
    os.makedirs(os.path.join(RES, 'runs'), exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    json.dump(frozen, open(os.path.join(RES, 'run_manifest.json'), 'w'), indent=1, default=str)
    json.dump(frozen, open(os.path.join(RES, 'runs', f'{stamp}_manifest.json'), 'w'), indent=1, default=str)

    # ── coverage funnel: month × sector, with exclusion reasons ──
    mom12 = momentum(P, 12)
    fun = []
    for t in form:
        for s in members_raw.get(t, ()):
            sec = secP.at[t, s] if s in secP.columns else None
            if s not in members.get(t, ()):
                reason = 'untrusted_spell (held price belongs to another / re-listed security)'
            elif s not in P.columns or not P[s].notna().any():
                reason = 'no_price_data_at_source'
            elif not np.isfinite(P.at[t, s]):
                reason = 'no_price_at_t (source history truncated / ticker re-used)'
            elif not np.isfinite(mom12.at[t, s]):
                reason = 'insufficient_history_for_12-1'
            elif not isinstance(sec, str):
                reason = 'sector_unknown'
            else:
                reason = 'eligible'
            fun.append((t, sec if isinstance(sec, str) else 'UNKNOWN', s, reason,
                        secFlag.at[t, s] if s in secFlag.columns else None))
    fun = pd.DataFrame(fun, columns=['month', 'sector', 'ticker', 'reason', 'sector_flag'])
    fun.to_csv(os.path.join(RES, 'coverage_detail.csv'), index=False)
    funnel = fun.pivot_table(index='month', columns='reason', values='ticker', aggfunc='count', fill_value=0)
    funnel['members'] = funnel.sum(axis=1)
    funnel['eligible_pct'] = funnel.get('eligible', 0) / funnel.members
    funnel.to_csv(os.path.join(RES, 'coverage_funnel_by_month.csv'))
    fun[fun.reason == 'eligible'].pivot_table(index='month', columns='sector', values='ticker', aggfunc='count',
                                              fill_value=0).to_csv(os.path.join(RES, 'eligible_by_month_sector.csv'))
    missing = fun[fun.reason != 'eligible'].groupby('ticker').agg(months=('month', 'count'), first=('month', 'min'),
                                                                  last=('month', 'max'), reason=('reason', 'first'))
    missing.sort_values('months', ascending=False).to_csv(os.path.join(RES, 'missing_members.csv'))
    print('eligible % of members: first', round(funnel.eligible_pct.iloc[0], 3), 'median',
          round(funnel.eligible_pct.median(), 3), 'last', round(funnel.eligible_pct.iloc[-1], 3))

    eng = Engine(P, daily, members, secP, form)
    px0, px1 = Prices(daily, P, 0), Prices(daily, P, 1)
    bench = {b: px0.nxt[b].reindex(form).set_axis(hold) for b in ['SPY', 'RSP']}
    bench_lag = {b: px1.nxt[b].reindex(form).set_axis(hold) for b in ['SPY']}

    R = {}
    R['SPEC'] = eng.run(SPEC, px0, resolutions)
    R['SPEC | ETF sector score'] = eng.run({**SPEC, 'score': 'etf'}, px0, resolutions)
    R['SPEC | next-day-close execution'] = eng.run(SPEC, px1, resolutions)
    for s in STRESS_UNRESOLVED:
        R[f'SPEC | unresolved exits = {int(s*100)}%'] = eng.run(SPEC, px0, resolutions, stress=s)
    R['NO SECTOR FILTER: top-1 stock'] = eng.run(SPEC, px0, resolutions, sector_filter=False)
    R['Ref: EW all stocks of best sector'] = eng.run({**SPEC, 'n_stk': 9999}, px0, resolutions)
    R['Ref: top-10, no sector filter'] = eng.run({**SPEC, 'n_stk': 10}, px0, resolutions, sector_filter=False)
    # best-sector ETF (only ETFs with a full 12-1 window at t; Telecom pre-2018 → XLK)
    rows, prev = [], None
    for t in form:
        m = mom12.loc[t, [e for e in sorted(set(ETF_OF.values())) if e in mom12.columns]].dropna()
        k = rank_desc(m).index[0]
        r = float(px0.nxt.at[t, k])
        capital, turn = capital_after_costs({k: 1.0}, {prev: 1.0} if prev else {}, COST_PER_SIDE)
        prev = k
        rows.append({'formation': t, 'month': t + pd.offsets.MonthEnd(1), 'picks': k, 'gross': r, 'turnover': turn,
                     'net': capital * (1 + r) - 1, 'capital_after_costs': capital})
    R['Ref: best sector ETF'] = pd.DataFrame(rows).set_index('month')

    summary = {}
    for name, df in R.items():
        b = bench_lag['SPY'] if 'next-day' in name else bench['SPY']
        summary[name] = {f'{lab}_{k}': stats(df[k].loc[a:z], rf, b) for lab, (a, z) in split.items() for k in ['gross', 'net']}
    for bname, b in bench.items():
        summary[f'Bench: {bname}'] = {f'{lab}_gross': stats(b.loc[a:z], rf, None if bname == 'SPY' else bench['SPY'])
                                     for lab, (a, z) in split.items()}

    # ── IS-only grid → frozen selection → OOS once ──
    grid, series = [], {}
    for look, n_sec, n_stk, score in itertools.product(*GRID.values()):
        cfg = dict(look=look, n_sec=n_sec, n_stk=n_stk, score=score)
        df = eng.run(cfg, px0, resolutions)
        grid_dir = os.path.join(RES, 'grid_monthly')
        os.makedirs(grid_dir, exist_ok=True)
        ledger_name = f'look{look}_sector{n_sec}_stock{n_stk}_{score}.csv'
        df.to_csv(os.path.join(grid_dir, ledger_name))
        key = tuple(np.round(df['net'].values, 10))
        series.setdefault(key, (cfg, df))
        g = {**cfg, 'distinct_id': list(series).index(key), 'monthly_ledger': 'grid_monthly/' + ledger_name}
        for lab, idx in {'SEL': sel_idx, 'IS': is_idx, 'OOS': oos_idx}.items():
            st = stats(df['net'].reindex(idx), rf)
            g.update({f'{lab}_CAGR': st['CAGR'], f'{lab}_Sharpe': st['Sharpe'], f'{lab}_maxDD': st['maxDD_month_end']})
        grid.append(g)
    grid = pd.DataFrame(grid).sort_values('SEL_Sharpe', ascending=False)
    grid.to_csv(os.path.join(RES, 'grid_is_oos.csv'), index=False)
    best = grid.iloc[0]
    best_cfg = dict(look=int(best.look), n_sec=int(best.n_sec), n_stk=int(best.n_stk), score=best.score)
    R['IS-selected config'] = eng.run(best_cfg, px0, resolutions)
    R[f'IS-selected, NO sector filter (same {best_cfg["n_sec"]*best_cfg["n_stk"]} stocks)'] = eng.run(best_cfg, px0, resolutions, sector_filter=False)
    for name in list(R)[-2:]:
        summary[name] = {f'{lab}_{k}': stats(R[name][k].loc[a:z], rf, bench['SPY']) for lab, (a, z) in split.items()
                         for k in ['gross', 'net']}
    distinct = grid.drop_duplicates('distinct_id')
    sr_trials = [stats(series[list(series)[i]][1]['net'].reindex(sel_idx), rf)['Sharpe'] / np.sqrt(12)
                 for i in distinct.distinct_id]
    dsr, sr0_ann, n_trials = deflated_sharpe(R['IS-selected config']['net'].reindex(sel_idx).values -
                                             rf.reindex(sel_idx).values, sr_trials, len(sel_idx))
    rank_corr = float(distinct[['SEL_Sharpe', 'OOS_Sharpe']].corr(method='spearman').iloc[0, 1])

    # ── uncertainty, incremental value of the sector step, concentration ──
    boot = {}
    for lab, (a, z) in split.items():
        boot[lab] = paired_bootstrap({'SPEC': R['SPEC']['net'].loc[a:z],
                                      'NO_SECTOR_FILTER_top1': R['NO SECTOR FILTER: top-1 stock']['net'].loc[a:z],
                                      'SPY': bench['SPY'].loc[a:z]}, rf)
    try:
        nav = daily_nav(R['SPEC'], daily)
        nav_with_initial = pd.concat([pd.Series([1.0]), nav.reset_index(drop=True)])
        daily_dd = float((nav_with_initial / nav_with_initial.cummax() - 1).min())
        daily_dd_status = 'verified_gross_close_marks'
    except ValueError as exc:
        daily_dd, daily_dd_status = None, str(exc)
    events = []
    for name in ['SPEC', 'IS-selected config']:
        df = R[name]
        for m, row in df.iterrows():
            for s, st in zip(row.picks.split('|'), row.exit_status.split('|')):
                if st != 'ok':
                    events.append({'strategy': name, 'formation': row.formation.date(), 'month': m.date(), 'ticker': s,
                                   'status': st, 'return_used': px0.ret(row.formation, s, resolutions)[0]})
    pd.DataFrame(events).to_csv(os.path.join(RES, 'exit_events.csv'), index=False)

    yr = {n: (1 + df['net']).groupby(df.index.year).prod() - 1 for n, df in R.items()}
    yr.update({b: (1 + s).groupby(s.index.year).prod() - 1 for b, s in bench.items()})
    pd.DataFrame(yr).to_csv(os.path.join(RES, 'calendar_year_returns_net.csv'))
    for name, df in R.items():
        safe = ''.join(c if c.isalnum() else '_' for c in name)[:60]
        df.to_csv(os.path.join(RES, f'monthly_{safe}.csv'))
    flags_used = pd.Series([secFlag.at[r.formation, p] for _, r in R['SPEC'].iterrows() for p in r.picks.split('|')]).value_counts().to_dict()

    meta = {'IS_selected_cfg': best_cfg, 'grid_configs': len(grid), 'grid_distinct_return_series': n_trials,
            'spec_rank_by_SEL_Sharpe': int(grid.reset_index(drop=True).query(
                "look==12 and n_sec==1 and n_stk==1 and score=='ew'").index[0] + 1),
            'deflated_sharpe_prob_IS_best': dsr, 'expected_max_sharpe_under_null_ann': sr0_ann,
            'diag_SEL_vs_OOS_sharpe_spearman_distinct': rank_corr,
            'bootstrap_paired_net': boot, 'spec_daily_maxDD_gross': daily_dd,
            'spec_daily_maxDD_status': daily_dd_status,
            'spec_contribution': contribution(R['SPEC']),
            'spec_sector_flags_of_picks': flags_used,
            'exit_events_spec': int(sum(e['strategy'] == 'SPEC' for e in events)),
            'eligible_pct_of_members': {'first': float(funnel.eligible_pct.iloc[0]),
                                        'median': float(funnel.eligible_pct.median()),
                                        'min': float(funnel.eligible_pct.min()), 'last': float(funnel.eligible_pct.iloc[-1])}}
    json.dump({'meta': meta, 'summary': summary}, open(os.path.join(RES, 'summary.json'), 'w'), indent=1, default=float)

    for name in summary:
        print(f'\n== {name}')
        for k, v in summary[name].items():
            if v and k.endswith('net') or (v and name.startswith('Bench')):
                print(f"  {k:10s} CAGR {v['CAGR']*100:6.1f}%  vol {v['vol']*100:5.1f}%  Sharpe {v['Sharpe']:5.2f}  "
                      f"maxDD {v['maxDD_month_end']*100:6.1f}%  alpha {v.get('alpha_ann', np.nan)*100:5.1f}% "
                      f"(NW t {v.get('alpha_t_NW', np.nan):4.2f})")
    print('\nmeta', json.dumps(meta, default=float, indent=1))

    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(2, 1, figsize=(11, 8), sharex=True, gridspec_kw={'height_ratios': [3, 1]})
        for lab, r in {'SPEC (net)': R['SPEC']['net'], 'No sector filter, top-1 (net)': R['NO SECTOR FILTER: top-1 stock']['net'],
                       'EW best sector (net)': R['Ref: EW all stocks of best sector']['net'], 'SPY': bench['SPY'],
                       'RSP': bench['RSP']}.items():
            eq = (1 + r.fillna(0)).cumprod()
            ax[0].plot(eq.index, eq.values, label=lab, lw=1.6 if 'SPEC' in lab else 1.0)
            ax[1].plot(eq.index, (eq / eq.cummax() - 1).values, lw=0.9)
        for a in ax:
            a.axvline(split['OOS'][0], color='k', ls='--', lw=1)
        ax[0].set_yscale('log'); ax[0].legend(fontsize=8); ax[0].grid(alpha=.3)
        ax[0].set_title('EXPLORATORY: best 12-1 stock in best 12-1 sector, monthly (IS | OOS at dashed line)')
        ax[1].set_ylabel('month-end DD'); ax[1].grid(alpha=.3)
        fig.tight_layout(); fig.savefig(os.path.join(RES, 'equity_curve.png'), dpi=130)
    except Exception as e:  # noqa
        print('chart failed', e)


if __name__ == '__main__':
    main()
