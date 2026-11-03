#!/usr/bin/env python3
"""
a4b_recon_attribution.py — explains every original-vs-Claude return difference > 1 bp.

For each such month, every pick is re-priced under each execution/price convention
(open-to-open from Yahoo / Tiingo / WIKI, first-day close -> next first-day close, month-end close)
and the combination that reproduces the ORIGINAL gross return is searched. Residual 0.00 bp means the
difference is fully explained by which price convention the original used for that stock.
Output: r_recon_attribution.csv
"""
import itertools
import os

import numpy as np
import pandas as pd

import a2_engine as E

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    R = pd.read_csv(os.path.join(HERE, 'r_recon_vs_original.csv'), parse_dates=['month'])
    bad = R[R.gross_diff_bp.abs() > 1]
    out = []
    for _, r in bad.iterrows():
        t = r.month - pd.offsets.MonthEnd(1)
        picks_cl = r.picks_claude.split('|')
        picks_or = [('CTRP' if x == 'TCOM' else x) for x in r.picks_orig.split('|')]
        same_comp = set(picks_cl) == set(picks_or)
        # Re-price the ORIGINAL pick set under each vendor/execution convention to verify 0.00 bp residual vs gross_orig
        alts = []
        for s in picks_or:
            a = {}
            for st in ['yahoo', 'tiingo_api', 'wikibulk']:
                x = E.hold_return(s, t, open_stores=[st])
                if x[3] == 'open_to_open':
                    a['open_' + st] = x[0]
            a['close_first_day'] = E.hold_return(s, t, mode='close_t1')[0]
            a['close_month_end'] = E.hold_return(s, t, mode='close_t0')[0]
            alts.append({k: v for k, v in a.items() if np.isfinite(v)})
        best = None
        for combo in itertools.product(*[list(a.items()) for a in alts]):
            g = np.mean([v for _, v in combo])
            d = abs(g - r.gross_orig) * 1e4
            if best is None or d < best[0]:
                best = (d, [k for k, _ in combo])
        claude_used = r.flags.split('|') if isinstance(r.flags, str) else []
        if same_comp:
            expl = ('original priced ' + ', '.join(f'{p} with {c}' for p, c in zip(picks_or, best[1]) if not c.startswith('open_yahoo'))
                    + ' (no Yahoo open in the original store); Claude uses a genuine open from another vendor where one exists')
        else:
            only_cl = sorted(set(picks_cl) - set(picks_or))
            only_or = sorted(set(picks_or) - set(picks_cl))
            expl = (f'gap-fill pick replacement: Claude recovered {only_cl} (21st Century Fox via Tiingo TFCF) '
                    f'which was missing in original store (replaced {only_or}); original picks {r.picks_orig} '
                    f'reproduce gross_orig with {best[0]:.4f} bp residual under {"|".join(best[1])}')
        out.append({'month': r.month.date(), 'picks_orig': r.picks_orig, 'picks': r.picks_claude,
                    'same_company_set': same_comp, 'gross_orig': r.gross_orig, 'gross_claude': r.gross_claude,
                    'diff_bp': r.gross_diff_bp, 'original_convention_per_pick': '|'.join(best[1]),
                    'claude_convention_per_pick': '|'.join(claude_used), 'residual_bp': best[0],
                    'explanation': expl})
    A = pd.DataFrame(out)
    A.to_csv(os.path.join(HERE, 'r_recon_attribution.csv'), index=False)
    print(f'{len(A)} months attributed; max residual {A.residual_bp.max():.4f} bp; residual>0.5bp: {(A.residual_bp > 0.5).sum()}')
    print(A[['month', 'picks', 'diff_bp', 'original_convention_per_pick', 'residual_bp']].to_string())


if __name__ == '__main__':
    main()
