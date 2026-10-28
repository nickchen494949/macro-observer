#!/usr/bin/env python3
"""
build_gap_ledger.py — one row per S&P member ticker that is NOT fully usable in the backtest:
what is missing, which months, which sources were tried, why it could not be filled.

Inputs: results/coverage_detail.csv (written by backtest.py), source logs, identity_resolutions.csv.
Outputs: results/gap_ledger.csv, results/gap_summary_by_year.csv, printed summary.
"""
import json, os

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
D, R = os.path.join(HERE, 'data'), os.path.join(HERE, 'results')


def jload(p):
    return json.load(open(p)) if os.path.exists(p) else {}


def main():
    cov = pd.read_csv(os.path.join(R, 'coverage_detail.csv'), parse_dates=['month'])
    yahoo_failed = jload(os.path.join(D, 'raw', '_failed.json'))
    tiingo = jload(os.path.join(D, 'raw_tiingo', '_log.json'))
    wiki = jload(os.path.join(D, 'raw_wiki', '_log.json'))
    wiki_chk = jload(os.path.join(D, 'raw_wiki_check', '_log.json'))
    idr = pd.read_csv(os.path.join(D, 'identity_resolutions.csv'))
    idr = idr.groupby('ticker').evidence.apply(lambda s: ' | '.join(s)).to_dict()
    first_px = {}
    for d_ in ['raw', 'raw_tiingo', 'raw_wiki']:
        p = os.path.join(D, d_)
        for f in os.listdir(p):
            if f.endswith('.json') and not f.startswith('_'):
                dd = json.load(open(os.path.join(p, f)))
                if dd['dates']:
                    k = f[:-5]
                    first_px[k] = min(first_px.get(k, dd['dates'][0]), dd['dates'][0])
    sp = pd.read_csv(os.path.join(D, 'sp500_ticker_start_end.csv'), parse_dates=['start_date'])
    sp['ticker'] = sp.ticker.str.replace('.', '-', regex=False)
    first_spell = sp.groupby('ticker').start_date.min()

    bad = cov[cov.reason != 'eligible']
    rows = []
    for (tk, reason), g in bad.groupby(['ticker', 'reason']):
        months = g.month.sort_values()
        y = 'Yahoo: ' + (f"failed ({yahoo_failed[tk]})" if tk in yahoo_failed else
                         'file exists' if os.path.exists(os.path.join(D, 'raw', f'{tk}.json')) else 'not requested')
        t = 'Tiingo: ' + str(tiingo.get(tk, 'not requested'))
        w = 'WIKI: ' + str(wiki.get(tk, wiki_chk.get(tk, 'not requested')))
        kind = reason
        if reason.startswith('insufficient_history'):
            fp = first_px.get(tk)
            fs = first_spell.get(tk)
            kind = ('insufficient_history: recent listing / spin-off (not a data gap)'
                    if fp and fs is not None and pd.Timestamp(fp) > fs - pd.Timedelta(days=400)
                    else 'insufficient_history: possible data gap')
        rows.append({'ticker': tk, 'problem': kind, 'months': len(months), 'first_month': months.iloc[0].date(),
                     'last_month': months.iloc[-1].date(), 'sector': g.sector.mode().iloc[0],
                     'sources_tried': '; '.join([y, t, w, 'SEC current ticker (resolve_successors.py)', 'rename aliases']),
                     'identity_evidence': idr.get(tk, '')})
    led = pd.DataFrame(rows).sort_values(['problem', 'months'], ascending=[True, False])
    led.to_csv(os.path.join(R, 'gap_ledger.csv'), index=False)
    # summary by year (member-months)
    cov['year'] = cov.month.dt.year
    real_gap = cov.reason.isin(['no_price_data_at_source', 'no_price_at_t (source history truncated / ticker re-used)',
                                'untrusted_spell (held price belongs to another / re-listed security)', 'sector_unknown'])
    ys = cov.assign(gap=real_gap).groupby('year').agg(member_months=('ticker', 'size'), gap_months=('gap', 'sum'))
    ys['gap_pct'] = (ys.gap_months / ys.member_months * 100).round(2)
    ys.to_csv(os.path.join(R, 'gap_summary_by_year.csv'))
    print('tickers with any gap (excl. recent listings):',
          led[~led.problem.str.contains('recent listing')].ticker.nunique())
    print(led.groupby('problem').ticker.nunique().to_string())
    print('member-months total', int(ys.member_months.sum()), 'gap', int(ys.gap_months.sum()),
          f"({ys.gap_months.sum() / ys.member_months.sum():.2%})")
    print(ys.to_string())


if __name__ == '__main__':
    main()
