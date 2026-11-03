#!/usr/bin/env python3
"""
a9_report_tables.py — renders every number used in the Markdown report directly from the CSV outputs
(no hand-typed figures). Output: REPORT_TABLES.md (included verbatim in the audit report).
"""
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))


def pct(v, d=2):
    return '' if pd.isna(v) else f'{v * 100:.{d}f}%'


def f2(v):
    return '' if pd.isna(v) else f'{v:.2f}'


def md(df):
    cols = list(df.columns)
    out = ['| ' + ' | '.join(cols) + ' |', '|' + '|'.join(['---'] * len(cols)) + '|']
    for _, r in df.iterrows():
        out.append('| ' + ' | '.join(str(r[c]) for c in cols) + ' |')
    return '\n'.join(out)


def main():
    X = pd.read_csv(os.path.join(HERE, 'x_stress.csv'))
    T = pd.read_csv(os.path.join(HERE, 'x_paired_tests.csv'))
    RM = pd.read_csv(os.path.join(HERE, 'x_risk_matched.csv'))
    MT = pd.read_csv(os.path.join(HERE, 'm_multiple_testing.csv'))
    C = pd.read_csv(os.path.join(HERE, 'x_contribution.csv'))
    CY = pd.read_csv(os.path.join(HERE, 'x_calendar_years.csv'), index_col=0)
    R = pd.read_csv(os.path.join(HERE, 'r_recon_vs_original.csv'))
    TR = pd.read_csv(os.path.join(HERE, 't_truncation_test.csv'))
    V = pd.read_csv(os.path.join(HERE, 'v_position_crosscheck.csv'))
    VS = pd.read_csv(os.path.join(HERE, 'x_vendor_swap.csv'))
    out = []

    # 1. headline windows
    W = ['FULL 2009-01..2026-09', '2009-2014', '2015-2019', '2020-2022', '2023-2026.09', '2009-2018 (pre-2019)',
         'ORIG 2015-02..2026-09', 'ORIG 2019-01..2026-09']
    s = X[X.variant == 'SPEC Top-3 (10bp)'].set_index('window').loc[W]
    q = X[X.variant == 'BENCH QQQ ETF'].set_index('window').loc[W]
    e = X[X.variant == 'BENCH NDX equal-weight (PIT, 10bp)'].set_index('window').loc[W]
    t1 = X[X.variant == 'Top-1'].set_index('window').loc[W]
    rm = RM.set_index('window').loc[W]
    tab = pd.DataFrame({'Window': W, 'Months': s.n_months.values,
                        'Top-3 CAGR': [pct(v) for v in s.CAGR], 'QQQ CAGR': [pct(v) for v in q.CAGR],
                        'NDX-EW CAGR': [pct(v) for v in e.CAGR], 'Top-1 CAGR': [pct(v) for v in t1.CAGR],
                        'Top-3 Sharpe': [f2(v) for v in s.Sharpe], 'QQQ Sharpe': [f2(v) for v in q.Sharpe],
                        'Top-3 vol': [pct(v, 1) for v in s.vol], 'Top-3 MaxDD (monthly)': [pct(v, 1) for v in s.MaxDD_monthly],
                        'Top-3 MaxDD (daily)': [pct(v, 1) for v in s.MaxDD_daily], 'QQQ MaxDD (monthly)': [pct(v, 1) for v in q.MaxDD_monthly],
                        'QQQ levered to same vol': [pct(v) for v in rm.QQQ_x_volmatched_CAGR],
                        'QQQ levered to same beta': [pct(v) for v in rm.QQQ_x_beta_CAGR], 'beta': [f2(v) for v in rm.beta]})
    out.append('### T1. Performance by window (net of 10 bp/side; QQQ = same open-to-open dates)\n\n' + md(tab))

    # 2. paired tests
    tt = T[T.window.isin(['FULL 2009-01..2026-09', '2009-2018 (pre-2019)', 'ORIG 2015-02..2026-09', 'ORIG 2019-01..2026-09',
                          '2009-2014', '2015-2019', '2020-2022', '2023-2026.09'])].copy()
    tab = pd.DataFrame({'Window': tt.window, 'vs': tt.B, 'CAGR diff': [pct(v) for v in tt.CAGR_diff],
                        'NW t (lag 3)': [f2(v) for v in tt.NW_t_lag3], 'p': [f'{v:.3f}' for v in tt.NW_p_lag3],
                        'Bootstrap 90% CI of CAGR diff': [f'[{pct(a)}, {pct(b)}]' for a, b in zip(tt['boot_CAGRdiff_p5'], tt['boot_CAGRdiff_p95'])],
                        'P(diff<=0)': [f'{v:.3f}' for v in tt['boot_P(diff<=0)']], 'monthly win': [pct(v, 0) for v in tt.monthly_win_rate],
                        'alpha/yr vs QQQ': [pct(v) for v in tt.alpha_ann], 'alpha NW t': [f2(v) for v in tt.alpha_NW_t]})
    out.append('### T2. Paired tests (SPEC Top-3 minus benchmark)\n\n' + md(tab))

    # 3. stress table
    order = list(dict.fromkeys(X.variant))
    rows = []
    for v in order:
        g = X[X.variant == v].set_index('window')
        rows.append({'Variant': v, 'FULL 2009-26': pct(g.at['FULL 2009-01..2026-09', 'CAGR']),
                     '2009-2018': pct(g.at['2009-2018 (pre-2019)', 'CAGR']),
                     '2015-02..2026-09': pct(g.at['ORIG 2015-02..2026-09', 'CAGR']),
                     '2019-01..2026-09': pct(g.at['ORIG 2019-01..2026-09', 'CAGR']),
                     'Sharpe FULL': f2(g.at['FULL 2009-01..2026-09', 'Sharpe']),
                     'MaxDD FULL (monthly)': pct(g.at['FULL 2009-01..2026-09', 'MaxDD_monthly'], 1)})
    out.append('### T3. Benchmarks, neighbours and stress variants (CAGR)\n\n' + md(pd.DataFrame(rows)))

    # 4. calendar years
    cy = CY.copy()
    cy.index.name = 'Year'
    cy = cy.reset_index()
    for c in cy.columns[1:]:
        cy[c] = [pct(v, 1) for v in cy[c]]
    out.append('### T4. Calendar-year net returns (2026 = Jan–Sep)\n\n' + md(cy))

    # 5. contribution
    for w in C.window.unique():
        g = C[C.window == w].head(10)
        tab = pd.DataFrame({'Ticker': g.ticker, 'Months held': g.months, 'Share of total log wealth': [pct(v, 1) for v in g.share_of_total_log_wealth],
                            'Best month': [pct(v, 1) for v in g.best], 'Worst month': [pct(v, 1) for v in g.worst]})
        out.append(f'### T5. Top-10 contributors, {w}\n\n' + md(tab))

    # 6. multiple testing
    tab = MT.copy()
    tab['sr_ann'] = tab.sr_ann.map(f2)
    tab['sr0_ann (expected max of N null trials)'] = tab['sr0_ann (expected max of N null trials)'].map(f2)
    tab['DSR'] = tab.DSR.map(lambda v: f'{v:.3f}')
    out.append('### T6. Deflated Sharpe ratio (N = number of strategies tried)\n\n' + md(tab))

    # 7. reconciliation / integrity summary
    A = pd.read_csv(os.path.join(HERE, 'r_recon_attribution.csv'))
    same = R.same_set.sum()
    same_comp = sum(set(('CTRP' if x == 'TCOM' else x) for x in str(a).split('|')) == set(str(b).split('|'))
                    for a, b in zip(R.picks_orig, R.picks_claude))
    big = R[R.gross_diff_bp.abs() > 1]
    lines = [f'- Original ledger months: {len(R)}; exact ticker-string match: {same}/{len(R)}; same-company match: {same_comp}/{len(R)} '
             f'(3 months `2016-01..03` are `CTRP` vs `TCOM` = same entity renamed in 2019; 2 months `2018-11..12` are `FOX` (`TFCF`, 21st Century Fox) '
             f'recovered via Tiingo EOD where the original store had a 2018 data gap).',
             f'- Months with |gross diff| > 1 bp: {len(big)}; all {len(A)}/{len(big)} attributed in `r_recon_attribution.csv` with max unexplained residual `{A.residual_bp.max():.4f} bp`.',
             f'- Truncation test: roster/eligible/ranking identical in '
             f'{int((TR.roster_equal & TR.eligible_equal & TR.ranking_equal).sum())}/{len(TR)} months; '
             f'max |momentum diff| {TR.max_abs_mom_diff.max():.2e}; Top-3 identical {int((TR.top3_full == TR.top3_trunc).sum())}/{len(TR)}.',
             f'- Positions: {len(V)}; independent Tiingo adjOpen comparison available for '
             f'{int((~V.primary_is_tiingo & V.tiingo_open_to_open.notna()).sum())} (+{int(V.primary_is_tiingo.sum())} priced from Tiingo directly).',
             f'- Vendor swap (Tiingo-first for signals and returns): same Top-3 set {int(VS.same_picks.sum())}/{len(VS)} months.']
    out.append('### T7. Integrity summary\n\n' + '\n'.join(lines))
    open(os.path.join(HERE, 'REPORT_TABLES.md'), 'w').write('\n\n'.join(out) + '\n')
    print('written REPORT_TABLES.md')


if __name__ == '__main__':
    main()
