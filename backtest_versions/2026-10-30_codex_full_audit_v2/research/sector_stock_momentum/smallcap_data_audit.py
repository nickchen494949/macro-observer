#!/usr/bin/env python3
"""
smallcap_data_audit.py — data-quality checks for the small/mid-cap HOLDOUT prices (WINNERS_SPEC.md §5d), run BEFORE the
exam and without computing any strategy return. Free small-cap prices (WIKI, Yahoo) contain bad prints and split
errors; a top-1 momentum rule would pick exactly those, so they must be neutralised by a rule fixed in advance.

Checks on every daily adjusted series (data/smallcap/daily_adj.parquet):
  F0 non-positive   : price <= 0 (not a quote) → removed
  F1 spike-reversal : |daily return| >= 40 % and within the next 3 sessions the price returns to within 10 % of the
                      pre-spike level (bad print, either direction)
  F2 split-like jump: a one-day ratio within 3 % of 2, 3, 4, 5, 8, 10, 15, 20 or their inverses that is NOT reversed
                      (likely an unadjusted split / reverse split in the "adjusted" series)
  F3 stale run      : >= 10 consecutive sessions with an identical price while dollar volume > 0
  F4 WIKI vs Yahoo  : for tickers carried by both sources (identity 'same'), monthly returns compared on the overlap
                      (median |diff|, share of months with |diff| > 5 %)
Rule (WINNERS_SPEC §5e, replaces §5d): flags are CANDIDATES for review, not corrections. A price is changed only with
evidence, and every change is written to data/smallcap/price_corrections.csv (original, corrected, evidence, date):
  - F0: a non-positive adjusted close while Yahoo's raw close is positive is a vendor adjustment error → that day's
    adjusted price set missing (the security is NOT dropped; the missing days follow the missing-data / exit rules)
  - F2: unresolved pending independent corporate-action/price evidence; no automatic rescaling.
    Codex v2 removes the unsupported rule that flattened any jump near a split.
  - F2 without a split record, F1, F3: KEPT as they are (may be real moves); reported, and a diagnostic exam run that
    additionally removes F1 prints and F3 runs is reported next to the primary run
Output: data/smallcap/quality_flags.csv, data/smallcap/price_corrections.csv, results/winners_holdout/data_audit.json
"""
import json, os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, 'data', 'smallcap')
OUT = os.path.join(HERE, 'results', 'winners_holdout')
os.makedirs(OUT, exist_ok=True)
RATIOS = [2, 3, 4, 5, 8, 10, 15, 20]


def flags_for(s, dv):
    s = s.dropna()
    out = []
    bad = s[s <= 0]
    for d in bad.index:
        out.append((d, 'F0_nonpositive_price', d))                 # removed (a price of 0 or below is not a quote)
    s = s[s > 0]
    if len(s) < 5:
        return out
    v = s.values
    r = v[1:] / v[:-1]
    idx = s.index
    for i in range(1, len(v)):
        ratio = v[i] / v[i - 1]
        if not np.isfinite(ratio) or ratio <= 0:
            continue
        # F1 spike-reversal
        if abs(ratio - 1) >= 0.40:
            fut = v[i + 1:i + 4]
            back = np.where(np.abs(fut / v[i - 1] - 1) <= 0.10)[0] if len(fut) else []
            if len(back):
                out.append((idx[i], 'F1_spike_reversal', idx[i + 1 + back[0]]))      # bad print(s): idx[i] … day before reversal
                continue
            # F2 split-like and not reversed
            for k in RATIOS:
                for target in (k, 1 / k):
                    if abs(ratio / target - 1) <= 0.03:
                        out.append((idx[i], 'F2_split_like', ratio))
                        break
                else:
                    continue
                break
    # F3 stale runs (>= 10 identical sessions) — reported with start and end
    same = np.r_[False, v[1:] == v[:-1]]
    i = 1
    while i < len(v):
        if same[i]:
            j = i
            while j + 1 < len(v) and same[j + 1]:
                j += 1
            if j - i + 2 >= 10 and dv is not None and (dv.reindex(idx[i-1:j+1]).fillna(0) > 0).all():
                out.append((idx[i - 1], 'F3_stale_run', idx[j]))
            i = j + 1
        else:
            i += 1
    return out


