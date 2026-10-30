#!/usr/bin/env python3
"""
pit_truncation_test.py — "pretend it is date C" test for look-ahead.

For several cut-off dates C: delete every price after C, rebuild the whole pipeline (integrity checks,
ticker aliases, spell trust, sectors, signals) and re-select. Every pick formed at or before C must be
IDENTICAL to the pick made with the full dataset. Any difference = information from after C leaked in.
(Membership and sector inputs are dated histories; they are also cut at C inside the engine by date.)
"""
import os, sys

import pandas as pd

import backtest as bt

CUTS = ['2011-06-30', '2014-12-31', '2018-03-31', '2021-04-30', '2024-06-30', '2026-01-31']


def picks(cutoff=None):
    daily, P, aliases, bad = bt.load_prices(cutoff)
    form = P.index[(P.index >= pd.Timestamp(bt.START) - pd.offsets.MonthEnd(1)) &
                   (P.index <= pd.Timestamp(bt.END) - pd.offsets.MonthEnd(1))]
    if cutoff is not None:
        form = form[form <= pd.Timestamp(cutoff)]
    members_raw, _ = bt.load_membership(form)
    members = {t: {x for x in m if not any(a <= t <= b for a, b in bad.get(x, []))} for t, m in members_raw.items()}
    sec_df = bt.build_sector_table(aliases)          # SAME preprocessing as production backtest.py
    secP, _ = bt.build_panel(sec_df, form)
    eng = bt.Engine(P, daily, members, secP, form)
    out = {}
    res = bt.load_resolutions()
    for name, cfg in {'SPEC': bt.SPEC, 'ETF': {**bt.SPEC, 'score': 'etf'},
                      'GRIDPT': dict(look=9, n_sec=3, n_stk=10, score='ew'), 'NOFILTER': bt.SPEC}.items():
        df = eng.run(cfg, bt.Prices(daily, P, 0), res, sector_filter=(name != 'NOFILTER'))
        out[name] = dict(zip(df.formation, df.picks))
    return out


def main():
    # freeze the raw files for the duration of the test (downloads may still be running)
    import shutil, tempfile
    snap = os.path.join(tempfile.gettempdir(), 'sector_momentum_raw_snapshot')
    shutil.rmtree(snap, ignore_errors=True)
    shutil.copytree(bt.RAW, snap)
    bt.RAW = snap
    if os.path.isdir(bt.RAW_TIINGO):
        snap_t = snap + '_tiingo'
        shutil.rmtree(snap_t, ignore_errors=True)
        shutil.copytree(bt.RAW_TIINGO, snap_t)
        bt.RAW_TIINGO = snap_t
    if os.path.isdir(bt.RAW_WIKI):
        snap_w = snap + '_wiki'
        shutil.rmtree(snap_w, ignore_errors=True)
        shutil.copytree(bt.RAW_WIKI, snap_w)
        bt.RAW_WIKI = snap_w
    full = picks(None)
    bad_total = 0
    for c in CUTS:
        cut = picks(c)
        for name in full:
            diff = [(t.date(), cut[name].get(t), full[name][t]) for t in full[name] if t <= pd.Timestamp(c)
                    and cut[name].get(t) != full[name][t]]
            n = sum(1 for t in full[name] if t <= pd.Timestamp(c))
            print(f'cut {c} {name:6s}: {n} formation months compared, {len(diff)} differ', flush=True)
            for d in diff[:5]:
                print('    ', d)
            bad_total += len(diff)
    print('RESULT:', 'PASS' if bad_total == 0 else f'FAIL ({bad_total} differing picks)')
    sys.exit(0 if bad_total == 0 else 1)


if __name__ == '__main__':
    main()
