"""Independent, no-download counterexamples for root-owned execution/ML fixes."""
from pathlib import Path
import hashlib
import json
import sys
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'research/sector_stock_momentum'
sys.path.insert(0, str(SRC))
import backtest as bt
import ml2_run as ml2

checks = []

def check(name, fn):
    try:
        detail = fn()
        checks.append({'name': name, 'status': 'PASS', 'detail': detail})
    except Exception as e:
        checks.append({'name': name, 'status': 'FAIL', 'reason': repr(e)})

def manual_entry_basis():
    ds = pd.to_datetime(['2020-01-31', '2020-02-03', '2020-02-28', '2020-03-02'])
    daily = pd.DataFrame({'SPY': 100., 'A': [100., 110., np.nan, np.nan]}, index=ds)
    forms = pd.to_datetime(['2020-01-31', '2020-02-29'])
    P = pd.DataFrame({'SPY': 100., 'A': [100., np.nan]}, index=forms)
    old = bt.SEG_D, bt.SEG_M
    try:
        bt.SEG_D = bt.SEG_M = None
        res = {(forms[0], 'A'): .1}  # terminal payout 110 / formation close 100 - 1
        close = bt.Prices(daily, P, 1).ret(forms[0], 'A', res)
        opened = ml2.OpenPrices(daily, P, daily.copy()).ret(forms[0], 'A', res)
        assert np.isclose(close[0], 0.), f'next close entry 110, payout 110: expected 0, got {close}'
        assert np.isclose(opened[0], 0.), f'next open entry 110, payout 110: expected 0, got {opened}'
        return {'next_close': close, 'next_open': opened}
    finally:
        bt.SEG_D, bt.SEG_M = old

def unknown_labels_not_training():
    forms = pd.date_range('2011-01-31', '2015-12-31', freq='ME')
    D = pd.DataFrame([{'t': t, 'ticker': s, 'mom_rank': i + 1, 'ret_oo': .1 * i,
                       'status_oo': 'ok', 'f': float(i)}
                      for t in forms for i, s in enumerate(['A', 'B'])])
    D.loc[(D.t == pd.Timestamp('2012-06-30')) & (D.ticker == 'A'), 'status_oo'] = 'source_gap'
    D.loc[(D.t == pd.Timestamp('2014-12-31')) & (D.ticker == 'A'), 'status_oo'] = 'unresolved'
    # If the implementation uses an explicit flag, it must agree with terminal status.
    D['label_resolved'] = ~D.status_oo.isin(['source_gap', 'unresolved'])
    class Px:
        sess = pd.bdate_range('2010-01-01', '2017-01-01')
    seen = []
    old = ml2.model_fit_predict, ml2.net_cagr, ml2.GRID, ml2.TEST_YEARS
    def record(kind, params, tr, te, cols):
        seen.append(tr.copy())
        return np.zeros(len(te))
    try:
        ml2.model_fit_predict = record
        ml2.net_cagr = lambda *a, **kw: 0.
        ml2.GRID = {'ridge': [{'alpha': 1.}]}
        ml2.TEST_YEARS = [2015]
        out, _ = ml2.walk_forward(D, {'px': Px()}, 'ridge', ['f'], 1)
        bad = sum(g.status_oo.isin(['source_gap', 'unresolved']).sum() for g in seen)
        assert bad == 0, f'{bad} unresolved labels reached training/refit'
        target = out[(out.t == pd.Timestamp('2014-12-31')) & (out.ticker == 'A')]
        assert len(target) == 1 and target.score.notna().all(), 'future unresolved outcome removed a test candidate'
        return {'fit_calls': len(seen), 'unknown_training_rows': int(bad), 'unknown_test_candidate_retained': True}
    finally:
        ml2.model_fit_predict, ml2.net_cagr, ml2.GRID, ml2.TEST_YEARS = old