def corrections(F, A):
    """Evidence-based corrections only (WINNERS_SPEC §5e)."""
    import datetime
    now = datetime.datetime.now().isoformat(timespec='seconds')
    rows = []
    for t, g in F[F.flag == 'F0_nonpositive_price'].groupby('ticker'):
        p = os.path.join(HERE, 'data', 'raw_smallcap', f'{t}.json')
        raw_ok = False
        if os.path.exists(p):
            j = json.load(open(p))
            c = pd.Series(j['close'], index=pd.to_datetime(j['dates']))
            raw_ok = bool((c.reindex(pd.to_datetime(g.date)) > 0).all())
        d = pd.to_datetime(g.date).sort_values()
        rows.append({'ticker': t, 'start': d.min().date(), 'end': d.max().date(), 'action': 'set_missing_days',
                     'days': len(d), 'factor': np.nan,
                     'original': f'adjclose <= 0 on {len(d)} days (min {A[t].reindex(d).min():.4g})',
                     'corrected': 'missing',
                     'evidence': 'non-positive adjusted close' + ('; Yahoo raw close positive on those days → vendor adjustment error' if raw_ok else ''),
                     'processed_at': now})
    # A nearby split does not prove that the adjusted series is wrong, its direction,
    # or its correction factor. Do not flatten a return using the observed jump.
    # These cases stay in the unresolved quality ledger until independently verified.
    unresolved = F[F.flag == 'F2_split_like'].copy()
    unresolved['audit_status'] = 'UNRESOLVED: split-date proximity is not a verified adjustment factor'
    unresolved.to_csv(os.path.join(D, 'unresolved_split_candidates.csv'), index=False)
    C = pd.DataFrame(rows, columns=['ticker', 'start', 'end', 'action', 'days', 'factor', 'original', 'corrected', 'evidence', 'processed_at'])
    C.to_csv(os.path.join(D, 'price_corrections.csv'), index=False)
    print('corrections:', C.action.value_counts().to_dict(), flush=True)
    return C


def main():
    A = pd.read_parquet(os.path.join(D, 'daily_adj.parquet'))
    DV = pd.read_parquet(os.path.join(D, 'daily_dv.parquet'))
    src = pd.read_csv(os.path.join(D, 'price_source.csv'), index_col=0).source
    rows = []
    for s in A.columns:
        if src.get(s) == 'sp_store':
            continue                                   # S&P store: already identity/integrity-audited
        for d, kind, ratio in flags_for(A[s], DV[s] if s in DV else None):
            is_d = kind in ('F3_stale_run', 'F1_spike_reversal', 'F0_nonpositive_price')
            rows.append({'ticker': s, 'date': d.date(), 'flag': kind, 'ratio': np.nan if is_d else ratio,
                         'end': ratio.date() if is_d else None, 'source': src.get(s)})
    F = pd.DataFrame(rows, columns=['ticker', 'date', 'flag', 'ratio', 'end', 'source'])
    F.to_csv(os.path.join(D, 'quality_flags.csv'), index=False)
    corrections(F, A)
    # F4 WIKI vs Yahoo agreement on overlapping tickers
    W = pd.read_parquet(os.path.join(HERE, 'data', 'wiki_bulk', 'wiki_prices.parquet'), columns=['ticker', 'date', 'adj_close'])
    Wm = {t: g.set_index('date').adj_close.resample('ME').last() for t, g in W.groupby('ticker')}
    ydir = os.path.join(HERE, 'data', 'raw_smallcap')
    diffs = []
    for f in sorted(os.listdir(ydir)):
        if not f.endswith('.json') or f.startswith('_'):
            continue
        t = f[:-5]
        if t not in Wm:
            continue
        j = json.load(open(os.path.join(ydir, f)))
        y = pd.Series(j['adjclose'], index=pd.to_datetime(j['dates'])).resample('ME').last()
        wm = Wm[t]
        ov = y.index.intersection(wm.index)
        if len(ov) < 13:
            continue
        a, b = y.loc[ov].pct_change(fill_method=None), wm.loc[ov].pct_change(fill_method=None)
        c = a.corr(b)
        if not (c >= 0.9):
            continue                                   # different companies (handled by the identity rule)
        dd = (a - b).abs().dropna()
        diffs.append({'ticker': t, 'months': len(dd), 'median_abs_diff': dd.median(), 'share_gt_5pct': (dd > 0.05).mean()})
    Df = pd.DataFrame(diffs)
    Df.to_csv(os.path.join(D, 'wiki_vs_yahoo_monthly.csv'), index=False)
    summ = {'securities_checked': int(sum(src.get(s) != 'sp_store' for s in A.columns)),
            'flags_by_type': F.flag.value_counts().to_dict(), 'securities_flagged': int(F.ticker.nunique()),
            'wiki_vs_yahoo_tickers': int(len(Df)),
            'wiki_vs_yahoo_median_abs_monthly_diff': float(Df.median_abs_diff.median()) if len(Df) else None,
            'wiki_vs_yahoo_share_months_gt_5pct': float((Df.share_gt_5pct * Df.months).sum() / Df.months.sum()) if len(Df) else None}
    json.dump(summ, open(os.path.join(OUT, 'data_audit.json'), 'w'), indent=1, default=str)
    print(json.dumps(summ, indent=1, default=str))


if __name__ == '__main__':
    main()
