#!/usr/bin/env python3
"""Regression tests for the portfolio ledgers (external audit 2026-10-29):
 1. daily NAV must follow the real price path inside a month (100 → 50 → 110 gives a −50 % daily drawdown);
 2. the 6-month tranche ledger must track drifting holdings (no hidden monthly rebalancing): A doubles then halves,
    B flat, tranches of 1/3 → monthly returns +16.67 %, −21.43 %, 0 %.
 3. unresolved exits are charged the stress return when a stress scenario is requested."""
import numpy as np
import pandas as pd

import backtest as bt
import winners_tracks as wt


class PX:
    def __init__(s, R):
        s.R = R

    def ret(s, t, sym, res):
        return s.R[(t, sym)]


def main():
    ok = True
    idx = pd.bdate_range('2020-01-27', '2020-02-28')
    v = np.full(len(idx), 100.0)
    k = np.where(idx > pd.Timestamp('2020-01-31'))[0]
    v[k[:len(k) // 2]] = np.linspace(100, 50, len(k) // 2)
    v[k[len(k) // 2:]] = np.linspace(50, 110, len(k) - len(k) // 2)
    df = pd.DataFrame([{'net': 0.10, 'gross': 0.10, 'exposure': 1.0, 'picks': 'A', 'weights': '1.0'}], index=[pd.Timestamp('2020-02-29')])
    nav = wt.daily_nav({'daily': pd.DataFrame({'A': v}, index=idx), 'rf': pd.Series(dtype=float)}, df)
    dd = float((nav / nav.cummax() - 1).min())
    ok &= abs(dd + 0.5) < 1e-6
    print('daily NAV drawdown', round(dd, 4), 'expected -0.5')
    t = pd.date_range('2020-01-31', periods=3, freq='ME')
    R = {(t[0], 'A'): (1.0, 'ok'), (t[0], 'B'): (0.0, 'ok'), (t[1], 'A'): (-0.5, 'ok'), (t[1], 'B'): (0.0, 'ok'),
         (t[2], 'A'): (0.0, 'ok'), (t[2], 'B'): (0.0, 'ok')}
    keep = bt.COST_PER_SIDE
    bt.COST_PER_SIDE = 0.0
    S = {'px': PX(R), 'res': {}, 'rf': pd.Series(0.0, index=t + pd.offsets.MonthEnd(1))}
    L = wt.tranche_ledger(S, {x: {'A': .5, 'B': .5} for x in t}, hold=3)
    got = L.net.round(4).tolist()
    ok &= got == [0.1667, -0.2143, 0.0]
    print('tranche ledger', got, 'expected [0.1667, -0.2143, 0.0]')
    R2 = {(t[0], 'A'): (0.0, 'unresolved')}
    S2 = {'px': PX(R2), 'res': {}, 'rf': pd.Series(0.0, index=t + pd.offsets.MonthEnd(1))}
    r = wt.run_weights(S2, {t[0]: {'A': 1.0}}, stress=-0.30)
    ok &= abs(r.net.iloc[0] + 0.30) < 1e-9
    print('stress on unresolved exit', r.net.iloc[0], 'expected -0.30')
    bt.COST_PER_SIDE = keep
    print('RESULT:', 'PASS' if ok else 'FAIL')
    raise SystemExit(0 if ok else 1)


if __name__ == '__main__':
    main()
