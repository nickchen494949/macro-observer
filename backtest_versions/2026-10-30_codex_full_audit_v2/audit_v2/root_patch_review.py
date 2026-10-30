"""Independent reviewer counterexamples for root-owned shared changes."""
import json, sys, hashlib
from pathlib import Path
import pandas as pd
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'research/sector_stock_momentum'
sys.path.insert(0, str(SRC))
import winners_tracks as wt
import earnings_factor as ear
import backtest as bt
from ml2_features import cashflow_ttm
checks = []
def check(name, fn):
    try:
        fn(); checks.append({'name': name, 'status': 'PASS'})
    except Exception as e:
        checks.append({'name': name, 'status': 'FAIL', 'reason': repr(e)})
def cash_empty():
    t = pd.Timestamp('2020-01-31'); m = t + pd.offsets.MonthEnd(1)
    class Px:
        def ret(self, *args): return (0.2, 'ok')
    S = {'px': Px(), 'res': {}, 'rf': pd.Series({m: 0.01})}
    d = wt.run_weights(S, {t: {}})
    assert np.isclose(d.net.iloc[0], .01) and d.exposure.iloc[0] == 0
    d = wt.run_weights(S, {t: {'A': .5}})
    assert np.isclose(d.net.iloc[0], 1.105 / 1.0005 - 1)
def tranche_exit_cash():
    t = pd.Timestamp('2020-01-31'); m = t + pd.offsets.MonthEnd(1)
    class Px:
        def ret(self, *args): return (0.0, 'delisted_in_month')
    d = wt.tranche_ledger({'px': Px(), 'res': {}, 'rf': pd.Series({m: .1})}, {t: {'A': 1}}, hold=2)
    assert np.isclose(d.net.iloc[0], .5 * 1.1 + .5 / 1.001 - 1)
def ear_bounds():
    t = pd.Timestamp('2021-06-30')
    X = pd.DataFrame({'t': [t], 'ticker': ['A'], 'cik': [1.]})
    E = pd.DataFrame({'ticker': ['A'] * 3, 'cik': [1] * 3, '_ear_segment': [1.] * 3,
                      'R': pd.to_datetime(['2020-01-01', '2021-03-01', '2021-06-01']),
                      'public': pd.to_datetime(['2020-01-02', '2021-03-02', '2021-06-02']), 'ear': [.1, .2, .3]})
    old = bt.SEG_M
    try:
        bt.SEG_M = pd.DataFrame({'A': [1.]}, index=[t])
        a = ear.attach(X, E)
        assert a.ear.iloc[0] == .3 and np.isnan(a.ear_sum4.iloc[0])
        E.loc[0, ['R', 'public']] = [pd.Timestamp('2021-01-01'), pd.Timestamp('2021-01-02')]
        assert np.isclose(ear.attach(X, E).ear_sum4.iloc[0], .6)
        bt.SEG_M.loc[t, 'A'] = 2
        assert ear.attach(X, E).ear.isna().all()
    finally:
        bt.SEG_M = old
def cfo_fixture(missing=False):
    vals = [(4, '2020-12-31', 100., '2021-02-01'), (1, '2021-03-31', 60., '2021-05-01')]
    if not missing:
        vals += [(1, '2020-03-31', 40., '2021-06-01')]
    return pd.DataFrame([{'cik': 1, 'tag': 'NetCashProvidedByUsedInOperatingActivities', 'qtrs': q,
                         'ddate': pd.Timestamp(d), 'value': v, 'filed': pd.Timestamp(f),
                         'uom': 'USD', 'is_first_report': True} for q, d, v, f in vals])
def cfo_known():
    r = cashflow_ttm(cfo_fixture())
    x = r[r.ddate == pd.Timestamp('2021-03-31')].iloc[-1]
    assert x.cfo_ttm == 120 and x.av_cfo_ttm == pd.Timestamp('2021-06-02')
    early = r[(r.ddate == pd.Timestamp('2021-03-31')) & (r.av_cfo_ttm <= pd.Timestamp('2021-05-31'))]
    assert len(early) and np.isnan(early.iloc[-1].cfo_ttm)
    cut = cashflow_ttm(cfo_fixture()[lambda d: d.filed <= pd.Timestamp('2021-05-31')])
    current = cut[cut.ddate == pd.Timestamp('2021-03-31')]
    assert len(current) and np.isnan(current.iloc[-1].cfo_ttm)
def cfo_missing():
    r = cashflow_ttm(cfo_fixture(True))
    current = r[r.ddate == pd.Timestamp('2021-03-31')]
    assert len(current) and current.cfo_ttm.isna().all(), 'missing current-quarter TTM must invalidate old FY, not disappear'
for name, fn in [('cash_and_partial_exposure_balance', cash_empty), ('terminal_proceeds_no_full_month_interest', tranche_exit_cash),
                  ('ear_three_event_age_and_identity', ear_bounds), ('cfo_ttm_value_and_latest_component_date', cfo_known),
                  ('cfo_missing_component_invalidation', cfo_missing)]:
    check(name, fn)
report = {'reviewer': 'legacy_ml_writer, independent of root-owned implementations', 'checks': checks,
          'source_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
                           [SRC / n for n in ['winners_tracks.py', 'winners_holdout.py', 'earnings_factor.py', 'ml2_run.py', 'ml2_features.py']]}}
(ROOT / 'audit_v2/root_patch_review.json').write_text(json.dumps(report, indent=2))
print(json.dumps(checks))