def open_status_matrix():
    """All five return statuses x all four entry/exit open availability states.

    Close fallback oracle has a real entry of 110 and terminal/exit wealth 121.
    Source unknown statuses remain unknown even when an entry open exists.
    The matrix isolates dispatch/denominator handling; the real-price tests
    separately cover exact-day missing entry and no forward-filled execution.
    """
    ds = pd.to_datetime(['2020-01-31', '2020-02-03', '2020-02-28', '2020-03-02'])
    forms = pd.to_datetime(['2020-01-31', '2020-02-29'])
    daily = pd.DataFrame({'SPY': 100., 'A': [100., 110., 121., 121.]}, index=ds)
    P = pd.DataFrame({'SPY': 100., 'A': [100., 121.]}, index=forms)
    old = bt.SEG_D, bt.SEG_M
    rows = []
    try:
        bt.SEG_D = bt.SEG_M = None
        for status in ['ok', 'resolved_manual', 'delisted_in_month', 'source_gap', 'unresolved']:
            for have_entry in [False, True]:
                for have_exit in [False, True]:
                    O = daily.copy()
                    O.loc[ds[1], 'A'] = 90. if have_entry else np.nan
                    O.loc[ds[-1], 'A'] = 144. if have_exit else np.nan
                    px = ml2.OpenPrices(daily, P, O)
                    base = 121. / 110. - 1 if status != 'unresolved' else 0.
                    px.close1.ret = lambda *a, r=base, s=status: (r, s)
                    res = {(forms[0], 'A'): .21} if status == 'resolved_manual' else {}
                    got = px.ret(forms[0], 'A', res)
                    expected = base
                    if status == 'ok' and have_entry and have_exit:
                        expected = 144. / 90. - 1
                    elif status in ['resolved_manual', 'delisted_in_month'] and have_entry:
                        expected = 121. / 90. - 1
                    rows.append({'status': status, 'entry_open': have_entry, 'exit_open': have_exit,
                                 'expected': expected, 'got': got[0], 'returned_status': got[1]})
                    assert got[1] == status and np.isclose(got[0], expected), rows[-1]
        return {'cases': len(rows), 'unknown_status_preserved': True, 'rows': rows}
    finally:
        bt.SEG_D, bt.SEG_M = old

def missing_real_entry():
    ds = pd.to_datetime(['2020-01-31', '2020-02-03', '2020-02-28', '2020-03-02'])
    daily = pd.DataFrame({'SPY': 100., 'A': [100., np.nan, np.nan, np.nan]}, index=ds)
    forms = pd.to_datetime(['2020-01-31', '2020-02-29'])
    P = pd.DataFrame({'SPY': 100., 'A': [100., np.nan]}, index=forms)
    old = bt.SEG_D, bt.SEG_M, bt.WIKI_SYMS
    try:
        bt.SEG_D = bt.SEG_M = None
        bt.WIKI_SYMS = set()
        results = []
        for manual in [False, True]:
            res = {(forms[0], 'A'): .1} if manual else {}
            for px in [bt.Prices(daily, P, 1), ml2.OpenPrices(daily, P, daily.copy())]:
                got = px.ret(forms[0], 'A', res)
                assert got == (0., 'unresolved'), (manual, type(px).__name__, got)
                results.append({'manual_resolution': manual, 'execution': type(px).__name__, 'result': got})
        return results
    finally:
        bt.SEG_D, bt.SEG_M, bt.WIKI_SYMS = old

check('manual_terminal_return_execution_entry_basis', manual_entry_basis)
check('unknown_labels_excluded_from_fit_but_not_test_pool', unknown_labels_not_training)
check('open_price_status_availability_matrix', open_status_matrix)
check('missing_exact_day_entry_not_forward_filled', missing_real_entry)
report = {'reviewer': 'legacy_ml_writer, independent of root-owned patches', 'checks': checks,
          'source_sha256': {n: hashlib.sha256((SRC / n).read_bytes()).hexdigest()
                            for n in ['backtest.py', 'ml2_run.py']}}
(ROOT / 'audit_v2/root_scope_counterexamples.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
