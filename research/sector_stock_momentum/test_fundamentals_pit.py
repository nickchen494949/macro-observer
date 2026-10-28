#!/usr/bin/env python3
"""Regression tests for the PIT fundamentals API (cases raised by the external audit 2026-10-28)."""
import numpy as np
from fundamentals_pit import load_eps, asof


def test_field_gating():
    # AMD 2012-Q1 revenue was first filed 2013-05-06 → must NOT be visible on 2012-05-10
    s = asof(load_eps('Information Technology'), '2012-05-10')
    r = s[s.ticker == 'AMD'].iloc[0]
    assert np.isnan(r.revenue) or r.filed_revenue + np.timedelta64(1, 'D') <= np.datetime64('2012-05-10'), r
    print('AMD gating OK:', r.period_end.date(), 'revenue', r.revenue, 'filed_revenue', r.filed_revenue)


def test_split_basis():
    p = load_eps('Information Technology')
    r = p[(p.ticker == 'NVDA') & (p.period_end.dt.strftime('%Y-%m') == '2024-07')].iloc[0]
    assert abs(r.eps_diluted_approx_ttm_adj - 2.131) < 0.01, r.eps_diluted_approx_ttm_adj
    print('NVDA split basis OK: TTM EPS (common basis) =', round(r.eps_diluted_approx_ttm_adj, 3))


if __name__ == '__main__':
    test_field_gating()
    test_split_basis()
    print('ALL PASS')
